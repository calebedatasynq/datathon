# Agente de vendas do Seguro Empresarial (MVP do datathon)

## Objetivo
Um agente que faz uma pergunta em vez de vinte e nunca promete o que a apólice não cobre.

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

## Comandos
- Instalar: `.venv/Scripts/python -m pip install -r requirements.txt`
- Testes: `.venv/Scripts/python -m pytest`
