from pathlib import Path
import json,pickle,sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import nbformat as n
from modelo import *
P=Path(__file__).resolve().parent;O=P/'resultados'
r=json.loads((O/'resultado_final.json').read_text());a=pickle.loads((O/'modelo_ordinal.pkl').read_bytes());m=a['modelo']
w=pd.read_csv(O/'pesos_e_estabilidade.csv');sens=pd.read_csv(O/'sensibilidade_criterios.csv');cases=pd.read_csv(O/'casos_explicados.csv');rank=pd.read_csv(O/'ranking_cv.csv')
scaler=m.prep.named_transformers_['num'].steps[-1][1];imputer=m.prep.named_transformers_['num'].steps[0][1]
recipe={'variaveis_numericas':m.colunas,'medianas':imputer.statistics_.tolist(),'medias_log1p':scaler.mean_.tolist(),'desvios_log1p':scaler.scale_.tolist(),'pesos':m.beta.tolist(),'limiares_z':m.thresholds.tolist(),'limiares_score':r['cortes'],'formula':'x_j=(log(1+valor_j)-media_log_j)/desvio_log_j; z=sum(beta_j*x_j); score=1/(1+exp(-z))'}
(O/'formula_parametros.json').write_text(json.dumps(recipe,ensure_ascii=False,indent=2)+'\n')
# Cálculo independente do modelo salvo para demonstrar reprodução.
test=pd.read_csv('/home/lucas/Documentos/hackathon/seguro_empresarial/dados/preparados/base_teste_comum.csv')
x=(np.log1p(test[m.colunas].fillna(dict(zip(m.colunas,imputer.statistics_))).to_numpy())-scaler.mean_)/scaler.scale_
s=expit(x@m.beta);saved=pd.read_csv(O/'scores_teste_comum.csv');assert np.allclose(s,saved.score)
fig,axes=plt.subplots(1,3,figsize=(15,4.3))
for name in PLANOS:
 axes[0].hist(saved.loc[saved.referencia_criterios==name,'score'],bins=np.linspace(0,1,21),alpha=.5,label=name)
for c in r['cortes']:axes[0].axvline(c,color='black',linestyle='--')
axes[0].set(title='Score por referência construída',xlabel='Score',ylabel='Estabelecimentos');axes[0].legend(fontsize=8)
cm=pd.read_csv(O/'matriz_confusao_teste.csv',index_col=0).to_numpy();axes[1].imshow(cm,cmap='Blues')
for i in range(3):
 for j in range(3):axes[1].text(j,i,str(cm[i,j]),ha='center',va='center',color='white' if cm[i,j]>32 else 'black')
axes[1].set(xticks=range(3),yticks=range(3),xticklabels=PLANOS,yticklabels=PLANOS,title='Teste: referência × indicação',xlabel='Indicação',ylabel='Referência')
axes[2].bar(['Mais abrangente','Mais restritivo'],sens.mudanca_recomendacao_oof.iloc[1:]*100,color=['#287b8e','#be7737'])
axes[2].set(title='Sensibilidade no desenvolvimento',ylabel='Recomendações alteradas (%)',ylim=(0,30))
fig.suptitle('Protótipo mock — concordância com critérios propostos, não adequação comercial',fontsize=12)
fig.tight_layout();fig.savefig(O/'diagnosticos.png',dpi=150);plt.close(fig)

def table(df):
    cols=list(df.columns);lines=['| '+' | '.join(cols)+' |','| '+' | '.join(['---']*len(cols))+' |']
    for row in df.itertuples(index=False,name=None):lines.append('| '+' | '.join(str(v) for v in row)+' |')
    return '\n'.join(lines)
cut1,cut2=r['cortes'];mt=r['teste']
text=f'''# Resultado do índice por regressão — base mock fornecida

Executado em 28/10/2026. **Modelo treinado de fato no desenvolvimento fornecido: {r['n_desenvolvimento']} estabelecimentos. Teste externo: {r['n_teste']} estabelecimentos de {r['empresas_teste']} empresas.** Não é a simulação matemática anterior.

## Resultado principal

Concordância com os planos de referência construídos: **{mt['acuracia']:.2%} (116/144)**. Macro-F1: {mt['macro_f1']:.4f}; acurácia balanceada: {mt['acuracia_balanceada']:.2%}. Intervalo bootstrap por empresa para concordância: {r['ic95_acuracia_teste_bootstrap_empresa'][0]:.1%}–{r['ic95_acuracia_teste_bootstrap_empresa'][1]:.1%}. Referência simples de classe mais frequente: {r['baseline_frequencias_treino']['acuracia']:.2%}. A regra geradora teria 100% por definição, sem comprovar adequação comercial.

A seleção interna escolheu **{r['modelo']}**, regularização {r['alpha']}. Quatro conjuntos de variáveis e três penalidades foram comparados em três dobras por empresa. A concordância interna média foi {r['cv_escolhido']['acuracia']:.2%}. O teste externo não foi usado para escolher o modelo.

## Fórmula aprendida

z = {m.beta[0]:.6f} × funcionários_padronizados + {m.beta[1]:.6f} × estoque_padronizado + {m.beta[2]:.6f} × bens_padronizados.

score = 1/(1+exp(-z)). Cada variável é padronizada depois de log(1+valor); use as médias e desvios em `formula_parametros.json`. Não multiplicar os pesos diretamente pelos valores brutos em reais. A fórmula independente foi conferida contra todos os scores do teste.

{table(w.round(6))}

Os três sinais ficaram positivos nas reamostragens. Isso é estabilidade condicional à referência proposta; **não é prova de significância estatística independente ou causalidade**. Os pesos são estimados, mas favorecem as variáveis que a política escolheu para criar os rótulos.

## Faixas aprendidas

| Score sem arredondamento | Indicação |
|---|---|
| 0 ≤ S < {cut1:.9f} | Essencial |
| {cut1:.9f} ≤ S < {cut2:.9f} | Prático |
| {cut2:.9f} ≤ S ≤ 1 | Total |

Os limites vêm dos dois limiares estimados da regressão, transformados pela função logística. A indicação usa a mediana ordinal; pode diferir da maior probabilidade de classe. Não arredondar o score antes de enquadrar. O intervalo do Total é estreito porque esta escala concentra scores altos perto de 1; não representa pouca frequência de clientes Total. Precisão decimal não significa certeza comercial.

## O que funcionou e o que não funcionou

- Empregados, estoque e bens foram suficientes para a melhor log-loss ordinal interna. Faturamento, contexto, área e termos de endereço não melhoraram o critério de seleção nesta comparação; isso não prova que sejam irrelevantes fora desta política.
- No teste: Essencial 64/66, Prático 24/43, Total 28/35. Prático foi a classe mais difícil: 16 casos desceram para Essencial e 3 subiram para Total. Houve 28 divergências no total, todas entre classes vizinhas.
- O comparador de regressão multinomial obteve log-loss interna 0,2133 e concordância 91,57%, contra 0,3759 e 84,15% da ordinal. **A ordinal não foi o melhor classificador comparado.** Sua restrição de um único eixo e pesos comuns custa desempenho nesta política. Mantivemos a ordinal como versão experimental por entregar o índice unidimensional solicitado; não a apresentamos como vencedora geral.
- Alterar a política muda aproximadamente 21%–23% das indicações internas. Portanto as recomendações dependem materialmente das hipóteses. Nenhum dos cenários foi escolhido pelo resultado do teste.
- As probabilidades não foram calibradas para vendas reais; não representam chance de contratação. A avaliação mede reprodução de uma política construída.

## Sensibilidade

{table(sens[['cenario','mudanca_recomendacao_oof','variacao_media_score_oof','corte1','corte2']].round(6))}

Os pesos por cenário e os intervalos bootstrap estão nos arquivos anexos. O score médio muda pouco, mas os cortes mudam bastante; nunca misturar score de uma versão com cortes de outra.

## Exemplos, incluindo erros

Primeiro caso disponível de cada referência e primeiro erro de cada classe, sem escolher apenas acertos:

{table(cases[['empresa_id','imovel_id','referencia_criterios','plano_indicado','score','acertou_referencia']].round(6))}

## RAG e reprodução

`perfis_rag_teste.jsonl` contém 144 perfis estruturados com contribuições, perguntas e limitações. `modelo_ordinal.pkl` congela a transformação, pesos e critérios. `inferir.py` aplica a novos CSVs preparados. `METODO.md` explica a política e a matemática. O notebook apresenta a mesma execução, sem retreinar no teste. Onze verificações numéricas e de integridade passaram, além da conferência independente da fórmula.

**Conclusão honesta:** o índice já funciona e produz pesos, faixas e explicações para a competição. Há evidência de generalização da política na base mock, mas a sensibilidade e o melhor resultado multinomial mostram que a versão ordinal deve ser apresentada como um compromisso explicável, não como plano ideal comprovado.
'''
(P/'RELATORIO_RESULTADOS.md').write_text(text)
nb=n.v4.new_notebook(cells=[n.v4.new_markdown_cell('# Índice por regressão ordinal — base mock do hackathon\nEste notebook lê a execução congelada. Para refazer o experimento completo, execute `executar.py`. Não reotimiza a partir do teste.'),n.v4.new_code_cell("from pathlib import Path\nimport json\nimport pandas as pd\nfrom IPython.display import display, Markdown, Image\np = Path.cwd()\ndisplay(Markdown((p/'RELATORIO_RESULTADOS.md').read_text()))"),n.v4.new_code_cell("display(pd.read_csv(p/'resultados/ranking_cv.csv'))\ndisplay(pd.read_csv(p/'resultados/pesos_e_estabilidade.csv'))"),n.v4.new_code_cell("display(Image(filename=str(p/'resultados/diagnosticos.png')))\ndisplay(pd.read_csv(p/'resultados/casos_explicados.csv'))"),n.v4.new_code_cell("display(json.loads((p/'resultados/formula_parametros.json').read_text()))\ndisplay(json.loads((p/'resultados/testes_execucao.json').read_text()))\ndisplay(json.loads((p/'resultados/perfis_rag_teste.jsonl').read_text().splitlines()[0]))")],metadata={'kernelspec':{'name':'python3','display_name':'Python 3','language':'python'}})
n.write(nb,P/'03_indice_regressao_base_mock.ipynb')
print('Relatório, fórmula, figura e notebook gerados.')
