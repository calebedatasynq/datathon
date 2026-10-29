"""Auditoria independente dos artefatos entregues; não ajusta o modelo."""
from pathlib import Path
import json,hashlib,sys,pickle
import numpy as np
import pandas as pd
from sklearn.metrics import log_loss,accuracy_score
P=Path('/home/lucas/Documentos/hackathon/seguro_empresarial/indice_regressao_v2');O=P/'resultados'
sys.path.insert(0,str(P))
from modelo import rotular,PLANOS
manifest=json.loads((P/'manifesto_sha256.json').read_text())
checks={'arquivos_preservados':all(hashlib.sha256((P/k).read_bytes()).hexdigest()==v for k,v in manifest.items())}
a=pickle.loads((O/'modelo_ordinal.pkl').read_bytes());m=a['modelo']
tr=pd.read_csv(P.parent/'dados/preparados/base_desenvolvimento.csv');te=pd.read_csv(P.parent/'dados/preparados/base_teste_comum.csv')
r=json.loads((O/'resultado.json').read_text());pred=pd.read_csv(O/'scores_teste.csv');y=rotular(te,a['criterios']);probs,h,s,c,con=m.predict(te)
checks.update({'sem_empresa_compartilhada':not bool(set(tr.empresa_id)&set(te.empresa_id)), 'oito_variaveis':len(m.colunas)==8,'144_scores_reproduzidos':np.allclose(s,pred.score),'144_referencias_reproduzidas':np.array_equal(PLANOS[y],pred.referencia), '144_planos_reproduzidos':np.array_equal(PLANOS[h],pred.indicado),'acuracia_confere':abs(accuracy_score(y,h)-r['metricas_teste']['acuracia'])<1e-12,'log_loss_confere':abs(log_loss(y,probs,labels=[0,1,2])-r['metricas_teste']['log_loss'])<1e-12,'formula_confere':np.allclose(1/(1+np.exp(-con.sum(axis=1))),s)})
cv=pd.read_csv(O/'cada_iteracao_e_dobra.csv');rank=pd.read_csv(O/'ranking_cv.csv')
checks['27_ajustes_completos']=len(cv)==27 and len(rank)==9
checks['r2_treino_formula']=np.allclose(cv.treino_indice_1_menos_LL_LL0,1-cv.treino_log_loss/cv.treino_log_loss_nulo)
checks['r2_validacao_formula']=np.allclose(cv.validacao_indice_1_menos_LL_LL0,1-cv.validacao_log_loss/cv.validacao_log_loss_nulo)
checks['selecao_por_cv']=rank.iloc[0].iteracao==r['selecionado'] and rank.iloc[0].alpha==r['alpha']
nb=json.loads((P/'04_iteracoes_8_9_10_variaveis.ipynb').read_text())
checks['notebook_executado_sem_erros']=all(c['execution_count'] is not None and all(v['output_type']!='error' for v in c['outputs']) for c in nb['cells'] if c['cell_type']=='code')
checks={k:bool(v) for k,v in checks.items()};assert all(checks.values()),checks
output={'data':'2026-10-28','verificacoes':checks,'conclusao':'CONSISTENCIA TECNICA VERIFICADA PARA APRESENTACAO DO EXPERIMENTO MOCK; NAO VALIDACAO COMERCIAL'}
Path('/tmp/auditoria_indice_v2.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(output,ensure_ascii=False,indent=2))
