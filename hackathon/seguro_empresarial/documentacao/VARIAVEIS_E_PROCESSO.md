# Etapa 1 — Variáveis para a regressão logística ordinal

Data: 28/10/2026. Versão: 1.0.

## O que foi feito

Foi criada uma base com uma linha por empresa-estabelecimento, preparada para receber o plano de referência e, depois, treinar a regressão logística ordinal. A proposta do documento IPU foi descartada. Não foram usados seu alvo monetário, regressão OLS, rateio de funcionários, regras de pontos ou cortes de planos.

Esta etapa seleciona **candidatas por significado de negócio e qualidade dos dados**. Ainda não estabelece significância estatística, importância preditiva ou peso de nenhuma variável. Não há plano de referência preenchido nas bases fornecidas.

As oito candidatas abaixo são um conjunto inicial para discussão e avaliação. Não há compromisso de colocar todas juntas no modelo final. A ordem das classes será ESSENCIAL < PRÁTICO < TOTAL; a adequação da hipótese ordinal será avaliada depois da rotulagem.

## 1. Unidade de análise e alvo

- Uma linha: um estabelecimento de uma empresa, identificado por `empresa_id` e `imovel_id`.
- Y: `plano_recomendado`, a ser preenchido com ESSENCIAL, PRATICO ou TOTAL mediante critérios documentados e revisão.
- `elegivel`: campo de avaliação de elegibilidade, preservado do template e ainda vazio. Um caso pendente ou inelegível não deve receber automaticamente ESSENCIAL.
- `empresa_id`: também é o grupo para separar treino/validação, pois filiais da mesma empresa não são observações completamente independentes.
- Os campos de IDs, alvo, elegibilidade e qualidade não entram automaticamente no conjunto de preditores.

## 2. Oito variáveis candidatas iniciais

| Variável na base preparada | O que significa e de onde vem | Por que avaliar | Cuidado / preparação posterior |
|---|---|---|---|
| `grupo_atividade` | Ramo da empresa; `empresas.grupo_atividade` | Diferentes operações têm bens, atividades e necessidades de cobertura distintas | É categoria, sem ordem numérica. Usar indicadores com referência; não repetir CNAE e descrição do CNAE no mesmo conjunto inicial |
| `faturamento_mensal_empresa` | Receita mensal em reais da empresa inteira; `empresas.faturamento_mensal` | Contextualiza escala econômica e capacidade operacional | Não é receita do estabelecimento. Pode ser presumida; manter origem/confiança. Avaliar log e redundância com funcionários apenas no treino |
| `funcionarios_estimados_empresa` | Número estimado de funcionários da empresa inteira; `empresas.quantidade_funcionarios_estimada` | Hipótese ligada à dimensão da operação e às necessidades de responsabilidade civil do empregador | Não representa a quantidade na filial. Não rateamos nem criamos um número por imóvel. Confirmar quantidade local para decisões específicas |
| `quantidade_estabelecimentos_empresa` | Contagem de imóveis cadastrados por empresa em `enderecos_estabelecimentos` | Ajuda a interpretar informações corporativas repetidas em mais de uma unidade | É número de unidades no pacote, não prova de todas as unidades reais. Variável de contexto, não gatilho automático para plano superior |
| `tipo_unidade` | MATRIZ ou FILIAL; `enderecos_estabelecimentos.tipo_unidade` | Permite avaliar diferenças entre tipos de unidade controlando os demais fatores | Não significa que matriz sempre precisa de maior proteção. Avaliar contribuição adicional à contagem de unidades |
| `area_m2` | Área cadastrada do imóvel em m²; `enderecos_estabelecimentos.area_cadastrada_m2` | Contexto da dimensão física e da exposição patrimonial | Zero, vazio ou origem NAO_DISPONIVEL tornam-se ausentes. Não substituir por zero. Considerar exclusão ou imputação com indicador de ausência após dividir treino/validação |
| `estoque_medio_estimado` | Valor estimado do estoque médio em reais do estabelecimento; tabela de sinais | Hipótese sobre importância das mercadorias e necessidade de proteção patrimonial/roubo | Estoque alto não comprova risco de roubo ou necessidade de PRÁTICO. É estimativa. Não incluir pico simultaneamente sem avaliar redundância |
| `valor_bens_ponderado_estabelecimento` | Soma de `bens_cadastrados.valor_bem_ponderado_referencia` por empresa e imóvel de referência | Resume bens associados ao estabelecimento, preservando a ponderação fornecida na base | Não é valor comprovado no local, de reposição ou importância segurada. Não soma estoque; considera todos os tipos de bens e não estima probabilidade de sinistro |

**Por que não estabelecer regras de plano agora:** o catálogo descreve coberturas, mas não prova que “receita maior = plano maior” ou que determinado valor patrimonial determina uma categoria. Alguns destes campos podem ser mais úteis para dimensionar coberturas do que para escolher o plano. A decisão de mantê-los dependerá de critérios de negócio, rótulos independentes, evidência multivariada e validação.

## 3. Duas variáveis condicionais

Também preservamos `possui_termo_loja` e `possui_termo_galeria`, convertendo SIM para 1 e NAO para 0. São indícios textuais do cadastro e entram como candidatas condicionais, fora da lista principal.

Esses termos **não comprovam** localização no térreo, existência de vitrine ou área de vidros. A relação com quebra de vidros precisaria de confirmação. Se houver interesse nesse aspecto, a informação preferível será a existência e característica de vidros expostos, hoje não fornecida diretamente no pacote.

## 4. Campos auxiliares mantidos

| Campo | Finalidade |
|---|---|
| `empresa_id`, `imovel_id` | Vincular registros e controlar grupos; nunca usar como números explicativos |
| `origem_faturamento`, `confianca_faturamento` | Mostrar como foi obtida a receita e avaliar robustez em subgrupos; confiança cadastral não equivale a probabilidade do modelo |
| `origem_area`, `confianca_area`, `area_ausente` | Rastrear qualidade e ausência da área; `area_ausente=1` quando não utilizável |
| `quantidade_bens_cadastrados` | Conferir a agregação de bens; quantidade de registros não é necessariamente quantidade física de itens |
| `proporcao_bens_baixa_confianca` | Fração dos registros de bens cujo vínculo é BAIXA; número entre 0 e 1, sem ponderação monetária |
| `bens_sem_cadastro` | Distinguir ausência de cadastro de valor igual a zero; nesses casos o valor agregado permanece ausente |
| `endereco_cnpj_compativel` | Apoiar conferência cadastral |
| `situacao_imovel_cadastral` | Apoiar revisão de elegibilidade e informações pendentes |
| `material_parede_externa_cadastrado` | Apoiar revisão de elegibilidade; NAO_DISPONIVEL permanece uma informação desconhecida |
| `elegivel` | Saída futura da revisão de elegibilidade; não é preditor do plano |
| `plano_recomendado` | Alvo futuro; preservado do template e atualmente vazio |

A base final tem 25 colunas: 2 chaves, 8 candidatas iniciais, 2 condicionais, 11 auxiliares de qualidade/contexto e 2 saídas (elegibilidade e plano). A quantidade de coeficientes futuros poderá ser maior que o número de variáveis, porque categorias geram indicadores.

## 5. O que ficou fora da primeira especificação

- **Cliente, endereço completo, CEP e códigos de identificação:** não têm interpretação útil automática como medidas numéricas. Evitar memorizar registros sintéticos.
- **UF, município e coordenadas:** localização não é um índice de roubo ou vendaval. O pacote não fornece esses riscos territoriais. Eventual enriquecimento exige fonte e granularidade adequadas.
- **CNAE/descrição e porte:** a atividade já foi representada por grupo; porte deve ser avaliado como alternativa às medidas de escala, não adicionado automaticamente junto delas.
- **Índices digitais:** podem ajudar na recomendação de adicionais ou assistências, mas não estabelecemos ainda hipótese suficiente para discriminar os três planos fixos. Isso não significa “sem efeito estatístico”.
- **Estoque de pico:** fortemente relacionado ao estoque médio e com significado distinto. Poderá substituir o médio em uma comparação futura; não é considerado idêntico.
- **Folha, compras, energia, aluguel e despesas fixas:** permanecem nas fontes para análises futuras. O conjunto inicial reduz redundância e complexidade; exclusão inicial não é conclusão de irrelevância.
- **Regras do IPU:** não foram incorporadas; não há inferência de térreo/vitrine, piso ou rateio de funcionários, limite de 8 funcionários ou cortes monetários de plano.

## 6. Como os dados foram preparados

1. Leitura dos arquivos originais, registrando caminho, número de linhas e hash SHA-256 para rastreabilidade.
2. Conferência de chaves únicas, referências de empresas/imóveis, domínios e valores negativos incompatíveis com as medidas selecionadas.
3. Contagem das unidades de cada empresa, sem ratear receita ou funcionários.
4. Agregação dos bens antes de juntá-los aos estabelecimentos, evitando multiplicar linhas, estoque e faturamento.
5. Junção da empresa (muitos estabelecimentos para uma empresa), dos sinais, dos bens agregados e do template (uma linha por estabelecimento).
6. Conversão de áreas indisponíveis para ausência e dos dois indicadores textuais para 0/1.
7. Preservação dos campos de plano e elegibilidade, sem gerar rótulos automaticamente.
8. Gravação separada de Desenvolvimento e Teste Comum. Nenhum modelo, imputador, padronizador, encoder aprendido ou limite de score foi ajustado.

## 7. Resultado desta execução

| Medida | Desenvolvimento | Teste Comum |
|---|---:|---:|
| Empresas | 2.500 | 120 |
| Estabelecimentos na base preparada | 2.978 | 144 |
| Colunas | 25 | 25 |
| Planos preenchidos | 0 | 0 |
| Área ausente | 1.838 (61,7%) | 87 (60,4%) |

Na base de Desenvolvimento, faturamento e funcionários da empresa têm correlação de Pearson de **0,9352** quando representados nas linhas dos estabelecimentos. Isso pede avaliação de redundância e estabilidade dos coeficientes, sem concluir automaticamente pela retirada de uma das variáveis. A análise por empresa única também deverá ser considerada; as empresas com duas unidades aparecem duas vezes na tabela de modelagem.

O Teste Comum foi preparado com as mesmas regras determinísticas. Suas estatísticas servem para inventário e conferência de preparação, não para escolher variáveis, cortes ou hiperparâmetros. Sem rótulos, não permite medir acerto de plano.

## 8. Próximas etapas, na ordem

1. **Revisar as hipóteses de negócio:** relacionar candidatos às necessidades realmente contempladas pelos planos. Identificar perguntas de confirmação: funcionários locais, características dos vidros, bens no local e demais lacunas relevantes.
2. **Definir o protocolo de rotulagem:** plano de referência, justificativa, revisor, fonte do critério e tratamento de pendências. Não atribuir planos apenas por quantis das candidatas ou por regras inventadas para facilitar o ajuste.
3. **Rotular e revisar um piloto:** buscar diversidade de atividade, porte e qualidade da informação. Rótulo de especialista é uma referência operacional e deve ter sua procedência registrada.
4. **Separar empresas e preparar o treino:** divisão agrupada; imputação, padronização e codificação estimadas apenas no conjunto de treino. Verificar contagem por classe antes de definir a complexidade.
5. **Ajustar e comparar modelos ordinais:** avaliar hipóteses, colinearidade, estabilidade, efeitos, intervalos de confiança e desempenho fora da amostra. Inferência deve considerar unidades da mesma empresa.
6. **Definir a apresentação do score e validar cortes:** somente após rótulos e ajuste. Documentar a diferença entre pontos de corte estatísticos e decisão comercial.

## 9. Como explicar esta etapa na apresentação

“Definimos cada estabelecimento como unidade de análise. Selecionamos oito variáveis candidatas a partir de seu significado de negócio, mantendo separados os dados de qualidade e elegibilidade. Agregamos os bens por imóvel e preservamos faturamento e funcionários no nível da empresa. Registramos ausências e redundâncias. A importância estatística será avaliada depois que os planos de referência forem rotulados e o modelo for validado em empresas separadas.”

## 10. Arquivos e reprodução

- `modelagem/preparar_base.py`: preparação reproduzível.
- `modelagem/variaveis.json`: lista oficial das candidatas e ordem pretendida do alvo.
- `modelagem/requirements.txt`: dependência usada nesta etapa.
- `dados/preparados/base_desenvolvimento.csv`: base para exploração e futura rotulagem/modelagem.
- `dados/preparados/base_teste_comum.csv`: mesma estrutura aplicada ao conjunto comum.
- `dados/preparados/relatorio_preparacao.json`: contagens, hashes, ambiente e verificações.

Comando, a partir da pasta do projeto, após instalar a dependência em ambiente Python próprio:

```bash
python modelagem/preparar_base.py --origem /home/lucas/Downloads/Seguro_Empresarial_DadosSinteticos
```

A execução recria apenas os arquivos preparados em `dados/preparados`. Os dados originais não são modificados. Para futuras anotações, usar arquivo de rótulos separado e versionado, com as chaves empresa/imóvel, para não perder o trabalho ao executar novamente a preparação.

Fontes: tabelas originais e dicionário do pacote Seguro Empresarial; catálogo de coberturas fixas e guia do datathon para contextualização de negócio. Os critérios de seleção aqui descritos são hipóteses iniciais da equipe de modelagem, não regras oficiais de enquadramento do BB.
