from pathlib import Path
import json, hashlib, pickle, warnings
import numpy as np
import pandas as pd
from scipy.optimize import check_grad, minimize
from scipy.special import expit
from sklearn.model_selection import GroupKFold
from sklearn.metrics import log_loss, f1_score, balanced_accuracy_score, accuracy_score, confusion_matrix
from sklearn.linear_model import LogisticRegression
from modelo import *
ROOT=Path('/home/lucas/Documentos/hackathon/seguro_empresarial')
HERE=Path(__file__).resolve().parent; OUT=HERE/'resultados'; OUT.mkdir(exist_ok=True)

def save(name,obj):
    (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def measures(y,p,pred):
    return {'acuracia':float(accuracy_score(y,pred)), 'acuracia_balanceada':float(balanced_accuracy_score(y,pred)),
            'macro_f1':float(f1_score(y,pred,labels=[0,1,2],average='macro',zero_division=0)),
            'log_loss':float(log_loss(y,p,labels=[0,1,2])), 'erro_ordinal':float(np.abs(y-pred).mean()),
            'brier_multiclasse':float(np.mean(np.sum((p-np.eye(3)[y])**2,axis=1)))}

def export_predictions(df,y,m,filename):
    p,pred,s,c,contrib=m.predict(df)
    out=df[['empresa_id','imovel_id']].copy()
    out['referencia_criterios']=PLANOS[y];out['plano_indicado']=PLANOS[pred];out['score']=s
    for k,pl in enumerate(PLANOS):out['p_'+pl]=p[:,k]
    out['acertou_referencia']=y==pred
    out.to_csv(OUT/filename,index=False)
    return out,p,pred,s,c,contrib

def main():
    train_path=ROOT/'dados/preparados/base_desenvolvimento.csv'
    dev=pd.read_csv(train_path)
    splits=list(GroupKFold(n_splits=3).split(dev,groups=dev.empresa_id))
    # Fixar desenho antes de ler o teste externo. Quantis são estimados apenas no treino de cada dobra.
    protocol={'versao':'ordinal_mock_v1','seed':20261028,'cenarios':CENARIOS,'especificacoes':SPECS,'penalidades':[.1,1.,10.],
              'selecao':'menor log_loss média nas 3 dobras agrupadas; apenas cenário central',
              'regra_decisao':'mediana ordinal; score=sigmoid(X beta)',
              'origem_rotulos':'politica_proposta_do_hackathon; nao observados',
              'hash_desenvolvimento':hashlib.sha256(train_path.read_bytes()).hexdigest()}
    save('protocolo_pre_teste.json',protocol)
    cv=[]; oof={}; models={}
    for nome,cols in SPECS.items():
        for alpha in [.1,1.,10.]:
            key=f'{nome}|{alpha}'; records=[]
            for fold,(ia,ib) in enumerate(splits):
                a=dev.iloc[ia];b=dev.iloc[ib];cr=criterios(a);ya=rotular(a,cr);yb=rotular(b,cr)
                assert not set(a.empresa_id)&set(b.empresa_id)
                m=Ordinal(cols,alpha).fit(a,ya);p,pred,s,c,_=m.predict(b)
                cv.append({'modelo':nome,'alpha':alpha,'dobra':fold,**measures(yb,p,pred),'corte1':c[0],'corte2':c[1]})
                records.append((ib,yb,p,pred))
            oof[key]=records
            print('CV concluída:',key,flush=True)
    cv=pd.DataFrame(cv);cv.to_csv(OUT/'comparacao_cv.csv',index=False)
    rank=cv.groupby(['modelo','alpha']).mean(numeric_only=True).sort_values('log_loss')
    rank.to_csv(OUT/'ranking_cv.csv'); chosen,alpha=rank.index[0];cols=SPECS[chosen]
    cr=criterios(dev);y=rotular(dev,cr);m=Ordinal(cols,alpha).fit(dev,y)
    save('criterios_congelados.json',cr)
    export_predictions(dev,y,m,'scores_desenvolvimento_ajuste.csv')
    # Sensibilidade exclusivamente dentro do desenvolvimento. Não escolhe hipótese pela acurácia.
    sensitivity=[]; sensitivity_coefs=[]
    for scenario in CENARIOS:
        oof_pred=np.empty(len(dev),int); oof_score=np.empty(len(dev));oof_y=np.empty(len(dev),int);oof_p=np.empty((len(dev),3))
        for ia,ib in splits:
            a=dev.iloc[ia];b=dev.iloc[ib];cc=criterios(a,scenario)
            mm=Ordinal(cols,alpha).fit(a,rotular(a,cc))
            pp,pr,ss,_,_=mm.predict(b)
            oof_pred[ib]=pr;oof_score[ib]=ss;oof_y[ib]=rotular(b,cc);oof_p[ib]=pp
        if scenario=='central':ref_pred=oof_pred.copy();ref_score=oof_score.copy();ref_y=oof_y.copy()
        cc=criterios(dev,scenario);mm=Ordinal(cols,alpha).fit(dev,rotular(dev,cc));cuts=expit(mm.thresholds)
        sensitivity.append({'cenario':scenario,**measures(oof_y,oof_p,oof_pred),
                            'mudanca_recomendacao_oof':float(np.mean(oof_pred!=ref_pred)),
                            'mudanca_referencia_oof':float(np.mean(oof_y!=ref_y)),
                            'variacao_media_score_oof':float(np.abs(oof_score-ref_score).mean()),
                            'corte1':cuts[0],'corte2':cuts[1],**{f'regra_{k}':v for k,v in cc.items()}})
        sensitivity_coefs.extend({'cenario':scenario,'termo':name,'peso':float(w)} for name,w in zip(mm.names,mm.beta))
    pd.DataFrame(sensitivity).to_csv(OUT/'sensibilidade_criterios.csv',index=False)
    pd.DataFrame(sensitivity_coefs).to_csv(OUT/'pesos_por_cenario.csv',index=False)
    # Diagnóstico comparativo: ordinal exige mesma direção nos dois limites; multinomial é mais flexível.
    checks=[]
    for ia,ib in splits:
        a=dev.iloc[ia];b=dev.iloc[ib];cc=criterios(a);ya=rotular(a,cc);yb=rotular(b,cc)
        mm=Ordinal(cols,alpha).fit(a,ya)
        flex=LogisticRegression(C=1/alpha,max_iter=1000).fit(mm.design(a),ya)
        pp=flex.predict_proba(mm.design(b));checks.append(measures(yb,pp,pp.argmax(axis=1)))
    save('diagnostico_multinomial_cv.json',{'metricas_medias':pd.DataFrame(checks).mean().to_dict(),
         'observacao':'Comparador flexível; não é teste formal de chances proporcionais. Não substitui automaticamente o índice ordinal.'})
    # Bootstrap por empresa condicionado à transformação e aos rótulos congelados.
    rng=np.random.default_rng(20261028);x=m.design(dev);groups=dev.groupby('empresa_id').indices;keys=list(groups)
    boots=[]
    for k in range(100):
        ix=np.concatenate([groups[g] for g in rng.choice(keys,len(keys),replace=True)])
        fit=minimize(objetivo,m.opt.x,args=(x[ix],y[ix],alpha),jac=True,method='L-BFGS-B',options={'maxiter':800,'ftol':1e-9})
        if fit.success:boots.append(fit.x)
    assert len(boots)>=90
    boots=np.array(boots);low,high=np.quantile(boots[:,:-2],[.025,.975],axis=0)
    weights=pd.DataFrame({'termo':m.names,'peso_beta':m.beta,'ic_bootstrap_2_5':low,'ic_bootstrap_97_5':high,
                          'sinal_estavel_condicional':(low>0)|(high<0),
                          'media_abs_contribuicao_treino':np.mean(np.abs(x*m.beta),axis=0)})
    weights.to_csv(OUT/'pesos_e_estabilidade.csv',index=False)
    bootcuts=expit(np.column_stack([boots[:,-2],boots[:,-2]+np.logaddexp(0,boots[:,-1])+1e-4]))
    save('bootstrap.json',{'replicas_validas':len(boots),'ic_cortes':np.quantile(bootcuts,[.025,.975],axis=0).tolist(),
                         'limite':'Intervalos condicionais à política, variáveis e transformação escolhidas. Não são significância confirmatória nem validação comercial.'})
    # Exportar modelo congelado ANTES de carregar teste externo.
    artifact={'modelo':m,'criterios':cr,'protocolo':protocol,'especificacao':chosen,'alpha':alpha}
    model_path=OUT/'modelo_ordinal.pkl';model_path.write_bytes(pickle.dumps(artifact))
    freeze={'modelo':chosen,'alpha':alpha,'variaveis':cols,'cortes':expit(m.thresholds).tolist(),
            'hash_modelo':hashlib.sha256(model_path.read_bytes()).hexdigest(),'hash_protocolo':hashlib.sha256((OUT/'protocolo_pre_teste.json').read_bytes()).hexdigest()}
    save('congelamento_antes_teste.json',freeze)
    # Agora, e somente agora, avaliar a base fornecida como teste comum.
    test_path=ROOT/'dados/preparados/base_teste_comum.csv';test=pd.read_csv(test_path)
    assert not set(dev.empresa_id)&set(test.empresa_id)
    yt=rotular(test,cr);predfile,p,pred,s,c,contrib=export_predictions(test,yt,m,'scores_teste_comum.csv')
    pd.DataFrame(confusion_matrix(yt,pred,labels=[0,1,2]),index=PLANOS,columns=PLANOS).to_csv(OUT/'matriz_confusao_teste.csv')
    freq=np.bincount(y,minlength=3)/len(y);base_p=np.tile(freq,(len(test),1))
    result={'natureza':'CONCORDANCIA COM CRITERIOS DO PROTOTIPO NA BASE MOCK',**freeze,
            'n_desenvolvimento':len(dev),'n_teste':len(test),'empresas_teste':test.empresa_id.nunique(),
            'cv_escolhido':rank.iloc[0].to_dict(),'teste':measures(yt,p,pred),
            'baseline_frequencias_treino':measures(yt,base_p,np.repeat(freq.argmax(),len(test))),
            'distribuicao_referencia_treino':dict(zip(PLANOS,np.bincount(y,minlength=3).tolist())),
            'distribuicao_referencia_teste':dict(zip(PLANOS,np.bincount(yt,minlength=3).tolist())),
            'hash_teste':hashlib.sha256(test_path.read_bytes()).hexdigest(),'elegibilidade':'NAO_AVALIADA'}
    # Incerteza de concordância: reamostragem agrupada dos casos de teste; sem retreino.
    tg=test.groupby('empresa_id').indices;tkeys=list(tg);acc=[]
    for _ in range(1000):
        ix=np.concatenate([tg[g] for g in rng.choice(tkeys,len(tkeys),replace=True)])
        acc.append(float(np.mean(yt[ix]==pred[ix])))
    result['ic95_acuracia_teste_bootstrap_empresa']=np.quantile(acc,[.025,.975]).tolist()
    save('resultado_final.json',result)
    # Casos não selecionados por acerto: primeiro de cada classe e primeiro erro de cada classe.
    ids=[]
    for cl in range(3):
        for mask in [yt==cl,(yt==cl)&(pred!=yt)]:
            poss=np.flatnonzero(mask)
            if len(poss):ids.append(int(poss[0]))
    predfile.iloc[list(dict.fromkeys(ids))].to_csv(OUT/'casos_explicados.csv',index=False)
    profiles=[]
    for i,row in test.iterrows():
        reasons=[{'variavel':name,'contribuicao_z':float(v)} for name,v in zip(m.names,contrib[i])]
        reasons.sort(key=lambda r:abs(r['contribuicao_z']),reverse=True)
        profiles.append({'versao':'ordinal_mock_v1','empresa_id':row.empresa_id,'imovel_id':row.imovel_id,
                         'status':'EXPERIMENTAL_BASE_MOCK','score':float(s[i]),'plano_sugerido':str(PLANOS[pred[i]]),
                         'cortes':c.tolist(),'probabilidades_referencia':dict(zip(PLANOS,p[i].tolist())),
                         'contribuicoes':reasons,'elegibilidade':'NAO_AVALIADA',
                         'perguntas':['Quantos empregados trabalham neste estabelecimento?','Quais bens e estoques estão efetivamente neste endereço?','Há necessidade de cobertura de vidros e exposição a vendaval?'],
                         'fontes':['catalogo_coberturas_fixas_planos.csv','criterios_congelados.json'],
                         'limites':['Aprendeu critérios propostos, não contratos ou necessidades confirmadas.','Não é probabilidade de compra nem garantia de cobertura.']})
    (OUT/'perfis_rag_teste.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False,allow_nan=False)+'\n' for r in profiles))
    # Checks numéricos e de contrato.
    rr=np.random.default_rng(1);xx=rr.normal(size=(20,3));yy=np.tile(np.arange(3),7)[:20];theta=np.r_[.1,.2,-.2,-.5,.7]
    err=check_grad(lambda t:objetivo(t,xx,yy,1.)[0],lambda t:objetivo(t,xx,yy,1.)[1],theta)
    checks={'gradiente_analitico':bool(err<1e-5),'probabilidades_somam_um':bool(np.allclose(p.sum(axis=1),1)),
            'probabilidades_validas':bool(((p>=0)&(p<=1)).all()),'score_no_intervalo':bool(((s>=0)&(s<=1)).all()),
            'cortes_ordenados':bool(0<c[0]<c[1]<1),'faixas_reproduzem_mediana':bool(np.array_equal(pred,np.searchsorted(c,s,side='right'))),
            'contribuicoes_reproduzem_score':bool(np.allclose(expit(contrib.sum(axis=1)),s)),
            'empresas_separadas':not bool(set(dev.empresa_id)&set(test.empresa_id)),
            'modelo_nao_alterado_apos_teste':hashlib.sha256(model_path.read_bytes()).hexdigest()==freeze['hash_modelo'],
            'exportacao_completa_rag':len(profiles)==len(test),'tres_classes_teste':len(np.unique(yt))==3}
    assert all(checks.values()),checks
    save('testes_execucao.json',checks)
    print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
