# Fontes e limites do enquadramento

Consulta original em 28/10/2026. Página oficial de planos: https://campanhas.bbseguros.com.br/seguro-empresarial/

Catálogo entregue no desafio: `dados/originais/Seguro_Empresarial_Desenvolvimento/catalogo_coberturas_fixas_planos.csv`.

O catálogo e a página relacionam as coberturas dos pacotes. Nossa política usa empregados como indicador indireto de prioridade para RC empregador e patrimônio como indicador indireto de prioridade para proteção contra roubo. O BB não definiu os percentis usados pelo nosso experimento.

A referência central prioriza Total quando empregados >=percentil 75 do desenvolvimento; caso contrário, Prático quando estoque ou bens >=percentil 60; demais casos Essencial. Valores completos em `modelo/criterios_referencia.json`. Essa referência não confirma necessidades, elegibilidade, importância segurada ou capacidade de pagamento. Vidros e vendaval exigem confirmação adicional.

Condições gerais oficiais localizadas na pesquisa, versão 1.1: https://assets-bbsegurosportal.bbseguros.com.br/2024-08/cg-seguro-empresarial-v_1-1.pdf?VersionId=F5j.aDPjl.ePJzIhjV.z1Y1Nbm0byQ6M

O pacote não inclui um corpus completo das condições gerais. A dupla do RAG deve usar documentos apropriados à versão do produto que vai demonstrar. Não tratar o catálogo resumido como substituto de condições, exclusões ou análise de aceitação.

A precisão calculada nos relatórios é concordância com referências construídas em dados mock. Não comprova adequação do plano, aumento de vendas ou calibração para clientes reais. O RAG não deve esconder essa natureza experimental.
