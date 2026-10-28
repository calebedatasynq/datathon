
import pandas as pd

# 1. Carregar os dados das empresas
caminho_arquivo = "dados/empresas.csv"

df = pd.read_csv(
    caminho_arquivo,
    encoding="utf-8-sig"
)

# 2. Mostrar o tamanho da base
print("Dimensões da base:", df.shape)

# 3. Conferir as colunas
print("\nColunas disponíveis:")
print(df.columns.tolist())

# 4. Visualizar os primeiros registros
print("\nPrimeiras 5 empresas:")
print(df.head().to_string(index=False))

# 5. Verificar valores ausentes
print("\nValores ausentes por coluna:")
print(df.isnull().sum().to_string())

# 6. Verificar identificadores duplicados
if "empresa_id" in df.columns:
    print(
        "\nQuantidade de empresa_id duplicados:",
        df["empresa_id"].duplicated().sum()
    )

# 7. Estatísticas das colunas numéricas
print("\nResumo estatístico:")
print(df.describe().to_string())
