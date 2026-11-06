# Tokenização - contagem e divisão de texto em janelas de tokens
from functools import lru_cache

from transformers import AutoTokenizer

import config


@lru_cache(maxsize=1)
def get_tokenizer():
    tok = AutoTokenizer.from_pretrained(config.EMBEDDING_MODEL)
    tok.model_max_length = 10**6
    return tok


def tokenizar(texto: str) -> list[str]:
    return get_tokenizer().tokenize(texto)


def contar_tokens(texto: str) -> int:
    return len(get_tokenizer().encode(texto, add_special_tokens=False))


def dividir_em_chunks(
    texto: str,
    max_tokens: int = config.CHUNK_TOKENS,
    overlap: int = config.CHUNK_OVERLAP,
) -> list[str]:
    if overlap >= max_tokens:
        raise ValueError("overlap deve ser menor que max_tokens")

    tok = get_tokenizer()
    ids = tok.encode(texto, add_special_tokens=False)

    if len(ids) <= max_tokens:
        texto = texto.strip()
        return [texto] if texto else []

    chunks = []
    passo = max_tokens - overlap
    for inicio in range(0, len(ids), passo):
        janela = ids[inicio:inicio + max_tokens]
        chunk = tok.decode(janela, skip_special_tokens=True).strip()
        if chunk:
            chunks.append(chunk)
        if inicio + max_tokens >= len(ids):
            break
    return chunks