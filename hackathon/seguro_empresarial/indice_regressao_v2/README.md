# Versão 2: 8–10 variáveis

Leia RELATORIO_ITERACOES.md ou 04_iteracoes_8_9_10_variaveis.ipynb.

Para reproduzir: instale requirements.txt; ajuste ROOT em executar.py para a pasta do projeto e os caminhos locais em gerar_entrega.py; execute `python executar.py` e `python gerar_entrega.py`. Precisa das bases preparadas do projeto e dos critérios congelados da v1 para verificar que a política não mudou.

Para aplicar o modelo: `python inferir.py base_preparada.csv --saida perfis.jsonl`. Os nomes das 8 colunas estão em resultados/resultado.json. Não abrir pickle de origem desconhecida.

Seleção pela validação agrupada no desenvolvimento. Teste comum é reavaliação, pois já foi consultado na v1. O pseudo-R² preditivo não é proporção da variância nem taxa de acerto. A inclusão de variáveis adicionais não comprovou ganho sobre a v1.
