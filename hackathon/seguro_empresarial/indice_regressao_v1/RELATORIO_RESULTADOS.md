# Resultado do índice por regressão — base mock fornecida

Executado em 28/10/2026. **Modelo treinado de fato no desenvolvimento fornecido: 2978 estabelecimentos. Teste externo: 144 estabelecimentos de 120 empresas.** Não é a simulação matemática anterior.

## Resultado principal

Concordância com os planos de referência construídos: **80.56% (116/144)**. Macro-F1: 0.7856; acurácia balanceada: 77.59%. Intervalo bootstrap por empresa para concordância: 73.6%–86.8%. Referência simples de classe mais frequente: 45.83%. A regra geradora teria 100% por definição, sem comprovar adequação comercial.

A seleção interna escolheu **patrimonio_emprego**, regularização 0.1. Quatro conjuntos de variáveis e três penalidades foram comparados em três dobras por empresa. A concordância interna média foi 84.15%. O teste externo não foi usado para escolher o modelo.

## Fórmula aprendida

z = 2.916990 × funcionários_padronizados + 1.395199 × estoque_padronizado + 1.012302 × bens_padronizados.

score = 1/(1+exp(-z)). Cada variável é padronizada depois de log(1+valor); use as médias e desvios em `formula_parametros.json`. Não multiplicar os pesos diretamente pelos valores brutos em reais. A fórmula independente foi conferida contra todos os scores do teste.

| termo | peso_beta | ic_bootstrap_2_5 | ic_bootstrap_97_5 | sinal_estavel_condicional | media_abs_contribuicao_treino |
| --- | --- | --- | --- | --- | --- |
| num__funcionarios_estimados_empresa | 2.91699 | 2.647883 | 3.23925 | True | 2.561075 |
| num__estoque_medio_estimado | 1.395199 | 1.226972 | 1.533605 | True | 1.125937 |
| num__valor_bens_ponderado_estabelecimento | 1.012302 | 0.756573 | 1.227932 | True | 0.831348 |

Os três sinais ficaram positivos nas reamostragens. Isso é estabilidade condicional à referência proposta; **não é prova de significância estatística independente ou causalidade**. Os pesos são estimados, mas favorecem as variáveis que a política escolheu para criar os rótulos.

## Faixas aprendidas

| Score sem arredondamento | Indicação |
|---|---|
| 0 ≤ S < 0.210735828 | Essencial |
| 0.210735828 ≤ S < 0.984372567 | Prático |
| 0.984372567 ≤ S ≤ 1 | Total |

Os limites vêm dos dois limiares estimados da regressão, transformados pela função logística. A indicação usa a mediana ordinal; pode diferir da maior probabilidade de classe. Não arredondar o score antes de enquadrar. O intervalo do Total é estreito porque esta escala concentra scores altos perto de 1; não representa pouca frequência de clientes Total. Precisão decimal não significa certeza comercial.

## O que funcionou e o que não funcionou

- Empregados, estoque e bens foram suficientes para a melhor log-loss ordinal interna. Faturamento, contexto, área e termos de endereço não melhoraram o critério de seleção nesta comparação; isso não prova que sejam irrelevantes fora desta política.
- No teste: Essencial 64/66, Prático 24/43, Total 28/35. Prático foi a classe mais difícil: 16 casos desceram para Essencial e 3 subiram para Total. Houve 28 divergências no total, todas entre classes vizinhas.
- O comparador de regressão multinomial obteve log-loss interna 0,2133 e concordância 91,57%, contra 0,3759 e 84,15% da ordinal. **A ordinal não foi o melhor classificador comparado.** Sua restrição de um único eixo e pesos comuns custa desempenho nesta política. Mantivemos a ordinal como versão experimental por entregar o índice unidimensional solicitado; não a apresentamos como vencedora geral.
- Alterar a política muda aproximadamente 21%–23% das indicações internas. Portanto as recomendações dependem materialmente das hipóteses. Nenhum dos cenários foi escolhido pelo resultado do teste.
- As probabilidades não foram calibradas para vendas reais; não representam chance de contratação. A avaliação mede reprodução de uma política construída.

## Sensibilidade

| cenario | mudanca_recomendacao_oof | variacao_media_score_oof | corte1 | corte2 |
| --- | --- | --- | --- | --- |
| central | 0.0 | 0.0 | 0.210736 | 0.984373 |
| mais_abrangente | 0.210208 | 0.012816 | 0.030794 | 0.930508 |
| mais_restritivo | 0.231363 | 0.010719 | 0.657662 | 0.996341 |

Os pesos por cenário e os intervalos bootstrap estão nos arquivos anexos. O score médio muda pouco, mas os cortes mudam bastante; nunca misturar score de uma versão com cortes de outra.

## Exemplos, incluindo erros

Primeiro caso disponível de cada referência e primeiro erro de cada classe, sem escolher apenas acertos:

| empresa_id | imovel_id | referencia_criterios | plano_indicado | score | acertou_referencia |
| --- | --- | --- | --- | --- | --- |
| CASO_00004 | IMO_CASO_00004_01 | ESSENCIAL | ESSENCIAL | 0.008504 | True |
| CASO_00026 | IMO_CASO_00026_01 | ESSENCIAL | PRATICO | 0.213372 | False |
| CASO_00003 | IMO_CASO_00003_01 | PRATICO | PRATICO | 0.957622 | True |
| CASO_00007 | IMO_CASO_00007_01 | PRATICO | ESSENCIAL | 0.118742 | False |
| CASO_00001 | IMO_CASO_00001_01 | TOTAL | TOTAL | 0.997373 | True |
| CASO_00020 | IMO_CASO_00020_01 | TOTAL | PRATICO | 0.972237 | False |

## RAG e reprodução

`perfis_rag_teste.jsonl` contém 144 perfis estruturados com contribuições, perguntas e limitações. `modelo_ordinal.pkl` congela a transformação, pesos e critérios. `inferir.py` aplica a novos CSVs preparados. `METODO.md` explica a política e a matemática. O notebook apresenta a mesma execução, sem retreinar no teste. Onze verificações numéricas e de integridade passaram, além da conferência independente da fórmula.

**Conclusão honesta:** o índice já funciona e produz pesos, faixas e explicações para a competição. Há evidência de generalização da política na base mock, mas a sensibilidade e o melhor resultado multinomial mostram que a versão ordinal deve ser apresentada como um compromisso explicável, não como plano ideal comprovado.
