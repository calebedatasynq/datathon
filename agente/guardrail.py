"""Confere a resposta antes de ela sair.

1. Determinística: toda cláusula citada está entre as recuperadas no turno, e uma resposta
   que não encaminha ao gerente cita ao menos uma cláusula.
2. Pelo Decisor: promete cobertura sem cláusula? informa preço ou valor de franquia?
   menciona dado sensível ou processo judicial?
A reescrita e o encaminhamento ficam no pipeline.
"""

from agente import config
from agente.contratos import ClausulaRecuperada, ResultadoGuardrail
from agente.decisor import Afirmacao, Decisor
from agente.redator import citacoes

CHECAGENS = {
    "promete_sem_clausula": Afirmacao(
        instrucao=(
            "`resposta` afirma que o seguro cobre algo que não está sustentado pelo texto de "
            "`clausulas_citadas`, ou diz que cobre algo que essas cláusulas excluem?"
        )
    ),
    "informa_preco": Afirmacao(
        instrucao=(
            "`resposta` informa quanto o cliente vai pagar pelo seguro (preço, prêmio, parcela) ou o valor da "
            "franquia? Limite de indenização ou faixa sugerida de cobertura não é preço."
        )
    ),
    "dado_sensivel": Afirmacao(
        instrucao=(
            "`resposta` menciona dado pessoal sensível do cliente (saúde, religião, etnia, orientação "
            "sexual, opinião política), processo judicial ou dívida do cliente?"
        )
    ),
}
MOTIVOS = {
    "promete_sem_clausula": "a resposta promete cobertura que as cláusulas citadas não sustentam",
    "informa_preco": "a resposta informa preço ou valor de franquia, que o agente não pode informar",
    "dado_sensivel": "a resposta menciona dado sensível ou processo judicial",
}


def conferir_citacoes(
    texto: str, clausulas: list[ClausulaRecuperada], encaminhando: bool, cortada: bool = False
) -> str | None:
    """Motivo da reprovação determinística, ou None."""
    if cortada or texto.count("[") != texto.count("]"):
        return "a resposta está incompleta (geração cortada)"
    citadas = citacoes(texto)
    recuperadas = {c.id for c in clausulas}
    inexistentes = [c for c in citadas if c not in recuperadas]
    if inexistentes:
        return f"cita cláusulas que não foram recuperadas: {', '.join(inexistentes)}"
    if not citadas and not encaminhando:
        return "não cita nenhuma cláusula"
    return None


def conferir(
    texto: str,
    clausulas: list[ClausulaRecuperada],
    decisor: Decisor,
    encaminhando: bool = False,
    tentativa: int = 1,
    cortada: bool = False,
) -> ResultadoGuardrail:
    motivo = conferir_citacoes(texto, clausulas, encaminhando, cortada)
    if motivo:
        return ResultadoGuardrail(aprovado=False, motivo=motivo, tentativas=tentativa)
    por_id = {c.id: c for c in clausulas}
    contexto = {
        "resposta": texto,
        "clausulas_citadas": [{"id": i, "texto": por_id[i].texto} for i in dict.fromkeys(citacoes(texto))],
    }
    respostas = decisor.avaliar(contexto, CHECAGENS)
    verificacoes = {nome: r.p_verdadeiro for nome, r in respostas.items()}
    falhas = [MOTIVOS[n] for n, p in verificacoes.items() if p >= config.LIMIAR_CONFIANCA]
    return ResultadoGuardrail(
        aprovado=not falhas,
        motivo="; ".join(falhas) or None,
        tentativas=tentativa,
        verificacoes=verificacoes,
    )
