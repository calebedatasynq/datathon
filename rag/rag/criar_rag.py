
import pandas as pd
import chromadb
from sentence_transformers import SentenceTransformer

# 1. Ler o catálogo
caminho_arquivo = "dados/catalogo_coberturas_fixas_planos.csv"

df = pd.read_csv(caminho_arquivo, encoding="utf-8-sig")

# 2. Validar e limpar os dados
colunas_necessarias = {"plano", "cobertura_fixa"}

if not colunas_necessarias.issubset(df.columns):
    raise ValueError("O catálogo não possui todas as colunas necessárias.")

df = df.dropna(subset=["plano", "cobertura_fixa"]).copy()

df["plano"] = df["plano"].astype(str).str.strip()
df["cobertura_fixa"] = df["cobertura_fixa"].astype(str).str.strip()

df = df.drop_duplicates(
    subset=["plano", "cobertura_fixa"]
).reset_index(drop=True)


# 3. Criar documentos textuais mais naturais
documentos = []

for _, linha in df.iterrows():
    plano = linha["plano"]
    cobertura_original = linha["cobertura_fixa"]

    # Transformar o identificador em texto legível
    cobertura_legivel = cobertura_original.replace("_", " ").lower()

    documento = (
        f"No plano de seguro empresarial {plano}, "
        f"uma das coberturas fixas é {cobertura_legivel}. "
        f"Identificador da cobertura: {cobertura_original}."
    )

    documentos.append(documento)


# 4. Carregar o modelo de embeddings
print("Carregando o modelo de embeddings...")

modelo = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")

# 5. Criar os embeddings
print("Gerando embeddings...")

embeddings = modelo.encode(
    documentos,
    normalize_embeddings=True
).tolist()

# 6. Criar um banco vetorial persistente
cliente_chroma = chromadb.PersistentClient(
    path="./banco_vetorial"
)

colecao = cliente_chroma.get_or_create_collection(
    name="catalogo_coberturas",
    metadata={"hnsw:space": "cosine"}
)

# 7. Salvar documentos, vetores e metadados
ids = [f"cobertura_{i}" for i in range(len(documentos))]

metadados = [
    {
        "plano": str(linha["plano"]),
        "cobertura_fixa": str(linha["cobertura_fixa"])
    }
    for _, linha in df.iterrows()
]

colecao.upsert(
    ids=ids,
    documents=documentos,
    embeddings=embeddings,
    metadatas=metadados
)

print(f"\nDocumentos indexados: {colecao.count()}")
print("Base vetorial criada em ./banco_vetorial")
