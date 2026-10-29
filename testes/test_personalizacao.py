"""Plano personalizado cobertura por cobertura, para os 144 estabelecimentos."""

import json

import pytest

from agente import config, rag
from agente.contratos import Confirmacao, Plano
from agente.dados_base import get_estabelecimento, listar_estabelecimentos
from agente.perfil import get_perfil_cliente, listar_clientes, perfil_de_entrada
from agente.personalizacao import (
    CLAUSULAS,
    DIMENSIONAR,
    ESSENCIAL,
    MINIMO_RELEVANTE_ADICIONAL,
    NAO_SE_APLICA,
    ORDEM_PACOTES,
    RECOMENDADA,
    est_com_entrada,
    inconsistencias,
    necessidades,
    perfil_relevante,
    personalizar,
)
from agente.regras import aplicar_confirmacao

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
    niveis = necessidades(est_com_entrada(get_estabelecimento(cliente_id), perfil.entrada))
    assert p.plano_motor == perfil.plano
    # nunca abaixo do índice do motor e sempre com as essenciais que existem em pacote
    assert ORDEM_PACOTES.index(p.plano_base) >= ORDEM_PACOTES.index(perfil.plano)
    do_pacote = rag.coberturas_do_plano(p.plano_base)
    essenciais_de_catalogo = {c for c, (n, _) in niveis.items() if n == ESSENCIAL and rag.planos_com_cobertura(c)}
    assert essenciais_de_catalogo <= set(do_pacote)
    # todas as coberturas do pacote entram; fora dele, só o que é necessário vira adicional
    assert [c.cobertura for c in p.coberturas if c.origem == "plano"] == do_pacote
    for c in p.coberturas:
        assert 0 < c.faixa_valor_min <= c.faixa_valor_max, c
        assert c.confianca in {"ALTA", "MEDIA", "BAIXA"} and c.regra_calculo and c.dados_utilizados
        assert c.necessidade != NAO_SE_APLICA and c.motivo_necessidade
        if c.origem == "adicional":
            assert c.cobertura not in do_pacote and c.necessidade in {ESSENCIAL, RECOMENDADA}
            assert c.faixa_valor_max >= MINIMO_RELEVANTE_ADICIONAL
        if c.origem == "opcional":
            assert c.cobertura not in do_pacote
    assert p.elegivel in {"SIM", "A_CONFIRMAR"}


def test_planos_sao_de_fato_personalizados():
    composicoes = {
        (p.plano_base, frozenset(c.cobertura for c in p.coberturas if c.origem != "opcional")) for p in TODOS.values()
    }
    assert len(composicoes) >= 20  # 144 clientes, não 3 pacotes


def test_aluguel_respeita_o_limite_de_12_meses_da_clausula():
    for c in listar_clientes():
        est = get_estabelecimento(c)
        cob = next((x for x in TODOS[c].coberturas if x.cobertura == "PERDA_PAGAMENTO_ALUGUEL"), None)
        if cob and est.paga_aluguel and est.valor_aluguel:
            assert cob.faixa_valor_max <= 12 * est.valor_aluguel + 1000


def test_inconsistencia_financeira_baixa_a_confianca():
    com_achado = [c for c in listar_clientes() if inconsistencias(get_estabelecimento(c))]
    assert com_achado
    for c in com_achado:
        p = TODOS[c]
        assert p.dados_a_conferir and p.confianca_geral != "ALTA"


def test_confirmacao_do_cliente_muda_as_necessidades():
    # Uma persona de fronteira: o sim e o não levam a planos personalizados diferentes.
    cliente = PERSONAS["PRATICO"]["cliente_id"]
    est = get_estabelecimento(cliente)
    perfil = perfil_relevante(get_perfil_cliente(cliente), est)
    pergunta = perfil.perguntas_pendentes[0]
    planos = {}
    for valor in ("sim", "nao"):
        _, novo = aplicar_confirmacao(perfil, Confirmacao(pergunta_id=pergunta.id, valor=valor, probabilidade=1))
        p = personalizar(novo, est)
        planos[valor] = (p.plano_base, {c.cobertura for c in p.coberturas if c.origem != "opcional"})
    assert planos["sim"] != planos["nao"]


def test_pergunta_que_nao_muda_o_plano_e_descartada():
    descartadas = [
        c
        for c in listar_clientes()
        if get_perfil_cliente(c).perguntas_pendentes
        and not perfil_relevante(get_perfil_cliente(c), get_estabelecimento(c)).perguntas_pendentes
    ]
    assert descartadas  # o motor perguntaria, mas o plano personalizado não mudaria


def test_dado_essencial_ausente_ainda_monta_pelas_necessidades():
    cliente = PERSONAS["TOTAL"]["cliente_id"]
    perfil = perfil_de_entrada({**get_perfil_cliente(cliente).entrada, "estoque_medio_estimado": None})
    p = personalizar(perfil, get_estabelecimento(cliente))
    assert p.plano_motor is None and p.plano_base == p.pacote_minimo
    assert p.elegivel == "A_CONFIRMAR" and p.confianca_geral == "BAIXA"


def test_obra_no_imovel_fica_a_confirmar_com_a_clausula():
    em_obra = [c for c in listar_clientes() if get_estabelecimento(c).situacao_imovel == "EM_OBRA"]
    assert em_obra and all(TODOS[c].elegivel == "A_CONFIRMAR" and "CG-7.1.u" in TODOS[c].motivo_elegibilidade for c in em_obra)


def test_incendio_sempre_essencial_e_nunca_aparece_cobertura_que_nao_se_aplica():
    assert all(
        next(c for c in p.coberturas if c.cobertura == "INCENDIO_RAIO_EXPLOSAO_FUMACA").necessidade == ESSENCIAL
        for p in TODOS.values()
    )


def test_pacote_essencial_so_quando_nada_essencial_fica_de_fora():
    for p in TODOS.values():
        if p.plano_base == Plano.ESSENCIAL:
            assert not [c for c in p.coberturas if c.origem == "adicional" and c.necessidade == ESSENCIAL and rag.planos_com_cobertura(c.cobertura)]
