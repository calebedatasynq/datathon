"""conhecimento/clausulas.jsonl → coleção Chroma em conhecimento/banco_vetorial.

Chroma com distância cosseno, como no RAG do BB Radar; modelo em config.MODELO_EMBEDDINGS.
A coleção guarda o hash do clausulas.jsonl e o modelo; se mudarem, rag.py ignora o índice
até reindexar.
Uso: python scripts/indexar_rag.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import chromadb  # noqa: E402

from agente import config, rag  # noqa: E402


def main():
    cs = rag.clausulas()
    print(f"Gerando embeddings de {len(cs)} cláusulas com {config.MODELO_EMBEDDINGS}...")
    vetores = rag.embeddings([rag.texto_indexado(c) for c in cs], "passage")
    cliente = chromadb.PersistentClient(path=str(config.DIR_BANCO_VETORIAL))
    try:
        cliente.delete_collection(config.COLECAO_VETORIAL)
    except Exception:
        pass
    colecao = cliente.create_collection(
        config.COLECAO_VETORIAL,
        metadata={
            "hnsw:space": "cosine",
            "hash_clausulas": rag.hash_clausulas(),
            "modelo": config.MODELO_EMBEDDINGS,
        },
    )
    colecao.add(
        ids=[c.id for c in cs],
        documents=[c.texto for c in cs],
        embeddings=vetores,
        metadatas=[{"cobertura": c.cobertura or "", "tipo": c.tipo.value, "parte": c.parte} for c in cs],
    )
    print(f"Indexadas: {colecao.count()} em {config.DIR_BANCO_VETORIAL.relative_to(config.RAIZ)}")


if __name__ == "__main__":
    main()
