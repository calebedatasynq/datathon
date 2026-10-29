"""Inferência portátil da regressão ordinal v2. Apenas biblioteca padrão Python 3.9+."""
import argparse
import csv
import json
import math
from pathlib import Path

ROOT=Path(__file__).resolve().parent
FORMULA=json.loads((ROOT/'modelo/formula_completa.json').read_text(encoding='utf-8'))
PLANOS=['ESSENCIAL','PRATICO','TOTAL']
CORE=['funcionarios_estimados_empresa','estoque_medio_estimado','valor_bens_ponderado_estabelecimento']

def sigmoid(z):
    if z>=0:return 1/(1+math.exp(-z))
    e=math.exp(z);return e/(1+e)

def score_empresa(empresa):
    """Recebe dict. Retorna perfil; ausências essenciais suspendem a recomendação."""
    if not isinstance(empresa,dict):raise ValueError('Entrada deve ser um objeto JSON')
    for key in ['empresa_id','imovel_id']:
        if not isinstance(empresa.get(key),str) or not empresa[key].strip():raise ValueError('Identificador ausente ou inválido: '+key)
    f=FORMULA;values=[];missing=[];warnings=[];questions=[]
    for j,key in enumerate(f['colunas_numericas']):
        raw=empresa.get(key)
        if raw is None or raw=='':
            missing.append(key);values.append(f['medianas_imputacao'][j])
        else:
            if isinstance(raw,bool):raise ValueError('Booleano não é número válido: '+key)
            try:v=float(raw)
            except (TypeError,ValueError):raise ValueError('Número inválido: '+key)
            if not math.isfinite(v) or v<0:raise ValueError('Número negativo ou não finito: '+key)
            values.append(v)
    cats=[];unknown=[]
    for key,options in zip(f['colunas_categoricas'],f['categorias']):
        raw=empresa.get(key)
        if raw not in options:unknown.append(key)
        cats.extend(float(raw==v) for v in options[1:])
    for key in missing:questions.append('Confirmar '+key)
    for key in unknown:questions.append('Informar categoria conhecida para '+key)
    out={'versao_modelo':'ordinal_mock_v2','versao_interface':'1.0','empresa_id':empresa['empresa_id'],'imovel_id':empresa['imovel_id'],
         'status':'EXPERIMENTAL_BASE_MOCK','score':None,'plano_sugerido':None,'cortes':f['cortes'],
         'probabilidades_referencia':None,'contribuicoes':[],'campos_ausentes':missing,'categorias_desconhecidas':unknown,
         'avisos':warnings,'perguntas_confirmacao':questions,'elegibilidade':'NAO_AVALIADA',
         'fontes':['modelo/formula_completa.json','modelo/criterios_referencia.json','documentacao/COBERTURAS_E_LIMITES.md'],
         'limites':['Referências construídas para o hackathon; não representam plano ideal observado.','Score não é probabilidade de compra.']}
    if any(k in missing for k in CORE) or unknown:
        out['status']='PRECISA_CONFIRMACAO';warnings.append('Recomendação suspensa: dados essenciais ausentes ou categoria fora do treino.')
        return out
    if missing:warnings.append('Dados opcionais imputados pela mediana do treino; confirmar antes da decisão comercial.')
    # Guarda operacional fora do intervalo observado, não muda a matemática do score.
    ranges=json.loads((ROOT/'modelo/intervalos_observados.json').read_text(encoding='utf-8'))
    for key,v in zip(f['colunas_numericas'],values):
        if key not in missing and not ranges[key]['min']<=v<=ranges[key]['max']:
            warnings.append('Valor fora do intervalo observado no treino: '+key)
            questions.append('Confirmar valor informado de '+key)
    values.extend(float(f['colunas_numericas'][j] in missing) for j in f['indices_indicadores_ausencia'])
    numeric=[(math.log1p(v)-mean)/std for v,mean,std in zip(values,f['medias_apos_log1p'],f['desvios_apos_log1p'])]
    x=[v for v,keep in zip(numeric+cats,f['mascara_colunas']) if keep]
    contributions=[b*v for b,v in zip(f['pesos'],x)]
    z=sum(contributions);t1,t2=f['limiares_z'];p0=sigmoid(t1-z);p2=sigmoid(z-t2);p1=max(0.,1-p0-p2)
    p=[p0,p1,p2];total=sum(p);p=[v/total for v in p]
    s=sigmoid(z);cls=int(z>=t1)+int(z>=t2)
    out.update(score=s,plano_sugerido=PLANOS[cls],probabilidades_referencia=dict(zip(PLANOS,p)),
        contribuicoes=[{'termo':name,'contribuicao_z':v} for name,v in zip(f['termos'],contributions)])
    out['distancia_ao_corte_mais_proximo']=min(abs(s-v) for v in f['cortes'])
    out['perguntas_confirmacao'].extend(['Quantos funcionários atuam neste endereço?','Quais coberturas o cliente precisa confirmar, incluindo vidros e vendaval?'])
    return out

def executar(entrada,saida):
    entrada=Path(entrada)
    if entrada.suffix.lower()=='.csv':
        with entrada.open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
    else:
        data=json.loads(entrada.read_text(encoding='utf-8'));rows=data if isinstance(data,list) else [data]
    seen=set();results=[]
    for row in rows:
        result=score_empresa(row);key=(result['empresa_id'],result['imovel_id'])
        if key in seen:raise ValueError('Empresa/estabelecimento repetido no lote: '+str(key))
        seen.add(key);results.append(result)
    saida=Path(saida);saida.parent.mkdir(parents=True,exist_ok=True)
    saida.write_text(''.join(json.dumps(v,ensure_ascii=False,allow_nan=False)+'\n' for v in results),encoding='utf-8')
    return len(results)

if __name__=='__main__':
    cli=argparse.ArgumentParser(description=__doc__);cli.add_argument('--entrada',required=True);cli.add_argument('--saida',required=True);args=cli.parse_args()
    print(str(executar(args.entrada,args.saida))+' perfis gravados.')
