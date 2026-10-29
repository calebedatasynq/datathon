"""Comparação de regressões ordinais. Exige planos de referência revisados.

Sem essas associações, registra bloqueio de treinamento e não produz scores.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.special import expit
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.metrics import balanced_accuracy_score, f1_score, log_loss, confusion_matrix
from sklearn.model_selection import StratifiedGroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler
from statsmodels.miscmodels.ordinal_model import OrderedModel

ROOT=Path(__file__).resolve().parents[1]
PLANOS=['ESSENCIAL','PRATICO','TOTAL']
CHAVES=['empresa_id','imovel_id']
COMUNS=['grupo_atividade','quantidade_estabelecimentos_empresa','tipo_unidade',
        'estoque_medio_estimado','valor_bens_ponderado_estabelecimento']
ESPECIFICACOES={
    'emprego':COMUNS+['funcionarios_estimados_empresa'],
    'economia':COMUNS+['faturamento_mensal_empresa'],
    'emprego_area':COMUNS+['funcionarios_estimados_empresa','area_m2'],
}


class SemRotulos(ValueError):
    pass


def validar_rotulos(base,rotulos):
    required=CHAVES+['plano_referencia','justificativa','revisor','fonte_criterio']
    if not set(required).issubset(rotulos.columns):
        raise ValueError('Arquivo de rótulos sem colunas obrigatórias')
    if rotulos[CHAVES].isna().any().any() or rotulos.duplicated(CHAVES).any():
        raise ValueError('Chave ausente ou duplicada no arquivo de rótulos')
    if not set(map(tuple,rotulos[CHAVES].to_numpy())).issubset(set(map(tuple,base[CHAVES].to_numpy()))):
        raise ValueError('Rótulo com estabelecimento fora da base')
    rotulos=rotulos.copy()
    rotulos['plano_referencia']=rotulos.plano_referencia.astype('string').str.strip().replace('',pd.NA)
    rotulos=rotulos.dropna(subset=['plano_referencia'])
    if rotulos.empty:
        raise SemRotulos('As três categorias existem, mas nenhum estabelecimento está associado a um plano de referência.')
    if not rotulos.plano_referencia.isin(PLANOS).all():
        raise ValueError('Plano diferente de ESSENCIAL, PRATICO e TOTAL')
    for c in ['justificativa','revisor','fonte_criterio']:
        if rotulos[c].fillna('').astype(str).str.strip().eq('').any():
            raise ValueError(f'Rótulo sem procedência: {c}')
    return base.drop(columns=['plano_recomendado'],errors='ignore').merge(rotulos,on=CHAVES,validate='one_to_one')


class RegressaoOrdinal:
    def __init__(self,colunas):
        self.colunas=colunas

    def fit(self,base,robusta=False):
        categoricas=[c for c in self.colunas if c in ['grupo_atividade','tipo_unidade']]
        numericas=[c for c in self.colunas if c not in categoricas]
        num=make_pipeline(SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True),
                          FunctionTransformer(np.log1p,feature_names_out='one-to-one'),StandardScaler())
        cat=make_pipeline(SimpleImputer(strategy='most_frequent'),
                          OneHotEncoder(drop='first',handle_unknown='ignore',sparse_output=False))
        self.preparador=ColumnTransformer([('numericas',num,numericas),('categoricas',cat,categoricas)])
        x=self.preparador.fit_transform(base[self.colunas])
        self.mascara=np.std(x,axis=0)>1e-10
        x=x[:,self.mascara]
        if np.linalg.matrix_rank(np.column_stack([np.ones(len(x)),x])) < x.shape[1]+1:
            raise ValueError('Dependência linear/constante implícita: revisar especificação')
        y=pd.Series(pd.Categorical(base.plano_referencia,categories=PLANOS,ordered=True),index=base.index)
        self.modelo=OrderedModel(y,x,distr='logit')
        kwargs={'cov_type':'cluster','cov_kwds':{'groups':base.empresa_id.to_numpy()}} if robusta else {}
        self.resultado=self.modelo.fit(method='bfgs',maxiter=1000,disp=False,**kwargs)
        if not self.resultado.mle_retvals.get('converged',False):
            raise ValueError('Modelo ordinal não convergiu')
        return self

    def predict(self,base):
        x=self.preparador.transform(base[self.colunas])[:,self.mascara]
        p=np.asarray(self.modelo.predict(self.resultado.params,exog=x))
        z=x@np.asarray(self.resultado.params)[:x.shape[1]]
        cortes=self.modelo.transform_threshold_params(np.asarray(self.resultado.params)[x.shape[1]:])[1:-1]
        # Regra ordinal pela mediana das classes, declarada antes da comparação.
        escolha=np.searchsorted(cortes,z,side='right')
        return p,escolha,expit(z),expit(cortes)


def metricas(base,pred):
    p,yhat,score,cortes=pred
    y=base.plano_referencia.map(dict(zip(PLANOS,range(3)))).to_numpy()
    return {'log_loss':float(log_loss(y,p,labels=[0,1,2])),
            'macro_f1':float(f1_score(y,yhat,labels=[0,1,2],average='macro',zero_division=0)),
            'acuracia_balanceada':float(balanced_accuracy_score(y,yhat)),
            'erro_ordinal_medio':float(np.abs(y-yhat).mean())}


def executar():
    out=ROOT/'resultados';out.mkdir(exist_ok=True)
    base=pd.read_csv(ROOT/'dados/preparados/base_desenvolvimento.csv')
    rotulos=pd.read_csv(ROOT/'dados/rotulos/rotulos_revisados.csv')
    try:
        dados=validar_rotulos(base,rotulos)
    except SemRotulos as exc:
        estado={'treinado':False,'motivo':str(exc),'n_rotulos':0,'n_categorias_previstas':3,
                'acuracia':None,'coeficientes':None,'limites_score':None}
        (out/'estado_modelagem.json').write_text(json.dumps(estado,ensure_ascii=False,indent=2)+'\n')
        return estado
    part=pd.read_csv(out/'particao_empresas_proposta.csv')
    dados=dados.merge(part,on=CHAVES,validate='one_to_one')
    treino=dados[dados.particao_proposta.eq('treino_desenvolvimento')].copy()
    teste=dados[dados.particao_proposta.eq('avaliacao_reservada')].copy()
    if set(treino.plano_referencia)!=set(PLANOS) or set(teste.plano_referencia)!=set(PLANOS):
        raise ValueError('Faltam classes em treino ou avaliação reservada; expandir rótulos sem escolher partição por desempenho')
    if set(treino.empresa_id)&set(teste.empresa_id):
        raise ValueError('Vazamento de empresas entre treino e avaliação')
    grupos_por_classe=treino.groupby('plano_referencia').empresa_id.nunique()
    if grupos_por_classe.min()<5:
        raise ValueError('Guardrail operacional: exigir pelo menos 5 empresas por classe para CV; não garante suficiência estatística')
    cv=StratifiedGroupKFold(n_splits=5,shuffle=True,random_state=42)
    dobras=list(cv.split(treino,treino.plano_referencia,treino.empresa_id))
    resultados=[]
    for nome,colunas in ESPECIFICACOES.items():
        for n,(it,iv) in enumerate(dobras,1):
            a,b=treino.iloc[it],treino.iloc[iv]
            if set(a.plano_referencia)!=set(PLANOS):
                raise ValueError('Uma dobra ficou sem classe no treino; ampliar amostra')
            m=RegressaoOrdinal(colunas).fit(a)
            resultados.append({'especificacao':nome,'dobra':n,**metricas(b,m.predict(b))})
    resultados=pd.DataFrame(resultados)
    resultados.to_csv(out/'comparacao_modelos_cv.csv',index=False)
    rank=resultados.groupby('especificacao').mean(numeric_only=True).sort_values(['log_loss','erro_ordinal_medio'])
    nome=rank.index[0]
    modelo=RegressaoOrdinal(ESPECIFICACOES[nome]).fit(treino,robusta=True)
    pred=modelo.predict(teste)
    medidas=metricas(teste,pred)
    pd.DataFrame(confusion_matrix(teste.plano_referencia.map(dict(zip(PLANOS,range(3)))),pred[1],labels=[0,1,2]),
                 index=PLANOS,columns=PLANOS).to_csv(out/'matriz_confusao_avaliacao.csv')
    nomes=list(modelo.preparador.get_feature_names_out()[modelo.mascara])+['limiar_1_parametrizado','incremento_log_limiar_2']
    ci=np.asarray(modelo.resultado.conf_int())
    pd.DataFrame({'termo':nomes,'coeficiente':np.asarray(modelo.resultado.params),
                  'p_valor_exploratorio':np.asarray(modelo.resultado.pvalues),
                  'ic95_inferior':ci[:,0],'ic95_superior':ci[:,1]}).to_csv(out/'coeficientes_exploratorios.csv',index=False)
    previsao=teste[CHAVES+['plano_referencia']].copy()
    for i,p in enumerate(PLANOS):previsao['p_'+p]=pred[0][:,i]
    previsao['plano_sugerido_mediana']=np.array(PLANOS)[pred[1]]
    previsao['score_ordinal']=pred[2]
    previsao.to_csv(out/'previsoes_avaliacao.csv',index=False)
    estado={'treinado':True,'especificacao':nome,'treino':len(treino),'avaliacao':len(teste),
            'metricas_avaliacao':medidas,'cortes_score':pred[3].tolist(),
            'hipotese_chances_proporcionais':'AINDA EXIGE DIAGNÓSTICO; não aprovar apenas pelas métricas',
            'inferencia':'Exploratória após escolha de especificação; erros agrupados por empresa. Não é conclusão confirmatória.'}
    (out/'estado_modelagem.json').write_text(json.dumps(estado,ensure_ascii=False,indent=2)+'\n')
    return estado


if __name__=='__main__':
    print(json.dumps(executar(),ensure_ascii=False,indent=2))
