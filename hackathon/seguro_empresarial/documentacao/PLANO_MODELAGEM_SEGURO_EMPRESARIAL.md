# Plano de modelagem — Seguro Empresarial

Data: 28/10/2026. Estado: planejamento; nenhum modelo treinado, rótulo criado ou corte estimado.

Atualização de execução em 28/10/2026: iniciada a preparação das variáveis e das bases, documentada em `VARIAVEIS_E_PROCESSO.md`. A proposta alternativa do documento IPU foi descartada por orientação do usuário; permanece a regressão logística ordinal como hipótese inicial. Não há modelo treinado ou cortes definidos. O planejamento abaixo registra a sequência de referência.

## 1. Objetivo acordado

Criar apoio à decisão do gerente para recomendar ESSENCIAL, PRÁTICO ou TOTAL a novos clientes e identificar oportunidades de revisão do plano de clientes atuais. A proposta é apresentar um score entre 0 e 1 com faixas justificadas, explicações e indicação das informações que precisam de confirmação.

O alvo pretendido é o plano considerado adequado para cada estabelecimento segundo critérios de negócio revisados. Plano vendido historicamente, plano adequado e aceitação de uma oferta são alvos diferentes. O projeto não deve interpretar a previsão de plano como probabilidade de compra ou como estimativa causal do benefício de um upgrade.

## 2. Conferência dos dados disponíveis

Conferência realizada com leitura integral dos 18 CSVs nas duas bases e comparação byte a byte dos 10 arquivos de cada ZIP com suas cópias extraídas. Não foram encontradas diferenças nos arquivos compactados. Não havia outros arquivos de dados na pasta deste projeto, desconsiderando diretórios de configuração.

| Verificação | Desenvolvimento | Teste Comum |
|---|---:|---:|
| Empresas | 2.500 | 120 |
| Estabelecimentos / linhas do template de resultados | 2.978 | 144 |
| `plano_recomendado` preenchido | 0 | 0 |
| `elegivel` preenchido | 0 | 0 |
| Linhas no template de coberturas | 0 | 0 |
| Plano atualmente contratado | Campo não fornecido | Campo não fornecido |

O catálogo contém 21 combinações de plano e cobertura fixa, com três planos distintos. É uma descrição dos produtos; não associa planos a clientes. Não foram encontrados rótulos alternativos de plano contratado, upgrade ou conversão nos campos das bases. A conclusão se limita ao pacote local inspecionado, sem pressupor o conteúdo de sistemas externos do BB.

O LEIA-ME descreve os campos do template como saídas que a equipe deve preencher. Também informa que os dados são sintéticos e que machine learning não é obrigatório. O guia, páginas 12–13, descreve elegibilidade e as coberturas dos planos, sem fornecer classificações individuais para treinamento.

Consequência: podemos começar preparação, definição de critérios e rotulagem. Ainda não podemos estimar coeficientes supervisionados, significância em relação ao plano ou faixas aprendidas dos dados.

## 3. Informações e decisões necessárias

| Necessidade | Como obter ou definir | Uso |
|---|---|---|
| Plano de referência por estabelecimento | Avaliação humana com critérios explícitos, idealmente revisada por especialista/mentor do BB; alternativamente, dados históricos autorizados, após avaliar o significado dos rótulos | Treinar e avaliar o modelo |
| Critérios de recomendação | Matriz de necessidades e coberturas, com origem de cada regra e hipóteses identificadas | Justificar os rótulos e as recomendações |
| Elegibilidade e pendências | Aplicar critérios do guia e confirmar casos inconclusivos; não converter falta de informação automaticamente em inelegibilidade | Evitar recomendar um plano para um caso que exige validação prévia |
| Plano atual e data de referência | Informação da carteira do cliente, se disponível | Comparar recomendação com situação atual e identificar upgrade |
| Necessidades não observadas | Perguntas de confirmação, por exemplo sobre vidros, segurança e interesse segurado | Completar critérios que os dados atuais não representam |
| Custo dos erros de recomendação | Discussão com responsável de negócio: proteção insuficiente, oferta excessiva e revisão manual | Escolher regra de decisão e eventuais cortes operacionais |

Não é necessário ter plano atual para desenvolver recomendação a novos clientes. Ele é necessário para avaliar upgrade real. Se for simulado na demonstração, identificar explicitamente a simulação. Preço e orçamento também precisam ser considerados antes de apresentar a recomendação como escolha economicamente ideal.

## 4. Etapas e critérios de conclusão

### Etapa 1 — Especificar o alvo e a matriz de decisão

Responsáveis: equipe de negócio e pessoa revisora com conhecimento do produto.

- Fixar uma linha por empresa-estabelecimento e definir o que significa “plano adequado”.
- Mapear coberturas fixas e adicionais às necessidades observadas; registrar fonte, variável disponível e pergunta de confirmação.
- Tratar elegibilidade antes da recomendação. Casos inconclusivos ficam pendentes, sem forçar ESSENCIAL como classe de descarte.
- Confirmar se ESSENCIAL < PRÁTICO < TOTAL é também uma ordenação útil de recomendação para os casos avaliados, além de ser uma progressão de cobertura.

Entrega: protocolo de rotulagem e matriz de decisão versionados, com hipóteses diferenciadas das regras do produto.

### Etapa 2 — Preparar a base analítica

Responsável: equipe de dados.

- Usar estabelecimentos como tabela principal; associar empresas por `empresa_id`, sinais por empresa e imóvel, e território por `territorio_id`.
- Agregar bens por imóvel antes da junção: valores, contagens por tipo e indicadores de confiança do vínculo.
- Preservar os CSVs originais; registrar versão, contagens, chaves, ausências e cardinalidade das junções.
- Não repartir faturamento da empresa entre unidades sem uma hipótese explícita. Não apresentar razões entre medidas de granularidades diferentes como indicadores observados.
- Tratar área zero como informação indisponível quando a origem indicar ausência; guardar indicador de ausência.
- Remover IDs dos preditores, manter apenas uma das colunas idênticas `dependencia_digital_pct` e `indice_maturidade_digital`, e avaliar redundância entre atividade/CNAE e entre índices derivados e componentes.
- Pré-selecionar variáveis por hipótese de negócio e disponibilidade no momento da recomendação. Faturamento, atividade, funcionários, área, estoque e bens são candidatos; relevância estatística ainda não foi demonstrada.

Entrega: tabela por estabelecimento e dicionário de variáveis com significado, unidade, origem, transformação, hipótese e limitações. Imputação, escalonamento e demais transformações aprendidas deverão ser ajustados apenas no treino.

### Etapa 3 — Produzir rótulos revisados

- Começar com um piloto diversificado por atividade, porte, número de unidades e qualidade da informação. Proposta operacional: cerca de 150 estabelecimentos, ajustável à disponibilidade dos revisores; esse número não é uma garantia de suficiência estatística.
- Buscar dois julgamentos independentes por caso no piloto. Registrar plano, justificativa, informações faltantes, revisor e versão do critério; resolver divergências por revisão documentada.
- Medir concordância e identificar critérios ambíguos. Não forçar consenso quando faltarem dados.
- Expandir a rotulagem após corrigir o protocolo. Definir volume final com base nas contagens por classe, complexidade do modelo, estabilidade e curvas de aprendizado; não usar os 2.978 registros como se todos já fossem exemplos supervisionados.
- Reservar empresas para avaliação independente antes de ajustar regras, escolher variáveis ou calibrar cortes. Representar também a distribuição esperada de uso, sem avaliar apenas os casos difíceis selecionados no piloto.

Entrega: base rotulada com procedência e amostra de avaliação preservada.

Se especialistas externos não estiverem disponíveis, os julgamentos da equipe podem sustentar um protótipo, com essa limitação explícita. Rótulos produzidos por regras ou IA são provisórios: o desempenho frente a eles mede reprodução dessas regras ou julgamentos. Clustering, por si só, não identifica qual grupo deveria receber cada plano. Um sistema de regras documentadas pode ser a primeira versão demonstrável enquanto a rotulagem é construída.

### Etapa 4 — Definir o desenho de avaliação

- Separar desenvolvimento e avaliação por `empresa_id`, mantendo unidades da mesma empresa no mesmo grupo.
- Conferir eventual sobreposição entre bases antes de usá-las como amostras independentes; a auditoria de rótulos não verificou essa sobreposição.
- Usar validação agrupada dentro do conjunto de desenvolvimento, respeitando a distribuição dos planos tanto quanto possível.
- Não usar o Teste Comum para escolher variáveis, ajustar cortes ou calibrar. Sem rótulos independentes, ele permite conferir execução e gerar entregas, mas não medir acurácia de recomendação.
- Definir previamente métricas: matriz de confusão, macro-F1, erros de uma ou duas categorias, log loss e curvas de calibração por classe. Acurácia isolada não basta.

Entrega: protocolo de avaliação, conjunto reservado e referência simples de comparação, incluindo o sistema de regras.

### Etapa 5 — Estimar efeitos e avaliar significância

- Ajustar regressão logística ordinal como primeira hipótese. Avaliar a suposição de chances proporcionais; comparar com multinomial quando a hipótese for inadequada.
- Para interpretação estatística, usar uma especificação justificada previamente. Examinar coeficientes, unidades dos efeitos, odds ratios, intervalos de confiança e efeitos sobre probabilidades.
- Avaliar variáveis categóricas em conjunto. Considerar a dependência entre estabelecimentos da mesma empresa por inferência robusta agrupada ou reamostragem de empresas; não tratar todas as linhas como independentes.
- Registrar a estratégia de múltiplas comparações se houver muitos testes exploratórios. Não eliminar variáveis automaticamente apenas por `p > 0,05` nem declarar importância pelo tamanho bruto de coeficientes em escalas diferentes.
- Verificar colinearidade, categorias raras, separação e estabilidade dos coeficientes.
- Se houver seleção automática ou regularização para predição, não apresentar valores-p convencionais após essa seleção como inferência confirmatória. Separar os resultados exploratórios das conclusões previamente especificadas.

Entrega: tabela de efeitos e incerteza, resultados de validação e justificativa das variáveis mantidas. Em dados sintéticos com rótulos produzidos pela equipe, a significância descreve esse processo de geração e rotulagem; não comprova efeitos no mercado real.

### Etapa 6 — Construir o score e justificar as faixas

- No modelo ordinal, a combinação ponderada das variáveis gera uma pontuação latente `z`; o ajuste estima dois limiares ordenados na mesma escala.
- É possível transformar `z` e os limiares pela função logística para apresentação entre 0 e 1. Essa escala expressa posição de recomendação; não é, por definição, uma probabilidade de contratação ou de plano específico.
- Distinguir limiares estatísticos dos cortes de decisão comercial. Usar diretamente os limiares ordinais equivale à decisão pela mediana da distribuição de classes; pode diferir da escolha da classe mais provável.
- Se o negócio preferir outra regra, escolher os cortes somente na validação, conforme custos de erro previamente definidos. Não ajustar ao conjunto final reservado.
- Estimar estabilidade dos limites por reamostragem agrupada por empresa. Documentar versão do modelo e da escala; a transformação para 0–1 é uma convenção de apresentação e seus números não são limites universais do produto.
- Se a hipótese ordinal falhar, reavaliar a exigência de um score escalar com intervalos contíguos; um modelo multinomial não fornece automaticamente essa estrutura.

Entrega: fórmula e limites calculados, regra de decisão, justificativa, incerteza e avaliação independente. Nenhum limite numérico está aprovado nesta versão do plano.

### Etapa 7 — Apoiar o gerente e registrar decisões

- Para novos clientes: exibir plano sugerido, justificativas, qualidade dos dados e perguntas necessárias.
- Para carteira existente: comparar com plano atual e destacar a necessidade adicional de cobertura que justifica a revisão. Não recomendar upgrade apenas porque o cliente está próximo de um corte.
- Permitir revisão humana e registrar decisões e discordâncias para avaliação posterior.
- Recomendações em casos próximos aos cortes ou com informação incompleta devem indicar necessidade de confirmação.

Entrega: demonstração com casos contrastantes e relatório de limitações. Para o desafio completo, recomendação de plano deve ser acompanhada pelas saídas de elegibilidade, coberturas e faixas de valores exigidas nos templates; o score não substitui essas saídas.

## 5. O que pode começar agora

1. Especificação do alvo e mapeamento de necessidades às coberturas.
2. Preparação e documentação da tabela por estabelecimento.
3. Organização do piloto e da revisão dos rótulos.
4. Definição prévia da avaliação e dos custos dos erros.

O primeiro bloqueio ao treinamento é a falta de plano de referência por estabelecimento. O bloqueio adicional para upgrade é a falta do plano atual. Não é preciso esperar rótulos para concluir as etapas preparatórias.

## 6. Registro e ferramentas propostas

- Manter esta documentação como versão inicial. Registrar decisões posteriores com data, responsável, evidência e justificativa.
- Python/pandas para preparação; statsmodels para análise ordinal/multinomial e inferência compatível com o desenho; scikit-learn para preparação, validação e alternativas preditivas. Fixar versões efetivamente utilizadas no momento da implementação.
- Artefatos futuros: dicionário analítico, protocolo de rotulagem, base de rótulos com procedência, definição dos grupos de avaliação, relatório de coeficientes, métricas, score e regras de apresentação.
- Não foram implementados pipelines ou ajustados modelos nesta etapa.

## 7. Fontes

- Pacote local: `/home/lucas/Downloads/Seguro_Empresarial_DadosSinteticos/`, diretórios Desenvolvimento e Teste Comum e seus ZIPs.
- `template_resultado_times.csv`: contagem direta dos campos preenchidos em cada base.
- `catalogo_coberturas_fixas_planos.csv`: descrição dos três planos e suas coberturas.
- `LEIA-ME.md` e `dicionario_dados.csv`: natureza, granularidade e papel dos campos.
- `DatathonBBDW_GuiaDosTimes.pdf`, páginas 12–13: elegibilidade e estrutura dos planos empresariais, conferidas visualmente.
- Statsmodels, regressão ordinal: https://www.statsmodels.org/stable/examples/notebooks/generated/ordinal_regression.html
- Scikit-learn, regressão logística: https://scikit-learn.org/stable/modules/generated/sklearn.linear_model.LogisticRegression.html
- Scikit-learn, calibração: https://scikit-learn.org/stable/modules/calibration.html
