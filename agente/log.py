"""Registro de cada turno em JSONL: estado completo, versões dos modelos, tempos e tokens.

O estado completo permite auditoria e o modo de reprodução da demo (rodar sem API).
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from agente import config
from agente.contratos import EstadoTurno

ARQUIVO_LOG = config.RAIZ / "logs" / "turnos.jsonl"


def registrar(
    estado: EstadoTurno,
    sessao_id: str,
    turno: int,
    versoes: dict,
    tempos: dict[str, float],
    tokens: dict,
    extras: dict | None = None,
    arquivo: Path | None = None,
) -> dict:
    registro = {
        "momento": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sessao_id": sessao_id,
        "turno": turno,
        "versoes": versoes,
        "tempos_s": tempos,
        "tokens": tokens,
        "estado": estado.model_dump(mode="json"),
        **(extras or {}),
    }
    arquivo = arquivo or ARQUIVO_LOG
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    with open(arquivo, "a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")
    return registro


def ler(arquivo: Path | None = None, sessao_id: str | None = None) -> list[dict]:
    arquivo = arquivo or ARQUIVO_LOG
    if not arquivo.exists():
        return []
    with open(arquivo, encoding="utf-8") as f:
        registros = [json.loads(linha) for linha in f if linha.strip()]
    return [r for r in registros if sessao_id is None or r["sessao_id"] == sessao_id]
