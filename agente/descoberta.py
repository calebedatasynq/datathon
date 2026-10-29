"""Conversa do zero: o agente não conhece o cliente e pergunta só o que muda o plano.

Cada pergunta tem faixas (botões) e aceita texto livre, que o Jev encaixa numa faixa. Antes de
cada pergunta, o agente testa todas as respostas possíveis no motor e na personalização: se
todas levam ao mesmo plano, a pergunta é pulada. O que não foi perguntado vem da mediana do
segmento na base de desenvolvimento. Quando nenhuma pergunta restante muda o plano, o agente
monta o cliente virtual e passa ao pipeline normal (recomendação com cláusulas e guardrail).
"""

import math
import re
import time
import uuid
from collections.abc import Callable
from pathlib import Path

import requests
from pydantic import BaseModel

from agente import config, log, territorio
from agente.contratos import EstadoTurno, Perfil, PlanoPersonalizado, ResultadoGuardrail, RiscoLocal
from agente.dados_base import Bem, Estabelecimento, perfil_segmento
from agente.decisor import Decisor, criar_decisor
from agente.enriquecimento import SEGMENTOS, classificar_cnae, enriquecer_cnpj
from agente.perfil import perfil_de_entrada
from agente.personalizacao import personalizar
from agente.pipeline import Conversa
from agente.redator import Redacao, redigir

MAX_PERGUNTAS = 8  # sem contar CNPJ e atividade
SALARIO_PADRAO = 3_000


class Opcao(BaseModel):
    id: str
    rotulo: str
    """O texto do botão."""
    descricao: str
    """O que o Jev lê para encaixar um texto livre nesta opção."""
    valor: float | bool | None = None


class PerguntaDescoberta(BaseModel):
    id: str
    texto: str
    opcoes: list[Opcao]
    segmentos: set[str] | None = None
    """Só para estes segmentos (None: todos)."""


def _faixas(prefixo: str, unidade: str, faixas: list[tuple[str, str, float]]) -> list[Opcao]:
    return [Opcao(id=f"{prefixo}_{i}", rotulo=r, descricao=f"{d} {unidade}".strip(), valor=v) for i, (r, d, v) in enumerate(faixas)]


SEGMENTOS_DA_BASE = [s for s in SEGMENTOS if s != "OUTRO"]
ROTULO_SEGMENTO = {
    "BELEZA": "Salão de beleza", "CLINICA": "Clínica", "ELETRONICOS": "Loja de eletrônicos",
    "ESCOLA_CURSO": "Escola ou cursos", "ESCRITORIO": "Escritório", "FARMACIA": "Farmácia",
    "MERCADO": "Mercado", "OFICINA": "Oficina", "RESTAURANTE": "Restaurante ou bar",
    "VAREJO_MODA": "Loja de roupas e calçados", "OUTRO": "Outro ramo",
}  # fmt: skip

PERGUNTAS = [
    PerguntaDescoberta(
        id="funcionarios",
        texto="Quantas pessoas trabalham na empresa, contando você?",
        opcoes=_faixas("func", "pessoas", [
            ("Até 5", "de 1 a 5", 3), ("6 a 16", "de 6 a 16", 11), ("17 a 30", "de 17 a 30", 23), ("Mais de 30", "mais de 30", 45),
        ]),
    ),
    PerguntaDescoberta(
        id="estoque",
        texto="Quanto você costuma ter em mercadoria e matéria-prima no local, em média?",
        opcoes=_faixas("est", "em estoque", [
            ("Quase nada", "nenhum ou quase nenhum (até R$ 2 mil)", 1_000), ("Até R$ 10 mil", "até R$ 10 mil", 5_000),
            ("R$ 10 a 40 mil", "entre R$ 10 mil e R$ 40 mil", 25_000), ("R$ 40 a 150 mil", "entre R$ 40 mil e R$ 150 mil", 90_000),
            ("Mais de R$ 150 mil", "mais de R$ 150 mil", 250_000),
        ]),
    ),
    PerguntaDescoberta(
        id="bens",
        texto="E quanto valem as máquinas, equipamentos e móveis do local, somados?",
        opcoes=_faixas("bens", "em máquinas, equipamentos e móveis", [
            ("Até R$ 30 mil", "até R$ 30 mil", 15_000), ("R$ 30 a 100 mil", "entre R$ 30 mil e R$ 100 mil", 60_000),
            ("R$ 100 a 400 mil", "entre R$ 100 mil e R$ 400 mil", 200_000), ("Mais de R$ 400 mil", "mais de R$ 400 mil", 600_000),
        ]),
    ),
    PerguntaDescoberta(
        id="imovel",
        texto="O ponto é alugado ou próprio?",
        opcoes=[
            Opcao(id="imovel_alugado", rotulo="Alugado", descricao="paga aluguel pelo imóvel", valor=True),
            Opcao(id="imovel_proprio", rotulo="Próprio", descricao="o imóvel é da empresa ou do dono, sem aluguel", valor=False),
        ],
    ),
    PerguntaDescoberta(
        id="aluguel",
        texto="Quanto é o aluguel por mês, mais ou menos?",
        opcoes=_faixas("alug", "de aluguel por mês", [
            ("Até R$ 3 mil", "até R$ 3 mil", 2_000), ("R$ 3 a 8 mil", "entre R$ 3 mil e R$ 8 mil", 5_500),
            ("R$ 8 a 20 mil", "entre R$ 8 mil e R$ 20 mil", 13_000), ("Mais de R$ 20 mil", "mais de R$ 20 mil", 30_000),
        ]),
    ),
    PerguntaDescoberta(
        id="faturamento",
        texto="Quanto a empresa fatura por mês, em média?",
        opcoes=_faixas("fat", "de faturamento por mês", [
            ("Até R$ 30 mil", "até R$ 30 mil", 20_000), ("R$ 30 a 100 mil", "entre R$ 30 mil e R$ 100 mil", 60_000),
            ("R$ 100 a 400 mil", "entre R$ 100 mil e R$ 400 mil", 200_000), ("Mais de R$ 400 mil", "mais de R$ 400 mil", 600_000),
        ]),
    ),
    PerguntaDescoberta(
        id="refrigeracao",
        texto="Você guarda mercadoria em geladeira, freezer ou câmara fria?",
        opcoes=[
            Opcao(id="refr_sim", rotulo="Sim", descricao="guarda mercadoria refrigerada", valor=True),
            Opcao(id="refr_nao", rotulo="Não", descricao="não usa refrigeração para mercadoria", valor=False),
        ],
        segmentos={"RESTAURANTE", "MERCADO", "FARMACIA", "CLINICA", "OUTRO"},
    ),
    PerguntaDescoberta(
        id="delivery",
        texto="A empresa faz entregas para os clientes?",
        opcoes=[
            Opcao(id="deliv_sim", rotulo="Sim", descricao="faz entregas ou delivery", valor=True),
            Opcao(id="deliv_nao", rotulo="Não", descricao="não faz entregas", valor=False),
        ],
        segmentos={"RESTAURANTE", "MERCADO", "FARMACIA", "VAREJO_MODA", "ELETRONICOS", "OUTRO"},
    ),
    PerguntaDescoberta(
        id="dinheiro",
        texto="Do que você recebe, quanto vem em dinheiro vivo ou cheque?",
        opcoes=[
            Opcao(id="din_pouco", rotulo="Quase nada", descricao="quase tudo é Pix, cartão ou boleto", valor=0.05),
            Opcao(id="din_parte", rotulo="Uma parte", descricao="uma parte em dinheiro ou cheque", valor=0.3),
            Opcao(id="din_maior", rotulo="A maior parte", descricao="a maior parte em dinheiro ou cheque", valor=0.7),
        ],
    ),
    PerguntaDescoberta(
        id="vitrine",
        texto="O ponto tem vitrine ou fachada de vidro?",
        opcoes=[
            Opcao(id="vitr_sim", rotulo="Sim", descricao="tem vitrine, porta ou fachada de vidro", valor=True),
            Opcao(id="vitr_nao", rotulo="Não", descricao="não tem vitrine nem fachada de vidro", valor=False),
        ],
    ),
]
POR_ID = {p.id: p for p in PERGUNTAS}
CURTO = {
    "funcionarios": "Pessoas na empresa", "estoque": "Estoque", "bens": "Máquinas e equipamentos",
    "imovel": "Imóvel", "aluguel": "Aluguel", "faturamento": "Faturamento mensal", "refrigeracao": "Refrigeração",
    "delivery": "Entregas", "dinheiro": "Recebe em dinheiro", "vitrine": "Vitrine",
}  # fmt: skip

# Cliente sem cadastro: o motivo de cada cobertura sai sem números (os do perfil são faixas ou
# medianas do ramo) e diz de onde veio o dado. Cobertura → (motivo, perguntas que o sustentam).
MOTIVO_SEM_NUMERO = {
    "DANOS_ELETRICOS": ("equipamentos elétricos sujeitos a raio e variação de tensão", {"bens"}),
    "PERDA_PAGAMENTO_ALUGUEL": ("o aluguel do ponto continua se o negócio parar", {"imovel", "aluguel"}),
    "DESPESAS_FIXAS": ("despesas fixas continuam se o negócio parar", {"faturamento", "funcionarios"}),
    "ROUBO_FURTO_ARROMBAMENTO": ("estoque e equipamentos portáteis no local", {"estoque", "bens"}),
    "ROUBO_OU_FURTO_DE_VALORES_MEDIANTE_ARROMBAMENTO": ("dinheiro recebido e guardado no caixa", {"dinheiro", "faturamento"}),
    "RESPONSABILIDADE_CIVIL_EMPREGADOR": ("acidentes com a equipe", {"funcionarios"}),
}
# Coberturas que dependem de uma pergunta de sim/não: sem a resposta, o motivo vem do que é típico do ramo.
DEPENDE_DE_SIM_NAO = {
    "DETERIORACAO_DE_MERCADORIAS_EM_AMBIENTES_FRIGORIFICADOS": "refrigeracao",
    "DELIVERY": "delivery",
    "QUEBRA_DE_VIDROS": "vitrine",
}
DEPENDE_TEXTO = {
    "refrigeracao": "refrigeração de mercadoria é comum no ramo",
    "delivery": "entregas são comuns no ramo",
    "vitrine": "vitrine não informada",
}
NAO_SABE = "Não sei"

ABERTURA = (
    "Olá! Vou montar um seguro sob medida para a sua empresa, perguntando só o que faz diferença. "
    "Para começar: quer me informar o CNPJ? Com ele a recomendação fica mais certeira e mais personalizada. "
    "Se preferir não informar, sem problema: é só me contar o que a sua empresa faz."
)
PERGUNTA_ATIVIDADE = "O que a sua empresa faz? Por exemplo: restaurante, farmácia, salão de beleza, oficina…"
PERGUNTA_CEP = (
    "Qual é o CEP do estabelecimento? Com ele eu consulto o histórico de clima e o relevo da região "
    "(vento forte, granizo, raios, alagamento, deslizamento e barragens próximas) para ajustar o plano."
)
SEM_CEP = "Prefiro não informar o CEP"
ROTULO_RESPOSTA = {"atividade": "Ramo", "cep": "CEP"}


class Resposta(BaseModel):
    pergunta: str
    rotulo: str
    valor: float | bool | None
    origem: str
    """"cliente", "cnpj" ou "estimado" (o cliente não soube; vale a mediana do segmento)."""
    probabilidade: float | None = None


# ---------- cliente virtual ----------


def _valor(respostas: dict[str, Resposta], chave: str, padrao):
    r = respostas.get(chave)
    return padrao if r is None or r.valor is None else r.valor


def estabelecimento_virtual(
    identificador: str, segmento: str | None, respostas: dict[str, Resposta], risco: RiscoLocal | None = None
) -> Estabelecimento:
    """O estabelecimento a partir das respostas; o que falta vem da mediana do segmento.
    risco: perigos naturais do CEP informado (None sem CEP)."""
    ref = perfil_segmento(segmento)
    funcionarios = float(_valor(respostas, "funcionarios", ref.funcionarios))
    faturamento = float(_valor(respostas, "faturamento", ref.faturamento))
    paga_aluguel = bool(_valor(respostas, "imovel", True))
    aluguel = float(_valor(respostas, "aluguel", ref.aluguel)) if paga_aluguel else 0.0
    estoque = float(_valor(respostas, "estoque", ref.estoque_medio))
    bens_total = float(_valor(respostas, "bens", ref.bens_ponderado))
    refrigeracao = _valor(respostas, "refrigeracao", None)
    delivery = _valor(respostas, "delivery", None)
    dinheiro = _valor(respostas, "dinheiro", None)
    vitrine = _valor(respostas, "vitrine", None)
    salario = ref.salario_medio or SALARIO_PADRAO
    folha = funcionarios * salario
    bens = [
        Bem(
            tipo=tipo,
            valor_ponderado=bens_total * parte,
            valor_cadastrado=bens_total * parte * ref.cadastrado_sobre_ponderado,
            confianca_vinculo="MEDIA",
        )
        for tipo, parte in ref.partes_bens.items()
    ]
    return Estabelecimento(
        imovel_id=f"{identificador}_01",
        empresa_id=identificador,
        grupo_atividade=segmento or "OUTRO",
        porte="MICRO" if funcionarios <= 9 else "PEQUENA" if funcionarios <= 49 else "MEDIA",
        tipo_unidade="MATRIZ",
        quantidade_estabelecimentos=1,
        faturamento_mensal_empresa=faturamento,
        funcionarios_empresa=funcionarios,
        percentual_receita_delivery=(ref.percentual_delivery if delivery else 0.0) if delivery is not None else ref.percentual_delivery * ref.delivery,
        paga_aluguel=paga_aluguel,
        valor_aluguel=aluguel,
        folha_pagamento_mensal=folha,
        despesa_fixa_mensal=max(folha + aluguel, ref.despesa_sobre_faturamento * faturamento),
        estoque_medio=estoque,
        estoque_pico=estoque * ref.pico_sobre_estoque,
        probabilidade_refrigeracao=(0.9 if refrigeracao else 0.05) if refrigeracao is not None else ref.refrigeracao,
        probabilidade_delivery=(0.9 if delivery else 0.05) if delivery is not None else ref.delivery,
        percentual_recebimentos_digitais=1 - dinheiro if dinheiro is not None else ref.recebimentos_digitais,
        indice_exposicao_digital=0.4,
        area_m2=None,
        termos_endereco=(["LOJA"] if vitrine else []) if vitrine is not None else [],
        situacao_imovel="REGULAR",
        endereco_cnpj_compativel=True,
        material_parede_externa="NAO_DISPONIVEL",
        bens=bens,
        risco=risco,
    )


def entrada_do_motor(est: Estabelecimento) -> dict:
    return {
        "empresa_id": est.empresa_id,
        "imovel_id": est.imovel_id,
        "funcionarios_estimados_empresa": est.funcionarios_empresa,
        "estoque_medio_estimado": est.estoque_medio,
        "valor_bens_ponderado_estabelecimento": sum(b.valor_ponderado for b in est.bens),
        "faturamento_mensal_empresa": est.faturamento_mensal_empresa,
        "quantidade_estabelecimentos_empresa": 1.0,
        "area_m2": None,
        "grupo_atividade": est.grupo_atividade,
        "tipo_unidade": "MATRIZ",
    }


def cliente_virtual(
    identificador: str, segmento: str | None, respostas: dict[str, Resposta], risco: RiscoLocal | None = None
) -> tuple[Perfil, Estabelecimento, PlanoPersonalizado]:
    est = estabelecimento_virtual(identificador, segmento, respostas, risco)
    respondidas = tuple(
        v for k, v in (("funcionarios", "funcionarios_estimados_empresa"), ("estoque", "estoque_medio_estimado"), ("bens", "valor_bens_ponderado_estabelecimento"))
        if k in respostas and respostas[k].origem != "estimado"
    )
    # As respondidas contam como confirmadas: o motor não volta a perguntar o que o cliente já disse.
    perfil = perfil_de_entrada(entrada_do_motor(est), respondidas or ("descoberta",))
    return perfil, est, _sem_numeros(personalizar(perfil, est, filtrar_pergunta=False), respostas)


def _sem_numeros(plano: PlanoPersonalizado, respostas: dict[str, Resposta]) -> PlanoPersonalizado:
    respondidas = {k for k, r in respostas.items() if r.origem in ("cliente", "cnpj")}
    for c in plano.coberturas:
        pergunta = DEPENDE_DE_SIM_NAO.get(c.cobertura)
        if pergunta and pergunta not in respondidas:
            c.motivo_necessidade = f"{DEPENDE_TEXTO[pergunta]} (não perguntei, a confirmar)"
            c.justificativa = c.motivo_necessidade
            continue
        if not any(ch.isdigit() for ch in (c.motivo_necessidade or "")) or c.cobertura not in MOTIVO_SEM_NUMERO:
            continue
        motivo, fontes = MOTIVO_SEM_NUMERO[c.cobertura]
        if c.cobertura == "RESPONSABILIDADE_CIVIL_EMPREGADOR" and "funcionarios" in respondidas:
            motivo = f"equipe de {respostas['funcionarios'].rotulo.lower()} pessoas"
        origem = "pelas suas respostas" if fontes & respondidas == fontes or (c.cobertura == "PERDA_PAGAMENTO_ALUGUEL" and "aluguel" in respondidas) else "estimado pelo ramo, a confirmar"
        c.motivo_necessidade = f"{motivo} ({origem})"
        c.justificativa = c.motivo_necessidade
    if "imovel" not in respondidas:
        plano.relacao_imovel = "A_CONFIRMAR"
    return plano


def _assinatura(p: PlanoPersonalizado) -> tuple:
    """O que conta como mudar o plano: o pacote, as coberturas que entram e a ordem de grandeza
    (degraus de ~3x) do limite de incêndio, a cobertura básica e o maior valor do seguro.
    Incluir os limites de todas as essenciais fazia o agente perguntar tudo (5 a 8 perguntas);
    os outros limites usam a mediana do ramo e ficam marcados para confirmar."""
    incendio = next((c for c in p.coberturas if c.cobertura == "INCENDIO_RAIO_EXPLOSAO_FUMACA"), None)
    return (
        p.plano_base,
        frozenset(c.cobertura for c in p.coberturas if c.origem != "opcional"),
        round(2 * math.log10(max(incendio.faixa_valor_max, 1))) if incendio else None,
    )


def proxima_pergunta(
    identificador: str, segmento: str | None, respostas: dict[str, Resposta], puladas: set[str], risco: RiscoLocal | None = None
) -> tuple[PerguntaDescoberta | None, list[tuple[str, str]]]:
    """A próxima pergunta que ainda pode mudar o plano, e as que foram puladas agora (com o motivo)."""
    puladas_agora = []
    feitas = sum(1 for r in respostas.values() if r.pergunta in POR_ID)
    for pergunta in PERGUNTAS:
        if pergunta.id in respostas or pergunta.id in puladas:
            continue
        if pergunta.segmentos and (segmento or "OUTRO") not in pergunta.segmentos:
            continue
        if pergunta.id == "aluguel" and not _valor(respostas, "imovel", True):
            continue
        if feitas >= MAX_PERGUNTAS:
            return None, puladas_agora
        planos = {
            _assinatura(cliente_virtual(identificador, segmento, {**respostas, pergunta.id: Resposta(pergunta=pergunta.id, rotulo=o.rotulo, valor=o.valor, origem="teste")}, risco)[2])
            for o in pergunta.opcoes
        }
        if len(planos) == 1:
            puladas_agora.append((pergunta.id, f"testei as {len(pergunta.opcoes)} respostas possíveis: o plano não muda"))
            continue
        return pergunta, puladas_agora
    return None, puladas_agora


# ---------- a conversa ----------


def _lista(itens: list[str]) -> str:
    return itens[0] if len(itens) == 1 else f"{', '.join(itens[:-1])} e {itens[-1]}"


def _cnpj_no_texto(texto: str) -> str | None:
    digitos = re.sub(r"\D", "", texto)
    return digitos if len(digitos) == 14 else None


class ConversaDescoberta:
    """Conversa com um cliente sem cadastro. Depois da recomendação, vira uma Conversa normal."""

    def __init__(
        self,
        decisor: Decisor | None = None,
        redigir_fn: Callable[..., Redacao] = redigir,
        arquivo_log: Path | None = None,
        sessao_id: str | None = None,
    ):
        self.decisor = decisor or criar_decisor()
        self.redigir = redigir_fn
        self.arquivo_log = arquivo_log
        self.sessao_id = sessao_id or uuid.uuid4().hex[:8]
        self.cliente_id = f"NOVO_{self.sessao_id}"
        self.segmento: str | None = None
        self.cnpj: dict | None = None
        self.respostas: dict[str, Resposta] = {}
        self.puladas: dict[str, str] = {}
        self.risco: RiscoLocal | None = None
        self.etapa = "cnpj"  # cnpj → atividade → cep → pergunta → recomendada
        self.pergunta: PerguntaDescoberta | None = None
        self.conversa: Conversa | None = None
        self.turnos = 0
        self.historico: list[dict] = [{"agente": ABERTURA}]

    # -- o que a interface mostra --
    def abertura(self) -> dict:
        return {"texto": ABERTURA, "opcoes": ["Prefiro não informar o CNPJ"]}

    def resumo(self) -> dict:
        """O que o agente já sabe, com a origem de cada dado."""
        itens = []
        if self.cnpj:
            itens.append({"rotulo": "Empresa", "valor": self.cnpj.get("razao_social") or "—", "origem": "cnpj"})
        if self.segmento:
            itens.append({"rotulo": "Ramo", "valor": ROTULO_SEGMENTO.get(self.segmento, self.segmento), "origem": "cnpj" if self.cnpj else "cliente"})
        if self.risco and "cep" in self.respostas:
            itens.append({"rotulo": "Local", "valor": self.respostas["cep"].rotulo, "origem": self.respostas["cep"].origem})
        for r in self.respostas.values():
            if r.pergunta in POR_ID:
                itens.append({"rotulo": CURTO[r.pergunta], "valor": r.rotulo, "origem": r.origem})
        return {
            "etapa": self.etapa,
            "sabe": itens,
            "puladas": [{"pergunta": CURTO[k], "motivo": v} for k, v in self.puladas.items()],
            "feitas": sum(1 for r in self.respostas.values() if r.pergunta in POR_ID and r.origem != "estimado"),
            "maximo": MAX_PERGUNTAS,
        }

    # -- leitura das respostas --
    def _ler_opcao(self, mensagem: str, pergunta: PerguntaDescoberta) -> tuple[str, Opcao | None, float]:
        """('opcao' | 'nao_sabe' | 'nao_respondeu', opção, probabilidade). Botão clicado não passa pelo Jev."""
        texto = mensagem.strip().lower()
        for o in pergunta.opcoes:
            if texto == o.rotulo.lower():
                return "opcao", o, 1.0
        if texto == NAO_SABE.lower():
            return "nao_sabe", None, 1.0
        opcoes = {o.id: o.descricao for o in pergunta.opcoes} | {
            "nao_sabe": "o cliente diz que não sabe ou não quer dizer",
            "nao_respondeu": "a mensagem fala de outra coisa ou faz uma pergunta",
        }
        r = self.decisor.escolher(
            {"pergunta": pergunta.texto, "mensagem_do_cliente": mensagem},
            "Qual opção corresponde à resposta de `mensagem_do_cliente` para `pergunta`?",
            opcoes,
        )
        if r.valor in ("nao_sabe", "nao_respondeu"):
            return r.valor, None, r.probabilidade
        if r.probabilidade < config.LIMIAR_CONFIANCA:
            return "nao_respondeu", None, r.probabilidade
        return "opcao", next(o for o in pergunta.opcoes if o.id == r.valor), r.probabilidade

    def _classificar_atividade(self, texto: str) -> tuple[str | None, float]:
        d = classificar_cnae(texto, self.decisor)
        if d.probabilidade < config.LIMIAR_CONFIANCA:
            return None, d.probabilidade
        return d.valor, d.probabilidade

    # -- o turno --
    def turno(self, mensagem: str, ao_progredir: Callable[[dict], None] | None = None, **_) -> EstadoTurno:
        if self.conversa is not None:  # já recomendou: segue como conversa normal
            return self.conversa.turno(mensagem, ao_progredir)
        etapas: list[dict] = []
        inicio = time.perf_counter()
        relogio = [inicio]

        def avisar(id_: str, titulo: str, detalhe: str | None = None, estado: str = "rodando"):
            evento = {"id": id_, "estado": estado, "titulo": titulo, "detalhe": detalhe}
            if estado != "rodando":
                agora = time.perf_counter()
                evento["segundos"] = round(agora - relogio[0], 3)
                relogio[0] = agora
                etapas.append(evento)
            else:
                relogio[0] = time.perf_counter()
            if ao_progredir:
                ao_progredir(evento)

        aviso, recomendar = self._interpretar(mensagem, avisar)
        if not recomendar:
            proxima, puladas_agora = None, []
            if self.etapa == "pergunta":
                avisar("escolher", "Escolhendo a próxima pergunta")
                proxima, puladas_agora = proxima_pergunta(self.cliente_id, self.segmento, self.respostas, set(self.puladas), self.risco)
                for pid, motivo in puladas_agora:
                    self.puladas[pid] = motivo
                detalhe = "; ".join(f"pulei “{POR_ID[p].texto}” ({m})" for p, m in puladas_agora) or None
                if proxima is None:
                    recomendar = True
                    avisar("escolher", "Nenhuma outra pergunta muda o plano", detalhe, "feito")
                else:
                    avisar("escolher", f"Próxima pergunta: {proxima.id}", detalhe, "feito")
                self.pergunta = proxima
        if recomendar:
            return self._recomendar(mensagem, aviso, etapas, avisar, ao_progredir)

        # pergunta de roteiro: texto fixo, sem LLM e sem afirmação de cobertura
        if self.etapa == "atividade":
            pergunta_texto, opcoes = PERGUNTA_ATIVIDADE, [ROTULO_SEGMENTO[s] for s in SEGMENTOS_DA_BASE]
        elif self.etapa == "cep":
            pergunta_texto, opcoes = PERGUNTA_CEP, [SEM_CEP]
        elif self.etapa == "cnpj":
            pergunta_texto, opcoes = "Pode digitar o CNPJ? Só os números já servem.", ["Prefiro não informar o CNPJ"]
        elif self.etapa == "cnpj_de_novo":
            pergunta_texto = (
                "Quer me informar o CNPJ? Com ele a recomendação fica mais certeira e mais personalizada. "
                "Se preferir, é só me contar o que a sua empresa faz."
            )
            opcoes = ["Prefiro não informar o CNPJ"]
        else:
            pergunta_texto, opcoes = self.pergunta.texto, [o.rotulo for o in self.pergunta.opcoes] + [NAO_SABE]
        resposta = f"{aviso} {pergunta_texto}".strip()
        provisorio = None
        if self.segmento:  # sem o ramo, um plano seria só média geral: melhor não mostrar nenhum
            _, _, provisorio = cliente_virtual(self.cliente_id, self.segmento, self.respostas, self.risco)
            avisar(
                "plano",
                "Plano provisório atualizado",
                f"pacote {provisorio.plano_base} · {sum(c.origem != 'opcional' for c in provisorio.coberturas)} coberturas "
                "(o que ainda não perguntei usa a mediana do ramo)",
                "feito",
            )
        estado = EstadoTurno(
            cliente_id=self.cliente_id,
            mensagem=mensagem,
            resposta=resposta,
            plano_personalizado=provisorio,
            guardrail=ResultadoGuardrail(aprovado=True, motivo="pergunta de roteiro, sem afirmação de cobertura"),
            opcoes=opcoes,
            descoberta=self.resumo(),
        )
        self._registrar(estado, etapas, inicio)
        return estado

    def _interpretar(self, mensagem: str, avisar) -> tuple[str, bool]:
        """Lê a resposta da etapa atual e avança. Devolve (frase de reconhecimento, recomendar já?)."""
        if self.etapa == "cnpj_de_novo":
            self.etapa = "cnpj"
        if self.etapa == "cnpj":
            cnpj = _cnpj_no_texto(mensagem)
            if cnpj:
                avisar("cnpj", "Consultando o CNPJ na BrasilAPI")
                try:
                    info = enriquecer_cnpj(cnpj, self.decisor)
                except (LookupError, ValueError):
                    avisar("cnpj", "Não consegui consultar o CNPJ", "sigo sem ele", "falhou")
                    self.etapa = "atividade"
                    return "Não consegui consultar esse CNPJ agora, mas seguimos sem ele.", False
                self.cnpj = info.model_dump()
                seg = info.segmento.valor if info.segmento and info.segmento.probabilidade >= config.LIMIAR_CONFIANCA else None
                avisar(
                    "cnpj",
                    "CNPJ consultado",
                    f"{info.razao_social} · {info.descricao_cnae} · {info.municipio}/{info.uf} · ramo: {ROTULO_SEGMENTO.get(seg, 'a confirmar')}",
                    "feito",
                )
                if seg is None:
                    self.etapa = "atividade"
                    return f"Encontrei {info.razao_social}. Não consegui encaixar a atividade num ramo com segurança.", False
                self.segmento = seg
                self.respostas["atividade"] = Resposta(pergunta="atividade", rotulo=ROTULO_SEGMENTO[seg], valor=None, origem="cnpj")
                return f"Encontrei {info.razao_social} ({ROTULO_SEGMENTO[seg].lower()}).{self._depois_do_ramo(avisar)}", False
            if mensagem.strip().lower() == "prefiro não informar o cnpj":  # botão: sem passar pelo Jev
                self.etapa = "atividade"
                return "Sem problema, seguimos sem o CNPJ.", False
            avisar("interpretar", "Interpretando a resposta com o Jev")
            r = self.decisor.escolher(
                {"mensagem_do_cliente": mensagem},
                "O cliente informou o CNPJ, recusou informar ou descreveu o que a empresa faz?",
                {
                    "nao_quer": "prefere não informar o CNPJ",
                    "descreve": "descreve o ramo ou o que a empresa faz",
                    "vai_informar": "aceita informar o CNPJ, mas ainda não passou o número",
                    "saudacao": "cumprimenta ou puxa conversa, sem responder sobre o CNPJ",
                    "outro": "outra coisa",
                },
            )
            avisar("interpretar", "Resposta interpretada", f"{r.valor.replace('_', ' ')} · {r.probabilidade:.0%}", "feito")
            if r.valor == "vai_informar":
                return "Ótimo.", False
            if r.valor == "descreve":
                return self._definir_atividade(mensagem, avisar)
            if r.valor in ("saudacao", "outro") or r.probabilidade < config.LIMIAR_CONFIANCA:
                # Um "olá" não é uma recusa: cumprimenta e repete o convite do CNPJ.
                self.etapa = "cnpj_de_novo"
                return "Olá!", False
            self.etapa = "atividade"
            return "Sem problema, seguimos sem o CNPJ.", False

        if self.etapa == "atividade":
            texto = mensagem.strip()
            segmento_botao = next((s for s, r in ROTULO_SEGMENTO.items() if r.lower() == texto.lower()), None)
            if segmento_botao:
                self.segmento = segmento_botao
                self.respostas["atividade"] = Resposta(pergunta="atividade", rotulo=ROTULO_SEGMENTO[segmento_botao], valor=None, origem="cliente")
                return f"Anotado: {ROTULO_SEGMENTO[segmento_botao]}.{self._depois_do_ramo(avisar)}", False
            return self._definir_atividade(mensagem, avisar)

        if self.etapa == "cep":
            texto = mensagem.strip()
            cep = territorio.normalizar_cep(texto)
            if texto.lower() == SEM_CEP.lower() or (cep is None and re.search(r"\bn[ãa]o\b", texto.lower())):
                self.etapa = "pergunta"
                return "Sem problema, sigo sem o CEP.", False
            if cep is None:
                return "Não encontrei um CEP nessa mensagem.", False
            frase = self._consultar_cep(cep, avisar, "cliente")
            if frase is None:
                return "Não consegui localizar esse CEP. Pode conferir os números?", False
            self.etapa = "pergunta"
            return frase, False

        # uma pergunta de faixa
        pergunta = self.pergunta
        avisar("interpretar", "Interpretando a resposta com o Jev")
        tipo, opcao, prob = self._ler_opcao(mensagem, pergunta)
        if tipo == "opcao":
            self.respostas[pergunta.id] = Resposta(pergunta=pergunta.id, rotulo=opcao.rotulo, valor=opcao.valor, origem="cliente", probabilidade=prob)
            avisar("interpretar", "Resposta interpretada", f"{pergunta.id}: {opcao.rotulo} · {prob:.0%}", "feito")
            return f"Anotado: {opcao.rotulo}.", False
        if tipo == "nao_sabe":
            self.respostas[pergunta.id] = Resposta(pergunta=pergunta.id, rotulo="Não sabe (uso a média do ramo)", valor=None, origem="estimado", probabilidade=prob)
            avisar("interpretar", "Cliente não soube responder", "uso a mediana do ramo e marco para confirmar depois", "feito")
            return "Sem problema, uso uma estimativa do seu ramo e marcamos para confirmar depois.", False
        avisar("interpretar", "A mensagem não responde à pergunta", f"probabilidade {prob:.0%}", "feito")
        self.puladas.pop(pergunta.id, None)
        self.respostas.pop(pergunta.id, None)
        # mantém a mesma pergunta: proxima_pergunta a devolve de novo
        if "?" in mensagem:
            return "Já respondo isso, assim que entender melhor o seu negócio.", False
        return "Não consegui encaixar essa resposta nesta pergunta.", False

    def _definir_atividade(self, mensagem: str, avisar) -> tuple[str, bool]:
        avisar("atividade", "Classificando o ramo com o Jev")
        seg, prob = self._classificar_atividade(mensagem)
        if seg is None:
            avisar("atividade", "Ramo ainda não identificado", f"confiança {prob:.0%}", "feito")
            self.etapa = "atividade"
            return "Não consegui entender bem o ramo.", False
        avisar("atividade", "Ramo identificado", f"{ROTULO_SEGMENTO.get(seg, seg)} · {prob:.0%}", "feito")
        self.segmento = seg
        self.respostas["atividade"] = Resposta(pergunta="atividade", rotulo=ROTULO_SEGMENTO.get(seg, seg), valor=None, origem="cliente", probabilidade=prob)
        return f"Entendi: {ROTULO_SEGMENTO.get(seg, seg).lower()}.{self._depois_do_ramo(avisar)}", False

    def _depois_do_ramo(self, avisar) -> str:
        """Com o ramo definido vem o local: o CEP do CNPJ, se houver; senão, a pergunta do CEP."""
        cep = territorio.normalizar_cep((self.cnpj or {}).get("cep") or "")
        frase = self._consultar_cep(cep, avisar, "cnpj") if cep else None
        self.etapa = "pergunta" if frase else "cep"
        return f" {frase}" if frase else ""

    def _consultar_cep(self, cep: str, avisar, origem: str) -> str | None:
        """Consulta o risco do local; devolve a frase para o cliente, ou None se o CEP não foi localizado."""
        try:
            risco = territorio.analisar_cep(cep, avisar)
        except (LookupError, ValueError, requests.RequestException):
            avisar("geo_cep", "Não consegui localizar o CEP", "sigo sem o risco do local", "falhou")
            return None
        self.risco = risco
        local = risco.local
        onde = ", ".join(x for x in (local.bairro, f"{local.municipio}/{local.uf}") if x)
        self.respostas["cep"] = Resposta(pergunta="cep", rotulo=onde, valor=None, origem=origem)
        altos = [p.nome.lower() for p in risco.perigos if p.nivel == "ALTO"]
        medios = [p.nome.lower() for p in risco.perigos if p.nivel == "MEDIO"]
        avisar(
            "geo",
            "Risco do local avaliado",
            f"altos: {', '.join(altos) or 'nenhum'} · médios: {', '.join(medios) or 'nenhum'} · agravamento {risco.agravamento.lower()}",
            "feito",
        )
        partes = []
        if altos:
            partes.append(f"risco alto de {_lista(altos)}")
        if medios:
            partes.append(f"risco moderado de {_lista(medios)}")
        achado = f"encontrei {'; '.join(partes)}" if partes else "não encontrei risco natural relevante"
        return f"Consultei a região ({onde}): {achado}. Vou considerar isso no plano."

    def _recomendar(self, mensagem: str, aviso: str, etapas: list, avisar, ao_progredir) -> EstadoTurno:
        """Fim das perguntas: monta o cliente virtual e passa ao pipeline normal."""
        avisar("montar", "Montando o seu perfil com as respostas")
        perfil, est, plano = cliente_virtual(self.cliente_id, self.segmento, self.respostas, self.risco)
        avisar(
            "montar",
            "Perfil montado",
            f"índice do motor: {perfil.plano or 'sem índice (ramo fora da base)'} · pacote {plano.plano_base} · "
            f"{len(plano.adicionais)} adicionais",
            "feito",
        )
        self.conversa = Conversa(
            self.cliente_id, decisor=self.decisor, redigir_fn=self.redigir, arquivo_log=self.arquivo_log,
            sessao_id=self.sessao_id, perfil=perfil, estabelecimento=est,
        )
        self.conversa.turnos = self.turnos
        self.conversa.historico = list(self.historico)
        self.conversa.respostas_do_cliente = {
            (POR_ID[r.pergunta].texto if r.pergunta in POR_ID else ROTULO_RESPOSTA[r.pergunta]): r.rotulo for r in self.respostas.values()
        }
        self.etapa = "recomendada"
        estado = self.conversa.turno(mensagem, ao_progredir, apresentar_recomendacao=True)
        self.turnos = self.conversa.turnos
        estado.descoberta = self.resumo()
        return estado

    def _registrar(self, estado: EstadoTurno, etapas: list[dict], inicio: float):
        self.turnos += 1
        self.historico += [{"cliente": estado.mensagem}, {"agente": estado.resposta}]
        etapas.append({"id": "registrar", "estado": "feito", "titulo": "Turno registrado para auditoria",
                       "detalhe": f"sessão {self.sessao_id} · turno {self.turnos}", "segundos": 0.0})
        log.registrar(
            estado, self.sessao_id, self.turnos,
            versoes={"modo": "descoberta", "decisor": self.decisor.ultima_execucao.get("modelo")},
            tempos={"total": round(time.perf_counter() - inicio, 3)},
            tokens={"decisor": self.decisor.ultima_execucao.get("tokens")},
            extras={"etapas": etapas, "abertura": ABERTURA if self.turnos == 1 else None},
            arquivo=self.arquivo_log,
        )
