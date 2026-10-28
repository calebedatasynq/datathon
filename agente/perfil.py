"""Camada A: perfil do cliente a partir do motor de score (score_empresa), sem LLM.

A pergunta pendente é achada por contrafactual: para cada variável estimada,
procura-se o valor em que o próprio score_empresa troca de plano. Se esse corte
está a até MARGEM_PERGUNTA do valor estimado, vale perguntar ao cliente.
"""

import csv
import importlib.util
import math
from functools import cache

from agente import config
from agente.contratos import Perfil, Pergunta, Plano

CAMPOS_ENTRADA = [
    "empresa_id",
    "imovel_id",
    "funcionarios_estimados_empresa",
    "estoque_medio_estimado",
    "valor_bens_ponderado_estabelecimento",
    "faturamento_mensal_empresa",
    "quantidade_estabelecimentos_empresa",
    "area_m2",
    "grupo_atividade",
    "tipo_unidade",
]
CAMPOS_TEXTO = {"empresa_id", "imovel_id", "grupo_atividade", "tipo_unidade"}

# Variáveis que o cliente consegue confirmar e que pesam no score (pesos positivos).
VARIAVEIS_PERGUNTA = [
    "estoque_medio_estimado",
    "valor_bens_ponderado_estabelecimento",
    "funcionarios_estimados_empresa",
]
VARIAVEIS_INTEIRAS = {"funcionarios_estimados_empresa"}


def _carregar_motor():
    spec = importlib.util.spec_from_file_location("motor_score", config.DIR_MOTOR / "score.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo.score_empresa


score_empresa = _carregar_motor()


@cache
def _base() -> dict[str, dict]:
    with open(config.BASE_CLIENTES, encoding="utf-8-sig", newline="") as f:
        return {linha["imovel_id"]: _entrada(linha) for linha in csv.DictReader(f)}


def _entrada(linha: dict) -> dict:
    entrada = {}
    for campo in CAMPOS_ENTRADA:
        valor = linha.get(campo)
        if campo in CAMPOS_TEXTO:
            entrada[campo] = valor
        else:
            entrada[campo] = float(valor) if valor not in (None, "") else None
    return entrada


def listar_clientes() -> list[str]:
    return list(_base())


def plano_de(entrada: dict) -> Plano | None:
    plano = score_empresa(entrada)["plano_sugerido"]
    return Plano(plano) if plano else None


def _com(entrada: dict, variavel: str, valor: float) -> dict:
    return {**entrada, variavel: valor}


def _limiar(entrada: dict, variavel: str, a: float, b: float) -> float:
    """Menor valor em [a, b] cujo plano é o de b (o score cresce com a variável)."""
    plano_b = plano_de(_com(entrada, variavel, b))
    for _ in range(60):
        meio = (a + b) / 2
        if plano_de(_com(entrada, variavel, meio)) == plano_b:
            b = meio
        else:
            a = meio
    return b


def _texto(variavel: str, limiar: float) -> str:
    reais = f"R$ {limiar:,.0f}".replace(",", ".")
    match variavel:
        case "estoque_medio_estimado":
            return f"O estoque médio deste endereço passa de {reais}?"
        case "valor_bens_ponderado_estabelecimento":
            return f"Os bens deste endereço (máquinas, equipamentos, móveis) somam mais de {reais}?"
        case "funcionarios_estimados_empresa":
            return f"A empresa tem {limiar:.0f} funcionários ou mais?"
    raise ValueError(variavel)


def pergunta_decisiva(entrada: dict) -> Pergunta | None:
    """A variável cujo corte de plano está mais perto do valor estimado, se dentro da margem."""
    plano = plano_de(entrada)
    if plano is None:
        return None
    melhor = None
    for variavel in VARIAVEIS_PERGUNTA:
        atual = entrada.get(variavel)
        if not atual:
            continue
        cima, baixo = atual * (1 + config.MARGEM_PERGUNTA), atual * (1 - config.MARGEM_PERGUNTA)
        candidatos = []
        if plano_de(_com(entrada, variavel, cima)) != plano:
            candidatos.append(_limiar(entrada, variavel, atual, cima))
        if plano_de(_com(entrada, variavel, baixo)) != plano:
            candidatos.append(_limiar(entrada, variavel, baixo, atual))
        for limiar in candidatos:
            if variavel in VARIAVEIS_INTEIRAS:
                limiar = float(math.ceil(limiar))
            distancia = abs(limiar / atual - 1)
            if distancia > config.MARGEM_PERGUNTA:
                continue
            if melhor is None or distancia < melhor[0]:
                melhor = (distancia, variavel, atual, limiar)
    if melhor is None:
        return None
    _, variavel, atual, limiar = melhor
    abaixo = limiar - 1 if variavel in VARIAVEIS_INTEIRAS else limiar * (1 - 1e-9)
    return Pergunta(
        id=f"{variavel}_acima_{limiar:.0f}",
        texto=_texto(variavel, limiar),
        variavel=variavel,
        valor_estimado=atual,
        limiar=limiar,
        plano_se_sim=plano_de(_com(entrada, variavel, limiar)),
        plano_se_nao=plano_de(_com(entrada, variavel, abaixo)),
    )


def perfil_de_entrada(entrada: dict) -> Perfil:
    saida = score_empresa(entrada)
    pergunta = pergunta_decisiva(entrada)
    return Perfil(
        cliente_id=saida["imovel_id"],
        empresa_id=saida["empresa_id"],
        segmento=entrada.get("grupo_atividade") or "",
        status=saida["status"],
        plano=saida["plano_sugerido"],
        score=saida["score"],
        cortes=saida["cortes"],
        probabilidades=saida["probabilidades_referencia"],
        distancia_ao_corte=saida.get("distancia_ao_corte_mais_proximo"),
        avisos=saida["avisos"],
        perguntas_pendentes=[pergunta] if pergunta else [],
        entrada=entrada,
    )


def get_perfil_cliente(cliente_id: str) -> Perfil:
    """cliente_id é o imovel_id do estabelecimento na base de teste comum."""
    try:
        entrada = _base()[cliente_id]
    except KeyError:
        raise KeyError(f"Cliente não encontrado na base: {cliente_id}") from None
    return perfil_de_entrada(entrada)
