# Templates do Seguro Empresarial sem RAG

## Versão simplificada para leitura

Abra `simplificados/Templates_Simplificados.xlsx`: duas abas com score visível e somente os campos essenciais. Os CSVs reduzidos também estão nessa pasta. Os arquivos completos de `saidas/` mantêm o formato técnico original.

Versão preliminar reproduzível do protótipo, preparada em 28/10/2026.

## Onde começar

Os CSVs preenchidos estão em `saidas/teste_comum/`. São os dois arquivos exigidos para os 144 estabelecimentos da base comum. Os equivalentes para desenvolvimento estão em `saidas/desenvolvimento/`.

As sugestões de plano e os valores são condicionais. Há pendências explícitas de elegibilidade, dados do cliente e revisão contratual. Estes arquivos ainda não devem ser apresentados como entrega definitiva validada pelo RAG.

## O que já funciona

- Lê as bases mock originais, confere chaves e usa a regressão ordinal v2 já entregue.
- Mantém o modelo e seus cortes, sem novo treinamento.
- Faz a triagem cadastral e suspende ofertas com sinais que exigem verificação.
- Relaciona os planos às coberturas fixas do catálogo e identifica adicionais candidatos.
- Calcula cenários monetários onde os dados permitem, com regras e escopo registrados.
- Explica exceções sem estimativa, formula perguntas e registra pendências por cobertura.
- Confere os dois templates entre si e reproduz o índice original nos 3.122 registros.

## Usar em outro computador

Extraia a pasta completa. Requer Python 3.9 ou superior. Não requer internet, bibliotecas adicionais, acesso a este computador ou RAG.

```text
python testar.py
python executar.py
```

No Linux, use `python3` se necessário; no Windows, `py -3`. Os caminhos internos são localizados pela pasta do programa. Para preservar os CSVs recebidos e gerar outra execução:

```text
python executar.py --saida nova_execucao
```

As fontes em `dados/` são somente lidas. A execução padrão atualiza apenas `saidas/`. Para alterar hipóteses, edite `politica.json`, revise a metodologia e os testes antes de comparar saídas.

## Como interpretar

- `PENDENTE_VALIDACAO` não significa inelegível. A base não comprova todos os requisitos de aceitação.
- Um plano preenchido é uma sugestão condicional do índice. As coberturas seguem esse plano; adicionais estão marcados como candidatos.
- Plano vazio indica oferta suspensa por restrição cadastral ou dados essenciais insuficientes. O plano do índice continua disponível em `auditoria.json` quando calculável.
- Confiança `BAIXA` expressa pendências concretas e estimativas parciais. Não é o score nem uma probabilidade calibrada.
- Valores em branco não são zero. Cada ausência tem motivo, pergunta e regra registrados.
- As faixas patrimoniais são cenários cadastrais parciais, sem estimativa do prédio. Não são preço do seguro, indenização garantida ou limite aceito pela seguradora.

Leia `documentacao/METODO.md`, `documentacao/PENDENCIAS_POS_RAG.md` e `documentacao/RELATORIO_EXECUCAO.md` antes da apresentação.
