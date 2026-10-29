"""Auditoria de dados e variáveis, sem criar rótulos de planos."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit

ROOT = Path(__file__).resolve().parents[1]
ORIGINAIS = ROOT / "dados/originais"
OUT = ROOT / "resultados"
PLANOS = ["ESSENCIAL", "PRATICO", "TOTAL"]


def ler(nome, comum=False):
    pasta = "Seguro_Empresarial_Teste_Comum" if comum else "Seguro_Empresarial_Desenvolvimento"
    return pd.read_csv(ORIGINAIS / pasta / (nome + ".csv"), encoding="utf-8-sig")


def ampliada(comum=False):
    nome = "teste_comum" if comum else "desenvolvimento"
    base = pd.read_csv(ROOT / f"dados/preparados/base_{nome}.csv")
    empresa = ler("empresas", comum)
    sinais = ler("sinais_financeiros_operacionais", comum)
    end = ler("enderecos_estabelecimentos", comum)
    bens = ler("bens_cadastrados", comum)
    for df, chaves in [(empresa, ["empresa_id"]),
                        (sinais, ["empresa_id", "imovel_id"]),
                        (end, ["empresa_id", "imovel_id"])]:
        extras = [c for c in df if c not in base.columns and c not in chaves]
        base = base.merge(df[chaves + extras], on=chaves, how="left", validate="many_to_one")
    agg = bens.groupby(["empresa_id", "imovel_id_referencia"]).agg(
        valor_bens_bruto=("valor_cadastrado", "sum"),
        probabilidade_media_vinculo=("probabilidade_bem_no_imovel_referencia", "mean"),
    ).reset_index().rename(columns={"imovel_id_referencia": "imovel_id"})
    return base.merge(agg, on=["empresa_id", "imovel_id"], validate="one_to_one")


def qualidade(base):
    rows = []
    excluir = {"empresa_id", "imovel_id", "cliente_id", "territorio_id", "plano_recomendado", "elegivel"}
    for c in base.columns:
        if c in excluir:
            continue
        x = base[c]
        sentinela = x.astype("string").eq("NAO_DISPONIVEL").fillna(False)
        invalida = x.isna() | sentinela
        if c in ["area_m2", "area_cadastrada_m2"]:
            invalida |= x.eq(0)
        numeric = pd.api.types.is_numeric_dtype(x)
        rows.append({
            "variavel": c, "tipo": "numerica" if numeric else "categorica",
            "distintos": x.nunique(), "ausentes_ou_indisponiveis": int(invalida.sum()),
            "pct_indisponivel": round(invalida.mean()*100, 3),
            "pct_zeros": round(x.eq(0).mean()*100, 3) if numeric else np.nan,
            "mediana": x.median() if numeric else np.nan,
            "p95": x.quantile(.95) if numeric else np.nan,
            "observacao": "Constante: não discrimina nesta amostra" if x.nunique() <= 1 else "Varia na base; utilidade para planos ainda não medida",
        })
    return pd.DataFrame(rows)


def correlacoes(base):
    nums = base.select_dtypes(include="number").drop(columns=["elegivel", "plano_recomendado"], errors="ignore")
    # Números de endereço/código não são medidas quantitativas de negócio.
    nums = nums.drop(columns=["numero", "codigo_ibge_municipio"], errors="ignore")
    corr = nums.corr()
    rows = []
    for i, a in enumerate(corr):
        for b in corr.columns[i+1:]:
            value = corr.loc[a, b]
            if abs(value) >= .8:
                rows.append({"variavel_a": a, "variavel_b": b, "pearson": value,
                             "iguais_em_todas_as_linhas": bool(base[a].equals(base[b]))})
    return pd.DataFrame(rows).sort_values("pearson", key=abs, ascending=False)


def casos(base):
    regras = [(f"atividade_{g}", base.grupo_atividade.eq(g)) for g in sorted(base.grupo_atividade.unique())]
    regras += [
        ("area_disponivel", base.area_m2.notna()), ("area_indisponivel", base.area_m2.isna()),
        ("empresa_unica_unidade", base.quantidade_estabelecimentos_empresa.eq(1)),
        ("empresa_varias_unidades", base.quantidade_estabelecimentos_empresa.gt(1)),
        ("matriz", base.tipo_unidade.eq("MATRIZ")), ("filial", base.tipo_unidade.eq("FILIAL")),
        ("faturamento_informado", base.origem_faturamento.eq("INFORMADO")),
        ("faturamento_presumido", base.origem_faturamento.ne("INFORMADO")),
        ("algum_bem_baixa_confianca", base.proporcao_bens_baixa_confianca.gt(0)),
        ("nenhum_bem_baixa_confianca", base.proporcao_bens_baixa_confianca.eq(0)),
        ("imovel_em_obra", base.situacao_imovel_cadastral.eq("EM_OBRA")),
        ("imovel_irregular", base.situacao_imovel_cadastral.eq("IRREGULAR")),
        ("endereco_incompativel", base.endereco_cnpj_compativel.eq("NAO")),
    ]
    cols = ["empresa_id", "imovel_id", "grupo_atividade", "tipo_unidade",
            "faturamento_mensal_empresa", "funcionarios_estimados_empresa",
            "quantidade_estabelecimentos_empresa", "area_m2", "area_ausente",
            "estoque_medio_estimado", "valor_bens_ponderado_estabelecimento",
            "origem_faturamento", "proporcao_bens_baixa_confianca",
            "situacao_imovel_cadastral", "endereco_cnpj_compativel"]
    rows = []
    for nome, mascara in regras:
        selected = base.loc[mascara, cols].sort_values(["empresa_id", "imovel_id"])
        if len(selected):
            row = selected.iloc[0].to_dict()
            row.update(caso=nome, casos_disponiveis=int(mascara.sum()),
                       plano_de_referencia="SEM ROTULO", resultado="Conferido com fontes; recomendação de plano pendente")
            rows.append(row)
    return pd.DataFrame(rows)


def vif_numerico(base):
    nomes = ["faturamento_mensal_empresa", "funcionarios_estimados_empresa", "area_m2",
             "estoque_medio_estimado", "valor_bens_ponderado_estabelecimento"]
    # Diagnóstico exploratório apenas das medidas numéricas e em casos completos.
    # Não é um imputador ou seleção ajustada na amostra de teste.
    x = np.log1p(base[nomes].dropna().astype(float))
    x = (x-x.mean())/x.std(ddof=0)
    rows = []
    for c in nomes:
        y=x[c].to_numpy(); z=np.column_stack([np.ones(len(x)), x.drop(columns=c)])
        fitted=z @ np.linalg.lstsq(z,y,rcond=None)[0]
        r2=1-np.sum((y-fitted)**2)/np.sum((y-y.mean())**2)
        rows.append({"variavel":c,"vif_log_casos_completos":1/(1-r2),"n":len(x)})
    return pd.DataFrame(rows)


def executar():
    OUT.mkdir(exist_ok=True)
    base=ampliada(); comum=ampliada(True)
    q=qualidade(base); corr=correlacoes(base); exemplos=casos(base)
    q.to_csv(OUT/'qualidade_todas_variaveis.csv',index=False,encoding='utf-8-sig')
    corr.to_csv(OUT/'redundancias.csv',index=False,encoding='utf-8-sig')
    exemplos.to_csv(OUT/'casos_demonstracao.csv',index=False,encoding='utf-8-sig')
    vif_numerico(base).to_csv(OUT/'vif_exploratorio.csv',index=False,encoding='utf-8-sig')
    grupos=base.groupby('grupo_atividade').agg(
        estabelecimentos=('imovel_id','size'),
        faturamento_mediano_empresa=('faturamento_mensal_empresa','median'),
        funcionarios_medianos_empresa=('funcionarios_estimados_empresa','median'),
        estoque_mediano=('estoque_medio_estimado','median'),
        bens_ponderados_medianos=('valor_bens_ponderado_estabelecimento','median'),
    )
    grupos.to_csv(OUT/'perfil_por_atividade.csv',encoding='utf-8-sig')
    stats=[]
    for comum_flag, nome, x in [(False,'desenvolvimento',base),(True,'teste_comum',comum)]:
        e=ler('empresas',comum_flag)
        stats.append({'base':nome,'estabelecimentos':len(x),'empresas':x.empresa_id.nunique(),
                      'planos_referencia':int(x.plano_recomendado.notna().sum()),
                      'area_ausente_pct':x.area_ausente.mean()*100,
                      'corr_receita_funcionarios_por_estabelecimento':x.faturamento_mensal_empresa.corr(x.funcionarios_estimados_empresa),
                      'corr_receita_funcionarios_por_empresa':e.faturamento_mensal.corr(e.quantidade_funcionarios_estimada),
                      'corr_estoque_medio_pico':x.estoque_medio_estimado.corr(x.estoque_pico_estimado),
                      'unidades_multiempresa':int(x.quantidade_estabelecimentos_empresa.gt(1).sum())})
    pd.DataFrame(stats).to_csv(OUT/'resumo_bases.csv',index=False,encoding='utf-8-sig')
    catalogo=ler('catalogo_coberturas_fixas_planos')
    pd.DataFrame([{'plano':p,'coberturas_catalogadas':int(catalogo.plano.eq(p).sum()),
                   'exemplos_rotulados':int(base.plano_recomendado.eq(p).sum()),
                   'acuracia':'NÃO ESTIMÁVEL','situacao':'Categoria conhecida; vínculo cliente-plano ausente'} for p in PLANOS]).to_csv(OUT/'situacao_por_plano.csv',index=False,encoding='utf-8-sig')
    treino,teste=next(GroupShuffleSplit(n_splits=1,test_size=.2,random_state=42).split(base,groups=base.empresa_id))
    part=base[['empresa_id','imovel_id']].copy();part['particao_proposta']='treino_desenvolvimento';part.loc[teste,'particao_proposta']='avaliacao_reservada'
    part.to_csv(OUT/'particao_empresas_proposta.csv',index=False,encoding='utf-8-sig')
    rotulos=base[['empresa_id','imovel_id']].copy()
    for c in ['plano_referencia','justificativa','revisor','fonte_criterio','versao_criterio']:
        rotulos[c]=''
    arquivo=ROOT/'dados/rotulos/rotulos_revisados.csv'
    if not arquivo.exists(): rotulos.to_csv(arquivo,index=False,encoding='utf-8-sig')
    fig,axes=plt.subplots(1,2,figsize=(12,4.5))
    medidas=['Área','Padrão construtivo','Material de parede']
    valores=[base.area_ausente.mean()*100,base.padrao_construtivo_cadastrado.eq('NAO_DISPONIVEL').mean()*100,base.material_parede_externa_cadastrado.eq('NAO_DISPONIVEL').mean()*100]
    axes[0].barh(medidas,valores,color='#2563eb');axes[0].set_xlim(0,100);axes[0].set_xlabel('% indisponível');axes[0].set_title('Qualidade: ausência real, incluindo códigos')
    for i,v in enumerate(valores):axes[0].text(v+1,i,f'{v:.1f}%',va='center')
    axes[1].scatter(base.faturamento_mensal_empresa,base.funcionarios_estimados_empresa,s=6,alpha=.25,color='#0f766e');axes[1].set_xlabel('Faturamento mensal da empresa (R$)');axes[1].set_ylabel('Funcionários estimados da empresa');axes[1].set_title('Informação parcialmente repetida')
    fig.tight_layout();fig.savefig(OUT/'diagnostico_variaveis.png',dpi=150);plt.close(fig)
    resumo={'variaveis_examinadas':len(q),'cenarios_demonstrados':len(exemplos),
            'treino_linhas':len(treino),'avaliacao_linhas':len(teste),
            'empresas_sobrepostas':len(set(base.iloc[treino].empresa_id)&set(base.iloc[teste].empresa_id)),
            'modelo_treinado':False,'motivo':'Ausência de plano de referência por estabelecimento',
            'limites_score_estimados':False,'melhor_modelo_identificado':False}
    (OUT/'estado_analise.json').write_text(json.dumps(resumo,ensure_ascii=False,indent=2)+'\n')
    return resumo


if __name__=='__main__':
    print(json.dumps(executar(),ensure_ascii=False,indent=2))
