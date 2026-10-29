"""Prepara piloto sem criar referência de plano ou score fictícios."""
import argparse
import json
from pathlib import Path
import pandas as pd


def executar(root):
    base=pd.read_csv(root/'dados/preparados/base_desenvolvimento.csv')
    part=pd.read_csv(root/'resultados/particao_empresas_proposta.csv')
    df=base.merge(part,on=['empresa_id','imovel_id'],validate='one_to_one')
    selecionados=[]
    for grupo in sorted(df.grupo_atividade.unique()):
        for bloco,n in [('treino_desenvolvimento',10),('avaliacao_reservada',5)]:
            candidatos=df[df.grupo_atividade.eq(grupo)&df.particao_proposta.eq(bloco)]
            candidatos=candidatos.sort_values(['empresa_id','imovel_id']).drop_duplicates('empresa_id')
            selecionados.append(candidatos.sample(n=n,random_state=20261028))
    piloto=pd.concat(selecionados).sort_values(['grupo_atividade','empresa_id']).reset_index(drop=True)
    assert len(piloto)==150 and piloto.empresa_id.nunique()==150
    perguntas=['necessita_roubo_furto','necessita_vendaval','necessita_rc_empregador','necessita_quebra_vidros']
    for col in perguntas:piloto[col]='NAO_CONFIRMADO'
    for col in ['plano_referencia','justificativa','revisor','fonte_criterio','versao_criterio','pergunta_pendente']:
        piloto[col]=''
    piloto['status_revisao']='PENDENTE'
    piloto['elegibilidade_revisada']='NAO_CONFIRMADO'
    destino=root/'dados/rotulos/piloto_150';destino.mkdir(parents=True,exist_ok=True)
    for bloco,arquivo in [('treino_desenvolvimento','casos_desenvolvimento_100.csv'),('avaliacao_reservada','casos_avaliacao_50.csv')]:
        saida=destino/arquivo
        if saida.exists():raise FileExistsError(f'Não sobrescrever revisão existente: {saida}')
        piloto[piloto.particao_proposta.eq(bloco)].drop(columns=['plano_recomendado','elegivel']).to_csv(saida,index=False,encoding='utf-8-sig')
    perfil=piloto.iloc[0]
    exemplo={
        'versao_contrato':'1.0',
        'cliente':{'empresa_id':perfil.empresa_id,'imovel_id':perfil.imovel_id},
        'status':'AGUARDANDO_REFERENCIA',
        'score':None,'cortes_score':None,'plano_sugerido':None,'probabilidades_por_plano':None,
        'fatos':[{'campo':c,'valor':perfil[c].item() if hasattr(perfil[c],'item') else perfil[c],
                  'origem':'base_desenvolvimento.csv','granularidade':'empresa' if c.endswith('_empresa') or c=='grupo_atividade' else 'estabelecimento'}
                 for c in ['grupo_atividade','faturamento_mensal_empresa','funcionarios_estimados_empresa','estoque_medio_estimado']],
        'perguntas_confirmacao':[
            {'codigo':'NECESSIDADES_COBERTURAS','pergunta':'Quais necessidades de proteção foram identificadas para este estabelecimento?','motivo':'Definir referência de cobertura antes de recomendar plano'},
            {'codigo':'FUNCIONARIOS_LOCAIS','pergunta':'Quantos funcionários trabalham neste endereço?','motivo':'A quantidade disponível refere-se à empresa inteira'}],
        'faixas_monetarias':None,'fontes_produto':[],
        'limitacoes':['Não há modelo de planos treinado e validado neste exemplo.','Valores da base são sintéticos; nenhuma probabilidade de compra foi estimada.'],
    }
    (root/'resultados/perfil_rag_exemplo_sem_inferencia.json').write_text(json.dumps(exemplo,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    resumo={'total':len(piloto),'desenvolvimento':100,'avaliacao':50,'empresas_unicas':piloto.empresa_id.nunique(),
            'rotulos_criados':0,'por_atividade':piloto.grupo_atividade.value_counts().to_dict()}
    (root/'resultados/piloto_rotulagem_rag.json').write_text(json.dumps(resumo,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(resumo,ensure_ascii=False,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--projeto',type=Path,required=True)
    executar(p.parse_args().projeto)
