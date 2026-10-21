# BolsaCheck 🎓

**Assistente inteligente para análise de elegibilidade em editais de bolsas de pós-graduação.**

O BolsaCheck é um projeto acadêmico que utiliza Modelos de Linguagem de Grande Escala (LLMs) e Recuperação Aumentada por Geração (RAG) para auxiliar estudantes na interpretação de editais de bolsas de mestrado e doutorado.

A aplicação permitirá que o usuário envie um edital em PDF, informe seus dados acadêmicos e receba uma análise preliminar dos requisitos, com justificativas baseadas no conteúdo do documento.

> **Aviso:** o BolsaCheck tem como objetivo auxiliar na compreensão dos editais. Suas análises não garantem a aprovação do candidato nem substituem a avaliação oficial da instituição responsável pela bolsa.

## 🎯 Objetivos

- Facilitar a interpretação de editais de bolsas acadêmicas.
- Identificar requisitos obrigatórios e critérios relevantes para a candidatura.
- Comparar os requisitos do edital com as informações fornecidas pelo estudante.
- Apresentar justificativas fundamentadas em trechos do documento.
- Aplicar técnicas de processamento de linguagem natural e inteligência artificial em uma aplicação real.

## ⚙️ Funcionalidades previstas

- [ ] Upload de editais em PDF.
- [ ] Extração e processamento do texto dos documentos.
- [ ] Segmentação do texto em trechos (*chunks*).
- [ ] Geração de embeddings e recuperação semântica.
- [ ] Implementação de RAG para fornecer contexto ao LLM.
- [ ] Integração com um modelo de linguagem pela API da NVIDIA.
- [ ] Formulário para preenchimento do perfil acadêmico.
- [ ] Análise individual dos requisitos do edital.
- [ ] Classificação dos requisitos como atendidos, não atendidos, pendentes de informação ou necessitando de confirmação.
- [ ] Apresentação de justificativas e referências ao documento.
- [ ] Interface web com Gradio.
- [ ] Testes com editais reais e perfis fictícios.
- [ ] Documentação para execução fora do Google Colab.

As funcionalidades serão implementadas e validadas progressivamente durante o desenvolvimento.

## 🧠 Tecnologias previstas

| Tecnologia | Finalidade |
|---|---|
| Python | Linguagem principal do projeto |
| Google Colab | Ambiente inicial de desenvolvimento e experimentação |
| API da NVIDIA | Acesso ao modelo de linguagem |
| Modelos de embeddings | Representação vetorial dos trechos do edital |
| RAG | Recuperação de informações para fundamentar as respostas |
| Gradio | Desenvolvimento da interface web |
| Bibliotecas de processamento de PDF | Extração do conteúdo dos documentos |
| Git e GitHub | Versionamento e organização do código |

Os modelos e as bibliotecas definitivos serão selecionados após os primeiros experimentos, considerando a qualidade das respostas em português, a disponibilidade dos endpoints e os limites de utilização.

## 🔎 Como funcionará

O fluxo planejado da aplicação será:

1. **Envio do edital:** o usuário seleciona um arquivo PDF.
2. **Processamento:** o sistema extrai o texto e o divide em trechos.
3. **Embeddings:** os trechos são convertidos em representações vetoriais.
4. **Recuperação com RAG:** o sistema recupera os trechos relevantes para a análise.
5. **Informações do candidato:** o usuário preenche os dados acadêmicos solicitados.
6. **Análise pelo LLM:** o modelo compara as informações do candidato com os requisitos recuperados.
7. **Apresentação dos resultados:** a interface exibe a situação de cada requisito, as justificativas e as referências disponíveis.

## 📋 Exemplo de utilização

Considere um edital fictício que exige mestrado concluído, proficiência em inglês e matrícula ativa em um programa de doutorado no exterior.

Um candidato informa que concluiu o mestrado, possui certificado de inglês e ainda não está matriculado no doutorado.

A aplicação deverá apresentar uma análise semelhante a esta:

| Requisito | Resultado ilustrativo |
|---|---|
| Mestrado concluído | Atendido |
| Proficiência em inglês | Atendido, sujeito à validade do certificado |
| Matrícula ativa no doutorado | Não atendido |

A conclusão deverá indicar que o candidato não atende a todos os requisitos obrigatórios identificados, explicando os motivos e apontando os trechos relevantes do edital.

*Este exemplo é fictício e serve apenas para demonstrar o comportamento esperado.*

## 📚 Conteúdos da disciplina aplicados

O projeto foi planejado para contemplar os conteúdos da primeira unidade de TEIA.

- **Tokenização:** transformação do texto em tokens para processamento pelo modelo.
- **Embeddings:** representação semântica dos trechos dos documentos.
- **Transformer:** estudo da arquitetura utilizada pelo LLM escolhido.
- **Engenharia de prompt:** elaboração de instruções para orientar a interpretação dos requisitos e a fundamentação das respostas.
- **RAG:** recuperação de trechos do edital para fornecer contexto relevante ao modelo.

O projeto utilizará modelos previamente treinados. Não está previsto treinar um LLM do zero.

## 🚀 Desenvolvimento e execução

O desenvolvimento inicial será realizado no Google Colab. Após a validação dos experimentos, o código será organizado para permitir a execução independente do notebook.

A aplicação final deverá utilizar Gradio como interface web e poderá ser executada na máquina da equipe ou em uma instância EC2.

**Status atual:** planejamento e definição do escopo.

As instruções de instalação, configuração da API e execução serão adicionadas após a implementação da primeira versão funcional.

## 🔐 Segurança

A chave da API da NVIDIA deverá ser armazenada em uma variável de ambiente ou em um arquivo `.env`.

O arquivo `.env` deverá estar listado no `.gitignore`, evitando o envio de credenciais ao repositório.

Os testes iniciais utilizarão editais públicos e perfis fictícios de candidatos. Não deverão ser enviados dados pessoais reais ou documentos confidenciais aos endpoints de teste sem verificar previamente as condições aplicáveis de privacidade e tratamento de dados.

## 🧪 Avaliação

O sistema será avaliado utilizando editais reais e perfis fictícios com diferentes condições de elegibilidade.

Serão considerados:

- Identificação correta dos requisitos.
- Relevância dos trechos recuperados.
- Concordância das classificações com análises de referência.
- Fundamentação das justificativas no documento original.
- Capacidade de reconhecer informações ausentes e ambiguidades.

Quando houver dados de referência suficientes, poderão ser utilizadas métricas como precisão, recall e F1-score.

## ⚠️ Limitações

- A qualidade da análise depende da extração do texto e da interpretação do edital.
- O modelo pode produzir respostas incorretas ou interpretações incompletas.
- Nem todos os PDFs, especialmente os digitalizados ou com tabelas complexas, poderão ser processados corretamente na primeira versão.
- A disponibilidade e os limites de uso da API dependem das condições vigentes da NVIDIA.
- A análise é preliminar e não representa uma decisão oficial sobre a concessão de uma bolsa.

## 🗺️ Próximas etapas

1. Selecionar editais públicos para os experimentos.
2. Testar modelos disponíveis na API da NVIDIA.
3. Implementar a extração e a segmentação dos PDFs.
4. Desenvolver o pipeline de embeddings e RAG.
5. Implementar a análise dos requisitos.
6. Construir a interface com Gradio.
7. Avaliar os resultados e documentar as limitações.
8. Preparar a execução independente do Google Colab.

## 🎓 Contexto acadêmico

Projeto desenvolvido para a disciplina de **TEIA**, com o objetivo de aplicar técnicas de inteligência artificial generativa e recuperação de informações na solução de um problema real.

## 📄 Licença

A licença do projeto será definida posteriormente.

Os editais utilizados nos testes permanecem sujeitos às condições de uso e aos direitos de seus respectivos responsáveis.
