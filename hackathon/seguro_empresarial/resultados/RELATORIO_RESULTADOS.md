# Resultado honesto da etapa de variáveis e preparação

Data: 28/10/2026. As três categorias de saída são conhecidas: ESSENCIAL, PRATICO e TOTAL.

## Resultado alcançado

- 26 testes executados, 26 aprovados, 0 com falha/erro.
- 18 de 18 CSVs copiados conferem byte a byte com os arquivos originais externos disponíveis.
- Desenvolvimento: 2.978 estabelecimentos e 2.500 empresas. Teste Comum: 144 e 120.
- 62 campos foram inspecionados na tabela ampliada, incluindo aliases preservados para auditoria e campos de cadastro; não são 62 preditores independentes propostos.
- 18 decisões de variáveis documentadas; 23 cenários com identificadores e valores reais conferidos com as fontes.
- Partição proposta: 2390 linhas de desenvolvimento/treino e 588 para avaliação reservada, com zero empresas compartilhadas.
- A execução não estimou acurácia, coeficientes, valores-p em relação aos planos ou cortes do score: não há associação de referência entre os estabelecimentos e os três planos.

## O que significa “cada caso” nesta entrega

Há pelo menos um exemplo de cada uma das dez atividades e de cada condição verificada: área disponível/ausente; empresa com uma/várias unidades; matriz/filial; faturamento informado/presumido; existência/ausência de bens de baixa confiança; imóvel em obra/irregular; endereço incompatível. São cenários de dados, não exemplos comprovados de cada plano.

| plano | coberturas_catalogadas | exemplos_rotulados | acuracia | situacao |
| --- | --- | --- | --- | --- |
| ESSENCIAL | 5 | 0 | NÃO ESTIMÁVEL | Categoria conhecida; vínculo cliente-plano ausente |
| PRATICO | 7 | 0 | NÃO ESTIMÁVEL | Categoria conhecida; vínculo cliente-plano ausente |
| TOTAL | 9 | 0 | NÃO ESTIMÁVEL | Categoria conhecida; vínculo cliente-plano ausente |

Não atribuí planos fictícios para preencher essa tabela. Para treinar, plano de referência pode ser uma recomendação revisada por especialistas; não precisa ser o plano atualmente contratado. Para identificar upgrade real, o plano atualmente contratado será necessário posteriormente.

## Revisão da lista inicial

A lista anterior de oito variáveis foi revisada, sem forçar sua confirmação. A especificação de emprego usa seis campos: atividade, funcionários da empresa, número de unidades, matriz/filial, estoque médio e bens ponderados. A especificação econômica substitui funcionários por faturamento. A terceira adiciona área à especificação de emprego.

Faturamento e funcionários têm correlação 0,9352 por estabelecimento e 0,9346 por empresa única. No diagnóstico numérico em log e 1.140 casos completos, seus VIFs foram 13,55 e 10,90. Isso motiva comparação de especificações, não prova que um deles é inútil. A área falta em 61,72% das linhas. Estoque médio e pico têm correlação 0,9947, mas não são iguais. Maturidade e dependência digital são duplicatas exatas.

O VIF é um diagnóstico parcial das variáveis numéricas, em casos completos; não é inferência sobre planos, nem avaliação de todas as categorias do futuro modelo. O Teste Comum não foi usado para selecionar uma especificação por desempenho.

| variavel | decisao | evidencia_ou_hipotese | limite |
| --- | --- | --- | --- |
| grupo_atividade | MANTER PARA TESTAR | Representa atividades com diferentes necessidades; 10 categorias observadas | Categorias não possuem ordem numérica |
| funcionarios_estimados_empresa | MANTER PARA TESTAR | Hipótese relacionada à operação e RC empregador; dado completo | É da empresa inteira, não funcionários locais |
| quantidade_estabelecimentos_empresa | CONTROLE DE CONTEXTO | Permite contextualizar medidas corporativas repetidas em unidades | Contagem do pacote, não critério automático de upgrade |
| tipo_unidade | CONTROLE DE CONTEXTO | Matriz/filial; dado completo | Contribuição adicional só poderá ser medida com Y |
| estoque_medio_estimado | MANTER PARA TESTAR | Estoque do estabelecimento; dado completo e confere com fonte | Já é estimativa; não mede risco de roubo |
| valor_bens_ponderado_estabelecimento | MANTER PARA TESTAR | Agregação confere integralmente com valores ponderados dos bens | Não é importância segurada nem comprovação de localização |
| faturamento_mensal_empresa | ALTERNATIVA À VARIÁVEL FUNCIONÁRIOS | Correlação por empresa 0,9346; VIF exploratório em log 13,55 com demais medidas | Não descartar definitivamente; comparar modelo econômico com modelo de emprego |
| area_m2 | MODELO ALTERNATIVO | 61,72% ausente; avaliar modelo com e sem área | Imputador deve ser ajustado só no treino; ausência pode carregar viés |
| estoque_pico_estimado | ALTERNATIVA AO ESTOQUE MÉDIO | Correlação 0,9947, sem identidade de valores | Usar como alternativa, não os dois automaticamente |
| indice_maturidade_digital | EXCLUIR DUPLICATA | Idêntica a dependencia_digital_pct nos 2.500 registros de empresas | A exclusão é por duplicação, não por significância |
| dependencia_digital_pct e índices digitais | RESERVAR PARA HIPÓTESE ESPECÍFICA | Dados variam; não há Y para provar ou refutar contribuição | Avaliar se distinguem planos fixos ou apenas adicionais/assistências |
| cnae_principal / descricao_cnae | ALTERNATIVA À ATIVIDADE AGRUPADA | Representações de atividade; começar com 10 grupos facilita interpretação | Não repetir representações por padrão |
| porte | ALTERNATIVA À ESCALA CONTÍNUA | Categoria MICRO/PEQUENA, relacionada à dimensão econômica | Pode ser comparado depois; não empilhar todas as medidas de tamanho |
| folha / compras / energia / despesas fixas | RESERVAR | Disponíveis e variáveis; investigação de redundância consta no arquivo de correlações | Nenhuma conclusão de irrelevância estatística foi feita |
| padrao_construtivo_cadastrado | NÃO PRIORIZAR NO MODELO DE PLANOS | 81,83% NAO_DISPONIVEL | Pode apoiar confirmação do imóvel |
| material_parede_externa_cadastrado | AUXILIAR DE ELEGIBILIDADE | 84,76% NAO_DISPONIVEL | Ausência não significa material aceito |
| possui_termo_loja / possui_termo_galeria | CONDICIONAL | Flags do cadastro preservadas e conferidas | Não significam térreo ou vitrine comprovados |
| UF / município / coordenadas | RESERVAR ENRIQUECIMENTO | Localização não traz índices de roubo, alagamento ou vendaval | Não transformar código IBGE em grandeza numérica |

## Exemplos explícitos e conferidos

Valores monetários em reais. Área ausente aparece como “—”. O CSV de casos contém mais campos de qualidade e a quantidade de exemplos disponíveis em cada condição.

| caso | empresa_id | imovel_id | grupo_atividade | tipo_unidade | area_m2 | estoque_medio_estimado | valor_bens_ponderado_estabelecimento |
| --- | --- | --- | --- | --- | --- | --- | --- |
| atividade_BELEZA | EMP_00027 | IMO_EMP_00027_01 | BELEZA | MATRIZ | — | 62100 | 92100 |
| atividade_CLINICA | EMP_00010 | IMO_EMP_00010_01 | CLINICA | MATRIZ | — | 32650 | 144350 |
| atividade_ELETRONICOS | EMP_00015 | IMO_EMP_00015_01 | ELETRONICOS | MATRIZ | — | 3300 | 53850 |
| atividade_ESCOLA_CURSO | EMP_00005 | IMO_EMP_00005_01 | ESCOLA_CURSO | MATRIZ | 355.0 | 72750 | 95100 |
| atividade_ESCRITORIO | EMP_00032 | IMO_EMP_00032_01 | ESCRITORIO | MATRIZ | — | 2250 | 17950 |
| atividade_FARMACIA | EMP_00001 | IMO_EMP_00001_01 | FARMACIA | MATRIZ | — | 125900 | 318000 |
| atividade_MERCADO | EMP_00002 | IMO_EMP_00002_01 | MERCADO | MATRIZ | 395.0 | 138950 | 1525050 |
| atividade_OFICINA | EMP_00008 | IMO_EMP_00008_01 | OFICINA | MATRIZ | 175.0 | 15400 | 237200 |
| atividade_RESTAURANTE | EMP_00072 | IMO_EMP_00072_01 | RESTAURANTE | MATRIZ | — | 131200 | 77850 |
| atividade_VAREJO_MODA | EMP_00009 | IMO_EMP_00009_01 | VAREJO_MODA | MATRIZ | — | 24300 | 41150 |
| area_disponivel | EMP_00001 | IMO_EMP_00001_02 | FARMACIA | FILIAL | 250.0 | 63000 | 413750 |
| area_indisponivel | EMP_00001 | IMO_EMP_00001_01 | FARMACIA | MATRIZ | — | 125900 | 318000 |
| empresa_unica_unidade | EMP_00003 | IMO_EMP_00003_01 | FARMACIA | MATRIZ | — | 355000 | 511850 |
| empresa_varias_unidades | EMP_00001 | IMO_EMP_00001_01 | FARMACIA | MATRIZ | — | 125900 | 318000 |
| matriz | EMP_00001 | IMO_EMP_00001_01 | FARMACIA | MATRIZ | — | 125900 | 318000 |
| filial | EMP_00001 | IMO_EMP_00001_02 | FARMACIA | FILIAL | 250.0 | 63000 | 413750 |
| faturamento_informado | EMP_00001 | IMO_EMP_00001_01 | FARMACIA | MATRIZ | — | 125900 | 318000 |
| faturamento_presumido | EMP_00002 | IMO_EMP_00002_01 | MERCADO | MATRIZ | 395.0 | 138950 | 1525050 |
| algum_bem_baixa_confianca | EMP_00002 | IMO_EMP_00002_01 | MERCADO | MATRIZ | 395.0 | 138950 | 1525050 |
| nenhum_bem_baixa_confianca | EMP_00001 | IMO_EMP_00001_01 | FARMACIA | MATRIZ | — | 125900 | 318000 |
| imovel_em_obra | EMP_00009 | IMO_EMP_00009_01 | VAREJO_MODA | MATRIZ | — | 24300 | 41150 |
| imovel_irregular | EMP_00036 | IMO_EMP_00036_02 | MERCADO | FILIAL | 545.0 | 135600 | 318650 |
| endereco_incompativel | EMP_00002 | IMO_EMP_00002_01 | MERCADO | MATRIZ | 395.0 | 138950 | 1525050 |

## O que os testes comprovam e o que permanece aberto

Comprovam a preservação das chaves, valores corporativos sem rateio, contagens de unidades e bens, soma de bens por imóvel, estoque por estabelecimento, tratamento de áreas e flags, identidade das classes do catálogo e bloqueio de treinamento sem referências. O arquivo `testes_integridade.csv` identifica cada teste; `testes_execucao.txt` tem o log.

Não comprovam que as seis variáveis sugeridas sejam preditivamente melhores, que os planos recomendados sejam adequados ou que a hipótese ordinal se sustente. Também não validam a qualidade original dos dados sintéticos, apenas sua preparação e os diagnósticos apresentados. Não há “melhor modelo” medido nesta entrega.

## Modelagem preparada para receber referências

`src/treinar.py` compara três especificações de regressão logística ordinal usando cinco dobras por empresa dentro do treino. O critério predefinido é menor log loss, com erro ordinal como desempate. Somente a especificação selecionada acessa a avaliação reservada. Imputação e codificação são ajustadas no treino de cada dobra. Os coeficientes finais usam erros agrupados por empresa e seus valores-p são explicitamente exploratórios após seleção de especificação.

Quando houver rótulos suficientes, ainda serão necessários diagnóstico de chances proporcionais, calibração por plano, intervalos de desempenho e revisão independente da adequação das recomendações. O script não declara aprovação do produto apenas por uma métrica. Não foi ajustado um modelo com alvo artificial para alegar esses resultados.

O score proposto é `logistica(z)`, com limiares transformados da mesma maneira. A regra de classificação ordinal usa a mediana das classes; não é necessariamente a classe mais provável. A escala não representa probabilidade de compra. Os limites ainda não existem: dependem do ajuste e da validação.

## Próxima ação concreta

Preencher e revisar `dados/rotulos/rotulos_revisados.csv`, que já contém os 2.978 pares empresa-imóvel, com plano de referência, justificativa, revisor, fonte e versão do critério. Reservar a avaliação do desempenho para dados não usados na escolha de regras e modelos. A hipótese de negócio precisa ser revisada antes da rotulagem; ter as três categorias prontas não resolve essa associação.

Um diferencial defensável para a apresentação é a rastreabilidade: dados originais, regras de preparação, registro da qualidade e perguntas de confirmação, empresas separadas para avaliação e revisão humana registrada. O benefício comercial desse diferencial ainda precisa ser medido.
