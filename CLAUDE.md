# Agente de vendas do Seguro Empresarial (MVP do datathon)

## Objetivo
Um agente que faz uma pergunta em vez de vinte e nunca promete o que a apólice não cobre.
ESSENCIAL, PRATICO e TOTAL são os planos vigentes da BB Seguros; o agente monta o plano cobertura
por cobertura (necessidade + faixa de limite), e o pacote BB mais próximo diz como contratar
(pacote + adicionais). Dois modos: cliente da base (cadastro) e conversa do zero (sem cadastro).

## Arquitetura (cascata)
1. Decisor (Jev ou plano B) classifica a mensagem e extrai confirmações, com probabilidade.
2. regras.py aplica a confirmação e recalcula o plano (determinístico, nunca LLM).
3. rag.py recupera cláusulas filtradas por segmento e plano.
4. redator.py (Claude Haiku) escreve a resposta citando cláusulas no formato [cl. X].
5. guardrail.py confere; reprovado duas vezes vai para o humano.

## Regras
- Python 3.13 (venv em .venv), tipagem e modelos pydantic em agente/contratos.py.
- Nenhuma conta ou regra de plano feita por LLM.
- Toda afirmação de cobertura precisa de cláusula recuperada.
- Nunca usar dado sensível nem processo judicial do cliente.
- Chaves só em .env; nunca no código.
- Cada função nova vem com teste em testes/.
- Modelo do LLM lido de MODELO_LLM no .env (padrão: claude-haiku-5-5; o plano original previa Sonnet, a equipe escolheu Haiku).
- Jev: POST https://api.typesafe.ai/v1/systemone, model jev-latest, chave JEV_API_KEY; tipos de pergunta choice, score e noul (ver testes/test_conexoes.py).
- Sem chave do Jev, o Decisor usa ClaudeDecisor (Haiku com tool use e enum).

## Perfil (camada A)
- Score e plano vêm só de score_empresa em Entrega_Indice_Seguro_RAG_v2/seguro_score_rag/score.py (não alterar o pacote).
- Planos: ESSENCIAL, PRATICO, TOTAL. cliente_id = imovel_id da base_teste_comum.csv.
- Pergunta pendente: contrafactual em score_empresa (estoque, bens, funcionários); no máximo uma, se o corte estiver a até MARGEM_PERGUNTA (0,30) do valor estimado.
- Personas em dados/fixtures/personas.json (gerar com scripts/selecionar_personas.py).

## Base de conhecimento e RAG (camada B)
- Fonte: Condições Gerais oficiais v1.1 em dados/cg/ → scripts/extrair_cg.py → conhecimento/clausulas.jsonl (887 chunks).
- O id do chunk é a citação: [cl. CG-8.2.a], [cl. ROUBO_FURTO_ARROMBAMENTO-3.1.c], [cl. TT-FURTO_SIMPLES], [cl. PLANO-TOTAL].
- Planos de cada cláusula vêm do catálogo do desafio (Seguro_Empresarial_Teste_Comum/catalogo_coberturas_fixas_planos.csv), nunca do PDF.
- Coberturas adicionais fora dos planos ficam com planos=[] e no_catalogo=false.
- Busca híbrida: BM25 + Chroma (multilingual-e5-small) por RRF; filtro rígido de segmento; plano só etiqueta (no_plano).
- Glossário curado de expansão de consulta em agente/rag.py (EXPANSOES). Avaliação: dados/fixtures/perguntas_rag.json; não calibrar com o conjunto "validacao".
- Depois de mudar clausulas.jsonl ou o modelo: python scripts/indexar_rag.py (senão a busca cai para BM25 com aviso).
- Fatos plano↔cobertura: rag.coberturas_do_plano / rag.planos_com_cobertura (catálogo), não a busca.

## Camada de decisão (Fase 3)
- agente/decisor.py: interface Decisor (escolher, pontuar, probabilidade, avaliar em lote); JevDecisor (TypeSafe /v1/systemone: choice, score, noul), ClaudeDecisor (Haiku, tool forçada com enum), DecisorComReserva (Jev → Claude se falhar). criar_decisor() escolhe.
- Perguntas do turno: intencao, confirmacao (sim / nao / nao_sabe / nao_respondeu, comparando com pergunta_pendente.limite), prontidao (score), rota (agente / gerente).
- Gerente (regra fixa em motivo_para_humano): rota gerente, nao_sabe, ou sim/não abaixo de LIMIAR_CONFIANCA. Só sim/não acima do limiar vão para regras.py (confirmacao_aplicavel).
- Avaliação: python scripts/avaliar_decisor.py (20 respostas em dados/fixtures/respostas_confirmacao.json).

## Regras, enriquecimento e redação (Fase 4)
- regras.py: aplica sim/não na entrada do motor (sim → no mínimo o limiar; não → logo abaixo) e chama score_empresa de novo. Depois de 1 confirmação não há nova pergunta (MAX_PERGUNTAS em perfil.py).
- enriquecimento.py: CNPJ pela BrasilAPI com cache em dados/fixtures/cnpj_cache.json; CNAE → segmento pelo Decisor (com opção OUTRO).
- redator.py: Haiku com regras de redação no SISTEMA; cita [cl. ID] só da lista recebida; variável confirmada não aparece como número (na entrada ela vale o limiar). rag.buscar_para_turno sempre inclui o resumo PLANO-<plano>.
- Ver respostas: python scripts/rodar_personas.py

## Guardrail, log e pipeline (Fase 5)
- pipeline.Conversa(cliente_id).turno(mensagem): decidir → regras → recuperar → redigir → conferir → registrar. Guarda perfil (com confirmações) e histórico entre turnos.
- guardrail.py: determinístico (citação fora das recuperadas ou resposta sem citação) + Decisor (promete sem cláusula, informa preço, dado sensível; reprova com p ≥ LIMIAR_CONFIANCA). Reprovou: reescreve uma vez; de novo: MENSAGEM_GERENTE e requer_humano.
- Objeção: identificar_objecao (Decisor) junta as cláusulas da objeção às recuperadas.
- log.py: logs/turnos.jsonl com estado completo, versões, tempos por etapa e tokens (base do modo de reprodução).

## Plano personalizado (decisões da equipe, out/2026)
- agente/personalizacao.py (sem LLM), cobertura por cobertura: necessidade(cobertura) → ESSENCIAL / RECOMENDADA / OPCIONAL / NAO_SE_APLICA com motivo, a partir das variáveis do estabelecimento.
- Pacote de contratação = menor pacote do catálogo CSV que contém todas as essenciais, nunca abaixo do índice do motor (PlanoPersonalizado.plano_base; plano_motor e pacote_minimo ficam registrados). Fora do pacote: essencial/recomendada com faixa ≥ MINIMO_RELEVANTE_ADICIONAL vira "adicional"; o resto, "opcional".
- est_com_entrada aplica ao estabelecimento os valores da entrada do motor (inclui confirmações); sem isso a confirmação não mudava as necessidades.
- perfil_relevante: a pergunta do motor só é feita se o sim e o não levam a planos personalizados diferentes (13 de 23 casos).
- Premissas de dimensionamento são constantes no topo do módulo; onde a CG fixa período/limite, a regra segue a cláusula (aluguel ≤ 12 meses, despesas fixas ≤ 180 dias, valores = dia + dia útil anterior).
- Inconsistência financeira (aluguel > 50% ou despesa fixa > faturamento do endereço) baixa a confiança e vira confirmação.
- Elegibilidade: SIM ou A_CONFIRMAR pelas cl. CG-6 e CG-7.1 (nunca NAO automático).
- Dados finos do estabelecimento: agente/dados_base.py (CSVs de Seguro_Empresarial_Teste_Comum).
- Entrega do desafio: python scripts/exportar_templates.py → saidas/template_resultado_times.csv e template_coberturas_times.csv.
- Cibernético: os planos incluem a Ampla Proteção Cibernética (site e comunicado BB Seguros, mar/2026); fonte curada SITE-CIBERNETICA em conhecimento/fontes_produto.jsonl; detalhes com o gerente; não negar citando CG-8.2.a (CG v1.1 é anterior).
- Preço: o agente nunca informa preço (decisão da equipe); limite de indenização não é preço.
- Redator: Haiku com output_config effort "low" e max_tokens 8000 (o raciocínio do Haiku conta no max_tokens e já cortou respostas); resposta cortada é reprovada pelo guardrail.

## Conversa do zero (agente/descoberta.py)
- Cliente sem cadastro: abre perguntando se quer informar o CNPJ (BrasilAPI → CNAE → ramo pelo Jev); sem CNPJ, pergunta o ramo.
- Perguntas com faixas (botões) e texto livre (Jev escolhe a faixa; botão não passa pelo Jev). Antes de cada pergunta, testa todas as respostas no motor + personalização (_assinatura: pacote, coberturas que entram e ordem de grandeza do limite de incêndio) e pula a que não muda nada. Típico: 3 a 8 perguntas, mediana 5 (MAX_PERGUNTAS = 8).
- O que não foi perguntado vem da mediana do ramo na base de DESENVOLVIMENTO (dados_base.perfil_segmento), nunca da de teste.
- Cliente virtual: estabelecimento_virtual + perfil_de_entrada; motivos sem números (faixas ou medianas não viram fatos), imóvel "A_CONFIRMAR" se não perguntado.
- Ao terminar, vira uma Conversa normal (Conversa aceita perfil/estabelecimento injetados) com apresentar_recomendacao=True; o redator recebe respostas_do_cliente e valores_estimados vazio.

## Interface (Fase 6)
- python app.py → http://127.0.0.1:8000. Backend FastAPI em interface/servidor.py; página estática em web/ (index.html, estilo.css, app.js), sem build.
- Conversa ao vivo: POST /api/conversas/{id}/mensagens devolve SSE com cada etapa (Conversa.turno(ao_progredir=...)) e o turno final; a página mostra as etapas como o "pensando" do Claude.
- Conversa do zero: POST /api/descobertas; mesma rota de mensagens; turnos trazem opcoes (botões) e descoberta (o que o agente sabe, puladas).
- Reprodução: /api/gravacoes lê logs/turnos.jsonl (inclui as etapas) e reexibe a conversa no ritmo gravado, sem API.
- Visual: skill .agents/skills/design-taste-frontend (app screen, estilo framed-sheet): moldura tingida do azul BB, amarelo BB só no plano recomendado, tinta azul-marinho Ibmec, IBM Plex Sans (+ Plex Mono só nos ids). Checar com lint.mjs --app web e inspect.mjs --app http://127.0.0.1:8000/.
- Redator com thinking desligado (Haiku pensava ~1.600 tokens, 13 s); 12/12 turnos aprovados na 1ª tentativa.

## Comandos
- Instalar: `.venv/Scripts/python -m pip install -r requirements.txt`
- Testes: `.venv/Scripts/python -m pytest`
