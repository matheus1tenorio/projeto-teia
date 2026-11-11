# Resumo do edital e análise de compatibilidade com o perfil do candidato
import json
import re
from datetime import date

import openai

import config
from core.rag import _get_llm, buscar, montar_contexto

CONSULTAS_RESUMO = {
    "identificacao": "instituição, programa de pós-graduação, curso, número do edital",
    "vagas_bolsas": "número de vagas, modalidades e quantidade de bolsas, valor da bolsa",
    "requisitos": "requisitos para inscrição e participação, quem pode se candidatar",
    "documentos": "documentos necessários para inscrição",
    "prazos": "prazos, datas, cronograma, período de inscrição, resultado",
    "selecao": "critérios de seleção, etapas, provas, pontuação, nota mínima",
}


def _criar_completion(system: str, user: str, desativar_raciocinio: bool):
    kwargs = dict(
        model=config.LLM_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.1,
        max_tokens=config.MAX_TOKENS_ANALISE,
    )
    if desativar_raciocinio:
        kwargs["extra_body"] = {"chat_template_kwargs": {"enable_thinking": False}}
    return _get_llm().chat.completions.create(**kwargs)


def _extrair_json(texto: str) -> dict:
    texto = re.sub(r"```(?:json)?", "", texto)
    inicio, fim = texto.find("{"), texto.rfind("}")
    if inicio == -1 or fim == -1:
        raise ValueError(f"Sem JSON válido: {texto[:200]}")
    return json.loads(texto[inicio:fim + 1])


def _chamar_llm_json(system: str, user: str, tentativas: int = 3) -> dict:
    ultimo_erro: Exception = RuntimeError("Falha ao obter resposta do LLM")
    desativar = config.DESATIVAR_RACIOCINIO

    for _ in range(tentativas):
        try:
            resp = _criar_completion(system, user, desativar)
        except openai.APIStatusError as e:
            print(f"[ERRO {e.status_code}] modelo={config.LLM_MODEL}")
            print(e.response.text)
            if desativar and e.status_code == 400:
                print("[AVISO] API recusou enable_thinking; tentando sem o parâmetro.")
                desativar = False
                ultimo_erro = e
                continue
            raise

        escolha = resp.choices[0]
        texto = escolha.message.content or ""

        if not texto.strip():
            print(
                f"[AVISO] Resposta vazia | finish_reason={escolha.finish_reason} "
                f"| usage={resp.usage}"
            )
            ultimo_erro = ValueError(
                f"Resposta vazia (finish_reason={escolha.finish_reason})"
            )
            continue

        try:
            return _extrair_json(texto)
        except (ValueError, json.JSONDecodeError) as e:
            ultimo_erro = e

    raise ultimo_erro


def _contexto_para(colecao: str, consultas: list[str]) -> list[dict]:
    vistos, trechos = set(), []
    for q in consultas:
        for t in buscar(colecao, q, k=config.K_POR_CONSULTA):
            chave = (t["pagina"], t["texto"][:80])
            if chave not in vistos:
                vistos.add(chave)
                trechos.append(t)
    return trechos


# Resumo 

SYSTEM_RESUMO = """Você extrai informações estruturadas de editais de pós-graduação.
Use SOMENTE os trechos fornecidos. Se algo não estiver nos trechos, use "Não informado no edital".

Regras:
1. Se o edital cobre mestrado e doutorado, inclua apenas itens do nível "{nivel}" ou comuns aos dois níveis.
2. Itens exclusivos do outro nível NÃO devem aparecer.
3. Não inclua nomes de membros de comissões nem listas longas de nomes.
4. Não cite números de trecho; cite apenas páginas, no formato (p. X), quando útil.

Responda APENAS com um objeto JSON, sem texto fora dele, com exatamente estas chaves:
{{
  "instituicao": "string",
  "programa": "string",
  "modalidades_bolsas": "string (modalidades, quantidade e valor, se informados)",
  "requisitos": ["string"],
  "documentos": ["string"],
  "prazos": [{{"evento": "string", "data": "string"}}],
  "criterios_selecao": ["string"],
  "outras_informacoes": ["string"]
}}"""


def resumir_edital(colecao: str, nivel: str = "Mestrado") -> dict:
    trechos = _contexto_para(colecao, list(CONSULTAS_RESUMO.values()))
    user = (
        f"NÍVEL DO CANDIDATO: {nivel}\n\n"
        f"TRECHOS DO EDITAL:\n{montar_contexto(trechos)}\n\n"
        "Gere o JSON do resumo."
    )
    return _chamar_llm_json(SYSTEM_RESUMO.format(nivel=nivel), user)


# Compatibilidade 

SYSTEM_COMPAT = """Você compara o perfil de um candidato com os requisitos FORMAIS de ELEGIBILIDADE e DOCUMENTAÇÃO de um edital de pós-graduação.

Regras:
1. Use SOMENTE os trechos do edital e os dados do perfil informados.
2. Liste apenas requisitos que o candidato precisa cumprir para se inscrever: titulação, prazos, documentos, taxa, língua, vínculo, ações afirmativas.
3. NÃO liste critérios de PONTUAÇÃO ou classificação: fórmulas de nota, pesos, desempate, etapas de avaliação, nem itens que apenas somam pontos (ex.: vínculo profissional, curso lato sensu, produção científica, histórico). Se o item é opcional ou só gera pontos, não o inclua.
4. Classifique cada item como:
   - "atende": o perfil comprova claramente o cumprimento;
   - "nao_atende": o perfil claramente não cumpre;
   - "confirmar": o perfil não traz dados suficientes (ex.: posse de documentos) ou o edital é ambíguo;
   - "nao_se_aplica": o requisito só vale para quem está em outra situação (outro nível, ações afirmativas, vaga de servidor, estrangeiro etc.).
5. Ter concluído um curso NÃO comprova posse do diploma ou histórico: use "confirmar".
6. Avalie apenas requisitos do nível do perfil. Respeite o que o edital diz para cada nível; não atribua requisito de um nível ao outro.
7. Justificativa curta (uma frase), citando só a página no formato (p. X). Nunca cite "Trecho N".
8. NÃO estime chances de aprovação nem de obtenção de bolsa.
9. Se um prazo do edital já terminou em relação à DATA DE HOJE, classifique como "confirmar" e diga na justificativa que o prazo foi encerrado em DD/MM/AAAA.

Responda APENAS com um objeto JSON, sem texto fora dele, neste formato:
{
  "itens": [
    {"requisito": "string", "status": "atende|nao_atende|confirmar|nao_se_aplica",
     "justificativa": "string", "paginas": [1]}
  ]
}"""

STATUS_VALIDOS = {"atende", "nao_atende", "confirmar", "nao_se_aplica"}


def analisar_compatibilidade(colecao: str, perfil: dict) -> dict:
    consultas = [
        "requisitos para inscrição e participação",
        "requisitos para concessão de bolsa, dedicação exclusiva, vínculo empregatício",
        "titulação exigida, graduação, mestrado, diploma",
        "nota mínima, média, proficiência em língua estrangeira",
        f"documentos exigidos para o nível {perfil.get('nivel', '')}",
        "taxa de inscrição, isenção, CadÚnico",
        "ações afirmativas, cotas, autodeclaração",
        "currículo Lattes, comprovação de produção científica",
    ]
    trechos = _contexto_para(colecao, consultas)
    perfil_txt = "\n".join(f"- {k}: {v}" for k, v in perfil.items())
    user = (
        f"DATA DE HOJE: {date.today():%d/%m/%Y}\n\n"
        f"TRECHOS DO EDITAL:\n{montar_contexto(trechos)}\n\n"
        f"PERFIL DO CANDIDATO:\n{perfil_txt}\n\n"
        "Gere o JSON da análise."
    )
    resultado = _chamar_llm_json(SYSTEM_COMPAT, user)

    itens = []
    for item in resultado.get("itens", []):
        if not isinstance(item, dict):
            continue
        if item.get("status") not in STATUS_VALIDOS:
            item["status"] = "confirmar"
        item.setdefault("justificativa", "")
        item.setdefault("paginas", [])
        itens.append(item)
    return {"itens": itens}