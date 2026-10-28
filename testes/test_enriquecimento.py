import csv

import pytest

from agente import config
from agente.decisor import ClaudeDecisor, JevDecisor
from agente.enriquecimento import classificar_cnae, consultar_cnpj, enriquecer_cnpj

CNAES = sorted(
    {
        (linha["descricao_cnae"], linha["grupo_atividade"])
        for pasta in ("Seguro_Empresarial_Teste_Comum", "Seguro_Empresarial_Desenvolvimento")
        for linha in csv.DictReader(open(config.RAIZ / pasta / "empresas.csv", encoding="utf-8-sig"))
    }
)
CNPJ_PUBLICO = "00.000.000/0001-91"  # Banco do Brasil, dado aberto da Receita


@pytest.fixture(scope="module", params=["jev", "claude"])
def decisor(request):
    if request.param == "jev":
        if not config.chave_jev():
            pytest.skip("JEV_API_KEY ausente")
        return JevDecisor()
    return ClaudeDecisor()


def test_cnae_para_segmento_bate_com_a_base(decisor):
    erros = [(d, g, s.valor) for d, g in CNAES if (s := classificar_cnae(d, decisor)).valor != g]
    assert len(erros) <= 2, erros  # 28 CNAEs da base; meta ≥ 26


def test_cnpj_do_cache_sem_rede():
    dados, fonte = consultar_cnpj(CNPJ_PUBLICO, usar_rede=False)
    assert fonte == "cache" and dados["razao_social"] == "BANCO DO BRASIL SA"


def test_cnpj_fora_dos_segmentos_vira_outro(decisor):
    resultado = enriquecer_cnpj(CNPJ_PUBLICO, decisor, usar_rede=False)
    assert resultado.segmento.valor == "OUTRO"


def test_cnpj_invalido():
    with pytest.raises(ValueError):
        consultar_cnpj("123")
