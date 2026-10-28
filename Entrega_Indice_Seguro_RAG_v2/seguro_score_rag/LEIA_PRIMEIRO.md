# Entrega para a dupla do RAG — índice empresarial v2

Este pacote é autocontido. Extraia o ZIP antes de executar. Não precisa acessar o computador de origem, conta externa ou internet para calcular scores. Requer Python 3.9 ou superior (se não estiver instalado, instalar Python é o único pré-requisito da inferência).

## Testar em poucos passos

Abra um terminal na pasta `seguro_score_rag` extraída:

```text
python testar.py
python score.py --entrada exemplos/empresa.json --saida saidas/empresa.jsonl
python score.py --entrada exemplos/lote.csv --saida saidas/lote.jsonl
python score.py --entrada dados/preparados/base_teste_comum.csv --saida saidas/teste.jsonl
```

No Windows, se necessário, use `py -3` em lugar de `python`. No Linux/macOS, pode ser `python3`. Não é preciso executar `pip install` para esses comandos. As saídas são JSONL: um objeto JSON por linha. A pasta de saída é criada automaticamente.

Os caminhos de entrada e saída são relativos ao terminal. O código localiza os parâmetros pelo próprio arquivo, funcionando mesmo quando chamado de outra pasta. Os comandos não treinam nem modificam o modelo.

## Integrar como ferramenta do agente

Com esta pasta no caminho de importação do aplicativo:

```python
from score import score_empresa
perfil = score_empresa(dados_da_empresa)
```

A função recebe um dicionário com os campos definidos em `documentacao/CONTRATO_RAG.md` e retorna um dicionário. Não há API HTTP pronta neste pacote; a dupla registra essa função no mecanismo de ferramentas do agente. Não é necessário carregar pickle, chamar uma LLM ou abrir um notebook para calcular o score.

Importante: usar os valores originais, sem logaritmo nem padronização prévia. O código faz a transformação. Não recalcular as faixas por conta própria e não usar faixas da v1.

## Conteúdo

- `score.py`: função e comando portátil, apenas Python padrão.
- `testar.py`: confere 3.122 linhas contra a implementação treinada e testa entradas problemáticas.
- `modelo/`: parâmetros matemáticos, política de referência e intervalos observados.
- `dados/preparados/`: bases prontas para inferência; representam estabelecimentos, não apenas empresas.
- `dados/originais/`: CSVs mock recebidos, para consulta. Não enviar um CSV original isolado diretamente à função.
- `exemplos/`: entrada, resposta e referência numérica para testes.
- `documentacao/`: contrato, explicação das fontes, roteiro de integração e limitações.
- `evidencias/`: relatório, notebook executado, auditoria e resultados da versão 2.
- `treinamento/`: código opcional para reproduzir o treinamento. Precisa das dependências específicas; não é necessário para o RAG.
- `MANIFESTO_SHA256.json`: permite verificar integridade dos arquivos após transferência.

## Modelo e limites

São 8 variáveis originais, transformadas em 17 coeficientes. Treinado em 2.978 estabelecimentos mock; reavaliado em 144, com 79,17% de concordância com referências construídas pela equipe. Não é acurácia de plano ideal observado. O teste já havia sido consultado na v1. A inclusão de variáveis não melhorou o desempenho observado frente à v1.

Status normal: `EXPERIMENTAL_BASE_MOCK`. Se faltar um dos três dados principais ou a categoria for desconhecida, a interface retorna `PRECISA_CONFIRMACAO`, score e plano nulos. Essa guarda operacional é adicional à regressão: evita recomendar com informação essencial desconhecida. Área e outros números opcionais ausentes podem ser imputados, sempre com aviso. Não há probabilidade de compra nem elegibilidade automática.

O RAG deve usar os documentos oficiais para coberturas e o resultado da ferramenta para o índice. A integração e a qualidade das respostas da LLM ainda precisam ser testadas pela dupla; os testes fornecidos verificam apenas os cálculos e o contrato local.

## Treinamento opcional

Crie um ambiente separado, instale `treinamento/requirements.txt` e execute `python treinamento/executar.py`. Os caminhos foram adaptados ao pacote. O script grava sua nova execução em `treinamento/resultados`, sem substituir o modelo servido em `modelo/`. As versões de bibliotecas registram o ambiente original; não são exigidas pela inferência portátil. A execução original está preservada nas evidências; o treinamento completo não foi repetido durante o empacotamento.
