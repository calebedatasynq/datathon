"""Roda um turno de cada persona (decidir → regras → buscar → redigir) e mostra a resposta.

Uso: python scripts/rodar_personas.py
"""

import json
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
warnings.filterwarnings("ignore")

from agente import config, rag  # noqa: E402
from agente.decisor import confirmacao_aplicavel, criar_decisor, decidir_turno  # noqa: E402
from agente.perfil import get_perfil_cliente  # noqa: E402
from agente.redator import montar_entrada, redigir  # noqa: E402
from agente.regras import aplicar_confirmacao  # noqa: E402

PERSONAS = json.loads((config.RAIZ / "dados" / "fixtures" / "personas.json").read_text(encoding="utf-8"))
MENSAGENS = {
    "ESSENCIAL": "Oi! Que seguro faz sentido para a minha farmácia? E se arrombarem a loja, cobre?",
    "PRATICO": "Somos uns 30 funcionários.",
    "TOTAL": "Se um funcionário se machucar trabalhando, o seguro cobre?",
}


def turno(cliente_id: str, mensagem: str, decisor) -> dict:
    perfil = get_perfil_cliente(cliente_id)
    decisoes, motivo = decidir_turno(perfil, mensagem, decisor)
    confirmacao = decisoes.confirmacao if confirmacao_aplicavel(decisoes) else None
    atualizado, perfil_novo = aplicar_confirmacao(perfil, confirmacao)
    clausulas = rag.buscar_para_turno(mensagem, atualizado.plano, perfil.segmento)
    respondida = perfil.perguntas_pendentes[0] if confirmacao else None
    entrada = montar_entrada(
        perfil_novo, mensagem, clausulas, atualizado, decisoes, motivo is not None, pergunta_respondida=respondida
    )
    redacao = redigir(entrada)
    return {
        "perfil": perfil,
        "decisoes": decisoes,
        "motivo": motivo,
        "atualizado": atualizado,
        "clausulas": clausulas,
        "redacao": redacao,
    }


if __name__ == "__main__":
    decisor = criar_decisor()
    for plano, persona in PERSONAS.items():
        r = turno(persona["cliente_id"], MENSAGENS[plano], decisor)
        d, a = r["decisoes"], r["atualizado"]
        print(f"\n===== {plano} · {persona['cliente_id']} · {r['perfil'].segmento}")
        print(f"cliente: {MENSAGENS[plano]}")
        print(f"decisor ({decisor.ultima_execucao.get('modelo')}): intenção={d.intencao.valor} {d.intencao.probabilidade:.2f}", end="")
        if d.confirmacao:
            print(f" | confirmação={d.confirmacao.valor} {d.confirmacao.probabilidade:.2f}", end="")
        print(f" | rota={d.rota.valor} | gerente: {r['motivo']}")
        print(f"plano: {a.plano_anterior} → {a.plano} | próxima pergunta: {a.proxima_pergunta.texto if a.proxima_pergunta else '-'}")
        print(f"cláusulas: {[c.id for c in r['clausulas']]}")
        print(f"citadas: {r['redacao'].citacoes} ({r['redacao'].segundos}s)")
        print(f"\n{r['redacao'].texto}")
