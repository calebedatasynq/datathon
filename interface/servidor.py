"""Servidor da demo: a página em web/ e uma API que transmite as etapas do agente ao vivo (SSE).

Rodar: python app.py   (abre em http://127.0.0.1:8000)
"""

import json
import math
import queue
import threading
import warnings
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agente import config, log, rag
from agente.dados_base import get_estabelecimento
from agente.decisor import criar_decisor
from agente.perfil import get_perfil_cliente, listar_clientes
from agente.personalizacao import personalizar
from agente.pipeline import Conversa

warnings.filterwarnings("ignore")
WEB = config.RAIZ / "web"
PERSONAS = json.loads((config.RAIZ / "dados" / "fixtures" / "personas.json").read_text(encoding="utf-8"))

NOMES_COBERTURA = {
    "INCENDIO_RAIO_EXPLOSAO_FUMACA": "Incêndio, raio, explosão e fumaça",
    "DANOS_ELETRICOS": "Danos elétricos",
    "PERDA_PAGAMENTO_ALUGUEL": "Perda ou pagamento de aluguel",
    "RESPONSABILIDADE_CIVIL_ESTABELECIMENTO": "Responsabilidade civil do estabelecimento",
    "DESPESAS_FIXAS": "Despesas fixas",
    "ROUBO_FURTO_ARROMBAMENTO": "Roubo e furto com arrombamento",
    "VENDAVAL_EVENTOS_CORRELATOS": "Vendaval, granizo e similares",
    "RESPONSABILIDADE_CIVIL_EMPREGADOR": "Responsabilidade civil do empregador",
    "QUEBRA_DE_VIDROS": "Quebra de vidros",
    "DETERIORACAO_DE_MERCADORIAS_EM_AMBIENTES_FRIGORIFICADOS": "Mercadorias refrigeradas",
    "DELIVERY": "Delivery",
    "ROUBO_OU_FURTO_DE_VALORES_MEDIANTE_ARROMBAMENTO": "Roubo de valores em caixa",
}
NOME_PLANO = {"ESSENCIAL": "Essencial", "PRATICO": "Prático", "TOTAL": "Total"}
SEGMENTOS = {
    "BELEZA": "Salão de beleza",
    "CLINICA": "Clínica",
    "ELETRONICOS": "Loja de eletrônicos",
    "ESCOLA_CURSO": "Escola e cursos",
    "ESCRITORIO": "Escritório",
    "FARMACIA": "Farmácia",
    "MERCADO": "Mercado",
    "OFICINA": "Oficina",
    "RESTAURANTE": "Restaurante",
    "VAREJO_MODA": "Loja de moda",
}
SUGESTOES = [
    "Que seguro faz sentido para o meu negócio?",
    "E se arrombarem a loja, cobre?",
    "Cobre ataque hacker?",
    "A enchente alagou a loja, o seguro paga?",
    "Achei caro, já tenho seguro em outro banco.",
    "Quero falar com o meu gerente.",
]

app = FastAPI(title="Agente Empresarial · BB Seguros")
app.mount("/estatico", StaticFiles(directory=WEB), name="estatico")
conversas: dict[str, Conversa] = {}
travas: dict[str, threading.Lock] = {}
decisor = criar_decisor()


# ---------- formatação para a interface ----------


def _segmento(codigo: str) -> str:
    return SEGMENTOS.get(codigo, codigo.replace("_", " ").capitalize())


def _sugestao_para(pergunta: dict | None) -> str | None:
    """Uma resposta de exemplo à pergunta pendente, do lado que muda o plano."""
    if not pergunta:
        return None
    limiar = pergunta["limiar"]
    match pergunta["variavel"]:
        case "funcionarios_estimados_empresa":
            return f"Somos uns {math.ceil(limiar * 1.3)} funcionários."
        case "estoque_medio_estimado":
            return f"Tenho uns R$ {math.ceil(limiar * 1.3 / 1000)} mil em estoque."
        case _:
            return f"Os equipamentos valem uns R$ {math.ceil(limiar * 1.3 / 1000)} mil."


def _personalizado(p: dict | None) -> dict | None:
    if p is None:
        return None
    coberturas = [
        {
            "cobertura": c["cobertura"],
            "nome": NOMES_COBERTURA.get(c["cobertura"], c["cobertura"]),
            "origem": c["origem"],
            "minimo": c["faixa_valor_min"],
            "maximo": c["faixa_valor_max"],
            "confianca": c["confianca"],
            "justificativa": c["justificativa"],
            "confirmar": c.get("informacao_a_confirmar"),
            "clausulas": c["clausulas"],
        }
        for c in p["coberturas"]
    ]
    return {
        "plano_base": p["plano_base"],
        "elegivel": p["elegivel"],
        "motivo_elegibilidade": p.get("motivo_elegibilidade"),
        "confianca_geral": p["confianca_geral"],
        "relacao_imovel": p["relacao_imovel"],
        "coberturas": coberturas,
        "dados_a_conferir": p.get("dados_a_conferir", []),
    }


def _reais(v: float) -> str:
    if v >= 1e6:
        return f"R$ {v / 1e6:.1f} mi".replace(".", ",")
    return f"R$ {v / 1e3:.0f} mil" if v >= 1e3 else f"R$ {v:.0f}"


def _achado(perfil: dict, personalizado: dict) -> str:
    """O fato do caso que mais importa, dito antes de qualquer mensagem."""
    plano = perfil["plano"]
    if plano is None:
        return "O motor suspendeu a indicação: faltam dados essenciais no cadastro."
    pergunta = perfil["perguntas_pendentes"][0] if perfil["perguntas_pendentes"] else None
    adicionais = sum(c["origem"] == "adicional" for c in personalizado["coberturas"])
    extra = f" O plano personalizado acrescenta {adicionais} {'cobertura' if adicionais == 1 else 'coberturas'} ao {NOME_PLANO[plano]}." if adicionais else ""
    if pergunta is None:
        return f"Caso claro: nenhuma resposta do cliente muda o plano {NOME_PLANO[plano]}.{extra}"
    outro = pergunta["plano_se_sim"] if pergunta["plano_se_sim"] != plano else pergunta["plano_se_nao"]
    sobe = outro == pergunta["plano_se_sim"]
    estimado, limiar = pergunta["valor_estimado"], pergunta["limiar"]
    if pergunta["variavel"] == "funcionarios_estimados_empresa":
        distancia = f"{abs(limiar - estimado):.0f} {'funcionário' if abs(limiar - estimado) == 1 else 'funcionários'}"
        corte = f"{limiar:.0f} ou mais"
    else:
        distancia, corte = _reais(abs(limiar - estimado)), f"acima de {_reais(limiar)}"
    direcao = "sobe para" if sobe else "cai para"
    return (
        f"Está a {distancia} do corte: com {corte}, o plano {direcao} {NOME_PLANO[outro]}. "
        f"Uma pergunta resolve.{extra}"
    )


def resumo_cliente(perfil: dict, personalizado: dict) -> dict:
    pergunta = perfil["perguntas_pendentes"][0] if perfil["perguntas_pendentes"] else None
    est = get_estabelecimento(perfil["cliente_id"])
    e = perfil["entrada"]
    fatos = [
        {"rotulo": "Funcionários da empresa", "valor": f"{e['funcionarios_estimados_empresa']:.0f}" if e.get("funcionarios_estimados_empresa") is not None else "—"},
        {"rotulo": "Estoque médio", "valor": _reais(e["estoque_medio_estimado"]) if e.get("estoque_medio_estimado") is not None else "—"},
        {"rotulo": "Bens no endereço", "valor": _reais(e["valor_bens_ponderado_estabelecimento"]) if e.get("valor_bens_ponderado_estabelecimento") is not None else "—"},
        {"rotulo": "Aluguel por mês", "valor": _reais(est.valor_aluguel) if est.paga_aluguel else "Não paga"},
    ]
    return {
        "fatos": fatos,
        "achado": _achado(perfil, personalizado),
        "cliente_id": perfil["cliente_id"],
        "empresa_id": perfil["empresa_id"],
        "segmento": _segmento(perfil["segmento"]),
        "tipo_unidade": perfil["entrada"].get("tipo_unidade"),
        "plano": perfil["plano"],
        "score": perfil["score"],
        "pergunta_pendente": pergunta["texto"] if pergunta else None,
        "sugestoes": [s for s in [_sugestao_para(pergunta), *SUGESTOES] if s],
        "personalizado": _personalizado(personalizado),
    }


def resumo_turno(estado: dict, etapas: list[dict], turno: int, tempos: dict | None = None) -> dict:
    """O que a interface mostra de um turno; serve ao vivo e na reprodução (vem do log)."""
    d = estado["decisoes"]
    atualizado = estado.get("perfil_atualizado") or {}
    return {
        "turno": turno,
        "mensagem": estado["mensagem"],
        "resposta": estado["resposta"],
        "etapas": etapas,
        "segundos": (tempos or {}).get("total") or round(sum(e.get("segundos") or 0 for e in etapas), 2),
        "plano_anterior": atualizado.get("plano_anterior"),
        "plano": atualizado.get("plano"),
        "proxima_pergunta": (atualizado.get("proxima_pergunta") or {}).get("texto"),
        "decisoes": {k: v for k, v in d.items() if v},
        "guardrail": estado.get("guardrail"),
        "requer_humano": estado["requer_humano"],
        "motivo_humano": estado.get("motivo_humano"),
        "clausulas": {
            c["id"]: {"rotulo": c["clausula"], "secao": c["secao"], "pagina": c["pagina"], "texto": c["texto"]}
            for c in estado["clausulas"]
        },
        "personalizado": _personalizado(estado.get("plano_personalizado")),
    }


def _evento(tipo: str, dados: dict) -> str:
    return f"event: {tipo}\ndata: {json.dumps(dados, ensure_ascii=False)}\n\n"


# ---------- API ----------


@app.on_event("startup")
def aquecer():
    """Carrega o modelo de embeddings e o índice antes do primeiro turno (primeiro turno levava 19 s)."""
    threading.Thread(target=lambda: rag.buscar("incêndio na loja", k=1), daemon=True).start()


@app.get("/")
def pagina():
    return FileResponse(WEB / "index.html")


@app.get("/api/saude")
def saude():
    return {
        "decisor": "Jev (TypeSafe) com Claude Haiku de reserva" if config.chave_jev() else "Claude Haiku",
        "redator": config.MODELO_LLM,
        "busca": "híbrida" if rag.modo_efetivo() == "hibrido" else "BM25",
    }


@app.get("/api/clientes")
def clientes():
    personas = []
    for plano, p in PERSONAS.items():
        perfil = get_perfil_cliente(p["cliente_id"])
        personas.append(
            {
                "cliente_id": perfil.cliente_id,
                "segmento": _segmento(perfil.segmento),
                "plano": plano,
                "tipo": p["tipo"],
                "tem_pergunta": bool(perfil.perguntas_pendentes),
            }
        )
    return {"personas": personas, "todos": listar_clientes()}


class NovaConversa(BaseModel):
    cliente_id: str


@app.post("/api/conversas")
def nova_conversa(pedido: NovaConversa):
    try:
        conversa = Conversa(pedido.cliente_id, decisor=decisor)
    except KeyError as erro:
        raise HTTPException(404, str(erro)) from None
    conversas[conversa.sessao_id] = conversa
    travas[conversa.sessao_id] = threading.Lock()
    personalizado = personalizar(conversa.perfil, conversa.estabelecimento)
    return {
        "sessao_id": conversa.sessao_id,
        "cliente": resumo_cliente(conversa.perfil.model_dump(mode="json"), personalizado.model_dump(mode="json")),
    }


class Mensagem(BaseModel):
    texto: str


@app.post("/api/conversas/{sessao_id}/mensagens")
def enviar(sessao_id: str, pedido: Mensagem):
    conversa = conversas.get(sessao_id)
    if conversa is None:
        raise HTTPException(404, "Conversa não encontrada; abra uma nova")
    texto = pedido.texto.strip()
    if not texto:
        raise HTTPException(422, "Mensagem vazia")
    fila: queue.Queue = queue.Queue()

    def rodar():
        trava = travas[sessao_id]
        with trava:
            try:
                etapas: list[dict] = []

                def progresso(evento: dict):
                    fila.put(("etapa", evento))
                    if evento["estado"] != "rodando":
                        etapas.append(evento)

                estado = conversa.turno(texto, ao_progredir=progresso)
                registro = log.ler(conversa.arquivo_log, sessao_id)[-1]
                fila.put(
                    ("turno", resumo_turno(estado.model_dump(mode="json"), etapas, conversa.turnos, registro["tempos_s"]))
                )
            except Exception as erro:  # a interface mostra o erro no próprio turno
                fila.put(("erro", {"mensagem": f"O turno falhou: {erro.__class__.__name__}: {str(erro)[:200]}"}))
            finally:
                fila.put(None)

    threading.Thread(target=rodar, daemon=True).start()

    def transmitir():
        while (item := fila.get()) is not None:
            yield _evento(*item)

    return StreamingResponse(transmitir(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


@app.get("/api/gravacoes")
def gravacoes():
    """Conversas registradas no log, para o modo de reprodução (sem chamar API)."""
    sessoes: dict[str, dict] = {}
    for r in log.ler():
        s = sessoes.setdefault(
            r["sessao_id"], {"sessao_id": r["sessao_id"], "cliente_id": r["estado"]["cliente_id"], "turnos": 0}
        )
        s["turnos"] += 1
        s["momento"] = r["momento"]
        s["primeira_mensagem"] = s.get("primeira_mensagem") or r["estado"]["mensagem"]
    return sorted(sessoes.values(), key=lambda s: s["momento"], reverse=True)[:30]


@app.get("/api/gravacoes/{sessao_id}")
def gravacao(sessao_id: str):
    registros = log.ler(sessao_id=sessao_id)
    if not registros:
        raise HTTPException(404, "Gravação não encontrada")
    primeiro = registros[0]["estado"]
    personalizado = personalizar(
        get_perfil_cliente(primeiro["cliente_id"]), get_estabelecimento(primeiro["cliente_id"])
    ).model_dump(mode="json")
    return {
        "sessao_id": sessao_id,
        "cliente": resumo_cliente(primeiro["perfil"], personalizado),
        "turnos": [
            resumo_turno(r["estado"], r.get("etapas", []), r["turno"], r["tempos_s"]) for r in registros
        ],
    }
