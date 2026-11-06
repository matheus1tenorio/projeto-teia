import sys
import time
import traceback

PDF = sys.argv[1] if len(sys.argv) > 1 else "editais/edital_1.pdf"
estado = {}


def etapa(nome):
    def deco(fn):
        t = time.time()
        try:
            fn()
            print(f"[OK]    {nome} ({time.time() - t:.1f}s)")
        except Exception:
            print(f"[FALHA] {nome}")
            traceback.print_exc()
            sys.exit(1)
    return deco


@etapa("1. Config e chave da API")
def _():
    import config
    assert config.NVIDIA_API_KEY, "NVIDIA_API_KEY vazia: confira o .env"
    print("        modelo:", config.LLM_MODEL)


@etapa("2. Tokenização")
def _():
    from core.tokenizacao import contar_tokens, tokenizar
    tokens = tokenizar("Inscrições abertas para o mestrado")
    assert len(tokens) > 0
    print("        tokens:", tokens)
    assert contar_tokens("Inscrições abertas") > 0


@etapa("3. Extração do PDF e chunks")
def _():
    import config
    from core.processador_pdf import processar_pdf
    chunks = processar_pdf(PDF)
    assert chunks, "Nenhum chunk gerado"
    maior = max(c.n_tokens for c in chunks)
    assert maior <= config.CHUNK_TOKENS + 10, f"Chunk com {maior} tokens (limite {config.CHUNK_TOKENS})"
    estado["chunks"] = chunks
    print(f"        {len(chunks)} chunks | maior: {maior} tokens | páginas: {chunks[-1].pagina}")


@etapa("4. Embeddings")
def _():
    from core.embeddings import embed_documentos, embed_pergunta
    v = embed_documentos(["O prazo de inscrição termina em março."])[0]
    q = embed_pergunta("Qual o prazo de inscrição?")
    sim = sum(a * b for a, b in zip(v, q))  # vetores normalizados = cosseno
    print(f"        dimensão: {len(v)} | similaridade pergunta x trecho: {sim:.2f}")
    assert len(v) == 384 and sim > 0.7, "Similaridade baixa: confira os prefixos passage:/query:"


@etapa("5. Indexação no ChromaDB (e reuso)")
def _():
    from core.rag import indexar_edital
    t = time.time()
    estado["col"] = indexar_edital(PDF)
    primeira = time.time() - t
    t = time.time()
    indexar_edital(PDF)
    segunda = time.time() - t
    print(f"        1ª vez: {primeira:.1f}s | 2ª vez (reuso): {segunda:.2f}s")
    assert segunda < primeira or segunda < 1, "Não está reaproveitando os embeddings"


@etapa("6. Busca semântica")
def _():
    from core.rag import buscar
    r = buscar(estado["col"], "Qual o prazo de inscrição?")
    assert r
    for t in r[:3]:
        print(f"        p.{t['pagina']} dist={t['distancia']:.3f} | {t['texto'][:70]!r}")


@etapa("7. Chat (LLM responde citando páginas)")
def _():
    from core.rag import perguntar
    r = perguntar(estado["col"], "Quais os prazos de inscrição?")
    print("        resposta:", r["resposta"][:300].replace("\n", " "))
    assert r["resposta"].strip()

    resp = r["resposta"].lower()
    assert "(p." in resp or "página" in resp or "pagina" in resp, \
        "Resposta sem citação de página: revise o prompt"
    if "(p." not in resp:
        print("        [AVISO] citou a página, mas fora do formato (p. X)")


@etapa("8. Resumo (JSON)")
def _():
    from services.analisador_edital import resumir_edital
    r = resumir_edital(estado["col"], "Mestrado")
    chaves = {"instituicao", "programa", "requisitos", "prazos"}
    assert chaves <= r.keys(), f"Faltam chaves: {chaves - r.keys()}"
    print("        instituição:", r["instituicao"])


@etapa("9. Compatibilidade (JSON)")
def _():
    from services.analisador_edital import analisar_compatibilidade
    perfil = {"nivel": "Mestrado", "graduacao": "Sistemas para Internet (concluída)"}
    r = analisar_compatibilidade(estado["col"], perfil)
    assert r["itens"], "Nenhum item retornado"
    for i in r["itens"][:5]:
        print(f"        [{i['status']}] {i['requisito'][:60]}")

print("\nTudo passou.")