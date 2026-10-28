"""PDF das Condições Gerais do Seguro Empresarial → conhecimento/clausulas.jsonl.

Cada chunk é um item numerado (8.1, 3.1.2...) ou uma alínea (8.1 i) de uma das três partes:
  CG  condições gerais         id "CG-8.1.i"
  TT  termos técnicos          id "TT-FURTO_SIMPLES"
  CE  condições especiais      id "<COBERTURA>-3.1.c" (cobertura do catálogo quando existe)
O id é o que a resposta cita: [cl. CG-8.1.i]. Os planos de cada chunk vêm do catálogo
do desafio, nunca do texto do PDF.

Uso: python scripts/extrair_cg.py [--amostra N]
"""

import argparse
import csv
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

from pypdf import PdfReader

RAIZ = Path(__file__).resolve().parent.parent
PDF = RAIZ / "dados" / "cg" / "cg-seguro-empresarial-v1.1.pdf"
CATALOGO = RAIZ / "Seguro_Empresarial_Teste_Comum" / "catalogo_coberturas_fixas_planos.csv"
DESTINO = RAIZ / "conhecimento" / "clausulas.jsonl"
PRODUTO = "SEGURO_EMPRESARIAL_V1.1"

# Título da condição especial no PDF → cobertura do catálogo. Revisado à mão.
COBERTURA_DO_TITULO = {
    "COBERTURA BASICA": "INCENDIO_RAIO_EXPLOSAO_FUMACA",
    "DANOS ELETRICOS": "DANOS_ELETRICOS",
    "DESPESAS FIXAS": "DESPESAS_FIXAS",
    "COBERTURA DE PERDA OU PAGAMENTO DE ALUGUEL": "PERDA_PAGAMENTO_ALUGUEL",
    "COBERTURA DE QUEBRA DE VIDROS": "QUEBRA_DE_VIDROS",
    "COBERTURA DE ROUBO OU FURTO DE BENS MEDIANTE ARROMBAMENTO": "ROUBO_FURTO_ARROMBAMENTO",
    "COBERTURA DE VENDAVAL, GRANIZO, CICLONE, TORNADO E FURACAO": "VENDAVAL_EVENTOS_CORRELATOS",
    "COBERTURA DE RESPONSABILIDADE CIVIL - EMPREGADOR": "RESPONSABILIDADE_CIVIL_EMPREGADOR",
    "COBERTURA DE RESPONSABILIDADE CIVIL - ESTABELECIMENTO": "RESPONSABILIDADE_CIVIL_ESTABELECIMENTO",
}
# Cabeçalhos de agrupamento que antecedem o título real de uma condição especial.
GRUPOS_CE = {"CONDICOES ESPECIAIS", "COBERTURAS ADICIONAIS", "COBERTURAS DE RESPONSABILIDADE CIVIL"}
# "COBERTURAS DE RESPONSABILIDADE CIVIL" também tem seção própria (disposições comuns de RC);
# vale para os planos que têm alguma cobertura de RC.
RC_GERAL = "RESPONSABILIDADE_CIVIL_DISPOSICOES_GERAIS"
COBERTURAS_DE_RC = ("RESPONSABILIDADE_CIVIL_ESTABELECIMENTO", "RESPONSABILIDADE_CIVIL_EMPREGADOR")

# "Exclusivamente para as atividades de X": X → grupo_atividade da base. Revisado à mão.
# Atividade sem correspondência (ex.: pet shop) vira um segmento que nenhum cliente tem.
SEGMENTO_DA_ATIVIDADE = [
    (r"ESTETIC|SALOES|SALAO|CABELEREIR", "BELEZA"),
    (r"BARES|RESTAURANTE|PIZZARIA", "RESTAURANTE"),
    (r"ESCOLA", "ESCOLA_CURSO"),
    (r"FARMACIA", "FARMACIA"),
    (r"OFICINA", "OFICINA"),
    (r"CONSULTORIO", "CLINICA"),
]
SEM_SEGMENTO_DA_BASE = "ATIVIDADE_FORA_DA_BASE"

# Título da seção numerada → tipo do chunk.
TIPO_DA_SECAO = [
    (r"EXCLUID|NAO COBERT|NAO INDENIZ|PERDA DE DIREITOS", "exclusao"),
    (r"FRANQUIA|PARTICIPACAO OBRIGATORIA", "franquia"),
    (r"CARENCIA", "carencia"),
    (r"OBRIGAC|AVISO DE SINISTRO|DOCUMENTOS|FORA DO HORARIO", "obrigacao"),
    (r"COBERT|BENS COBERTOS|OBJETIVO|EMPRESAS ABRANGIDAS|EM TRANSITO|APURACAO", "cobertura"),
]

RE_CABECALHO = re.compile(r"^(Seguro Empresarial - Processo SUSEP|W:\\)")
RE_NUMERO_PAGINA = re.compile(r"^\d{1,3}$")
RE_SECAO = re.compile(r"^(\d+)\.\s+([^a-z]+)$")
RE_ITEM = re.compile(r"^(\d+(?:\.\d+)+)\.?\s+(.*)$")
RE_ALINEA = re.compile(r"^([a-z])\)\s+(.*)$")
RE_TERMO = re.compile(r"^[A-ZÁÉÍÓÚÂÊÔÃÕÇÜ0-9 ,’'()/-]{3,}$")


def sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def normalizar_titulo(texto: str) -> str:
    return re.sub(r"\s+", " ", sem_acento(texto)).strip().upper()


def slug(texto: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", normalizar_titulo(texto)).strip("_")


def planos_por_cobertura() -> dict[str, list[str]]:
    planos = defaultdict(list)
    with open(CATALOGO, encoding="utf-8-sig", newline="") as f:
        for linha in csv.DictReader(f):
            planos[linha["cobertura_fixa"].strip()].append(linha["plano"].strip())
    return dict(planos)


def linhas_do_pdf() -> list[tuple[int, str]]:
    """(página, linha) do corpo do documento, sem cabeçalhos, rodapés e índice."""
    linhas = []
    for indice, pagina in enumerate(PdfReader(PDF).pages):
        for linha in (pagina.extract_text() or "").splitlines():
            linha = linha.strip()
            if linha and not RE_CABECALHO.match(linha) and not RE_NUMERO_PAGINA.match(linha):
                linhas.append((indice + 1, linha))
    # O corpo começa no segundo "CONDIÇÕES GERAIS" (o primeiro está no índice, com pontilhado).
    inicio = next(
        i for i, (_, l) in enumerate(linhas) if normalizar_titulo(l) == "CONDICOES GERAIS" and i > 10
    )
    return linhas[inicio + 1 :]


def indice_condicoes_especiais(linhas: list[tuple[int, str]]) -> int:
    # A última ocorrência: antes dela, "CONDIÇÕES ESPECIAIS" é um verbete dos termos técnicos.
    return max(i for i, (_, l) in enumerate(linhas) if normalizar_titulo(l) == "CONDICOES ESPECIAIS")


def eh_subtitulo(texto: str) -> bool:
    """Item que só nomeia um bloco ("3.1. FARMÁCIA", "1.2. Cobertura Simultânea")."""
    return len(texto) < 45 and not texto.rstrip().endswith((".", ";"))


def tipo_da_secao(titulo: str, parte: str) -> str:
    if parte == "TT":
        return "definicao"
    for padrao, tipo in TIPO_DA_SECAO:
        if re.search(padrao, normalizar_titulo(titulo)):
            return tipo
    return "condicao"


def segmentos(texto: str) -> list[str] | None:
    achado = re.search(r"Exclusivamente para (?:a|as) atividades? (?:de )?(.*?)(?:,? além|$)", texto, re.I)
    if not achado:
        return None
    atividade = normalizar_titulo(achado.group(1))
    encontrados = [seg for padrao, seg in SEGMENTO_DA_ATIVIDADE if re.search(padrao, atividade)]
    return sorted(set(encontrados)) or [SEM_SEGMENTO_DA_BASE]


class Extrator:
    def __init__(self):
        self.planos = planos_por_cobertura()
        self.todos_planos = sorted({p for ps in self.planos.values() for p in ps})
        self.chunks: list[dict] = []
        self.parte = "CG"
        self.cobertura = None  # chave da condição especial (catálogo ou slug do título)
        self.titulo_cobertura = None
        self.secao = ""
        self.item = None  # {"numero", "pagina", "linhas", "alineas": [[letra, pagina, linhas]]}
        self.capitulos: dict[str, str] = {}  # número do item → texto, para dar contexto aos filhos
        self.termo = None
        self.buffer_titulo: list[str] = []

    # ---- emissão ----
    def _base(self, id_, rotulo, texto, pagina, tipo, nucleo=None):
        if self.parte == "CE":
            if self.cobertura == RC_GERAL:
                planos = sorted({p for c in COBERTURAS_DE_RC for p in self.planos.get(c, [])})
            else:
                planos = self.planos.get(self.cobertura, [])
            cobertura = self.cobertura
        else:
            planos, cobertura = self.todos_planos, None
        return {
            "id": id_,
            "produto": PRODUTO,
            "parte": self.parte,
            "planos": planos,
            "cobertura": cobertura,
            "no_catalogo": self.parte != "CE" or self.cobertura in self.planos or self.cobertura == RC_GERAL,
            "secao": (self.titulo_cobertura + " · " if self.parte == "CE" else "") + self.secao,
            "tipo": tipo,
            "segmentos": segmentos(texto),
            "clausula": rotulo,
            "pagina": pagina,
            "texto": re.sub(r"\s+", " ", texto).strip(),
            # Só o conteúdo próprio (a alínea ou o item, sem o caput do pai): vai à frente na indexação.
            "nucleo": re.sub(r"\s+", " ", nucleo or texto).strip(),
        }

    def _prefixo(self):
        return "CG" if self.parte == "CG" else self.cobertura

    def fechar_item(self):
        if not self.item:
            return
        it, self.item = self.item, None
        caput = re.sub(r"\s+", " ", " ".join(it["linhas"])).strip()
        self.capitulos[it["numero"]] = caput
        pai = self.capitulos.get(it["numero"].rsplit(".", 1)[0]) if it["numero"].count(".") >= 2 else None
        if pai and len(pai) < 150:
            caput = f"{pai} — {caput}"
        tipo = tipo_da_secao(self.secao, self.parte)
        prefixo = self._prefixo()
        proprio = caput.rsplit(" — ", 1)[-1]
        if not eh_subtitulo(proprio) and (not it["alineas"] or not proprio.endswith(":")):
            self.chunks.append(
                self._base(
                    f"{prefixo}-{it['numero']}", f"{prefixo} {it['numero']}", caput, it["pagina"], tipo, proprio
                )
            )
        for letra, pagina, linhas in it["alineas"]:
            alinea = " ".join(linhas)
            texto = f"{caput} {letra}) {alinea}"
            self.chunks.append(
                self._base(
                    f"{prefixo}-{it['numero']}.{letra}",
                    f"{prefixo} {it['numero']} {letra}",
                    texto,
                    pagina,
                    tipo,
                    alinea,
                )
            )

    def fechar_termo(self):
        if not self.termo:
            return
        nome, pagina, linhas = self.termo
        self.termo = None
        if linhas:
            texto = f"{nome}: {' '.join(linhas)}"
            self.chunks.append(self._base(f"TT-{slug(nome)}", f"TT {nome}", texto, pagina, "definicao", texto))

    # ---- leitura ----
    def iniciar_condicoes_especiais(self):
        self.fechar_termo()
        self.parte = "CE"

    def processar(self, pagina: int, linha: str):
        titulo = normalizar_titulo(linha)
        if titulo == "CONSULTA AOS TERMOS TECNICOS":
            self.fechar_item()
            self.parte, self.secao = "TT", "Termos técnicos"
            return
        if self.parte == "TT":
            return self._termo(pagina, linha)
        if self.parte == "CE" and not RE_ITEM.match(linha) and not RE_ALINEA.match(linha):
            if RE_SECAO.match(linha) and RE_SECAO.match(linha).group(1) == "1" and self.buffer_titulo:
                self._abrir_cobertura()
            elif RE_TERMO.match(linha) and not RE_SECAO.match(linha):
                self.buffer_titulo.append(linha)
                return
            else:
                self.buffer_titulo = []
        secao = RE_SECAO.match(linha)
        if secao:
            self.fechar_item()
            self.secao = f"{secao.group(1)}. {secao.group(2).strip()}"
            return
        item = RE_ITEM.match(linha)
        if item:
            self.fechar_item()
            self.item = {"numero": item.group(1), "pagina": pagina, "linhas": [item.group(2)], "alineas": []}
            return
        alinea = RE_ALINEA.match(linha)
        if alinea and self.item:
            self.item["alineas"].append([alinea.group(1), pagina, [alinea.group(2)]])
            return
        if self.item:
            destino = self.item["alineas"][-1][2] if self.item["alineas"] else self.item["linhas"]
            destino.append(linha)

    def _abrir_cobertura(self):
        self.fechar_item()
        self.capitulos = {}
        linhas = [l for l in self.buffer_titulo if normalizar_titulo(l) not in GRUPOS_CE]
        grupo = normalizar_titulo(self.buffer_titulo[-1])
        self.buffer_titulo = []
        if not linhas:  # o próprio grupo tem seção (disposições comuns de RC)
            self.titulo_cobertura, self.cobertura = grupo, RC_GERAL
            return
        self.titulo_cobertura = normalizar_titulo(" ".join(linhas))
        self.cobertura = next(
            (cob for titulo, cob in COBERTURA_DO_TITULO.items() if self.titulo_cobertura.startswith(titulo)),
            None,
        ) or slug(re.sub(r"^COBERTURAS? DE ", "", self.titulo_cobertura))

    def _termo(self, pagina, linha):
        # Um termo é uma linha toda em maiúsculas; a definição vem nas linhas seguintes.
        if RE_TERMO.match(linha) and linha == linha.upper() and len(linha) < 80:
            if self.termo and not self.termo[2]:
                self.termo[0] += " " + linha  # termo quebrado em duas linhas
                return
            self.fechar_termo()
            self.termo = [linha.strip(), pagina, []]
        elif self.termo:
            self.termo[2].append(linha)

    def finalizar(self):
        self.fechar_item()
        self.fechar_termo()
        return self.chunks


def extrair() -> list[dict]:
    extrator = Extrator()
    linhas = linhas_do_pdf()
    inicio_ce = indice_condicoes_especiais(linhas)
    for i, (pagina, linha) in enumerate(linhas):
        if i == inicio_ce:
            extrator.iniciar_condicoes_especiais()
        else:
            extrator.processar(pagina, linha)
    return extrator.finalizar()


def documentos_do_catalogo(planos: dict[str, list[str]]) -> list[dict]:
    """Um chunk por plano com as coberturas fixas do catálogo do desafio (fonte estruturada)."""
    por_plano = defaultdict(list)
    for cobertura, lista in planos.items():
        for plano in lista:
            por_plano[plano].append(cobertura)
    chunks = []
    for plano, coberturas in sorted(por_plano.items()):
        legiveis = ", ".join(c.replace("_", " ").lower() for c in coberturas)
        chunks.append(
            {
                "id": f"PLANO-{plano}",
                "produto": PRODUTO,
                "parte": "CATALOGO",
                "planos": [plano],
                "cobertura": None,
                "no_catalogo": True,
                "secao": "Catálogo de coberturas fixas dos planos",
                "tipo": "cobertura",
                "segmentos": None,
                "clausula": f"Plano {plano}",
                "pagina": None,
                "texto": f"O plano {plano} do Seguro Empresarial tem as coberturas fixas: {legiveis}.",
                "nucleo": f"O plano {plano} do Seguro Empresarial tem as coberturas fixas: {legiveis}.",
            }
        )
    return chunks


def main():
    cli = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    cli.add_argument("--amostra", type=int, default=0, help="mostra N chunks e não grava")
    args = cli.parse_args()
    chunks = extrair()
    chunks += documentos_do_catalogo(planos_por_cobertura())
    # O PDF tem numeração repetida (ex.: duas alíneas "a)" em 26.4.1); a repetição ganha sufixo.
    vistos = defaultdict(int)
    for c in chunks:
        vistos[c["id"]] += 1
        if vistos[c["id"]] > 1:
            print(f"aviso: numeração repetida no PDF em {c['id']} (pág. {c['pagina']}); gravado como -{vistos[c['id']]}")
            c["id"] += f"-{vistos[c['id']]}"
            c["clausula"] += f" ({vistos[c['id'].rsplit('-', 1)[0]]}ª ocorrência)"
    if len({c["id"] for c in chunks}) != len(chunks):
        sys.exit("ids repetidos após o sufixo")
    if args.amostra:
        passo = max(1, len(chunks) // args.amostra)
        for c in chunks[::passo][: args.amostra]:
            print(json.dumps(c, ensure_ascii=False, indent=1))
        return
    DESTINO.parent.mkdir(exist_ok=True)
    DESTINO.write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in chunks), encoding="utf-8")
    print(f"{len(chunks)} chunks gravados em {DESTINO.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
