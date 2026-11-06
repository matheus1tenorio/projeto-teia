# Geração local de embeddings com multilingual-e5-small.
from functools import lru_cache

from sentence_transformers import SentenceTransformer

import config

@lru_cache(maxsize=1)
def get_modelo() -> SentenceTransformer:
    return SentenceTransformer(config.EMBEDDING_MODEL)


def embed_documentos(textos: list[str]) -> list[list[float]]:
    if not textos:
        return []
    entradas = [config.PREFIXO_DOCUMENTO + t for t in textos]
    vetores = get_modelo().encode(
        entradas,
        normalize_embeddings=True,
        batch_size=16,
        show_progress_bar=False,
    )
    return vetores.tolist()


def embed_pergunta(pergunta: str) -> list[float]:
    vetor = get_modelo().encode(
        config.PREFIXO_PERGUNTA + pergunta,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return vetor.tolist()