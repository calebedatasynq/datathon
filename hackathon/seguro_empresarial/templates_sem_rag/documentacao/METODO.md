# Método de preenchimento dos templates

## Escopo e origem

Política `templates_mock_v1.0`, 28/10/2026. Os cabeçalhos, identificadores e ordem dos registros são os arquivos originais do desafio. As saídas são estimativas do protótipo sobre dados sintéticos. Não há consulta a empresas reais, enriquecimento geográfico, chamada de IA ou acesso à rede na execução.

O índice vem do ZIP `Entrega_Indice_Seguro_RAG_v2.zip` recebido em Documentos. Foram copiadas a função de inferência, os parâmetros e as referências numéricas, sem recalibrar pesos ou faixas. O índice sugere o plano segundo referências construídas pela equipe; não confirma elegibilidade nem define valores de coberturas.

## Fontes contratuais consultadas

- Guia local: `Guia_dos_times.pdf`, páginas 12 e 13 para elegibilidade, planos e adicionais; página 14 para avaliação.
- LEIA-ME e dicionário das bases originais: granularidade, campos exigidos, faixas e justificativa de exceções.
- Catálogo de coberturas fixas original de cada base: nomes e composição dos planos.
- Página oficial de planos: https://campanhas.bbseguros.com.br/seguro-empresarial/ (consulta 28/10/2026).
- Condições gerais/especiais v1.1: https://assets-bbsegurosportal.bbseguros.com.br/2024-08/cg-seguro-empresarial-v_1-1.pdf?VersionId=F5j.aDPjl.ePJzIhjV.z1Y1Nbm0byQ6M (consulta 28/10/2026).

Referências contratuais: construção/aceitação, páginas 11–12 e 18–19; despesas fixas, 61–62; aluguel, 78; vidros, 79–80; adicionais, seções próprias. A v1.1 prevê horizonte máximo de 180 dias para despesas fixas e 12 meses para aluguel, sujeitos às condições da apólice. **A aplicação desta versão e os limites comercializáveis ainda devem ser revisados na integração com o RAG.**

## Convenções de saída

CSVs em UTF-8 com BOM, separador vírgula, números com ponto decimal e textos delimitados por aspas quando necessário. Campos de listas usam ` | `. Identificadores não são alterados. Valores ausentes são vazios; não se usa zero como substituto. `dados_utilizados` contém JSON para preservar nomes e valores.

O dicionário permite convenções livres documentadas. Usamos `PENDENTE_VALIDACAO` em elegibilidade. Nenhum caso é aprovado automaticamente porque a base não confirma integralmente construção, telhado, funcionamento e condições de aceitação. O campo `motivo_inelegibilidade` explica a pendência quando não há inelegibilidade confirmada. Esse vocabulário precisa ser revisto se a organização fornecer validador com domínio fechado.

Sinais de obra, irregularidade, endereço não compatível, material combustível ou CNAE rural válido suspendem oferta. São pendências, não negativas automáticas de aceitação. Nesses casos não se emitem plano e coberturas no template; preservamos a indicação matemática em auditoria quando calculável. Uma obra pequena ou divergência cadastral pode ser resolvida por confirmação posterior.

Localização usa exclusivamente termos explícitos do endereço, incluindo múltiplos sinais quando existem. Aluguel recorrente positivo sugere inquilino, com confirmação; sua ausência não prova propriedade.

## Matriz de valores

Todas as regras abaixo são hipóteses de cenários da equipe. Os horizontes de 3 e 6 meses de despesas e de 6 e 12 de aluguel não foram aprendidos pela regressão. Os limites oficiais de contratação não foram inferidos ou inventados.

| Cobertura | Cálculo implementado | Limitação e próxima confirmação |
|---|---|---|
| Incêndio/raio/explosão/fumaça | Cenário mínimo = bens de conteúdo ponderados + estoque médio. Máximo = bens de conteúdo cadastrados integrais + estoque de pico. | Conteúdo parcial; falta prédio e inventário de reposição confirmado. |
| Danos elétricos | Soma ponderada versus soma cadastral dos tipos de equipamentos elétricos explicitamente mapeados. | Classificação preliminar; não usar energia mensal como valor dos bens. |
| Aluguel | Aluguel recorrente positivo × 6 a 12 meses. | Parcela de aluguel observada; faltam contrato, condomínio/IPTU e prazo real. Sem aluguel observado, fica pendente. |
| RC estabelecimento | Sem faixa nesta versão. | Faltam cenários de severidade, terceiros e limites comercializáveis. Faturamento não dimensiona indenização. |
| Despesas fixas | (Folha local + energia média local) × 3 a 6 meses. | Componentes parciais. Confirmar composição da folha, despesas que persistem e enquadramento. |
| Roubo/furto mediante arrombamento | Mesmos cenários de conteúdo usados em incêndio. | Exposição integral de cadastro, não probabilidade de perda; confirmar bens e categorias aceitos. |
| Vendaval e correlatos | Mesmos cenários de conteúdo usados em incêndio. | Não representa risco climático nem orçamento de telhado/prédio. É cenário parcial para conteúdo. |
| RC empregador | Sem faixa nesta versão. | Funcionários são da empresa inteira; faltam empregados locais, cenários e limites do produto. |
| Vidros | Sem faixa nesta versão. | Faltam itens, dimensões, material e orçamento de reposição/instalação. |
| Delivery (candidato) | Sem faixa nesta versão. | Participação da receita é empresarial; faltam confirmação local e valores por envio/acúmulo. |
| Mercadorias refrigeradas (candidato) | Sem faixa nesta versão. | Probabilidade de refrigeração ou equipamento não informa valor de mercadoria refrigerada. |
| Letreiros (candidato) | Soma ponderada versus soma cadastral dos bens LETREIRO. | Confirmar características, enquadramento e valor de reposição/instalação. |

Os bens usados como conteúdo são os tipos registrados em `politica.json`, separados de LETREIRO. Os limites são cenários cadastrais: a probabilidade de vínculo já está no valor ponderado da base, mas não constitui fração segurável nem intervalo probabilístico. **Nenhum dos extremos assegura proteção suficiente.** O cenário integral supõe vínculo de todos os bens listados ao endereço e não prova completude do cadastro. Não há fator inventado de reposição, custo por m² ou percentual de dano.

Para conteúdo, sem inventário de bens não se usa somente estoque como se fosse todo o conteúdo. Para danos elétricos, sem equipamentos identificados não se inventa uma proporção do patrimônio. Ambas as situações ficam como ausência excepcional de estimativa, com pergunta específica. Ausência de área não impede estimar conteúdo por inventário; a área não é imputada para calcular reconstrução.

Estoques médio/de pico são cenários alternativos, não valores a somar. Letreiros ficam separados do conteúdo genérico. As coberturas patrimoniais podem se referir aos mesmos bens: **não somar suas faixas como patrimônio total**. Na cobertura de despesas fixas, a referência agregada não é somada à folha, energia ou aluguel. Se o agregado for inferior a folha+energia, registramos a inconsistência.

## Adicionais e assistências

Delivery é candidato se a empresa tem participação de receita delivery positiva, mas exige confirmação local. Mercadorias refrigeradas são candidatas quando há equipamento de refrigeração associado ou indicador de referência >=0,6. Esse corte é hipótese configurável para priorizar pergunta, não probabilidade de sinistro ou quantidade de estoque. Letreiros são candidatos quando existe bem desse tipo. Adicionais não são confirmados automaticamente.

Home office, valores em espécie, RC garagista, sprinklers, bens ao ar livre, recomposição de documentos e proteção cibernética ficam para avaliação posterior: não há dados suficientes de aplicabilidade e condições específicas nesta etapa. Não se recomenda cyber por exposição digital. A assistência Proteção Digital não é registrada como cobertura.

## Confiança e perguntas

A confiança geral e das faixas é BAIXA nesta versão por critérios explícitos: aceitação não confirmada, vínculo patrimonial probabilístico, inventário parcial, hipóteses de duração e/ou dados monetários faltantes. Não há justificativa para confiança alta sobre o resultado completo, mesmo com cadastro pontual de boa qualidade. A confiança cadastral de um bem permanece em sua fonte e não calibra automaticamente a confiança do plano.

As perguntas de elegibilidade vêm primeiro, seguidas de interesse segurado, lacunas do índice e perguntas por cobertura. São deduplicadas. O RAG poderá agrupar e priorizar a redação na jornada, mantendo as pendências estruturadas na auditoria.

## Testes e rastreabilidade

`testar.py` verifica regras com exemplos numéricos independentes, chaves e ordem, composição dos planos, suspensão por impedimentos e dados essenciais ausentes. Confere cada faixa emitida com as fontes originais e reproduz os 3.122 scores/planos da referência anterior. `saidas/fontes_sha256.json` identifica as fontes utilizadas; `auditoria.json` preserva score, indicação original, restrições, contribuições e pendências.

Os testes comprovam execução e coerência das regras propostas. Não comprovam adequação comercial, valor de reposição real, cobertura de todos os riscos ou contratação aceita. A integração com o RAG e a demonstração completa foram deixadas para a próxima etapa.
