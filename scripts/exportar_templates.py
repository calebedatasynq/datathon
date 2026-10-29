"""Preenche os templates de entrega do desafio com o plano personalizado de cada estabelecimento.

Gera saidas/template_resultado_times.csv (uma linha por empresa-estabelecimento, na ordem do
template) e saidas/template_coberturas_times.csv (uma linha por cobertura). Sem LLM: tudo vem do
motor de score, das regras de personalização e do catálogo do desafio.
Uso: python scripts/exportar_templates.py
     python scripts/exportar_templates.py --ambas-bases
"""

import csv
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agente import config  # noqa: E402
from agente.dados_base import PASTA_BASE, estabelecimentos_da_base, get_estabelecimento  # noqa: E402
from agente.perfil import _entrada, get_perfil_cliente, perfil_de_entrada  # noqa: E402
from agente.personalizacao import personalizar  # noqa: E402

SAIDA = config.RAIZ / "saidas"
FONTES = (
    "Condições Gerais Seguro Empresarial v1.1 (BB Seguros/Aliança do Brasil, processo SUSEP 15414.604242/2022-04); "
    "catálogo do desafio complementado pelo Guia dos Times final, seção 10; "
    "SITE-CIBERNETICA (BB Seguros, comunicado de 12/03/2026); motor de score ordinal_mock_v2"
)


def _cabecalho(pasta: Path, arquivo: str) -> list[str]:
    with open(pasta / arquivo, encoding="utf-8-sig", newline="") as f:
        return next(csv.reader(f))


def _ordem(pasta: Path) -> list[tuple[str, str]]:
    with open(pasta / "template_resultado_times.csv", encoding="utf-8-sig", newline="") as f:
        return [(linha["empresa_id"], linha["imovel_id"]) for linha in csv.DictReader(f)]


def _fontes(p) -> str:
    if p.risco_local is None:
        return FONTES
    r = p.risco_local
    return f"{FONTES}; risco do local (consulta em {r.consultado_em}, granularidade: município; ver docs/fontes_territoriais.md): " + "; ".join(r.fontes)


def _exportar_base(pasta: Path, base_preparada: Path, destino: Path, conversa: bool) -> tuple[int, int]:
    destino.mkdir(parents=True, exist_ok=True)
    if conversa:
        perfis = None
        estabelecimentos = None
    else:
        with open(base_preparada, encoding="utf-8-sig", newline="") as f:
            perfis = {linha["imovel_id"]: _entrada(linha) for linha in csv.DictReader(f)}
        estabelecimentos = estabelecimentos_da_base(pasta)
    resultado, coberturas, trilha = [], [], []
    for empresa_id, imovel_id in _ordem(pasta):
        if conversa:
            perfil, estabelecimento = get_perfil_cliente(imovel_id), get_estabelecimento(imovel_id)
        else:
            perfil = perfil_de_entrada(perfis[imovel_id])
            estabelecimento = estabelecimentos[imovel_id]
        if perfil.empresa_id != empresa_id or estabelecimento.empresa_id != empresa_id:
            raise ValueError(f"Empresa divergente no estabelecimento {imovel_id}")
        p = personalizar(perfil, estabelecimento)
        trilha.append({"empresa_id": empresa_id, "imovel_id": imovel_id, "score": perfil.score,
                      "plano_motor": perfil.plano, "plano_final": p.plano_base,
                      "elegibilidade": p.elegivel, "alternativas": p.alternativas})
        resultado.append(
            {
                "empresa_id": empresa_id,
                "imovel_id": imovel_id,
                "elegivel": p.elegivel,
                "motivo_inelegibilidade": p.motivo_elegibilidade or "",
                "tipo_localizacao_sugerido": p.tipo_localizacao,
                "relacao_imovel_sugerida": p.relacao_imovel,
                "plano_recomendado": p.plano_base or "",
                "coberturas_recomendadas": ";".join(c.cobertura for c in p.coberturas if c.origem != "opcional"),
                "confianca_geral": p.confianca_geral,
                "justificativa_recomendacao": p.justificativa,
                "perguntas_confirmacao": " | ".join(p.perguntas_confirmacao),
                "fontes_publicas_adicionais": _fontes(p),
            }
        )
        for c in p.coberturas:
            if c.origem == "opcional":  # o template lista o que o plano recomenda, não as opções
                continue
            origem = f"no pacote {p.plano_base}" if c.origem == "plano" else "adicional pela necessidade do cliente"
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
                    "observacao": f"necessidade {c.necessidade.lower()}; {origem}; cláusulas: {', '.join(c.clausulas)}",
                }
            )
    for nome, linhas in (("template_resultado_times.csv", resultado), ("template_coberturas_times.csv", coberturas)):
        with open(destino / nome, "w", encoding="utf-8-sig", newline="") as f:
            escritor = csv.DictWriter(f, fieldnames=_cabecalho(pasta, nome))
            escritor.writeheader()
            escritor.writerows(linhas)
    (destino / "trilha_recomendacoes.json").write_text(json.dumps(trilha, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(resultado), len(coberturas)


def exportar() -> tuple[int, int]:
    """Mantém a exportação antiga do teste comum em saidas/."""
    return _exportar_base(PASTA_BASE, config.BASE_CLIENTES, SAIDA, conversa=True)


def exportar_ambas(saida: Path | None = None) -> dict[str, tuple[int, int]]:
    """Gera os quatro CSVs com a mesma lógica do motor e do personalizador."""
    raiz = Path(saida) if saida is not None else SAIDA / "ambas_bases"
    motor = config.DIR_MOTOR / "dados" / "preparados"
    bases = {
        "desenvolvimento": (config.RAIZ / "Seguro_Empresarial_Desenvolvimento", motor / "base_desenvolvimento.csv"),
        "teste_comum": (PASTA_BASE, config.BASE_CLIENTES),
    }
    return {
        nome: _exportar_base(pasta, preparada, raiz / nome, conversa=(nome == "teste_comum"))
        for nome, (pasta, preparada) in bases.items()
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ambas-bases", action="store_true", help="gera os quatro templates em subdiretórios")
    args = parser.parse_args()
    if args.ambas_bases:
        for nome, (n_resultado, n_coberturas) in exportar_ambas().items():
            print(f"{nome}: {n_resultado} estabelecimentos e {n_coberturas} coberturas")
    else:
        n_resultado, n_coberturas = exportar()
        print(f"{n_resultado} estabelecimentos e {n_coberturas} coberturas em {SAIDA.relative_to(config.RAIZ)}/")
