# Ajustes ao roteiro de arquitetura após atualização do repositório

Documento de trabalho: conferir a versão final do pitch com a equipe antes de gravar.

O roteiro em `pitch_arquitetura.md` descreve corretamente a cascata decisor → regras → RAG → redação → verificação. Após o pull, o MVP também contém conversa sem cadastro, personalização por cobertura e enriquecimento territorial opcional. O foco permanece no agente autônomo; o índice e o RAG alimentam decisões e explicações.

Trocar afirmações absolutas por evidências observáveis:

- “O RAG garante que nada sem cláusula seja dito” é forte demais. Há recuperação, exigência de citação e verificação, mas a qualidade semântica das respostas do LLM depende de avaliação específica.
- “Uma pergunta em vez de vinte” vale para a pergunta contrafactual do score; a cotação/contratação exige outras confirmações. Na base comum há média de 8,47 pendências registradas por caso após a revisão de elegibilidade, não 1.
- “Contratação concluída pelo agente” só deve ser dito se o fluxo de aceite, cotação e resultado de contratação forem demonstrados na versão integrada; indicar explicitamente quando o ambiente é simulado.
- Os 586 testes citados no roteiro referem-se a estado anterior do código. A revisão atual passou 521 testes locais selecionados antes dos últimos ajustes e sua auditoria CSV foi executada; informar a contagem final após rodar a suíte pertinente.
- “RAG acertou 29/30” é um resultado relatado no roteiro, não refeito nesta revisão. Mostrar método, conjunto e execução se essa métrica entrar no vídeo.

Números verificáveis da entrega em `saidas/ambas_bases/metricas_guia_final.json`: 144/144 casos comuns processados; 138 sugestões condicionais, 6 suspensas; 138/138 sugestões com coberturas fixas e Proteção Cibernética; 64 planos finais diferentes do plano inicial do motor. Essas diferenças explicam o diferencial: o score dá uma hipótese interpretável, as regras verificam necessidades essenciais e o agente pede confirmação antes da venda.

Na demonstração, usar um caso concreto e mostrar: entrada → score/plano inicial → necessidade que elevou ou manteve o plano → elegibilidade/pendências → cláusula citada → alternativa → próximo passo. A apresentação deve dizer claramente que os rótulos da regressão foram construídos sobre dados sintéticos; não existe rótulo real de “plano ideal”.
