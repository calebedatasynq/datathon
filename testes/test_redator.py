"""Fase 4: as três personas recebem resposta coerente com o plano e com cláusula citada."""

import json
import unicodedata

import pytest

from agente import config
from agente.decisor import criar_decisor
from scripts.rodar_personas import MENSAGENS, turno

PERSONAS = json.loads((config.RAIZ / "dados" / "fixtures" / "personas.json").read_text(encoding="utf-8"))


def _normal(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto.upper()) if unicodedata.category(c) != "Mn")


@pytest.fixture(scope="module")
def decisor():
    return criar_decisor()


@pytest.fixture(scope="module", params=list(PERSONAS))
def resultado(request, decisor):
    plano = request.param
    return plano, turno(PERSONAS[plano]["cliente_id"], MENSAGENS[plano], decisor)


def test_resposta_cita_so_clausulas_recuperadas(resultado):
    _, r = resultado
    recuperadas = {c.id for c in r["clausulas"]}
    assert r["redacao"].citacoes, r["redacao"].texto
    assert set(r["redacao"].citacoes) <= recuperadas, r["redacao"].texto


def test_resposta_fala_do_plano_calculado(resultado):
    _, r = resultado
    assert _normal(r["atualizado"].plano.value) in _normal(r["redacao"].texto)


def test_no_maximo_uma_pergunta(resultado):
    _, r = resultado
    assert r["redacao"].texto.count("?") <= 1


def test_fronteira_muda_de_plano_com_a_confirmacao(resultado):
    plano, r = resultado
    if plano != "PRATICO":
        pytest.skip("só a persona de fronteira tem pergunta pendente")
    assert (r["atualizado"].plano_anterior, r["atualizado"].plano) == ("PRATICO", "TOTAL")


def test_pedido_fora_da_cobertura_e_recusado_com_a_exclusao(decisor):
    r = turno(PERSONAS["TOTAL"]["cliente_id"], "Se um hacker sequestrar meus sistemas com ransomware, o seguro paga?", decisor)
    assert "CG-8.2.a" in r["redacao"].citacoes, r["redacao"].texto
