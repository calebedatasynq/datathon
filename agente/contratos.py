"""Contratos pydantic entre as camadas. O estado do turno é o que liga tudo."""

from enum import StrEnum

from pydantic import BaseModel, Field


class NivelIPU(StrEnum):
    ALTO = "ALTO"
    FRONTEIRA = "FRONTEIRA"
    BAIXO = "BAIXO"


class TipoClausula(StrEnum):
    COBERTURA = "cobertura"
    EXCLUSAO = "exclusao"
    OBRIGACAO = "obrigacao"
    CARENCIA = "carencia"


class Faixa(BaseModel):
    """Faixa de valor em reais (ex.: estoque entre 40 e 150 mil)."""

    nome: str
    minimo: float | None = None
    maximo: float | None = None


class Pergunta(BaseModel):
    """Pergunta que ainda decide o plano, com as respostas possíveis."""

    id: str
    texto: str
    opcoes: list[str]


class Perfil(BaseModel):
    """Escrito por perfil.py."""

    cliente_id: str
    segmento: str
    plano_provavel: str
    ipu: NivelIPU
    ipu_valor: float | None = None
    faixas: list[Faixa] = Field(default_factory=list)
    confianca: float = Field(ge=0, le=1)
    perguntas_pendentes: list[Pergunta] = Field(default_factory=list)


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

    plano_anterior: str
    plano: str
    proxima_pergunta: Pergunta | None = None


class Clausula(BaseModel):
    """Um chunk das Condições Gerais. Escrito por rag.py."""

    id: str
    produto: str
    plano: str | None = None
    cobertura: str | None = None
    tipo: TipoClausula
    segmento: str | None = None
    clausula: str
    texto: str


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
    clausulas: list[Clausula] = Field(default_factory=list)
    resposta: str | None = None
    guardrail: ResultadoGuardrail | None = None
    requer_humano: bool = False
