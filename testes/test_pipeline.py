"""Fase 5: guardrail, log e pipeline. Pronto quando uma citação inexistente é barrada."""

import json

import pytest

from agente import config, log, rag
from agente.decisor import Decisor, Resposta, criar_decisor
from agente.guardrail import conferir, conferir_citacoes
from agente.pipeline import MENSAGEM_GERENTE, Conversa
from agente.redator import Redacao, citacoes

PERSONAS = json.loads((config.RAIZ / "dados" / "fixtures" / "personas.json").read_text(encoding="utf-8"))
TOTAL = PERSONAS["TOTAL"]["cliente_id"]
FRONTEIRA = PERSONAS["PRATICO"]["cliente_id"]


# ---------- dublês, para testar o fluxo sem API ----------


class DecisorFixo(Decisor):
    """Responde sempre a primeira opção ('agente' na rota) e nega as checagens do guardrail."""

    nome = "fixo"

    def avaliar(self, contexto, questoes):
        self.ultima_execucao = {"decisor": self.nome, "modelo": "fixo", "segundos": 0, "tokens": None}
        saida = {}
        for nome, q in questoes.items():
            if q.tipo == "afirmacao":
                saida[nome] = Resposta(valor="nao", probabilidade=0.99, p_verdadeiro=0.01)
            elif nome == "rota":
                saida[nome] = Resposta(valor="agente", probabilidade=0.99)
            else:
                valor = q.niveis[0] if q.tipo == "nota" else next(iter(q.opcoes))
                saida[nome] = Resposta(valor=valor, probabilidade=0.99)
        return saida


def redator_que_responde(*textos):
    """Redator falso que devolve os textos em sequência (um por chamada)."""
    fila = list(textos)

    def redigir(entrada, instrucao_extra=None):
        texto = fila.pop(0)
        return Redacao(texto=texto, citacoes=citacoes(texto), modelo="falso", segundos=0, tokens={})

    return redigir


@pytest.fixture
def arquivo_log(tmp_path):
    return tmp_path / "turnos.jsonl"


# ---------- determinístico ----------


def test_citacao_inexistente_e_barrada():
    clausulas = rag.buscar_para_turno("cobre incêndio?", None, None)
    motivo = conferir_citacoes("Cobre sim [cl. CG-99.9].", clausulas, encaminhando=False)
    assert motivo and "CG-99.9" in motivo


def test_citacao_real_mas_nao_recuperada_tambem_e_barrada():
    clausulas = rag.buscar_para_turno("cobre incêndio?", None, None)
    assert "CG-8.2.a" not in {c.id for c in clausulas}
    assert conferir_citacoes("Não cobre [cl. CG-8.2.a].", clausulas, encaminhando=False)


def test_resposta_cortada_e_barrada():
    clausulas = rag.buscar_para_turno("o que o plano total cobre?", None, None)
    assert conferir_citacoes("O TOTAL cobre [cl. PLANO-TOTAL].", clausulas, False, cortada=True)
    assert conferir_citacoes("O TOTAL cobre [cl. PLANO-TOT", clausulas, False)


def test_resposta_sem_citacao_so_passa_quando_encaminha():
    assert conferir_citacoes("Cobre tudo.", [], encaminhando=False)
    assert conferir_citacoes("Um gerente vai continuar.", [], encaminhando=True) is None


def test_reprovada_duas_vezes_vai_para_o_gerente(arquivo_log):
    conversa = Conversa(
        TOTAL,
        decisor=DecisorFixo(),
        redigir_fn=redator_que_responde("Cobre [cl. CG-99.9].", "Cobre mesmo [cl. INVENTADA-1.1]."),
        arquivo_log=arquivo_log,
    )
    estado = conversa.turno("o seguro cobre incêndio?")
    assert estado.resposta == MENSAGEM_GERENTE
    assert estado.requer_humano and "guardrail" in estado.motivo_humano
    assert estado.guardrail.tentativas == 2 and not estado.guardrail.aprovado
    registro = log.ler(arquivo_log)[0]
    assert "CG-99.9" in registro["resposta_reprovada"] and "INVENTADA" in registro["resposta_reprovada_2"]


def test_reescrita_corrige_e_passa(arquivo_log):
    conversa = Conversa(
        TOTAL,
        decisor=DecisorFixo(),
        redigir_fn=redator_que_responde("Cobre [cl. CG-99.9].", "O TOTAL tem estas coberturas [cl. PLANO-TOTAL]."),
        arquivo_log=arquivo_log,
    )
    estado = conversa.turno("o que o meu plano cobre?")
    assert estado.guardrail.aprovado and estado.guardrail.tentativas == 2
    assert not estado.requer_humano and "PLANO-TOTAL" in estado.resposta


def test_log_tem_o_necessario_para_auditoria(arquivo_log):
    conversa = Conversa(
        TOTAL,
        decisor=DecisorFixo(),
        redigir_fn=redator_que_responde("O TOTAL cobre [cl. PLANO-TOTAL]."),
        arquivo_log=arquivo_log,
        sessao_id="teste",
    )
    conversa.turno("oi")
    registro = log.ler(arquivo_log, "teste")[0]
    assert registro["versoes"]["motor_score"] and registro["versoes"]["embeddings"]
    assert {"decidir", "regras", "recuperar", "redigir", "conferir", "total"} <= set(registro["tempos_s"])
    estado = registro["estado"]
    assert estado["decisoes"]["intencao"]["probabilidade"] == 0.99
    assert estado["clausulas"] and estado["guardrail"]["aprovado"]


# ---------- com API ----------


@pytest.fixture(scope="module")
def decisor():
    return criar_decisor()


def test_guardrail_barra_preco(decisor):
    clausulas = rag.buscar_para_turno("o que o plano total cobre?", None, None)
    resultado = conferir("O plano TOTAL custa R$ 89,90 por mês [cl. PLANO-TOTAL].", clausulas, decisor)
    assert not resultado.aprovado and "preço" in resultado.motivo


def test_guardrail_barra_promessa_contra_a_exclusao(decisor):
    clausulas = rag.buscar_para_turno("a enchente alagou a loja", None, None)
    resultado = conferir("Pode ficar tranquilo: alagamento por enchente está coberto [cl. CG-8.1.l].", clausulas, decisor)
    assert not resultado.aprovado and "promete" in resultado.motivo


def test_conversa_de_fronteira_ponta_a_ponta(decisor, arquivo_log):
    conversa = Conversa(FRONTEIRA, decisor=decisor, arquivo_log=arquivo_log)
    primeiro = conversa.turno("Oi, que seguro vocês recomendam para a minha farmácia?")
    assert primeiro.guardrail.aprovado and not primeiro.requer_humano
    assert primeiro.resposta.count("?") == 1  # faz a pergunta pendente
    segundo = conversa.turno("Somos uns 30 funcionários.")
    assert (segundo.perfil_atualizado.pacote_anterior, segundo.perfil_atualizado.pacote) == ("PRATICO", "TOTAL")
    assert segundo.guardrail.aprovado and not segundo.requer_humano
    assert len(log.ler(arquivo_log, conversa.sessao_id)) == 2


def test_resposta_vaga_vai_para_o_gerente(decisor, arquivo_log):
    conversa = Conversa(FRONTEIRA, decisor=decisor, arquivo_log=arquivo_log)
    estado = conversa.turno("sei lá, nunca contei quantos funcionários a gente tem")
    assert estado.requer_humano and estado.perfil_atualizado.pacote == estado.perfil_atualizado.pacote_anterior
