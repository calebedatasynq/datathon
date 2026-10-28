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

# Pacote do motor de score entregue pela equipe; só score_empresa é usado.
DIR_MOTOR = RAIZ / "Entrega_Indice_Seguro_RAG_v2" / "seguro_score_rag"
BASE_CLIENTES = DIR_MOTOR / "dados" / "preparados" / "base_teste_comum.csv"
# Pergunta-se uma variável quando o corte de plano está a até esta fração do valor estimado.
MARGEM_PERGUNTA = float(os.getenv("MARGEM_PERGUNTA", "0.30"))

# Base de conhecimento (RAG)
CLAUSULAS = RAIZ / "conhecimento" / "clausulas.jsonl"
CATALOGO = RAIZ / "Seguro_Empresarial_Teste_Comum" / "catalogo_coberturas_fixas_planos.csv"
DIR_BANCO_VETORIAL = RAIZ / "conhecimento" / "banco_vetorial"
COLECAO_VETORIAL = "clausulas_cg"
# O RAG do BB Radar usava paraphrase-multilingual-MiniLM-L12-v2; em 30 perguntas de teste o
# híbrido com ele acertou 25/30 (pior que BM25, 28/30) e com o e5-small, 29/30.
MODELO_EMBEDDINGS = "intfloat/multilingual-e5-small"
# "hibrido" (BM25 + vetorial) ou "bm25"; sem o índice vetorial, cai para BM25.
MODO_BUSCA = os.getenv("MODO_BUSCA", "hibrido")


def cliente_anthropic():
    import anthropic

    return anthropic.Anthropic(api_key=chave_anthropic())
