# Iterações com 8, 9 e 10 variáveis

Execução: 28/10/2026. Base mock fornecida. Mesma política de referência da v1; aumentamos as variáveis de entrada, sem mudar os alvos para forçar importância das variáveis novas.

## Resultado por iteração

| n_variaveis | alpha | pseudo_r2_mcfadden_treino | pseudo_r2_preditivo_cv | acuracia_cv | log_loss_cv |
| --- | --- | --- | --- | --- | --- |
| 8 | 1.0 | 0.648767 | 0.645772 | 0.834788 | 0.378808 |
| 9 | 1.0 | 0.64885 | 0.644934 | 0.833109 | 0.379705 |
| 10 | 1.0 | 0.649022 | 0.644804 | 0.832774 | 0.379844 |

Foram executados 27 ajustes: três conjuntos de variáveis, três penalidades e três dobras separadas por empresa. A tabela mostra a melhor penalidade de cada conjunto; todos os detalhes estão em `cada_iteracao_e_dobra.csv` e `ranking_cv.csv`. A versão selecionada usa **8 variáveis**, com penalidade 1. A diferença entre as versões é pequena: não afirmamos superioridade estatística comprovada.

## O que significa R² aqui

Usamos **pseudo-R² de McFadden = 1 − LL_modelo/LL_nulo**, conforme [documentação statsmodels](https://www.statsmodels.org/stable/dev/generated/statsmodels.base.model.GenericLikelihoodModelResults.html). LL é a soma dos logaritmos das probabilidades da referência. A penalidade L2 não é incluída nessa soma. O modelo nulo usa apenas frequências dos planos no treino.

No treino, a tabela informa o índice de ajuste McFadden nos parâmetros penalizados. Na validação, usamos a mesma razão como **análogo preditivo**, com frequências aprendidas apenas no treino de cada dobra. Não é o pseudo-R² clássico ajustado na própria validação. O resultado agregado soma as log-verossimilhanças das previsões fora da amostra antes de calcular a razão. Um valor negativo seria possível se as previsões fossem piores que o modelo nulo.

**0,6458 não significa 64,58% da variância explicada nem 64,58% de acerto.** Selecionamos pela menor log-loss de validação, equivalente a maximizar essa razão quando o denominador é o mesmo. A regularização e as referências derivadas impedem interpretar este índice como prova de significância.

## Variáveis

| Iteração | Variáveis acrescentadas | Justificativa e limite |
|---|---|---|
| 8 | Funcionários; estoque; bens; faturamento; quantidade de estabelecimentos; atividade; tipo de unidade; área | Patrimônio, emprego, escala e contexto. Funcionários e faturamento referem-se à empresa, não ao endereço. Área tem muitos valores ausentes. |
| 9 | Presença do termo loja no endereço | Contexto exploratório, não confirmação de vitrine ou risco. |
| 10 | Presença do termo galeria no endereço | Contexto exploratório, não evidência de proteção ou exposição. |

São 8 variáveis originais no modelo escolhido, que viram **17 coeficientes** após categorias e indicador de ausência. Atividade tem vários pesos, relativos à categoria-base BELEZA; tipo de unidade usa FILIAL como base. Não existe um peso único de atividade sem especificar sua categoria. A regressão continua ordinal, com um único índice.

## Pesos e estabilidade

| termo | peso | ic_condicional_2_5 | ic_condicional_97_5 | sinal_estavel_condicional |
| --- | --- | --- | --- | --- |
| num__funcionarios_estimados_empresa | 2.890323 | 2.513148 | 3.355206 | True |
| num__estoque_medio_estimado | 1.302932 | 1.14481 | 1.472943 | True |
| num__valor_bens_ponderado_estabelecimento | 1.018984 | 0.782641 | 1.26607 | True |
| num__faturamento_mensal_empresa | 0.100012 | -0.399497 | 0.411498 | False |
| num__quantidade_estabelecimentos_empresa | -0.137338 | -0.29745 | -0.03159 | True |
| num__area_m2 | 0.059618 | -0.054542 | 0.169789 | False |
| num__missingindicator_area_m2 | 0.003361 | -0.107255 | 0.134345 | False |
| cat__grupo_atividade_CLINICA | 0.243811 | -0.178384 | 0.66629 | False |
| cat__grupo_atividade_ELETRONICOS | 0.20616 | -0.221763 | 0.694726 | False |
| cat__grupo_atividade_ESCOLA_CURSO | 0.201755 | -0.271505 | 0.570321 | False |
| cat__grupo_atividade_ESCRITORIO | 0.067674 | -0.294724 | 0.530529 | False |
| cat__grupo_atividade_FARMACIA | 0.584133 | 0.220909 | 1.013432 | True |
| cat__grupo_atividade_MERCADO | 0.294332 | -0.086985 | 0.655885 | False |
| cat__grupo_atividade_OFICINA | 0.036316 | -0.229433 | 0.443015 | False |
| cat__grupo_atividade_RESTAURANTE | -0.162121 | -0.641332 | 0.192504 | False |
| cat__grupo_atividade_VAREJO_MODA | 0.588416 | 0.237332 | 0.981181 | True |
| cat__tipo_unidade_MATRIZ | 0.227888 | -0.123102 | 0.52441 | False |

Pesos numéricos são para variáveis transformadas por log(1+x) e padronizadas. Indicadores de ausência também passam pela transformação do pipeline. Categorias são indicadores 0/1 com base omitida. A soma das contribuições produz z; sigmoid(z) produz o score. Fórmula e parâmetros completos em `formula_completa.json`.

100 reamostragens por empresa indicam estabilidade **condicional** à política, transformação e seleção. Faturamento, área e o indicador de ausência da área têm intervalos que cruzam zero. Logo, não foram confirmados como efeitos estáveis nesta referência. Funcionários, estoque e bens mantêm sinais positivos estáveis; quantidade de estabelecimentos tem sinal negativo condicional, sem interpretação causal. Alguns contrastes de atividade também têm estabilidade, mas não são recomendação de seguro por setor.

Os critérios de referência continuam baseados em três variáveis. Acrescentar cinco preditores não cria informação de adequação que não existe no alvo. Não é defensável dizer que as oito variáveis são estatisticamente significativas.

## Novas faixas, próprias da versão 2

- Essencial: score abaixo de 0.284127232.
- Prático: de 0.284127232 até abaixo de 0.989682875.
- Total: de 0.989682875 em diante.

Score = sigmoid(X beta); faixas = sigmoid dos dois limiares ajustados. Decisão pela mediana ordinal, não necessariamente pela maior probabilidade. Não arredondar antes de enquadrar. Não misturar scores da v2 com faixas da v1.

## Reavaliação do teste comum

Acertos: **114/144 = 79.17%**, ante 116/144 = 80,56% na v1. Pseudo-R² preditivo: 0.631592. Log-loss: 0.391467. Assim, **o requisito de pelo menos oito variáveis foi atendido, mas não melhorou o resultado observado**. Não ajustamos a seleção com base nessa reavaliação.

O teste já havia sido consultado na versão anterior; esta é uma comparação na mesma base, não uma nova avaliação independente intocada. A concordância é com critérios construídos, não com planos ideais observados. A limitação ordinal frente ao comparador multinomial encontrada na v1 não foi resolvida por acrescentar variáveis.

## Entregáveis e verificações

`perfis_rag.jsonl` contém 144 perfis da versão 2. `modelo_ordinal.pkl` contém a transformação e parâmetros. `inferir.py` aplica novos lotes sem treinar. `testes.json` registra 11 verificações aprovadas e `teste_inferencia.json` confirma reprodução dos 144 scores e planos após carregar o modelo. O notebook apresenta a execução congelada.
