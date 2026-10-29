"""Teste de software com dados inteiramente simulados; não é validação comercial."""
import sys
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import log_loss
from sklearn.model_selection import train_test_split

PROJETO = Path('/home/lucas/Documentos/hackathon/seguro_empresarial')
sys.path.insert(0, str(PROJETO / 'src'))
from treinar import RegressaoOrdinal, metricas, PLANOS


def executar():
    rng = np.random.default_rng(20261028)
    n = 2400
    x = rng.normal(size=(n, 3))
    # Processo inventado APENAS para testar recuperação de uma relação conhecida.
    z = 1.2*x[:, 0] + 0.8*x[:, 1] + rng.logistic(size=n)
    y = np.searchsorted([-0.7, 0.9], z)
    base = pd.DataFrame(np.exp(x), columns=['sinal_a', 'sinal_b', 'ruido'])
    base['empresa_id'] = [f'SIMULACAO_{i}' for i in range(n)]
    base['plano_referencia'] = np.array(PLANOS)[y]
    a, b = train_test_split(base, test_size=0.25, random_state=42, stratify=y)
    assert not set(a.empresa_id) & set(b.empresa_id)
    resultados = []
    exemplos = []
    for nome, colunas in [('dois_sinais', ['sinal_a', 'sinal_b']),
                           ('um_sinal', ['sinal_a']), ('somente_ruido', ['ruido'])]:
        modelo = RegressaoOrdinal(colunas).fit(a, robusta=True)
        p, pred, score, cortes = modelo.predict(b)
        assert np.isfinite(p).all() and np.allclose(p.sum(axis=1), 1)
        assert (p >= 0).all() and (p <= 1).all()
        assert 0 < cortes[0] < cortes[1] < 1
        assert np.array_equal(pred, np.searchsorted(cortes, score, side='right'))
        resultados.append({'cenario':nome, **metricas(b, (p,pred,score,cortes)),
                           'cortes_apenas_simulacao':cortes.tolist(), 'convergiu':True})
        if nome == 'dois_sinais':
            for classe in PLANOS:
                i = np.flatnonzero(b.plano_referencia.to_numpy() == classe)[0]
                exemplos.append({'id_simulado':b.iloc[i].empresa_id, 'referencia_artificial':classe,
                                 'predicao':PLANOS[pred[i]], 'score_simulado':float(score[i]),
                                 'probabilidades':dict(zip(PLANOS, p[i].tolist()))})
    frequencias = a.plano_referencia.value_counts(normalize=True).reindex(PLANOS).to_numpy()
    baseline = log_loss(b.plano_referencia.map(dict(zip(PLANOS, range(3)))),
                        np.tile(frequencias, (len(b), 1)), labels=[0,1,2])
    real = pd.read_csv(PROJETO/'dados/rotulos/rotulos_revisados.csv')
    n_rotulos = int(real.plano_referencia.astype('string').fillna('').str.strip().ne('').sum())
    resumo = {'natureza':'TESTE TECNICO EM SIMULACAO; NAO USAR PARA CLIENTES',
              'semente':20261028,'treino_simulado':len(a),'teste_simulado':len(b),
              'rotulos_revisados_disponiveis':n_rotulos,'log_loss_baseline_simulado':baseline,
              'resultados':resultados,'exemplos_simulados':exemplos,
              'limite':'Nenhuma evidencia de adequacao dos planos ou significancia das variaveis empresariais.'}
    out = Path(__file__).resolve().parent/'resultados'
    out.mkdir(exist_ok=True)
    (out/'teste_tecnico.json').write_text(json.dumps(resumo,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(resumo,ensure_ascii=False,indent=2))
    return resumo

if __name__ == '__main__':
    executar()
