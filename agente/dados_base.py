"""Dados originais do desafio por estabelecimento (empresa + endereço + sinais + bens).

O motor de score usa a base preparada; a personalização usa estes dados mais finos.
"""

import csv
from collections import defaultdict
from functools import cache
from pathlib import Path

from pydantic import BaseModel

from agente import config

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
