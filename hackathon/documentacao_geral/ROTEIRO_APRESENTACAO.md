# Roteiro para apresentar o protótipo com segurança

## 1. Problema e proposta

“Queremos apoiar o gestor na conversa de venda de seguro empresarial. A solução combina um índice calculado por regressão e um agente RAG que explica coberturas, contextualiza o perfil e pergunta o que falta.”

O índice sugere um enquadramento; não aprova a contratação nem confirma elegibilidade.

## 2. Dados e referência

“Usamos a base mock fornecida: 2.978 estabelecimentos no desenvolvimento e 144 estabelecimentos de 120 empresas no teste comum. Não há empresa compartilhada entre essas duas bases.”

“Como a base não traz o plano adequado de cada empresa, construímos uma referência com critérios explícitos ligados às coberturas. O BB fundamenta quais coberturas existem; os critérios de associação foram propostos por nós.”

Política central, calculada no desenvolvimento: Total para funcionários estimados da empresa >=17; entre os restantes, Prático quando estoque médio >=percentil 60 (aproximadamente R$39.670) ou bens ponderados >=percentil 60 (R$196.460); restante Essencial. A prioridade de Total é uma aproximação de RC empregador; patrimônio aproxima prioridade da proteção contra roubo. Não são limites oficiais nem necessidades confirmadas. No código, usar os limites completos, não os arredondados para apresentação.

## 3. Regressão e comparação

“Comparamos versões de 8, 9 e 10 variáveis, três intensidades de regularização e três divisões por empresa: 27 ajustes. Transformações e critérios foram calculados somente com o treino de cada divisão. A versão de 8 variáveis teve a menor log-loss de validação.”

Variáveis: funcionários, estoque, bens, faturamento, número de estabelecimentos, atividade, tipo de unidade e área. Atividade gera coeficientes por categoria; oito variáveis não significa oito coeficientes. O modelo final tem 17 coeficientes após codificação e indicador de ausência.

| Versão | Pseudo-R² no treino | Índice preditivo na validação | Concordância na validação |
|---|---:|---:|---:|
| 8 variáveis | 0,6488 | 0,6458 | 83,48% |
| 9 variáveis | 0,6489 | 0,6449 | 83,31% |
| 10 variáveis | 0,6490 | 0,6448 | 83,28% |

O pseudo-R² compara a log-verossimilhança com um modelo que usa somente frequências dos planos. Não significa porcentagem de variância explicada. As diferenças são pequenas; não fizemos teste confirmatório de superioridade entre as versões.

## 4. Score e explicação

“A regressão estima os pesos e dois limiares. Somamos as contribuições das variáveis transformadas e aplicamos a função logística, obtendo score entre 0 e 1. Os limiares passam pela mesma transformação para produzir as faixas.”

Faixas da v2: Essencial abaixo de 0,284127232; Prático até abaixo de 0,989682875; Total a partir desse limite. A implementação usa a precisão completa. A decisão corresponde à mediana ordinal da distribuição prevista. Score não é chance de compra e não é, por si só, probabilidade do plano Total.

Funcionários, estoque e bens têm pesos positivos estáveis condicionados à política. Faturamento e área tiveram intervalos que cruzam zero. Não apresentamos todas as oito variáveis como estatisticamente significativas. Efeitos de atividade são relativos à categoria-base, não recomendações universais por setor.

## 5. Resultado e limites

“No teste comum, o modelo reproduziu 114 de 144 referências: 79,17%. Esse número mede concordância com nossa política, e não acerto sobre um plano ideal observado.”

- A base de teste foi reavaliada após a v1; não chamamos a v2 de nova validação independente intocada.
- A v1 com três variáveis teve 80,56%; o requisito de oito variáveis não trouxe ganho observado.
- Na v1, mudar os critérios alterou 21%–23% das indicações internas. Essa análise é da v1, não uma medição de sensibilidade específica da v2.
- O comparador multinomial da v1 classificou melhor internamente. A ordinal fornece o score único com faixas solicitado, com custo de flexibilidade. Não foi demonstrado que seja o melhor classificador.
- Como os rótulos vêm de regras, a regra original teria 100% de concordância por construção. A contribuição da regressão neste protótipo é um índice contínuo e uma decomposição de contribuições. A utilidade comercial desse índice ainda não foi medida.

## 6. Integração com RAG

“O agente recebe score, plano sugerido, probabilidades da referência, contribuições e campos ausentes. Usa documentos do seguro para explicar coberturas e perguntas para confirmar necessidades.”

A entrega contém 144 perfis, mas a existência do arquivo não comprova integração ponta a ponta. Antes de uma demonstração integrada, a outra dupla precisa consumir o arquivo e verificar que o agente:

1. Usa a versão v2 e suas faixas, sem misturar com v1.
2. Distingue dado cadastral de hipótese e de necessidade confirmada.
3. Não chama o score de chance de compra.
4. Cita a fonte da cobertura e não atribui nossos quantis ao BB.
5. Não inventa preço, franquia, elegibilidade ou informação ausente.

## Respostas curtas para a banca

**“Está validado?”** A consistência técnica e a concordância com nossa política foram verificadas na base mock. Adequação comercial e aumento de vendas não foram validados.

**“Por que esses rótulos?”** Para viabilizar o experimento sem histórico de planos, propusemos critérios transparentes e rastreáveis às coberturas. A associação é nossa hipótese, e não uma verdade observada.

**“Por que oito variáveis?”** Para explorar patrimônio, emprego e contexto dentro do escopo definido. A comparação mostrou que mais variáveis não melhoraram o desempenho; não ocultamos isso.

**“O que falta?”** Validar a conversa integrada ao RAG e, fora do hackathon, coletar necessidades e resultados observados para avaliar adequação, calibração e impacto nas vendas.

## Evidência da auditoria

Em 28/10/2026, 14 verificações passaram: preservação dos arquivos, separação de empresas, reprodução dos 144 scores, planos e referências, acurácia, log-loss, fórmula, contagem das iterações, cálculo dos índices, seleção por validação e execução do notebook. Arquivo: `AUDITORIA_APRESENTACAO.json`.
