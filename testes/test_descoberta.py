"""Conversa do zero: o agente pergunta só o que muda o plano e depois recomenda (sem API)."""

import pytest

from agente import log
from agente.decisor import Decisor, Resposta as RespostaDecisor
from agente.descoberta import (
    MAX_PERGUNTAS,
    PERGUNTAS,
    POR_ID,
    ConversaDescoberta,
    Resposta,
    cliente_virtual,
    estabelecimento_virtual,
    proxima_pergunta,
)
from agente.dados_base import perfil_segmento
from agente.redator import Redacao, citacoes


class DecisorFixo(Decisor):
    """Escolhe sempre a primeira opção com 99% e nega as checagens do guardrail."""

    nome = "fixo"

    def avaliar(self, contexto, questoes):
        self.ultima_execucao = {"decisor": self.nome, "modelo": "fixo", "segundos": 0, "tokens": None}
        saida = {}
        for nome, q in questoes.items():
            if q.tipo == "afirmacao":
                saida[nome] = RespostaDecisor(valor="nao", probabilidade=0.99, p_verdadeiro=0.01)
            elif nome == "rota":
                saida[nome] = RespostaDecisor(valor="agente", probabilidade=0.99)
            else:
                valor = q.niveis[0] if q.tipo == "nota" else next(iter(q.opcoes))
                saida[nome] = RespostaDecisor(valor=valor, probabilidade=0.99)
        return saida


class RedatorEspiao:
    """Responde citando o resumo do plano e guarda o que recebeu."""

    def __init__(self):
        self.entradas = []

    def __call__(self, entrada, instrucao_extra=None):
        self.entradas.append(entrada)
        texto = f"Seu plano sob medida [cl. PLANO-{entrada['plano_recomendado']}]."
        return Redacao(texto=texto, citacoes=citacoes(texto), modelo="falso", segundos=0, tokens={})


def _responder(pergunta_id: str, indice: int) -> Resposta:
    o = POR_ID[pergunta_id].opcoes[indice]
    return Resposta(pergunta=pergunta_id, rotulo=o.rotulo, valor=o.valor, origem="cliente")


@pytest.fixture
def arquivo_log(tmp_path):
    return tmp_path / "turnos.jsonl"


def test_toda_pergunta_tem_ao_menos_duas_opcoes():
    assert all(len(p.opcoes) >= 2 for p in PERGUNTAS)


def test_primeira_pergunta_depois_do_ramo_e_sobre_a_equipe():
    pergunta, _ = proxima_pergunta("NOVO_t", "RESTAURANTE", {}, set())
    assert pergunta.id == "funcionarios"


def test_pergunta_que_nao_muda_o_plano_e_pulada_com_motivo():
    puladas_total = set()
    respostas = {}
    while True:
        pergunta, puladas = proxima_pergunta("NOVO_t", "ESCRITORIO", respostas, puladas_total)
        puladas_total |= {p for p, _ in puladas}
        assert all("não muda" in motivo for _, motivo in puladas)
        if pergunta is None:
            break
        respostas[pergunta.id] = _responder(pergunta.id, 0)
    assert puladas_total  # algo foi pulado: nem toda pergunta muda o plano
    assert len(respostas) <= MAX_PERGUNTAS


def test_pergunta_fora_do_ramo_nao_e_feita():
    respostas, puladas = {}, set()
    feitas = []
    while (p := proxima_pergunta("NOVO_t", "ESCRITORIO", respostas, puladas)[0]) is not None:
        feitas.append(p.id)
        respostas[p.id] = _responder(p.id, 0)
    assert "refrigeracao" not in feitas and "delivery" not in feitas


def test_cliente_virtual_usa_as_respostas_e_a_mediana_do_ramo():
    respostas = {"funcionarios": _responder("funcionarios", 2), "estoque": _responder("estoque", 3)}
    perfil, est, plano = cliente_virtual("NOVO_t", "FARMACIA", respostas)
    assert perfil.entrada["funcionarios_estimados_empresa"] == POR_ID["funcionarios"].opcoes[2].valor
    assert perfil.entrada["estoque_medio_estimado"] == POR_ID["estoque"].opcoes[3].valor
    ref = perfil_segmento("FARMACIA")
    assert est.faturamento_mensal_empresa == ref.faturamento  # não perguntado: mediana do ramo
    assert perfil.perguntas_pendentes == []  # o motor não volta a perguntar o que o cliente disse
    # Nenhum motivo mostra número além das faixas que o próprio cliente escolheu.
    def sem_faixas(texto):
        for r in respostas.values():
            texto = texto.replace(r.rotulo.lower(), "")
        return texto.replace("CG-3.1", "")

    assert not [c for c in plano.coberturas if any(ch.isdigit() for ch in sem_faixas(c.motivo_necessidade))]
    assert plano.relacao_imovel == "A_CONFIRMAR"


def test_imovel_proprio_zera_o_aluguel():
    est = estabelecimento_virtual("NOVO_t", "MERCADO", {"imovel": _responder("imovel", 1)})
    assert not est.paga_aluguel and est.valor_aluguel == 0


def test_ramo_fora_da_base_monta_pelas_necessidades():
    perfil, _, plano = cliente_virtual("NOVO_t", "OUTRO", {"funcionarios": _responder("funcionarios", 0)})
    assert perfil.plano is None and plano.plano_base == plano.pacote_minimo


def test_conversa_do_zero_pelos_botoes_ate_a_recomendacao(arquivo_log):
    redator = RedatorEspiao()
    conversa = ConversaDescoberta(decisor=DecisorFixo(), redigir_fn=redator, arquivo_log=arquivo_log)
    assert "CNPJ" in conversa.abertura()["texto"]
    estado = conversa.turno("Prefiro não informar o CNPJ")
    assert "Restaurante ou bar" in estado.opcoes
    estado = conversa.turno("Restaurante ou bar")
    perguntas = 0
    while conversa.etapa != "recomendada":
        perguntas += 1
        assert estado.opcoes and estado.plano_personalizado is not None  # plano provisório a cada passo
        estado = conversa.turno(estado.opcoes[0])
        assert perguntas <= MAX_PERGUNTAS + 1
    assert estado.guardrail.aprovado and "PLANO-" in estado.resposta
    entrada = redator.entradas[-1]
    assert entrada["apresentar_recomendacao"] and entrada["respostas_do_cliente"]
    assert entrada["cliente"]["valores_estimados"] == {}  # faixas não viram números exatos
    assert estado.descoberta["etapa"] == "recomendada" and estado.descoberta["sabe"]
    registros = log.ler(arquivo_log, conversa.sessao_id)
    assert len(registros) == conversa.turnos and registros[0]["abertura"]
    # depois da recomendação, segue como conversa normal
    seguinte = conversa.turno("e se arrombarem a loja?")
    assert seguinte.guardrail.aprovado and conversa.conversa is not None


def test_resposta_que_nao_encaixa_repete_a_pergunta(arquivo_log):
    class DecisorNaoResponde(DecisorFixo):
        def avaliar(self, contexto, questoes):
            saida = super().avaliar(contexto, questoes)
            if "pergunta" in contexto:
                return {n: RespostaDecisor(valor="nao_respondeu", probabilidade=0.95) for n in questoes}
            return saida

    conversa = ConversaDescoberta(decisor=DecisorNaoResponde(), redigir_fn=RedatorEspiao(), arquivo_log=arquivo_log)
    conversa.turno("Prefiro não informar o CNPJ")
    conversa.turno("Farmácia")
    antes = conversa.turno("Prefiro não informar o CEP")
    depois = conversa.turno("hoje está chovendo")
    assert depois.opcoes == antes.opcoes and "Não consegui encaixar" in depois.resposta


def test_saudacao_nao_e_recusa_do_cnpj(arquivo_log):
    class DecisorSaudacao(DecisorFixo):
        def avaliar(self, contexto, questoes):
            saida = super().avaliar(contexto, questoes)
            if "q" in questoes and "saudacao" in getattr(questoes["q"], "opcoes", {}):
                return {"q": RespostaDecisor(valor="saudacao", probabilidade=0.97)}
            return saida

    conversa = ConversaDescoberta(decisor=DecisorSaudacao(), redigir_fn=RedatorEspiao(), arquivo_log=arquivo_log)
    estado = conversa.turno("ola")
    assert estado.resposta.startswith("Olá!") and "CNPJ" in estado.resposta
    assert estado.plano_personalizado is None and conversa.segmento is None
    estado = conversa.turno("Prefiro não informar o CNPJ")
    assert "Farmácia" in estado.opcoes  # segue para o ramo normalmente
