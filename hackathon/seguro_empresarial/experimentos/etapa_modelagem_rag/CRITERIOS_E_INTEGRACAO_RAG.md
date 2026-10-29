# Classificação de referência e integração com o agente de novas vendas

Data: 28/10/2026. Estado: proposta para revisão; não é regra oficial de enquadramento do BB.

## O que queremos prever

Plano de referência adequado às necessidades de coberturas fixas confirmadas do estabelecimento: ESSENCIAL, PRATICO ou TOTAL. O alvo não é o plano atualmente contratado nem a aceitação de uma oferta. Uma venda efetiva requer cotação, condições de contratação e decisão do cliente.

## Critério proposto para classificar a primeira amostra

Usar como referência o **menor nível do catálogo que contemple as coberturas fixas consideradas necessárias na revisão do caso**. Esse é um critério de cobertura; não demonstra a melhor escolha econômica, porque não dispomos de prêmio/preço ou orçamento do cliente.

O catálogo do desafio contém:

| Nível | Coberturas que acrescenta |
|---|---|
| ESSENCIAL | Incêndio/raio/explosão/fumaça; danos elétricos; perda/pagamento de aluguel; RC estabelecimento; despesas fixas |
| PRATICO | As anteriores + roubo/furto mediante arrombamento e vendaval/eventos correlatos |
| TOTAL | As anteriores + RC empregador e quebra de vidros |

Fonte: `dados/originais/Seguro_Empresarial_Desenvolvimento/catalogo_coberturas_fixas_planos.csv`. Limites, exclusões, franquias e aceitação precisam ser recuperados da documentação vigente do produto; a lista de nomes não os define.

### Perguntas que sustentam a referência

Registrar SIM, NAO ou NAO_CONFIRMADO para necessidade de roubo/furto, vendaval, RC empregador e quebra de vidros. Cada resposta precisa de justificativa e origem. Há diferença entre uma característica do cliente e uma necessidade de cobertura confirmada.

- Estoque/bens elevados não provam risco de roubo e não criam automaticamente um plano PRATICO.
- Funcionários da empresa não são a contagem de funcionários do endereço; sua presença não é um limite oficial de enquadramento em TOTAL.
- Termos loja/galeria no cadastro não comprovam vitrine ou vidro exposto.
- Município não representa automaticamente risco de vendaval.
- Informação desconhecida permanece NAO_CONFIRMADO, sem conversão automática em NAO.

### Correspondência entre necessidades confirmadas e nível mínimo

1. Caso que exige revisão de elegibilidade permanece pendente antes de qualquer indicação comercial definitiva.
2. Havendo necessidade confirmada de RC empregador ou quebra de vidros, o menor nível que contém essas coberturas fixas no catálogo é TOTAL.
3. Sem essas necessidades, havendo necessidade confirmada de roubo/furto ou vendaval, o menor nível correspondente é PRATICO.
4. Quando as necessidades adicionais foram avaliadas e não identificadas, o nível de referência pode ser ESSENCIAL.
5. Se uma resposta desconhecida ainda puder mudar a classificação, registrar pendência e a pergunta que resolveria a decisão.

Essa correspondência não autoriza inferir respostas a partir de limites monetários inventados. O revisor pode apontar que os dados não permitem decidir. A adequação final da recomendação requer revisão de negócio; não classificar automaticamente todos os clientes com funcionários como TOTAL.

## Piloto de 150 casos

- Dez casos de desenvolvimento e cinco de avaliação por grupo de atividade: 100 + 50 casos, dez atividades.
- Seleção reproduzível, com no máximo um estabelecimento por empresa no piloto.
- Casos selecionados respeitam a partição de empresas já registrada. As classes de plano ainda não são conhecidas; não é garantido equilíbrio entre os planos.
- Os arquivos da dupla não mostram a indicação de plano de outro revisor. Recomenda-se revisar independentemente e conciliar divergências.
- Não alterar critérios usando os resultados da avaliação reservada. Se isso acontecer, é preciso definir nova avaliação independente antes de alegar desempenho.
- O piloto não garante volume suficiente para a regressão. É necessário conferir distribuição de classes, número de parâmetros e incerteza após a revisão.

O arquivo geral `dados/rotulos/rotulos_revisados.csv` continua sendo a fonte do modelo principal. Só devem entrar nele referências revisadas, com procedência, justificativa e versão. Rótulos provisórios produzidos por regras/IA precisam de arquivo e resultados separados.

## Como alimentar o modelo conceitual do RAG

O agente consulta uma ferramenta de perfil estruturado. A ferramenta entrega valores do cliente e, quando houver modelo adequado para uso, o score. O conteúdo documental permanece no RAG de conhecimento.

Contrato proposto:

- `cliente`: IDs de empresa e estabelecimento; data de referência dos dados.
- `status`: AGUARDANDO_REFERENCIA, EXPERIMENTAL ou VALIDADO_PARA_USO_DEFINIDO.
- `score`: valor 0–1, versão do modelo, significado e cortes da mesma versão. Ausente quando ainda não estimado.
- `plano_sugerido`: categoria e regra de decisão utilizada. Não preencher como fato quando não houver inferência aprovada.
- `probabilidades_por_plano`: saída do modelo, se existente; não confundir com probabilidade de compra.
- `motivos`: características que contribuíram, com fonte do dado. Associações estatísticas não são causas.
- `qualidade_dados`: campos ausentes, estimados e sua procedência. Separar qualidade cadastral de incerteza estatística.
- `perguntas_confirmacao`: dúvidas que podem alterar elegibilidade ou recomendação, ordenadas por relevância.
- `faixas_monetarias`: cálculo separado de dimensionamento, com método e fontes; não derivar automaticamente do score ordinal.
- `fontes_produto`: documentos/cláusulas recuperados pelo RAG para explicar as coberturas.
- `limitacoes`: escopo da validação e limites do caso.

### Uso pelo agente

1. Identificar o estabelecimento e conferir a atualidade dos dados.
2. Consultar o perfil e as pendências.
3. Fazer perguntas capazes de alterar a decisão; atualizar o perfil com a origem da confirmação.
4. Consultar o modelo aprovado e recuperar documentos pertinentes ao plano e às necessidades.
5. Explicar a recomendação com dados do cliente e citações documentais.
6. Encaminhar para cotação ou revisão humana conforme o caso.

O agente não deve transformar EXPERIMENTAL em “plano ideal comprovado”, completar scores ausentes ou inventar cláusulas/faixas em reais. Consultas externas seguem o caminho C do desenho: finalidade, permissão e procedência independentes do cálculo do score.

## Etapas 2, 3 e 4

Depois das referências, comparar regressões ordinais nas especificações já preparadas, com empresas separadas e transformações ajustadas no treino. Medir erros por plano, log loss, calibração e estabilidade; verificar chances proporcionais. Os pesos e os cortes do score dependerão desse ajuste.

Se a opção for executar antes com rótulos provisórios, o experimento deve declarar que mede reprodução dos critérios propostos. Não apresentá-lo como validação de adequação real dos planos nem juntar esses rótulos aos revisados.
