# Euler: agente empresarial

Projeto da equipe BBDI para o Datathon Proteção Inteligente. O MVP conversa com uma empresa ou gerente, calcula uma sugestão inicial de plano, considera necessidades de cobertura e recupera cláusulas para explicar a resposta. Os dados do desafio são sintéticos.

## Como funciona

1. `agente/perfil.py` consulta o índice de regressão logística ordinal e produz um score entre 0 e 1 e um plano inicial.
2. `agente/personalizacao.py` e `agente/regras.py` usam dados do estabelecimento e respostas confirmadas para ajustar a sugestão e as faixas de cobertura.
3. `agente/rag.py` busca trechos das Condições Gerais e fontes do produto. A busca combina palavras-chave e vetores quando o índice vetorial está disponível; sem ele, usa BM25 e emite um aviso.
4. O decisor interpreta a mensagem, o redator formula a resposta com as fontes recuperadas e o guardrail verifica citações e promessas. Casos incertos podem ser encaminhados a um gerente.

O score não é probabilidade de compra. O modelo foi treinado com rótulos construídos pela equipe sobre dados sintéticos; ele não comprova qual plano é ideal para clientes reais. A sugestão não representa cotação, aprovação de risco ou emissão de apólice.

## Executar a demonstração

Requer Python 3.13, as dependências de `requirements.txt` e acesso à rede para respostas ao vivo. Na raiz do repositório:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

Abra `http://127.0.0.1:8000`. Copie `.env.example` para `.env` e substitua o valor de exemplo de `ANTHROPIC_API_KEY` por uma chave válida para conversar com o agente. `JEV_API_KEY` é opcional; sem ela, o decisor usa Claude. O arquivo `.env` é ignorado pelo Git. Mude a Key conforme modelo.

Para reconstruir o índice vetorial, execute `python scripts/indexar_rag.py`. Esse passo pode baixar o modelo de embeddings. Os arquivos `conhecimento/clausulas.jsonl` e `conhecimento/fontes_produto.jsonl` já estão no repositório; a busca por palavras-chave funciona sem o índice vetorial.

## Dados e arquivos

| Caminho | Conteúdo |
| --- | --- |
| `Seguro_Empresarial_Desenvolvimento/` | Base sintética usada para referências e treino do índice. |
| `Seguro_Empresarial_Teste_Comum/` | Casos e templates do teste comum do desafio. |
| `Entrega_Indice_Seguro_RAG_v2/seguro_score_rag/` | Motor de score usado pelo agente, parâmetros, documentação e evidências do modelo. |
| `dados/cg/` e `conhecimento/` | Condições Gerais e trechos consultados pelo RAG. |
| `dados/fixtures/` | Personas e dados de apoio à demonstração e aos testes. |
| `agente/`, `interface/` e `web/` | Lógica da conversa, API e interface. |
| `scripts/` e `testes/` | Preparação, indexação, exportação e testes. |
| `saidas/` | Os dois CSVs gerados pela versão atual deste repositório. |
| `docs/` | Fontes e limitações do enriquecimento territorial. |
| `hackathon/` e `rag/rag/` | Material analítico e protótipos anteriores, preservados para consulta. |

## Reproduzir os CSVs

Após instalar as dependências, execute `python scripts/exportar_templates.py`. O comando preenche `saidas/template_resultado_times.csv` e `saidas/template_coberturas_times.csv` sem chamar modelos de linguagem. Os arquivos versionados nesta revisão têm 144 linhas de resultado e 1.271 linhas de coberturas. Esses números descrevem os arquivos presentes na `main`; execute o comando e compare os arquivos antes da submissão.

Para os testes automatizados, use `python -m pytest -q`. `testes/test_conexoes.py` chama serviços externos e exige credenciais válidas; os demais testes devem ser avaliados conforme as dependências do ambiente.

## Limitações e fontes

As recomendações usam dados fictícios e podem depender de confirmação de atividade, imóvel, cobertura e elegibilidade. Não há integração demonstrada com emissão real de apólice. O agente não informa preço. O enriquecimento por CEP usa fontes públicas e pode ter granularidade de município ou dados ausentes; veja `docs/fontes_territoriais.md`. IA foi usada ativamente durante  o desenvolvimento do projeto, nas seguintes áreas: (Códigos python, interfaces visuais [frontend], geração de documentação [Fora esse], preenchimento do template, calculos matematicos e  Alimentação do RAG) Ideia e lógica do projeto foi usado apenas para duvidas.
