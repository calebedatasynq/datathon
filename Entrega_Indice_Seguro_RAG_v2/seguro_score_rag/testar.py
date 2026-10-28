"""Testes portáteis: execute python testar.py, sem instalar dependências."""
import csv,json,math,tempfile
from pathlib import Path
from score import score_empresa,executar,ROOT,FORMULA

def main():
    expected={}
    with (ROOT/'exemplos/referencia_numerica_3122.csv').open(encoding='utf-8',newline='') as f:
        for r in csv.DictReader(f):expected[(r['base'],r['empresa_id'],r['imovel_id'])]=r
    max_error=0.;count=0
    for base in ['base_desenvolvimento.csv','base_teste_comum.csv']:
        with (ROOT/'dados/preparados'/base).open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
        for row in rows:
            result=score_empresa(row);ref=expected[(base,row['empresa_id'],row['imovel_id'])]
            error=abs(result['score']-float(ref['score']));max_error=max(max_error,error)
            assert error<1e-12 and result['plano_sugerido']==ref['plano'],ref
            assert abs(sum(result['probabilidades_referencia'].values())-1)<1e-12
            for name,value in result['probabilidades_referencia'].items():assert abs(value-float(ref['p_'+name]))<1e-12
            count+=1
    assert count==3122
    sample=json.loads((ROOT/'exemplos/empresa.json').read_text(encoding='utf-8'))
    missing=dict(sample,funcionarios_estimados_empresa=None);assert score_empresa(missing)['score'] is None
    unknown=dict(sample,grupo_atividade='NOVO_SEGMENTO');assert score_empresa(unknown)['status']=='PRECISA_CONFIRMACAO'
    optional=dict(sample,area_m2=None);assert score_empresa(optional)['score'] is not None
    for bad in [-1,float('inf'),float('nan'),True,'abc']:
        try:score_empresa(dict(sample,estoque_medio_estimado=bad))
        except ValueError:pass
        else:raise AssertionError('Número inválido foi aceito')
    extreme=dict(sample,estoque_medio_estimado=1e20);assert score_empresa(extreme)['avisos']
    with tempfile.TemporaryDirectory() as tmp:
        p=Path(tmp);(p/'duplo.json').write_text(json.dumps([sample,sample]))
        try:executar(p/'duplo.json',p/'out.jsonl')
        except ValueError:pass
        else:raise AssertionError('Duplicata aceita')
        assert executar(ROOT/'exemplos/lote.csv',p/'out.jsonl')==3
    manifest=ROOT/'MANIFESTO_SHA256.json'
    if manifest.exists():
        import hashlib
        for name,digest in json.loads(manifest.read_text()).items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest,name
    print(json.dumps({'status':'APROVADO','registros_comparados':count,'erro_maximo_score':max_error,'probabilidades_e_planos':'REPRODUZIDOS','casos_limite':'APROVADOS','dependencias_externas':0},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
