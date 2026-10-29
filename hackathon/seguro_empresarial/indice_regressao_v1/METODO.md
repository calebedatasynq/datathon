# Índice ordinal de perfil empresarial — versão 1

Data: 28/10/2026. Escopo: novas vendas, protótipo do hackathon, base mock fornecida. Esta versão substitui a exigência anterior de revisão externa para executar um experimento. Não substitui os arquivos de rótulos revisados: os novos alvos são referências construídas e identificadas como tais.

## Evidência e hipótese são coisas diferentes

O catálogo fornecido e a [página oficial BB Seguros](https://campanhas.bbseguros.com.br/seguro-empresarial/) mostram o Prático acrescentando proteção contra roubo/furto de bens mediante arrombamento e vendaval, e o Total acrescentando RC empregador e vidros. Isso fundamenta a ligação entre patrimônio, emprego e coberturas. Não determina uma regra oficial de indicação. As condições de aceitação, adicionais, franquias e exclusões continuam dependendo do produto e da contratação.

A política abaixo é uma hipótese explícita da equipe, autorizada para o protótipo. Um estabelecimento com poucos funcionários também pode precisar de RC empregador. Estoque baixo não implica ausência de necessidade de proteção. Essencial significa referência residual da política, não declaração de que outras coberturas são desnecessárias.

## Como construímos a referência

Na política central:

1. TOTAL quando funcionários estimados da empresa atingem ou superam o percentil 75 do treino, calculado com uma linha por empresa. É um indicador indireto de prioridade para RC empregador, não contagem de empregados do endereço.
2. Entre os demais casos, PRÁTICO quando estoque médio ou valor ponderado dos bens atingem ou superam seus percentis 60 no treino, calculados por estabelecimento. É indicador indireto de prioridade de proteção patrimonial.
3. Demais casos: ESSENCIAL.

A precedência é Total, depois Prático, depois Essencial. Percentis foram escolhidos como convenção de priorização relativa antes da avaliação, não descobertos em norma ou otimizados pelo teste. Os valores em reais e empregados aparecem em `criterios_congelados.json`. Esse procedimento evita inventar valores monetários universais, mas não remove a hipótese humana. Não há promessa de classes equilibradas.

Alternativas pré-definidas: percentis 50/65 (mais abrangente) e 70/85 (mais restritivo). A sensibilidade mede a influência dessas escolhas, sem escolher a política que produzir a maior acurácia. Vidros, vendaval, risco geográfico e elegibilidade não recebem rótulo presumido.

## Variáveis comparadas

- Patrimônio e emprego: funcionários, estoque e bens. Ligação direta com os critérios de referência.
- Com faturamento: mesmas variáveis mais receita. Verifica ganho incremental apesar de correlação com empregados.
- Com contexto: primeiras três mais atividade, tipo de unidade e quantidade de estabelecimentos.
- Com área e termos do endereço: primeiras três mais área, presença de loja e galeria. Sinais exploratórios, não confirmação de vidros ou exposição.

Valores ausentes são preenchidos pela mediana do treino e recebem indicador de ausência. Variáveis numéricas passam por log(1+x) e padronização; categorias têm codificação indicadora com uma categoria-base. A transformação é ajustada apenas no treino de cada dobra. IDs não entram no modelo. Regularização L2 evita pesos excessivos ao aprender referências determinísticas; os limiares não são penalizados. Não há seleção de variáveis por p-valor.

## Matemática do índice

Para a linha transformada x, z = soma(beta_j * x_j). O score é S = sigmoid(z) = 1/(1+exp(-z)).

A regressão ordinal estima beta e dois limiares t1 < t2 conjuntamente, minimizando a log-loss média mais alpha/(2n) vezes a soma dos quadrados dos pesos. A ordenação é imposta por t2 = t1 + softplus(d) + 0,0001.

P(Essencial) = sigmoid(t1-z).
P(Prático) = sigmoid(t2-z) - sigmoid(t1-z).
P(Total) = 1 - sigmoid(t2-z).

As faixas são a=sigmoid(t1) e b=sigmoid(t2): Essencial para S<a, Prático para a<=S<b, Total para S>=b. Isto corresponde à mediana da distribuição prevista; a igualdade vai para a classe superior. Essa decisão minimiza o erro absoluto ordinal previsto, mas não necessariamente maximiza a taxa de acerto exato. Os extremos 0 e 1 são limites matemáticos; valores finitos ficam entre eles.

O score não é a probabilidade de compra e tampouco P(Total). As três probabilidades são probabilidades da referência construída, sujeitas à calibração. O peso positivo desloca o índice para planos superiores, condicionado às demais variáveis. Os pesos não somam 100% e não são efeitos causais. Uma contribuição individual é beta_j*x_j; sua soma reproduz z, não o próprio score. Em numéricas, o peso corresponde a um desvio padrão na escala logarítmica, e não a um real ou empregado adicional.

## Separação de dados

Usamos todo o desenvolvimento fornecido para seleção em três dobras por empresa. Estabelecimentos da mesma empresa nunca se dividem entre treino e validação. Os percentis da referência também são recalculados somente no treino de cada dobra, e aplicados sem alteração à validação. Portanto, a validação mede o procedimento completo de geração de referências e ajuste.

Comparamos 4 especificações x 3 penalidades (0,1; 1; 10). Selecionamos menor log-loss média na política central. A sensibilidade usa apenas desenvolvimento. Um modelo multinomial com as mesmas variáveis funciona como diagnóstico de flexibilidade: uma vantagem grande sugere limitação da hipótese ordinal. Não é teste formal de chances proporcionais.

Após a escolha, treinamos em todo o desenvolvimento e gravamos política, parâmetros e hashes. Só então o script lê a base de teste comum, aplica a referência congelada e calcula métricas uma vez. Os IDs do teste foram previamente inspecionados somente para integridade, não para seleção. O código não ajusta critérios, variáveis ou penalidade usando o desempenho externo.

## Incerteza e honestidade

Cem reamostragens por empresa no desenvolvimento estimam estabilidade condicional dos pesos e cortes, mantendo transformação, política e variáveis congeladas. Os intervalos não incluem toda a incerteza da escolha de modelo ou do critério. Mil reamostragens por empresa no teste estimam intervalo da concordância externa, sem retreinar.

Não reportamos p-valores confirmatórios: os rótulos são derivados de variáveis, houve seleção e há penalização. Um intervalo que não cruza zero indica estabilidade condicional no protótipo, não relevância causal ou necessidade comprovada de cobertura. Correlação receita/emprego e dados ausentes limitam interpretação.

A regra que gera o alvo é o comparador determinístico perfeito por construção. A regressão pode perder acertos ao suavizá-la. Seu propósito adicional aqui é produzir índice contínuo, pesos e contribuições; não deve ser apresentada como mais correta que a própria referência nem como prova de aumento de vendas.

## Entrega ao agente

`perfis_rag_teste.jsonl` fornece score, faixas, plano, probabilidades, contribuições e perguntas para cada estabelecimento do teste. O status é EXPERIMENTAL_BASE_MOCK. O agente deve consultar documentos oficiais para explicar coberturas e não transformar uma contribuição estatística em afirmação factual de risco. Elegibilidade permanece NAO_AVALIADA. Proximidade de cortes e sensibilidade sugerem perguntas, não confiança comercial automática.

Para reproduzir: executar `executar.py` no ambiente do projeto. Artefato `modelo_ordinal.pkl` é local e confiável; não carregar pickle de origem desconhecida. `inferir.py` permite novos lotes preparados com o mesmo contrato, sem retreino. Histórico anterior de simulação técnica permanece separado desta execução com a base fornecida.
