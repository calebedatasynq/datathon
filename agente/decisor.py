"""Camada de decisão: perguntas tipadas sobre o turno, sempre com probabilidade.

Decisor é a interface; JevDecisor (TypeSafe System One) é o principal e ClaudeDecisor
(Haiku com tool use e enum) é o plano B, com a mesma interface. DecisorComReserva usa o
Jev e cai para o Claude se a chamada falhar. Nenhuma regra de plano é decidida aqui:
o decisor só transforma a mensagem em dado; regras.py aplica o dado.
"""

import json
import time
from abc import ABC, abstractmethod
from typing import Literal

import requests
from pydantic import BaseModel

from agente import config
from agente.contratos import Confirmacao, Decisao, Decisoes, Perfil, Pergunta

URL_JEV = "https://api.typesafe.ai/v1/systemone"
MODELO_JEV = "jev-latest"


class Escolha(BaseModel):
    tipo: Literal["escolha"] = "escolha"
    instrucao: str
    opcoes: dict[str, str | None]
    """Nome da opção → descrição (enviada ao modelo para separar opções parecidas)."""


class Nota(BaseModel):
    tipo: Literal["nota"] = "nota"
    instrucao: str
    niveis: list[str]
    """Do mais baixo ao mais alto."""


class Afirmacao(BaseModel):
    tipo: Literal["afirmacao"] = "afirmacao"
    instrucao: str


Questao = Escolha | Nota | Afirmacao


class Resposta(BaseModel):
    """Resposta a uma questão. Para Afirmacao, valor é "sim"/"nao" e p_verdadeiro é a probabilidade crua."""

    valor: str
    probabilidade: float
    p_verdadeiro: float | None = None

    def decisao(self) -> Decisao:
        return Decisao(valor=self.valor, probabilidade=self.probabilidade)


class Decisor(ABC):
    nome: str
    ultima_execucao: dict = {}
    """Modelo, tempo e tokens da última chamada, para o log."""

    @abstractmethod
    def avaliar(self, contexto: dict, questoes: dict[str, Questao]) -> dict[str, Resposta]:
        """Avalia todas as questões contra o mesmo contexto, numa chamada só."""

    def escolher(self, contexto: dict, instrucao: str, opcoes: dict[str, str | None]) -> Resposta:
        return self.avaliar(contexto, {"q": Escolha(instrucao=instrucao, opcoes=opcoes)})["q"]

    def pontuar(self, contexto: dict, instrucao: str, rubrica: list[str]) -> Resposta:
        return self.avaliar(contexto, {"q": Nota(instrucao=instrucao, niveis=rubrica)})["q"]

    def probabilidade(self, contexto: dict, afirmacao: str) -> float:
        return self.avaliar(contexto, {"q": Afirmacao(instrucao=afirmacao)})["q"].p_verdadeiro


def _resposta_de_afirmacao(p: float) -> Resposta:
    return Resposta(valor="sim" if p >= 0.5 else "nao", probabilidade=max(p, 1 - p), p_verdadeiro=p)


class JevDecisor(Decisor):
    nome = "jev"

    def __init__(self, chave: str | None = None, modelo: str = MODELO_JEV, timeout: float = 20):
        self.chave = chave or config.chave_jev()
        self.modelo = modelo
        self.timeout = timeout

    @staticmethod
    def _questao(q: Questao) -> dict:
        match q:
            case Escolha():
                return {"type": "choice", "instructions": q.instrucao, "criteria": q.opcoes}
            case Nota():
                return {"type": "score", "instructions": q.instrucao, "criteria": q.niveis}
            case Afirmacao():
                return {"type": "noul", "instructions": q.instrucao}

    def avaliar(self, contexto, questoes):
        inicio = time.perf_counter()
        resposta = requests.post(
            URL_JEV,
            headers={"Authorization": f"Bearer {self.chave}"},
            json={
                "model": self.modelo,
                "state": json.dumps(contexto, ensure_ascii=False),
                "questions": {nome: self._questao(q) for nome, q in questoes.items()},
            },
            timeout=self.timeout,
        )
        resposta.raise_for_status()
        corpo = resposta.json()
        self.ultima_execucao = {
            "decisor": self.nome,
            "modelo": corpo.get("model"),
            "segundos": round(time.perf_counter() - inicio, 3),
            "tokens": corpo.get("usage"),
        }
        saida = {}
        for nome, q in questoes.items():
            r = corpo["answers"][nome]
            match q:
                case Escolha():
                    saida[nome] = Resposta(valor=r["choice"], probabilidade=r["probabilities"][r["choice"]])
                case Nota():
                    nivel, p = max(r["probabilities"].items(), key=lambda item: item[1])
                    saida[nome] = Resposta(valor=q.niveis[int(nivel)], probabilidade=p)
                case Afirmacao():
                    saida[nome] = _resposta_de_afirmacao(r["noul"])
        return saida


class ClaudeDecisor(Decisor):
    """Plano B: o Claude preenche uma ferramenta com enum e probabilidade por questão."""

    nome = "claude"
    SISTEMA = (
        "Você é a camada de decisão de um agente de vendas de seguro empresarial. "
        "Avalie o estado JSON e responda cada questão preenchendo a ferramenta. "
        "Para cada resposta, dê a probabilidade calibrada de ela estar certa: "
        "use valores baixos quando a mensagem for vaga ou ambígua."
    )

    def __init__(self, modelo: str | None = None):
        self.modelo = modelo or config.MODELO_DECISOR
        self._cliente = None

    @property
    def cliente(self):
        if self._cliente is None:
            self._cliente = config.cliente_anthropic()
        return self._cliente

    @staticmethod
    def _propriedade(q: Questao) -> dict:
        probabilidade = {"type": "number", "minimum": 0, "maximum": 1}
        match q:
            case Escolha():
                opcoes = "; ".join(f"{k}: {v}" if v else k for k, v in q.opcoes.items())
                return {
                    "type": "object",
                    "description": f"{q.instrucao} Opções — {opcoes}",
                    "properties": {
                        "valor": {"type": "string", "enum": list(q.opcoes)},
                        "probabilidade": probabilidade,
                    },
                    "required": ["valor", "probabilidade"],
                }
            case Nota():
                return {
                    "type": "object",
                    "description": f"{q.instrucao} Níveis do mais baixo ao mais alto.",
                    "properties": {"valor": {"type": "string", "enum": q.niveis}, "probabilidade": probabilidade},
                    "required": ["valor", "probabilidade"],
                }
            case Afirmacao():
                return {
                    "type": "object",
                    "description": f"Probabilidade de a afirmação ser verdadeira: {q.instrucao}",
                    "properties": {"probabilidade": probabilidade},
                    "required": ["probabilidade"],
                }

    def avaliar(self, contexto, questoes):
        inicio = time.perf_counter()
        ferramenta = {
            "name": "registrar_decisoes",
            "description": "Registra a resposta de cada questão sobre o estado.",
            "input_schema": {
                "type": "object",
                "properties": {nome: self._propriedade(q) for nome, q in questoes.items()},
                "required": list(questoes),
            },
        }
        resposta = self.cliente.messages.create(
            model=self.modelo,
            max_tokens=1024,
            system=self.SISTEMA,
            tools=[ferramenta],
            tool_choice={"type": "tool", "name": "registrar_decisoes"},
            messages=[{"role": "user", "content": json.dumps(contexto, ensure_ascii=False)}],
        )
        entrada = next(b for b in resposta.content if b.type == "tool_use").input
        self.ultima_execucao = {
            "decisor": self.nome,
            "modelo": resposta.model,
            "segundos": round(time.perf_counter() - inicio, 3),
            "tokens": {"input_tokens": resposta.usage.input_tokens, "output_tokens": resposta.usage.output_tokens},
        }
        saida = {}
        for nome, q in questoes.items():
            r = entrada[nome]
            if isinstance(q, Afirmacao):
                saida[nome] = _resposta_de_afirmacao(float(r["probabilidade"]))
            else:
                saida[nome] = Resposta(valor=r["valor"], probabilidade=float(r["probabilidade"]))
        return saida


class DecisorComReserva(Decisor):
    """Usa o principal; se a chamada falhar (rede, chave, formato), usa a reserva."""

    def __init__(self, principal: Decisor, reserva: Decisor):
        self.principal, self.reserva = principal, reserva
        self.nome = principal.nome

    def avaliar(self, contexto, questoes):
        try:
            saida = self.principal.avaliar(contexto, questoes)
            self.ultima_execucao = self.principal.ultima_execucao
        except Exception as erro:
            saida = self.reserva.avaliar(contexto, questoes)
            self.ultima_execucao = {**self.reserva.ultima_execucao, "falha_principal": repr(erro)[:200]}
        return saida


def criar_decisor() -> Decisor:
    """Jev com o Claude de reserva quando há JEV_API_KEY; senão só o Claude."""
    if config.chave_jev():
        return DecisorComReserva(JevDecisor(), ClaudeDecisor())
    return ClaudeDecisor()


# ---------- perguntas tipadas do turno ----------

INTENCAO = Escolha(
    instrucao="Qual é a intenção de `mensagem_do_cliente`?",
    opcoes={
        "responder_pergunta": "responde à `pergunta_pendente` com um dado, um número ou dizendo que não sabe",
        "perguntar_cobertura": "pergunta o que o seguro cobre ou não cobre, ou como ele funciona",
        "objecao": "resiste a contratar: preço, já tem seguro, acha que não precisa, desconfia",
        "quer_contratar": "diz que quer contratar ou fechar o seguro",
        "sem_interesse": "recusa ou encerra a conversa",
        "outro": "saudação ou qualquer outro assunto",
    },
)

CONFIRMACAO = Escolha(
    instrucao=(
        "`mensagem_do_cliente` responde à `pergunta_pendente`? Compare o valor que o cliente informa "
        "com `pergunta_pendente.limite`."
    ),
    opcoes={
        "sim": "o valor informado é igual ou maior que o limite",
        "nao": "o valor informado é menor que o limite",
        "nao_sabe": "o cliente diz que não sabe, ou dá um valor vago ou uma faixa com valores dos dois lados do limite",
        "nao_respondeu": "a mensagem fala de outra coisa e não responde à pergunta",
    },
)

PRONTIDAO = Nota(
    instrucao="Quão pronto para contratar o cliente parece em `mensagem_do_cliente`?",
    niveis=["sem interesse", "curioso, só pesquisando", "avaliando, com dúvidas", "pronto para contratar"],
)

ROTA = Escolha(
    instrucao="A conversa pode seguir com o agente automático ou precisa de um gerente humano?",
    opcoes={
        "agente": "dúvida comum sobre o seguro, resposta a uma pergunta ou objeção comum",
        "gerente": (
            "pede para falar com uma pessoa, reclama, relata um sinistro em andamento "
            "ou pede algo que exige análise humana"
        ),
    },
)

UNIDADE = {
    "funcionarios_estimados_empresa": "funcionários",
    "estoque_medio_estimado": "reais",
    "valor_bens_ponderado_estabelecimento": "reais",
}


def contexto_do_turno(perfil: Perfil | None, mensagem: str, pergunta: Pergunta | None) -> dict:
    """Estado enviado ao decisor: só o necessário, sem dado pessoal do cliente."""
    contexto = {"mensagem_do_cliente": mensagem}
    if perfil is not None:
        contexto["cliente"] = {"segmento": perfil.segmento, "plano_recomendado": perfil.plano}
    if pergunta is not None:
        contexto["pergunta_pendente"] = {
            "texto": pergunta.texto,
            "limite": pergunta.limiar,
            "unidade": UNIDADE[pergunta.variavel],
        }
    return contexto


def decidir_turno(
    perfil: Perfil | None, mensagem: str, decisor: Decisor, pergunta: Pergunta | None = None
) -> tuple[Decisoes, str | None]:
    """Decisões do turno e, se o caso deve ir para o gerente, o motivo."""
    if pergunta is None and perfil is not None and perfil.perguntas_pendentes:
        pergunta = perfil.perguntas_pendentes[0]
    questoes: dict[str, Questao] = {"intencao": INTENCAO, "prontidao": PRONTIDAO, "rota": ROTA}
    if pergunta is not None:
        questoes["confirmacao"] = CONFIRMACAO
    respostas = decisor.avaliar(contexto_do_turno(perfil, mensagem, pergunta), questoes)
    decisoes = Decisoes(
        intencao=respostas["intencao"].decisao(),
        prontidao=respostas["prontidao"].decisao(),
        rota=respostas["rota"].decisao(),
    )
    if pergunta is not None:
        r = respostas["confirmacao"]
        decisoes.confirmacao = Confirmacao(pergunta_id=pergunta.id, valor=r.valor, probabilidade=r.probabilidade)
    return decisoes, motivo_para_humano(decisoes)


def motivo_para_humano(decisoes: Decisoes) -> str | None:
    """Regra fixa (não LLM) de quando o caso vai para o gerente."""
    if decisoes.rota and decisoes.rota.valor == "gerente":
        return f"rota: gerente ({decisoes.rota.probabilidade:.0%})"
    c = decisoes.confirmacao
    if c is not None:
        if c.valor == "nao_sabe":
            return f"cliente não soube responder ({c.probabilidade:.0%})"
        if c.valor in ("sim", "nao") and c.probabilidade < config.LIMIAR_CONFIANCA:
            return f"confirmação '{c.valor}' com confiança baixa ({c.probabilidade:.0%})"
    return None


def confirmacao_aplicavel(decisoes: Decisoes) -> bool:
    """Só sim/não acima do limiar viram dado para regras.py."""
    c = decisoes.confirmacao
    return c is not None and c.valor in ("sim", "nao") and c.probabilidade >= config.LIMIAR_CONFIANCA
