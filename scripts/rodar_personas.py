"""Roda um turno de cada persona pelo pipeline completo e mostra decisões, plano personalizado e resposta.

Uso: python scripts/rodar_personas.py
"""

import json
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
warnings.filterwarnings("ignore")

from agente import config  # noqa: E402
from agente.decisor import criar_decisor  # noqa: E402
from agente.pipeline import Conversa  # noqa: E402

PERSONAS = json.loads((config.RAIZ / "dados" / "fixtures" / "personas.json").read_text(encoding="utf-8"))
MENSAGENS = {
    "ESSENCIAL": "Oi! Que seguro faz sentido para a minha farmácia? E se arrombarem a loja, cobre?",
    "PRATICO": "Somos uns 30 funcionários.",
    "TOTAL": "Se um funcionário se machucar trabalhando, o seguro cobre?",
}


def turno(cliente_id: str, mensagem: str, decisor, arquivo_log: Path | None = None):
    return Conversa(cliente_id, decisor=decisor, arquivo_log=arquivo_log).turno(mensagem)


if __name__ == "__main__":
    decisor = criar_decisor()
    for plano, persona in PERSONAS.items():
        e = turno(persona["cliente_id"], MENSAGENS[plano], decisor)
        d, a, p = e.decisoes, e.perfil_atualizado, e.plano_personalizado
        print(f"\n===== {plano} · {persona['cliente_id']} · {e.perfil.segmento}")
        print(f"cliente: {MENSAGENS[plano]}")
        print(f"intenção={d.intencao.valor}", f"| confirmação={d.confirmacao.valor}" if d.confirmacao else "", f"| gerente: {e.motivo_humano}")
        print(f"plano base: {a.plano_anterior} → {a.plano} | adicionais: {[c.cobertura for c in p.adicionais]}")
        print(f"guardrail: {'ok' if e.guardrail.aprovado else 'REPROVOU'} (tentativas {e.guardrail.tentativas}) {e.guardrail.motivo or ''}")
        print(f"\n{e.resposta}")
