# Contrato da ferramenta score_empresa — interface 1.0, modelo ordinal_mock_v2

## Entrada: uma linha por estabelecimento

| Campo | Tipo / unidade | Escala |
|---|---|---|
| empresa_id | texto não vazio | identificador da empresa |
| imovel_id | texto não vazio | identificador do estabelecimento |
| funcionarios_estimados_empresa | número não negativo | empregados da empresa inteira |
| estoque_medio_estimado | número não negativo, reais | estabelecimento |
| valor_bens_ponderado_estabelecimento | número não negativo, reais | soma ponderada dos bens do estabelecimento |
| faturamento_mensal_empresa | número não negativo, reais/mês | empresa inteira |
| quantidade_estabelecimentos_empresa | número não negativo | quantidade de endereços cadastrados na base |
| area_m2 | número não negativo ou null, m² | área do estabelecimento |
| grupo_atividade | categoria | uma das categorias em modelo/formula_completa.json |
| tipo_unidade | FILIAL ou MATRIZ | estabelecimento |

Enviar números JSON, com ponto decimal e sem “R$” nem separador de milhar. No CSV, texto numérico é convertido. Campo vazio ou null representa ausência; zero é valor observado, não ausência. Valores negativos, não finitos, booleanos e textos inválidos são rejeitados. O esquema JSON descreve a entrada completa desejada; a função também trata entradas incompletas devolvendo confirmação ou imputação documentada.

A preparação já foi feita em `dados/preparados`. Contagens não devem ser confundidas com total nacional da empresa; faturamento e empregados não são rateados por endereço. O valor dos bens já incorpora ponderação da base e não equivale a importância segurada contratada.

## Saída

- `versao_modelo`, `versao_interface`, `empresa_id`, `imovel_id`: rastreabilidade.
- `status`: EXPERIMENTAL_BASE_MOCK ou PRECISA_CONFIRMACAO.
- `score`: índice de 0 a 1; null quando a interface suspende indicação.
- `plano_sugerido`: ESSENCIAL, PRATICO, TOTAL ou null.
- `cortes`: limites próprios do modelo, sem arredondamento. Decisão final já vem pronta.
- `probabilidades_referencia`: probabilidades dos rótulos construídos, não probabilidades de compra. Null quando pendente.
- `contribuicoes`: termos e parcelas de z. Podem ser positivas ou negativas; somam z, não o score. Categorias são contrastes com categoria-base.
- `campos_ausentes`, `categorias_desconhecidas`, `avisos`: qualidade de entrada, não “confiança estatística”.
- `perguntas_confirmacao`: perguntas a levar ao gestor/cliente.
- `distancia_ao_corte_mais_proximo`: distância numérica, quando calculado. Não é intervalo de confiança. Não definimos um limiar arbitrário de proximidade.
- `elegibilidade`: NAO_AVALIADA.
- `fontes`, `limites`: procedência e restrições de interpretação.

## Uso pelo agente

1. Consultar o cadastro/preparação e chamar a ferramenta.
2. Se PRECISA_CONFIRMACAO, perguntar os campos indicados; não inventar um score ou recomendar um plano usando null como zero.
3. Se houver avisos, explicá-los e confirmar informações. Valores fora do treino são extrapolação; não ocultar o aviso.
4. Com score válido, explicar a indicação como apoio experimental. Consultar as coberturas no RAG e citar a fonte do produto.
5. Não converter contribuição positiva em afirmação de sinistro provável ou causalidade.
6. Não gerar preço, franquia ou aprovação de risco a partir do score.

Nenhum contato externo nem envio de dados é realizado pelo código. Não há autenticação ou servidor web, porque este módulo é uma função local a ser incorporada ao agente.

## Casos para demonstração integrada

- Empresa completa: score e plano devem coincidir com o exemplo.
- Área ausente: cálculo com imputação e aviso.
- Funcionários, estoque ou bens ausentes: pedir confirmação, sem plano.
- Categoria desconhecida: pedir confirmação, sem plano.
- Número negativo ou texto inválido: tratar erro de entrada, não pedir à LLM para consertar silenciosamente.
- Valor muito alto: explicitar extrapolação, sem prometer confiabilidade.
- Lote com estabelecimento repetido: rejeitar duplicação.
- Score perto de limite: mostrar informação sem arredondar para decidir; confirmar necessidades antes de uma conclusão comercial.
