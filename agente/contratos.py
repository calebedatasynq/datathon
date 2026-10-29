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
    confirmadas: list[str] = Field(default_factory=list)
    """Variáveis já confirmadas pelo cliente; não voltam a ser perguntadas."""
    entrada: dict
    """Entrada exata do motor; regras.py altera e chama score_empresa de novo."""


class CoberturaRecomendada(BaseModel):
    """Uma linha do template_coberturas_times.csv. Faixa em reais; regra determinística."""

    cobertura: str
    origem: str
    """"plano" (vem no pacote de contratação), "adicional" (necessária e fora do pacote) ou
    "opcional" (fora do pacote, baixa necessidade: o cliente pode incluir)."""
    necessidade: str = "RECOMENDADA"
    """ESSENCIAL, RECOMENDADA, OPCIONAL ou NAO_SE_APLICA, calculada das variáveis do cliente."""
    motivo_necessidade: str | None = None
    faixa_valor_min: float
    faixa_valor_max: float
    confianca: str
    """ALTA, MEDIA ou BAIXA."""
    dados_utilizados: str
    regra_calculo: str
    justificativa: str
    informacao_a_confirmar: str | None = None
    clausulas: list[str]
    """Cláusulas das Condições Gerais que sustentam a cobertura (citáveis)."""


class Local(BaseModel):
    """Onde fica o estabelecimento (CEP geocodificado ou coordenada aproximada da base)."""

    cep: str | None = None
    logradouro: str | None = None
    bairro: str | None = None
    municipio: str
    uf: str
    codigo_ibge: str | None = None
    latitude: float
    longitude: float
    precisao: str
    """"CEP" (ponto do CEP ou da rua) ou "MUNICIPIO" (só a cidade: perigos locais ficam no nível do município)."""
    fonte: str


class Perigo(BaseModel):
    """Um perigo natural no local, com o indicador público que sustenta o nível."""

    id: str
    """VENDAVAL, GRANIZO, RAIOS, ALAGAMENTO, DESLIZAMENTO ou BARRAGEM."""
    nome: str
    nivel: str
    """ALTO, MEDIO, BAIXO ou SEM_DADO."""
    indicador: str
    fonte: str
    coberto: bool
    """Se a apólice pode cobrir o dano (com a cobertura certa) ou se é excluída."""
    cobertura: str | None = None
    clausulas: list[str] = Field(default_factory=list)


class RiscoLocal(BaseModel):
    """Riscos naturais do local a partir de fontes públicas. Não é preço: o agravamento é indicativo
    para a subscrição e nunca é informado ao cliente como valor."""

    local: Local
    perigos: list[Perigo]
    agravamento: str
    """BAIXO, MEDIO ou ALTO: pressão de custo pelos perigos que o seguro cobre."""
    fator_agravamento: float
    """Indicativo interno (1,00 = sem agravamento); não é preço nem taxa."""
    analise_de_aceitacao: bool
    """Perigo alto que o seguro não cobre: a aceitação depende da análise do risco (cl. CG-13.3)."""
    fontes: list[str]
    falhas: list[str] = Field(default_factory=list)
    consultado_em: str

    def nivel(self, perigo: str) -> str:
        return next((p.nivel for p in self.perigos if p.id == perigo), "SEM_DADO")


class PlanoPersonalizado(BaseModel):
    """Plano base do motor + coberturas adicionais + faixa por cobertura. Uma linha do template_resultado."""

    imovel_id: str
    empresa_id: str
    plano_base: Plano | None
    """Pacote de contratação: o menor que cobre as essenciais, nunca abaixo do índice do motor."""
    plano_motor: Plano | None = None
    pacote_minimo: Plano | None = None
    elegivel: str
    """SIM, A_CONFIRMAR ou NAO quando há restrição explícita no cadastro."""
    motivo_elegibilidade: str | None = None
    tipo_localizacao: str
    relacao_imovel: str
    coberturas: list[CoberturaRecomendada]
    confianca_geral: str
    justificativa: str
    perguntas_confirmacao: list[str]
    dados_a_conferir: list[str] = Field(default_factory=list)
    """Inconsistências financeiras do cadastro (não usar esses números como certos)."""
    risco_local: RiscoLocal | None = None
    """Perigos naturais do local (CEP ou município), quando consultados."""
    alternativas: list[dict] = Field(default_factory=list)

    @property
    def adicionais(self) -> list[CoberturaRecomendada]:
        return [c for c in self.coberturas if c.origem == "adicional"]

    @property
    def opcionais(self) -> list[CoberturaRecomendada]:
        return [c for c in self.coberturas if c.origem == "opcional"]


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
    """Índice do motor de score antes e depois da confirmação."""
    pacote_anterior: Plano | None = None
    pacote: Plano | None = None
    """Pacote de contratação do plano personalizado antes e depois (o que o cliente vê)."""
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
    verificacoes: dict[str, float] = Field(default_factory=dict)
    """Probabilidades das checagens feitas pelo Decisor (última tentativa)."""


class EstadoTurno(BaseModel):
    """Estado de um turno; cada camada lê e escreve seus campos."""

    cliente_id: str
    mensagem: str
    perfil: Perfil | None = None
    decisoes: Decisoes = Field(default_factory=Decisoes)
    perfil_atualizado: PerfilAtualizado | None = None
    clausulas: list[ClausulaRecuperada] = Field(default_factory=list)
    plano_personalizado: PlanoPersonalizado | None = None
    resposta: str | None = None
    guardrail: ResultadoGuardrail | None = None
    requer_humano: bool = False
    motivo_humano: str | None = None
    opcoes: list[str] = Field(default_factory=list)
    """Respostas sugeridas para a próxima pergunta (botões na interface)."""
    descoberta: dict | None = None
    """Conversa do zero: o que o cliente respondeu, perguntas puladas e progresso."""
