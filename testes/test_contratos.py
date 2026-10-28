import pytest
from pydantic import ValidationError

from agente.contratos import Confirmacao, Decisoes, EstadoTurno, NivelIPU, Perfil


def test_estado_turno_minimo():
    estado = EstadoTurno(cliente_id="EST_0042", mensagem="tenho uns 50 mil em mercadoria")
    assert estado.decisoes == Decisoes()
    assert estado.requer_humano is False


def test_estado_turno_roundtrip_json():
    estado = EstadoTurno(
        cliente_id="EST_0042",
        mensagem="tenho uns 50 mil em mercadoria",
        perfil=Perfil(
            cliente_id="EST_0042",
            segmento="varejo",
            plano_provavel="intermediario",
            ipu=NivelIPU.FRONTEIRA,
            confianca=0.8,
        ),
        decisoes=Decisoes(
            confirmacao=Confirmacao(pergunta_id="estoque_40k", valor="sim", probabilidade=0.92)
        ),
    )
    assert EstadoTurno.model_validate_json(estado.model_dump_json()) == estado


def test_probabilidade_fora_do_intervalo_falha():
    with pytest.raises(ValidationError):
        Confirmacao(pergunta_id="x", valor="sim", probabilidade=1.5)
