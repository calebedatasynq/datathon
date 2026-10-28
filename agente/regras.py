"""Aplica a confirmação do cliente e recalcula o plano com a mesma regra do motor.

Determinístico, sem LLM: troca o valor confirmado na entrada do score_empresa e chama o
motor de novo. "Sim" leva a variável até o limiar (no mínimo); "não" a deixa logo abaixo
dele (no máximo). Um valor estimado que já está do lado certo é mantido.
"""

from agente.contratos import Confirmacao, Perfil, PerfilAtualizado, Pergunta
from agente.perfil import VARIAVEIS_INTEIRAS, perfil_de_entrada


def valor_confirmado(pergunta: Pergunta, resposta: str) -> float:
    estimado, limiar = pergunta.valor_estimado, pergunta.limiar
    if resposta == "sim":
        return max(estimado, limiar)
    abaixo = limiar - 1 if pergunta.variavel in VARIAVEIS_INTEIRAS else limiar * (1 - 1e-9)
    return min(estimado, abaixo)


def aplicar_confirmacao(perfil: Perfil, confirmacao: Confirmacao | None) -> tuple[PerfilAtualizado, Perfil]:
    """Plano antes e depois, e o perfil novo. Sem confirmação aplicável, o perfil não muda.

    Quem chama decide se a confirmação é aplicável (decisor.confirmacao_aplicavel).
    """
    pergunta = next((p for p in perfil.perguntas_pendentes if confirmacao and p.id == confirmacao.pergunta_id), None)
    if pergunta is None or confirmacao.valor not in ("sim", "nao"):
        atualizado = PerfilAtualizado(
            plano_anterior=perfil.plano,
            plano=perfil.plano,
            proxima_pergunta=perfil.perguntas_pendentes[0] if perfil.perguntas_pendentes else None,
        )
        return atualizado, perfil
    entrada = {**perfil.entrada, pergunta.variavel: valor_confirmado(pergunta, confirmacao.valor)}
    novo = perfil_de_entrada(entrada, tuple([*perfil.confirmadas, pergunta.variavel]))
    atualizado = PerfilAtualizado(
        plano_anterior=perfil.plano,
        plano=novo.plano,
        proxima_pergunta=novo.perguntas_pendentes[0] if novo.perguntas_pendentes else None,
    )
    return atualizado, novo
