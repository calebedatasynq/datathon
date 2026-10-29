# BB Radar — Seguro Empresarial

Equipe: **preencher nome da equipe, integrantes e instituição/turma antes da entrega**. Desafio: Seguro Empresarial.

O MVP usa dados sintéticos de empresa e estabelecimento para sugerir proteção. A regressão logística ordinal v2 produz um índice de 0 a 1 e um plano inicial; regras determinísticas de necessidades podem elevar o pacote para incluir coberturas essenciais. O agente pergunta, recupera cláusulas por RAG, explica a oferta e registra a trilha. Elegibilidade pendente impede concluir contratação como aprovada.

## Executar

Python 3.x. Código analítico e testes locais verificados com Python 3.12; a equipe descreve Python 3.13 para sua demonstração. Instale `requirements.txt` em um ambiente virtual, execute `python app.py` para a interface e acesse `http://127.0.0.1:8000`. Para respostas ao vivo, configure `ANTHROPIC_API_KEY` ou `CLAUDE_KEY` em `.env` local. `JEV_API_KEY` é opcional; sem ele, o decisor usa Claude. Nunca versionar `.env`. Sem chaves, os testes determinísticos e a exportação dos templates funcionam; a conversa com LLM não foi validada nesta revisão.

```bash
python -m pip install -r requirements.txt
python scripts/exportar_templates.py --ambas-bases
python scripts/auditar_entrega.py
python -m pytest -q testes/test_guia_final.py testes/test_personalizacao.py testes/test_perfil.py testes/test_regras.py testes/test_descoberta.py
python app.py
```

## Arquivos e arquitetura

- `Entrega_Indice_Seguro_RAG_v2/seguro_score_rag/`: motor e dados preparados. Variáveis, pesos, cortes e origem dos rótulos estão na documentação do motor e em `hackathon/documentacao_geral/`.
- `Seguro_Empresarial_Desenvolvimento/` e `Seguro_Empresarial_Teste_Comum/`: bases e templates originais. O teste comum é a entrega obrigatória; desenvolvimento é suplemento.
- `agente/`: perfil, decisor, regras, personalização, RAG, redator e conferência. O LLM não escolhe o plano nem calcula faixas. A conversa sem cadastro usa referências construídas na base de desenvolvimento.
- `interface/` e `web/`: demonstração e API. `dados/fixtures/`: personas e riscos pré-calculados. `docs/fontes_territoriais.md`: fontes, método e limitações do enriquecimento.
- `saidas/ambas_bases/{teste_comum,desenvolvimento}/`: dois CSVs preenchidos por base e `trilha_recomendacoes.json` com score, plano do motor, plano final e alternativas.
- `saidas/ambas_bases/metricas_guia_final.json`: auditoria estrutural reproduzível.

## Premissas e resultados medidos

Os rótulos de referência foram construídos pela equipe sobre dados sintéticos, com critérios documentados de coberturas. O índice aprende a reproduzir esses critérios; não mede chance de compra nem prova que o plano seja o mais adequado em clientes reais. O score é a sugestão inicial. A decisão final do MVP também considera necessidades cobertas pelo pacote e elegibilidade.

Em 29/10/2026, a exportação e a auditoria local encontraram **144/144** casos de teste e **2.978/2.978** de desenvolvimento processados. Os testes comuns têm **1.350** linhas de coberturas, **138** sugestões condicionais e **6** recomendações suspensas por restrições explícitas. Todas as 138 sugestões incluem coberturas fixas e Proteção Cibernética; **64** planos finais diferem do plano inicial da regressão por regras de necessidade. A auditoria encontrou zero divergências estruturais nos itens verificados. No desenvolvimento, são **28.519** linhas de coberturas, **2.900** sugestões condicionais, **78** suspensas e **1.094** planos finais diferentes do motor.

Todas as sugestões do teste têm elegibilidade **A_CONFIRMAR**: faltam confirmações de atividade, local, situação legal e duplicidade de seguro BB. Isso limita a interpretação comercial da exportação. A Proteção Cibernética usa R$ 20 mil–40 mil como intervalo público entre planos, com confiança baixa e limite específico a confirmar; não é cotação nem limite contratado. O limite de R$ 7,5 milhões da cobertura básica gera encaminhamento ao Seguro Personalizado Empresarial quando ultrapassado. Dados externos de risco territorial têm granularidade e limitações documentadas em `docs/fontes_territoriais.md`.

As métricas estruturais não medem conversão, qualidade de resposta do LLM nem adequação atuarial. Contratação real depende de confirmação, cotação e integrações do Banco. A interface de demonstração e o fluxo de aceite devem ser identificados como simulados quando não houver emissão real verificada. Os testes que chamam provedores externos dependem de credenciais e rede e não entraram na validação local desta revisão.

## Uso de IA e responsabilidade

Ferramentas de IA apoiaram a análise, a programação, a documentação e a redação. A equipe precisa revisar o código e defender critérios, resultados e limites. Dados usados na recomendação devem ter origem autorizada; o agente mantém trilha de fontes e encaminha casos incertos. Não usar atributos pessoais sensíveis como atalho para risco.

Antes da entrega, preencher a identificação da equipe, anexar vídeo de até cinco minutos e verificar a demonstração ao vivo. Os critérios e o prazo estão no Guia dos Times final. Consulte também `INTEGRACAO_INDICE.md`.
