"""Plano personalizado cobertura por cobertura: necessidade e faixa em reais de cada cobertura,
e o pacote BB mais próximo como forma de contratar (pacote + adicionais).

Determinístico, sem LLM. As faixas seguem "valor em risco" a partir dos dados do estabelecimento
(mínimo com valores ponderados/médios, máximo com cadastrados/pico). Onde as Condições Gerais
fixam período ou limite, a regra segue a cláusula; o resto são premissas da equipe, declaradas
abaixo e repetidas em cada regra_calculo. Não são critérios de subscrição da BB Seguros.
"""

import math

from agente import rag
from agente.contratos import CoberturaRecomendada, Perfil, PlanoPersonalizado, Plano
from agente.dados_base import Estabelecimento

# ---------- premissas da equipe (ajustáveis) ----------
TIPOS_ELETRICOS = {
    "EQUIPAMENTO_ELETRONICO", "EQUIPAMENTO_REFRIGERACAO", "EQUIPAMENTO_INFORMATICA", "SISTEMA_SEGURANCA",
    "EQUIPAMENTO_COZINHA", "EQUIPAMENTO_MEDICO", "EQUIPAMENTO_OFICINA", "MAQUINA", "EQUIPAMENTO_BELEZA", "LETREIRO",
}  # fmt: skip
TIPOS_PORTATEIS = {"EQUIPAMENTO_ELETRONICO", "EQUIPAMENTO_INFORMATICA", "EQUIPAMENTO_BELEZA", "EQUIPAMENTO_MEDICO"}
MESES_ALUGUEL = (6, 12)  # 12 = limite da cl. PERDA_PAGAMENTO_ALUGUEL-1.6; 6 = reparo típico (premissa)
MESES_DESPESAS_FIXAS = (3, 6)  # 6 meses = 180 dias, limite da cl. DESPESAS_FIXAS-2.1
FRACAO_VENDAVAL = (0.25, 0.5)  # vendaval costuma causar perda parcial (premissa)
RC_ESTABELECIMENTO_POR_PORTE = {"MICRO": (50_000, 100_000), "PEQUENA": (100_000, 200_000), "MEDIA": (200_000, 500_000)}
SALARIOS_RC_EMPREGADOR = (12, 36)  # de 1 a 3 anos do salário médio por evento (premissa)
VIDROS_POR_LOCALIZACAO = {"LOJA": (10_000, 30_000), "GALERIA": (10_000, 30_000), "SALA": (3_000, 10_000), "TORRE": (3_000, 10_000)}
VIDROS_PADRAO = (5_000, 15_000)
DIAS_UTEIS_MES = 22
FRACAO_ESTOQUE_REFRIGERADO = (0.2, 0.5)
FRACAO_ELETRICOS_SEM_CADASTRO = (0.2, 0.5)  # parte dos bens que é equipamento elétrico (premissa)  # parte do estoque que depende de refrigeração (premissa)

# Gatilhos dos adicionais
MINIMO_SUBTRAIVEL_ROUBO = 10_000  # estoque + portáteis para sugerir roubo fora do plano
MINIMO_FUNCIONARIOS_RC_EMPREGADOR = 17  # critério de referência do motor (modelo/criterios_referencia.json)
MINIMO_REFRIGERACAO = 0.5
MINIMO_DELIVERY = 0.5
MINIMO_RECEBIMENTO_FISICO = 0.3  # fração do faturamento recebida fora do digital
MINIMO_DINHEIRO_DIA = 2_000  # recebimento em espécie por dia para sugerir roubo de valores
MINIMO_RELEVANTE_ADICIONAL = 5_000  # adicional com faixa máxima abaixo disso não é sugerido
# Coerência financeira (o LEIA-ME do desafio pede tratar inconsistências)
MAXIMO_ALUGUEL_SOBRE_FATURAMENTO = 0.5
MAXIMO_DESPESA_SOBRE_FATURAMENTO = 1.0

CLAUSULAS = {
    "INCENDIO_RAIO_EXPLOSAO_FUMACA": ["INCENDIO_RAIO_EXPLOSAO_FUMACA-1.1.a", "CG-5.2.b"],
    "DANOS_ELETRICOS": ["DANOS_ELETRICOS-1.1"],
    "PERDA_PAGAMENTO_ALUGUEL": ["PERDA_PAGAMENTO_ALUGUEL-1.1", "PERDA_PAGAMENTO_ALUGUEL-1.6"],
    "RESPONSABILIDADE_CIVIL_ESTABELECIMENTO": ["RESPONSABILIDADE_CIVIL_ESTABELECIMENTO-1.1.a"],
    "DESPESAS_FIXAS": ["DESPESAS_FIXAS-1.1", "DESPESAS_FIXAS-2.1"],
    "ROUBO_FURTO_ARROMBAMENTO": ["ROUBO_FURTO_ARROMBAMENTO-1.1"],
    "VENDAVAL_EVENTOS_CORRELATOS": ["VENDAVAL_EVENTOS_CORRELATOS-1.1"],
    "RESPONSABILIDADE_CIVIL_EMPREGADOR": ["RESPONSABILIDADE_CIVIL_EMPREGADOR-1.1"],
    "QUEBRA_DE_VIDROS": ["QUEBRA_DE_VIDROS-1.1.a"],
    "DETERIORACAO_DE_MERCADORIAS_EM_AMBIENTES_FRIGORIFICADOS": ["DETERIORACAO_DE_MERCADORIAS_EM_AMBIENTES_FRIGORIFICADOS-1.1.a"],
    "DELIVERY": ["DELIVERY-1.1.a"],
    "ROUBO_OU_FURTO_DE_VALORES_MEDIANTE_ARROMBAMENTO": [
        "ROUBO_OU_FURTO_DE_VALORES_MEDIANTE_ARROMBAMENTO-1.1",
        "ROUBO_OU_FURTO_DE_VALORES_MEDIANTE_ARROMBAMENTO-2.1",
    ],
}


def _reais(valor: float) -> str:
    return f"R$ {valor:,.0f}".replace(",", ".")


def _faixa(minimo: float, maximo: float) -> tuple[float, float]:
    """Arredonda para milhares (mínimo para baixo, máximo para cima), mínimo de R$ 1.000."""
    minimo, maximo = sorted((max(minimo, 1000), max(maximo, 1000)))
    return float(math.floor(minimo / 1000) * 1000), float(math.ceil(maximo / 1000) * 1000)


class _Bens:
    def __init__(self, est: Estabelecimento):
        self.est = est

    def soma(self, campo: str, tipos: set[str] | None = None) -> float:
        return sum(getattr(b, campo) for b in self.est.bens if tipos is None or b.tipo in tipos)

    def confianca(self) -> str:
        total = self.soma("valor_ponderado")
        baixa = sum(b.valor_ponderado for b in self.est.bens if b.confianca_vinculo == "BAIXA")
        return "MEDIA" if total and baixa / total < 0.3 else "BAIXA"


def _faturamento_do_endereco(est: Estabelecimento) -> float:
    return est.faturamento_mensal_empresa / max(est.quantidade_estabelecimentos, 1)


def inconsistencias(est: Estabelecimento) -> list[str]:
    """Sinais financeiros que não fecham entre si; baixam a confiança e viram confirmação."""
    faturamento = _faturamento_do_endereco(est)
    achados = []
    if est.paga_aluguel and faturamento and est.valor_aluguel / faturamento > MAXIMO_ALUGUEL_SOBRE_FATURAMENTO:
        achados.append(
            f"aluguel ({_reais(est.valor_aluguel)}) acima de {MAXIMO_ALUGUEL_SOBRE_FATURAMENTO:.0%} "
            f"do faturamento do endereço ({_reais(faturamento)})"
        )
    if faturamento and est.despesa_fixa_mensal / faturamento > MAXIMO_DESPESA_SOBRE_FATURAMENTO:
        achados.append(
            f"despesa fixa ({_reais(est.despesa_fixa_mensal)}) maior que o faturamento do endereço ({_reais(faturamento)})"
        )
    return achados


def _dinheiro_por_dia(est: Estabelecimento) -> float:
    return _faturamento_do_endereco(est) * (1 - est.percentual_recebimentos_digitais) / DIAS_UTEIS_MES


# ---------- coberturas ----------


def _incendio(est: Estabelecimento, bens: _Bens) -> dict:
    minimo = bens.soma("valor_ponderado") + est.estoque_medio
    maximo = bens.soma("valor_cadastrado") + est.estoque_pico
    confirmar = "valores dos bens com vínculo de baixa confiança"
    if not est.paga_aluguel:
        confirmar += "; se o imóvel é próprio, o valor de reconstrução do prédio (não está na base)"
    return dict(
        faixa=_faixa(minimo, maximo),
        confianca=bens.confianca(),
        dados="bens cadastrados do endereço (ponderado e cadastrado), estoque médio e de pico",
        regra="conteúdo (cl. CG-5.2.b): mín = bens ponderados + estoque médio; máx = bens cadastrados + estoque de pico",
        justificativa=f"conteúdo estimado entre {_reais(minimo)} e {_reais(maximo)}",
        confirmar=confirmar,
    )


def _danos_eletricos(est: Estabelecimento, bens: _Bens) -> dict:
    minimo, maximo = bens.soma("valor_ponderado", TIPOS_ELETRICOS), bens.soma("valor_cadastrado", TIPOS_ELETRICOS)
    if not maximo:  # nenhum equipamento elétrico no cadastro: referência = parte do conteúdo
        a, b = FRACAO_ELETRICOS_SEM_CADASTRO
        return dict(
            faixa=_faixa(a * bens.soma("valor_ponderado"), b * bens.soma("valor_cadastrado")),
            confianca="BAIXA",
            dados="não há equipamento elétrico no cadastro; referência = bens do endereço",
            regra=f"{a:.0%} a {b:.0%} dos bens cadastrados (premissa da equipe)",
            justificativa="equipamentos elétricos não cadastrados, estimados a partir dos bens do endereço",
            confirmar="lista e valor dos equipamentos elétricos (nenhum está no cadastro)",
        )
    return dict(
        faixa=_faixa(minimo, maximo),
        confianca=bens.confianca(),
        dados="bens elétricos/eletrônicos cadastrados (equipamentos, refrigeração, informática, máquinas...)",
        regra="mín = valor ponderado dos equipamentos elétricos; máx = valor cadastrado deles",
        justificativa=f"equipamentos elétricos do endereço somam até {_reais(maximo)}",
        confirmar="lista e valor dos equipamentos elétricos",
    )


def _aluguel(est: Estabelecimento, bens: _Bens) -> dict:
    a, b = MESES_ALUGUEL
    if est.paga_aluguel and est.valor_aluguel:
        incoerente = any(i.startswith("aluguel") for i in inconsistencias(est))
        return dict(
            faixa=_faixa(a * est.valor_aluguel, b * est.valor_aluguel),
            confianca="BAIXA" if incoerente else "ALTA",
            dados=f"aluguel recorrente pago ({_reais(est.valor_aluguel)}/mês)",
            regra=f"{a} a {b} meses de aluguel; 12 meses é o limite da cl. PERDA_PAGAMENTO_ALUGUEL-1.6",
            justificativa=f"aluguel de {_reais(est.valor_aluguel)}/mês por até {b} meses de reparo",
            confirmar="valor do aluguel, que parece alto frente ao faturamento" if incoerente else None,
        )
    referencia = max(est.despesa_fixa_mensal * 0.1, 1000)
    return dict(
        faixa=_faixa(a * referencia, b * referencia),
        confianca="BAIXA",
        dados="não há aluguel recorrente: provável imóvel próprio; referência = 10% da despesa fixa mensal",
        regra=f"{a} a {b} meses de um aluguel de referência; cobre o aluguel pago a terceiros (cl. PERDA_PAGAMENTO_ALUGUEL-1.4)",
        justificativa="se o imóvel próprio ficar inutilizável, cobre o aluguel de outro ponto",
        confirmar="se o imóvel é próprio e o aluguel de um ponto equivalente",
    )


def _rc_estabelecimento(est: Estabelecimento, bens: _Bens) -> dict:
    minimo, maximo = RC_ESTABELECIMENTO_POR_PORTE.get(est.porte, RC_ESTABELECIMENTO_POR_PORTE["PEQUENA"])
    return dict(
        faixa=_faixa(minimo, maximo),
        confianca="BAIXA",
        dados=f"porte da empresa ({est.porte}); a base não tem dado de circulação de público nem de sinistros",
        regra=f"faixa de referência da equipe por porte: {_reais(minimo)} a {_reais(maximo)}",
        justificativa="danos a clientes e terceiros no estabelecimento",
        confirmar="circulação de clientes no local e se há atendimento ao público",
    )


def _despesas_fixas(est: Estabelecimento, bens: _Bens) -> dict:
    a, b = MESES_DESPESAS_FIXAS
    incoerente = any(i.startswith("despesa") for i in inconsistencias(est))
    return dict(
        faixa=_faixa(a * est.despesa_fixa_mensal, b * est.despesa_fixa_mensal),
        confianca="BAIXA" if incoerente else "MEDIA",
        dados=f"despesa fixa mensal estimada ({_reais(est.despesa_fixa_mensal)})",
        regra=f"{a} a {b} meses de despesa fixa; 180 dias é o limite da cl. DESPESAS_FIXAS-2.1",
        justificativa=f"mantém {_reais(est.despesa_fixa_mensal)}/mês de despesas fixas durante a paralisação",
        confirmar="valor das despesas fixas mensais, que parece alto frente ao faturamento"
        if incoerente
        else "valor das despesas fixas mensais (salários, contas, aluguel)",
    )


def _roubo(est: Estabelecimento, bens: _Bens) -> dict:
    minimo = est.estoque_medio + bens.soma("valor_ponderado", TIPOS_PORTATEIS)
    maximo = est.estoque_pico + bens.soma("valor_cadastrado", TIPOS_PORTATEIS)
    return dict(
        faixa=_faixa(minimo, maximo),
        confianca=bens.confianca(),
        dados="estoque médio e de pico; equipamentos portáteis (eletrônicos, informática, beleza, médicos)",
        regra="mín = estoque médio + portáteis ponderados; máx = estoque de pico + portáteis cadastrados",
        justificativa=f"bens subtraíveis entre {_reais(minimo)} e {_reais(maximo)}",
        confirmar="valor do estoque em época de pico",
    )


def _vendaval(est: Estabelecimento, bens: _Bens) -> dict:
    a, b = FRACAO_VENDAVAL
    base_min = bens.soma("valor_ponderado") + est.estoque_medio
    base_max = bens.soma("valor_cadastrado") + est.estoque_pico
    return dict(
        faixa=_faixa(a * base_min, b * base_max),
        confianca="BAIXA",
        dados="bens e estoque do endereço; a base não tem índice territorial de vendaval",
        regra=f"{a:.0%} a {b:.0%} do conteúdo (perda parcial, premissa da equipe)",
        justificativa="danos por vento, granizo e similares ao estabelecimento e bens",
        confirmar="tipo de telhado e histórico de vendaval na região",
    )


def _rc_empregador(est: Estabelecimento, bens: _Bens) -> dict:
    salario = est.folha_pagamento_mensal / max(est.funcionarios_empresa, 1)
    a, b = SALARIOS_RC_EMPREGADOR
    return dict(
        faixa=_faixa(a * salario, b * salario),
        confianca="BAIXA",
        dados=f"folha mensal ({_reais(est.folha_pagamento_mensal)}) e funcionários ({est.funcionarios_empresa:.0f})",
        regra=f"{a} a {b} salários médios por evento (premissa da equipe)",
        justificativa=f"acidente com empregado; salário médio estimado em {_reais(salario)}",
        confirmar="número de funcionários neste endereço e atividades de risco",
    )


def _vidros(est: Estabelecimento, bens: _Bens) -> dict:
    local = next((t for t in ("LOJA", "GALERIA", "SALA", "TORRE") if t in est.termos_endereco), None)
    minimo, maximo = VIDROS_POR_LOCALIZACAO.get(local, VIDROS_PADRAO)
    return dict(
        faixa=_faixa(minimo, maximo),
        confianca="BAIXA",
        dados=f"tipo de localização pelo endereço ({local or 'não identificado'}); área não informada"
        if not est.area_m2
        else f"tipo de localização ({local or 'não identificado'}) e área de {est.area_m2:.0f} m²",
        regra="faixa de referência da equipe por tipo de localização (loja/galeria com vitrine valem mais)",
        justificativa="vitrines, vidros, espelhos e fachadas",
        confirmar="se há vitrine ou fachada de vidro e a metragem",
    )


def _frigorificados(est: Estabelecimento, bens: _Bens) -> dict:
    a, b = FRACAO_ESTOQUE_REFRIGERADO
    return dict(
        faixa=_faixa(a * est.estoque_medio, b * est.estoque_pico),
        confianca="BAIXA",
        dados=f"probabilidade de refrigeração ({est.probabilidade_refrigeracao:.0%}) e estoque",
        regra=f"{a:.0%} do estoque médio a {b:.0%} do estoque de pico (parte refrigerada, premissa)",
        justificativa="perda de mercadoria refrigerada por pane ou falta de energia",
        confirmar="quanto do estoque fica em geladeira ou câmara fria",
    )


def _delivery(est: Estabelecimento, bens: _Bens) -> dict:
    diario = _faturamento_do_endereco(est) * max(est.percentual_receita_delivery, 0.1) / DIAS_UTEIS_MES
    return dict(
        faixa=_faixa(diario, 2 * diario),
        confianca="BAIXA",
        dados=f"faturamento do endereço e participação do delivery ({est.percentual_receita_delivery:.0%})",
        regra="1 a 2 dias de mercadoria entregue (faturamento do endereço × % delivery ÷ 22 dias úteis)",
        justificativa="mercadoria danificada durante a entrega ao cliente",
        confirmar="se as entregas são feitas por veículo próprio ou contratado",
    )


def _valores(est: Estabelecimento, bens: _Bens) -> dict:
    diario = _dinheiro_por_dia(est)
    return dict(
        faixa=_faixa(diario, 2 * diario),
        confianca="MEDIA",
        dados=f"faturamento do endereço e recebimentos fora do digital ({1 - est.percentual_recebimentos_digitais:.0%})",
        regra="1 a 2 dias de recebimento em espécie: a cl. ROUBO_OU_FURTO_DE_VALORES_MEDIANTE_ARROMBAMENTO-2.1 "
        "limita ao movimento do dia e do dia útil anterior",
        justificativa=f"cerca de {_reais(diario)} por dia recebidos em dinheiro ou cheque",
        confirmar="se há cofre e quanto fica em caixa fora do expediente",
    )


DIMENSIONAR = {
    "INCENDIO_RAIO_EXPLOSAO_FUMACA": _incendio,
    "DANOS_ELETRICOS": _danos_eletricos,
    "PERDA_PAGAMENTO_ALUGUEL": _aluguel,
    "RESPONSABILIDADE_CIVIL_ESTABELECIMENTO": _rc_estabelecimento,
    "DESPESAS_FIXAS": _despesas_fixas,
    "ROUBO_FURTO_ARROMBAMENTO": _roubo,
    "VENDAVAL_EVENTOS_CORRELATOS": _vendaval,
    "RESPONSABILIDADE_CIVIL_EMPREGADOR": _rc_empregador,
    "QUEBRA_DE_VIDROS": _vidros,
    "DETERIORACAO_DE_MERCADORIAS_EM_AMBIENTES_FRIGORIFICADOS": _frigorificados,
    "DELIVERY": _delivery,
    "ROUBO_OU_FURTO_DE_VALORES_MEDIANTE_ARROMBAMENTO": _valores,
}


# ---------- necessidade de cada cobertura (o plano sai daqui, não do pacote) ----------

ESSENCIAL, RECOMENDADA, OPCIONAL, NAO_SE_APLICA = "ESSENCIAL", "RECOMENDADA", "OPCIONAL", "NAO_SE_APLICA"
ORDEM_PACOTES = [Plano.ESSENCIAL, Plano.PRATICO, Plano.TOTAL]
SEGMENTOS_SEM_PUBLICO = {"ESCRITORIO"}  # recebem poucos clientes no local
MINIMO_ELETRICOS_ESSENCIAL = 30_000
MINIMO_DESPESA_ESSENCIAL = 20_000
MINIMO_SUBTRAIVEL_RECOMENDADA = 3_000
MINIMO_FUNCIONARIOS_RECOMENDADA = 5
MINIMO_DINHEIRO_DIA_ESSENCIAL = 10_000


def necessidade(nome: str, est: Estabelecimento, bens: _Bens) -> tuple[str, str]:
    """(nível, motivo) de uma cobertura para este estabelecimento. Regras da equipe, sem LLM."""
    subtraivel = est.estoque_medio + bens.soma("valor_ponderado", TIPOS_PORTATEIS)
    match nome:
        case "INCENDIO_RAIO_EXPLOSAO_FUMACA":
            return ESSENCIAL, "cobertura básica obrigatória do seguro (cl. CG-3.1)"
        case "RESPONSABILIDADE_CIVIL_ESTABELECIMENTO":
            if est.grupo_atividade in SEGMENTOS_SEM_PUBLICO:
                return RECOMENDADA, "danos a visitantes e terceiros no local"
            return ESSENCIAL, "recebe clientes no estabelecimento"
        case "DANOS_ELETRICOS":
            eletricos = bens.soma("valor_cadastrado", TIPOS_ELETRICOS)
            if eletricos >= MINIMO_ELETRICOS_ESSENCIAL:
                return ESSENCIAL, f"{_reais(eletricos)} em equipamentos elétricos"
            return RECOMENDADA, "equipamentos elétricos sujeitos a raio e variação de tensão"
        case "PERDA_PAGAMENTO_ALUGUEL":
            if est.paga_aluguel:
                return ESSENCIAL, f"paga {_reais(est.valor_aluguel)} de aluguel, que continua se o ponto parar"
            return OPCIONAL, "imóvel provavelmente próprio: só cobre aluguel de outro ponto"
        case "DESPESAS_FIXAS":
            if est.despesa_fixa_mensal >= MINIMO_DESPESA_ESSENCIAL:
                return ESSENCIAL, f"{_reais(est.despesa_fixa_mensal)} por mês de despesas fixas"
            return RECOMENDADA, "despesas fixas continuam se o negócio parar"
        case "ROUBO_FURTO_ARROMBAMENTO":
            if subtraivel >= MINIMO_SUBTRAIVEL_ROUBO:
                return ESSENCIAL, f"cerca de {_reais(subtraivel)} em estoque e equipamentos portáteis"
            if subtraivel >= MINIMO_SUBTRAIVEL_RECOMENDADA:
                return RECOMENDADA, f"cerca de {_reais(subtraivel)} em estoque e equipamentos portáteis"
            return OPCIONAL, "pouco estoque e poucos equipamentos portáteis"
        case "VENDAVAL_EVENTOS_CORRELATOS":
            if est.termos_endereco and set(est.termos_endereco) <= {"SALA", "TORRE"}:
                return OPCIONAL, "sala em prédio: telhado e fachada são do condomínio"
            return RECOMENDADA, "sem dado de risco climático da região; protege telhado, fachada e bens"
        case "RESPONSABILIDADE_CIVIL_EMPREGADOR":
            n = est.funcionarios_empresa
            if n >= MINIMO_FUNCIONARIOS_RC_EMPREGADOR:
                return ESSENCIAL, f"{n:.0f} funcionários"
            if n >= MINIMO_FUNCIONARIOS_RECOMENDADA:
                return RECOMENDADA, f"{n:.0f} funcionários"
            return OPCIONAL, "equipe muito pequena"
        case "QUEBRA_DE_VIDROS":
            if {"LOJA", "GALERIA"} & set(est.termos_endereco):
                return RECOMENDADA, "loja com vitrine ou fachada de vidro"
            return OPCIONAL, "sem vitrine identificada"
        case "DETERIORACAO_DE_MERCADORIAS_EM_AMBIENTES_FRIGORIFICADOS":
            if est.probabilidade_refrigeracao >= MINIMO_REFRIGERACAO and est.estoque_medio > 0:
                return RECOMENDADA, "guarda mercadoria refrigerada"
            return NAO_SE_APLICA, "não usa refrigeração para mercadoria"
        case "DELIVERY":
            if est.probabilidade_delivery >= MINIMO_DELIVERY:
                return RECOMENDADA, "faz entregas"
            return NAO_SE_APLICA, "não faz entregas"
        case "ROUBO_OU_FURTO_DE_VALORES_MEDIANTE_ARROMBAMENTO":
            dia = _dinheiro_por_dia(est)
            fisico = 1 - est.percentual_recebimentos_digitais
            if dia >= MINIMO_DINHEIRO_DIA_ESSENCIAL:
                return ESSENCIAL, f"cerca de {_reais(dia)} por dia recebidos em dinheiro"
            if fisico >= MINIMO_RECEBIMENTO_FISICO and dia >= MINIMO_DINHEIRO_DIA:
                return RECOMENDADA, f"cerca de {_reais(dia)} por dia recebidos em dinheiro"
            if dia > 0:
                return OPCIONAL, "pouco dinheiro em caixa"
            return NAO_SE_APLICA, "recebe tudo no digital"
    raise ValueError(nome)


def necessidades(est: Estabelecimento) -> dict[str, tuple[str, str]]:
    bens = _Bens(est)
    return {nome: necessidade(nome, est, bens) for nome in DIMENSIONAR}


def pacote_minimo(niveis: dict[str, tuple[str, str]]) -> Plano:
    """Menor pacote da BB Seguros cujo catálogo contém todas as coberturas essenciais que existem em pacote."""
    no_catalogo = set(rag._catalogo())
    essenciais = {c for c, (n, _) in niveis.items() if n == ESSENCIAL and c in no_catalogo}
    return next((p for p in ORDEM_PACOTES if essenciais <= set(rag.coberturas_do_plano(p))), Plano.TOTAL)


def pacote_de_contratacao(niveis: dict[str, tuple[str, str]], plano_motor: Plano | None) -> Plano:
    """O pacote mínimo pelas necessidades, nunca abaixo do índice do motor de score."""
    minimo = pacote_minimo(niveis)
    if plano_motor is None:
        return minimo
    return max(minimo, plano_motor, key=ORDEM_PACOTES.index)


def _cobertura(
    nome: str, origem: str, est: Estabelecimento, bens: _Bens, nivel: tuple[str, str]
) -> CoberturaRecomendada:
    d = DIMENSIONAR[nome](est, bens)
    return CoberturaRecomendada(
        cobertura=nome,
        origem=origem,
        necessidade=nivel[0],
        motivo_necessidade=nivel[1],
        faixa_valor_min=d["faixa"][0],
        faixa_valor_max=d["faixa"][1],
        confianca=d["confianca"],
        dados_utilizados=d["dados"],
        regra_calculo=d["regra"],
        justificativa=f"{nivel[1]}; {d['justificativa']}",
        informacao_a_confirmar=d["confirmar"],
        clausulas=CLAUSULAS[nome],
    )


def elegibilidade(perfil: Perfil, est: Estabelecimento) -> tuple[str, str | None, list[str]]:
    """(SIM ou A_CONFIRMAR, motivo, perguntas). Critérios das cl. CG-6 e CG-7.1; nunca NAO automático."""
    pendencias, perguntas = [], []
    if perfil.status != "EXPERIMENTAL_BASE_MOCK":
        pendencias.append("dados essenciais ausentes no cadastro")
    if est.situacao_imovel == "EM_OBRA":
        pendencias.append("imóvel em obra (cl. CG-7.1.u)")
        perguntas.append("A obra no imóvel obriga a desocupar o local?")
    if est.situacao_imovel == "IRREGULAR":
        pendencias.append("situação cadastral do imóvel irregular")
        perguntas.append("O imóvel está regularizado na prefeitura?")
    if not est.endereco_cnpj_compativel:
        pendencias.append("endereço não confere com o CNPJ (cl. CG-6.1.1.a)")
        perguntas.append("O CNPJ está registrado neste endereço?")
    if est.material_parede_externa == "NAO_DISPONIVEL":
        perguntas.append("O imóvel é de alvenaria, concreto ou outro material incombustível? (cl. CG-6.1.2)")
    return ("A_CONFIRMAR" if pendencias else "SIM"), ("; ".join(pendencias) or None), perguntas


def _nome(cobertura: str) -> str:
    return cobertura.lower().replace("_", " ")


def est_com_entrada(est: Estabelecimento, entrada: dict) -> Estabelecimento:
    """O estabelecimento com os valores da entrada do motor (que incluem o que o cliente confirmou):
    funcionários, estoque e bens. Sem isso a confirmação mudava o índice e não as necessidades."""
    mudancas = {}
    if entrada.get("funcionarios_estimados_empresa") is not None:
        mudancas["funcionarios_empresa"] = entrada["funcionarios_estimados_empresa"]
    if entrada.get("estoque_medio_estimado") is not None and entrada["estoque_medio_estimado"] != est.estoque_medio:
        novo = entrada["estoque_medio_estimado"]
        mudancas["estoque_medio"] = novo
        mudancas["estoque_pico"] = est.estoque_pico * novo / est.estoque_medio if est.estoque_medio else novo * 1.3
    bens_entrada = entrada.get("valor_bens_ponderado_estabelecimento")
    ponderado = sum(b.valor_ponderado for b in est.bens)
    if bens_entrada is not None and ponderado and abs(bens_entrada - ponderado) > 1:
        fator = bens_entrada / ponderado
        mudancas["bens"] = [
            b.model_copy(update={"valor_cadastrado": b.valor_cadastrado * fator, "valor_ponderado": b.valor_ponderado * fator})
            for b in est.bens
        ]
    return est.model_copy(update=mudancas) if mudancas else est


def _assinatura(p: PlanoPersonalizado) -> tuple:
    """O que define o plano para o cliente: o pacote e as coberturas que entram (não as opcionais)."""
    return p.plano_base, frozenset(c.cobertura for c in p.coberturas if c.origem != "opcional")


def pergunta_muda_o_plano(perfil: Perfil, est: Estabelecimento) -> bool:
    """A pergunta pendente do motor só vale a pena se o sim e o não levam a planos personalizados diferentes."""
    if not perfil.perguntas_pendentes:
        return False
    from agente.contratos import Confirmacao
    from agente.regras import aplicar_confirmacao

    pergunta = perfil.perguntas_pendentes[0]
    planos = set()
    for valor in ("sim", "nao"):
        _, novo = aplicar_confirmacao(perfil, Confirmacao(pergunta_id=pergunta.id, valor=valor, probabilidade=1))
        planos.add(_assinatura(personalizar(novo, est, filtrar_pergunta=False)))
    return len(planos) > 1


def perfil_relevante(perfil: Perfil, est: Estabelecimento) -> Perfil:
    """O perfil sem a pergunta pendente quando ela não muda o plano personalizado (tese: só perguntar o que muda)."""
    if perfil.perguntas_pendentes and not pergunta_muda_o_plano(perfil, est_com_entrada(est, perfil.entrada)):
        return perfil.model_copy(update={"perguntas_pendentes": []})
    return perfil


def personalizar(perfil: Perfil, est: Estabelecimento, filtrar_pergunta: bool = True) -> PlanoPersonalizado:
    """Plano cobertura por cobertura: nível de necessidade e faixa de cada uma; o pacote BB mais
    próximo diz como contratar (pacote + adicionais)."""
    if filtrar_pergunta:
        perfil = perfil_relevante(perfil, est)
    est = est_com_entrada(est, perfil.entrada)
    bens = _Bens(est)
    elegivel, motivo_eleg, perguntas_eleg = elegibilidade(perfil, est)
    niveis = necessidades(est)
    minimo = pacote_minimo(niveis)
    pacote = pacote_de_contratacao(niveis, perfil.plano)
    do_pacote = rag.coberturas_do_plano(pacote)
    coberturas = [_cobertura(c, "plano", est, bens, niveis[c]) for c in do_pacote]
    for c, nivel in niveis.items():
        if c in do_pacote or nivel[0] == NAO_SE_APLICA:
            continue
        cob = _cobertura(c, "opcional", est, bens, nivel)
        if nivel[0] in (ESSENCIAL, RECOMENDADA) and cob.faixa_valor_max >= MINIMO_RELEVANTE_ADICIONAL:
            cob.origem = "adicional"
        coberturas.append(cob)
    adicionais = [c for c in coberturas if c.origem == "adicional"]

    achados = inconsistencias(est)
    perguntas = [p.texto for p in perfil.perguntas_pendentes] + perguntas_eleg
    perguntas += [f"Confirmar: {a}" for a in achados]
    perguntas += [
        f"Confirmar: {c.informacao_a_confirmar}"
        for c in coberturas
        if c.origem != "opcional"
        and c.informacao_a_confirmar
        and c.confianca == "BAIXA"
        and "parece alto" not in c.informacao_a_confirmar
    ][:3]
    principal = next((c for c in coberturas if c.cobertura == "INCENDIO_RAIO_EXPLOSAO_FUMACA"), None)
    if elegivel != "SIM":
        confianca = "BAIXA"
    elif perfil.perguntas_pendentes or perfil.avisos or achados or (principal and principal.confianca == "BAIXA"):
        confianca = "MEDIA"
    else:
        confianca = "ALTA"

    essenciais = [c for c, (n, _) in niveis.items() if n == ESSENCIAL]
    justificativa = f"Pacote {pacote}: menor pacote com as coberturas essenciais ({', '.join(map(_nome, essenciais))})"
    if perfil.plano is not None and pacote != minimo:
        justificativa = f"Pacote {pacote}: índice do motor (score {perfil.score:.3f}); pelas necessidades bastaria o {minimo}"
    elif perfil.plano is not None:
        justificativa += f"; índice do motor: {perfil.plano} (score {perfil.score:.3f})"
    else:
        justificativa += "; motor sem índice: faltam dados essenciais"
    if achados:
        justificativa += "; dados a conferir: " + "; ".join(achados)
    if adicionais:
        justificativa += "; adicionais: " + "; ".join(
            f"{_nome(c.cobertura)} ({c.motivo_necessidade})" for c in adicionais
        )
    local = next((t for t in ("LOJA", "GALERIA", "SALA", "TORRE") if t in est.termos_endereco), "NAO_IDENTIFICADO")
    return PlanoPersonalizado(
        imovel_id=est.imovel_id,
        empresa_id=est.empresa_id,
        plano_base=pacote,
        plano_motor=perfil.plano,
        pacote_minimo=minimo,
        elegivel=elegivel,
        motivo_elegibilidade=motivo_eleg,
        tipo_localizacao=local,
        relacao_imovel="LOCATARIO" if est.paga_aluguel else "PROPRIETARIO_PROVAVEL",
        coberturas=coberturas,
        confianca_geral=confianca,
        justificativa=justificativa,
        perguntas_confirmacao=list(dict.fromkeys(perguntas)),
        dados_a_conferir=achados,
    )
