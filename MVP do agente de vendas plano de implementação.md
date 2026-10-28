# MVP do agente de vendas: plano de implementação

Oct 28, 2026 
## Objetivo do MVP

O MVP prova uma frase: **um agente que faz uma pergunta em vez de vinte e nunca promete o que a apólice não cobre.** Tudo o que não ajuda a provar essa frase fica fora do MVP.

O que precisa funcionar ao vivo na demo:

1. O cliente escreve uma resposta livre e o Jev a transforma em dado ("estoque + portáteis > R$ 40 mil? sim, 92%").
2. O código atualiza o plano recomendado com essa confirmação.
3. O  responde com o plano, o risco em reais e a cláusula citada.
4. Um caso de baixa confiança vai para o gerente.

Critérios de sucesso:

| Critério | Meta |
| --- | --- |
| Personas que rodam ponta a ponta sem erro | 3 de 3 (ALTO, FRONTEIRA, BAIXO) |
| Respostas sobre cobertura com cláusula citada e correta | ≥ 90% do conjunto de teste |
| Pedidos fora da cobertura recusados corretamente | 100% do conjunto de teste |
| Confirmações extraídas corretamente pela camada de decisão | ≥ 90% de 20 respostas de teste |
| Perguntas até a recomendação | 0 a 1 em 144 casos (já medido: 84 sem pergunta, 60 com uma) |

Fica fora do MVP: BB Radar, INR, HIBP real, JusBrasil, clima e crime por município. Eles aparecem no pitch como próxima fase.

## Arquitetura

Cada turno passa por uma cascata: o Jev decide, o código calcula, o Sonnet só escreve e o Jev confere antes de a resposta sair.

&#91;embedded content: arquitetura em cascata · um turno da conversa\]

O plano nunca é decidido por LLM: a confirmação extraída pelo Jev entra na mesma regra do motor original. Na demo, o pipeline é fixo, sem o LLM escolher ferramentas sozinho, porque uma ordem previsível não trava ao vivo.

## Stack e pré-requisitos

A stack é toda Python, com o mínimo de dependências para a demo não quebrar.

| Peça | Escolha | Por quê |
| --- | --- | --- |
| Linguagem | Python 3.13 | Mesma versão do motor atual |
| LLM que escreve | Claude Sonnet via SDK `anthropic` | Redige a resposta com citação. Confirmem o nome exato do modelo em docs.claude.com (a versão mais recente é `claude-sonnet-5-5`) |
| Camada de decisão | Jev (TypeSafe) via OpenRouter ou API da TypeSafe | Classificação rápida com probabilidade |
| Plano B da decisão | Claude Haiku com tool use e `enum` | Mesma interface, caso o Jev não esteja acessível |
| Busca no RAG | BM25 (`rank-bm25`) + filtro por metadados | Corpus pequeno (centenas de cláusulas), sem servidor, sem baixar modelo |
| Busca vetorial (opcional) | Chroma + embeddings multilíngues locais | Só se sobrar tempo; o BM25 com filtro já resolve o MVP |
| Extração das CG | `pypdf` ou `pdfplumber` | PDFs das Condições Gerais em texto |
| CNPJ | BrasilAPI (consulta pública) + cache local | Dado aberto da Receita; a base é sintética, então a demo usa um CNPJ público real e fixtures |
| Interface | Streamlit | Chat + painel lateral "caixa de vidro" em poucas linhas |
| Validação de dados | `pydantic` | Contratos entre as camadas |
| Testes | `pytest` | Testes de cada fase e avaliação final |

Pré-requisitos para resolver hoje:

- [ ] Chave da API da Anthropic com crédito, em `.env` (`ANTHROPIC_API_KEY`)
- [ ] Chave do OpenRouter ou acesso antecipado da TypeSafe (`JEV_API_KEY`), testada com uma chamada
- [ ] PDFs das Condições Gerais do Empresarial e do Proteção Cibernética na pasta `dados/cg/`
- [ ] Saídas do score (`recomendacoes_canais.jsonl` e arquivos do IPU) copiadas para `dados/score/`
- [ ] Claude Code instalado e um repositório Git criado
- [ ] Confirmar no edital se o uso de APIs externas na demo é permitido

## Estrutura do repositório

Cada camada da arquitetura é um módulo com contrato próprio, para que o Claude Code trabalhe numa peça por vez e os testes isolem falhas.

```
bb-agente/
├── CLAUDE.md                 # regras do projeto para o Claude Code
├── .env.example              # ANTHROPIC_API_KEY, JEV_API_KEY, MODELO_LLM
├── requirements.txt
├── dados/
│   ├── cg/                   # PDFs das Condições Gerais
│   ├── score/                # saídas do motor e do IPU
│   └── fixtures/             # CNPJ em cache, personas, respostas de teste
├── conhecimento/
│   ├── clausulas.jsonl       # chunks das CG com metadados
│   ├── especiais_segmento.jsonl
│   └── objecoes.jsonl        # objeções e respostas curadas
├── agente/
│   ├── contratos.py          # modelos pydantic entre as camadas
│   ├── perfil.py             # A) get_perfil_cliente
│   ├── rag.py                # B) indexação e busca com filtro
│   ├── enriquecimento.py     # C) CNPJ e CNAE → segmento
│   ├── decisor.py            # interface Decisor + JevDecisor + ClaudeDecisor
│   ├── regras.py             # aplica a confirmação e recalcula o plano
│   ├── redator.py            # prompt do Sonnet e montagem da resposta
│   ├── guardrail.py          # checagem de citação + Jev confere
│   ├── log.py                # registro de cada turno em JSONL
│   └── pipeline.py           # um turno ponta a ponta
├── scripts/
│   ├── extrair_cg.py         # PDF → clausulas.jsonl
│   └── avaliar.py            # roda o conjunto de teste e gera o relatório
├── app.py                    # interface Streamlit
└── testes/
```

O contrato que liga tudo é o estado do turno. Cada camada lê e escreve campos dele:

| Campo | Quem escreve | Exemplo |
| --- | --- | --- |
| `cliente_id`, `mensagem` | interface | `"EST_0042"`, `"tenho uns 50 mil em mercadoria"` |
| `perfil` | perfil.py | segmento, plano provável, IPU, faixas, perguntas pendentes |
| `decisoes` | decisor.py | intenção, confirmação extraída, prontidão, rota, cada uma com probabilidade |
| `perfil_atualizado` | regras.py | plano recalculado e próxima pergunta |
| `clausulas` | rag.py | ids e textos recuperados |
| `resposta` | redator.py | texto com citações |
| `guardrail` | guardrail.py | aprovado ou motivo da reprovação |
| `requer_humano` | decisor.py ou guardrail.py | verdadeiro quando a confiança fica abaixo do limiar |

## Fases de implementação

São sete fases em ordem de dependência. Cada uma termina com um teste que passa; só depois a próxima começa.

### Fase 0 · Base do projeto

1. Criar o repositório, o `CLAUDE.md`, o `requirements.txt` e o `.env.example`.
2. Escrever `contratos.py` com os modelos pydantic do estado do turno (tabela acima).
3. Fazer uma chamada de teste ao Sonnet e uma ao Jev (ou ao plano B).

Pronto quando: `pytest testes/test_conexoes.py` passa com as duas chamadas.

### Fase 1 · Perfil do cliente (camada A)

1. Ler as saídas do score e do IPU e juntar por id do estabelecimento.
2. Expor `get_perfil_cliente(id) -> Perfil` com segmento, plano provável, IPU, faixas em reais, confiança e perguntas que decidem o plano.
3. Separar três personas da base comum (uma ALTO, uma FRONTEIRA, uma BAIXO) em `dados/fixtures/personas.json`.

Pronto quando: as três personas devolvem perfil completo, sem campo vazio.

### Fase 2 · Base de conhecimento e RAG (camada B)

1. `scripts/extrair_cg.py`: extrair o texto dos PDFs e quebrar por cláusula usando a numeração (3.1, 8.1 x...).
2. Gravar cada chunk em `clausulas.jsonl` com: `id`, `produto`, `plano`, `cobertura`, `tipo` (cobertura, exclusão, obrigação, carência), `segmento`, `clausula`, `texto`.
3. Revisar à mão os metadados das cláusulas mais usadas (roubo, despesas fixas, aluguel, coberturas especiais por segmento). Aqui a curadoria vale mais que o volume.
4. Escrever `objecoes.jsonl` com 10 a 15 objeções (preço, "nunca aconteceu comigo", "já tenho seguro") e a resposta com base na cláusula.
5. `rag.py`: busca BM25 filtrada pelo segmento e pelo plano do perfil, devolvendo os 5 melhores chunks.

Pronto quando: 10 perguntas de teste recuperam a cláusula esperada entre os 5 primeiros resultados.

### Fase 3 · Camada de decisão (Jev)

1. Definir a interface `Decisor` com três métodos: `escolher(contexto, opcoes)`, `pontuar(contexto, rubrica)` e `probabilidade(contexto, afirmacao)`.
2. Implementar `JevDecisor` seguindo a documentação da TypeSafe e `ClaudeDecisor` com tool use e campos `enum` como plano B.
3. Escrever as perguntas tipadas do turno: intenção, confirmação pendente, prontidão de compra e rota.
4. Definir o limiar de confiança (começar com 0,70) abaixo do qual `requer_humano = true`.

Pronto quando: 20 respostas livres de teste geram a confirmação certa em pelo menos 18.

### Fase 4 · Regras, enriquecimento e redação

1. `regras.py`: aplicar a confirmação extraída (por exemplo, estoque acima de R$ 40 mil) e recalcular o plano com a mesma regra do motor.
2. `enriquecimento.py`: consultar o CNPJ (com cache) e classificar a descrição do CNAE em um dos 10 segmentos pelo Decisor.
3. `redator.py`: prompt do Sonnet com o perfil, as cláusulas recuperadas e as regras de redação (uma pergunta por vez, risco em reais, citação obrigatória no formato `[cl. 8.1 x]`).

Pronto quando: as três personas recebem uma resposta coerente com o plano e com a cláusula citada.

### Fase 5 · Guardrail, log e pipeline

1. Checagem determinística: toda cláusula citada na resposta precisa estar entre as recuperadas.
2. Checagem pelo Decisor: "promete cobertura sem cláusula?" e "menciona dado sensível?".
3. Reprovou: o redator reescreve uma vez; reprovou de novo, vai para o gerente.
4. `log.py`: gravar cada turno com versão do modelo, decisões, probabilidades, cláusulas e tempo.
5. `pipeline.py`: um turno ponta a ponta, na ordem decidir, regras, recuperar, redigir, conferir, registrar.

Pronto quando: uma resposta forçada a citar cláusula inexistente é barrada.

### Fase 6 · Interface da demo

1. `app.py` em Streamlit: seletor de persona, chat no centro e painel lateral "caixa de vidro".
2. O painel mostra, a cada turno: decisões do Jev com probabilidade, plano antes e depois, cláusulas usadas e resultado do guardrail.
3. Modo de reprodução: rodar a conversa a partir do log, sem chamar API, para o caso de a internet cair na apresentação.

Pronto quando: as três personas rodam ao vivo e em modo de reprodução.

## Avaliação

A avaliação é o que transforma "funciona na demo" em "funciona". O `scripts/avaliar.py` roda tudo e gera um relatório de uma página para o slide.

| Conjunto | Tamanho | Como montar | Métrica |
| --- | --- | --- | --- |
| Perguntas sobre cobertura | 30 | Tiradas das CG, com a cláusula esperada anotada | Cláusula correta citada (meta ≥ 90%) |
| Pedidos fora da cobertura | 10 | Exclusões reais: ransomware, golpe de PIX, furto simples, alagamento | Recusa correta com a cláusula de exclusão (meta 100%) |
| Respostas livres para confirmação | 20 | Variações de "tenho uns 50 mil", "não sei", "menos de 30" | Confirmação extraída certa (meta ≥ 90%) |
| Casos ambíguos | 5 | Respostas vagas de propósito | Encaminhados ao gerente |
| Personas | 3 | ALTO, FRONTEIRA e BAIXO da base comum | Conversa completa sem erro |

Métricas operacionais registradas pelo log: tempo por turno, custo por turno (tokens do Sonnet e do Jev) e proporção de turnos que foram para o humano.

Duas comparações que valem slide: o custo da camada de decisão com Jev contra o mesmo trabalho feito pelo Sonnet, e as perguntas até a recomendação contra as 20 a 25 da cotação tradicional.

## Cronograma

O caminho mínimo (fases 0 a 5 com uma persona) precisa estar pronto hoje à noite; amanhã de manhã é para interface, avaliação e ensaio. Pergunta em aberto: qual é o horário exato da entrega em 29/10?

1. **Hoje, 17h30–18h30** · Fase 0 e pré-requisitos. Bloqueio do dia: confirmar o acesso ao Jev até 18h30; sem acesso, seguir com o plano B.
2. **Hoje, 18h30–20h** · Fases 1 e 2 em paralelo: uma pessoa no perfil, outra na extração e curadoria das cláusulas.
3. **Hoje, 20h–21h30** · Fase 3, camada de decisão.
4. **Hoje, 21h30–23h** · Fases 4 e 5 com uma persona ponta a ponta. Marco: o primeiro turno completo roda.
5. **Amanhã, primeiras 2 h** · Fase 6 (interface e modo de reprodução) e as outras duas personas.
6. **Amanhã, hora seguinte** · Avaliação completa e relatório.
7. **Amanhã, última hora antes da entrega** · Congelar o código, gravar um vídeo da demo como segurança e ensaiar o pitch duas vezes.

Divisão sugerida para uma equipe de três: dados e RAG (fases 1 e 2), decisão e pipeline (fases 3 a 5), interface e pitch (fase 6, avaliação e slides).

## Como usar o Claude Code

O Claude Code rende mais com um `CLAUDE.md` claro e um pedido por fase, sempre terminando com "rode os testes". Revisem cada diff antes de seguir: vocês respondem pelo código no pitch.

Conteúdo sugerido do `CLAUDE.md`:

```markdown
# Agente de vendas do Seguro Empresarial (MVP do datathon)

## Objetivo
Um agente que faz uma pergunta em vez de vinte e nunca promete o que a apólice não cobre.

## Arquitetura (cascata)
1. Decisor (Jev ou plano B) classifica a mensagem e extrai confirmações, com probabilidade.
2. regras.py aplica a confirmação e recalcula o plano (determinístico, nunca LLM).
3. rag.py recupera cláusulas filtradas por segmento e plano.
4. redator.py (Sonnet) escreve a resposta citando cláusulas no formato [cl. X].
5. guardrail.py confere; reprovado duas vezes vai para o humano.

## Regras
- Python 3.13, tipagem e modelos pydantic em agente/contratos.py.
- Nenhuma conta ou regra de plano feita por LLM.
- Toda afirmação de cobertura precisa de cláusula recuperada.
- Nunca usar dado sensível nem processo judicial do cliente.
- Chaves só em .env; nunca no código.
- Cada função nova vem com teste em testes/.
- Modelo do LLM lido de MODELO_LLM no .env.
```

Prompts por fase (um por sessão, nesta ordem):

1. **Fase 0:** "Leia o CLAUDE.md. Crie a estrutura de pastas, o requirements.txt e agente/contratos.py com o estado do turno descrito no plano. Escreva testes/test\_conexoes.py que faz uma chamada ao Sonnet. Rode os testes."
2. **Fase 1:** "Leia os arquivos em dados/score/ e mostre as colunas antes de codar. Depois implemente agente/perfil.py com get\_perfil\_cliente(id) e selecione três personas (IPU ALTO, FRONTEIRA e BAIXO) em dados/fixtures/personas.json. Rode os testes."
3. **Fase 2:** "Implemente scripts/extrair\_cg.py para quebrar os PDFs de dados/cg/ por cláusula, com os metadados do plano. Mostre 10 chunks de amostra para eu revisar antes de gravar tudo. Depois implemente agente/rag.py com BM25 e filtro por metadados, e um teste com 10 perguntas e a cláusula esperada."
4. **Fase 3:** "Implemente agente/decisor.py com a interface Decisor e as classes JevDecisor e ClaudeDecisor. Para o Jev, siga a documentação que vou colar a seguir; não invente o formato da API. O ClaudeDecisor usa tool use com enum. Crie testes com 20 respostas livres em dados/fixtures/."
5. **Fase 4:** "Implemente regras.py reaproveitando a regra de plano do motor original (cortes de R$ 40 mil e R$ 150 mil), enriquecimento.py com cache em dados/fixtures/ e redator.py com o prompt de redação. Rode as três personas e me mostre as respostas."
6. **Fase 5:** "Implemente guardrail.py, log.py e pipeline.py. Inclua um teste que força uma citação inexistente e confirma que ela é barrada."
7. **Fase 6:** "Crie app.py em Streamlit com seletor de persona, chat e painel lateral mostrando decisões, plano antes e depois, cláusulas e guardrail. Adicione um modo de reprodução a partir do log."

Dica: no prompt da fase 3, colem a página da documentação do Jev. O modelo é de setembro de 2026, e a documentação atual é a fonte certa para o formato das chamadas.

## Riscos, plano B e governança

O maior risco é a demo travar ao vivo. Por isso todo componente externo tem um substituto local.

| Risco | Sinal | Plano B |
| --- | --- | --- |
| Sem acesso ao Jev | Chave não sai até 18h30 de hoje | `ClaudeDecisor` com Haiku; manter o desenho da cascata no pitch |
| PDFs das CG mal extraídos | Cláusulas quebradas ou sem numeração | Montar os chunks principais à mão a partir do `contexto_condicoes_gerais.md` |
| Internet ou API caem na apresentação | Erro de conexão | Modo de reprodução pelo log + vídeo gravado |
| Sonnet cita cláusula errada | Guardrail reprova | Reescrita automática; segunda falha vai para o humano |
| CNPJ da base é sintético | Consulta não encontra | Fixtures em cache; mostrar uma consulta real com CNPJ público |
| Escopo cresce de novo | Vontade de incluir Radar, HIBP, clima | Congelar o escopo deste plano; o resto vai para "próximos passos" |

Governança e LGPD, para responder ao júri:

- A demo usa só a base sintética do desafio e dados abertos (CNPJ). Nenhum dado real de cliente sai do ambiente.
- Em produção, enviar dado de cliente a uma API externa é transferência de dados e exige avaliação do BB. O desenho em cascata funciona com um modelo de decisão hospedado no próprio banco.
- O plano é decidido por regra auditável, nunca por LLM. O LLM só escreve.
- Toda resposta fica registrada com versão do modelo, decisões, probabilidades e cláusulas, o que permite auditoria.
- HIBP e monitoramento digital só com consentimento explícito do cliente (fora do MVP).
- O agente nunca usa processos judiciais nem atributos sensíveis do cliente para vender.
- Abaixo do limiar de confiança, o caso vai para uma pessoa.

## Checklist antes do pitch

- [ ] As três personas rodam ao vivo, do começo ao fim
- [ ] O modo de reprodução funciona sem internet
- [ ] Vídeo da demo gravado
- [ ] Relatório de avaliação com os números reais (citação, recusa, extração, custo, tempo)
- [ ] Um caso indo para o gerente aparece na demo
- [ ] Um pedido fora da cobertura (ex.: ransomware) é recusado com a cláusula
- [ ] README atualizado com como rodar, premissas e uso de IA
- [ ] Chaves fora do repositório
- [ ] Diagrama da arquitetura no slide
- [ ] Respostas prontas para: LGPD, por que não usar IA no score, como provar aumento de vendas (piloto A/B), o que acontece sem o Jev
- [ ] Pitch ensaiado duas vezes dentro do tempo
