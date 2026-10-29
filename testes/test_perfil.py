import json

import pytest

from agente import config
from agente.contratos import Plano
from agente.perfil import (
    _com,
    get_perfil_cliente,
    listar_clientes,
    perfil_de_entrada,
    plano_de,
    score_empresa,
)

PERSONAS = json.loads((config.RAIZ / "dados" / "fixtures" / "personas.json").read_text(encoding="utf-8"))
REFERENCIA = {
    json.loads(linha)["imovel_id"]: json.loads(linha)
    for linha in (config.DIR_MOTOR / "exemplos" / "perfis_teste_prontos.jsonl").open(encoding="utf-8")
}


def test_base_tem_144_estabelecimentos():
    assert len(listar_clientes()) == 144


@pytest.mark.parametrize("cliente_id", list(REFERENCIA))
def test_score_e_plano_iguais_ao_motor(cliente_id):
    perfil = get_perfil_cliente(cliente_id)
    assert perfil.score == pytest.approx(REFERENCIA[cliente_id]["score"], abs=1e-12)
    assert perfil.plano == REFERENCIA[cliente_id]["plano_sugerido"]


@pytest.mark.parametrize("plano", list(Plano))
def test_personas_tem_perfil_completo(plano):
    # A persona é definida pelo pacote de contratação do plano personalizado, não só pelo índice.
    from agente.dados_base import get_estabelecimento
    from agente.personalizacao import personalizar

    cliente_id = PERSONAS[plano]["cliente_id"]
    perfil = get_perfil_cliente(cliente_id)
    assert personalizar(perfil, get_estabelecimento(cliente_id)).plano_base == plano
    assert perfil.status == "EXPERIMENTAL_BASE_MOCK"
    assert perfil.segmento and perfil.score is not None and perfil.probabilidades
    assert not perfil.avisos or PERSONAS[plano]["tipo"] == "fronteira"  # só a fronteira aceita área imputada


def test_persona_fronteira_tem_pergunta_que_muda_o_plano():
    from agente.dados_base import get_estabelecimento
    from agente.personalizacao import perfil_relevante

    cliente_id = PERSONAS["PRATICO"]["cliente_id"]
    perfil = perfil_relevante(get_perfil_cliente(cliente_id), get_estabelecimento(cliente_id))
    assert len(perfil.perguntas_pendentes) == 1
    pergunta = perfil.perguntas_pendentes[0]
    assert pergunta.plano_se_sim != pergunta.plano_se_nao


@pytest.mark.parametrize("cliente_id", listar_clientes())
def test_pergunta_bate_com_o_motor(cliente_id):
    perfil = get_perfil_cliente(cliente_id)
    for p in perfil.perguntas_pendentes:
        # O limiar é exatamente onde score_empresa troca de plano, dentro da margem.
        assert abs(p.limiar / p.valor_estimado - 1) <= config.MARGEM_PERGUNTA
        assert plano_de(_com(perfil.entrada, p.variavel, p.limiar)) == p.plano_se_sim
        assert perfil.plano in (p.plano_se_sim, p.plano_se_nao)


def test_no_maximo_uma_pergunta():
    assert all(len(get_perfil_cliente(c).perguntas_pendentes) <= 1 for c in listar_clientes())


def test_dado_essencial_ausente_suspende_plano_sem_pergunta():
    entrada = get_perfil_cliente(PERSONAS["TOTAL"]["cliente_id"]).entrada
    perfil = perfil_de_entrada({**entrada, "estoque_medio_estimado": None})
    assert perfil.status == "PRECISA_CONFIRMACAO"
    assert perfil.plano is None and perfil.score is None
    assert perfil.perguntas_pendentes == []


def test_cliente_inexistente():
    with pytest.raises(KeyError):
        get_perfil_cliente("NAO_EXISTE")


def test_motor_e_o_do_pacote():
    assert score_empresa.__module__ == "motor_score"
