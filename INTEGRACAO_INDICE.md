# Integração do índice de regressão com o agente de vendas

## Fluxo

O agente já usa `score_empresa` de `Entrega_Indice_Seguro_RAG_v2/seguro_score_rag/score.py`. A camada `agente/perfil.py` transforma os dados preparados do estabelecimento em score de 0 a 1, plano sugerido, cortes e pergunta de confirmação. A camada `agente/regras.py` recalcula o mesmo score após uma resposta confirmada. A personalização acrescenta coberturas e faixas de limite ao plano base. O RAG recupera cláusulas para explicar a oferta; ele não calcula o score.

O índice usa pesos da regressão ordinal v2 ajustada sobre rótulos construídos por critérios do projeto. Portanto, o resultado mede a reprodução desses critérios nos dados sintéticos; não comprova qual plano é ideal em vendas reais. O score tampouco é probabilidade de contratação. Consulte a documentação do motor no pacote entregue para variáveis, coeficientes, cortes, testes e limitações.

## As duas bases e seus quatro templates

`Seguro_Empresarial_Desenvolvimento` e `Seguro_Empresarial_Teste_Comum` têm os mesmos cabeçalhos de template, mas conjuntos distintos de estabelecimentos: 2.978 e 144, sem sobreposição de pares `(empresa_id, imovel_id)`. Cada pasta contém um template de resultado e outro de coberturas. Os dois templates originais de coberturas são idênticos e só têm cabeçalho; os de resultado têm registros diferentes. Por isso os quatro originais são mantidos separados.

Para gerar os quatro arquivos preenchidos, a partir da raiz do repositório:

```bash
python scripts/exportar_templates.py --ambas-bases
```

As saídas ficam em `saidas/ambas_bases/desenvolvimento/` e `saidas/ambas_bases/teste_comum/`. A opção sem argumento preserva a exportação anterior da base de teste em `saidas/`. O exportador usa o mesmo `score_empresa` e a mesma personalização determinística nas duas bases, preservando os cabeçalhos de cada template. Não depende de chave de LLM para gerar esses arquivos.

## Conferência executada

| Base | Resultados | Coberturas |
| --- | ---: | ---: |
| Desenvolvimento | 2.978 | 24.356 |
| Teste comum | 144 | 1.165 |

Foram conferidos cabeçalhos, ordem e identificação dos estabelecimentos, além da associação das coberturas aos estabelecimentos exportados. A suíte pertinente de perfil, personalização, regras e exportação passou com **458 testes**. Isso verifica o comportamento implementado e a consistência dos arquivos sintéticos, não a eficácia comercial ou a adequação atuarial do plano.
