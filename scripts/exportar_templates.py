"""Preenche os templates de entrega do desafio com o plano personalizado de cada estabelecimento.

Gera saidas/template_resultado_times.csv (uma linha por empresa-estabelecimento, na ordem do
template) e saidas/template_coberturas_times.csv (uma linha por cobertura). Sem LLM: tudo vem do
motor de score, das regras de personalização e do catálogo do desafio.
Uso: python scripts/exportar_templates.py
"""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agente import config  # noqa: E402
from agente.dados_base import PASTA_BASE, get_estabelecimento  # noqa: E402
from agente.perfil import get_perfil_cliente  # noqa: E402
from agente.personalizacao import personalizar  # noqa: E402

SAIDA = config.RAIZ / "saidas"
FONTES = (
    "Condições Gerais Seguro Empresarial v1.1 (BB Seguros/Aliança do Brasil, processo SUSEP 15414.604242/2022-04); "
    "catálogo de coberturas do desafio; motor de score ordinal_mock_v2"
)


def _cabecalho(arquivo: str) -> list[str]:
    with open(PASTA_BASE / arquivo, encoding="utf-8-sig", newline="") as f:
        return next(csv.reader(f))


def _ordem() -> list[tuple[str, str]]:
    with open(PASTA_BASE / "template_resultado_times.csv", encoding="utf-8-sig", newline="") as f:
        return [(linha["empresa_id"], linha["imovel_id"]) for linha in csv.DictReader(f)]


def exportar() -> tuple[int, int]:
    SAIDA.mkdir(exist_ok=True)
    resultado, coberturas = [], []
    for empresa_id, imovel_id in _ordem():
        p = personalizar(get_perfil_cliente(imovel_id), get_estabelecimento(imovel_id))
        resultado.append(
            {
                "empresa_id": empresa_id,
                "imovel_id": imovel_id,
                "elegivel": p.elegivel,
                "motivo_inelegibilidade": p.motivo_elegibilidade or "",
                "tipo_localizacao_sugerido": p.tipo_localizacao,
                "relacao_imovel_sugerida": p.relacao_imovel,
                "plano_recomendado": p.plano_base or "",
                "coberturas_recomendadas": ";".join(c.cobertura for c in p.coberturas),
                "confianca_geral": p.confianca_geral,
                "justificativa_recomendacao": p.justificativa,
                "perguntas_confirmacao": " | ".join(p.perguntas_confirmacao),
                "fontes_publicas_adicionais": FONTES,
            }
        )
        for c in p.coberturas:
            origem = f"fixa do plano {p.plano_base}" if c.origem == "plano" else "adicional sugerida pelo perfil"
            coberturas.append(
                {
                    "empresa_id": empresa_id,
                    "imovel_id": imovel_id,
                    "cobertura": c.cobertura,
                    "faixa_valor_min": f"{c.faixa_valor_min:.0f}",
                    "faixa_valor_max": f"{c.faixa_valor_max:.0f}",
                    "confianca_estimativa": c.confianca,
                    "dados_utilizados": c.dados_utilizados,
                    "regra_calculo_utilizada": c.regra_calculo,
                    "justificativa": c.justificativa,
                    "informacao_a_confirmar": c.informacao_a_confirmar or "",
                    "observacao": f"{origem}; cláusulas: {', '.join(c.clausulas)}",
                }
            )
    for nome, linhas in (("template_resultado_times.csv", resultado), ("template_coberturas_times.csv", coberturas)):
        with open(SAIDA / nome, "w", encoding="utf-8-sig", newline="") as f:
            escritor = csv.DictWriter(f, fieldnames=_cabecalho(nome))
            escritor.writeheader()
            escritor.writerows(linhas)
    return len(resultado), len(coberturas)


if __name__ == "__main__":
    n_resultado, n_coberturas = exportar()
    print(f"{n_resultado} estabelecimentos e {n_coberturas} coberturas em {SAIDA.relative_to(config.RAIZ)}/")
