# Pipeline RAG - indexação no ChromaDB, recuperação e geração com o LLM da NVIDIA
import hashlib
from functools import lru_cache
from pathlib import Path

import chromadb
from openai import OpenAI

import config
from core.embeddings import embed_documentos, embed_pergunta
from core.processador_pdf import processar_pdf


# Armazenamento (ChromaDB)

@lru_cache(maxsize=1)
def _get_client():
    config.CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(config.CHROMA_DIR))


def _id_edital(caminho_pdf: str | Path) -> str:
    h = hashlib.sha256(Path(caminho_pdf).read_bytes()).hexdigest()
    return f"edital_{h[:16]}"


def indexar_edital(caminho_pdf: str | Path) -> str:
    nome = _id_edital(caminho_pdf)
    client = _get_client()

    if nome in [c.name for c in client.list_collections()]:
        if client.get_collection(nome).count() > 0:
            return nome  # embeddings já gerados: não recalcula
        client.delete_collection(nome)  # coleção vazia de uma tentativa que falhou

    chunks = processar_pdf(caminho_pdf)
    vetores = embed_documentos([c.texto for c in chunks])

    colecao = client.create_collection(name=nome, metadata={"hnsw:space": "cosine"})
    try:
        colecao.add(
            ids=[str(c.indice) for c in chunks],
            documents=[c.texto for c in chunks],
            embeddings=vetores,
            metadatas=[{"pagina": c.pagina, "n_tokens": c.n_tokens} for c in chunks],
        )
    except Exception:
        client.delete_collection(nome)  # não deixa coleção meio indexada
        raise
    return nome


# Recuperação

def buscar(nome_colecao: str, pergunta: str, k: int = config.TOP_K) -> list[dict]:
    colecao = _get_client().get_collection(nome_colecao)
    k = max(1, min(k, colecao.count()))
    r = colecao.query(
        query_embeddings=[embed_pergunta(pergunta)],
        n_results=k,
    )
    return [
        {"texto": doc, "pagina": meta["pagina"], "distancia": dist}
        for doc, meta, dist in zip(
            r["documents"][0], r["metadatas"][0], r["distances"][0]
        )
    ]


# Geração (LLM via API da NVIDIA) 

@lru_cache(maxsize=1)
def _get_llm() -> OpenAI:
    if not config.NVIDIA_API_KEY:
        raise RuntimeError("NVIDIA_API_KEY não encontrada no .env")
    return OpenAI(
        base_url=config.NVIDIA_BASE_URL,
        api_key=config.NVIDIA_API_KEY,
        timeout=config.LLM_TIMEOUT,
    )


SYSTEM_PROMPT = """Você é um assistente que ajuda candidatos a interpretar editais de bolsas de pós-graduação.

Regras:
1. Responda SOMENTE com base nos trechos do edital fornecidos no contexto.
2. Se a informação não estiver nos trechos, diga claramente que não encontrou no edital. Não invente.
3. Ao final de CADA afirmação, cite a página entre parênteses, exatamente no formato (p. X). Nunca escreva "página X" por extenso.
4. Não estime chances de aprovação ou de concessão de bolsa.
5. Responda em português, de forma clara e objetiva.

Exemplo de resposta correta:
"As inscrições vão de 12/05/2026 a 27/05/2026 (p. 1). A taxa deve ser paga até o último dia (p. 3)."
"""


def montar_contexto(trechos: list[dict]) -> str:
    return "\n\n".join(
        f"[Trecho {i} | página {t['pagina']}]\n{t['texto']}"
        for i, t in enumerate(trechos, start=1)
    )


def gerar_resposta(pergunta: str, trechos: list[dict]) -> str:
    mensagens = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"CONTEXTO (trechos do edital):\n{montar_contexto(trechos)}\n\n"
                f"PERGUNTA: {pergunta}"
            ),
        },
    ]
    kwargs = dict(
        model=config.LLM_MODEL,
        messages=mensagens,
        temperature=config.TEMPERATURA,
        max_tokens=config.MAX_TOKENS_RESPOSTA,
    )
    if config.DESATIVAR_RACIOCINIO:
        kwargs["extra_body"] = {"chat_template_kwargs": {"enable_thinking": False}}

    resp = _get_llm().chat.completions.create(**kwargs)
    texto = (resp.choices[0].message.content or "").strip()
    return texto or "Não consegui gerar uma resposta. Tente reformular a pergunta."


def perguntar(nome_colecao: str, pergunta: str) -> dict:
    trechos = buscar(nome_colecao, pergunta)
    resposta = gerar_resposta(pergunta, trechos)
    paginas = sorted({t["pagina"] for t in trechos})
    return {"resposta": resposta, "trechos": trechos, "paginas": paginas}