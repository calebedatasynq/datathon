"""Contratos pydantic entre as camadas. O estado do turno é o que liga tudo."""

from enum import StrEnum

from pydantic import BaseModel, Field


class Plano(StrEnum):
    ESSENCIAL = "ESSENCIAL"
    PRATICO = "PRATICO"
    TOTAL = "TOTAL"


class TipoClausula(StrEnum):
    COBERTURA = "cobertura"
    EXCLUSAO = "exclusao"
    OBRIGACAO = "obrigacao"
    CARENCIA = "carencia"
    FRANQUIA = "franquia"
    CONDICAO = "condicao"
    DEFINICAO = "definicao"


class Pergunta(BaseModel):
    """Pergunta que ainda decide o plano: "variavel passa de limiar?"."""

    id: str
    texto: str
    opcoes: list[str] = Field(default_factory=lambda: ["sim", "nao", "nao_sei"])
    variavel: str
    valor_estimado: float
    limiar: float
    plano_se_sim: Plano
    plano_se_nao: Plano


class Perfil(BaseModel):
    """Escrito por perfil.py a partir de score_empresa, sem LLM."""

    cliente_id: str
    empresa_id: str
    segmento: str
    status: str
    plano: Plano | None
    score: float | None
    cortes: list[float]
    probabilidades: dict[Plano, float] | None = None
    distancia_ao_corte: float | None = None
    avisos: list[str] = Field(default_factory=list)
    perguntas_pendentes: list[Pergunta] = Field(default_factory=list)
    entrada: dict
    """Entrada exata do motor; regras.py altera e chama score_empresa de novo."""


class Decisao(BaseModel):
    """Uma resposta tipada do Decisor, sempre com probabilidade."""

    valor: str
    probabilidade: float = Field(ge=0, le=1)


class Confirmacao(Decisao):
    pergunta_id: str


class Decisoes(BaseModel):
    """Escrito por decisor.py."""

    intencao: Decisao | None = None
    confirmacao: Confirmacao | None = None
    prontidao: Decisao | None = None
    rota: Decisao | None = None


class PerfilAtualizado(BaseModel):
    """Escrito por regras.py. Plano recalculado por regra, nunca por LLM."""

    plano_anterior: Plano | None
    plano: Plano | None
    proxima_pergunta: Pergunta | None = None


class Clausula(BaseModel):
    """Um chunk das Condições Gerais (conhecimento/clausulas.jsonl). O id é o que se cita."""

    id: str
    produto: str
    parte: str
    """CG (condições gerais), TT (termos técnicos), CE (condições especiais) ou CATALOGO."""
    planos: list[Plano]
    """Planos que incluem esta cláusula, segundo o catálogo do desafio."""
    cobertura: str | None = None
    no_catalogo: bool
    """False para coberturas adicionais que não estão em nenhum dos três planos."""
    secao: str
    tipo: TipoClausula
    segmentos: list[str] | None = None
    """None vale para todos; senão só para esses grupos de atividade."""
    clausula: str
    pagina: int | None = None
    texto: str
    nucleo: str
    """Conteúdo próprio do chunk (a alínea, sem o caput); usado à frente na indexação."""


class ClausulaRecuperada(Clausula):
    """Escrito por rag.py."""

    pontuacao: float
    no_plano: bool | None = None
    """Se a cláusula vale para o plano do cliente; None quando a busca não recebeu plano."""


class ResultadoGuardrail(BaseModel):
    """Escrito por guardrail.py."""

    aprovado: bool
    motivo: str | None = None
    tentativas: int = 1


class EstadoTurno(BaseModel):
    """Estado de um turno; cada camada lê e escreve seus campos."""

    cliente_id: str
    mensagem: str
    perfil: Perfil | None = None
    decisoes: Decisoes = Field(default_factory=Decisoes)
    perfil_atualizado: PerfilAtualizado | None = None
    clausulas: list[ClausulaRecuperada] = Field(default_factory=list)
    resposta: str | None = None
    guardrail: ResultadoGuardrail | None = None
    requer_humano: bool = False
