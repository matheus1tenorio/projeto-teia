# Extração de texto do PDF e geração de chunks com metadados de página
import re
from dataclasses import dataclass
from pathlib import Path

import pymupdf as fitz  # PyMuPDF

from core.tokenizacao import contar_tokens, dividir_em_chunks


@dataclass
class Chunk:
    texto: str
    pagina: int
    indice: int
    n_tokens: int


def _limpar(texto: str) -> str:
    texto = texto.replace("\x00", "")
    texto = re.sub(r"-\n(\w)", r"\1", texto)
    texto = re.sub(r"[ \t]+", " ", texto)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()


def extrair_paginas(caminho_pdf: str | Path) -> list[tuple[int, str]]:
    paginas = []
    with fitz.open(caminho_pdf) as doc:
        for i, pagina in enumerate(doc, start=1):
            texto = _limpar(pagina.get_text())
            if texto:
                paginas.append((i, texto))
    return paginas


def processar_pdf(caminho_pdf: str | Path) -> list[Chunk]:
    paginas = extrair_paginas(caminho_pdf)
    if not paginas:
        raise ValueError(
        )

    chunks: list[Chunk] = []
    for numero, texto in paginas:
        for trecho in dividir_em_chunks(texto):
            chunks.append(Chunk(
                texto=trecho,
                pagina=numero,
                indice=len(chunks),
                n_tokens=contar_tokens(trecho),
            ))
    return chunks