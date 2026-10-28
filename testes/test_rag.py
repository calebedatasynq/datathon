"""Fase 2: a busca traz a cláusula esperada no top 5.

dados/fixtures/perguntas_rag.json tem dois conjuntos: "ajuste" (usado para calibrar a busca)
e "validacao" (escrito depois, nunca usado para calibrar). Meta do plano: ≥ 90%; pedidos fora
da cobertura (a cláusula de exclusão precisa aparecer): 100%.
"""

import json

import pytest

from agente import config, rag
from agente.contratos import Plano

PERGUNTAS = json.loads((config.RAIZ / "dados" / "fixtures" / "perguntas_rag.json").read_text(encoding="utf-8"))
EXCLUSOES = {"CG-8.2.a", "CG-8.1.l", "CG-8.1.i", "ROUBO_FURTO_ARROMBAMENTO-3.1.c"}
FORA_DA_COBERTURA = [
    q
    for conjunto in ("ajuste", "validacao")
    for q in PERGUNTAS[conjunto]
    if EXCLUSOES & set(q["esperadas"])
]


def acerta(ids: list[str], esperadas: list[str]) -> bool:
    return any(i == e or (e.endswith("*") and i.startswith(e[:-1])) for i in ids for e in esperadas)


@pytest.fixture(params=["hibrido", "bm25"])
def modo(request, monkeypatch):
    monkeypatch.setattr(config, "MODO_BUSCA", request.param)
    if request.param == "hibrido" and rag.modo_efetivo() != "hibrido":
        pytest.skip("índice vetorial ausente: rode scripts/indexar_rag.py")
    return request.param


def test_ids_esperados_existem():
    for conjunto in ("ajuste", "validacao"):
        for q in PERGUNTAS[conjunto]:
            for e in q["esperadas"]:
                assert any(i.startswith(e[:-1]) for i in rag.por_id()) if e.endswith("*") else e in rag.por_id()


@pytest.mark.parametrize("conjunto", ["ajuste", "validacao"])
def test_top5_acima_de_90_por_cento(conjunto, modo):
    erros = [
        q["pergunta"]
        for q in PERGUNTAS[conjunto]
        if not acerta([c.id for c in rag.buscar(q["pergunta"], k=5)], q["esperadas"])
    ]
    taxa = 1 - len(erros) / len(PERGUNTAS[conjunto])
    assert taxa >= 0.9, f"{modo}/{conjunto}: {taxa:.0%}; erros: {erros}"


@pytest.mark.parametrize("q", FORA_DA_COBERTURA, ids=[q["pergunta"][:40] for q in FORA_DA_COBERTURA])
def test_pedido_fora_da_cobertura_traz_a_exclusao(q, modo):
    assert acerta([c.id for c in rag.buscar(q["pergunta"], k=5)], q["esperadas"])


def test_filtro_de_segmento():
    pergunta = "roubaram os pertences dos clientes no restaurante durante o assalto"
    restaurante = [c.id for c in rag.buscar(pergunta, segmento="RESTAURANTE", k=10)]
    farmacia = [c.id for c in rag.buscar(pergunta, segmento="FARMACIA", k=10)]
    assert "ROUBO_FURTO_ARROMBAMENTO-2.1" in restaurante
    assert "ROUBO_FURTO_ARROMBAMENTO-2.1" not in farmacia


def test_etiqueta_no_plano():
    roubo = next(c for c in rag.buscar("arrombaram a loja", plano=Plano.ESSENCIAL) if c.id.startswith("ROUBO_FURTO"))
    assert roubo.no_plano is False
    roubo = next(c for c in rag.buscar("arrombaram a loja", plano=Plano.PRATICO) if c.id.startswith("ROUBO_FURTO"))
    assert roubo.no_plano is True


def test_no_maximo_duas_por_cobertura_e_tipo():
    resultado = rag.buscar("quebraram a vitrine de vidro", k=5)
    grupos = [(c.parte, c.cobertura, c.tipo) for c in resultado]
    assert all(grupos.count(g) <= rag.MAX_POR_GRUPO for g in grupos)


def test_expansao_so_acrescenta():
    assert rag.expandir("caí num golpe de PIX").startswith("caí num golpe de PIX")
    assert "estelionato" in rag.expandir("caí num golpe de PIX")
