"""Plano personalizado: plano base + adicionais + faixa por cobertura, para os 144 estabelecimentos."""

import json

import pytest

from agente import config, rag
from agente.contratos import Plano
from agente.dados_base import get_estabelecimento, listar_estabelecimentos
from agente.perfil import get_perfil_cliente, listar_clientes, perfil_de_entrada
from agente.personalizacao import (
    CLAUSULAS,
    DIMENSIONAR,
    MINIMO_RELEVANTE_ADICIONAL,
    inconsistencias,
    personalizar,
)

PERSONAS = json.loads((config.RAIZ / "dados" / "fixtures" / "personas.json").read_text(encoding="utf-8"))
TODOS = {c: personalizar(get_perfil_cliente(c), get_estabelecimento(c)) for c in listar_clientes()}


def test_base_original_cobre_os_mesmos_estabelecimentos_do_motor():
    assert set(listar_estabelecimentos()) == set(listar_clientes())


def test_toda_cobertura_tem_regra_e_clausula_existente():
    assert set(CLAUSULAS) == set(DIMENSIONAR)
    assert all(i in rag.por_id() for ids in CLAUSULAS.values() for i in ids)


@pytest.mark.parametrize("cliente_id", list(TODOS))
def test_plano_personalizado_completo_e_coerente(cliente_id):
    p = TODOS[cliente_id]
    perfil = get_perfil_cliente(cliente_id)
    assert p.plano_base == perfil.plano
    fixas = [c.cobertura for c in p.coberturas if c.origem == "plano"]
    assert fixas == rag.coberturas_do_plano(perfil.plano)  # todas as fixas do plano, sem tirar nenhuma
    for c in p.coberturas:
        assert 0 < c.faixa_valor_min <= c.faixa_valor_max, c
        assert c.confianca in {"ALTA", "MEDIA", "BAIXA"} and c.regra_calculo and c.dados_utilizados
    for c in p.adicionais:
        assert c.cobertura not in fixas and c.faixa_valor_max >= MINIMO_RELEVANTE_ADICIONAL
    assert p.elegivel in {"SIM", "A_CONFIRMAR"}


def test_adicional_preenche_o_que_o_plano_base_nao_tem():
    essencial_com_roubo = [
        p for p in TODOS.values() if p.plano_base == Plano.ESSENCIAL and "ROUBO_FURTO_ARROMBAMENTO" in {c.cobertura for c in p.adicionais}
    ]
    assert essencial_com_roubo  # o ESSENCIAL não tem roubo; quem tem estoque relevante recebe o adicional
    assert not any("ROUBO_FURTO_ARROMBAMENTO" in {c.cobertura for c in p.adicionais} for p in TODOS.values() if p.plano_base != Plano.ESSENCIAL)


def test_aluguel_respeita_o_limite_de_12_meses_da_clausula():
    for c in listar_clientes():
        est = get_estabelecimento(c)
        cob = next((x for x in TODOS[c].coberturas if x.cobertura == "PERDA_PAGAMENTO_ALUGUEL"), None)
        if cob and est.paga_aluguel and est.valor_aluguel:
            assert cob.faixa_valor_max <= 12 * est.valor_aluguel + 1000


def test_inconsistencia_financeira_baixa_a_confianca():
    persona = PERSONAS["ESSENCIAL"]["cliente_id"]  # aluguel e despesa fixa acima do faturamento do endereço
    p = TODOS[persona]
    assert inconsistencias(get_estabelecimento(persona)) and p.dados_a_conferir
    assert p.confianca_geral != "ALTA"
    aluguel = next(c for c in p.coberturas if c.cobertura == "PERDA_PAGAMENTO_ALUGUEL")
    assert aluguel.confianca == "BAIXA"


def test_dado_essencial_ausente_nao_inventa_plano():
    cliente = PERSONAS["TOTAL"]["cliente_id"]
    perfil = perfil_de_entrada({**get_perfil_cliente(cliente).entrada, "estoque_medio_estimado": None})
    p = personalizar(perfil, get_estabelecimento(cliente))
    assert p.plano_base is None and p.coberturas == [] and p.elegivel == "A_CONFIRMAR" and p.confianca_geral == "BAIXA"


def test_obra_no_imovel_fica_a_confirmar_com_a_clausula():
    em_obra = [c for c in listar_clientes() if get_estabelecimento(c).situacao_imovel == "EM_OBRA"]
    assert em_obra and all(TODOS[c].elegivel == "A_CONFIRMAR" and "CG-7.1.u" in TODOS[c].motivo_elegibilidade for c in em_obra)
