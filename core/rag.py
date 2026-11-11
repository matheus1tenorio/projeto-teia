# Pipeline RAG - indexação no ChromaDB, recuperação (1 ou vários editais) e geração com o LLM da NVIDIA
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

    existentes = [getattr(c, "name", c) for c in client.list_collections()]
    if nome in existentes:
        if client.get_collection(nome).count() > 0:
            return nome  
        client.delete_collection(nome)  

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
        client.delete_collection(nome)  
        raise
    return nome


def _pdfs_da_pasta() -> list[Path]:
    config.EDITAIS_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(p for p in config.EDITAIS_DIR.iterdir() if p.suffix.lower() == ".pdf")


def indexar_pasta() -> tuple[dict[str, str], dict[str, str]]:
    """Indexa todos os PDFs de editais/ (os já indexados são reaproveitados).
    Retorna ({nome_do_arquivo: id_da_colecao}, {nome_do_arquivo: erro})."""
    editais, erros = {}, {}
    for pdf in _pdfs_da_pasta():
        try:
            editais[pdf.name] = indexar_edital(pdf)
        except Exception as e:
            erros[pdf.name] = str(e)
    return editais, erros


#  Recuperação 

def _consultar(nome_colecao: str, vetor: list[float], k: int) -> list[dict]:
    colecao = _get_client().get_collection(nome_colecao)
    k = max(1, min(k, colecao.count()))
    r = colecao.query(query_embeddings=[vetor], n_results=k)
    return [
        {"texto": doc, "pagina": meta["pagina"], "distancia": dist}
        for doc, meta, dist in zip(
            r["documents"][0], r["metadatas"][0], r["distances"][0]
        )
    ]


def buscar(nome_colecao: str, pergunta: str, k: int = config.TOP_K) -> list[dict]:
    """Busca semântica em UM edital."""
    return _consultar(nome_colecao, embed_pergunta(pergunta), k)


def buscar_multi(editais: dict[str, str], pergunta: str, k: int = config.TOP_K_MULTI) -> list[dict]:
    """Busca semântica em VÁRIOS editais: consulta cada coleção e fica com os k
    trechos mais próximos no conjunto (o embedding da pergunta é calculado uma vez)."""
    vetor = embed_pergunta(pergunta)
    trechos = []
    for nome_arquivo, colecao in editais.items():
        for t in _consultar(colecao, vetor, k):
            t["edital"] = Path(nome_arquivo).stem
            trechos.append(t)
    trechos.sort(key=lambda t: t["distancia"])
    return trechos[:k]


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

SYSTEM_PROMPT_MULTI = """Você é um assistente que ajuda candidatos a interpretar editais de bolsas de pós-graduação.
Os trechos fornecidos podem vir de VÁRIOS editais diferentes; cada trecho informa o edital de origem.

Regras:
1. Responda SOMENTE com base nos trechos fornecidos.
2. Diga sempre de qual edital vem cada informação. Não misture informações de editais diferentes; se os editais divergem, compare-os explicitamente.
3. Se a informação não estiver nos trechos, diga que não encontrou. Não invente. Se a pergunta for sobre todos os editais mas os trechos cobrem só alguns, avise que a resposta pode estar incompleta.
4. Cite a fonte de CADA afirmação no formato (nome_do_edital, p. X).
5. Não estime chances de aprovação ou de concessão de bolsa.
6. Responda em português, de forma clara e objetiva.

Exemplo de resposta correta:
"O edital_1 exige inglês (edital_1, p. 3), enquanto o edital_2 não menciona proficiência (edital_2, p. 2)."
"""


def montar_contexto(trechos: list[dict]) -> str:
    partes = []
    for i, t in enumerate(trechos, start=1):
        origem = f"edital {t['edital']} | " if t.get("edital") else ""
        partes.append(f"[Trecho {i} | {origem}página {t['pagina']}]\n{t['texto']}")
    return "\n\n".join(partes)


def gerar_resposta(pergunta: str, trechos: list[dict], multi: bool = False) -> str:
    mensagens = [
        {"role": "system", "content": SYSTEM_PROMPT_MULTI if multi else SYSTEM_PROMPT},
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
    # Chat com UM edital
    trechos = buscar(nome_colecao, pergunta)
    resposta = gerar_resposta(pergunta, trechos)
    paginas = sorted({t["pagina"] for t in trechos})
    return {
        "resposta": resposta,
        "trechos": trechos,
        "paginas": paginas,
        "fontes": [f"p. {p}" for p in paginas],
    }


def perguntar_multi(editais: dict[str, str], pergunta: str) -> dict:
    # chat com TODOS os editais indexados
    trechos = buscar_multi(editais, pergunta)
    resposta = gerar_resposta(pergunta, trechos, multi=True)
    fontes = sorted({(t["edital"], t["pagina"]) for t in trechos})
    return {
        "resposta": resposta,
        "trechos": trechos,
        "paginas": sorted({p for _, p in fontes}),
        "fontes": [f"{e}, p. {p}" for e, p in fontes],
    }