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
