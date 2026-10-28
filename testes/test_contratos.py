import pytest
from pydantic import ValidationError

from agente.contratos import Confirmacao, Decisoes, EstadoTurno, Perfil, Plano


def test_estado_turno_minimo():
    estado = EstadoTurno(cliente_id="EST_0042", mensagem="tenho uns 50 mil em mercadoria")
    assert estado.decisoes == Decisoes()
    assert estado.requer_humano is False


def test_estado_turno_roundtrip_json():
    estado = EstadoTurno(
        cliente_id="EST_0042",
        mensagem="tenho uns 50 mil em mercadoria",
        perfil=Perfil(
            cliente_id="IMO_0042",
            empresa_id="EMP_0042",
            segmento="VAREJO_MODA",
            status="EXPERIMENTAL_BASE_MOCK",
            plano=Plano.PRATICO,
            score=0.5,
            cortes=[0.28, 0.99],
            entrada={"imovel_id": "IMO_0042"},
        ),
        decisoes=Decisoes(
            confirmacao=Confirmacao(pergunta_id="estoque_40k", valor="sim", probabilidade=0.92)
        ),
    )
    assert EstadoTurno.model_validate_json(estado.model_dump_json()) == estado


def test_probabilidade_fora_do_intervalo_falha():
    with pytest.raises(ValidationError):
        Confirmacao(pergunta_id="x", valor="sim", probabilidade=1.5)
