"""Mede a confirmação extraída pelo decisor nas respostas livres de dados/fixtures/respostas_confirmacao.json.

Uso: python scripts/avaliar_decisor.py [jev] [claude]   (padrão: os dois)
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agente import config  # noqa: E402
from agente.contratos import Pergunta, Plano  # noqa: E402
from agente.decisor import ClaudeDecisor, JevDecisor, decidir_turno, motivo_para_humano  # noqa: E402

FIXTURE = config.RAIZ / "dados" / "fixtures" / "respostas_confirmacao.json"


def carregar() -> tuple[dict[str, Pergunta], list[dict]]:
    dados = json.loads(FIXTURE.read_text(encoding="utf-8"))
    perguntas = {
        nome: Pergunta(
            **p, valor_estimado=p["limiar"], plano_se_sim=Plano.TOTAL, plano_se_nao=Plano.PRATICO
        )
        for nome, p in dados["perguntas"].items()
    }
    return perguntas, dados["respostas"]


def avaliar(decisor) -> dict:
    perguntas, respostas = carregar()
    linhas, acertos, humanos, segundos = [], 0, 0, 0.0
    for r in respostas:
        decisoes, motivo = decidir_turno(None, r["mensagem"], decisor, perguntas[r["pergunta"]])
        c = decisoes.confirmacao
        ok = c.valor == r["esperado"]
        acertos += ok
        humanos += motivo is not None
        segundos += decisor.ultima_execucao["segundos"]
        linhas.append({**r, "obtido": c.valor, "probabilidade": c.probabilidade, "humano": motivo, "ok": ok})
    return {
        "decisor": decisor.nome,
        "modelo": decisor.ultima_execucao.get("modelo"),
        "acertos": acertos,
        "total": len(respostas),
        "para_humano": humanos,
        "segundos_medio": round(segundos / len(respostas), 2),
        "linhas": linhas,
    }


if __name__ == "__main__":
    escolhidos = sys.argv[1:] or ["jev", "claude"]
    for nome in escolhidos:
        resultado = avaliar(JevDecisor() if nome == "jev" else ClaudeDecisor())
        print(
            f"\n== {resultado['decisor']} ({resultado['modelo']}): {resultado['acertos']}/{resultado['total']} "
            f"| para o gerente: {resultado['para_humano']} | {resultado['segundos_medio']} s/turno"
        )
        for l in resultado["linhas"]:
            marca = "ok " if l["ok"] else "ERR"
            humano = f"  → gerente: {l['humano']}" if l["humano"] else ""
            print(
                f"  {marca} [{l['pergunta']}] {l['mensagem'][:45]:45} esperado={l['esperado']:13} "
                f"obtido={l['obtido']:13} p={l['probabilidade']:.2f}{humano}"
            )
