# Coberturas, dados e próximo treino

Pesquisa em 28/10/2026. Escopo: novas vendas. Sem contato com especialistas, conforme informado pela equipe.

## Evidência oficial

[Página comercial BB Seguros](https://campanhas.bbseguros.com.br/seguro-empresarial/): Essencial reúne incêndio/raio/explosão/fumaça, danos elétricos, aluguel, RC estabelecimento e despesas fixas. Prático acrescenta roubo/furto de bens mediante arrombamento e eventos de vendaval. Total acrescenta RC empregador e quebra de vidros. Existem adicionais conforme atividade, inclusive delivery e mercadorias refrigeradas. Assistências são outro componente; não equivalem às coberturas.

[Condições gerais e especiais, versão 1.1](https://assets-bbsegurosportal.bbseguros.com.br/2024-08/cg-seguro-empresarial-v_1-1.pdf?VersionId=F5j.aDPjl.ePJzIhjV.z1Y1Nbm0byQ6M), processo 15414.604242/2022-04: cláusula 6 (páginas 11–12) descreve estabelecimentos abrangidos e construção; cláusula 9 (página 17) remete franquias/POS à apólice; cláusula 13 (páginas 18–19) condiciona aceitação à análise do risco. Coberturas possuem condições específicas e exclusões. A versão foi localizada em fonte oficial; sua aplicabilidade a uma contratação futura precisa ser confirmada.

Nenhuma dessas evidências estabelece os cortes de um score, pesos estatísticos ou uma regra de faturamento que atribua os três planos. A ordem de abrangência não prova a hipótese de chances proporcionais da regressão ordinal.

## O que podemos fazer automaticamente

| Informação disponível | Uso defensável | Informação que falta |
|---|---|---|
| Atividade econômica | Contextualizar perguntas e consultar cláusulas | Operação efetiva no endereço |
| Estoque e bens ponderados | Discutir patrimônio e necessidade de proteção | Valores atuais, vínculo e necessidade de cobertura confirmados |
| Funcionários estimados da empresa | Sinalizar pergunta sobre empregados | Quantidade no estabelecimento e necessidade de RC empregador |
| Faturamento estimado | Contexto econômico; candidato a teste futuro | Orçamento, preço e resposta de referência |
| Área e material cadastrado | Identificar lacunas de elegibilidade | Construção completa, telhado e dados atualizados |
| Termos loja/galeria | Preparar pergunta sobre vidros | Existência, dimensões e interesse na cobertura |
| Município | Contexto geográfico | Evidência de exposição local; não presumir risco pelo nome |

Eu preparo cruzamentos, casos e documentação. A equipe não precisa preencher manualmente o que a base já informa. Necessidades ausentes não podem ser descobertas por regressão: no produto, o agente pergunta ao cliente e registra a resposta e a data. Uma resposta sobre interesse em cobertura não equivale a análise de aceitação pela seguradora.

## Sem especialista disponível

Podemos apresentar um protótipo de correspondência entre necessidades declaradas e coberturas do catálogo. Escolher o menor pacote que as contenha é uma política proposta pela equipe, não regra oficial de adequação. Preço, adicionais e exclusões podem alterar a escolha. Casos incompletos devem gerar perguntas, não rótulos automáticos.

Treinar uma regressão para copiar essa política é possível depois de registrar respostas, mas sua avaliação mede concordância com a política. Não mede adequação independente, conversão ou satisfação. Para avaliar vendas, será necessário coletar ofertas, escolhas e resultados de clientes; compra e adequação são alvos diferentes.

## Execução desta etapa

O script `teste_tecnico_regressao.py` treina a implementação ordinal em uma simulação matemática separada, com alvo artificial explicitamente conhecido. Compara informação relevante, informação incompleta e variável sem sinal. Usa treino e teste separados, verifica probabilidades e cortes. Não atribui planos às empresas da base, não publica score de cliente e não altera `rotulos_revisados.csv`.

Esse teste comprova funcionamento técnico no cenário simulado. Não confirma variáveis significativas do seguro empresarial. Os resultados ficam em `resultados/teste_tecnico.json` e no notebook de demonstração. O modelo de negócio continua sem referência supervisionada.
