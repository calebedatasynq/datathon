# Resultado técnico — não representa desempenho em clientes

Foram ajustadas três regressões ordinais em 1.800 registros inteiramente simulados e avaliadas em outros 600. O alvo foi criado por uma equação artificial, não pelas condições do BB. Nenhum plano foi atribuído às empresas do dataset.

| Cenário simulado | Log loss (menor é melhor) | Acurácia balanceada |
|---|---:|---:|
| dois_sinais | 0.9204 | 52.5% |
| um_sinal | 0.9779 | 49.1% |
| somente_ruido | 1.0924 | 33.3% |

O cenário com sinais conhecidos superou o cenário sem informação. Isso verifica funcionamento do treinamento neste teste. Não seleciona variáveis do seguro. Os três modelos convergiram, as probabilidades somam 1 e a decisão por cortes concorda com a decisão ordinal pela mediana.

O exemplo de Essencial foi acertado; os exemplos de Prático e Total foram subestimados. Foram preservados os erros, sem escolher apenas exemplos favoráveis. Os números e os três exemplos completos estão no JSON. Nenhum limiar deste teste pode ser usado em clientes.

Ainda existem zero planos de referência preenchidos na base revisada. Não há acurácia comercial nem pesos empresariais confirmados.
