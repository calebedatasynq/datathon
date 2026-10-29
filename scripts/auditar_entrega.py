"""Métricas verificáveis dos CSVs gerados, sem LLM ou requisições externas."""
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from agente import config, rag
from agente.personalizacao import RESTRITAS_PRATICO_TOTAL


def ler(path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def auditar(base, saida):
    resultados = ler(saida / "template_resultado_times.csv")
    coberturas = ler(saida / "template_coberturas_times.csv")
    originais = ler(base / "template_resultado_times.csv")
    chave = lambda r: (r["empresa_id"], r["imovel_id"])
    esperadas, obtidas = [chave(r) for r in originais], [chave(r) for r in resultados]
    erros = []
    if esperadas != obtidas or len(set(obtidas)) != len(obtidas):
        erros.append("chaves/ordem/duplicidade diferentes do template original")
    por_caso = defaultdict(list)
    pares = set(obtidas)
    for c in coberturas:
        por_caso[chave(c)].append(c)
        if chave(c) not in pares:
            erros.append("cobertura sem estabelecimento")
        try:
            a, b = float(c["faixa_valor_min"]), float(c["faixa_valor_max"])
            if not 0 < a <= b < float("inf"):
                raise ValueError()
        except ValueError:
            erros.append("faixa inválida")
        if not all(c[k].strip() for k in ("dados_utilizados", "regra_calculo_utilizada", "justificativa")):
            erros.append("cobertura sem rastreabilidade")
    fixas_ok, propostas, ciber = 0, 0, 0
    for r in resultados:
        cs = por_caso[chave(r)]
        nomes = {c["cobertura"] for c in cs}
        plano = r["plano_recomendado"]
        if len(nomes) != len(cs):
            erros.append("cobertura duplicada")
        if nomes != set(filter(None, r["coberturas_recomendadas"].split(";"))):
            erros.append("consolidado diverge do detalhamento")
        if r["elegivel"] == "NAO":
            if plano or cs or not r["motivo_inelegibilidade"]:
                erros.append("caso inelegível com oferta ou sem motivo")
            continue
        propostas += 1
        obrigatorias = set(rag.coberturas_do_plano(plano))
        if not obrigatorias or not obrigatorias <= nomes:
            erros.append("cobertura obrigatória ausente")
        else:
            fixas_ok += 1
        ciber += "AMPLA_PROTECAO_CIBERNETICA" in nomes
        if plano == "ESSENCIAL" and nomes & RESTRITAS_PRATICO_TOTAL:
            erros.append("adicional incompatível com Essencial")
    trilha = json.loads((saida / "trilha_recomendacoes.json").read_text(encoding="utf-8"))
    return {
        "plano_final_diferente_do_motor_sem_suspensos": sum(t["plano_final"] is not None and t["plano_final"] != t["plano_motor"] for t in trilha),
        "casos_com_alternativas": sum(bool(t["alternativas"]) for t in trilha),
        "casos_esperados": len(originais), "casos_processados": len(resultados),
        "cobertura_processamento_percentual": 100 * len(set(obtidas) & set(esperadas)) / len(esperadas),
        "linhas_coberturas": len(coberturas), "sugestoes_inclusive_condicionais": propostas,
        "sugestoes_com_todas_fixas": fixas_ok, "sugestoes_com_cibernetica": ciber,
        "elegibilidade": dict(Counter(r["elegivel"] for r in resultados)),
        "planos": dict(Counter(r["plano_recomendado"] or "SUSPENSO" for r in resultados)),
        "confianca": dict(Counter(r["confianca_geral"] for r in resultados)),
        "casos_com_justificativa": sum(bool(r["justificativa_recomendacao"].strip()) for r in resultados),
        "media_pendencias_confirmacao": sum(len(list(filter(None, r["perguntas_confirmacao"].split(" | ")))) for r in resultados) / len(resultados),
        "erros": dict(Counter(erros)),
        "limites": "Verifica conformidade estrutural; não valida comercialmente os planos, APIs ou qualidade das respostas do LLM.",
    }


if __name__ == "__main__":
    saida = config.RAIZ / "saidas" / "ambas_bases"
    metricas = {nome: auditar(config.RAIZ / pasta, saida / nome) for nome, pasta in (
        ("desenvolvimento", "Seguro_Empresarial_Desenvolvimento"), ("teste_comum", "Seguro_Empresarial_Teste_Comum"))}
    (saida / "metricas_guia_final.json").write_text(json.dumps(metricas, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(metricas, ensure_ascii=False, indent=2))
    sys.exit(int(any(m["erros"] for m in metricas.values())))
