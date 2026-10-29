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
from agente.personalizacao import perfil_relevante, personalizar
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


INTENCOES = {
    "responder_pergunta": "responde à pergunta",
    "perguntar_cobertura": "pergunta sobre cobertura",
    "objecao": "objeção",
    "quer_contratar": "quer contratar",
    "sem_interesse": "sem interesse",
    "outro": "outro assunto",
}


def _resumo_decisoes(d) -> str:
    partes = []
    if d.intencao:
        partes.append(f"intenção: {INTENCOES.get(d.intencao.valor, d.intencao.valor)} {d.intencao.probabilidade:.0%}")
    if d.confirmacao:
        partes.append(f"confirmação: {d.confirmacao.valor.replace('_', ' ')} {d.confirmacao.probabilidade:.0%}")
    if d.rota:
        partes.append(f"rota: {d.rota.valor} {d.rota.probabilidade:.0%}")
    return " · ".join(partes)


class Conversa:
    """Uma conversa com um cliente; guarda o perfil (com confirmações) e o histórico entre turnos."""

    def __init__(
        self,
        cliente_id: str,
        decisor: Decisor | None = None,
        redigir_fn: Callable[..., Redacao] = redigir,
        arquivo_log: Path | None = None,
        sessao_id: str | None = None,
        perfil: Perfil | None = None,
        estabelecimento=None,
    ):
        """perfil e estabelecimento prontos servem ao cliente sem cadastro (conversa do zero)."""
        self.cliente_id = cliente_id
        self.estabelecimento = estabelecimento or get_estabelecimento(cliente_id)
        self.perfil = perfil_relevante(perfil or get_perfil_cliente(cliente_id), self.estabelecimento)
        self.respostas_do_cliente: dict[str, str] = {}
        """Respostas da conversa do zero (rótulos das faixas), para o redator citar o que o cliente contou."""
        self.decisor = decisor or criar_decisor()
        self.redigir = redigir_fn
        self.arquivo_log = arquivo_log
        self.sessao_id = sessao_id or uuid.uuid4().hex[:8]
        self.historico: list[dict] = []
        self.turnos = 0

    def turno(
        self,
        mensagem: str,
        ao_progredir: Callable[[dict], None] | None = None,
        apresentar_recomendacao: bool = False,
    ) -> EstadoTurno:
        """Um turno. ao_progredir recebe cada etapa ao começar e ao terminar (para a interface ao vivo)."""
        tempos, tokens, extras = {}, {}, {}
        etapas: list[dict] = []
        relogio = time.perf_counter()

        def marcar(etapa: str):
            nonlocal relogio
            agora = time.perf_counter()
            tempos[etapa] = round(agora - relogio, 3)
            relogio = agora

        def avisar(id_: str, titulo: str, detalhe: str | None = None, estado_etapa: str = "rodando"):
            evento = {"id": id_, "estado": estado_etapa, "titulo": titulo, "detalhe": detalhe}
            if estado_etapa != "rodando":
                evento["segundos"] = tempos.get(id_)
                etapas.append(evento)
            if ao_progredir:
                ao_progredir(evento)

        perfil = self.perfil
        estado = EstadoTurno(cliente_id=self.cliente_id, mensagem=mensagem, perfil=perfil)
        avisar(
            "perfil",
            "Cadastro e índice do motor lidos",
            f"plano {perfil.plano} · score {perfil.score:.3f}".replace(".", ",")
            if perfil.plano
            else "cadastro incompleto: plano suspenso pelo motor",
            "feito",
        )

        # 1. decidir
        avisar("decidir", "Interpretando a mensagem com o Jev")
        decisoes, motivo = decidir_turno(perfil, mensagem, self.decisor)
        estado.decisoes = decisoes
        tokens["decisor"] = self.decisor.ultima_execucao.get("tokens")
        modelo_decisor = self.decisor.ultima_execucao.get("modelo")
        if self.decisor.ultima_execucao.get("falha_principal"):
            extras["falha_decisor_principal"] = self.decisor.ultima_execucao["falha_principal"]
        marcar("decidir")
        avisar("decidir", f"Mensagem interpretada ({modelo_decisor})", _resumo_decisoes(decisoes), "feito")
        objecao = None
        if decisoes.intencao and decisoes.intencao.valor == "objecao":
            avisar("objecao", "Identificando a objeção do cliente")
            objecao = identificar_objecao(mensagem, self.decisor)
            extras["objecao"] = objecao["id"] if objecao else None
            marcar("objecao")
            avisar(
                "objecao",
                "Objeção identificada" if objecao else "Objeção sem correspondência segura",
                objecao["objecao"] if objecao else "segue sem orientação curada",
                "feito",
            )

        # 2. regras (determinístico)
        avisar("regras", "Recalculando o plano no motor de score")
        confirmacao = decisoes.confirmacao if confirmacao_aplicavel(decisoes) else None
        respondida = perfil.perguntas_pendentes[0] if confirmacao else None
        atualizado, perfil_novo = aplicar_confirmacao(perfil, confirmacao)
        perfil_novo = perfil_relevante(perfil_novo, self.estabelecimento)
        personalizado = personalizar(perfil_novo, self.estabelecimento)
        pacote_antes = personalizar(perfil, self.estabelecimento).plano_base if confirmacao else personalizado.plano_base
        atualizado = atualizado.model_copy(
            update={
                "pacote_anterior": pacote_antes,
                "pacote": personalizado.plano_base,
                "proxima_pergunta": perfil_novo.perguntas_pendentes[0] if perfil_novo.perguntas_pendentes else None,
            }
        )
        estado.perfil_atualizado = atualizado
        estado.plano_personalizado = personalizado
        marcar("regras")
        if atualizado.pacote != atualizado.pacote_anterior:
            detalhe = f"pacote {atualizado.pacote_anterior} → {atualizado.pacote}, pela resposta a: {respondida.texto}"
        elif confirmacao:
            detalhe = f"pacote mantido: {atualizado.pacote}; necessidades recalculadas com a resposta"
        else:
            detalhe = f"pacote {atualizado.pacote}"
        detalhe += f" · {len(personalizado.adicionais)} adicionais · {len(personalizado.coberturas)} faixas"
        avisar("regras", "Plano personalizado montado", detalhe, "feito")

        # 3. recuperar
        avisar("recuperar", "Consultando as Condições Gerais")
        clausulas = rag.buscar_para_turno(mensagem, personalizado.plano_base, perfil.segmento)
        extras_ids = [c.clausulas[0] for c in personalizado.adicionais] + (objecao["clausulas"] if objecao else [])
        clausulas += _clausulas_extras(extras_ids, perfil_novo, {c.id for c in clausulas})
        estado.clausulas = clausulas
        marcar("recuperar")
        avisar(
            "recuperar",
            f"{len(clausulas)} cláusulas recuperadas (busca {'híbrida' if rag.modo_efetivo() == 'hibrido' else 'BM25'})",
            " · ".join(c.id for c in clausulas[:4]) + (" …" if len(clausulas) > 4 else ""),
            "feito",
        )

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
        if self.respostas_do_cliente:
            # Cliente sem cadastro: os números do perfil são faixas ou medianas do ramo, não fatos.
            entrada["respostas_do_cliente"] = self.respostas_do_cliente
            entrada["cliente"]["valores_estimados"] = {}
        if apresentar_recomendacao:
            entrada["apresentar_recomendacao"] = True
        avisar("redigir", "Redigindo a resposta com o Claude Haiku")
        redacao = self.redigir(entrada)
        tokens["redator"] = [redacao.tokens]
        marcar("redigir")
        avisar("redigir", "Resposta redigida", f"{len(redacao.citacoes)} citações · {redacao.modelo}", "feito")
        avisar("conferir", "Conferindo citações e promessas")
        guardrail = conferir(redacao.texto, clausulas, self.decisor, encaminhando, 1, redacao.cortada)
        tokens["guardrail"] = [self.decisor.ultima_execucao.get("tokens")] if guardrail.verificacoes else []
        marcar("conferir")
        avisar(
            "conferir",
            "Resposta aprovada pelo guardrail" if guardrail.aprovado else "Guardrail reprovou a resposta",
            None if guardrail.aprovado else guardrail.motivo,
            "feito" if guardrail.aprovado else "falhou",
        )
        if not guardrail.aprovado:
            extras["resposta_reprovada"] = redacao.texto
            extras["motivo_reprovacao"] = guardrail.motivo
            avisar("reescrever", "Reescrevendo a resposta")
            redacao = self.redigir(
                entrada,
                instrucao_extra=f"A resposta anterior foi reprovada: {guardrail.motivo}. Reescreva cumprindo as regras.",
            )
            tokens["redator"].append(redacao.tokens)
            marcar("reescrever")
            avisar("reescrever", "Resposta reescrita", None, "feito")
            avisar("conferir_2", "Conferindo de novo")
            guardrail = conferir(redacao.texto, clausulas, self.decisor, encaminhando, 2, redacao.cortada)
            if guardrail.verificacoes:
                tokens["guardrail"].append(self.decisor.ultima_execucao.get("tokens"))
            marcar("conferir_2")
            avisar(
                "conferir_2",
                "Reescrita aprovada" if guardrail.aprovado else "Reprovada de novo: vai para o gerente",
                None if guardrail.aprovado else guardrail.motivo,
                "feito" if guardrail.aprovado else "falhou",
            )
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
        avisar("registrar", "Turno registrado para auditoria", f"sessão {self.sessao_id} · turno {self.turnos}", "feito")
        extras["etapas"] = etapas
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
