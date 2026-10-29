"""Aplicar modelo congelado a um CSV preparado, sem retreino nem rotulagem."""
import argparse,json,pickle
from pathlib import Path
import numpy as np
import pandas as pd
from modelo import PLANOS

def inferir(arquivo,modelo,saida):
    artifact=pickle.loads(Path(modelo).read_bytes());m=artifact['modelo'];df=pd.read_csv(arquivo)
    required=['empresa_id','imovel_id']+m.colunas
    missing=set(required)-set(df.columns)
    if missing:raise ValueError(f'Colunas ausentes: {sorted(missing)}')
    if df[['empresa_id','imovel_id']].isna().any().any() or df.duplicated(['empresa_id','imovel_id']).any():raise ValueError('Chaves ausentes ou repetidas')
    for c in m.colunas:
        if c not in ['grupo_atividade','tipo_unidade']:
            df[c]=pd.to_numeric(df[c],errors='raise')
            if (df[c].dropna()<0).any() or np.isinf(df[c].dropna()).any():raise ValueError(f'Valor inválido em {c}')
    p,pred,s,c,contrib=m.predict(df)
    rows=[]
    for i,row in df.iterrows():
        rows.append({'versao':'ordinal_mock_v1','empresa_id':row.empresa_id,'imovel_id':row.imovel_id,
                     'status':'EXPERIMENTAL_BASE_MOCK','score':float(s[i]),'plano_sugerido':str(PLANOS[pred[i]]),
                     'cortes':c.tolist(),'probabilidades_referencia':dict(zip(PLANOS,p[i].tolist())),
                     'contribuicoes':[{'variavel':name,'contribuicao_z':float(v)} for name,v in zip(m.names,contrib[i])],
                     'campos_ausentes':df.loc[i,m.colunas][df.loc[i,m.colunas].isna()].index.tolist(),
                     'elegibilidade':'NAO_AVALIADA',
                     'limite':'Indicação experimental aprendida de critérios do hackathon; não é probabilidade de compra.'})
    Path(saida).write_text(''.join(json.dumps(r,ensure_ascii=False,allow_nan=False)+'\n' for r in rows))
    return rows

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('csv');a.add_argument('--modelo',default=str(Path(__file__).parent/'resultados/modelo_ordinal.pkl'));a.add_argument('--saida',required=True)
    v=a.parse_args();inferir(v.csv,v.modelo,v.saida)
