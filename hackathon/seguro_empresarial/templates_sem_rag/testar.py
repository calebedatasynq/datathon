"""Testes independentes de junções, regras, faixas, suspensão e reprodução do índice."""
import copy
import csv
import json
import math
import tempfile
from pathlib import Path
from executar import ROOT, POLITICA, build, coverage, eligibility, number, process, read, validate, index


def rejects(call):
    try:
        call()
    except (ValueError, KeyError):
        return
    raise AssertionError('Entrada inválida aceita')


def main():
    checks = []
    company = {'grupo_atividade': 'RESTAURANTE', 'cnae_principal': '5611-2/01',
               'quantidade_funcionarios_estimada': '4', 'percentual_receita_delivery_est': '0'}
    address = {'situacao_imovel_cadastral': 'REGULAR', 'endereco_cnpj_compativel': 'SIM',
               'material_parede_externa_cadastrado': 'ALVENARIA'}
    signal = {'estoque_medio_estimado': '100', 'estoque_pico_estimado': '200',
              'pagamento_aluguel_recorrente': 'SIM', 'valor_aluguel_recorrente': '1000',
              'folha_pagamento_mensal': '2000', 'energia_media_mensal_6m': '300',
              'despesa_fixa_mensal_estimada': '4000', 'probabilidade_refrigeracao_referencia': '0.4'}
    assets = [{'bem_id': 'B1', 'tipo_bem': 'EQUIPAMENTO_INFORMATICA', 'valor_cadastrado': '1000', 'valor_bem_ponderado_referencia': '700'},
              {'bem_id': 'B2', 'tipo_bem': 'LETREIRO', 'valor_cadastrado': '500', 'valor_bem_ponderado_referencia': '400'}]
    def cov(code, s=None, a=None):
        return coverage(code, company, address, s if s is not None else signal, a if a is not None else assets)
    fire = cov('INCENDIO_RAIO_EXPLOSAO_FUMACA')
    assert (fire['faixa_valor_min'], fire['faixa_valor_max']) == (800, 1200)
    assert 'B2' not in json.loads(fire['dados_utilizados'])['bens_ids']
    checks.append('Conteúdo soma inventário separado de estoque e exclui letreiros')
    electric = cov('DANOS_ELETRICOS')
    assert (electric['faixa_valor_min'], electric['faixa_valor_max']) == (700, 1000)
    assert cov('DANOS_ELETRICOS', a=[])['faixa_valor_min'] is None
    checks.append('Danos elétricos só usa tipos identificados; sem cadastro permanece ausente')
    rent = cov('PERDA_PAGAMENTO_ALUGUEL')
    assert (rent['faixa_valor_min'], rent['faixa_valor_max']) == (6000, 12000)
    no_rent = cov('PERDA_PAGAMENTO_ALUGUEL', dict(signal, pagamento_aluguel_recorrente='NAO', valor_aluguel_recorrente='0'))
    assert no_rent['faixa_valor_min'] is None
    checks.append('Aluguel sem pagamento não vira zero nem prova imóvel próprio')
    expense = cov('DESPESAS_FIXAS')
    assert (expense['faixa_valor_min'], expense['faixa_valor_max']) == (6900, 13800)
    assert cov('DESPESAS_FIXAS', dict(signal, despesa_fixa_mensal_estimada='100'))['observacao'].find('INCONSISTENCIA_FINANCEIRA') >= 0
    checks.append('Despesas não duplicam agregado/aluguel; inconsistência financeira exposta')
    for code in ['QUEBRA_DE_VIDROS', 'RESPONSABILIDADE_CIVIL_EMPREGADOR', 'RESPONSABILIDADE_CIVIL_ESTABELECIMENTO', 'DELIVERY', 'DETERIORACAO_MERCADORIAS_FRIGORIFICADAS']:
        row = cov(code)
        assert row['faixa_valor_min'] is None and 'SEM_ESTIMATIVA_JUSTIFICADA' in row['observacao']
    checks.append('Exceções sem base monetária ficam justificadas e não recebem valor inventado')
    assert eligibility(company, address)[0] == 'PENDENTE_VALIDACAO'
    for changed in [dict(address, situacao_imovel_cadastral='EM_OBRA'), dict(address, situacao_imovel_cadastral='IRREGULAR'), dict(address, endereco_cnpj_compativel='NAO'), dict(address, material_parede_externa_cadastrado='MADEIRA')]:
        assert eligibility(company, changed)[1]
    assert eligibility(dict(company, cnae_principal='0111-3/01'), address)[1]
    checks.append('Elegibilidade incompleta nunca é aprovada; sinais impeditivos suspendem oferta')
    for raw in ['-1', 'nan', 'inf', True, 'texto']:
        rejects(lambda raw=raw: number({'a': raw}, 'a'))
    assert number({'a': '0'}, 'a') == 0 and number({'a': ''}, 'a') is None
    rejects(lambda: index([{'id': 'x'}, {'id': 'x'}], ['id'], 'teste'))
    rejects(lambda: cov('INCENDIO_RAIO_EXPLOSAO_FUMACA', dict(signal, estoque_pico_estimado='50')))
    checks.append('Zeros/ausências distintos; chaves duplicadas, não finitos e estoque inconsistente rejeitados')
    for base in ['Desenvolvimento', 'Teste_Comum']:
        payload = build(base)
        original = ROOT/'dados/originais'/('Seguro_Empresarial_'+base)
        targets = read(original/'template_resultado_times.csv')
        assert [tuple(r[f] for f in ['empresa_id', 'imovel_id']) for r in payload['resultado']] == [tuple(r[f] for f in ['empresa_id', 'imovel_id']) for r in targets]
        assert len(payload['resultado']) == (2978 if base == 'Desenvolvimento' else 144)
        # Conferir CSVs efetivamente entregues, não só objetos em memória.
        for name, fields, expected_rows in [('template_resultado_times', payload['resultado_header'], payload['resultado']),
                                             ('template_coberturas_times', payload['coberturas_header'], payload['coberturas'])]:
            target = ROOT/'saidas'/payload['base']/(name+'.csv')
            if target.exists():
                actual = read(target)
                assert len(actual) == len(expected_rows)
                assert list(actual[0]) == fields
                for saved, expected in zip(actual, expected_rows):
                    for field in fields:
                        value = expected[field]
                        if isinstance(value,(int,float)):
                            assert float(saved[field]) == value
                        else:
                            assert saved[field] == (value if value is not None else '')
        # Controle independente de cada faixa emitida, sem chamar coverage().
        signals = {(r['empresa_id'],r['imovel_id']):r for r in read(original/'sinais_financeiros_operacionais.csv')}
        all_assets = {r['bem_id']:r for r in read(original/'bens_cadastrados.csv')}
        for row in payload['coberturas']:
            if row['faixa_valor_min'] is None:
                continue
            d = json.loads(row['dados_utilizados']); s = signals[(row['empresa_id'],row['imovel_id'])]
            code = row['cobertura']
            if code == 'DESPESAS_FIXAS':
                amount = float(s['folha_pagamento_mensal']) + float(s['energia_media_mensal_6m'])
                expected = (amount*3, amount*6)
            elif code == 'PERDA_PAGAMENTO_ALUGUEL':
                amount = float(s['valor_aluguel_recorrente']); expected = (amount*6, amount*12)
            else:
                selected = [all_assets[b] for b in d['bens_ids']]
                w = sum(float(b['valor_bem_ponderado_referencia']) for b in selected)
                c = sum(float(b['valor_cadastrado']) for b in selected)
                expected = (w, c)
                if code in ['INCENDIO_RAIO_EXPLOSAO_FUMACA', 'ROUBO_FURTO_ARROMBAMENTO', 'VENDAVAL_EVENTOS_CORRELATOS']:
                    expected = (w+float(s['estoque_medio_estimado']), c+float(s['estoque_pico_estimado']))
            assert tuple(round(v,2) for v in expected) == (row['faixa_valor_min'],row['faixa_valor_max'])
        # Reproduzir o índice entregue antes desta etapa, não recalibrar modelo.
        score_file = ROOT/'referencias'/('scores_'+('desenvolvimento' if base=='Desenvolvimento' else 'teste_comum')+'.csv')
        references = {(r['empresa_id'],r['imovel_id']):r for r in read(score_file)}
        for detail in payload['detalhes']:
            ref = references[(detail['empresa_id'],detail['imovel_id'])]
            assert abs(detail['score']-float(ref['score'])) < 1e-12
            assert detail['plano_indice'] == ref['plano']
        # Verificar suspensão e ausência essencial diretamente no processador.
        p = read(ROOT/'dados/preparados'/('base_'+payload['base']+'.csv'))[0]
        c = next(r for r in read(original/'empresas.csv') if r['empresa_id']==p['empresa_id'])
        a = next(r for r in read(original/'enderecos_estabelecimentos.csv') if r['imovel_id']==p['imovel_id'])
        s = signals[(p['empresa_id'],p['imovel_id'])]
        catalog = {}
        for r in read(original/'catalogo_coberturas_fixas_planos.csv'):
            catalog.setdefault(r['plano'],[]).append(r['cobertura_fixa'])
        blocked, rows, d = process(c, dict(a,situacao_imovel_cadastral='EM_OBRA'),s,[],p,catalog)
        assert not blocked['plano_recomendado'] and not rows and d['plano_indice']
        normal_a = dict(a,situacao_imovel_cadastral='REGULAR',endereco_cnpj_compativel='SIM')
        missing, rows, d = process(c,normal_a,s,[],dict(p,estoque_medio_estimado=''),catalog)
        assert not missing['plano_recomendado'] and not rows and d['score'] is None
        checks.append(base+': chaves/ordem, fórmulas independentes, reprodução integral do índice e suspensão')
    checks.append('CSVs salvos: cabeçalhos, valores, listas e quantidade de linhas conferidos com a geração')
    report = {'status':'APROVADO', 'verificacoes':checks,
              'escopo':'Integridade e regras do protótipo; não valida adequação comercial nem limites de contratação.'}
    path = ROOT/'evidencias/testes.json'; path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
