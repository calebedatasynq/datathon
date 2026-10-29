# Próxima etapa: RAG e confirmações

## Depende do RAG pronto ou ficará mais completo com ele

1. Revisar por cobertura a versão contratual aplicável, enquadramentos, exclusões, franquias, períodos e limites disponíveis, com citação de documento e trecho. As referências atuais foram consultadas manualmente, não recuperadas pelo RAG.
2. Revisar adicionais candidatos por atividade e operação efetiva. Resolver sobreposições e evitar confundir assistência com cobertura.
3. Acrescentar explicações contratuais contextualizadas às justificativas e perguntas existentes, sem alterar fórmulas ou números silenciosamente.
4. Agrupar e priorizar perguntas para a jornada One Click Buy/assistida/agente, preservando todos os pontos em aberto.
5. Testar o fluxo integrado: perfil -> ferramenta de índice -> triagem e faixas -> recuperação de condições -> confirmação -> resultado.
6. Gerar nova versão dos templates após essa revisão. Preservar a versão preliminar e comparar mudanças por empresa/estabelecimento/cobertura, com origem e motivo.

O RAG deve consumir os valores do programa, não recalcular o score por texto. O plano do índice e o plano eventualmente revisado após necessidades devem continuar distinguíveis em auditoria. Alterações devem trazer documento, evidência do cliente ou política versionada.

## Exige confirmação humana ou dado novo; o RAG sozinho não resolve

| Informação faltante | Efeito |
|---|---|
| Operação efetiva, construção completa, telhado, obras, regularidade e impedimentos | Confirmar elegibilidade e resolver ofertas suspensas. |
| Relação com imóvel e interesse em prédio/conteúdo | Definir escopo de proteção. Ausência de aluguel não prova propriedade. |
| Área confiável e custo local de reconstrução | Dimensionar prédio; não usar custo por m² inventado. |
| Inventário e valores atuais de reposição, vínculo dos bens e separação de estoque | Completar faixas patrimoniais e corrigir subdimensionamento. |
| Aluguel alternativo, contrato, condomínio/IPTU e tempo de recuperação | Completar aluguel e despesas. |
| Atividades, fluxo de terceiros, empregados locais e cenários de danos | Dimensionar responsabilidade civil com limites disponíveis do produto. |
| Quantidade, material e orçamento de vidros e instalação | Dimensionar vidros. |
| Mercadorias refrigeradas e valor máximo simultâneo | Dimensionar deterioração; equipamento não representa mercadoria. |
| Operação local de delivery e valores por envio/acúmulo | Confirmar e dimensionar adicional de delivery. |

Não substituir essas lacunas por afirmações da LLM. Uma passagem contratual explica condições, mas não comprova a condição física da empresa mock.

## Contrato sugerido para integração posterior

Entradas já disponíveis: `saidas/<base>/auditoria.json`, os dois CSVs e `pendencias_por_cobertura.json`. Identificar sempre `empresa_id` + `imovel_id` e, nas faixas, `cobertura`.

Anotações futuras devem preservar: campo alterado, valor anterior, novo valor, tipo de evidência (`DOCUMENTO_CONTRATUAL` ou `CONFIRMACAO_CLIENTE`), fonte/trecho, data e responsável. Não foi implementado consumo automático dessas respostas nesta etapa, porque a estrutura final depende da integração do RAG.

Casos mínimos de demonstração: cadastro completo com indicação condicional; obra/endereço divergente com oferta suspensa; parede/telhado desconhecido; sem aluguel; equipamento ausente; falta de dado essencial do índice; adicionais candidatos; RC/vidros sem valor e confirmação posterior.
