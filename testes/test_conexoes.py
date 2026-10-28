"""Fase 0: o redator (Haiku) e o plano B do Decisor respondem de verdade."""

import pytest

from agente import config


@pytest.fixture(scope="module")
def cliente():
    return config.cliente_anthropic()


def test_redator_responde(cliente):
    resposta = cliente.messages.create(
        model=config.MODELO_LLM,
        max_tokens=200,
        messages=[{"role": "user", "content": "Quanto é 17*23? Responda só o número."}],
    )
    texto = "".join(b.text for b in resposta.content if b.type == "text")
    assert "391" in texto


def test_decisor_plano_b_tool_use_enum(cliente):
    # Mesma forma que o ClaudeDecisor vai usar: tool forçada com enum + probabilidade.
    ferramenta = {
        "name": "registrar_confirmacao",
        "description": "Registra se o estoque mais portáteis passa de R$ 40 mil.",
        "input_schema": {
            "type": "object",
            "properties": {
                "valor": {"type": "string", "enum": ["sim", "nao", "nao_sei"]},
                "probabilidade": {"type": "number", "minimum": 0, "maximum": 1},
            },
            "required": ["valor", "probabilidade"],
        },
    }
    resposta = cliente.messages.create(
        model=config.MODELO_DECISOR,
        max_tokens=300,
        tools=[ferramenta],
        tool_choice={"type": "tool", "name": "registrar_confirmacao"},
        messages=[{"role": "user", "content": "Cliente: tenho uns 50 mil em mercadoria na loja."}],
    )
    chamada = next(b for b in resposta.content if b.type == "tool_use")
    assert chamada.input["valor"] == "sim"
    assert 0 <= chamada.input["probabilidade"] <= 1


def _perguntar_jev(state: str, questions: dict) -> dict:
    import requests

    resposta = requests.post(
        "https://api.typesafe.ai/v1/systemone",
        headers={"Authorization": f"Bearer {config.chave_jev()}"},
        json={"model": "jev-latest", "state": state, "questions": questions},
        timeout=30,
    )
    resposta.raise_for_status()
    return resposta.json()["answers"]


ESTOQUE_40K = {
    "type": "noul",
    "instructions": "O estoque mais os portáteis do cliente passa de R$ 40 mil?",
}


@pytest.mark.skipif(not config.chave_jev(), reason="JEV_API_KEY ausente")
def test_jev_responde():
    respostas = _perguntar_jev(
        "Cliente: tenho uns 50 mil em mercadoria na loja, fora os notebooks.",
        {
            "estoque_acima_40k": ESTOQUE_40K,
            "intencao": {
                "type": "choice",
                "instructions": "Qual a intenção da mensagem?",
                "criteria": {
                    "informar_dado": "o cliente responde uma pergunta com um dado",
                    "perguntar_cobertura": "o cliente pergunta o que o seguro cobre",
                    "objecao": "o cliente resiste a comprar",
                    "outro": None,
                },
            },
        },
    )
    assert respostas["estoque_acima_40k"]["noul"] > 0.7
    assert respostas["intencao"]["choice"] == "informar_dado"


@pytest.mark.skipif(not config.chave_jev(), reason="JEV_API_KEY ausente")
def test_jev_resposta_vaga_fica_abaixo_do_limiar():
    respostas = _perguntar_jev(
        "Cliente: sei lá, nunca contei direito o que tenho na loja.",
        {"estoque_acima_40k": ESTOQUE_40K},
    )
    p = respostas["estoque_acima_40k"]["noul"]
    # Vaga nos dois sentidos: nem sim nem não com confiança.
    assert config.LIMIAR_CONFIANCA > p > 1 - config.LIMIAR_CONFIANCA
