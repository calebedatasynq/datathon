"""Prepara candidatos para regressão ordinal; não treina nem cria rótulos.

Execução: python modelagem/preparar_base.py --origem /caminho/do/pacote
Dependência: pandas; versão executada registrada em requirements.txt. Os arquivos originais são apenas lidos.
"""

import argparse
import hashlib
import json
import platform
from pathlib import Path

import pandas as pd


KEY = ["empresa_id", "imovel_id"]
CONFIG = json.loads(Path(__file__).with_name("variaveis.json").read_text(encoding="utf-8"))
CANDIDATAS = CONFIG["candidatas_iniciais"]
CONDICIONAIS = CONFIG["candidatas_condicionais"]


def exigir(condicao, mensagem):
    if not condicao:
        raise ValueError(mensagem)


def chave_unica(df, cols, nome):
    exigir(not df[cols].isna().any().any(), f"Chave ausente: {nome}")
    exigir(not df.duplicated(cols).any(), f"Chave duplicada: {nome}")


def preparar(pasta, destino):
    nomes = ["empresas", "enderecos_estabelecimentos",
             "sinais_financeiros_operacionais", "bens_cadastrados",
             "template_resultado_times"]
    dados, fontes = {}, {}
    for nome in nomes:
        caminho = pasta / f"{nome}.csv"
        dados[nome] = pd.read_csv(caminho, encoding="utf-8-sig")
        fontes[nome] = {
            "arquivo": str(caminho.resolve()),
            "sha256": hashlib.sha256(caminho.read_bytes()).hexdigest(),
            "linhas": len(dados[nome]),
        }
    e = dados["empresas"]
    a = dados["enderecos_estabelecimentos"]
    s = dados["sinais_financeiros_operacionais"]
    b = dados["bens_cadastrados"]
    t = dados["template_resultado_times"]
    for df, cols, nome in [(e, ["empresa_id"], "empresas"),
                           (a, ["imovel_id"], "imóveis"),
                           (s, KEY, "sinais"), (t, KEY, "template"),
                           (b, ["bem_id"], "bens")]:
        chave_unica(df, cols, nome)
    exigir(set(e.empresa_id) == set(a.empresa_id), "Empresas e imóveis não correspondem")
    pares = set(map(tuple, a[KEY].to_numpy()))
    for df, nome in [(s, "sinais"), (t, "template")]:
        exigir(set(map(tuple, df[KEY].to_numpy())) == pares,
                f"Pares empresa-imóvel divergentes: {nome}")
    bp = b.rename(columns={"imovel_id_referencia": "imovel_id"}).copy()
    exigir(set(map(tuple, bp[KEY].to_numpy())).issubset(pares),
            "Bem vinculado a empresa ou imóvel incompatível")
    exigir(bp.nivel_confianca_vinculo.isin(["ALTA", "MEDIA", "BAIXA"]).all(),
            "Confiança dos bens fora do domínio esperado")
    exigir(bp.valor_bem_ponderado_referencia.notna().all()
            and bp.valor_bem_ponderado_referencia.ge(0).all(),
            "Valor ponderado de bem inválido")
    bp["vinculo_baixa_confianca"] = bp.nivel_confianca_vinculo.eq("BAIXA")
    bens = bp.groupby(KEY, as_index=False).agg(
        valor_bens_ponderado_estabelecimento=("valor_bem_ponderado_referencia", "sum"),
        quantidade_bens_cadastrados=("bem_id", "size"),
        proporcao_bens_baixa_confianca=("vinculo_baixa_confianca", "mean"),
    )
    empresa = e[["empresa_id", "grupo_atividade", "faturamento_mensal",
                 "quantidade_funcionarios_estimada", "origem_faturamento",
                 "confianca_faturamento"]].rename(columns={
        "faturamento_mensal": "faturamento_mensal_empresa",
        "quantidade_funcionarios_estimada": "funcionarios_estimados_empresa",
    })
    contagens = a.groupby("empresa_id").size()
    empresa["quantidade_estabelecimentos_empresa"] = empresa.empresa_id.map(contagens)
    base = a[KEY + ["tipo_unidade", "area_cadastrada_m2", "origem_area",
                    "confianca_area", "possui_termo_loja", "possui_termo_galeria",
                    "endereco_cnpj_compativel", "situacao_imovel_cadastral",
                    "material_parede_externa_cadastrado"]].copy()
    exigir(base.area_cadastrada_m2.dropna().ge(0).all(), "Área negativa")
    ausente = (base.area_cadastrada_m2.isna()
               | base.area_cadastrada_m2.eq(0)
               | base.origem_area.eq("NAO_DISPONIVEL"))
    base["area_m2"] = base.area_cadastrada_m2.mask(ausente)
    base["area_ausente"] = ausente.astype(int)
    base = base.drop(columns="area_cadastrada_m2")
    for coluna in CONDICIONAIS:
        exigir(base[coluna].dropna().isin(["SIM", "NAO"]).all(),
                f"Domínio inesperado: {coluna}")
        base[coluna] = base[coluna].map({"SIM": 1, "NAO": 0}).astype("Int64")
    base = base.merge(empresa, on="empresa_id", how="left", validate="many_to_one")
    base = base.merge(s[KEY + ["estoque_medio_estimado"]], on=KEY,
                      how="left", validate="one_to_one")
    base = base.merge(bens, on=KEY, how="left", validate="one_to_one")
    # Sem bens cadastrados não significa valor patrimonial igual a zero.
    base["quantidade_bens_cadastrados"] = base.quantidade_bens_cadastrados.fillna(0).astype(int)
    base["bens_sem_cadastro"] = base.quantidade_bens_cadastrados.eq(0).astype(int)
    base = base.merge(t[KEY + ["plano_recomendado", "elegivel"]],
                      on=KEY, how="left", validate="one_to_one")
    base["plano_recomendado"] = base.plano_recomendado.astype("string").str.strip().replace("", pd.NA)
    exigir(base.plano_recomendado.dropna().isin(["ESSENCIAL", "PRATICO", "TOTAL"]).all(),
            "Plano de origem fora das categorias previstas")
    exigir(len(base) == len(a), "Junção alterou quantidade de estabelecimentos")
    chave_unica(base, KEY, "base final")
    numericas = [c for c in CANDIDATAS if c not in ["grupo_atividade", "tipo_unidade"]]
    for coluna in numericas:
        exigir(base[coluna].dropna().ge(0).all(), f"Valor negativo em {coluna}")
    auxiliares = [c for c in base.columns if c not in KEY + CANDIDATAS + CONDICIONAIS
                  + ["plano_recomendado", "elegivel"]]
    base = base[KEY + CANDIDATAS + CONDICIONAIS + auxiliares
                + ["elegivel", "plano_recomendado"]].sort_values(KEY).reset_index(drop=True)
    destino.parent.mkdir(parents=True, exist_ok=True)
    base.to_csv(destino, index=False, encoding="utf-8-sig")
    correlacoes = base[numericas].corr()
    pares_correlacionados = [
        {"variavel_1": x, "variavel_2": y, "pearson": round(float(correlacoes.loc[x, y]), 6)}
        for i, x in enumerate(numericas) for y in numericas[i+1:]
        if abs(correlacoes.loc[x, y]) >= .8
    ]
    resumo = {
        "fontes": fontes, "arquivo_saida": str(destino.resolve()),
        "linhas": len(base), "empresas": int(base.empresa_id.nunique()),
        "colunas": len(base.columns), "candidatas_iniciais": CANDIDATAS,
        "candidatas_condicionais": CONDICIONAIS, "auxiliares": auxiliares,
        "rotulos_plano_preenchidos": int(base.plano_recomendado.notna().sum()),
        "area_ausente": int(base.area_ausente.sum()),
        "bens_sem_cadastro": int(base.bens_sem_cadastro.sum()),
        "ausentes_por_candidata": {c: int(base[c].isna().sum()) for c in CANDIDATAS + CONDICIONAIS},
        "correlacoes_pearson_absolutas_ge_0_8": pares_correlacionados,
        "grupo_atividade": base.grupo_atividade.value_counts().to_dict(),
        "verificacoes": "Chaves, referências empresa-imóvel, junções, domínios e não-negatividade conferidos.",
    }
    return resumo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--origem", type=Path, required=True)
    parser.add_argument("--saida", type=Path, default=Path(__file__).resolve().parents[1] / "dados" / "preparados")
    args = parser.parse_args()
    resumo = {"versao_preparacao": "1.0", "python": platform.python_version(),
              "pandas": pd.__version__, "modelo_treinado": False, "bases": {}}
    for pasta, nome in [("Seguro_Empresarial_Desenvolvimento", "desenvolvimento"),
                        ("Seguro_Empresarial_Teste_Comum", "teste_comum")]:
        resumo["bases"][nome] = preparar(args.origem / pasta, args.saida / f"base_{nome}.csv")
    (args.saida / "relatorio_preparacao.json").write_text(
        json.dumps(resumo, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    for nome, base in resumo["bases"].items():
        print(nome, {k: base[k] for k in ["linhas", "empresas", "colunas", "rotulos_plano_preenchidos", "area_ausente"]})
        print("correlações para revisão:", base["correlacoes_pearson_absolutas_ge_0_8"])


if __name__ == "__main__":
    main()
