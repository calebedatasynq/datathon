# Atualização: versão com 8 variáveis

[Entrega v2: comparação de 8, 9 e 10 variáveis e pseudo-R²](indice_regressao_v2/README.md). A v1 permanece disponível para comparação; a v2 atende ao mínimo de 8 variáveis, sem ganho de desempenho observado.

# Atualização de 28/10/2026: índice treinado na base mock

A entrega ativa está em [indice_regressao_v1/README.md](indice_regressao_v1/README.md). Inclui modelo treinado, pesos, faixas, avaliação externa e perfis para RAG. Os registros abaixo e `estado_modelagem.json` pertencem à etapa anterior sem rótulos revisados; o novo experimento usa referências construídas e está separado.

# Seguro Empresarial — regressão logística ordinal

Projeto para apoiar recomendação de ESSENCIAL, PRÁTICO e TOTAL. Data desta entrega: 28/10/2026.

## Abrir primeiro

1. `notebooks/01_auditoria_variaveis_modelagem.ipynb`: notebook **executado**, com tabelas, gráfico e saídas visíveis.
2. `resultados/RELATORIO_RESULTADOS.html`: relatório para leitura e apresentação no navegador.
3. `resultados/RELATORIO_RESULTADOS.md`: versão textual dos resultados e limitações.
4. `resultados/casos_demonstracao.csv`: 23 cenários com IDs e valores conferidos.
5. `resultados/decisoes_variaveis.csv`: decisão fundamentada sobre 18 variáveis/blocos.

## Estado científico

As três classes são conhecidas. Há **zero associações preenchidas entre estabelecimentos e planos de referência** nas bases entregues. Por isso, nenhum modelo de planos foi treinado, nenhum coeficiente de planos foi estimado e nenhuma acurácia ou limite do score foi inventado.

Os 26 testes verificam dados, preparação e barreiras de entrada. Não são 26 testes de acerto comercial. A auditoria inspecionou 62 campos da tabela ampliada, inclusive aliases e cadastro, que não correspondem a 62 preditores independentes. Os exemplos cobrem atividades e condições de dados; não são exemplos já rotulados de cada plano.

Os documentos em `documentacao` preservam o plano e a lista de candidatas anteriores como histórico. **A revisão mais recente é `resultados/RELATORIO_RESULTADOS.md`**: seis campos na especificação de emprego, faturamento como alternativa a funcionários, e área como comparação adicional. As escolhas seguem provisórias quanto à utilidade para prever planos.

Não foram incorporadas regras, índices ou modelagem do documento IPU descartado.

## Estrutura

```text
dados/originais/       cópias dos CSVs recebidos, sem alteração
dados/preparados/      tabelas por estabelecimento e manifesto de preparação
dados/rotulos/         arquivo para referências revisadas, separado da preparação
src/                  preparação, diagnósticos e comparação ordinal
tests/                conferências dos dados reais e barreiras de entrada
notebooks/            notebook executado
resultados/           evidências, exemplos, relatório e ambiente de execução
documentacao/         plano e dicionário anteriores, preservados como histórico
```

## Executar

Criar um ambiente Python próprio (execução desta entrega: Python 3.12; versões exatas em `resultados/ambiente_execucao.json`):

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python executar_projeto.py
```

Abrir o notebook no VS Code/Jupyter e escolher esse ambiente Python. Não é necessário Jupyter Lab para reproduzir pelo comando acima.

A reprodução substitui resultados e tabelas preparadas, preservando o arquivo de rótulos se ele já existir. Não editar dados preparados para criar rótulos, pois serão recriados.

O notebook executa código Python local; os dados do cliente não são enviados a um serviço de IA. As bibliotecas foram instaladas somente para análise local. `requirements.txt` fixa dependências diretas; `ambiente_execucao.json` registra o ambiente utilizado. A conferência com a pasta original externa usa `/home/lucas/Downloads/Seguro_Empresarial_DadosSinteticos` ou a variável `SEGURO_FONTES_ORIGINAIS`; se ela não estiver disponível em outra máquina, o relatório de hashes indicará essa limitação.

## O que preencher para treinar

`dados/rotulos/rotulos_revisados.csv` já contém os 2.978 pares empresa-estabelecimento. Preencher `plano_referencia`, `justificativa`, `revisor`, `fonte_criterio` e `versao_criterio` para os casos revisados. Plano de referência pode ser uma recomendação; não exige conhecer o plano já contratado.

Não gerar esse alvo simplesmente dividindo faturamento em três faixas para depois declarar sucesso na sua reprodução. A adequação da recomendação precisa de critérios documentados e revisão independente. Pendência de elegibilidade não deve ser convertida automaticamente em ESSENCIAL.

`src/treinar.py` está preparado para comparar três especificações ordinais, respeitando empresas e avaliação reservada. A execução atual só verificou a barreira sem rótulos, não o ajuste e o desempenho em referências reais. O guardrail de cinco empresas por classe serve à execução da validação cruzada; não é garantia de amostra suficiente ou de confiabilidade estatística.

Mesmo depois de obter rótulos, chances proporcionais, calibração e adequação comercial precisam ser avaliadas. Os valores-p após escolha de especificação são exploratórios. O score transformado de 0 a 1 representa posição ordinal, não probabilidade de compra.
