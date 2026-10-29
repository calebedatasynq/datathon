"""Pré-calcula o risco do local de cada território da base de teste (territorio.csv).

A coordenada da base é perturbada ("não representa endereço real"): o clima usa a coordenada
aproximada (grade de ~25 km) e os perigos locais ficam no nível do município (setores do SGB);
barragens e relevo ficam SEM_DADO. Saída: dados/fixtures/risco_territorio.json.

    python scripts/enriquecer_territorio.py
"""

import csv
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agente import territorio  # noqa: E402
from agente.contratos import Local  # noqa: E402
from agente.dados_base import PASTA_BASE  # noqa: E402

MUNICIPIOS = {  # a base grava sem acento; o SGB e o ViaCEP usam o nome oficial
    "Sao Paulo": "São Paulo", "Brasilia": "Brasília", "Goiania": "Goiânia",
}  # fmt: skip


def main():
    with open(PASTA_BASE / "territorio.csv", encoding="utf-8-sig", newline="") as f:
        linhas = list(csv.DictReader(f))
    saida = {}
    for i, t in enumerate(linhas, 1):
        local = Local(
            municipio=MUNICIPIOS.get(t["municipio_real"], t["municipio_real"]),
            uf=t["uf_real"],
            codigo_ibge=t["codigo_ibge_municipio"],
            latitude=float(t["latitude_aproximada"]),
            longitude=float(t["longitude_aproximada"]),
            precisao="MUNICIPIO",
            fonte=territorio.FONTES["base"],
        )
        risco = territorio.analisar(local)
        for _ in range(3):  # o Open-Meteo limita consultas por minuto: espera e tenta de novo
            if not risco.falhas:
                break
            print(f"     {'; '.join(risco.falhas)}: aguardando 65 s")
            time.sleep(65)
            risco = territorio.analisar(local)
        saida[t["territorio_id"]] = risco.model_dump(mode="json")
        altos = [p.id for p in risco.perigos if p.nivel == "ALTO"]
        print(f"{i:3}/{len(linhas)} {t['territorio_id']} {local.municipio}/{local.uf}: agravamento {risco.agravamento}"
              f"{' · altos: ' + ', '.join(altos) if altos else ''}{' · falhas: ' + '; '.join(risco.falhas) if risco.falhas else ''}")
    territorio.ARQUIVO_BASE.write_text(json.dumps(saida, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"gravado: {territorio.ARQUIVO_BASE}")


if __name__ == "__main__":
    main()
