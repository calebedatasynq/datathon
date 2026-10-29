"""Escolhe as três personas da demo na base de teste comum e grava dados/fixtures/personas.json.

A chave é o pacote de contratação do plano personalizado (não só o índice do motor).
ESSENCIAL e TOTAL: casos claros (dados completos, sem pergunta, mais longe do corte do motor).
PRATICO: caso de fronteira (dados completos e uma pergunta cujo sim e não levam a planos
personalizados diferentes), para mostrar a confirmação do Jev ao vivo.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agente import config  # noqa: E402
from agente.contratos import Confirmacao, Plano  # noqa: E402
from agente.dados_base import get_estabelecimento  # noqa: E402
from agente.perfil import get_perfil_cliente, listar_clientes  # noqa: E402
from agente.personalizacao import perfil_relevante, personalizar  # noqa: E402
from agente.regras import aplicar_confirmacao  # noqa: E402

DESTINO = config.RAIZ / "dados" / "fixtures" / "personas.json"


def selecionar() -> dict:
    casos, com_aviso = [], []
    for cliente_id in listar_clientes():
        est = get_estabelecimento(cliente_id)
        perfil = perfil_relevante(get_perfil_cliente(cliente_id), est)
        plano = personalizar(perfil, est)
        if perfil.plano and not plano.dados_a_conferir and plano.elegivel == "SIM":
            (com_aviso if perfil.avisos else casos).append((perfil, plano))
    personas = {}
    for pacote in (Plano.ESSENCIAL, Plano.TOTAL):
        claros = [(pf, pl) for pf, pl in casos if pl.plano_base == pacote and not pf.perguntas_pendentes]
        escolhido = max(claros, key=lambda c: (len(c[1].adicionais) > 0, c[0].distancia_ao_corte))
        personas[pacote] = {"cliente_id": escolhido[0].cliente_id, "tipo": "claro"}
    # Fronteira boa para a demo: o "sim" do cliente faz o pacote subir (a mudança aparece na tela).
    fronteira = []
    # Aqui um aviso de área imputada é aceito: poucos casos têm um "sim" que sobe o pacote.
    for pf, pl in casos + com_aviso:
        if pl.plano_base != Plano.PRATICO or not pf.perguntas_pendentes:
            continue
        pergunta = pf.perguntas_pendentes[0]
        _, novo = aplicar_confirmacao(pf, Confirmacao(pergunta_id=pergunta.id, valor="sim", probabilidade=1))
        if personalizar(novo, get_estabelecimento(pf.cliente_id)).plano_base == Plano.TOTAL:
            fronteira.append((pf, pl))
    escolhido = min(fronteira, key=lambda c: c[0].distancia_ao_corte)
    personas[Plano.PRATICO] = {"cliente_id": escolhido[0].cliente_id, "tipo": "fronteira"}
    return {plano.value: personas[plano] for plano in Plano}


if __name__ == "__main__":
    personas = selecionar()
    DESTINO.write_text(json.dumps(personas, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(personas, indent=2, ensure_ascii=False))
