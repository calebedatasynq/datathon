"""Configuração lida do .env. Nenhuma chave fica no código."""

import os
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")


def chave_anthropic() -> str:
    # CLAUDE_KEY é aceito como alias porque é o nome usado no .env da equipe.
    chave = os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_KEY")
    if not chave:
        raise RuntimeError("Defina ANTHROPIC_API_KEY (ou CLAUDE_KEY) no .env")
    return chave


def chave_jev() -> str | None:
    return os.getenv("JEV_API_KEY") or None


MODELO_LLM = os.getenv("MODELO_LLM", "claude-haiku-5-5")
MODELO_DECISOR = os.getenv("MODELO_DECISOR", "claude-haiku-5-5")
LIMIAR_CONFIANCA = float(os.getenv("LIMIAR_CONFIANCA", "0.70"))


def cliente_anthropic():
    import anthropic

    return anthropic.Anthropic(api_key=chave_anthropic())
