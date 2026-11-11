"""
BolsaCheck — interface web (Streamlit).

Rodar localmente:   streamlit run app.py
Rodar na EC2:       streamlit run app.py --server.address 0.0.0.0 --server.port 8501 --server.headless true
"""

import hmac
import os
import re
from pathlib import Path

import streamlit as st

import config
from core.rag import indexar_edital, indexar_pasta, perguntar, perguntar_multi
from services.analisador_edital import analisar_compatibilidade, resumir_edital

st.set_page_config(page_title="BolsaCheck", page_icon="🎓", layout="wide")

NAO_INFORMADO = "Não informado no edital"
STATUS_INFO = {
    "atende": ("✅ Atende", st.success),
    "nao_atende": ("❌ Não atende", st.error),
    "confirmar": ("⚠️ Precisa de confirmação", st.warning),
    "nao_se_aplica": ("➖ Não se aplica ao seu perfil", st.info),
}
DOCUMENTOS_OPCOES = [
    "Diploma ou comprovante de conclusão da graduação",
    "Histórico escolar completo",
    "RG e CPF",
    "Certidão de quitação eleitoral",
    "Currículo Lattes atualizado",
    "Comprovante de proficiência em língua estrangeira",
    "Pré-projeto de pesquisa",
    "Comprovante de pagamento da taxa ou de isenção",
]


# Acesso

def _checar_senha() -> bool:
    senha = os.getenv("APP_PASSWORD")
    if not senha:
        return True
    if st.session_state.get("autenticado"):
        return True
    st.title("🎓 BolsaCheck")
    digitada = st.text_input("Senha de acesso", type="password")
    if digitada:
        if hmac.compare_digest(digitada, senha):
            st.session_state["autenticado"] = True
            st.rerun()
        else:
            st.error("Senha incorreta.")
    return False


# Helpers de exibição

def _como_lista(valor) -> list:
    if not valor:
        return []
    return valor if isinstance(valor, list) else [valor]


def _mostrar_lista(titulo: str, itens) -> None:
    itens = _como_lista(itens)
    st.markdown(f"**{titulo}**")
    if not itens:
        st.caption(NAO_INFORMADO)
        return
    for item in itens:
        st.markdown(f"- {item}")


def _mostrar_resumo(r: dict) -> None:
    c1, c2 = st.columns(2)
    c1.markdown(f"**Instituição**\n\n{r.get('instituicao') or NAO_INFORMADO}")
    c2.markdown(f"**Programa**\n\n{r.get('programa') or NAO_INFORMADO}")
    st.markdown(f"**Modalidades e bolsas**\n\n{r.get('modalidades_bolsas') or NAO_INFORMADO}")

    col_a, col_b = st.columns(2)
    with col_a:
        _mostrar_lista("Requisitos", r.get("requisitos"))
        _mostrar_lista("Documentação necessária", r.get("documentos"))
    with col_b:
        st.markdown("**Prazos**")
        prazos = _como_lista(r.get("prazos"))
        if not prazos:
            st.caption(NAO_INFORMADO)
        for p in prazos:
            if isinstance(p, dict):
                st.markdown(f"- **{p.get('evento', '')}:** {p.get('data', '')}")
            else:
                st.markdown(f"- {p}")
        _mostrar_lista("Critérios de seleção", r.get("criterios_selecao"))
    _mostrar_lista("Outras informações", r.get("outras_informacoes"))


def _mostrar_item(i: dict, caixa) -> None:
    paginas = ", ".join(str(p) for p in _como_lista(i.get("paginas")))
    fonte = f" _(p. {paginas})_" if paginas else ""
    justificativa = re.sub(r"\s*\(p\.[^)]*\)", "", i.get("justificativa", "")).strip()
    caixa(f"**{i.get('requisito', '')}**\n\n{justificativa}{fonte}")


def _contar(itens: list[dict]) -> dict:
    return {k: sum(1 for i in itens if i["status"] == k) for k in STATUS_INFO}


def _mostrar_compatibilidade(r: dict) -> None:
    itens = r.get("itens", [])
    if not itens:
        st.warning("A análise não retornou itens. Tente novamente.")
        return

    contagem = _contar(itens)
    cols = st.columns(4)
    for col, (chave, (rotulo, _)) in zip(cols, STATUS_INFO.items()):
        col.metric(rotulo, contagem[chave])

    for chave, (rotulo, caixa) in STATUS_INFO.items():
        grupo = [i for i in itens if i["status"] == chave]
        if not grupo:
            continue
        if chave == "nao_se_aplica":
            with st.expander(f"{rotulo} ({len(grupo)})"):
                for i in grupo:
                    _mostrar_item(i, caixa)
            continue
        st.markdown(f"#### {rotulo}")
        for i in grupo:
            _mostrar_item(i, caixa)


def _mostrar_comparativo(resultados: dict[str, dict]) -> None:
    linhas = []
    for nome, r in resultados.items():
        if "erro" in r:
            linhas.append({"Edital": Path(nome).stem, "✅ Atende": "erro", "❌ Não atende": "-",
                           "⚠️ Confirmar": "-", "➖ Não se aplica": "-"})
            continue
        c = _contar(r.get("itens", []))
        linhas.append({"Edital": Path(nome).stem, "✅ Atende": c["atende"],
                       "❌ Não atende": c["nao_atende"], "⚠️ Confirmar": c["confirmar"],
                       "➖ Não se aplica": c["nao_se_aplica"]})
    st.dataframe(linhas, use_container_width=True, hide_index=True)

    escolhido = st.selectbox("Ver detalhes de:", list(resultados), format_func=lambda n: Path(n).stem,
                             key="detalhe_comparativo")
    r = resultados[escolhido]
    if "erro" in r:
        st.error(f"Falha na análise deste edital: {r['erro']}")
    else:
        _mostrar_compatibilidade(r)


# Estado e indexação

def _carregar_editais(forcar: bool = False) -> dict[str, str]:
    if forcar or "editais" not in st.session_state:
        with st.spinner("Preparando a base de editais (a primeira vez pode demorar)..."):
            editais, erros = indexar_pasta()
        st.session_state["editais"] = editais
        st.session_state["erros_indexacao"] = erros
    return st.session_state["editais"]


def _indexar_upload(arquivo) -> None:
    chave = (arquivo.name, arquivo.size)
    if st.session_state.get("arquivo_chave") == chave:
        return
    st.session_state["arquivo_chave"] = chave
    st.session_state["erro_upload"] = None

    config.EDITAIS_DIR.mkdir(parents=True, exist_ok=True)
    destino = config.EDITAIS_DIR / Path(arquivo.name).name
    destino.write_bytes(arquivo.getbuffer())
    with st.spinner("Lendo o edital e gerando embeddings..."):
        try:
            colecao = indexar_edital(destino)
        except Exception as e:
            destino.unlink(missing_ok=True)
            st.session_state["erro_upload"] = f"Não foi possível processar {arquivo.name}: {e}"
            return
    st.session_state["editais"][destino.name] = colecao
    st.session_state["edital_ativo"] = destino.name


def _perfil_do_formulario(**campos) -> dict:
    perfil = {
        "nivel": campos["nivel"],
        "curso_graduacao": campos["curso"] or "não informado",
        "situacao_graduacao": campos["situacao"],
        "instituicao_graduacao": campos["instituicao"] or "não informada",
        "ano_conclusao": campos["ano"] or "não informado",
        "proficiencia_idioma": campos["idioma"] or "não informada",
        "vinculo_empregaticio": campos["vinculo"],
        "acoes_afirmativas": campos["afirmativas"],
        "maior_titulacao": campos["titulacao"],
        "nacionalidade": campos["nacionalidade"],
        "dedicacao_exclusiva": campos["dedicacao"],
        "documentos_que_possui": ", ".join(campos["documentos"]) or "nenhum marcado",
    }
    if campos["extra"].strip():
        perfil["outras_informacoes"] = campos["extra"].strip()
    return perfil


# Interface

def main() -> None:
    if not _checar_senha():
        return

    st.title("🎓 BolsaCheck")
    st.caption(
        "Análise de editais de pós-graduação com IA. A ferramenta ajuda a interpretar o edital "
        "e checar requisitos formais; **não estima chances de aprovação ou de bolsa.** "
        "Confirme sempre as informações no edital oficial."
    )

    if not config.NVIDIA_API_KEY:
        st.error("NVIDIA_API_KEY não encontrada. Configure no arquivo .env.")
        return

    editais = _carregar_editais()

    with st.sidebar:
        st.header("Editais")
        arquivo = st.file_uploader("Adicionar edital (PDF)", type=["pdf"])
        if arquivo:
            _indexar_upload(arquivo)
        if st.session_state.get("erro_upload"):
            st.error(st.session_state["erro_upload"])
        for nome, erro in st.session_state.get("erros_indexacao", {}).items():
            st.warning(f"{nome}: {erro}")

        editais = st.session_state["editais"]
        nomes = list(editais)
        if st.session_state.get("edital_ativo") not in nomes:
            st.session_state.pop("edital_ativo", None)
        if nomes:
            st.selectbox("Edital ativo", nomes, key="edital_ativo", format_func=lambda n: Path(n).stem)
        st.caption(f"{len(nomes)} edital(is) na base")
        if st.button("🔄 Reindexar pasta editais/"):
            _carregar_editais(forcar=True)
            st.rerun()
        st.divider()
        st.caption(f"Modelo: `{config.LLM_MODEL}`")

    if not editais:
        st.info("👈 Adicione um edital em PDF na barra lateral (ou coloque PDFs na pasta editais/) para começar.")
        return

    nome_ativo = st.session_state["edital_ativo"]
    colecao = editais[nome_ativo]

    aba_resumo, aba_compat, aba_chat = st.tabs(
        ["📄 Resumo", "✅ Compatibilidade", "💬 Chat com os editais"]
    )

    # Resumo
    with aba_resumo:
        st.caption(f"Edital: **{Path(nome_ativo).stem}**")
        nivel_resumo = st.radio("Nível", ["Mestrado", "Doutorado"], horizontal=True, key="nivel_resumo")
        chave = ("resumo", colecao, nivel_resumo)
        if st.button("Gerar resumo", type="primary"):
            with st.spinner("Analisando o edital..."):
                try:
                    st.session_state[chave] = resumir_edital(colecao, nivel_resumo)
                except Exception as e:
                    st.error(f"Falha ao gerar o resumo: {e}")
        if chave in st.session_state:
            _mostrar_resumo(st.session_state[chave])

    # Compatibilidade
    with aba_compat:
        st.markdown("Preencha seu perfil para comparar com os requisitos do edital.")
        with st.form("perfil"):
            c1, c2 = st.columns(2)
            nivel = c1.selectbox("Nível pretendido", ["Mestrado", "Doutorado"])
            curso = c2.text_input("Curso de graduação", placeholder="Ex.: Ciência da Computação")
            situacao = c1.selectbox("Situação da graduação", ["Concluída", "Cursando (concluo em breve)", "Não concluída"])
            instituicao = c2.text_input("Instituição de graduação")
            ano = c1.text_input("Ano de conclusão (ou previsão)")
            idioma = c2.text_input("Proficiência em língua estrangeira", placeholder="Ex.: Inglês B2, sem certificado")
            vinculo = c1.selectbox("Vínculo empregatício", ["Sem vínculo", "Com vínculo (CLT)", "Servidor público"])
            afirmativas = c2.selectbox(
                "Concorre a ações afirmativas?",
                ["Não", "Sim (negros, indígenas, quilombolas, PcD, trans)", "Prefiro não informar"],
            )
            titulacao = c1.selectbox("Maior titulação concluída", ["Graduação", "Especialização", "Mestrado", "Doutorado"])
            nacionalidade = c2.selectbox("Nacionalidade", ["Brasileira", "Estrangeira"])
            dedicacao = c1.selectbox("Pode se dedicar com exclusividade à pós-graduação?", ["Sim", "Não", "Não sei"])
            documentos = st.multiselect("Documentos que você já possui", DOCUMENTOS_OPCOES)
            extra = st.text_area("Outras informações relevantes (opcional)", height=70)
            b1, b2 = st.columns(2)
            enviar = b1.form_submit_button(f"Analisar em: {Path(nome_ativo).stem}", type="primary")
            enviar_todos = b2.form_submit_button("Comparar em TODOS os editais", disabled=len(editais) < 2)

        chave_c = ("compat", colecao)
        chave_todos = ("compat_todos", tuple(sorted(editais.values())))
        if enviar or enviar_todos:
            perfil = _perfil_do_formulario(
                nivel=nivel, curso=curso, situacao=situacao, instituicao=instituicao,
                ano=ano, idioma=idioma, vinculo=vinculo, afirmativas=afirmativas,
                titulacao=titulacao, nacionalidade=nacionalidade, dedicacao=dedicacao,
                documentos=documentos, extra=extra,
            )
            if enviar:
                with st.spinner("Comparando seu perfil com o edital..."):
                    try:
                        st.session_state[chave_c] = analisar_compatibilidade(colecao, perfil)
                    except Exception as e:
                        st.error(f"Falha na análise: {e}")
            else:
                resultados, total = {}, len(editais)
                barra = st.progress(0.0)
                for n, (nome, col) in enumerate(editais.items()):
                    barra.progress(n / total, text=f"Analisando {Path(nome).stem} ({n + 1}/{total})...")
                    try:
                        resultados[nome] = analisar_compatibilidade(col, perfil)
                    except Exception as e:
                        resultados[nome] = {"erro": str(e)}
                barra.empty()
                st.session_state[chave_todos] = resultados

        if chave_todos in st.session_state:
            st.markdown("### Comparativo entre editais")
            _mostrar_comparativo(st.session_state[chave_todos])
            st.divider()
        if chave_c in st.session_state:
            st.markdown(f"### Resultado: {Path(nome_ativo).stem}")
            _mostrar_compatibilidade(st.session_state[chave_c])
        if chave_c in st.session_state or chave_todos in st.session_state:
            st.caption("Resultado preliminar: confirme cada requisito no edital oficial.")

    # Chat
    with aba_chat:
        escopo = st.radio(
            "Perguntar em", ["Edital ativo", "Todos os editais"], horizontal=True,
            disabled=len(editais) < 2, key="escopo_chat",
        )
        multi = escopo == "Todos os editais" and len(editais) > 1

        historicos = st.session_state.setdefault("historicos", {})
        historico = historicos.setdefault("__todos__" if multi else colecao, [])

        for msg in historico:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                if msg.get("fontes"):
                    st.caption("Fontes (trechos recuperados): " + " · ".join(msg["fontes"]))
                if msg.get("trechos"):
                    with st.expander("Ver trechos usados"):
                        for t in msg["trechos"]:
                            origem = f"{t['edital']} · " if t.get("edital") else ""
                            st.markdown(f"**{origem}p. {t['pagina']}** · distância {t['distancia']:.3f}")
                            st.text(t["texto"])

        pergunta = st.chat_input("Pergunte algo sobre o(s) edital(is)...")
        if pergunta:
            historico.append({"role": "user", "content": pergunta})
            with st.chat_message("user"):
                st.markdown(pergunta)
            with st.chat_message("assistant"):
                with st.spinner("Buscando nos editais..."):
                    try:
                        r = perguntar_multi(editais, pergunta) if multi else perguntar(colecao, pergunta)
                        historico.append({
                            "role": "assistant",
                            "content": r["resposta"],
                            "fontes": r["fontes"],
                            "trechos": r["trechos"],
                        })
                    except Exception as e:
                        historico.append({"role": "assistant", "content": f"Erro ao responder: {e}"})
            st.rerun()


main()