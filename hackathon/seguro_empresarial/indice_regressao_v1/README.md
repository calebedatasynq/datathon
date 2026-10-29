# Entrega ativa: índice por regressão na base mock

Comece por `RELATORIO_RESULTADOS.md` ou pelo notebook `03_indice_regressao_base_mock.ipynb`.

- `METODO.md`: critérios, vínculo com coberturas e matemática.
- `resultados/pesos_e_estabilidade.csv`: pesos e intervalos condicionais.
- `resultados/formula_parametros.json`: cálculo numérico completo e faixas.
- `resultados/scores_teste_comum.csv`: scores e referências dos 144 estabelecimentos externos.
- `resultados/perfis_rag_teste.jsonl`: saída estruturada para o agente.
- `resultados/referencias_*.csv`: rótulos construídos, dados e motivo da regra.
- `resultados/sensibilidade_criterios.csv`: mudanças de critérios, cortes e indicação.
- `resultados/modelo_ordinal.pkl`: modelo e transformação congelados.

## Reproduzir

Ambiente usado: `/tmp/hackathon-seguro-venv/bin/python`. Em outro computador, instale `requirements.txt` em um ambiente Python e ajuste `ROOT` em `executar.py` para o projeto que contém os dados preparados. Os dados preparados e sua preparação estão no projeto pai.

Execute, nesta pasta:

```bash
python executar.py
python gerar_relatorio.py
```

Isso refaz a seleção e a avaliação conforme protocolo fixo, não deve ser usado para ajustar parâmetros em resposta ao teste já visto. O notebook apenas apresenta os resultados congelados, podendo ser executado sem refazer treinamento.

Para inferência sem treino:

```bash
python inferir.py /caminho/base_preparada.csv --saida perfis.jsonl
```

O CSV deve conter empresa_id, imovel_id e as três variáveis da versão atual. Valores faltantes usam a mediana aprendida; faltas são informadas na saída. Números negativos, infinitos e chaves repetidas são rejeitados. O perfil não substitui avaliação de elegibilidade.

## Como apresentar

“O modelo aprendeu uma política de enquadramento construída com os dados mock e fundamentada nas coberturas. Em empresas separadas para teste, houve 80,56% de concordância com essa política. O índice explica contribuições e alimenta o agente, que pergunta o que falta.”

Não afirmar que houve 80,56% de acerto sobre o plano ideal. A multinomial foi melhor na classificação interna, enquanto a ordinal fornece o score único com faixas. Alterações de critérios mudam cerca de 21%–23% das indicações. Esses limites fazem parte do resultado, não são omitidos.
