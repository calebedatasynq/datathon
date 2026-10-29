"""Dados originais do desafio por estabelecimento (empresa + endereço + sinais + bens).

O motor de score usa a base preparada; a personalização usa estes dados mais finos.
"""

import csv
from collections import defaultdict
from functools import cache
from pathlib import Path

from pydantic import BaseModel, Field

from agente import config, territorio
from agente.contratos import RiscoLocal

PASTA_BASE = config.RAIZ / "Seguro_Empresarial_Teste_Comum"


class Bem(BaseModel):
    tipo: str
    valor_cadastrado: float
    valor_ponderado: float
    confianca_vinculo: str


class Estabelecimento(BaseModel):
    imovel_id: str
    empresa_id: str
    grupo_atividade: str
    porte: str
    tipo_unidade: str
    quantidade_estabelecimentos: int
    faturamento_mensal_empresa: float
    funcionarios_empresa: float
    percentual_receita_delivery: float
    paga_aluguel: bool
    valor_aluguel: float
    folha_pagamento_mensal: float
    despesa_fixa_mensal: float
    estoque_medio: float
    estoque_pico: float
    probabilidade_refrigeracao: float
    probabilidade_delivery: float
    percentual_recebimentos_digitais: float
    indice_exposicao_digital: float
    area_m2: float | None
    termos_endereco: list[str]
    """LOJA, SALA, GALERIA, TORRE: termos que aparecem no endereço."""
    situacao_imovel: str
    endereco_cnpj_compativel: bool
    material_parede_externa: str
    bens: list[Bem]
    confirmacoes_elegibilidade: dict[str, bool] = Field(default_factory=dict)
    """Respostas explícitas: atividade_aceita, local_aceito, sem_tombamento e sem_seguro_bb_duplicado."""
    risco: RiscoLocal | None = None
    """Perigos naturais do local (agente/territorio.py); None se não consultado."""


def _ler(arquivo: str, pasta: Path = PASTA_BASE) -> list[dict]:
    with open(pasta / arquivo, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _num(valor: str | None) -> float:
    return float(valor) if valor not in (None, "") else 0.0


@cache
def _indice(pasta: Path = PASTA_BASE) -> dict[str, Estabelecimento]:
    empresas = {e["empresa_id"]: e for e in _ler("empresas.csv", pasta)}
    sinais = {s["imovel_id"]: s for s in _ler("sinais_financeiros_operacionais.csv", pasta)}
    enderecos = _ler("enderecos_estabelecimentos.csv", pasta)
    por_empresa = defaultdict(int)
    for e in enderecos:
        por_empresa[e["empresa_id"]] += 1
    bens = defaultdict(list)
    for b in _ler("bens_cadastrados.csv", pasta):
        bens[b["imovel_id_referencia"]].append(
            Bem(
                tipo=b["tipo_bem"],
                valor_cadastrado=_num(b["valor_cadastrado"]),
                valor_ponderado=_num(b["valor_bem_ponderado_referencia"]),
                confianca_vinculo=b["nivel_confianca_vinculo"],
            )
        )
    indice = {}
    for e in enderecos:
        emp, s = empresas[e["empresa_id"]], sinais[e["imovel_id"]]
        area = _num(e["area_cadastrada_m2"])
        indice[e["imovel_id"]] = Estabelecimento(
            imovel_id=e["imovel_id"],
            empresa_id=e["empresa_id"],
            grupo_atividade=emp["grupo_atividade"],
            porte=emp["porte"],
            tipo_unidade=e["tipo_unidade"],
            quantidade_estabelecimentos=por_empresa[e["empresa_id"]],
            faturamento_mensal_empresa=_num(emp["faturamento_mensal"]),
            funcionarios_empresa=_num(emp["quantidade_funcionarios_estimada"]),
            percentual_receita_delivery=_num(emp["percentual_receita_delivery_est"]),
            paga_aluguel=s["pagamento_aluguel_recorrente"] == "SIM",
            valor_aluguel=_num(s["valor_aluguel_recorrente"]),
            folha_pagamento_mensal=_num(s["folha_pagamento_mensal"]),
            despesa_fixa_mensal=_num(s["despesa_fixa_mensal_estimada"]),
            estoque_medio=_num(s["estoque_medio_estimado"]),
            estoque_pico=_num(s["estoque_pico_estimado"]),
            probabilidade_refrigeracao=_num(s["probabilidade_refrigeracao_referencia"]),
            probabilidade_delivery=_num(s["probabilidade_delivery_referencia"]),
            percentual_recebimentos_digitais=_num(s["percentual_recebimentos_digitais"]),
            indice_exposicao_digital=_num(s["indice_exposicao_digital"]),
            area_m2=area or None,
            termos_endereco=[t for t in ("LOJA", "SALA", "GALERIA", "TORRE") if e[f"possui_termo_{t.lower()}"] == "SIM"],
            situacao_imovel=e["situacao_imovel_cadastral"],
            endereco_cnpj_compativel=e["endereco_cnpj_compativel"] == "SIM",
            material_parede_externa=e["material_parede_externa_cadastrado"],
            bens=bens[e["imovel_id"]],
            risco=territorio.risco_da_base(e["territorio_id"]),
        )
    return indice


def estabelecimentos_da_base(pasta: Path) -> dict[str, Estabelecimento]:
    """Lê qualquer uma das duas bases sem alterar o cadastro usado na conversa."""
    return _indice(Path(pasta))


def get_estabelecimento(imovel_id: str) -> Estabelecimento:
    try:
        return _indice()[imovel_id]
    except KeyError:
        raise KeyError(f"Estabelecimento não encontrado: {imovel_id}") from None


def listar_estabelecimentos() -> list[str]:
    return list(_indice())


# ---------- referências por segmento (base de desenvolvimento, nunca a de teste) ----------

PASTA_REFERENCIA = config.RAIZ / "Seguro_Empresarial_Desenvolvimento"


class PerfilSegmento(BaseModel):
    """Medianas de um grupo de atividade, para estimar o que um cliente novo ainda não disse."""

    segmento: str
    funcionarios: float
    estoque_medio: float
    bens_ponderado: float
    faturamento: float
    aluguel: float
    salario_medio: float
    despesa_sobre_faturamento: float
    pico_sobre_estoque: float
    refrigeracao: float
    delivery: float
    percentual_delivery: float
    recebimentos_digitais: float
    partes_bens: dict[str, float]
    """Tipo de bem → parte do valor ponderado do segmento (soma 1)."""
    cadastrado_sobre_ponderado: float


def _mediana(valores: list[float], padrao: float) -> float:
    v = sorted(x for x in valores if x is not None)
    return v[len(v) // 2] if v else padrao


def _ler_ref(arquivo: str) -> list[dict]:
    with open(PASTA_REFERENCIA / arquivo, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


@cache
def _perfis_segmento() -> dict[str, PerfilSegmento]:
    empresas = {e["empresa_id"]: e for e in _ler_ref("empresas.csv")}
    sinais = _ler_ref("sinais_financeiros_operacionais.csv")
    enderecos = _ler_ref("enderecos_estabelecimentos.csv")
    segmento_do_imovel = {e["imovel_id"]: empresas[e["empresa_id"]]["grupo_atividade"] for e in enderecos}
    bens_por_seg: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    cad_por_seg: dict[str, float] = defaultdict(float)
    pond_por_imovel: dict[str, float] = defaultdict(float)
    for b in _ler_ref("bens_cadastrados.csv"):
        seg = segmento_do_imovel.get(b["imovel_id_referencia"])
        if seg is None:
            continue
        bens_por_seg[seg][b["tipo_bem"]] += _num(b["valor_bem_ponderado_referencia"])
        cad_por_seg[seg] += _num(b["valor_cadastrado"])
        pond_por_imovel[b["imovel_id_referencia"]] += _num(b["valor_bem_ponderado_referencia"])
    linhas = defaultdict(list)
    for s in sinais:
        emp = empresas[s["empresa_id"]]
        linhas[emp["grupo_atividade"]].append((s, emp))
    perfis = {}
    for seg, rows in linhas.items():
        fat = [_num(e["faturamento_mensal"]) for _, e in rows]
        func = [_num(e["quantidade_funcionarios_estimada"]) for _, e in rows]
        partes = bens_por_seg[seg]
        total_bens = sum(partes.values()) or 1
        perfis[seg] = PerfilSegmento(
            segmento=seg,
            funcionarios=_mediana(func, 6),
            estoque_medio=_mediana([_num(s["estoque_medio_estimado"]) for s, _ in rows], 25_000),
            bens_ponderado=_mediana([pond_por_imovel.get(s["imovel_id"], 0) for s, _ in rows], 130_000),
            faturamento=_mediana(fat, 190_000),
            aluguel=_mediana([_num(s["valor_aluguel_recorrente"]) for s, _ in rows if s["pagamento_aluguel_recorrente"] == "SIM"], 10_000),
            salario_medio=_mediana(
                [_num(s["folha_pagamento_mensal"]) / max(_num(e["quantidade_funcionarios_estimada"]), 1) for s, e in rows], 3_000
            ),
            despesa_sobre_faturamento=_mediana(
                [_num(s["despesa_fixa_mensal_estimada"]) / _num(e["faturamento_mensal"]) for s, e in rows if _num(e["faturamento_mensal"])], 0.4
            ),
            pico_sobre_estoque=_mediana(
                [_num(s["estoque_pico_estimado"]) / _num(s["estoque_medio_estimado"]) for s, _ in rows if _num(s["estoque_medio_estimado"])], 1.3
            ),
            refrigeracao=_mediana([_num(s["probabilidade_refrigeracao_referencia"]) for s, _ in rows], 0.3),
            delivery=_mediana([_num(s["probabilidade_delivery_referencia"]) for s, _ in rows], 0.2),
            percentual_delivery=_mediana(
                [_num(e["percentual_receita_delivery_est"]) for _, e in rows if _num(e["percentual_receita_delivery_est"])], 0.2
            ),
            recebimentos_digitais=_mediana([_num(s["percentual_recebimentos_digitais"]) for s, _ in rows], 0.5),
            partes_bens={tipo: v / total_bens for tipo, v in partes.items()},
            cadastrado_sobre_ponderado=(cad_por_seg[seg] / sum(partes.values())) if partes else 1.3,
        )
    return perfis


def perfil_segmento(segmento: str | None) -> PerfilSegmento:
    """Referência do segmento; para um segmento fora da base, a mediana de todos (marcada como OUTRO)."""
    perfis = _perfis_segmento()
    if segmento in perfis:
        return perfis[segmento]
    todos = list(perfis.values())
    media_partes: dict[str, float] = defaultdict(float)
    for p in todos:
        for tipo, parte in p.partes_bens.items():
            media_partes[tipo] += parte / len(todos)
    campos = {
        campo: _mediana([getattr(p, campo) for p in todos], 0)
        for campo in PerfilSegmento.model_fields
        if campo not in ("segmento", "partes_bens")
    }
    return PerfilSegmento(segmento="OUTRO", partes_bens=dict(media_partes), **campos)
