"""Fase 2: a base de cláusulas extraída do PDF e as objeções estão íntegras."""

import json

import pytest

from agente import config, rag
from agente.contratos import Plano

OBJECOES = [
    json.loads(linha) for linha in (config.RAIZ / "conhecimento" / "objecoes.jsonl").open(encoding="utf-8")
]


def test_ids_unicos_e_validos():
    ids = [c.id for c in rag.clausulas()]
    assert len(ids) == len(set(ids)) > 800


def test_toda_cobertura_do_catalogo_tem_clausulas_com_os_planos_do_catalogo():
    for cobertura, planos in rag._catalogo().items():
        do_pdf = [c for c in rag.clausulas() if c.cobertura == cobertura]
        assert do_pdf, cobertura
        assert all(sorted(c.planos) == sorted(planos) for c in do_pdf), cobertura


def test_coberturas_fora_do_catalogo_nao_tem_plano():
    fora = [c for c in rag.clausulas() if not c.no_catalogo]
    assert fora and all(c.planos == [] for c in fora)


@pytest.mark.parametrize(
    "id_, trecho",
    [
        ("CG-8.2.a", "ataques cibernéticos"),
        ("CG-8.1.i", "Furto simples"),
        ("CG-8.1.l", "Alagamento"),
        ("ROUBO_FURTO_ARROMBAMENTO-3.1.c", "estelionato"),
        ("DANOS_ELETRICOS-1.1", "variações anormais de tensão"),
        ("TT-FURTO_SIMPLES", "sem vestígio"),
        ("CG-9.1", "Franquia"),
    ],
)
def test_clausulas_chave_extraidas_com_o_texto_certo(id_, trecho):
    assert trecho in rag.por_id()[id_].texto


def test_clausula_de_atividade_tem_segmento():
    assert rag.por_id()["ROUBO_FURTO_ARROMBAMENTO-2.1"].segmentos == ["BELEZA", "RESTAURANTE"]
    assert rag.por_id()["RESPONSABILIDADE_CIVIL_ESTABELECIMENTO-3.3.1.a"].segmentos == ["FARMACIA"]


@pytest.mark.parametrize("objecao", OBJECOES, ids=[o["id"] for o in OBJECOES])
def test_objecao_cita_clausulas_existentes(objecao):
    assert objecao["clausulas"]
    assert all(i in rag.por_id() for i in objecao["clausulas"])


def test_catalogo_estruturado():
    # A documentação do BB Radar listou só ESSENCIAL e PRATICO; o catálogo tem os três.
    assert rag.planos_com_cobertura("DANOS_ELETRICOS") == [Plano.ESSENCIAL, Plano.PRATICO, Plano.TOTAL]
    assert rag.planos_com_cobertura("QUEBRA_DE_VIDROS") == [Plano.TOTAL]
    assert len(rag.coberturas_do_plano(Plano.ESSENCIAL)) == 6
    assert len(rag.coberturas_do_plano(Plano.TOTAL)) == 10
