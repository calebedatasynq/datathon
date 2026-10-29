# Resultado da etapa sem RAG

Execução de 28/10/2026. Templates preliminares; integração e revisão final pelo RAG adiadas conforme o escopo.

| Medida | Desenvolvimento | Teste Comum |
|---|---:|---:|
| Estabelecimentos | 2978 | 144 |
| Empresas | 2500 | 120 |
| Linhas de coberturas | 16470 | 776 |
| Faixas numéricas preliminares | 10335 | 477 |
| Ausências de faixa justificadas | 6135 | 299 |

## Indicações e elegibilidade

No Teste Comum: 57 Essencial, 25 Prático e 24 Total, todos condicionais. Outros 38 estabelecimentos têm oferta suspensa por sinal cadastral. A indicação matemática original permanece em auditoria. Nenhum foi classificado automaticamente como inelegível.

Os 144 registros permanecem PENDENTE_VALIDACAO quanto à aceitação, pois faltam confirmações completas do estabelecimento. Isso não impede simular a indicação nos 106 casos sem restrição cadastral explícita.

Motivos de suspensão no Teste Comum (podem coexistir):

- Endereço divergente/sem confirmação: 33.
- Situação cadastral EM_OBRA: 6.
- Situação cadastral IRREGULAR: 1.

## Faixas que ficaram pendentes no Teste Comum

| Cobertura | Linhas sem faixa |
|---|---:|
| DANOS_ELETRICOS | 9 |
| RESPONSABILIDADE_CIVIL_ESTABELECIMENTO | 106 |
| RESPONSABILIDADE_CIVIL_EMPREGADOR | 24 |
| QUEBRA_DE_VIDROS | 24 |
| DELIVERY | 57 |
| DETERIORACAO_MERCADORIAS_FRIGORIFICADAS | 38 |
| PERDA_PAGAMENTO_ALUGUEL | 41 |

299 linhas de cobertura estão sem faixa numérica, todas com justificativa, dados utilizados e pergunta. Essas lacunas são materialmente relevantes: o preenchimento ainda não cumpre a etapa de dimensionamento completo. Responsabilidade civil, vidros, delivery e mercadorias refrigeradas exigem dados ou cenários não disponíveis; aluguel sem pagamento observado exige esclarecer a relação e custo alternativo; danos elétricos exige inventário identificado.

## O que foi validado

- Cabeçalhos originais e ordem das 2.978/144 linhas de resultado.
- Identificadores únicos, junções sem perda/duplicação e cobertura fixa completa nos planos emitidos.
- Consistência exata da lista de coberturas entre os dois arquivos.
- Faixas finitas, não negativas e ordenadas, sem transformar ausência em zero.
- Cada valor numérico confrontado com as fontes por cálculo independente.
- Reprodução dos 3.122 scores e indicações do índice original, sem retreinamento.
- Casos de ausência de dado essencial, cadastro divergente, obra, valores inválidos, sem aluguel/equipamentos e inconsistência financeira.

Os testes não validam comercialmente as faixas nem aprovam aceitação do risco. As fontes e seu hash estão em `saidas/fontes_sha256.json`. Os testes podem ser repetidos com `python testar.py`.

## O que foi deixado para depois

A lista está em `PENDENCIAS_POS_RAG.md`: revisão contratual contextualizada e citada, adicionais, jornada de perguntas e teste integrado. As confirmações físicas/operacionais do cliente também estão separadas; não serão preenchidas apenas pelo RAG.
