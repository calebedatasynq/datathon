"""Fase 3: camada de decisão. Meta: ≥ 18 de 20 confirmações certas."""

import json

import pytest

from agente import config
from agente.contratos import Confirmacao, Decisao, Decisoes
from agente.decisor import (
    Afirmacao,
    ClaudeDecisor,
    Decisor,
    DecisorComReserva,
    Escolha,
    JevDecisor,
    Nota,
    Resposta,
    confirmacao_aplicavel,
    decidir_turno,
    motivo_para_humano,
)
from agente.perfil import get_perfil_cliente
from scripts.avaliar_decisor import avaliar

PERSONAS = json.loads((config.RAIZ / "dados" / "fixtures" / "personas.json").read_text(encoding="utf-8"))
sem_jev = pytest.mark.skipif(not config.chave_jev(), reason="JEV_API_KEY ausente")


# ---------- regras fixas (sem API) ----------


def _decisoes(valor, p, rota="agente"):
    return Decisoes(
        confirmacao=Confirmacao(pergunta_id="x", valor=valor, probabilidade=p),
        rota=Decisao(valor=rota, probabilidade=0.9),
    )


@pytest.mark.parametrize(
    "valor, p, rota, humano, aplica",
    [
        ("sim", 0.92, "agente", False, True),
        ("sim", 0.60, "agente", True, False),  # abaixo do limiar
        ("nao", 0.80, "agente", False, True),
        ("nao_sabe", 0.95, "agente", True, False),
        ("nao_respondeu", 0.99, "agente", False, False),
        ("sim", 0.92, "gerente", True, True),
    ],
)
def test_regras_de_humano_e_de_aplicacao(valor, p, rota, humano, aplica):
    decisoes = _decisoes(valor, p, rota)
    assert (motivo_para_humano(decisoes) is not None) == humano
    assert confirmacao_aplicavel(decisoes) == aplica


def test_payload_do_jev_segue_a_documentacao():
    assert JevDecisor._questao(Escolha(instrucao="i", opcoes={"a": None})) == {
        "type": "choice",
        "instructions": "i",
        "criteria": {"a": None},
    }
    assert JevDecisor._questao(Nota(instrucao="i", niveis=["baixo", "alto"]))["criteria"] == ["baixo", "alto"]
    assert JevDecisor._questao(Afirmacao(instrucao="i")) == {"type": "noul", "instructions": "i"}


class _Falha(Decisor):
    nome = "falha"

    def avaliar(self, contexto, questoes):
        raise ConnectionError("sem rede")


class _Fixo(Decisor):
    nome = "fixo"

    def avaliar(self, contexto, questoes):
        self.ultima_execucao = {"decisor": self.nome, "segundos": 0}
        return {n: Resposta(valor="x", probabilidade=1.0) for n in questoes}


def test_reserva_assume_quando_o_principal_falha():
    decisor = DecisorComReserva(_Falha(), _Fixo())
    assert decisor.escolher({}, "i", {"x": None}).valor == "x"
    assert decisor.ultima_execucao["decisor"] == "fixo"
    assert "sem rede" in decisor.ultima_execucao["falha_principal"]


# ---------- com API ----------


@sem_jev
def test_jev_confirmacoes_acima_da_meta():
    resultado = avaliar(JevDecisor())
    assert resultado["acertos"] >= 18, [l for l in resultado["linhas"] if not l["ok"]]


def test_plano_b_claude_confirmacoes_acima_da_meta():
    resultado = avaliar(ClaudeDecisor())
    assert resultado["acertos"] >= 18, [l for l in resultado["linhas"] if not l["ok"]]


@pytest.fixture(scope="module", params=["jev", "claude"])
def decisor(request):
    if request.param == "jev":
        if not config.chave_jev():
            pytest.skip("JEV_API_KEY ausente")
        return JevDecisor()
    return ClaudeDecisor()


@pytest.mark.parametrize(
    "mensagem, intencao",
    [
        ("o seguro cobre enchente?", "perguntar_cobertura"),
        ("achei caro, já tenho seguro em outro banco", "objecao"),
        ("pode fechar, quero contratar o plano", "quer_contratar"),
    ],
)
def test_intencao(decisor, mensagem, intencao):
    perfil = get_perfil_cliente(PERSONAS["TOTAL"]["cliente_id"])
    decisoes, _ = decidir_turno(perfil, mensagem, decisor)
    assert decisoes.intencao.valor == intencao


def test_pedido_de_pessoa_vai_para_o_gerente(decisor):
    perfil = get_perfil_cliente(PERSONAS["TOTAL"]["cliente_id"])
    decisoes, motivo = decidir_turno(perfil, "quero falar com o meu gerente, por favor", decisor)
    assert decisoes.rota.valor == "gerente" and motivo


def test_persona_fronteira_confirma_e_libera_o_dado(decisor):
    perfil = get_perfil_cliente(PERSONAS["PRATICO"]["cliente_id"])
    decisoes, motivo = decidir_turno(perfil, "somos uns 30 funcionários", decisor)
    assert decisoes.confirmacao.pergunta_id == perfil.perguntas_pendentes[0].id
    assert decisoes.confirmacao.valor == "sim" and confirmacao_aplicavel(decisoes)
    assert motivo is None
