from pathlib import Path
import json,pickle
import numpy as np
import pandas as pd
import nbformat
from modelo import *
from inferir import inferir
P=Path(__file__).resolve().parent;O=P/'resultados'
r=json.loads((O/'resultado.json').read_text());t=pd.read_csv(O/'resumo_8_9_10.csv');w=pd.read_csv(O/'pesos.csv')
a=pickle.loads((O/'modelo_ordinal.pkl').read_bytes());m=a['modelo']
num=m.prep.named_transformers_['num'];imp=num.steps[0][1];scale=num.steps[-1][1];cat=m.prep.named_transformers_['cat']
formula={'versao':'ordinal_mock_v2','formula':'z=sum(beta_j*x_j); score=sigmoid(z); x é a transformação descrita abaixo',
 'colunas_numericas':[c for c in m.colunas if c not in CAT],
 'medianas_imputacao':imp.statistics_.tolist(),'indices_indicadores_ausencia':imp.indicator_.features_.tolist(),
 'transformacao_numerica':'Imputar; anexar indicadores de ausência; log1p de todas estas colunas; (valor-media)/desvio',
 'medias_apos_log1p':scale.mean_.tolist(),'desvios_apos_log1p':scale.scale_.tolist(),
 'colunas_categoricas':[c for c in m.colunas if c in CAT],
 'categorias':[v.tolist() for v in cat.categories_],'categoria_base':[v[0] for v in cat.categories_],
 'transformacao_categorica':'One-hot, excluindo a primeira categoria; categorias novas viram vetor zero e exigem aviso',
 'ordem':'numéricas e indicadores primeiro, categorias depois; aplicar máscara antes de beta',
 'mascara_colunas':m.mask.tolist(),'termos':m.names,'pesos':m.beta.tolist(),'limiares_z':m.thresholds.tolist(),'cortes':r['cortes']}
(O/'formula_completa.json').write_text(json.dumps(formula,ensure_ascii=False,indent=2)+'\n')
rows=inferir('/home/lucas/Documentos/hackathon/seguro_empresarial/dados/preparados/base_teste_comum.csv',O/'modelo_ordinal.pkl','/tmp/verificacao_indice_v2.jsonl')
expected=pd.read_csv(O/'scores_teste.csv');assert np.allclose([v['score'] for v in rows],expected.score)
assert [v['plano_sugerido'] for v in rows]==expected.indicado.tolist()
(O/'teste_inferencia.json').write_text(json.dumps({'144_scores_e_planos_reproduzidos':True},indent=2)+'\n')
def table(df):
 return '\n'.join(['| '+' | '.join(df.columns)+' |','| '+' | '.join(['---']*len(df.columns))+' |']+['| '+' | '.join(map(str,row))+' |' for row in df.itertuples(index=False,name=None)])
a1,a2=r['cortes']
text=f'''# Iterações com 8, 9 e 10 variáveis

Execução: 28/10/2026. Base mock fornecida. Mesma política de referência da v1; aumentamos as variáveis de entrada, sem mudar os alvos para forçar importância das variáveis novas.

## Resultado por iteração

{table(t[['n_variaveis','alpha','pseudo_r2_mcfadden_treino','pseudo_r2_preditivo_cv','acuracia_cv','log_loss_cv']].round(6))}

Foram executados 27 ajustes: três conjuntos de variáveis, três penalidades e três dobras separadas por empresa. A tabela mostra a melhor penalidade de cada conjunto; todos os detalhes estão em `cada_iteracao_e_dobra.csv` e `ranking_cv.csv`. A versão selecionada usa **8 variáveis**, com penalidade 1. A diferença entre as versões é pequena: não afirmamos superioridade estatística comprovada.

## O que significa R² aqui

Usamos **pseudo-R² de McFadden = 1 − LL_modelo/LL_nulo**, conforme [documentação statsmodels](https://www.statsmodels.org/stable/dev/generated/statsmodels.base.model.GenericLikelihoodModelResults.html). LL é a soma dos logaritmos das probabilidades da referência. A penalidade L2 não é incluída nessa soma. O modelo nulo usa apenas frequências dos planos no treino.

No treino, a tabela informa o índice de ajuste McFadden nos parâmetros penalizados. Na validação, usamos a mesma razão como **análogo preditivo**, com frequências aprendidas apenas no treino de cada dobra. Não é o pseudo-R² clássico ajustado na própria validação. O resultado agregado soma as log-verossimilhanças das previsões fora da amostra antes de calcular a razão. Um valor negativo seria possível se as previsões fossem piores que o modelo nulo.

**0,6458 não significa 64,58% da variância explicada nem 64,58% de acerto.** Selecionamos pela menor log-loss de validação, equivalente a maximizar essa razão quando o denominador é o mesmo. A regularização e as referências derivadas impedem interpretar este índice como prova de significância.

## Variáveis

| Iteração | Variáveis acrescentadas | Justificativa e limite |
|---|---|---|
| 8 | Funcionários; estoque; bens; faturamento; quantidade de estabelecimentos; atividade; tipo de unidade; área | Patrimônio, emprego, escala e contexto. Funcionários e faturamento referem-se à empresa, não ao endereço. Área tem muitos valores ausentes. |
| 9 | Presença do termo loja no endereço | Contexto exploratório, não confirmação de vitrine ou risco. |
| 10 | Presença do termo galeria no endereço | Contexto exploratório, não evidência de proteção ou exposição. |

São 8 variáveis originais no modelo escolhido, que viram **17 coeficientes** após categorias e indicador de ausência. Atividade tem vários pesos, relativos à categoria-base BELEZA; tipo de unidade usa FILIAL como base. Não existe um peso único de atividade sem especificar sua categoria. A regressão continua ordinal, com um único índice.

## Pesos e estabilidade

{table(w.round(6))}

Pesos numéricos são para variáveis transformadas por log(1+x) e padronizadas. Indicadores de ausência também passam pela transformação do pipeline. Categorias são indicadores 0/1 com base omitida. A soma das contribuições produz z; sigmoid(z) produz o score. Fórmula e parâmetros completos em `formula_completa.json`.

100 reamostragens por empresa indicam estabilidade **condicional** à política, transformação e seleção. Faturamento, área e o indicador de ausência da área têm intervalos que cruzam zero. Logo, não foram confirmados como efeitos estáveis nesta referência. Funcionários, estoque e bens mantêm sinais positivos estáveis; quantidade de estabelecimentos tem sinal negativo condicional, sem interpretação causal. Alguns contrastes de atividade também têm estabilidade, mas não são recomendação de seguro por setor.

Os critérios de referência continuam baseados em três variáveis. Acrescentar cinco preditores não cria informação de adequação que não existe no alvo. Não é defensável dizer que as oito variáveis são estatisticamente significativas.

## Novas faixas, próprias da versão 2

- Essencial: score abaixo de {a1:.9f}.
- Prático: de {a1:.9f} até abaixo de {a2:.9f}.
- Total: de {a2:.9f} em diante.

Score = sigmoid(X beta); faixas = sigmoid dos dois limiares ajustados. Decisão pela mediana ordinal, não necessariamente pela maior probabilidade. Não arredondar antes de enquadrar. Não misturar scores da v2 com faixas da v1.

## Reavaliação do teste comum

Acertos: **114/144 = {r['metricas_teste']['acuracia']:.2%}**, ante 116/144 = 80,56% na v1. Pseudo-R² preditivo: {r['metricas_teste']['indice_1_menos_LL_LL0']:.6f}. Log-loss: {r['metricas_teste']['log_loss']:.6f}. Assim, **o requisito de pelo menos oito variáveis foi atendido, mas não melhorou o resultado observado**. Não ajustamos a seleção com base nessa reavaliação.

O teste já havia sido consultado na versão anterior; esta é uma comparação na mesma base, não uma nova avaliação independente intocada. A concordância é com critérios construídos, não com planos ideais observados. A limitação ordinal frente ao comparador multinomial encontrada na v1 não foi resolvida por acrescentar variáveis.

## Entregáveis e verificações

`perfis_rag.jsonl` contém 144 perfis da versão 2. `modelo_ordinal.pkl` contém a transformação e parâmetros. `inferir.py` aplica novos lotes sem treinar. `testes.json` registra 11 verificações aprovadas e `teste_inferencia.json` confirma reprodução dos 144 scores e planos após carregar o modelo. O notebook apresenta a execução congelada.
'''
(P/'RELATORIO_ITERACOES.md').write_text(text)
nb=nbformat.v4.new_notebook(cells=[nbformat.v4.new_markdown_cell('# Regressão ordinal: 8–10 variáveis e pseudo-R²\nResultados congelados. A execução abaixo não retreina nem seleciona com base no teste.'),nbformat.v4.new_code_cell("from pathlib import Path\nimport json\nimport pandas as pd\nfrom IPython.display import display, Markdown\np=Path.cwd()\ndisplay(Markdown((p/'RELATORIO_ITERACOES.md').read_text()))"),nbformat.v4.new_code_cell("display(pd.read_csv(p/'resultados/resumo_8_9_10.csv'))\ndisplay(pd.read_csv(p/'resultados/cada_iteracao_e_dobra.csv'))"),nbformat.v4.new_code_cell("display(pd.read_csv(p/'resultados/pesos.csv'))\ndisplay(json.loads((p/'resultados/formula_completa.json').read_text()))"),nbformat.v4.new_code_cell("display(json.loads((p/'resultados/testes.json').read_text()))\ndisplay(json.loads((p/'resultados/perfis_rag.jsonl').read_text().splitlines()[0]))")],metadata={'kernelspec':{'name':'python3','display_name':'Python 3','language':'python'}})
nbformat.write(nb,P/'04_iteracoes_8_9_10_variaveis.ipynb')
(P/'README.md').write_text('''# Versão 2: 8–10 variáveis\n\nLeia RELATORIO_ITERACOES.md ou 04_iteracoes_8_9_10_variaveis.ipynb.\n\nPara reproduzir: instale requirements.txt; ajuste ROOT em executar.py para a pasta do projeto e os caminhos locais em gerar_entrega.py; execute `python executar.py` e `python gerar_entrega.py`. Precisa das bases preparadas do projeto e dos critérios congelados da v1 para verificar que a política não mudou.\n\nPara aplicar o modelo: `python inferir.py base_preparada.csv --saida perfis.jsonl`. Os nomes das 8 colunas estão em resultados/resultado.json. Não abrir pickle de origem desconhecida.\n\nSeleção pela validação agrupada no desenvolvimento. Teste comum é reavaliação, pois já foi consultado na v1. O pseudo-R² preditivo não é proporção da variância nem taxa de acerto. A inclusão de variáveis adicionais não comprovou ganho sobre a v1.\n''')
print('Relatório, notebook, fórmula e inferência verificados.')
