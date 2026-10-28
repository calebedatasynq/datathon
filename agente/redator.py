"""Redação da resposta (Claude Haiku). O LLM só escreve: plano, valores e cláusulas chegam prontos.

Regras de redação: uma pergunta por vez, risco em reais (a partir dos valores do perfil, nunca
preço), toda afirmação de cobertura citada como [cl. ID] com um id da lista recebida.
"""

import json
import re
import time

from pydantic import BaseModel

from agente import config
from agente.contratos import ClausulaRecuperada, Decisoes, Perfil, PerfilAtualizado, Pergunta

RE_CITACAO = re.compile(r"\[cl\.\s*([^\]]+?)\s*\]")

SISTEMA = """Você é o assistente de vendas do Seguro Empresarial do Banco do Brasil, conversando com o dono de um pequeno negócio.
Você recebe um JSON com o cliente, o plano já calculado pelo sistema, as cláusulas recuperadas das Condições Gerais e a mensagem do cliente. Escreva só a resposta ao cliente.

Regras obrigatórias:
1. O plano é `plano_recomendado`, calculado pela análise do cadastro do cliente no banco. Nunca recomende outro nem faça contas de plano. Não diga que a recomendação veio de algo que o cliente informou, a menos que haja `confirmacao_do_cliente`. Se `plano_anterior` for diferente, diga em uma frase que a resposta do cliente mudou a recomendação. Use só os números de `cliente.valores_estimados`; não deduza nem compare números a partir da confirmação.
2. Toda afirmação sobre o que o seguro cobre ou não cobre cita pelo menos uma cláusula de `clausulas`, no formato [cl. ID], com o ID copiado exatamente. Um ID por colchete. Nunca cite um ID que não está na lista.
3. Se nenhuma cláusula da lista sustenta a resposta, diga que vai confirmar com o gerente. Não invente cobertura.
4. Cláusula com `no_plano: false` não está no plano do cliente: diga isso e, se `planos` não estiver vazio, em qual plano está. Cláusula com `no_catalogo: false` é cobertura adicional fora dos três planos.
5. Pedido que cai numa exclusão (`tipo: exclusao`): recuse com clareza e cite a cláusula.
6. Risco em reais: quando ajudar, use os valores de `cliente.valores_estimados` para mostrar o que está em jogo. Nunca informe preço, prêmio, valor de franquia, aprovação de sinistro ou elegibilidade.
7. No máximo uma pergunta ao cliente. Se houver `proxima_pergunta`, termine com ela (pode reformular sem mudar o sentido).
8. Se `encaminhar_gerente` for true, diga que um gerente vai continuar o atendimento e não faça pergunta.
9. Não use nem mencione dado pessoal sensível, processos judiciais ou informações que o cliente não deu.
10. Português do Brasil, tom cordial e direto, até 120 palavras, sem listas longas nem markdown pesado."""


class Redacao(BaseModel):
    texto: str
    citacoes: list[str]
    modelo: str
    segundos: float
    tokens: dict


def citacoes(texto: str) -> list[str]:
    return RE_CITACAO.findall(texto)


VALORES = {
    "funcionarios_estimados_empresa": "funcionarios_empresa",
    "estoque_medio_estimado": "estoque_medio_reais",
    "valor_bens_ponderado_estabelecimento": "bens_do_endereco_reais",
    "faturamento_mensal_empresa": "faturamento_mensal_empresa_reais",
}


def _valores(perfil: Perfil) -> dict:
    # Variável confirmada fica de fora: na entrada do motor ela vale o limiar, não um dado real.
    return {nome: perfil.entrada.get(campo) for campo, nome in VALORES.items() if campo not in perfil.confirmadas}


def _clausula(c: ClausulaRecuperada) -> dict:
    return {
        "id": c.id,
        "tipo": c.tipo.value,
        "cobertura": c.cobertura,
        "planos": [p.value for p in c.planos],
        "no_plano": c.no_plano,
        "no_catalogo": c.no_catalogo,
        "texto": c.texto,
    }


def montar_entrada(
    perfil: Perfil,
    mensagem: str,
    clausulas: list[ClausulaRecuperada],
    atualizado: PerfilAtualizado | None = None,
    decisoes: Decisoes | None = None,
    encaminhar_gerente: bool = False,
    objecao: dict | None = None,
    historico: list[dict] | None = None,
    pergunta_respondida: Pergunta | None = None,
) -> dict:
    """pergunta_respondida: a pergunta que o cliente acabou de confirmar (sim/não aplicável)."""
    proxima: Pergunta | None = atualizado.proxima_pergunta if atualizado else (
        perfil.perguntas_pendentes[0] if perfil.perguntas_pendentes else None
    )
    entrada = {
        "cliente": {
            "segmento": perfil.segmento,
            "tipo_unidade": perfil.entrada.get("tipo_unidade"),
            "valores_estimados": _valores(perfil),
        },
        "plano_recomendado": (atualizado.plano if atualizado else perfil.plano),
        "plano_anterior": (atualizado.plano_anterior if atualizado else perfil.plano),
        "intencao_do_cliente": decisoes.intencao.valor if decisoes and decisoes.intencao else None,
        "proxima_pergunta": None if encaminhar_gerente or proxima is None else proxima.texto,
        "encaminhar_gerente": encaminhar_gerente,
        "clausulas": [_clausula(c) for c in clausulas],
        "historico": historico or [],
        "mensagem_do_cliente": mensagem,
    }
    if pergunta_respondida is not None and decisoes and decisoes.confirmacao:
        entrada["confirmacao_do_cliente"] = {
            "pergunta": pergunta_respondida.texto,
            "resposta": decisoes.confirmacao.valor,
        }
    if objecao:
        entrada["orientacao_para_objecao"] = {"objecao": objecao["objecao"], "como_responder": objecao["orientacao"]}
    return entrada


def redigir(entrada: dict, instrucao_extra: str | None = None, modelo: str | None = None) -> Redacao:
    """instrucao_extra é usada pelo guardrail para pedir a reescrita."""
    cliente = config.cliente_anthropic()
    conteudo = json.dumps(entrada, ensure_ascii=False)
    if instrucao_extra:
        conteudo += f"\n\nCorreção obrigatória: {instrucao_extra}"
    inicio = time.perf_counter()
    resposta = cliente.messages.create(
        model=modelo or config.MODELO_LLM,
        max_tokens=2000,
        system=SISTEMA,
        messages=[{"role": "user", "content": conteudo}],
    )
    texto = "".join(b.text for b in resposta.content if b.type == "text").strip()
    return Redacao(
        texto=texto,
        citacoes=citacoes(texto),
        modelo=resposta.model,
        segundos=round(time.perf_counter() - inicio, 3),
        tokens={"input_tokens": resposta.usage.input_tokens, "output_tokens": resposta.usage.output_tokens},
    )
