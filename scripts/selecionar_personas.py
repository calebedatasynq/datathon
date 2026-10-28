"""Escolhe as três personas da demo na base de teste comum e grava dados/fixtures/personas.json.

ESSENCIAL e TOTAL: casos claros (dados completos, sem pergunta, mais longe do corte).
PRATICO: caso de fronteira (dados completos, com pergunta que muda o plano), para
mostrar a confirmação do Jev ao vivo.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agente import config  # noqa: E402
from agente.contratos import Plano  # noqa: E402
from agente.perfil import get_perfil_cliente, listar_clientes  # noqa: E402

DESTINO = config.RAIZ / "dados" / "fixtures" / "personas.json"


def selecionar() -> dict:
    completos = [p for p in map(get_perfil_cliente, listar_clientes()) if p.plano and not p.avisos]
    personas = {}
    for plano in (Plano.ESSENCIAL, Plano.TOTAL):
        claros = [p for p in completos if p.plano == plano and not p.perguntas_pendentes]
        escolhido = max(claros, key=lambda p: p.distancia_ao_corte)
        personas[plano] = {"cliente_id": escolhido.cliente_id, "tipo": "claro"}
    fronteira = [
        p
        for p in completos
        if p.plano == Plano.PRATICO
        and p.perguntas_pendentes
        and p.perguntas_pendentes[0].plano_se_sim != p.perguntas_pendentes[0].plano_se_nao
    ]
    escolhido = min(fronteira, key=lambda p: p.distancia_ao_corte)
    personas[Plano.PRATICO] = {"cliente_id": escolhido.cliente_id, "tipo": "fronteira"}
    return {plano.value: personas[plano] for plano in Plano}


if __name__ == "__main__":
    personas = selecionar()
    DESTINO.write_text(json.dumps(personas, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(personas, indent=2, ensure_ascii=False))
