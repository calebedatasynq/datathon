
import chromadb
from sentence_transformers import SentenceTransformer

# 1. Carregar o modelo
modelo = SentenceTransformer(
    "paraphrase-multilingual-MiniLM-L12-v2"
)

# 2. Conectar à base vetorial
cliente_chroma = chromadb.PersistentClient(
    path="./banco_vetorial"
)

colecao = cliente_chroma.get_collection(
    name="catalogo_coberturas"
)

# 3. Receber uma pergunta
pergunta = input("Digite sua pergunta sobre as coberturas: ")

# 4. Transformar a pergunta em embedding
embedding_pergunta = modelo.encode(
    [pergunta],
    normalize_embeddings=True
).tolist()

# 5. Buscar todos os documentos do catálogo
resultados = colecao.query(
    query_embeddings=embedding_pergunta,
    n_results=colecao.count()
)

# 6. Encontrar a cobertura mais próxima da pergunta
melhores_distancias = {}

for metadados, distancia in zip(
    resultados["metadatas"][0],
    resultados["distances"][0]
):
    cobertura = metadados["cobertura_fixa"]

    if (
        cobertura not in melhores_distancias
        or distancia < melhores_distancias[cobertura]
    ):
        melhores_distancias[cobertura] = distancia

coberturas_ordenadas = sorted(
    melhores_distancias.items(),
    key=lambda item: item[1]
)

# 7. Mostrar as três coberturas mais próximas
print("\nCoberturas mais relacionadas à pergunta:\n")

for cobertura, distancia in coberturas_ordenadas[:3]:
    print(f"- {cobertura} (distância: {distancia:.4f})")

# 8. Confirmar os planos no catálogo recuperado
if coberturas_ordenadas:
    cobertura_escolhida = coberturas_ordenadas[0][0]

    planos = sorted({
        metadados["plano"]
        for metadados in resultados["metadatas"][0]
        if metadados["cobertura_fixa"] == cobertura_escolhida
    })

    print(f"\nCobertura selecionada: {cobertura_escolhida}")
    print("Planos associados:")

    for plano in planos:
        print(f"- {plano}")
