"""API da interface: a conversa do zero começa sem nenhum dado do cliente (sem chamar API externa)."""

import json

import pytest
from fastapi.testclient import TestClient

from interface.servidor import app


@pytest.fixture(scope="module")
def cliente():
    with TestClient(app) as c:
        yield c


def _eventos(resposta) -> list[tuple[str, dict]]:
    eventos = []
    for bloco in resposta.text.split("\n\n"):
        linhas = dict(l.split(": ", 1) for l in bloco.splitlines() if ": " in l)
        if "event" in linhas:
            eventos.append((linhas["event"], json.loads(linhas["data"])))
    return eventos


def test_saude_anuncia_a_conversa_do_zero(cliente):
    # A página usa isto para não cair na conversa anterior quando o servidor é antigo.
    assert "descoberta" in cliente.get("/api/saude").json()["recursos"]


def test_conversa_do_zero_nao_sabe_nada_do_cliente(cliente):
    # Uma conversa com cadastro aberta antes não pode vazar para a conversa do zero.
    cliente.post("/api/conversas", json={"cliente_id": "IMO_CASO_00043_01"})
    dados = cliente.post("/api/descobertas").json()
    assert dados["cliente"]["modo"] == "descoberta" and dados["cliente"]["cliente_id"] is None
    assert dados["cliente"]["fatos"] == [] and dados["cliente"]["personalizado"] is None
    assert dados["descoberta"]["sabe"] == [] and dados["descoberta"]["feitas"] == 0
    assert "CNPJ" in dados["abertura"]["texto"]


def test_primeiras_respostas_da_conversa_do_zero(cliente):
    sessao = cliente.post("/api/descobertas").json()["sessao_id"]
    turno = dict(_eventos(cliente.post(f"/api/conversas/{sessao}/mensagens", json={"texto": "Prefiro não informar o CNPJ"})))["turno"]
    assert "Farmácia" in turno["opcoes"] and turno["descoberta"]["sabe"] == []
    assert turno["personalizado"] is None  # sem o ramo, nenhum plano (seria só média geral)
    turno = dict(_eventos(cliente.post(f"/api/conversas/{sessao}/mensagens", json={"texto": "Farmácia"})))["turno"]
    assert turno["descoberta"]["sabe"] == [{"rotulo": "Ramo", "valor": "Farmácia", "origem": "cliente"}]
    assert turno["opcoes"]  # a próxima pergunta, com as faixas
    assert turno["personalizado"]["plano_base"]  # plano em formação


def test_sessao_inexistente(cliente):
    assert cliente.post("/api/conversas/nao-existe/mensagens", json={"texto": "oi"}).status_code == 404
