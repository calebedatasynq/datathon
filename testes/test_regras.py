import json

import pytest

from agente import config
from agente.contratos import Confirmacao, Plano
from agente.perfil import get_perfil_cliente, plano_de
from agente.regras import aplicar_confirmacao, valor_confirmado

PERSONAS = json.loads((config.RAIZ / "dados" / "fixtures" / "personas.json").read_text(encoding="utf-8"))


@pytest.fixture
def fronteira():
    return get_perfil_cliente(PERSONAS["PRATICO"]["cliente_id"])


def _confirmacao(perfil, valor):
    return Confirmacao(pergunta_id=perfil.perguntas_pendentes[0].id, valor=valor, probabilidade=0.95)


def test_sim_recalcula_com_o_motor(fronteira):
    pergunta = fronteira.perguntas_pendentes[0]
    atualizado, novo = aplicar_confirmacao(fronteira, _confirmacao(fronteira, "sim"))
    assert atualizado.plano_anterior == Plano.PRATICO
    assert atualizado.plano == pergunta.plano_se_sim == Plano.TOTAL
    assert novo.plano == plano_de(novo.entrada)  # mesma regra do motor, sem atalho
    assert novo.entrada[pergunta.variavel] >= pergunta.limiar


def test_nao_mantem_o_plano(fronteira):
    atualizado, novo = aplicar_confirmacao(fronteira, _confirmacao(fronteira, "nao"))
    assert atualizado.plano == fronteira.perguntas_pendentes[0].plano_se_nao == Plano.PRATICO


@pytest.mark.parametrize("valor", ["sim", "nao"])
def test_depois_de_confirmar_nao_pergunta_mais(fronteira, valor):
    atualizado, novo = aplicar_confirmacao(fronteira, _confirmacao(fronteira, valor))
    assert atualizado.proxima_pergunta is None and novo.perguntas_pendentes == []
    assert novo.confirmadas == [fronteira.perguntas_pendentes[0].variavel]


@pytest.mark.parametrize("valor", [None, "nao_sabe", "nao_respondeu"])
def test_sem_confirmacao_aplicavel_nada_muda(fronteira, valor):
    confirmacao = None if valor is None else _confirmacao(fronteira, valor)
    atualizado, novo = aplicar_confirmacao(fronteira, confirmacao)
    assert novo is fronteira
    assert atualizado.plano == atualizado.plano_anterior == Plano.PRATICO
    assert atualizado.proxima_pergunta == fronteira.perguntas_pendentes[0]


def test_valor_estimado_do_lado_certo_e_mantido(fronteira):
    pergunta = fronteira.perguntas_pendentes[0].model_copy(update={"valor_estimado": 40, "limiar": 23})
    assert valor_confirmado(pergunta, "sim") == 40
    assert valor_confirmado(pergunta, "nao") == 22
