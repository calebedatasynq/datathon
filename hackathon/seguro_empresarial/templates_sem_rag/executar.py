"""Gera os templates de desenvolvimento e teste sem rede, RAG ou dependências.

Python 3.9+. Leia LEIA_PRIMEIRO.md e documentacao/METODO.md.
"""
import argparse
import csv
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'indice'))
from score import score_empresa

POLITICA = json.loads((ROOT / 'politica.json').read_text(encoding='utf-8'))
BB = 'https://campanhas.bbseguros.com.br/seguro-empresarial/'
CG = 'https://assets-bbsegurosportal.bbseguros.com.br/2024-08/cg-seguro-empresarial-v_1-1.pdf?VersionId=F5j.aDPjl.ePJzIhjV.z1Y1Nbm0byQ6M'
MISSING = {'', 'NAO_DISPONIVEL', 'NAO_INFORMADO', 'DESCONHECIDO'}


def dump(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')


def read(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as stream:
        return list(csv.DictReader(stream))


def number(row, field):
    raw = row.get(field)
    if raw is None or raw in MISSING:
        return None
    if isinstance(raw, bool):
        raise ValueError('Booleano inválido: ' + field)
    v = float(raw)
    if not math.isfinite(v) or v < 0:
        raise ValueError('Número negativo/não finito: ' + field)
    return v


def key(row):
    return row['empresa_id'], row['imovel_id']


def index(rows, fields, label):
    out = {}
    for row in rows:
        k = tuple(row.get(f, '') for f in fields)
        if not all(k) or k in out:
            raise ValueError('Chave ausente/duplicada em ' + label + ': ' + str(k))
        out[k] = row
    return out


def join_unique(parts):
    return ' | '.join(dict.fromkeys(p for p in parts if p))


def asset_range(assets, types):
    chosen = [b for b in assets if b['tipo_bem'] in types]
    if not chosen:
        return None, None, chosen
    raw = [number(b, 'valor_cadastrado') for b in chosen]
    weighted = [number(b, 'valor_bem_ponderado_referencia') for b in chosen]
    if any(v is None for v in raw + weighted):
        return None, None, chosen
    if any(w > r + 1 for w, r in zip(weighted, raw)):
        raise ValueError('Valor ponderado de bem superior ao cadastrado')
    # Cenários de cadastro, não limites probabilísticos do valor em risco.
    return min(sum(weighted), sum(raw)), sum(raw), chosen


def eligibility(company, address):
    reasons = []
    cnae = ''.join(c for c in company.get('cnae_principal', '') if c.isdigit())
    # Só reconhecer CNAE rural sintaticamente válido. Não inventar reprovação por grupo.
    if len(cnae) == 7 and cnae[:2] in {'01', '02', '03'}:
        reasons.append('CNAE rural: confirmar atividade efetiva e enquadramento; oferta suspensa')
    situation = address.get('situacao_imovel_cadastral', '')
    if situation != 'REGULAR':
        reasons.append('Situação cadastral ' + (situation or 'ausente') + ': confirmar uso, obras e regularidade; oferta suspensa')
    material = address.get('material_parede_externa_cadastrado', '')
    if material in {'MADEIRA', 'COMBUSTIVEL', 'PREDOMINANTEMENTE_COMBUSTIVEL'}:
        reasons.append('Material externo combustível: validar aceitação; oferta suspensa')
    if address.get('endereco_cnpj_compativel') != 'SIM':
        reasons.append('Endereço divergente/sem confirmação: validar local do risco; oferta suspensa')
    questions = [
        'O estabelecimento está em operação regular, com atividade aceita e sem impedimento de uso ou tombamento?',
        'Paredes, telhado e demais elementos da construção atendem às condições do seguro, sem obra estrutural impeditiva?'
    ]
    if material in MISSING:
        questions[1] = 'Qual o material das paredes externas e do telhado? Há obra estrutural ou condição que impeça o uso?'
    return 'PENDENTE_VALIDACAO', reasons, questions


def location(address):
    signals = [('possui_termo_loja', 'LOJA'), ('possui_termo_sala', 'SALA'),
               ('possui_termo_galeria', 'GALERIA'), ('possui_termo_torre', 'TORRE')]
    found = [label for field, label in signals if address.get(field) == 'SIM']
    return '+'.join(found) + '_A_CONFIRMAR' if found else 'A_CONFIRMAR'


def coverage(code, company, address, signals, assets):
    kind = 'FIXA'
    lo = hi = None
    confidence = 'BAIXA'
    evidence = {}
    notes = ['Sugestão preliminar condicionada à elegibilidade e às condições contratuais.']
    rule = ''
    question = ''
    reason = ''
    if code in {'INCENDIO_RAIO_EXPLOSAO_FUMACA', 'ROUBO_FURTO_ARROMBAMENTO', 'VENDAVAL_EVENTOS_CORRELATOS'}:
        lo, hi, chosen = asset_range(assets, POLITICA['tipos_conteudo'])
        stock = number(signals, 'estoque_medio_estimado')
        peak = number(signals, 'estoque_pico_estimado')
        if peak is not None and stock is not None and peak < stock:
            raise ValueError('Estoque de pico inferior ao médio')
        if lo is not None and stock is not None and peak is not None:
            lo, hi = lo + stock, hi + peak
        else:
            lo = hi = None
        evidence = {'bens_ids': [b['bem_id'] for b in chosen],
                    'bens_ponderados': sum(number(b, 'valor_bem_ponderado_referencia') or 0 for b in chosen) if chosen else None,
                    'bens_cadastrados': sum(number(b, 'valor_cadastrado') or 0 for b in chosen) if chosen else None,
                    'estoque_medio': stock, 'estoque_pico': peak}
        rule = 'min=sum(bens_conteudo_ponderados)+estoque_medio; max=sum(bens_conteudo_cadastrados)+estoque_pico; exige inventário e estoque disponíveis'
        reason = 'Cenários de exposição do conteúdo cadastrado, com estoque médio versus de pico e vínculo ponderado versus integral.'
        question = 'Quais bens realmente estão neste endereço e qual seu valor de reposição? O estoque está separado dos bens? Deseja proteger prédio, conteúdo ou ambos?'
        notes += ['ESCOPO_PARCIAL_CONTEUDO: prédio não dimensionado por falta de custo de reconstrução e interesse segurado.',
                  'Não representa inventário completo, LMI aceito, previsão de perda ou valor garantido de indenização.',
                  'Letreiros separados do conteúdo genérico. Não somar faixas entre coberturas que protegem os mesmos bens.']
        if code == 'VENDAVAL_EVENTOS_CORRELATOS':
            notes.append('Cenário de reposição integral do conteúdo cadastrado exposto; falta dimensionar prédio/telhado. Sem índice climático local e sem percentual arbitrário de dano.')
        if code == 'ROUBO_FURTO_ARROMBAMENTO':
            notes.append('Cenário patrimonial não garante aceitação de todas as categorias nem cobre automaticamente furto simples ou dinheiro.')
    elif code == 'DANOS_ELETRICOS':
        lo, hi, chosen = asset_range(assets, POLITICA['tipos_eletricos'])
        evidence = {'bens_ids': [b['bem_id'] for b in chosen], 'tipos': sorted({b['tipo_bem'] for b in chosen})}
        rule = 'min=sum(bens_eletricos_ponderados); max=sum(bens_eletricos_cadastrados); sem itens identificados => sem estimativa'
        reason = 'Cenários de reposição dos equipamentos de natureza elétrica identificados; classificação preliminar por tipo.'
        question = 'Os equipamentos listados são elétricos, estão neste endereço e quais seus valores de reposição? Existem instalações ou máquinas elétricas não listadas?'
        notes.append('Não usa conta de energia como valor dos equipamentos. Máquinas e equipamentos de oficina genéricos exigem classificação antes de inclusão.')
    elif code == 'PERDA_PAGAMENTO_ALUGUEL':
        rent = number(signals, 'valor_aluguel_recorrente')
        evidence = {'pagamento_aluguel_recorrente': signals.get('pagamento_aluguel_recorrente'), 'aluguel_mensal': rent}
        if signals.get('pagamento_aluguel_recorrente') == 'SIM' and rent is not None and rent > 0:
            lo, hi = [rent * m for m in POLITICA['meses_aluguel']]
        rule = 'Com aluguel recorrente positivo: min=aluguel_mensal*' + str(POLITICA['meses_aluguel'][0]) + '; max=aluguel_mensal*' + str(POLITICA['meses_aluguel'][1]) + '; sem aluguel observado => pendente'
        reason = 'Cenários de duração em meses ' + str(POLITICA['meses_aluguel']) + ' propostos pela equipe para a parcela de aluguel observada.'
        question = 'Qual a relação com o imóvel, aluguel contratual, condomínio, IPTU e prazo esperado de recuperação? Há obrigação de manter o aluguel após sinistro?'
        notes.append('Sem pagamento recorrente não significa imóvel próprio nem cobertura inaplicável; pode ser necessário aluguel temporário. Falta condomínio/IPTU.')
    elif code == 'DESPESAS_FIXAS':
        payroll = number(signals, 'folha_pagamento_mensal')
        energy = number(signals, 'energia_media_mensal_6m')
        total = number(signals, 'despesa_fixa_mensal_estimada')
        evidence = {'folha_mensal': payroll, 'energia_mensal': energy, 'despesa_fixa_total_referencia': total}
        if payroll is not None and energy is not None:
            monthly = payroll + energy
            lo, hi = [monthly * m for m in POLITICA['meses_despesas']]
        rule = 'base_mensal=folha_pagamento_mensal+energia_media_mensal_6m; min=base_mensal*' + str(POLITICA['meses_despesas'][0]) + '; max=base_mensal*' + str(POLITICA['meses_despesas'][1])
        reason = 'Cenários em meses ' + str(POLITICA['meses_despesas']) + ' para os componentes identificáveis de folha e energia, sem somar aluguel ou software automaticamente.'
        question = 'Quais despesas permanecem na paralisação e são contratualmente indenizáveis? A folha já inclui encargos? Qual prazo de recuperação?'
        notes.append('Escopo parcial: encargos, água, tributos e outras rubricas precisam de confirmação. Não soma a despesa agregada à folha/energia, evitando dupla contagem.')
        if total is not None and payroll is not None and energy is not None and total < payroll + energy:
            notes.append('INCONSISTENCIA_FINANCEIRA: despesa agregada menor que folha+energia; conferir antes de uso comercial.')
    elif code in {'RESPONSABILIDADE_CIVIL_ESTABELECIMENTO', 'RESPONSABILIDADE_CIVIL_EMPREGADOR'}:
        evidence = {'grupo_atividade': company.get('grupo_atividade'), 'funcionarios_empresa': number(company, 'quantidade_funcionarios_estimada')}
        rule = 'SEM_ESTIMATIVA: definir cenários de danos a terceiros/empregados e confrontar limites disponíveis do produto; não há conversão defensável de faturamento ou folha em indenização'
        reason = 'Cobertura fixa do plano; cadastro não dimensiona severidade, circulação de terceiros nem limite de responsabilidade.'
        question = 'Quantas pessoas atuam/circulam neste endereço, quais atividades e cenários de danos precisam de proteção e quais limites o produto permite?'
    elif code == 'QUEBRA_DE_VIDROS':
        evidence = {'possui_termo_loja': address.get('possui_termo_loja'), 'possui_termo_galeria': address.get('possui_termo_galeria')}
        rule = 'SEM_ESTIMATIVA: área/tipo de vidros e orçamento de reposição+instalação ausentes; área construída não equivale à área de vidro'
        reason = 'Cobertura fixa do Total; endereço não informa dimensões, materiais ou custo de reposição dos itens.'
        question = 'Quais vidros, espelhos e demais itens aplicáveis existem e qual orçamento de reposição e instalação?'
    elif code == 'DELIVERY':
        kind = 'ADICIONAL_CANDIDATA'
        evidence = {'percentual_receita_delivery_empresa': number(company, 'percentual_receita_delivery_est')}
        rule = 'SEM_ESTIMATIVA: confirmar delivery no endereço, mercadorias, valor por envio/acúmulo e condições aplicáveis; receita mensal não equivale a valor transportado'
        reason = 'Participação de delivery na empresa indica necessidade de confirmação no estabelecimento.'
        question = 'Este endereço realiza delivery? Quais bens, responsáveis, trajetos e valores máximos por envio/acúmulo?'
    elif code == 'DETERIORACAO_MERCADORIAS_FRIGORIFICADAS':
        kind = 'ADICIONAL_CANDIDATA'
        evidence = {'probabilidade_refrigeracao_referencia': number(signals, 'probabilidade_refrigeracao_referencia'),
                    'equipamentos_refrigeracao': [b['bem_id'] for b in assets if b['tipo_bem'] == 'EQUIPAMENTO_REFRIGERACAO'],
                    'estoque_pico_total': number(signals, 'estoque_pico_estimado')}
        rule = 'SEM_ESTIMATIVA: quantidade e valor de mercadorias refrigeradas desconhecidos; não multiplicar estoque por probabilidade_refrigeracao'
        reason = 'Indício de refrigeração; equipamento pode existir sem mercadoria segurável.'
        question = 'Há mercadorias ou vacinas refrigeradas? Qual valor máximo simultâneo, manutenção, temperatura e contingência?'
    elif code == 'LETREIROS_ANUNCIOS_LUMINOSOS':
        kind = 'ADICIONAL_CANDIDATA'
        lo, hi, chosen = asset_range(assets, {'LETREIRO'})
        evidence = {'bens_ids': [b['bem_id'] for b in chosen]}
        rule = 'min=sum(letreiros_ponderados); max=sum(letreiros_cadastrados); confirmar enquadramento e reposição'
        reason = 'Bem cadastrado como letreiro sugere adicional específico, condicionado às suas características.'
        question = 'O letreiro está neste endereço, enquadra-se na cobertura e qual seu valor de reposição e instalação?'
    else:
        raise ValueError('Cobertura sem regra: ' + code)
    pending = lo is None or hi is None
    if pending:
        lo = hi = None
        notes.append('SEM_ESTIMATIVA_JUSTIFICADA: ' + rule)
    else:
        if not math.isfinite(lo) or not math.isfinite(hi) or not 0 <= lo <= hi:
            raise ValueError('Faixa inválida: ' + code)
        lo, hi = round(lo, 2), round(hi, 2)
        notes.append('FAIXA_PRELIMINAR_DE_CENARIO: parâmetros não calibrados com sinistros nem limites comerciais.')
    if kind == 'ADICIONAL_CANDIDATA':
        notes.append('Aplicabilidade ainda não confirmada; não representa adicional contratado ou aceito.')
    notes.insert(0, kind)
    return {'cobertura': code, 'faixa_valor_min': lo, 'faixa_valor_max': hi,
            'confianca_estimativa': confidence, 'dados_utilizados': json.dumps(evidence, ensure_ascii=False, allow_nan=False),
            'regra_calculo_utilizada': rule, 'justificativa': reason,
            'informacao_a_confirmar': question, 'observacao': join_unique(notes)}


def process(company, address, signals, assets, prepared, catalog):
    status, restrictions, questions = eligibility(company, address)
    profile = score_empresa(prepared)
    ids = {f: prepared[f] for f in ['empresa_id', 'imovel_id']}
    plan = profile['plano_sugerido'] if not restrictions else None
    rows = []
    if plan:
        codes = list(catalog[plan])
        if (number(company, 'percentual_receita_delivery_est') or 0) > 0:
            codes.append('DELIVERY')
        if (number(signals, 'probabilidade_refrigeracao_referencia') or 0) >= POLITICA['limiar_perguntar_refrigeracao'] or any(b['tipo_bem'] == 'EQUIPAMENTO_REFRIGERACAO' for b in assets):
            codes.append('DETERIORACAO_MERCADORIAS_FRIGORIFICADAS')
        if any(b['tipo_bem'] == 'LETREIRO' for b in assets):
            codes.append('LETREIROS_ANUNCIOS_LUMINOSOS')
        rows = [dict(ids, **coverage(code, company, address, signals, assets)) for code in codes]
    questions += ['O interesse é proteger prédio, conteúdo ou ambos, e qual a relação contratual com o imóvel?']
    questions += profile['perguntas_confirmacao']
    if restrictions:
        questions += ['Confirmar restrição: ' + r for r in restrictions]
    questions += [r['informacao_a_confirmar'] for r in rows]
    reason = 'Proposta experimental na base mock. '
    if profile['score'] is not None:
        reason += 'Índice ordinal v2=' + format(profile['score'], '.9f') + '; indicação do índice=' + profile['plano_sugerido'] + '. '
        reason += ('Plano condicional à validação de elegibilidade e necessidades. ' if plan else 'Oferta suspensa por restrição cadastral. ')
    else:
        reason += 'Sem plano: dados essenciais ausentes/categoria desconhecida. '
    reason += 'Atividade=' + company['grupo_atividade'] + '; estoque médio local=' + str(number(signals, 'estoque_medio_estimado')) + '; empregados da empresa=' + str(number(company, 'quantidade_funcionarios_estimada')) + '. '
    reason += 'Confiança BAIXA pelas confirmações de elegibilidade e estimativas parciais; score não é confiança. '
    reason += 'Adicionais são candidatos a confirmar, sem contratação automática.'
    reason += (' Avisos do índice: ' + join_unique(profile['avisos'])) if profile['avisos'] else ''
    result = dict(ids, elegivel=status,
                  motivo_inelegibilidade=join_unique(restrictions) if restrictions else 'Sem impedimento cadastral identificado; elegibilidade ainda não confirmada integralmente.',
                  tipo_localizacao_sugerido=location(address),
                  relacao_imovel_sugerida='INQUILINO_A_CONFIRMAR' if signals.get('pagamento_aluguel_recorrente') == 'SIM' and (number(signals, 'valor_aluguel_recorrente') or 0) > 0 else 'A_CONFIRMAR',
                  plano_recomendado=plan or '', coberturas_recomendadas=join_unique([r['cobertura'] for r in rows]),
                  confianca_geral='BAIXA', justificativa_recomendacao=reason,
                  perguntas_confirmacao=join_unique(questions), fontes_publicas_adicionais=BB + ' | ' + CG)
    detail = dict(ids, score=profile['score'], plano_indice=profile['plano_sugerido'],
                  plano_template=plan, elegibilidade=status, restricoes=restrictions,
                  contribuicoes=sorted(profile['contribuicoes'], key=lambda r: abs(r['contribuicao_z']), reverse=True),
                  avisos_indice=profile['avisos'], dados_ausentes=profile['campos_ausentes'],
                  status='OFERTA_SUSPENSA' if restrictions else ('PLANO_CONDICIONAL' if plan else 'INDICE_PENDENTE'),
                  pendencias=[dict(ids, cobertura=r['cobertura'],
                                  tipo='DADOS_E_CONTRATO' if r['faixa_valor_min'] is None else 'CONFIRMAR_FAIXA_PARCIAL',
                                  motivo=r['regra_calculo_utilizada'], pergunta=r['informacao_a_confirmar']) for r in rows])
    return result, rows, detail


def build(base, data_root=None):
    folder = (data_root or ROOT / 'dados/originais') / ('Seguro_Empresarial_' + base)
    suffix = 'desenvolvimento' if base == 'Desenvolvimento' else 'teste_comum'
    inputs = {name: read(folder / (name + '.csv')) for name in ['empresas', 'enderecos_estabelecimentos', 'sinais_financeiros_operacionais', 'bens_cadastrados', 'template_resultado_times', 'catalogo_coberturas_fixas_planos']}
    companies = index(inputs['empresas'], ['empresa_id'], 'empresas')
    addresses = index(inputs['enderecos_estabelecimentos'], ['empresa_id', 'imovel_id'], 'endereços')
    signals = index(inputs['sinais_financeiros_operacionais'], ['empresa_id', 'imovel_id'], 'sinais')
    targets = index(inputs['template_resultado_times'], ['empresa_id', 'imovel_id'], 'template')
    prepared = index(read(ROOT / 'dados/preparados' / ('base_' + suffix + '.csv')), ['empresa_id', 'imovel_id'], 'base preparada')
    if not set(addresses) == set(signals) == set(targets) == set(prepared):
        raise ValueError('Pares empresa-estabelecimento divergentes')
    if {k[0] for k in targets} != {k[0] for k in companies}:
        raise ValueError('Empresas divergentes')
    assets = defaultdict(list)
    index(inputs['bens_cadastrados'], ['bem_id'], 'bens')
    for b in inputs['bens_cadastrados']:
        k = b['empresa_id'], b['imovel_id_referencia']
        if k not in targets:
            raise ValueError('Bem órfão: ' + b['bem_id'])
        # Validar os dados que alimentam as faixas mesmo se a oferta estiver suspensa.
        for field in ['valor_cadastrado', 'valor_bem_ponderado_referencia', 'probabilidade_bem_no_imovel_referencia']:
            if number(b, field) is None:
                raise ValueError('Bem sem ' + field)
        if number(b, 'probabilidade_bem_no_imovel_referencia') > 1:
            raise ValueError('Probabilidade de vínculo > 1')
        if b['tipo_bem'] not in POLITICA['tipos_conteudo'] + ['LETREIRO']:
            raise ValueError('Tipo de bem não mapeado: ' + b['tipo_bem'])
        assets[k].append(b)
    catalog = defaultdict(list)
    for row in inputs['catalogo_coberturas_fixas_planos']:
        catalog[row['plano']].append(row['cobertura_fixa'])
    if {p: len(v) for p, v in catalog.items()} != {'ESSENCIAL': 5, 'PRATICO': 7, 'TOTAL': 9}:
        raise ValueError('Catálogo de planos mudou: revisar regras')
    results, covers, details = [], [], []
    for k in targets:  # Preservar a ordem do template original.
        company, address, signal = companies[(k[0],)], addresses[k], signals[k]
        expected = prepared[k]
        # Conferência de coerência entre base de inferência e fontes atuais.
        if number(expected, 'estoque_medio_estimado') != number(signal, 'estoque_medio_estimado'):
            raise ValueError('Base preparada desatualizada: estoque ' + str(k))
        if number(expected, 'funcionarios_estimados_empresa') != number(company, 'quantidade_funcionarios_estimada') or expected['grupo_atividade'] != company['grupo_atividade']:
            raise ValueError('Base preparada desatualizada: empresa ' + str(k))
        if number(expected, 'faturamento_mensal_empresa') != number(company, 'faturamento_mensal') or expected['tipo_unidade'] != address['tipo_unidade']:
            raise ValueError('Base preparada desatualizada: faturamento/unidade ' + str(k))
        if number(expected, 'quantidade_estabelecimentos_empresa') != sum(1 for pair in addresses if pair[0] == k[0]):
            raise ValueError('Base preparada desatualizada: contagem de estabelecimentos ' + str(k))
        asset_sum = sum(number(b, 'valor_bem_ponderado_referencia') for b in assets[k]) if assets[k] else None
        if asset_sum != number(expected, 'valor_bens_ponderado_estabelecimento'):
            raise ValueError('Base preparada desatualizada: bens ' + str(k))
        for f, value in signal.items():
            if f not in ['empresa_id', 'imovel_id', 'pagamento_aluguel_recorrente']:
                number(signal, f)
        result, rows, detail = process(company, address, signal, assets[k], expected, catalog)
        results.append(result); covers.extend(rows); details.append(detail)
    result_header = list(inputs['template_resultado_times'][0])
    with (folder / 'template_coberturas_times.csv').open(encoding='utf-8-sig', newline='') as stream:
        coverage_header = next(csv.reader(stream))
    validate(results, covers, targets, catalog, result_header, coverage_header)
    summary = {'estabelecimentos': len(results), 'empresas': len(companies), 'linhas_coberturas': len(covers),
               'planos_condicionais': dict(Counter(r['plano_recomendado'] or 'SEM_PLANO' for r in results)),
               'elegibilidade': dict(Counter(r['elegivel'] for r in results)),
               'status': dict(Counter(d['status'] for d in details)),
               'faixas_numericas': sum(r['faixa_valor_min'] is not None for r in covers),
               'faixas_ausentes_justificadas': sum(r['faixa_valor_min'] is None for r in covers),
               'coberturas_sem_faixa': dict(Counter(r['cobertura'] for r in covers if r['faixa_valor_min'] is None)),
               'adicionais_candidatas': dict(Counter(r['cobertura'] for r in covers if r['observacao'].startswith('ADICIONAL_CANDIDATA')))}
    return {'base': suffix, 'resultado_header': result_header, 'coberturas_header': coverage_header,
            'resultado': results, 'coberturas': covers, 'detalhes': details, 'resumo': summary}


def validate(results, covers, targets, catalog, rh, ch):
    index(results, ['empresa_id', 'imovel_id'], 'saída resultado')
    index(covers, ['empresa_id', 'imovel_id', 'cobertura'], 'saída coberturas')
    if set(map(key, results)) != set(targets):
        raise ValueError('Saída com chaves divergentes')
    by_pair = defaultdict(list)
    for row in covers:
        if set(row) != set(ch) or key(row) not in targets:
            raise ValueError('Cobertura fora do contrato')
        lo, hi = row['faixa_valor_min'], row['faixa_valor_max']
        if (lo is None) != (hi is None):
            raise ValueError('Faixa parcialmente nula')
        if lo is not None and (not math.isfinite(lo) or not math.isfinite(hi) or not 0 <= lo <= hi):
            raise ValueError('Faixa inválida')
        if lo is None and 'SEM_ESTIMATIVA_JUSTIFICADA' not in row['observacao']:
            raise ValueError('Faixa ausente sem justificativa')
        if any(not row[f] for f in ['dados_utilizados', 'regra_calculo_utilizada', 'justificativa', 'informacao_a_confirmar']):
            raise ValueError('Explicação de cobertura incompleta')
        by_pair[key(row)].append(row)
    for row in results:
        if set(row) != set(rh):
            raise ValueError('Cabeçalho de resultado divergente')
        actual = [c['cobertura'] for c in by_pair[key(row)]]
        listed = row['coberturas_recomendadas'].split(' | ') if row['coberturas_recomendadas'] else []
        if actual != listed:
            raise ValueError('Templates discordam das coberturas')
        plan = row['plano_recomendado']
        if plan and not set(catalog[plan]).issubset(actual):
            raise ValueError('Cobertura fixa omitida')
        if not plan and actual:
            raise ValueError('Cobertura para oferta suspensa')


def write_csv(path, rows, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)


def execute(output, intermediate_only=False):
    summaries = {}
    for base in ['Desenvolvimento', 'Teste_Comum']:
        payload = build(base)
        folder = output / payload['base']
        dump(folder / 'auditoria.json', payload['detalhes'])
        dump(folder / 'pendencias_por_cobertura.json', [p for detail in payload['detalhes'] for p in detail['pendencias']])
        dump(folder / 'resumo.json', payload['resumo'])
        if intermediate_only:
            dump(folder / 'intermediario.json', {k: v for k, v in payload.items() if k != 'detalhes'})
        if not intermediate_only:
            write_csv(folder / 'template_resultado_times.csv', payload['resultado'], payload['resultado_header'])
            write_csv(folder / 'template_coberturas_times.csv', payload['coberturas'], payload['coberturas_header'])
        summaries[payload['base']] = payload['resumo']
    source_paths = sorted((ROOT / 'dados').rglob('*.csv')) + sorted((ROOT / 'indice/modelo').glob('*.json')) + [ROOT / 'indice/score.py', ROOT / 'politica.json', ROOT / 'documentacao/Guia_dos_times.pdf']
    dump(output / 'fontes_sha256.json', {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in source_paths})
    dump(output / 'resumo_geral.json', summaries)
    return summaries


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--saida', type=Path, default=ROOT / 'saidas')
    parser.add_argument('--somente-intermediario', action='store_true')
    args = parser.parse_args()
    print(json.dumps(execute(args.saida, args.somente_intermediario), ensure_ascii=False, indent=2))
