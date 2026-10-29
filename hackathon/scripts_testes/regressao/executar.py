"""Iterações com 8, 9 e 10 variáveis; seleção apenas em CV do desenvolvimento."""
from pathlib import Path
import json,pickle,hashlib
import numpy as np
import pandas as pd
from scipy.special import expit
from scipy.optimize import minimize
from sklearn.model_selection import GroupKFold
from sklearn.metrics import log_loss,accuracy_score,f1_score,confusion_matrix
from modelo import Ordinal,objetivo,criterios,rotular,PLANOS,EMP,EST,BEM
ROOT=Path('/home/lucas/Documentos/hackathon/seguro_empresarial')
P=Path(__file__).resolve().parent;O=P/'resultados';O.mkdir(exist_ok=True)
BASE=[EMP,EST,BEM,'faturamento_mensal_empresa','quantidade_estabelecimentos_empresa','grupo_atividade','tipo_unidade','area_m2']
SPECS={'8_variaveis':BASE,'9_variaveis':BASE+['possui_termo_loja'],'10_variaveis':BASE+['possui_termo_loja','possui_termo_galeria']}

def save(name,d):(O/name).write_text(json.dumps(d,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def metric(y,p,pred,freq):
    loss=float(log_loss(y,p,labels=[0,1,2]));null=float(log_loss(y,np.tile(freq,(len(y),1)),labels=[0,1,2]))
    return {'log_loss':loss,'log_loss_nulo':null,'indice_1_menos_LL_LL0':1-loss/null,'acuracia':float(accuracy_score(y,pred)),'macro_f1':float(f1_score(y,pred,average='macro',labels=[0,1,2],zero_division=0))}

def main():
    dev=pd.read_csv(ROOT/'dados/preparados/base_desenvolvimento.csv');folds=list(GroupKFold(3).split(dev,groups=dev.empresa_id))
    save('protocolo.json',{'especificacoes':SPECS,'penalidades':[.1,1,10],'politica':'central v1 mantida; percentis estimados no treino de cada dobra',
        'r2':'McFadden no ajuste, análogo preditivo fora da amostra; likelihood sem penalidade',
        'selecao':'menor log_loss OOF agregada entre 8/9/10 e penalidades',
        'limite_teste':'Base de teste já avaliada na v1; reavaliação comparativa, não nova validação intocada'})
    records=[];aggregate=[];oof_store={}
    for name,cols in SPECS.items():
        for alpha in [.1,1.,10.]:
            pp=np.zeros((len(dev),3));yy=np.zeros(len(dev),int);hh=np.zeros(len(dev),int);nullp=np.zeros((len(dev),3))
            for fold,(ia,ib) in enumerate(folds):
                a,b=dev.iloc[ia],dev.iloc[ib];cr=criterios(a);ya,yb=rotular(a,cr),rotular(b,cr)
                assert not set(a.empresa_id)&set(b.empresa_id)
                freq=np.bincount(ya,minlength=3)/len(ya)
                m=Ordinal(cols,alpha).fit(a,ya)
                pa,ha,*_=m.predict(a);pb,hb,*_=m.predict(b)
                tr=metric(ya,pa,ha,freq);va=metric(yb,pb,hb,freq)
                records.append({'iteracao':name,'n_variaveis':len(cols),'alpha':alpha,'dobra':fold+1,
                    **{'treino_'+k:v for k,v in tr.items()},**{'validacao_'+k:v for k,v in va.items()}})
                pp[ib]=pb;yy[ib]=yb;hh[ib]=hb;nullp[ib]=freq
            loss=log_loss(yy,pp,labels=[0,1,2]);null=log_loss(yy,nullp,labels=[0,1,2])
            aggregate.append({'iteracao':name,'n_variaveis':len(cols),'alpha':alpha,'log_loss_cv':loss,'pseudo_r2_preditivo_cv':1-loss/null,'acuracia_cv':accuracy_score(yy,hh),'macro_f1_cv':f1_score(yy,hh,average='macro')})
            oof_store[(name,alpha)]=(yy,pp,hh)
            print(name,alpha,'pseudo-R2 preditivo CV',round(1-loss/null,6),flush=True)
    pd.DataFrame(records).to_csv(O/'cada_iteracao_e_dobra.csv',index=False)
    ranking=pd.DataFrame(aggregate).sort_values('log_loss_cv');ranking.to_csv(O/'ranking_cv.csv',index=False)
    best=ranking.iloc[0];name=best.iteracao;alpha=float(best.alpha)
    cr=criterios(dev);y=rotular(dev,cr);freq=np.bincount(y,minlength=3)/len(y)
    # política final precisa ser a mesma da v1: mudança apenas das variáveis.
    old=json.loads((ROOT/'indice_regressao_v1/resultados/criterios_congelados.json').read_text())
    assert cr==old
    summaries=[];models={}
    for key,cols in SPECS.items():
        row=ranking[ranking.iteracao.eq(key)].iloc[0];mm=Ordinal(cols,float(row.alpha)).fit(dev,y);models[key]=mm
        p,h,*_=mm.predict(dev);tr=metric(y,p,h,freq)
        summaries.append({**row.to_dict(),'pseudo_r2_mcfadden_treino':tr['indice_1_menos_LL_LL0'],'acuracia_treino':tr['acuracia'],'n_coeficientes_apos_codificacao':len(mm.beta)})
    summary=pd.DataFrame(summaries);summary.to_csv(O/'resumo_8_9_10.csv',index=False)
    m=models[name];artifact={'modelo':m,'criterios':cr,'versao':'ordinal_mock_v2','variaveis':SPECS[name],'alpha':alpha}
    path=O/'modelo_ordinal.pkl';path.write_bytes(pickle.dumps(artifact));digest=hashlib.sha256(path.read_bytes()).hexdigest()
    save('congelamento.json',{'iteracao':name,'alpha':alpha,'hash_modelo':digest,'limiares_z':m.thresholds.tolist(),'cortes_score':expit(m.thresholds).tolist()})
    # Coeficientes e estabilidade condicional: transformação/política congeladas.
    x=m.design(dev);rng=np.random.default_rng(20261028);groups=dev.groupby('empresa_id').indices;keys=list(groups);boots=[]
    for _ in range(100):
        ix=np.concatenate([groups[g] for g in rng.choice(keys,len(keys),replace=True)])
        b=minimize(objetivo,m.opt.x,args=(x[ix],y[ix],alpha),jac=True,method='L-BFGS-B',options={'maxiter':1000,'ftol':1e-9})
        if b.success:boots.append(b.x[:-2])
    assert len(boots)>=90
    lo,hi=np.quantile(boots,[.025,.975],axis=0)
    pd.DataFrame({'termo':m.names,'peso':m.beta,'ic_condicional_2_5':lo,'ic_condicional_97_5':hi,'sinal_estavel_condicional':(lo>0)|(hi<0)}).to_csv(O/'pesos.csv',index=False)
    # Grupo de contribuição de cada variável de entrada, incluindo categorias e ausência.
    grouped=[]
    for col in m.colunas:
        idx=[j for j,t in enumerate(m.names) if t==f'num__{col}' or t==f'num__missingindicator_{col}' or t.startswith(f'cat__{col}_')]
        grouped.append({'variavel':col,'termos':[m.names[j] for j in idx], 'media_abs_contribuicao_z':float(np.abs((x*m.beta)[:,idx].sum(axis=1)).mean()),'fracao_ausente':float(dev[col].isna().mean())})
    save('contribuicao_por_variavel.json',grouped)
    # Leitura do teste somente após seleção e congelamento; reconhecido como reavaliação.
    test=pd.read_csv(ROOT/'dados/preparados/base_teste_comum.csv');yt=rotular(test,cr)
    assert not set(dev.empresa_id)&set(test.empresa_id)
    p,h,s,c,contrib=m.predict(test)
    tmetrics=metric(yt,p,h,freq)
    res={'versao':'ordinal_mock_v2','selecionado':name,'n_variaveis':len(m.colunas),'variaveis':m.colunas,'alpha':alpha,'cortes':c.tolist(),
         'treino':len(dev),'teste':len(test),'metricas_teste':tmetrics,'bootstrap_validos':len(boots),
         'limite':'Concordância com referências construídas; teste já consultado na v1. Pseudo-R2 não é porcentagem de variância explicada.'}
    save('resultado.json',res)
    pred=test[['empresa_id','imovel_id']].copy();pred['referencia']=PLANOS[yt];pred['indicado']=PLANOS[h];pred['score']=s
    for j,cl in enumerate(PLANOS):pred['p_'+cl]=p[:,j]
    pred.to_csv(O/'scores_teste.csv',index=False)
    pd.DataFrame(confusion_matrix(yt,h,labels=[0,1,2]),index=PLANOS,columns=PLANOS).to_csv(O/'confusao.csv')
    profiles=[]
    for i,row in test.iterrows():
        profiles.append({'versao':'ordinal_mock_v2','status':'EXPERIMENTAL_BASE_MOCK','empresa_id':row.empresa_id,'imovel_id':row.imovel_id,
            'score':float(s[i]),'plano_sugerido':str(PLANOS[h[i]]),'cortes':c.tolist(),'probabilidades_referencia':dict(zip(PLANOS,p[i].tolist())),
            'contribuicoes':[{'termo':term,'contribuicao_z':float(v)} for term,v in zip(m.names,contrib[i])],
            'campos_ausentes':row[m.colunas][row[m.colunas].isna()].index.tolist(),'elegibilidade':'NAO_AVALIADA',
            'limite':'Modelo aprende critérios do protótipo. Não é chance de venda nem garantia de adequação.'})
    (O/'perfis_rag.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,allow_nan=False)+'\n' for r in profiles))
    tests={'8_a_10_variaveis':8<=len(m.colunas)<=10,'3_iteracoes_9_configuracoes_27_ajustes':len(records)==27,
        'politica_v1_preservada':cr==old,'p_somam_1':bool(np.allclose(p.sum(axis=1),1)),
        'p_validas':bool(((p>=0)&(p<=1)).all()),'score_valido':bool(((s>=0)&(s<=1)).all()),
        'cortes_ordenados':bool(0<c[0]<c[1]<1),'mediana_confere':bool(np.array_equal(h,np.searchsorted(c,s,side='right'))),
        'contribuicoes_conferem':bool(np.allclose(expit(contrib.sum(axis=1)),s)),
        'modelo_congelado':hashlib.sha256(path.read_bytes()).hexdigest()==digest,'bootstrap_90_ou_mais':len(boots)>=90}
    assert all(tests.values());save('testes.json',tests)
    print(summary.to_string(index=False),flush=True);print(json.dumps(res,indent=2,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
