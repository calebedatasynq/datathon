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
- Sem chave do Jev, o Decisor usa ClaudeDecisor (Haiku com tool use e enum).

## Comandos
- Instalar: `.venv/Scripts/python -m pip install -r requirements.txt`
- Testes: `.venv/Scripts/python -m pytest`
