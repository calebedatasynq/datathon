"""Um turno ponta a ponta, sempre na mesma ordem: decidir, regras, recuperar, redigir, conferir, registrar.

O pipeline é fixo (o LLM não escolhe ferramentas), para a demo não travar ao vivo.
"""

import time
import uuid
from collections.abc import Callable
from pathlib import Path

from agente import config, log, rag
from agente.contratos import ClausulaRecuperada, EstadoTurno, Perfil
from agente.dados_base import get_estabelecimento
from agente.decisor import Decisor, confirmacao_aplicavel, criar_decisor, decidir_turno
from agente.guardrail import conferir
from agente.perfil import get_perfil_cliente
from agente.personalizacao import personalizar
from agente.redator import Redacao, montar_entrada, redigir
from agente.regras import aplicar_confirmacao

MENSAGEM_GERENTE = (
    "Para não te passar nenhuma informação imprecisa, vou chamar um gerente do Banco do Brasil "
    "para confirmar esse ponto e continuar o seu atendimento."
)
VERSAO_MOTOR = "ordinal_mock_v2"
HISTORICO_MAXIMO = 6


def identificar_objecao(mensagem: str, decisor: Decisor) -> dict | None:
    objecoes = rag.objecoes()
    opcoes = {id_: o["objecao"] for id_, o in objecoes.items()} | {"nenhuma": "nenhuma das objeções acima"}
    resposta = decisor.escolher(
        {"mensagem_do_cliente": mensagem}, "Qual objeção o cliente levanta em `mensagem_do_cliente`?", opcoes
    )
    if resposta.valor == "nenhuma" or resposta.probabilidade < config.LIMIAR_CONFIANCA:
        return None
    return objecoes[resposta.valor]


def _clausulas_extras(ids: list[str], perfil: Perfil, ja_tem: set[str]) -> list[ClausulaRecuperada]:
    """Cláusulas que o turno precisa poder citar além das recuperadas (objeção, adicionais)."""
    return [
        ClausulaRecuperada(
            **rag.por_id()[i].model_dump(), pontuacao=0.0, no_plano=perfil.plano in rag.por_id()[i].planos
        )
        for i in dict.fromkeys(ids)
        if i not in ja_tem
    ]


class Conversa:
    """Uma conversa com um cliente; guarda o perfil (com confirmações) e o histórico entre turnos."""

    def __init__(
        self,
        cliente_id: str,
        decisor: Decisor | None = None,
        redigir_fn: Callable[..., Redacao] = redigir,
        arquivo_log: Path | None = None,
        sessao_id: str | None = None,
    ):
        self.cliente_id = cliente_id
        self.perfil = get_perfil_cliente(cliente_id)
        self.estabelecimento = get_estabelecimento(cliente_id)
        self.decisor = decisor or criar_decisor()
        self.redigir = redigir_fn
        self.arquivo_log = arquivo_log
        self.sessao_id = sessao_id or uuid.uuid4().hex[:8]
        self.historico: list[dict] = []
        self.turnos = 0

    def turno(self, mensagem: str) -> EstadoTurno:
        tempos, tokens, extras = {}, {}, {}
        relogio = time.perf_counter()

        def marcar(etapa: str):
            nonlocal relogio
            agora = time.perf_counter()
            tempos[etapa] = round(agora - relogio, 3)
            relogio = agora

        perfil = self.perfil
        estado = EstadoTurno(cliente_id=self.cliente_id, mensagem=mensagem, perfil=perfil)

        # 1. decidir
        decisoes, motivo = decidir_turno(perfil, mensagem, self.decisor)
        estado.decisoes = decisoes
        tokens["decisor"] = self.decisor.ultima_execucao.get("tokens")
        modelo_decisor = self.decisor.ultima_execucao.get("modelo")
        if self.decisor.ultima_execucao.get("falha_principal"):
            extras["falha_decisor_principal"] = self.decisor.ultima_execucao["falha_principal"]
        objecao = None
        if decisoes.intencao and decisoes.intencao.valor == "objecao":
            objecao = identificar_objecao(mensagem, self.decisor)
            extras["objecao"] = objecao["id"] if objecao else None
        marcar("decidir")

        # 2. regras (determinístico)
        confirmacao = decisoes.confirmacao if confirmacao_aplicavel(decisoes) else None
        respondida = perfil.perguntas_pendentes[0] if confirmacao else None
        atualizado, perfil_novo = aplicar_confirmacao(perfil, confirmacao)
        estado.perfil_atualizado = atualizado
        personalizado = personalizar(perfil_novo, self.estabelecimento)
        estado.plano_personalizado = personalizado
        marcar("regras")

        # 3. recuperar
        clausulas = rag.buscar_para_turno(mensagem, atualizado.plano, perfil.segmento)
        extras_ids = [c.clausulas[0] for c in personalizado.adicionais] + (objecao["clausulas"] if objecao else [])
        clausulas += _clausulas_extras(extras_ids, perfil_novo, {c.id for c in clausulas})
        estado.clausulas = clausulas
        marcar("recuperar")

        # 4. redigir e 5. conferir: reprovou, reescreve uma vez; reprovou de novo, vai ao gerente
        encaminhando = motivo is not None
        entrada = montar_entrada(
            perfil_novo,
            mensagem,
            clausulas,
            atualizado,
            decisoes,
            encaminhando,
            objecao,
            self.historico[-HISTORICO_MAXIMO:],
            respondida,
            personalizado,
        )
        redacao = self.redigir(entrada)
        tokens["redator"] = [redacao.tokens]
        marcar("redigir")
        guardrail = conferir(redacao.texto, clausulas, self.decisor, encaminhando, 1, redacao.cortada)
        tokens["guardrail"] = [self.decisor.ultima_execucao.get("tokens")] if guardrail.verificacoes else []
        marcar("conferir")
        if not guardrail.aprovado:
            extras["resposta_reprovada"] = redacao.texto
            redacao = self.redigir(
                entrada,
                instrucao_extra=f"A resposta anterior foi reprovada: {guardrail.motivo}. Reescreva cumprindo as regras.",
            )
            tokens["redator"].append(redacao.tokens)
            marcar("reescrever")
            guardrail = conferir(redacao.texto, clausulas, self.decisor, encaminhando, 2, redacao.cortada)
            if guardrail.verificacoes:
                tokens["guardrail"].append(self.decisor.ultima_execucao.get("tokens"))
            marcar("conferir_2")
        resposta = redacao.texto
        if not guardrail.aprovado:
            extras["resposta_reprovada_2"] = redacao.texto
            resposta = MENSAGEM_GERENTE
            motivo = f"guardrail reprovou duas vezes: {guardrail.motivo}"
        estado.resposta = resposta
        estado.guardrail = guardrail
        estado.requer_humano = motivo is not None
        estado.motivo_humano = motivo

        # 6. registrar e avançar a conversa
        self.turnos += 1
        self.perfil = perfil_novo
        self.historico += [{"cliente": mensagem}, {"agente": resposta}]
        tempos["total"] = round(sum(tempos.values()), 3)
        log.registrar(
            estado,
            self.sessao_id,
            self.turnos,
            versoes={
                "motor_score": VERSAO_MOTOR,
                "decisor": modelo_decisor,
                "redator": redacao.modelo,
                "embeddings": config.MODELO_EMBEDDINGS,
                "busca": rag.modo_efetivo(),
                "limiar_confianca": config.LIMIAR_CONFIANCA,
            },
            tempos=tempos,
            tokens=tokens,
            extras=extras,
            arquivo=self.arquivo_log,
        )
        return estado
