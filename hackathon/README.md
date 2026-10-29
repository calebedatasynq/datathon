# Hackathon - seguro empresarial

Pastas para a equipe:

- `resultados/`: métricas, pesos, scores, gráficos e painel da regressão v2.
- `documentacao_geral/`: resumo do projeto, guia de apresentação e explicações.
- `scripts_testes/`: código da regressão e testes/exportação do RAG. A exportação do RAG deve ser executada no checkout do repositório, onde estão as bases e módulos `agente/`.
- `templates/`: quatro arquivos originais e quatro preenchidos, separados em `desenvolvimento/` e `teste_comum/`. Consulte `CONFERENCIA.json`.

A pasta `seguro_empresarial/` continua como projeto histórico completo para preservar os notebooks, dados e caminhos já usados; os arquivos organizados acima são uma seleção para entrega. O checkout do RAG foi trabalhado na branch `feat/integracao-indice-regressao`.

Os dois templates de coberturas originais são byte a byte idênticos e contêm apenas o cabeçalho. Os templates de resultado têm o mesmo cabeçalho, mas 2.978 e 144 estabelecimentos diferentes. Os quatro arquivos preenchidos foram gerados pelo exportador do RAG, com o mesmo motor ordinal v2. Sua interpretação é experimental, conforme a documentação.

Após a revisão do Guia final: 28.519 linhas de coberturas no desenvolvimento e 1.350 no teste comum. `resultados/metricas_guia_final.json` registra a auditoria, inclusive as recomendações suspensas e os planos finais alterados pelas regras. Sugestões condicionais precisam de confirmação antes da contratação.
