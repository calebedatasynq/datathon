"""Camada B: recuperação de cláusulas das Condições Gerais.

Busca híbrida: BM25 (palavras) + vetorial (Chroma, como no RAG do BB Radar, com e5-small),
combinadas por Reciprocal Rank Fusion. Filtro por segmento é rígido; o plano só etiqueta
cada resultado (no_plano), para o redator poder dizer "isso não está no seu plano".
Fatos objetivos (qual plano tem qual cobertura) vêm do catálogo, não da busca: é a lição
registrada na documentação do RAG do BB Radar.
Sem o índice vetorial (ou com ele desatualizado), a busca cai para BM25 e avisa.
"""

import csv
import hashlib
import json
import re
import threading
import time
import unicodedata
import warnings
from collections import defaultdict
from functools import cache

from rank_bm25 import BM25Okapi

from agente import config
from agente.contratos import Clausula, ClausulaRecuperada, Plano

K_RRF = 60
CANDIDATOS = 50
# No máximo este número de cláusulas da mesma cobertura e tipo no resultado: sem isso,
# as alíneas de exclusão de uma cobertura tomam o top 5 e escondem o que ela cobre.
MAX_POR_GRUPO = 2

STOPWORDS = set(
    """a o e de da do das dos em no na nos nas um uma uns umas para por pelo pela pelos pelas com sem
    se que ou ao aos as os é ser foi são como mais menos já não sim meu minha meus minhas seu sua
    seus suas eu ele ela eles elas isso esse essa este esta aquele aquela tem ter tenho vocês você
    me te lhe nos qual quais quando onde quem muito pouco também até sobre entre""".split()
)


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def tokenizar(texto: str) -> list[str]:
    """Minúsculas, sem acento, sem stopwords; radical = sem plural, truncado em 6 letras."""
    tokens = []
    for palavra in re.findall(r"[a-z0-9]+", _sem_acento(texto.lower())):
        if palavra in STOPWORDS or len(palavra) < 2:
            continue
        if len(palavra) > 3 and palavra.endswith("s"):
            palavra = palavra[:-1]
        tokens.append(palavra[:6])
    return tokens


# Glossário curado: vocabulário do cliente → vocabulário das Condições Gerais.
# Só acrescenta termos à pergunta; nunca troca nem remove o que o cliente escreveu.
EXPANSOES = [
    (r"\bfogo\b|queimou tudo|incendi", "incêndio"),
    (r"\braio\b.*(queim|estrag)|(queim|estrag).*\braio\b|curto|pico de (luz|energia)|oscila", "danos elétricos variações de tensão"),
    (r"hacker|ransomware|v[ií]rus|ciber|invad\w* (o )?sistema|sistema travad", "ampla proteção cibernética ataques cibernéticos"),
    (r"\bpix\b|golpe|engan", "estelionato fraude"),
    (r"enchente|alag|inund|transbord", "alagamento inundação"),
    (r"funcion[aá]ri|empregad|colaborador", "empregados"),
    (r"machuc|acident|feriu|ferid", "acidentes danos corporais"),
    (r"cliente|visitante|terceir", "terceiros"),
    (r"escorreg|trope[cç]|caiu", "danos corporais terceiros estabelecimento"),
    (r"vitrine|janela|espelho|vidra[cç]", "vidros"),
    (r"sal[aá]rio|folha de pagamento|contas|despesas", "despesas fixas"),
    (r"assalt|roub|levaram|arromb", "roubo furto mediante arrombamento"),
    (r"sumiu|sumir|desapare|sem (sinal|vest[ií]gio)", "desaparecimento furto simples sem vestígio"),
    (r"avisar|comunicar|acionar", "aviso de sinistro"),
    (r"telhado|destelh|ventania", "vendaval"),
    (r"franquia|participa[cç][aã]o obrigat", "franquia dedutível participação obrigatória"),
]


def expandir(pergunta: str) -> str:
    extras = [termos for padrao, termos in EXPANSOES if re.search(padrao, pergunta, re.I)]
    return " ".join([pergunta, *extras])


def texto_indexado(c: Clausula) -> str:
    # O conteúdo próprio vem antes: o MiniLM lê só os primeiros ~128 tokens.
    cobertura = (c.cobertura or "").replace("_", " ").lower()
    contexto = c.texto if c.texto != c.nucleo else ""  # caput do item pai, quando há
    return f"{c.nucleo} | {cobertura} | {c.secao} | {contexto}"


@cache
def clausulas() -> list[Clausula]:
    """Cláusulas das Condições Gerais + fontes públicas curadas do produto."""
    resultado = []
    for arquivo in (config.CLAUSULAS, config.FONTES_PRODUTO):
        with open(arquivo, encoding="utf-8") as f:
            resultado += [Clausula.model_validate_json(linha) for linha in f if linha.strip()]
    return resultado


@cache
def por_id() -> dict[str, Clausula]:
    return {c.id: c for c in clausulas()}


def hash_clausulas() -> str:
    return hashlib.sha256(config.CLAUSULAS.read_bytes() + config.FONTES_PRODUTO.read_bytes()).hexdigest()


@cache
def _bm25() -> BM25Okapi:
    return BM25Okapi([tokenizar(texto_indexado(c)) for c in clausulas()])


# ---------- vetorial ----------


@cache
def _modelo():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(config.MODELO_EMBEDDINGS)


def embeddings(textos: list[str], tipo: str) -> list[list[float]]:
    """tipo é "query" (pergunta) ou "passage" (cláusula): o e5 exige o prefixo."""
    return _modelo().encode([f"{tipo}: {t}" for t in textos], normalize_embeddings=True).tolist()


_COLECAO = None
_FALHOU_EM: float | None = None
_TRAVA_COLECAO = threading.Lock()
NOVA_TENTATIVA_S = 30


def _colecao():
    """Coleção Chroma, ou None (com aviso) se não existe ou não bate com clausulas.jsonl.

    Só o sucesso fica guardado: a primeira abertura podia falhar por concorrência (aquecimento
    e primeira requisição ao mesmo tempo) e o servidor ficava em BM25 para sempre.
    """
    global _COLECAO, _FALHOU_EM
    if _COLECAO is not None:
        return _COLECAO
    if _FALHOU_EM is not None and time.monotonic() - _FALHOU_EM < NOVA_TENTATIVA_S:
        return None
    with _TRAVA_COLECAO:
        if _COLECAO is not None:
            return _COLECAO
        try:
            import chromadb

            cliente = chromadb.PersistentClient(path=str(config.DIR_BANCO_VETORIAL))
            colecao = cliente.get_collection(config.COLECAO_VETORIAL)
        except Exception as erro:  # pacote ausente, pasta ausente ou coleção ausente
            _FALHOU_EM = time.monotonic()
            warnings.warn(f"Busca vetorial indisponível ({erro}); usando só BM25. Rode scripts/indexar_rag.py")
            return None
        metadados = colecao.metadata or {}
        if metadados.get("hash_clausulas") != hash_clausulas() or metadados.get("modelo") != config.MODELO_EMBEDDINGS:
            _FALHOU_EM = time.monotonic()
            warnings.warn("Índice vetorial desatualizado; usando só BM25. Rode scripts/indexar_rag.py")
            return None
        _COLECAO = colecao
        return colecao


def modo_efetivo() -> str:
    if config.MODO_BUSCA == "bm25" or _colecao() is None:
        return "bm25"
    return "hibrido"


def _ranking_vetorial(pergunta: str) -> list[str]:
    resultado = _colecao().query(query_embeddings=embeddings([pergunta], "query"), n_results=CANDIDATOS)
    return resultado["ids"][0]


def _ranking_bm25(pergunta: str) -> list[str]:
    notas = _bm25().get_scores(tokenizar(pergunta))
    ordem = sorted(range(len(notas)), key=lambda i: notas[i], reverse=True)[:CANDIDATOS]
    return [clausulas()[i].id for i in ordem if notas[i] > 0]


# ---------- busca ----------


def _vale_para_segmento(c: Clausula, segmento: str | None) -> bool:
    return c.segmentos is None or (segmento is not None and segmento in c.segmentos)


def buscar(
    pergunta: str, plano: Plano | None = None, segmento: str | None = None, k: int = 5
) -> list[ClausulaRecuperada]:
    """As k cláusulas mais relevantes para a pergunta, válidas para o segmento do cliente."""
    pergunta = expandir(pergunta)
    rankings = [_ranking_bm25(pergunta)]
    if modo_efetivo() == "hibrido":
        rankings.append(_ranking_vetorial(pergunta))
    notas: dict[str, float] = defaultdict(float)
    for ranking in rankings:
        for posicao, id_ in enumerate(ranking):
            notas[id_] += 1 / (K_RRF + posicao + 1)
    resultado = []
    por_grupo: dict[tuple, int] = defaultdict(int)
    for id_, nota in sorted(notas.items(), key=lambda item: item[1], reverse=True):
        c = por_id()[id_]
        if not _vale_para_segmento(c, segmento):
            continue
        grupo = (c.parte, c.cobertura, c.tipo)
        if por_grupo[grupo] >= MAX_POR_GRUPO:
            continue
        por_grupo[grupo] += 1
        no_plano = None if plano is None else plano in c.planos
        resultado.append(ClausulaRecuperada(**c.model_dump(), pontuacao=nota, no_plano=no_plano))
        if len(resultado) == k:
            break
    return resultado


# Cláusula das CG v1.1 → fonte mais nova que a substitui. Quando as duas vêm no mesmo turno, a
# antiga sai: a exclusão de ataques cibernéticos (8.2 a) é anterior à Ampla Proteção Cibernética.
SUPERADAS = {"CG-8.2.a": "SITE-CIBERNETICA"}


def buscar_para_turno(mensagem: str, plano: Plano | None, segmento: str | None, k: int = 5) -> list[ClausulaRecuperada]:
    """Busca do turno + o resumo do plano recomendado (catálogo), para a resposta poder citá-lo."""
    resultado = buscar(mensagem, plano, segmento, k)
    ids = {c.id for c in resultado}
    resultado = [c for c in resultado if not (SUPERADAS.get(c.id) in ids)]
    if plano is not None and f"PLANO-{plano}" not in {c.id for c in resultado}:
        resumo = por_id()[f"PLANO-{plano}"]
        resultado.append(ClausulaRecuperada(**resumo.model_dump(), pontuacao=0.0, no_plano=True))
    if plano is not None and "SITE-CIBERNETICA" not in {c.id for c in resultado}:
        resultado.append(ClausulaRecuperada(**por_id()["SITE-CIBERNETICA"].model_dump(), pontuacao=0.0, no_plano=True))
    resultado = [c for c in resultado if not (SUPERADAS.get(c.id) in {r.id for r in resultado})]
    return resultado


@cache
def objecoes() -> dict[str, dict]:
    caminho = config.RAIZ / "conhecimento" / "objecoes.jsonl"
    with open(caminho, encoding="utf-8") as f:
        return {o["id"]: o for o in map(json.loads, f)}


# ---------- catálogo (consulta estruturada) ----------


@cache
def _catalogo() -> dict[str, list[Plano]]:
    planos = defaultdict(list)
    with open(config.CATALOGO, encoding="utf-8-sig", newline="") as f:
        for linha in csv.DictReader(f):
            planos[linha["cobertura_fixa"].strip()].append(Plano(linha["plano"].strip()))
    # Guia final, seção 10.2: complemento ao CSV original do desafio.
    planos["AMPLA_PROTECAO_CIBERNETICA"] = list(Plano)
    return dict(planos)


def coberturas_do_plano(plano: Plano) -> list[str]:
    return [cobertura for cobertura, planos in _catalogo().items() if plano in planos]


def planos_com_cobertura(cobertura: str) -> list[Plano]:
    return _catalogo().get(cobertura, [])


def exportar_amostra(ids: list[str]) -> str:
    return json.dumps([por_id()[i].model_dump() for i in ids], ensure_ascii=False, indent=1)
