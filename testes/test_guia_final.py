"""Regras do guia final independentes das expectativas antigas do MVP."""
from agente import rag
from agente.dados_base import get_estabelecimento
from agente.perfil import get_perfil_cliente, listar_clientes
from agente.personalizacao import personalizar, RESTRITAS_PRATICO_TOTAL


def caso(**mudancas):
    cliente = listar_clientes()[0]
    return get_perfil_cliente(cliente), get_estabelecimento(cliente).model_copy(update=mudancas)


def test_cibernetica_obrigatoria_com_faixa_de_referencia_explicita():
    p, e = caso(situacao_imovel="REGULAR")
    proposta = personalizar(p, e)
    c = next(c for c in proposta.coberturas if c.cobertura == "AMPLA_PROTECAO_CIBERNETICA")
    assert c.origem == "plano" and c.confianca == "BAIXA"
    assert c.faixa_valor_min == 20000 and c.faixa_valor_max == 40000
    assert "não é limite confirmado" in c.regra_calculo
    assert all(c.cobertura in rag.coberturas_do_plano(plano) for plano in ("ESSENCIAL", "PRATICO", "TOTAL"))


def test_obra_bloqueia_proposta_e_material_ausente_pede_confirmacao():
    p, e = caso(situacao_imovel="EM_OBRA")
    r = personalizar(p, e)
    assert r.elegivel == "NAO" and r.plano_base is None and r.coberturas == []
    p, e = caso(situacao_imovel="REGULAR", material_parede_externa="NAO_DISPONIVEL")
    assert personalizar(p, e).elegivel == "A_CONFIRMAR"


def test_todas_sugestoes_respeitam_coberturas_restritas():
    for cliente in listar_clientes():
        r = personalizar(get_perfil_cliente(cliente), get_estabelecimento(cliente))
        if r.plano_base == "ESSENCIAL":
            assert not RESTRITAS_PRATICO_TOTAL.intersection(c.cobertura for c in r.coberturas)


def test_limite_basico_acima_do_produto_exige_encaminhamento():
    p, e = caso(situacao_imovel="REGULAR", estoque_pico=8_000_000)
    r = personalizar(p, e)
    assert r.elegivel == "A_CONFIRMAR"
    assert "Seguro Personalizado Empresarial" in r.motivo_elegibilidade


def test_restricoes_ausentes_nao_sao_tratadas_como_confirmadas():
    p, e = caso(situacao_imovel="REGULAR", material_parede_externa="ALVENARIA", endereco_cnpj_compativel=True, risco=None)
    assert personalizar(p, e).elegivel == "A_CONFIRMAR"
    confirmado = e.model_copy(update={"confirmacoes_elegibilidade": {
        k: True for k in ("atividade_aceita", "local_aceito", "sem_tombamento", "sem_seguro_bb_duplicado")}})
    assert personalizar(p, confirmado).elegivel == "SIM"
    assert len(personalizar(p, confirmado).alternativas) == 2


def test_redator_recebe_pendencias_e_alternativas():
    from agente.redator import resumo_personalizado
    p, e = caso(situacao_imovel="REGULAR")
    entrada = resumo_personalizado(personalizar(p, e))
    assert entrada["elegibilidade"] == "A_CONFIRMAR"
    assert entrada["confirmacoes_necessarias"] and entrada["alternativas_para_comparacao"]
