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

## Comandos
- Instalar: `.venv/Scripts/python -m pip install -r requirements.txt`
- Testes: `.venv/Scripts/python -m pytest`
