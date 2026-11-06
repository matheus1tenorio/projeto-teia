"""
BolsaCheck — interface web (Streamlit).

Rodar localmente:   streamlit run app.py
Rodar na EC2:       streamlit run app.py --server.address 0.0.0.0 --server.port 8501 --server.headless true
"""
import hmac
import os
from pathlib import Path

import streamlit as st

import config
from core.rag import indexar_edital, perguntar
from services.analisador_edital import analisar_compatibilidade, resumir_edital

st.set_page_config(page_title="BolsaCheck", page_icon="🎓", layout="wide")

NAO_INFORMADO = "Não informado no edital"
STATUS_INFO = {
    "atende": ("✅ Atende", st.success),
    "nao_atende": ("❌ Não atende", st.error),
    "confirmar": ("⚠️ Precisa de confirmação", st.warning),
    "nao_se_aplica": ("➖ Não se aplica ao seu perfil", st.info),
}


# Acesso (opcional, recomendado na EC2) 

def _checar_senha() -> bool:
    # Se APP_PASSWORD estiver no .env, exige senha antes de usar o app (evita que qualquer pessoa com o IP consuma sua chave da NVIDIA).
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


def _mostrar_compatibilidade(r: dict) -> None:
    itens = r.get("itens", [])
    if not itens:
        st.warning("A análise não retornou itens. Tente novamente.")
        return

    contagem = {k: sum(1 for i in itens if i["status"] == k) for k in STATUS_INFO}
    cols = st.columns(4)
    for col, (chave, (rotulo, _)) in zip(cols, STATUS_INFO.items()):
        col.metric(rotulo, contagem[chave])

    for chave, (rotulo, caixa) in STATUS_INFO.items():
        grupo = [i for i in itens if i["status"] == chave]
        if not grupo:
            continue
        st.markdown(f"#### {rotulo}")
        for i in grupo:
            paginas = ", ".join(str(p) for p in _como_lista(i.get("paginas")))
            fonte = f" _(p. {paginas})_" if paginas else ""
            caixa(f"**{i.get('requisito', '')}**\n\n{i.get('justificativa', '')}{fonte}")


# Estado e indexação 

def _indexar_upload(arquivo) -> None:
    chave = (arquivo.name, arquivo.size)
    if st.session_state.get("arquivo_chave") == chave:
        return
    config.EDITAIS_DIR.mkdir(parents=True, exist_ok=True)
    destino = config.EDITAIS_DIR / Path(arquivo.name).name
    destino.write_bytes(arquivo.getbuffer())
    with st.spinner("Lendo o edital e gerando embeddings..."):
        try:
            colecao = indexar_edital(destino)
        except Exception as e:
            st.session_state.pop("colecao", None)
            st.error(f"Não foi possível processar o PDF: {e}")
            return
    st.session_state.update(
        arquivo_chave=chave, colecao=colecao, nome_edital=arquivo.name
    )


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

    with st.sidebar:
        st.header("1. Edital")
        arquivo = st.file_uploader("Envie o edital (PDF)", type=["pdf"])
        if arquivo:
            _indexar_upload(arquivo)
        if st.session_state.get("colecao"):
            st.success(f"Pronto: {st.session_state['nome_edital']}")
        st.divider()
        st.caption(f"Modelo: `{config.LLM_MODEL}`")

    colecao = st.session_state.get("colecao")
    if not colecao:
        st.info("👈 Envie um edital em PDF na barra lateral para começar.")
        return

    aba_resumo, aba_compat, aba_chat = st.tabs(
        ["📄 Resumo", "✅ Compatibilidade", "💬 Chat com o edital"]
    )

    # Resumo 
    with aba_resumo:
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
            extra = st.text_area("Outras informações relevantes (opcional)", height=70)
            enviar = st.form_submit_button("Analisar compatibilidade", type="primary")

        chave_c = ("compat", colecao)
        if enviar:
            perfil = {
                "nivel": nivel,
                "curso_graduacao": curso or "não informado",
                "situacao_graduacao": situacao,
                "instituicao_graduacao": instituicao or "não informada",
                "ano_conclusao": ano or "não informado",
                "proficiencia_idioma": idioma or "não informada",
                "vinculo_empregaticio": vinculo,
                "acoes_afirmativas": afirmativas,
            }
            if extra.strip():
                perfil["outras_informacoes"] = extra.strip()
            with st.spinner("Comparando seu perfil com o edital..."):
                try:
                    st.session_state[chave_c] = analisar_compatibilidade(colecao, perfil)
                except Exception as e:
                    st.error(f"Falha na análise: {e}")
        if chave_c in st.session_state:
            _mostrar_compatibilidade(st.session_state[chave_c])
            st.caption("Resultado preliminar: confirme cada requisito no edital oficial.")

    # Chat 
    with aba_chat:
        historicos = st.session_state.setdefault("historicos", {})
        historico = historicos.setdefault(colecao, [])

        for msg in historico:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                if msg.get("paginas"):
                    st.caption("Fontes (páginas recuperadas): " + ", ".join(f"p. {p}" for p in msg["paginas"]))
                if msg.get("trechos"):
                    with st.expander("Ver trechos usados"):
                        for t in msg["trechos"]:
                            st.markdown(f"**p. {t['pagina']}** · distância {t['distancia']:.3f}")
                            st.text(t["texto"])

        pergunta = st.chat_input("Pergunte algo sobre o edital...")
        if pergunta:
            historico.append({"role": "user", "content": pergunta})
            with st.chat_message("user"):
                st.markdown(pergunta)
            with st.chat_message("assistant"):
                with st.spinner("Buscando no edital..."):
                    try:
                        r = perguntar(colecao, pergunta)
                        historico.append({
                            "role": "assistant",
                            "content": r["resposta"],
                            "paginas": r["paginas"],
                            "trechos": r["trechos"],
                        })
                    except Exception as e:
                        historico.append({"role": "assistant", "content": f"Erro ao responder: {e}"})
            st.rerun()


main()