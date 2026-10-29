# Base do Seguro Empresarial

## Uso do pacote
Os arquivos fornecem sinais para que a equipe verifique elegibilidade, recomende um plano por combinação empresa-estabelecimento e detalhe as faixas das coberturas aplicáveis.

## Granularidade
`empresas.csv` contém informações no nível da empresa. `enderecos_estabelecimentos.csv`, `sinais_financeiros_operacionais.csv` e `territorio.csv` estão no nível da empresa e do estabelecimento. `bens_cadastrados.csv` contém bens associados probabilisticamente a um estabelecimento de referência. Ao comparar faturamento com despesas, estoque e folha, considere essa diferença de granularidade e empresas com mais de uma unidade.

## Natureza dos dados
Todos os clientes, empresas, estabelecimentos, bens, transações e endereços são fictícios. Município, UF, código IBGE e CNAEs utilizados são referências reais; os registros não representam empresas ou endereços reais.

## Relações econômicas e operacionais
Faturamento, folha, despesas, compras de fornecedores, estoque, energia e aluguel apresentam relações plausíveis com porte, atividade, área e características operacionais, preservando dispersão e incerteza. Os indicadores de refrigeração, delivery e exposição digital são referências recalculáveis. Exposição digital não representa probabilidade de ataque, vulnerabilidade técnica ou risco cibernético residual.

## Template de resultado
Em `template_resultado_times.csv`, preencha uma linha por empresa-estabelecimento, incluindo elegibilidade, plano recomendado, justificativa, confiança e perguntas de confirmação.

## Template de coberturas
O arquivo `template_coberturas_times.csv` contém apenas o cabeçalho. Para cada empresa-estabelecimento, registre todas as coberturas fixas do plano recomendado e eventuais coberturas adicionais aplicáveis. Para cada cobertura dimensionável, informe faixa mínima e máxima em reais, confiança, dados utilizados, regra de cálculo, justificativa e informações a confirmar. Confiança baixa não dispensa uma faixa quando houver base minimamente defensável. A ausência de estimativa deve ser excepcional e justificada.

O arquivo `catalogo_coberturas_fixas_planos.csv` apresenta a nomenclatura para conferência da entrega. Assistências acompanham o plano e não são registradas como coberturas.

## Território e fontes externas
A base não fornece índices de alagamento, vendaval ou furto. Enriquecimento externo é opcional e deve documentar fonte, data, granularidade, metodologia e limitações.

## Liberdade analítica
A base não impõe categorias de risco nem uma única metodologia. Features derivadas podem ser recalculadas, substituídas ou ignoradas, desde que a decisão seja explicada. Não é obrigatório usar machine learning.

## Métricas
Use métricas adequadas à abordagem, como casos processados, recomendações explicadas, perguntas de confirmação, baixa confiança, estabilidade, elegibilidade, completude, tempo, consistência, sensibilidade das faixas, falhas e reprodutibilidade.

## Tecnologias, IA e dados externos
Python não é obrigatório. Quando usado, documente versão e dependências. Outras tecnologias podem ser utilizadas se forem permitidas, demonstráveis e documentadas. O uso de IA deve ser declarado, e a equipe deve compreender e defender a solução. Dados externos devem ser públicos ou autorizados.

## Recomendações desejáveis
- diferenciar informação disponível, sugestão e confirmação;
- reduzir e priorizar perguntas;
- demonstrar empresas e estabelecimentos contrastantes;
- tratar casos com área ausente, bens de baixa confiança ou inconsistência financeira;
- permitir uso em One Click Buy, atendimento assistido e agentes autônomos;
- documentar testes de coerência e tratamento de valores extremos.
