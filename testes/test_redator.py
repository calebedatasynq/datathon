"""As três personas recebem resposta coerente com o plano, com cláusula citada e completa."""

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
def resultado(request, decisor, tmp_path_factory):
    plano = request.param
    log = tmp_path_factory.mktemp("log") / "turnos.jsonl"
    return plano, turno(PERSONAS[plano]["cliente_id"], MENSAGENS[plano], decisor, log)


def test_resposta_aprovada_e_cita_so_clausulas_do_turno(resultado):
    _, e = resultado
    assert e.guardrail.aprovado and not e.requer_humano, e.resposta
    recuperadas = {c.id for c in e.clausulas}
    from agente.redator import citacoes

    assert citacoes(e.resposta) and set(citacoes(e.resposta)) <= recuperadas


def test_resposta_fala_do_plano_calculado(resultado):
    _, e = resultado
    assert _normal(e.perfil_atualizado.plano.value) in _normal(e.resposta)


def test_no_maximo_uma_pergunta(resultado):
    _, e = resultado
    assert e.resposta.count("?") <= 1


def test_fronteira_muda_de_plano_com_a_confirmacao(resultado):
    plano, e = resultado
    if plano != "PRATICO":
        pytest.skip("só a persona de fronteira tem pergunta pendente")
    assert (e.perfil_atualizado.plano_anterior, e.perfil_atualizado.plano) == ("PRATICO", "TOTAL")
    assert e.plano_personalizado.plano_base == "TOTAL"


def test_cibernetico_e_tratado_como_incluido(decisor, tmp_path):
    e = turno(
        PERSONAS["ESSENCIAL"]["cliente_id"],
        "Se um hacker sequestrar meus sistemas com ransomware, o seguro ajuda?",
        decisor,
        tmp_path / "t.jsonl",
    )
    from agente.redator import citacoes

    assert "SITE-CIBERNETICA" in citacoes(e.resposta), e.resposta
    assert "CG-8.2.a" not in citacoes(e.resposta)


def test_enchente_continua_recusada(decisor, tmp_path):
    e = turno(PERSONAS["TOTAL"]["cliente_id"], "A enchente alagou a loja, o seguro paga?", decisor, tmp_path / "t.jsonl")
    from agente.redator import citacoes

    assert "CG-8.1.l" in citacoes(e.resposta), e.resposta
