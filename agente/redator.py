"""Redação da resposta (Claude Haiku). O LLM só escreve: plano, valores e cláusulas chegam prontos.

Regras de redação: uma pergunta por vez, risco em reais (a partir dos valores do perfil, nunca
preço), toda afirmação de cobertura citada como [cl. ID] com um id da lista recebida.
"""

import json
import re
import time

from pydantic import BaseModel

from agente import config
from agente.contratos import ClausulaRecuperada, Decisoes, Perfil, PerfilAtualizado, Pergunta, PlanoPersonalizado

RE_CITACAO = re.compile(r"\[cl\.\s*([^\]]+?)\s*\]")

SISTEMA = """Você é o assistente de vendas do Seguro Empresarial do Banco do Brasil, conversando com o dono de um pequeno negócio.
Você recebe um JSON com o cliente, o plano já calculado pelo sistema, as cláusulas recuperadas das Condições Gerais e a mensagem do cliente. Escreva só a resposta ao cliente.

Regras obrigatórias:
1. O plano é personalizado cobertura por cobertura: `plano_recomendado` é o pacote BB pelo qual se contrata (o menor que cobre o que é essencial para este negócio), e `plano_personalizado.adicionais` são coberturas necessárias que ficam fora do pacote. Apresente pelo que o negócio precisa, não pelo nome do pacote. Nunca recomende outro nem faça contas de plano. Não diga que a recomendação veio de algo que o cliente informou, a menos que haja `confirmacao_do_cliente` ou `respostas_do_cliente`. Se `plano_anterior` for diferente, diga em uma frase que a resposta do cliente mudou a recomendação. Use só os números de `cliente.valores_estimados`; não deduza nem compare números a partir da confirmação.
2. Toda afirmação sobre o que o seguro cobre ou não cobre cita pelo menos uma cláusula de `clausulas`, no formato [cl. ID], com o ID copiado exatamente. Um ID por colchete. Nunca cite um ID que não está na lista.
3. Se nenhuma cláusula da lista sustenta a resposta, diga que vai confirmar com o gerente. Não invente cobertura.
4. Cláusula com `no_plano: false` não está no plano do cliente: diga isso e, se `planos` não estiver vazio, em qual plano está. Cláusula com `no_catalogo: false` é cobertura adicional fora dos três planos.
5. Pedido que cai numa exclusão (`tipo: exclusao`): recuse com clareza e cite a cláusula.
6. Risco em reais: quando ajudar, use os valores de `cliente.valores_estimados` para mostrar o que está em jogo. Nunca informe preço, prêmio, valor de franquia, aprovação de sinistro ou elegibilidade.
7. Ao apresentar a recomendação, fale do plano base e de no máximo 2 adicionais de `plano_personalizado.adicionais` (os mais relevantes para a mensagem), cada um com o motivo, a faixa sugerida de limite de indenização ("limite sugerido entre R$ X e R$ Y") e a cláusula do adicional. Diga que as faixas são sugestões a confirmar. Limite de indenização não é preço.
8. Só se o cliente perguntar sobre riscos cibernéticos (hacker, vírus, ransomware, golpe digital): os planos incluem a Ampla Proteção Cibernética; cite SITE-CIBERNETICA e diga que o que ela cobre em detalhe é confirmado com o gerente. Não use CG-8.2.a para negar essa proteção.
9. Se houver `plano_personalizado.dados_a_conferir`, não use esses números como certos.
10. No máximo uma pergunta ao cliente. Se houver `proxima_pergunta`, termine com ela (pode reformular sem mudar o sentido).
11. Se `encaminhar_gerente` for true, diga que um gerente vai continuar o atendimento e não faça pergunta.
12. Não use nem mencione dado pessoal sensível, processos judiciais ou informações que o cliente não deu.
13. Português do Brasil, tom cordial e direto, até 150 palavras, sem listas longas nem markdown pesado.
14. Se `apresentar_recomendacao` for true, é a primeira recomendação depois das perguntas: diga em uma frase que o plano foi montado com o que o cliente contou em `respostas_do_cliente` (sem repetir todos os números), apresente as coberturas essenciais deste negócio e os adicionais com a faixa sugerida, cite as cláusulas e termine perguntando se quer ajustar algo. Comece pela recomendação, não por uma resposta à última mensagem. Neste caso o limite é de 180 palavras.
15. Se houver `respostas_do_cliente`, o cliente respondeu em faixas: cite a faixa como ele respondeu ("6 a 16 funcionários"), nunca um número exato, e nunca apresente como fato um valor que ele não informou (os motivos das coberturas trazem estimativas internas).
16. `plano_personalizado.risco_do_local` traz perigos naturais da região do estabelecimento, de dados públicos. Ao apresentar a recomendação, ou se o cliente perguntar sobre o local, mencione em uma ou duas frases os de nível ALTO (ou MEDIO, se não houver ALTO): os de `coberto: true` ligados à cobertura que protege, com a cláusula; os de `coberto: false` (alagamento, deslizamento, barragem) deixando claro que o seguro não cobre, com a cláusula de exclusão. Pode dizer que o risco da região entra na análise da seguradora e pode pesar no custo, mas nunca cite valor, percentual ou fator. Se `analise_de_aceitacao` for true, diga que a contratação depende da análise do risco pela seguradora."""


class Redacao(BaseModel):
    texto: str
    citacoes: list[str]
    modelo: str
    segundos: float
    tokens: dict
    cortada: bool = False
    """True se a geração parou por limite de tokens (a resposta está incompleta)."""


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


def _faixa(c) -> str:
    return f"R$ {c.faixa_valor_min:,.0f} a R$ {c.faixa_valor_max:,.0f}".replace(",", ".")


def resumo_personalizado(p: PlanoPersonalizado) -> dict:
    """O que o redator precisa do plano personalizado (sem as regras de cálculo)."""
    return {
        "plano_base": p.plano_base,
        "coberturas_do_plano": [
            {"cobertura": c.cobertura, "limite_sugerido": _faixa(c)} for c in p.coberturas if c.origem == "plano"
        ],
        "adicionais": [
            {"cobertura": c.cobertura, "motivo": c.justificativa, "limite_sugerido": _faixa(c), "clausula": c.clausulas[0]}
            for c in p.adicionais
        ],
        "dados_a_conferir": p.dados_a_conferir,
    } | ({"risco_do_local": resumo_risco(p.risco_local)} if p.risco_local else {})


def resumo_risco(r) -> dict:
    """Perigos médios e altos do local (os baixos e sem dado não ajudam a resposta); sem o fator de agravamento."""
    return {
        "local": ", ".join(x for x in (r.local.bairro, f"{r.local.municipio}/{r.local.uf}") if x),
        "precisao": "endereço do CEP" if r.local.precisao == "CEP" else "só o município",
        "perigos": [
            {"perigo": p.nome, "nivel": p.nivel, "indicador": p.indicador, "coberto": p.coberto, "cobertura": p.cobertura, "clausulas": p.clausulas}
            for p in r.perigos
            if p.nivel in ("ALTO", "MEDIO")
        ],
        "analise_de_aceitacao": r.analise_de_aceitacao,
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
    personalizado: PlanoPersonalizado | None = None,
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
        "plano_recomendado": (
            personalizado.plano_base if personalizado else (atualizado.plano if atualizado else perfil.plano)
        ),
        "plano_anterior": (
            atualizado.pacote_anterior
            if atualizado and atualizado.pacote_anterior
            else (personalizado.plano_base if personalizado else perfil.plano)
        ),
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
    if personalizado is not None:
        entrada["plano_personalizado"] = resumo_personalizado(personalizado)
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
        # Haiku 5.5 pensa por padrão; mesmo com esforço "low" gastava ~1.600 tokens de raciocínio
        # (13 s) para redigir com fatos e cláusulas já prontos. Sem raciocínio: ~4x mais rápido;
        # o guardrail continua conferindo cada resposta.
        max_tokens=8000,
        output_config={"effort": "low"},
        thinking={"type": "disabled"},
        system=SISTEMA,
        messages=[{"role": "user", "content": conteudo}],
    )
    texto = "".join(b.text for b in resposta.content if b.type == "text").strip()
    return Redacao(
        texto=texto,
        citacoes=citacoes(texto),
        modelo=resposta.model,
        segundos=round(time.perf_counter() - inicio, 3),
        tokens={
            "input_tokens": resposta.usage.input_tokens,
            "output_tokens": resposta.usage.output_tokens,
            "thinking_tokens": getattr(getattr(resposta.usage, "output_tokens_details", None), "thinking_tokens", None),
        },
        cortada=resposta.stop_reason == "max_tokens",
    )
