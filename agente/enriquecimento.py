"""Enriquecimento: CNPJ (BrasilAPI, dado aberto da Receita) e CNAE → segmento pelo Decisor.

A base do desafio é sintética e não tem CNPJ; a demo consulta um CNPJ público real e usa o
cache em dados/fixtures/cnpj_cache.json quando não há internet.
"""

import json
import re

import requests
from pydantic import BaseModel

from agente import config
from agente.contratos import Decisao
from agente.decisor import Decisor

URL_BRASILAPI = "https://brasilapi.com.br/api/cnpj/v1/{cnpj}"
CACHE_CNPJ = config.RAIZ / "dados" / "fixtures" / "cnpj_cache.json"

# Descrições genéricas dos grupos de atividade da base (sem copiar os CNAEs dela).
SEGMENTOS = {
    "BELEZA": "salão de beleza, cabeleireiro, estética, manicure",
    "CLINICA": "clínica ou consultório de saúde: médico, fisioterapia, exames",
    "ELETRONICOS": "loja de eletrônicos, informática, celulares, eletrodomésticos",
    "ESCOLA_CURSO": "escola, curso, treinamento ou ensino",
    "ESCRITORIO": "escritório de serviços profissionais: advocacia, contabilidade, consultoria",
    "FARMACIA": "farmácia ou drogaria",
    "MERCADO": "mercado, supermercado, mercearia ou comércio de alimentos e mercadorias em geral",
    "OFICINA": "oficina mecânica, autopeças ou serviços para veículos",
    "RESTAURANTE": "restaurante, lanchonete, bar ou fornecimento de refeições",
    "VAREJO_MODA": "loja de roupas, calçados, acessórios ou artigos de viagem",
    "OUTRO": "nenhum dos segmentos acima",
}


class Enriquecimento(BaseModel):
    cnpj: str
    razao_social: str | None = None
    cnae: str | None = None
    descricao_cnae: str | None = None
    municipio: str | None = None
    uf: str | None = None
    cep: str | None = None
    """CEP do endereço do CNPJ (para o risco do local)."""
    segmento: Decisao | None = None
    fonte: str
    """"brasilapi" ou "cache"."""


def _limpar(cnpj: str) -> str:
    digitos = re.sub(r"\D", "", cnpj)
    if len(digitos) != 14:
        raise ValueError(f"CNPJ inválido: {cnpj}")
    return digitos


def _cache() -> dict:
    return json.loads(CACHE_CNPJ.read_text(encoding="utf-8")) if CACHE_CNPJ.exists() else {}


def consultar_cnpj(cnpj: str, usar_rede: bool = True, timeout: float = 10) -> tuple[dict, str]:
    """Dados públicos do CNPJ e a fonte. Grava no cache a cada consulta bem-sucedida."""
    cnpj = _limpar(cnpj)
    cache = _cache()
    if usar_rede:
        try:
            resposta = requests.get(URL_BRASILAPI.format(cnpj=cnpj), timeout=timeout)
            resposta.raise_for_status()
            dados = resposta.json()
            campos = ("razao_social", "cnae_fiscal", "cnae_fiscal_descricao", "municipio", "uf", "cep")
            cache[cnpj] = {campo: dados.get(campo) for campo in campos}
            CACHE_CNPJ.write_text(json.dumps(cache, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
            return cache[cnpj], "brasilapi"
        except requests.RequestException:
            pass
    if cnpj in cache:
        return cache[cnpj], "cache"
    raise LookupError(f"CNPJ {cnpj} indisponível: sem rede e fora do cache")


def classificar_cnae(descricao: str, decisor: Decisor) -> Decisao:
    resposta = decisor.escolher(
        {"atividade_economica": descricao},
        "Em qual segmento de negócio se encaixa `atividade_economica` (descrição da CNAE)?",
        SEGMENTOS,
    )
    return resposta.decisao()


def enriquecer_cnpj(cnpj: str, decisor: Decisor, usar_rede: bool = True) -> Enriquecimento:
    dados, fonte = consultar_cnpj(cnpj, usar_rede)
    descricao = dados.get("cnae_fiscal_descricao")
    return Enriquecimento(
        cnpj=_limpar(cnpj),
        razao_social=dados.get("razao_social"),
        cnae=str(dados["cnae_fiscal"]) if dados.get("cnae_fiscal") else None,
        descricao_cnae=descricao,
        municipio=dados.get("municipio"),
        uf=dados.get("uf"),
        cep=str(dados["cep"]) if dados.get("cep") else None,
        segmento=classificar_cnae(descricao, decisor) if descricao else None,
        fonte=fonte,
    )
