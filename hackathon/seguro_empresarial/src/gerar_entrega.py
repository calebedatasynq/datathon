"""Gera relatório e notebook executado a partir de resultados reais."""
import base64
import hashlib
import html
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import tempfile

import nbformat
from nbclient import NotebookClient
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'resultados'


def auditoria_fontes():
    fonte=Path(os.environ.get('SEGURO_FONTES_ORIGINAIS','/home/lucas/Downloads/Seguro_Empresarial_DadosSinteticos'))
    linhas=[]
    for p in sorted((ROOT/'dados/originais').glob('*/*.csv')):
        original=fonte/p.relative_to(ROOT/'dados/originais')
        sha=hashlib.sha256(p.read_bytes()).hexdigest()
        referencia=hashlib.sha256(original.read_bytes()).hexdigest() if original.exists() else None
        linhas.append({'arquivo':str(p.relative_to(ROOT/'dados/originais')),
                       'sha256_copia':sha,'sha256_original':referencia,
                       'igual_ao_original':sha==referencia if referencia else 'ORIGINAL EXTERNO NÃO DISPONÍVEL'})
    df=pd.DataFrame(linhas)
    df.to_csv(OUT/'conferencia_fontes_originais.csv',index=False)
    if df.igual_ao_original.eq(False).any():raise ValueError('Cópia difere da fonte externa')
    return df


def decisoes():
    rows=[
      ('grupo_atividade','MANTER PARA TESTAR','Representa atividades com diferentes necessidades; 10 categorias observadas','Categorias não possuem ordem numérica'),
      ('funcionarios_estimados_empresa','MANTER PARA TESTAR','Hipótese relacionada à operação e RC empregador; dado completo','É da empresa inteira, não funcionários locais'),
      ('quantidade_estabelecimentos_empresa','CONTROLE DE CONTEXTO','Permite contextualizar medidas corporativas repetidas em unidades','Contagem do pacote, não critério automático de upgrade'),
      ('tipo_unidade','CONTROLE DE CONTEXTO','Matriz/filial; dado completo','Contribuição adicional só poderá ser medida com Y'),
      ('estoque_medio_estimado','MANTER PARA TESTAR','Estoque do estabelecimento; dado completo e confere com fonte','Já é estimativa; não mede risco de roubo'),
      ('valor_bens_ponderado_estabelecimento','MANTER PARA TESTAR','Agregação confere integralmente com valores ponderados dos bens','Não é importância segurada nem comprovação de localização'),
      ('faturamento_mensal_empresa','ALTERNATIVA À VARIÁVEL FUNCIONÁRIOS','Correlação por empresa 0,9346; VIF exploratório em log 13,55 com demais medidas','Não descartar definitivamente; comparar modelo econômico com modelo de emprego'),
      ('area_m2','MODELO ALTERNATIVO','61,72% ausente; avaliar modelo com e sem área','Imputador deve ser ajustado só no treino; ausência pode carregar viés'),
      ('estoque_pico_estimado','ALTERNATIVA AO ESTOQUE MÉDIO','Correlação 0,9947, sem identidade de valores','Usar como alternativa, não os dois automaticamente'),
      ('indice_maturidade_digital','EXCLUIR DUPLICATA','Idêntica a dependencia_digital_pct nos 2.500 registros de empresas','A exclusão é por duplicação, não por significância'),
      ('dependencia_digital_pct e índices digitais','RESERVAR PARA HIPÓTESE ESPECÍFICA','Dados variam; não há Y para provar ou refutar contribuição','Avaliar se distinguem planos fixos ou apenas adicionais/assistências'),
      ('cnae_principal / descricao_cnae','ALTERNATIVA À ATIVIDADE AGRUPADA','Representações de atividade; começar com 10 grupos facilita interpretação','Não repetir representações por padrão'),
      ('porte','ALTERNATIVA À ESCALA CONTÍNUA','Categoria MICRO/PEQUENA, relacionada à dimensão econômica','Pode ser comparado depois; não empilhar todas as medidas de tamanho'),
      ('folha / compras / energia / despesas fixas','RESERVAR','Disponíveis e variáveis; investigação de redundância consta no arquivo de correlações','Nenhuma conclusão de irrelevância estatística foi feita'),
      ('padrao_construtivo_cadastrado','NÃO PRIORIZAR NO MODELO DE PLANOS','81,83% NAO_DISPONIVEL','Pode apoiar confirmação do imóvel'),
      ('material_parede_externa_cadastrado','AUXILIAR DE ELEGIBILIDADE','84,76% NAO_DISPONIVEL','Ausência não significa material aceito'),
      ('possui_termo_loja / possui_termo_galeria','CONDICIONAL','Flags do cadastro preservadas e conferidas','Não significam térreo ou vitrine comprovados'),
      ('UF / município / coordenadas','RESERVAR ENRIQUECIMENTO','Localização não traz índices de roubo, alagamento ou vendaval','Não transformar código IBGE em grandeza numérica'),
    ]
    df=pd.DataFrame(rows,columns=['variavel','decisao','evidencia_ou_hipotese','limite'])
    df['significancia_para_planos']='NÃO AVALIÁVEL SEM ASSOCIAÇÕES DE REFERÊNCIA'
    df.to_csv(OUT/'decisoes_variaveis.csv',index=False,encoding='utf-8-sig')
    return df


def tabela_md(df):
    cols=list(df.columns)
    def cel(v):return '—' if pd.isna(v) else str(v).replace('|','/').replace('\n',' ')
    return '\n'.join(['| '+' | '.join(cols)+' |','| '+' | '.join(['---']*len(cols))+' |']+
                     ['| '+' | '.join(cel(v) for v in row)+' |' for row in df.itertuples(index=False,name=None)])


def gerar_relatorio(fontes,decisao):
    resumo=json.loads((OUT/'estado_analise.json').read_text())
    testes=pd.read_csv(OUT/'testes_integridade.csv')
    casos=pd.read_csv(OUT/'casos_demonstracao.csv')
    niveis=pd.read_csv(OUT/'situacao_por_plano.csv')
    exemplos=casos[['caso','empresa_id','imovel_id','grupo_atividade','tipo_unidade','area_m2','estoque_medio_estimado','valor_bens_ponderado_estabelecimento']]
    texto=f'''# Resultado honesto da etapa de variáveis e preparação

Data: 28/10/2026. As três categorias de saída são conhecidas: ESSENCIAL, PRATICO e TOTAL.

## Resultado alcançado

- {len(testes)} testes executados, {testes.resultado.eq('APROVADO').sum()} aprovados, {testes.resultado.ne('APROVADO').sum()} com falha/erro.
- {fontes.igual_ao_original.eq(True).sum()} de {len(fontes)} CSVs copiados conferem byte a byte com os arquivos originais externos disponíveis.
- Desenvolvimento: 2.978 estabelecimentos e 2.500 empresas. Teste Comum: 144 e 120.
- {resumo['variaveis_examinadas']} campos foram inspecionados na tabela ampliada, incluindo aliases preservados para auditoria e campos de cadastro; não são 62 preditores independentes propostos.
- 18 decisões de variáveis documentadas; 23 cenários com identificadores e valores reais conferidos com as fontes.
- Partição proposta: {resumo['treino_linhas']} linhas de desenvolvimento/treino e {resumo['avaliacao_linhas']} para avaliação reservada, com zero empresas compartilhadas.
- A execução não estimou acurácia, coeficientes, valores-p em relação aos planos ou cortes do score: não há associação de referência entre os estabelecimentos e os três planos.

## O que significa “cada caso” nesta entrega

Há pelo menos um exemplo de cada uma das dez atividades e de cada condição verificada: área disponível/ausente; empresa com uma/várias unidades; matriz/filial; faturamento informado/presumido; existência/ausência de bens de baixa confiança; imóvel em obra/irregular; endereço incompatível. São cenários de dados, não exemplos comprovados de cada plano.

{tabela_md(niveis)}

Não atribuí planos fictícios para preencher essa tabela. Para treinar, plano de referência pode ser uma recomendação revisada por especialistas; não precisa ser o plano atualmente contratado. Para identificar upgrade real, o plano atualmente contratado será necessário posteriormente.

## Revisão da lista inicial

A lista anterior de oito variáveis foi revisada, sem forçar sua confirmação. A especificação de emprego usa seis campos: atividade, funcionários da empresa, número de unidades, matriz/filial, estoque médio e bens ponderados. A especificação econômica substitui funcionários por faturamento. A terceira adiciona área à especificação de emprego.

Faturamento e funcionários têm correlação 0,9352 por estabelecimento e 0,9346 por empresa única. No diagnóstico numérico em log e 1.140 casos completos, seus VIFs foram 13,55 e 10,90. Isso motiva comparação de especificações, não prova que um deles é inútil. A área falta em 61,72% das linhas. Estoque médio e pico têm correlação 0,9947, mas não são iguais. Maturidade e dependência digital são duplicatas exatas.

O VIF é um diagnóstico parcial das variáveis numéricas, em casos completos; não é inferência sobre planos, nem avaliação de todas as categorias do futuro modelo. O Teste Comum não foi usado para selecionar uma especificação por desempenho.

{tabela_md(decisao.drop(columns='significancia_para_planos'))}

## Exemplos explícitos e conferidos

Valores monetários em reais. Área ausente aparece como “—”. O CSV de casos contém mais campos de qualidade e a quantidade de exemplos disponíveis em cada condição.

{tabela_md(exemplos)}

## O que os testes comprovam e o que permanece aberto

Comprovam a preservação das chaves, valores corporativos sem rateio, contagens de unidades e bens, soma de bens por imóvel, estoque por estabelecimento, tratamento de áreas e flags, identidade das classes do catálogo e bloqueio de treinamento sem referências. O arquivo `testes_integridade.csv` identifica cada teste; `testes_execucao.txt` tem o log.

Não comprovam que as seis variáveis sugeridas sejam preditivamente melhores, que os planos recomendados sejam adequados ou que a hipótese ordinal se sustente. Também não validam a qualidade original dos dados sintéticos, apenas sua preparação e os diagnósticos apresentados. Não há “melhor modelo” medido nesta entrega.

## Modelagem preparada para receber referências

`src/treinar.py` compara três especificações de regressão logística ordinal usando cinco dobras por empresa dentro do treino. O critério predefinido é menor log loss, com erro ordinal como desempate. Somente a especificação selecionada acessa a avaliação reservada. Imputação e codificação são ajustadas no treino de cada dobra. Os coeficientes finais usam erros agrupados por empresa e seus valores-p são explicitamente exploratórios após seleção de especificação.

Quando houver rótulos suficientes, ainda serão necessários diagnóstico de chances proporcionais, calibração por plano, intervalos de desempenho e revisão independente da adequação das recomendações. O script não declara aprovação do produto apenas por uma métrica. Não foi ajustado um modelo com alvo artificial para alegar esses resultados.

O score proposto é `logistica(z)`, com limiares transformados da mesma maneira. A regra de classificação ordinal usa a mediana das classes; não é necessariamente a classe mais provável. A escala não representa probabilidade de compra. Os limites ainda não existem: dependem do ajuste e da validação.

## Próxima ação concreta

Preencher e revisar `dados/rotulos/rotulos_revisados.csv`, que já contém os 2.978 pares empresa-imóvel, com plano de referência, justificativa, revisor, fonte e versão do critério. Reservar a avaliação do desempenho para dados não usados na escolha de regras e modelos. A hipótese de negócio precisa ser revisada antes da rotulagem; ter as três categorias prontas não resolve essa associação.

Um diferencial defensável para a apresentação é a rastreabilidade: dados originais, regras de preparação, registro da qualidade e perguntas de confirmação, empresas separadas para avaliação e revisão humana registrada. O benefício comercial desse diferencial ainda precisa ser medido.
'''
    (OUT/'RELATORIO_RESULTADOS.md').write_text(texto,encoding='utf-8')
    imagem=base64.b64encode((OUT/'diagnostico_variaveis.png').read_bytes()).decode()
    pagina=f'''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><title>Seguro Empresarial — resultados</title>
<style>body{{font:16px/1.6 system-ui;background:#f4f7fb;color:#17263c;max-width:1250px;margin:30px auto;padding:24px}}main{{background:white;padding:32px;border-radius:16px}}h1,h2{{color:#164584}}table{{border-collapse:collapse;width:100%;font-size:13px;margin:20px 0}}td,th{{border:1px solid #d5dfea;padding:8px;text-align:left}}th{{background:#edf3fb}}.box{{background:#eaf2ff;padding:16px;border-left:5px solid #2563eb}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}img{{width:100%}}section{{overflow:auto}}</style><main><h1>Seguro Empresarial: dados e variáveis</h1>
<div class="box">{len(testes)} testes aprovados · {len(casos)} cenários demonstrados · 0 associações cliente-plano disponíveis · nenhum acerto preditivo alegado</div>
<h2>Diagnóstico observado</h2><img src="data:image/png;base64,{imagem}" alt="Ausências e redundância nas variáveis">
<h2>Situação por plano</h2>{niveis.to_html(index=False)}
<h2>Decisões sobre as variáveis</h2><section>{decisao.to_html(index=False)}</section>
<h2>Exemplos conferidos com as fontes</h2><section>{exemplos.to_html(index=False,na_rep='Ausente')}</section>
<h2>Relatório integral e limites da conclusão</h2><pre>{html.escape(texto)}</pre></main></html>'''
    (OUT/'RELATORIO_RESULTADOS.html').write_text(pagina,encoding='utf-8')


def gerar_notebook():
    nb=nbformat.v4.new_notebook()
    md=nbformat.v4.new_markdown_cell;code=nbformat.v4.new_code_cell
    nb.cells=[
      md('# Seguro Empresarial — auditoria, variáveis e regressão ordinal\n\nNotebook executado em 28/10/2026. Categorias: ESSENCIAL, PRATICO e TOTAL. Plano de referência por estabelecimento ainda ausente. Os resultados abaixo separam auditoria de dados, hipóteses de variáveis e modelagem supervisionada. A proposta IPU foi descartada.'),
      code("from pathlib import Path\nimport sys, json, subprocess\nimport pandas as pd\nfrom IPython.display import display, Image, Markdown\nROOT = Path.cwd() if (Path.cwd()/'src').exists() else Path.cwd().parent\nsys.path.insert(0,str(ROOT/'src'))\nOUT=ROOT/'resultados'\nprint('Projeto:',ROOT)\nprint('Python:',sys.version.split()[0],'pandas:',pd.__version__)"),
      md('## 1. Reproduzir preparação e conferir as fontes\nUma linha por estabelecimento; sem rateio de receita/funcionários e sem rótulos inventados. Os arquivos originais são preservados.'),
      code("r=subprocess.run([sys.executable,str(ROOT/'src/preparar_base.py'),'--origem',str(ROOT/'dados/originais'),'--saida',str(ROOT/'dados/preparados')],capture_output=True,text=True,check=True)\nprint(r.stdout)\nfrom analisar import executar as auditar\ndisplay(auditar())\nfrom gerar_entrega import auditoria_fontes\nfontes=auditoria_fontes()\ndisplay(fontes[['arquivo','igual_ao_original']])"),
      md('## 2. Situação por plano e possibilidade de treinamento\nConhecer o nome das classes é diferente de ter exemplos associados às classes. Não é obrigatório conhecer o plano contratado para treinar recomendação: pode-se usar um plano de referência revisado.'),
      code("display(pd.read_csv(OUT/'situacao_por_plano.csv'))\nfrom treinar import executar as modelar\nestado=modelar()\ndisplay(estado)"),
      md('## 3. Testes contra os dados originais\nA aprovação dos testes demonstra integridade da preparação e funcionamento das barreiras de entrada. Não mede acerto de recomendação de planos.'),
      code("r=subprocess.run([sys.executable,str(ROOT/'tests/test_integridade.py')],capture_output=True,text=True)\nprint(r.stdout)\nif r.returncode: print(r.stderr); print((OUT/'testes_execucao.txt').read_text()); raise RuntimeError('Falha nos testes')\ndisplay(pd.read_csv(OUT/'testes_integridade.csv').fillna(''))"),
      md('## 4. Inspecionar outras variáveis\nTabela ampliada de diagnóstico, não lista de preditores finais. Inclui aliases para conferência. Ausência considera códigos como NAO_DISPONIVEL e área zero. Nenhuma associação estatística com plano foi estimada.'),
      code("display(pd.read_csv(OUT/'resumo_bases.csv'))\nqualidade=pd.read_csv(OUT/'qualidade_todas_variaveis.csv')\nprint('Campos examinados:',len(qualidade))\nwith pd.option_context('display.max_rows',100): display(qualidade)"),
      md('## 5. Redundância e estabilidade potencial dos coeficientes\nCorrelação não seleciona sozinha o modelo. O VIF abaixo usa apenas variáveis numéricas em log e 1.140 casos completos; não substitui o diagnóstico da especificação final com categorias.'),
      code("display(pd.read_csv(OUT/'redundancias.csv').head(30))\ndisplay(pd.read_csv(OUT/'vif_exploratorio.csv'))\ndisplay(Image(filename=str(OUT/'diagnostico_variaveis.png')))"),
      md('## 6. Decisão sobre cada candidata\nRevisamos a lista inicial. A primeira especificação tem atividade, funcionários, número de unidades, tipo de unidade, estoque e bens. A alternativa econômica substitui funcionários por faturamento; uma terceira avalia área. Nenhuma foi declarada superior em previsão.'),
      code("display(pd.read_csv(OUT/'decisoes_variaveis.csv'))\nfrom treinar import ESPECIFICACOES\ndisplay(ESPECIFICACOES)"),
      md('## 7. Resultados explícitos de cada cenário\nPelo menos um exemplo de cada atividade e condição relevante de cadastro. Estes não são exemplos validados de cada plano. Valores monetários em reais; funcionários e receita mantêm a granularidade da empresa.'),
      code("casos=pd.read_csv(OUT/'casos_demonstracao.csv')\nprint('Cenários cobertos:',len(casos))\nwith pd.option_context('display.max_rows',100,'display.max_columns',30): display(casos)\ndisplay(pd.read_csv(OUT/'perfil_por_atividade.csv'))"),
      md('## 8. Separação por empresa\nA partição é proposta e fixa, sem consultar desempenho ou ajustar regras na avaliação. O Teste Comum é usado para aplicação e preparação, não para escolher variáveis.'),
      code("part=pd.read_csv(OUT/'particao_empresas_proposta.csv')\ndisplay(part.groupby('particao_proposta').agg(linhas=('imovel_id','size'),empresas=('empresa_id','nunique')))\na=set(part[part.particao_proposta.eq('treino_desenvolvimento')].empresa_id)\nb=set(part[part.particao_proposta.eq('avaliacao_reservada')].empresa_id)\nprint('Empresas compartilhadas:',len(a&b))"),
      md('## 9. Modelagem preparada e limites\n`src/treinar.py` prevê comparação ordinal em cinco dobras agrupadas, seleção por log loss e avaliação reservada. O score é uma transformação da posição ordinal e não a probabilidade de comprar. Os limiares vêm do ajuste; a regra de classificação é a mediana das classes. Chances proporcionais e calibração ainda exigirão análise depois dos rótulos. Valores-p após seleção são exploratórios.\n\nQuando não há planos associados aos exemplos, coeficientes, acurácia e cortes devem permanecer ausentes.'),
      code("if estado.get('treinado'):\n    display(pd.read_csv(OUT/'comparacao_modelos_cv.csv'))\n    display(pd.read_csv(OUT/'matriz_confusao_avaliacao.csv'))\n    display(pd.read_csv(OUT/'coeficientes_exploratorios.csv'))\nelse:\n    print('Acurácia: NÃO ESTIMÁVEL')\n    print('Significância em relação aos planos: NÃO ESTIMÁVEL')\n    print('Limites do score: AINDA NÃO ESTIMADOS')\n    print('Preencher dados/rotulos/rotulos_revisados.csv com referências revisadas.')"),
      md('## 10. Como defender na apresentação\n“Testamos a integridade dos dados, documentamos as hipóteses de variáveis e mostramos casos reais do dataset. Encontramos redundância entre tamanho econômico e funcionários, muitos dados de área ausentes e índices duplicados. Nossa comparação de modelos será por empresas separadas e só poderá medir acerto depois da associação de planos de referência. A solução busca recomendação rastreável e revisão humana, com limites de validade explícitos.”\n\nReferências: [Statsmodels — modelo ordinal](https://www.statsmodels.org/stable/examples/notebooks/generated/ordinal_regression.html), [Scikit-learn — validação agrupada](https://scikit-learn.org/stable/modules/cross_validation.html), [calibração](https://scikit-learn.org/stable/modules/calibration.html).'),
    ]
    temp=Path(tempfile.mkdtemp(prefix='hackathon-kernel-'))
    kernel=temp/'kernels/hackathon_seguro';kernel.mkdir(parents=True)
    (kernel/'kernel.json').write_text(json.dumps({'argv':[sys.executable,'-m','ipykernel_launcher','-f','{connection_file}'],'display_name':'Python seguro','language':'python'}))
    os.environ['JUPYTER_PATH']=str(temp)
    os.environ['IPYTHONDIR']=str(temp/'ipython')
    os.environ['JUPYTER_RUNTIME_DIR']=str(temp/'runtime')
    os.environ['MPLCONFIGDIR']='/tmp/hackathon-matplotlib'
    nb.metadata.kernelspec={'name':'hackathon_seguro','display_name':'Python seguro','language':'python'}
    NotebookClient(nb,timeout=120,kernel_name='hackathon_seguro',resources={'metadata':{'path':str(ROOT)}}).execute()
    # Usar o kernel padrão ao abrir em outra máquina; o ambiente executado foi registrado.
    nb.metadata.kernelspec={'name':'python3','display_name':'Python 3','language':'python'}
    nbformat.validate(nb)
    for cell in nb.cells:
        for output in cell.get('outputs',[]):
            if output.output_type=='error':raise RuntimeError('Notebook com erro de execução')
    destino=ROOT/'notebooks/01_auditoria_variaveis_modelagem.ipynb'
    nbformat.write(nb,destino)
    return destino


def executar():
    fontes=auditoria_fontes();decisao=decisoes()
    gerar_relatorio(fontes,decisao)
    versions={p:importlib.metadata.version(p) for p in ['pandas','numpy','scipy','scikit-learn','statsmodels','matplotlib','nbformat','nbclient','ipykernel']}
    (OUT/'ambiente_execucao.json').write_text(json.dumps({'python':sys.version,'pacotes':versions},indent=2)+'\n')
    (ROOT/'requirements.txt').write_text('\n'.join(f'{p}=={v}' for p,v in versions.items())+'\n')
    print('Notebook executado:',gerar_notebook())


if __name__=='__main__':executar()
