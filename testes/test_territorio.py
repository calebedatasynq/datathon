"""Risco do local: níveis a partir dos indicadores, efeito no plano e na conversa do zero (sem rede)."""

import pytest

from agente import rag, territorio
from agente.contratos import Local
from agente.descoberta import SEM_CEP, ConversaDescoberta, cliente_virtual
from agente.personalizacao import necessidades
from agente.redator import resumo_personalizado
from testes.test_descoberta import DecisorFixo, RedatorEspiao

CEP = Local(cep="01310100", bairro="Bela Vista", municipio="São Paulo", uf="SP", latitude=-23.565, longitude=-46.652,
            precisao="CEP", fonte="teste")  # fmt: skip
MUNICIPIO = CEP.model_copy(update={"precisao": "MUNICIPIO", "cep": None})
CALMO = {"anos": 10, "chuva_forte_ano": 0.2, "chuva_maxima_mm": 60, "rajada_forte_ano": 0.1, "rajada_maxima_kmh": 70}
VENTOSO = {"anos": 10, "chuva_forte_ano": 3.5, "chuva_maxima_mm": 130, "rajada_forte_ano": 2.3, "rajada_maxima_kmh": 110}
SEM_TEMPESTADE = {"anos": 3, "trovoada_ano": 1.0, "granizo_ano": 0.0}
COM_GRANIZO = {"anos": 3, "trovoada_ano": 10.4, "granizo_ano": 2.7}
PLANO = {"altitude_m": 760, "declividade_pct": 3, "abaixo_do_entorno_m": -5}
MAPEADO = {"mapeado": True, "massa_alto": 2, "agua_alto": 1}


def _setor(tipo: str, grau: str, distancia: int) -> dict:
    return {"tipologias": [tipo], "grau": grau, "distancia_m": distancia, "setor": "X"}


def _risco(local=CEP, clima=CALMO, tempestades=SEM_TEMPESTADE, relevo=PLANO, proximos=(), municipio=MAPEADO, barragens=(), falhas=None):
    return territorio.avaliar(local, clima, tempestades, relevo, list(proximos) if proximos is not None else None,
                              municipio, list(barragens) if barragens is not None else None, falhas)  # fmt: skip


def test_local_calmo_tem_tudo_baixo_e_sem_agravamento():
    r = _risco()
    assert {p.id: p.nivel for p in r.perigos} == dict.fromkeys(territorio.NOMES, "BAIXO")
    assert r.agravamento == "BAIXO" and r.fator_agravamento == 1.0 and not r.analise_de_aceitacao


def test_vento_e_granizo_frequentes_sao_altos_e_agravam():
    r = _risco(clima=VENTOSO, tempestades=COM_GRANIZO)
    assert r.nivel("VENDAVAL") == r.nivel("GRANIZO") == r.nivel("RAIOS") == "ALTO"
    assert r.agravamento == "ALTO" and 1 < r.fator_agravamento <= territorio.FATOR_MAXIMO
    assert "2,3 dia(s) por ano" in next(p for p in r.perigos if p.id == "VENDAVAL").indicador


def test_setor_do_sgb_perto_e_alto_nao_coberto_e_pede_analise():
    r = _risco(proximos=[_setor("Deslizamento", "Muito alto", 120)])
    deslizamento = next(p for p in r.perigos if p.id == "DESLIZAMENTO")
    assert deslizamento.nivel == "ALTO" and not deslizamento.coberto and deslizamento.clausulas == ["CG-8.1.o"]
    assert r.analise_de_aceitacao and r.agravamento == "BAIXO"  # não coberto não vira agravamento de preço


def test_setor_de_inundacao_mais_longe_e_medio():
    r = _risco(proximos=[_setor("Inundação", "Alto", 900)])
    assert r.nivel("ALAGAMENTO") == "MEDIO" and not r.analise_de_aceitacao


def test_baixada_com_chuva_forte_e_alagamento_medio():
    r = _risco(clima=VENTOSO, relevo={"altitude_m": 10, "declividade_pct": 2, "abaixo_do_entorno_m": 40})
    alagamento = next(p for p in r.perigos if p.id == "ALAGAMENTO")
    assert alagamento.nivel == "MEDIO" and "40 m abaixo" in alagamento.indicador


def test_barragem_de_rejeito_e_alta():
    r = _risco(barragens=[{"nome": "B1", "distancia_m": 6200, "rejeito": True}])
    assert r.nivel("BARRAGEM") == "ALTO" and r.analise_de_aceitacao


def test_fonte_fora_do_ar_e_sem_dado_nunca_baixo():
    r = _risco(clima=None, tempestades=None, barragens=None, falhas=["clima: HTTPError"])
    assert r.nivel("VENDAVAL") == r.nivel("GRANIZO") == r.nivel("BARRAGEM") == "SEM_DADO"
    assert r.falhas == ["clima: HTTPError"]


def test_sem_endereco_exato_perigo_local_fica_no_municipio():
    r = _risco(local=MUNICIPIO, proximos=None, relevo=None, barragens=None, municipio={"mapeado": True, "massa_alto": 44, "agua_alto": 3})
    assert r.nivel("DESLIZAMENTO") == "MEDIO" and r.nivel("ALAGAMENTO") == "BAIXO"
    assert r.nivel("BARRAGEM") == "SEM_DADO" and not r.analise_de_aceitacao  # no máximo MEDIO sem o endereço
    sem_mapa = _risco(local=MUNICIPIO, proximos=None, relevo=None, barragens=None, municipio={"mapeado": False, "massa_alto": 0, "agua_alto": 0})
    assert sem_mapa.nivel("DESLIZAMENTO") == "SEM_DADO"  # cidade sem setorização não é risco baixo


def test_clausulas_dos_perigos_existem_na_base():
    ids = rag.por_id()
    assert all(c in ids for _, _, clausulas in territorio.COBERTURA.values() for c in clausulas)


def test_normalizar_cep():
    assert territorio.normalizar_cep("meu cep é 01310-100") == "01310100"
    assert territorio.normalizar_cep("CNPJ 12.345.678/0001-90") is None


@pytest.mark.parametrize(("clima", "tempestades", "nivel"), [(VENTOSO, COM_GRANIZO, "ESSENCIAL"), (CALMO, SEM_TEMPESTADE, "OPCIONAL")])
def test_risco_muda_a_necessidade_de_vendaval(clima, tempestades, nivel):
    _, est, _ = cliente_virtual("NOVO_t", "MERCADO", {}, _risco(clima=clima, tempestades=tempestades))
    assert necessidades(est)["VENDAVAL_EVENTOS_CORRELATOS"][0] == nivel


def test_vendaval_essencial_leva_ao_pacote_com_vendaval():
    _, _, sem = cliente_virtual("NOVO_t", "ESCRITORIO", {})
    _, _, com = cliente_virtual("NOVO_t", "ESCRITORIO", {}, _risco(clima=VENTOSO, tempestades=COM_GRANIZO))
    assert "VENDAVAL_EVENTOS_CORRELATOS" in rag.coberturas_do_plano(com.plano_base)
    assert com.risco_local is not None and sem.risco_local is None
    vendaval = next(c for c in com.coberturas if c.cobertura == "VENDAVAL_EVENTOS_CORRELATOS")
    assert vendaval.necessidade == "ESSENCIAL" and not any(ch.isdigit() for ch in vendaval.motivo_necessidade)


def test_risco_nao_coberto_alto_deixa_elegibilidade_a_confirmar():
    _, _, plano = cliente_virtual("NOVO_t", "MERCADO", {}, _risco(proximos=[_setor("Deslizamento", "Alto", 0)]))
    assert plano.elegivel == "A_CONFIRMAR" and "CG-13.3" in plano.motivo_elegibilidade


def test_redator_recebe_perigos_relevantes_sem_fator():
    _, _, plano = cliente_virtual("NOVO_t", "MERCADO", {}, _risco(clima=VENTOSO, tempestades=COM_GRANIZO))
    risco = resumo_personalizado(plano)["risco_do_local"]
    assert {p["nivel"] for p in risco["perigos"]} <= {"ALTO", "MEDIO"} and risco["perigos"]
    assert "fator" not in str(risco)  # o fator de agravamento nunca chega ao texto do cliente


def test_conversa_do_zero_pergunta_o_cep_e_usa_o_risco(tmp_path, monkeypatch):
    chamados = []

    def analisar_cep(cep, avisar=None, usar_rede=True):
        chamados.append(cep)
        return _risco(clima=VENTOSO, tempestades=COM_GRANIZO)

    monkeypatch.setattr(territorio, "analisar_cep", analisar_cep)
    redator = RedatorEspiao()
    conversa = ConversaDescoberta(decisor=DecisorFixo(), redigir_fn=redator, arquivo_log=tmp_path / "t.jsonl")
    conversa.turno("Prefiro não informar o CNPJ")
    estado = conversa.turno("Mercado")
    assert estado.opcoes == [SEM_CEP] and "CEP" in estado.resposta
    estado = conversa.turno("é 01310-100")
    assert chamados == ["01310100"] and "risco alto" in estado.resposta
    assert {"rotulo": "Local", "valor": "Bela Vista, São Paulo/SP", "origem": "cliente"} in estado.descoberta["sabe"]
    assert estado.plano_personalizado.risco_local is not None
    while conversa.etapa != "recomendada":
        estado = conversa.turno(estado.opcoes[0])
    entrada = redator.entradas[-1]
    assert entrada["plano_personalizado"]["risco_do_local"]["perigos"]
    citaveis = {c["id"] for c in entrada["clausulas"]}
    assert "VENDAVAL_EVENTOS_CORRELATOS-1.1" in citaveis  # a cláusula do perigo pode ser citada
    assert entrada["respostas_do_cliente"]["CEP"] == "Bela Vista, São Paulo/SP"


def test_conversa_do_zero_sem_cep_segue_normalmente(tmp_path, monkeypatch):
    monkeypatch.setattr(territorio, "analisar_cep", lambda *a, **k: pytest.fail("não deveria consultar"))
    conversa = ConversaDescoberta(decisor=DecisorFixo(), redigir_fn=RedatorEspiao(), arquivo_log=tmp_path / "t.jsonl")
    conversa.turno("Prefiro não informar o CNPJ")
    conversa.turno("Farmácia")
    estado = conversa.turno(SEM_CEP)
    assert conversa.etapa == "pergunta" and conversa.risco is None and estado.opcoes != [SEM_CEP]


def test_cep_nao_localizado_pergunta_de_novo(tmp_path, monkeypatch):
    def falha(*a, **k):
        raise LookupError("CEP não encontrado")

    monkeypatch.setattr(territorio, "analisar_cep", falha)
    conversa = ConversaDescoberta(decisor=DecisorFixo(), redigir_fn=RedatorEspiao(), arquivo_log=tmp_path / "t.jsonl")
    conversa.turno("Prefiro não informar o CNPJ")
    conversa.turno("Farmácia")
    estado = conversa.turno("00000-000")
    assert conversa.etapa == "cep" and estado.opcoes == [SEM_CEP] and "conferir" in estado.resposta
