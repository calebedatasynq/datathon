"""Riscos naturais do local, pelo CEP, a partir de fontes públicas abertas (sem chave).

- Endereço: ViaCEP (CEP → rua, bairro, município, código IBGE).
- Coordenada: Nominatim/OpenStreetMap (CEP → ponto; sem o CEP no OSM, a rua; por fim, a cidade).
- Clima: Open-Meteo. Arquivo ERA5 (2016–2025) para chuva forte e rajadas; previsões históricas
  (2023–2025) para trovoada e granizo, que o ERA5 não classifica.
- Relevo: Open-Meteo Elevation (Copernicus DEM 90 m) no ponto e em volta: declividade e baixada.
- Setores de risco geológico: SGB/CPRM (deslizamento, inundação, enxurrada), WFS público.
- Barragens: OpenStreetMap via Overpass, num raio de 10 km.

Os níveis são regras da equipe (limiares abaixo, calibrados com 10 cidades); não são critério de
subscrição da BB Seguros. O agravamento é indicativo para a subscrição e nunca é informado ao
cliente como preço. Cada fonte que falhar vira SEM_DADO no perigo correspondente, nunca BAIXO.
"""

import json
import math
import re
import threading
import time
import unicodedata
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import requests

from agente import config
from agente.contratos import Local, Perigo, RiscoLocal

ARQUIVO_CACHE = config.RAIZ / "dados" / "fixtures" / "territorio_cache.json"
ARQUIVO_BASE = config.RAIZ / "dados" / "fixtures" / "risco_territorio.json"
CABECALHO = {"User-Agent": "agente-seguro-empresarial-datathon/1.0 (prototipo academico)"}

URL_VIACEP = "https://viacep.com.br/ws/{cep}/json/"
URL_NOMINATIM = "https://nominatim.openstreetmap.org/search"
URL_ARQUIVO = "https://archive-api.open-meteo.com/v1/archive"
URL_PREVISOES = "https://historical-forecast-api.open-meteo.com/v1/forecast"
URL_ELEVACAO = "https://api.open-meteo.com/v1/elevation"
URL_SGB = "https://geoservicos.sgb.gov.br/geoserver/ows"
URLS_OVERPASS = ["https://overpass-api.de/api/interpreter", "https://maps.mail.ru/osm/tools/overpass/api/interpreter"]
TEMPO_OVERPASS_S = 12  # o Overpass é lento e limita consultas: passou disso, barragem fica SEM_DADO

# ---------- premissas da equipe (calibração: SP, POA, Curitiba, Manaus, Recife, Petrópolis,
# Chapecó, Fortaleza e Blumenau; ver docs/fontes_territoriais.md) ----------
PERIODO_CLIMA = ("2016-01-01", "2025-12-31")  # 10 anos de ERA5
PERIODO_MODELOS = ("2023-01-01", "2025-12-31")  # 3 anos de previsões (códigos de trovoada e granizo)
RAJADA_FORTE_KMH = 75  # vendaval da CG é vento ≥ 54 km/h (cl. TT-VENDAVAL); 75 separa os eventos que causam dano
CHUVA_FORTE_MM = 50  # chuva diária
CODIGOS_TROVOADA = {95, 96, 99}
CODIGOS_GRANIZO = {96, 99}
LIMIARES = {  # dias por ano: (MEDIO a partir de, ALTO a partir de)
    "VENDAVAL": (0.5, 1.5),
    "GRANIZO": (0.5, 1.5),
    "RAIOS": (3.0, 8.0),
    "CHUVA_FORTE": (1.0, 3.0),
}
DISTANCIA_RELEVO_M = (250, 1000)  # declividade no anel de 250 m; baixada contra o anel de 1 km
DECLIVIDADE_INGREME = 25  # %
BAIXADA_M = 8  # o ponto fica ao menos 8 m abaixo da média do entorno de 1 km
RAIO_SETOR_ALTO_M = 300
RAIO_SETOR_MEDIO_M = 1500
SETORES_MUNICIPIO_MEDIO = 20  # sem o endereço exato, município com muitos setores de risco alto
RAIO_BARRAGENS_M = 10_000
RAIO_BARRAGEM_PROXIMA_M = 3_000
PESO_AGRAVAMENTO = {"ALTO": 0.15, "MEDIO": 0.05}
FATOR_MAXIMO = 1.5

TIPOS_MASSA = ("desliz", "queda", "rastej", "corrida", "eros")
TIPOS_AGUA = ("inunda", "enxurr", "alaga")

NOMES = {
    "VENDAVAL": "Vendaval e ventos fortes",
    "GRANIZO": "Granizo",
    "RAIOS": "Tempestades com raios",
    "ALAGAMENTO": "Alagamento e enchente",
    "DESLIZAMENTO": "Deslizamento de encosta",
    "BARRAGEM": "Rompimento de barragem",
}
COBERTURA = {  # perigo → (a apólice pode cobrir?, cobertura, cláusulas)
    "VENDAVAL": (True, "VENDAVAL_EVENTOS_CORRELATOS", ["VENDAVAL_EVENTOS_CORRELATOS-1.1", "TT-VENDAVAL"]),
    "GRANIZO": (True, "VENDAVAL_EVENTOS_CORRELATOS", ["VENDAVAL_EVENTOS_CORRELATOS-1.1", "QUEBRA_DE_VIDROS-1.1.b"]),
    "RAIOS": (True, "DANOS_ELETRICOS", ["DANOS_ELETRICOS-1.1", "INCENDIO_RAIO_EXPLOSAO_FUMACA-1.1.b"]),
    "ALAGAMENTO": (False, None, ["CG-8.1.l", "VENDAVAL_EVENTOS_CORRELATOS-3.1.g"]),
    "DESLIZAMENTO": (False, None, ["CG-8.1.o"]),
    "BARRAGEM": (False, None, ["CG-8.1.l"]),
}
FONTES = {
    "viacep": "ViaCEP (endereço do CEP)",
    "nominatim": "Nominatim/OpenStreetMap (coordenada do CEP, ODbL)",
    "base": "territorio.csv do desafio (coordenada aproximada, perturbada)",
    "clima": "Open-Meteo Historical Weather (ERA5, ~25 km, diário 2016–2025)",
    "modelos": "Open-Meteo Historical Forecast (modelos de previsão, 2023–2025)",
    "relevo": "Open-Meteo Elevation (Copernicus DEM, 90 m)",
    "sgb": "SGB/CPRM, setores de risco geológico (WFS gestao-territorial:risco_geologico)",
    "barragens": "OpenStreetMap via Overpass (barragens num raio de 10 km)",
}


# ---------- cache em disco (respostas brutas: mudar um limiar não exige consultar de novo) ----------

_trava = threading.Lock()
_cache: dict | None = None


def _ler_cache() -> dict:
    global _cache
    if _cache is None:
        try:
            _cache = json.loads(ARQUIVO_CACHE.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            _cache = {}
    return _cache


def _em_cache(chave: str, buscar: Callable[[], object], usar_rede: bool = True):
    with _trava:
        if chave in _ler_cache():
            return _cache[chave]
    if not usar_rede:
        raise LookupError(f"sem cache para {chave}")
    valor = buscar()
    with _trava:
        _ler_cache()[chave] = valor
        ARQUIVO_CACHE.parent.mkdir(parents=True, exist_ok=True)
        ARQUIVO_CACHE.write_text(json.dumps(_cache, ensure_ascii=False, indent=0), encoding="utf-8")
    return valor


def _get(url: str, params: dict | None = None, timeout: float = 30) -> dict | list:
    r = requests.get(url, params=params, headers=CABECALHO, timeout=timeout)
    r.raise_for_status()
    return r.json()


def _normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", sem_acento).strip().upper()


def _distancia_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6_371_000 * math.asin(math.sqrt(a))


def _deslocar(lat: float, lon: float, norte_m: float, leste_m: float) -> tuple[float, float]:
    return lat + norte_m / 111_320, lon + leste_m / (111_320 * math.cos(math.radians(lat)))


# ---------- localização ----------


def normalizar_cep(texto: str) -> str | None:
    """O CEP (8 dígitos) contido no texto, ou None."""
    m = re.search(r"\b(\d{5})-?(\d{3})\b", texto or "")
    return m.group(1) + m.group(2) if m else None


def _nominatim(params: dict) -> dict | None:
    resultado = _get(URL_NOMINATIM, {**params, "format": "jsonv2", "addressdetails": 1, "limit": 1, "countrycodes": "br"}, 15)
    return resultado[0] if resultado else None


def _mesma_cidade(achado: dict, municipio: str) -> bool:
    end = achado.get("address", {})
    nomes = (end.get(k) for k in ("city", "town", "village", "municipality"))
    return any(_normalizar(n) == _normalizar(municipio) for n in nomes if n)


def localizar_cep(cep: str, usar_rede: bool = True) -> Local:
    """CEP → endereço (ViaCEP) e coordenada (OSM: o CEP, senão a rua, senão a cidade)."""
    cep = normalizar_cep(cep) or ""
    if len(cep) != 8:
        raise ValueError("CEP inválido")

    def buscar() -> dict:
        end = _get(URL_VIACEP.format(cep=cep), timeout=10)
        if end.get("erro"):
            raise LookupError("CEP não encontrado")
        municipio, uf = end["localidade"], end["uf"]
        tentativas = [
            ({"postalcode": f"{cep[:5]}-{cep[5:]}", "country": "Brasil"}, "CEP"),
            ({"street": end.get("logradouro"), "city": municipio, "state": uf, "country": "Brasil"}, "CEP"),
            ({"city": municipio, "state": uf, "country": "Brasil"}, "MUNICIPIO"),
        ]
        for params, precisao in tentativas:
            if any(v in (None, "") for v in params.values()):
                continue
            achado = _nominatim(params)
            if achado and _mesma_cidade(achado, municipio):
                return {
                    "cep": cep, "logradouro": end.get("logradouro") or None, "bairro": end.get("bairro") or None,
                    "municipio": municipio, "uf": uf, "codigo_ibge": end.get("ibge"),
                    "latitude": float(achado["lat"]), "longitude": float(achado["lon"]), "precisao": precisao,
                    "fonte": f"{FONTES['viacep']}; {FONTES['nominatim']}",
                }  # fmt: skip
            time.sleep(1)  # política de uso do Nominatim: no máximo 1 consulta por segundo
        raise LookupError("coordenada do CEP não encontrada")

    return Local(**_em_cache(f"cep:{cep}", buscar, usar_rede))


# ---------- fontes ----------


def _na_grade(lat: float, lon: float, passo: float) -> tuple[float, float]:
    """O ponto da grade do modelo mais próximo (o ERA5 tem 0,25°): mesma célula, mesma consulta."""
    return round(round(lat / passo) * passo, 4), round(round(lon / passo) * passo, 4)


def clima(lat: float, lon: float, usar_rede: bool = True) -> dict:
    """Dias por ano de chuva forte e de rajada forte (ERA5, 10 anos), com os máximos."""
    lat, lon = _na_grade(lat, lon, 0.25)

    def buscar() -> dict:
        d = _get(URL_ARQUIVO, {
            "latitude": lat, "longitude": lon, "start_date": PERIODO_CLIMA[0], "end_date": PERIODO_CLIMA[1],
            "daily": "precipitation_sum,wind_gusts_10m_max", "timezone": "America/Sao_Paulo",
        }, 60)["daily"]  # fmt: skip
        chuva = [x for x in d["precipitation_sum"] if x is not None]
        rajada = [x for x in d["wind_gusts_10m_max"] if x is not None]
        anos = len(d["time"]) / 365.25
        return {
            "anos": round(anos, 1),
            "chuva_forte_ano": round(sum(x >= CHUVA_FORTE_MM for x in chuva) / anos, 2),
            "chuva_maxima_mm": round(max(chuva, default=0), 1),
            "rajada_forte_ano": round(sum(x >= RAJADA_FORTE_KMH for x in rajada) / anos, 2),
            "rajada_maxima_kmh": round(max(rajada, default=0), 1),
        }

    return _em_cache(f"clima:{lat},{lon}", buscar, usar_rede)


def tempestades(lat: float, lon: float, usar_rede: bool = True) -> dict:
    """Dias por ano com trovoada e com granizo nos modelos de previsão (o ERA5 não traz esses códigos)."""
    lat, lon = _na_grade(lat, lon, 0.1)

    def buscar() -> dict:
        d = _get(URL_PREVISOES, {
            "latitude": lat, "longitude": lon, "start_date": PERIODO_MODELOS[0], "end_date": PERIODO_MODELOS[1],
            "daily": "weather_code", "timezone": "America/Sao_Paulo",
        }, 60)["daily"]  # fmt: skip
        codigos = [c for c in d["weather_code"] if c is not None]
        anos = len(d["time"]) / 365.25
        return {
            "anos": round(anos, 1),
            "trovoada_ano": round(sum(c in CODIGOS_TROVOADA for c in codigos) / anos, 2),
            "granizo_ano": round(sum(c in CODIGOS_GRANIZO for c in codigos) / anos, 2),
        }

    return _em_cache(f"tempestades:{lat},{lon}", buscar, usar_rede)


def relevo(lat: float, lon: float, usar_rede: bool = True) -> dict:
    """Declividade em volta do ponto (%) e quanto o ponto fica abaixo do entorno de 1 km (m)."""

    def buscar() -> dict:
        perto, longe = DISTANCIA_RELEVO_M
        pontos = [(lat, lon)]
        for distancia in (perto, longe):
            pontos += [_deslocar(lat, lon, n * distancia, l * distancia) for n, l in ((1, 0), (-1, 0), (0, 1), (0, -1))]
        d = _get(URL_ELEVACAO, {
            "latitude": ",".join(f"{p[0]:.5f}" for p in pontos), "longitude": ",".join(f"{p[1]:.5f}" for p in pontos),
        }, 20)["elevation"]  # fmt: skip
        centro, anel_perto, anel_longe = d[0], d[1:5], d[5:9]
        return {
            "altitude_m": round(centro, 1),
            "declividade_pct": round(max(abs(h - centro) for h in anel_perto) / perto * 100, 1),
            "abaixo_do_entorno_m": round(sum(anel_longe) / 4 - centro, 1),
        }

    return _em_cache(f"relevo:{lat:.4f},{lon:.4f}", buscar, usar_rede)


def _tipologias(p: dict) -> list[str]:
    return [p[f"tipolo_g{i}"].strip() for i in range(1, 6) if (p.get(f"tipolo_g{i}") or "").strip()]


def _dentro(lat: float, lon: float, anel: list) -> bool:
    dentro = False
    for (x1, y1), (x2, y2) in zip(anel, anel[1:] + anel[:1]):
        if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
            dentro = not dentro
    return dentro


def _distancia_poligono(lat: float, lon: float, geometria: dict) -> float:
    poligonos = geometria["coordinates"] if geometria["type"] == "MultiPolygon" else [geometria["coordinates"]]
    if any(_dentro(lat, lon, p[0]) for p in poligonos):
        return 0.0
    return min(_distancia_m(lat, lon, y, x) for p in poligonos for anel in p for x, y in anel)


def setores_proximos(lat: float, lon: float, usar_rede: bool = True) -> list[dict]:
    """Setores de risco geológico do SGB a até 1,5 km do ponto, com a distância."""

    def buscar() -> list[dict]:
        delta = 0.02  # ~2 km; o filtro fino é pela distância ao polígono
        d = _get(URL_SGB, {
            "service": "WFS", "version": "1.0.0", "request": "GetFeature", "typeName": "gestao-territorial:risco_geologico",
            "outputFormat": "application/json", "bbox": f"{lon - delta},{lat - delta},{lon + delta},{lat + delta}",
        }, 40)  # fmt: skip
        setores = []
        for f in d["features"]:
            distancia = _distancia_poligono(lat, lon, f["geometry"])
            if distancia <= RAIO_SETOR_MEDIO_M:
                p = f["properties"]
                setores.append({"tipologias": _tipologias(p), "grau": p.get("grau_risco"), "distancia_m": round(distancia), "setor": p.get("num_setor")})
        return sorted(setores, key=lambda s: s["distancia_m"])

    return _em_cache(f"sgb:{lat:.4f},{lon:.4f}", buscar, usar_rede)


def setores_do_municipio(municipio: str, uf: str, usar_rede: bool = True) -> dict:
    """Setores de risco alto ou muito alto do município, por grupo. mapeado=False: o SGB não setorizou a
    cidade (várias capitais têm mapeamento próprio), o que não quer dizer risco baixo."""

    def buscar() -> list[dict]:
        d = _get(URL_SGB, {
            "service": "WFS", "version": "1.0.0", "request": "GetFeature", "typeName": "gestao-territorial:risco_geologico",
            "outputFormat": "application/json", "CQL_FILTER": f"uf='{uf}'",
            "propertyName": "municipio,grau_risco,tipolo_g1,tipolo_g2,tipolo_g3,tipolo_g4,tipolo_g5",
        }, 60)  # fmt: skip
        return [{"municipio": f["properties"]["municipio"], "grau": f["properties"]["grau_risco"], "tipologias": _tipologias(f["properties"])} for f in d["features"]]

    setores = [s for s in _em_cache(f"sgb_uf:{uf}", buscar, usar_rede) if _normalizar(s["municipio"]) == _normalizar(municipio)]
    altos = [s for s in setores if _normalizar(s["grau"] or "") in ("ALTO", "MUITO ALTO")]
    return {
        "mapeado": bool(setores),
        "massa_alto": sum(_grupo(s["tipologias"]) == "massa" for s in altos),
        "agua_alto": sum(_grupo(s["tipologias"]) == "agua" for s in altos),
    }


def _grupo(tipologias: list[str]) -> str | None:
    texto = " ".join(tipologias).lower()
    if any(t in texto for t in TIPOS_MASSA):
        return "massa"
    if any(t in texto for t in TIPOS_AGUA):
        return "agua"
    return None


def barragens(lat: float, lon: float, usar_rede: bool = True) -> list[dict]:
    """Barragens do OpenStreetMap a até 10 km, com a distância e se é de rejeito de mineração."""
    consulta = (
        f"[out:json][timeout:{TEMPO_OVERPASS_S}];(way[\"waterway\"=\"dam\"](around:{RAIO_BARRAGENS_M},{lat},{lon});"
        f"way[\"man_made\"=\"dam\"](around:{RAIO_BARRAGENS_M},{lat},{lon});"
        f"way[\"reservoir_type\"=\"tailings\"](around:{RAIO_BARRAGENS_M},{lat},{lon}););out center tags;"
    )

    def buscar() -> list[dict]:
        erro, limite = None, time.monotonic() + TEMPO_OVERPASS_S
        for url in URLS_OVERPASS:
            restante = limite - time.monotonic()
            if restante < 2:
                break
            try:
                r = requests.post(url, data={"data": consulta}, headers=CABECALHO, timeout=restante)
                r.raise_for_status()
                elementos = r.json()["elements"]
                break
            except (requests.RequestException, ValueError, KeyError) as e:
                erro = e
        else:
            raise LookupError(f"Overpass indisponível: {erro}")
        achadas = []
        for e in elementos:
            ponto = e.get("center") or {"lat": e.get("lat"), "lon": e.get("lon")}
            if ponto.get("lat") is None:
                continue
            tags = e.get("tags", {})
            nome = tags.get("name")
            achadas.append({
                "nome": nome, "distancia_m": round(_distancia_m(lat, lon, ponto["lat"], ponto["lon"])),
                "rejeito": tags.get("reservoir_type") == "tailings" or "rejeito" in (nome or "").lower(),
            })  # fmt: skip
        return sorted(achadas, key=lambda b: b["distancia_m"])

    return _em_cache(f"barragens:{lat:.3f},{lon:.3f}", buscar, usar_rede)


# ---------- avaliação (pura, sem rede) ----------


def _por_limiar(valor: float, perigo: str) -> str:
    medio, alto = LIMIARES[perigo]
    return "ALTO" if valor >= alto else "MEDIO" if valor >= medio else "BAIXO"


def _num(valor: float, casas: int = 1) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


def _altura(abaixo_m: float) -> str:
    if abs(abaixo_m) < 1:
        return "o ponto fica na altura do entorno"
    return f"o ponto fica {_num(abs(abaixo_m), 0)} m {'abaixo' if abaixo_m > 0 else 'acima'} do entorno de 1 km"


def _perigo(id_: str, nivel: str, indicador: str, fonte: str) -> Perigo:
    coberto, cobertura, clausulas = COBERTURA[id_]
    return Perigo(id=id_, nome=NOMES[id_], nivel=nivel, indicador=indicador, fonte=fonte, coberto=coberto, cobertura=cobertura, clausulas=clausulas)


def _setor_mais_proximo(setores: list[dict], grupo: str, raio: float, altos: bool = False) -> dict | None:
    return next(
        (
            s for s in setores
            if _grupo(s["tipologias"]) == grupo and s["distancia_m"] <= raio
            and (not altos or _normalizar(s["grau"] or "") in ("ALTO", "MUITO ALTO"))
        ),
        None,
    )  # fmt: skip


def _texto_setor(s: dict) -> str:
    onde = "o endereço fica dentro de" if s["distancia_m"] == 0 else f"a {s['distancia_m']} m de"
    return f"{onde} setor de risco {(s['grau'] or '').lower()} de {', '.join(t.lower() for t in s['tipologias'])} mapeado pelo SGB"


def avaliar(
    local: Local,
    dados_clima: dict | None,
    dados_tempestades: dict | None,
    dados_relevo: dict | None,
    proximos: list[dict] | None,
    municipio: dict | None,
    dados_barragens: list[dict] | None,
    falhas: list[str] | None = None,
) -> RiscoLocal:
    """Nível de cada perigo a partir dos indicadores (None = a fonte falhou ou não se aplica)."""
    falhas = list(falhas or [])
    perigos = []
    preciso = local.precisao == "CEP"

    # clima (cobertos)
    if dados_clima:
        perigos.append(_perigo(
            "VENDAVAL", _por_limiar(dados_clima["rajada_forte_ano"], "VENDAVAL"),
            f"{_num(dados_clima['rajada_forte_ano'])} dia(s) por ano com rajadas de {RAJADA_FORTE_KMH} km/h ou mais; "
            f"máxima de {_num(dados_clima['rajada_maxima_kmh'], 0)} km/h (2016–2025)",
            FONTES["clima"],
        ))  # fmt: skip
    else:
        perigos.append(_perigo("VENDAVAL", "SEM_DADO", "clima não consultado", FONTES["clima"]))
    if dados_tempestades:
        perigos.append(_perigo(
            "GRANIZO", _por_limiar(dados_tempestades["granizo_ano"], "GRANIZO"),
            f"{_num(dados_tempestades['granizo_ano'])} dia(s) por ano com trovoada e granizo (2023–2025)", FONTES["modelos"],
        ))  # fmt: skip
        perigos.append(_perigo(
            "RAIOS", _por_limiar(dados_tempestades["trovoada_ano"], "RAIOS"),
            f"{_num(dados_tempestades['trovoada_ano'])} dia(s) por ano com trovoada (2023–2025)", FONTES["modelos"],
        ))  # fmt: skip
    else:
        perigos.append(_perigo("GRANIZO", "SEM_DADO", "previsões históricas não consultadas", FONTES["modelos"]))
        perigos.append(_perigo("RAIOS", "SEM_DADO", "previsões históricas não consultadas", FONTES["modelos"]))
    chuva = _por_limiar(dados_clima["chuva_forte_ano"], "CHUVA_FORTE") if dados_clima else None
    texto_chuva = (
        f"{_num(dados_clima['chuva_forte_ano'])} dia(s) por ano com mais de {CHUVA_FORTE_MM} mm de chuva" if dados_clima else ""
    )

    # alagamento e deslizamento (não cobertos)
    mapeado = bool(municipio and municipio["mapeado"])
    fonte_sgb = FONTES["sgb"] + (f"; {FONTES['relevo']}" if dados_relevo else "")
    if preciso and proximos is not None:
        for id_, grupo in (("ALAGAMENTO", "agua"), ("DESLIZAMENTO", "massa")):
            alto = _setor_mais_proximo(proximos, grupo, RAIO_SETOR_ALTO_M, altos=True)
            perto = _setor_mais_proximo(proximos, grupo, RAIO_SETOR_MEDIO_M)
            if alto:
                perigos.append(_perigo(id_, "ALTO", _texto_setor(alto), fonte_sgb))
            elif perto:
                perigos.append(_perigo(id_, "MEDIO", _texto_setor(perto), fonte_sgb))
            elif id_ == "ALAGAMENTO" and dados_relevo and dados_relevo["abaixo_do_entorno_m"] >= BAIXADA_M and chuva in ("MEDIO", "ALTO"):
                perigos.append(_perigo(
                    id_, "MEDIO", f"{_altura(dados_relevo['abaixo_do_entorno_m'])} e há {texto_chuva}", fonte_sgb,
                ))  # fmt: skip
            elif id_ == "DESLIZAMENTO" and dados_relevo and dados_relevo["declividade_pct"] >= DECLIVIDADE_INGREME:
                perigos.append(_perigo(id_, "MEDIO", f"terreno íngreme em volta ({_num(dados_relevo['declividade_pct'], 0)}% de declividade)", fonte_sgb))
            else:
                partes = ["nenhum setor de risco do SGB a menos de 1,5 km" if mapeado else "município sem setorização do SGB"]
                if dados_relevo:
                    partes.append(
                        _altura(dados_relevo["abaixo_do_entorno_m"]) if id_ == "ALAGAMENTO"
                        else f"declividade de {_num(dados_relevo['declividade_pct'], 0)}%"
                    )  # fmt: skip
                if id_ == "ALAGAMENTO" and texto_chuva:
                    partes.append(texto_chuva)
                nivel = "BAIXO" if mapeado or dados_relevo else "SEM_DADO"
                perigos.append(_perigo(id_, nivel, "; ".join(partes), fonte_sgb))
    else:
        # Sem o endereço exato (cliente da base, coordenada perturbada): só o nível do município, no máximo MEDIO.
        for id_, chave, nome in (("ALAGAMENTO", "agua_alto", "inundação ou enxurrada"), ("DESLIZAMENTO", "massa_alto", "deslizamento")):
            if municipio is None:
                perigos.append(_perigo(id_, "SEM_DADO", "setores do SGB não consultados", FONTES["sgb"]))
                continue
            n = municipio[chave]
            sufixo = "; o endereço exato não foi avaliado"
            if not mapeado:
                if id_ == "ALAGAMENTO" and chuva == "ALTO":
                    perigos.append(_perigo(id_, "MEDIO", f"município sem setorização do SGB; {texto_chuva}{sufixo}", FONTES["clima"]))
                else:
                    perigos.append(_perigo(id_, "SEM_DADO", f"município sem setorização do SGB{sufixo}", FONTES["sgb"]))
            elif n >= SETORES_MUNICIPIO_MEDIO:
                perigos.append(_perigo(id_, "MEDIO", f"o município tem {n} setores de risco alto de {nome} (SGB){sufixo}", FONTES["sgb"]))
            else:
                perigos.append(_perigo(id_, "BAIXO", f"o município tem {n} setor(es) de risco alto de {nome} (SGB){sufixo}", FONTES["sgb"]))

    # barragens (não coberto: o efeito do rompimento é inundação)
    if not preciso:
        perigos.append(_perigo("BARRAGEM", "SEM_DADO", "precisa do endereço exato (CEP)", FONTES["barragens"]))
    elif dados_barragens is None:
        perigos.append(_perigo("BARRAGEM", "SEM_DADO", "consulta de barragens indisponível", FONTES["barragens"]))
    else:
        rejeito = next((b for b in dados_barragens if b["rejeito"]), None)
        proxima = next((b for b in dados_barragens if b["distancia_m"] <= RAIO_BARRAGEM_PROXIMA_M), None)
        if rejeito:
            perigos.append(_perigo("BARRAGEM", "ALTO", f"barragem de rejeito {rejeito['nome'] or 'sem nome'} a {_num(rejeito['distancia_m'] / 1000)} km", FONTES["barragens"]))
        elif proxima:
            perigos.append(_perigo("BARRAGEM", "MEDIO", f"barragem {proxima['nome'] or 'sem nome'} a {_num(proxima['distancia_m'] / 1000)} km", FONTES["barragens"]))
        elif dados_barragens:
            b = dados_barragens[0]
            perigos.append(_perigo("BARRAGEM", "BAIXO", f"barragem mais próxima a {_num(b['distancia_m'] / 1000)} km", FONTES["barragens"]))
        else:
            perigos.append(_perigo("BARRAGEM", "BAIXO", "nenhuma barragem mapeada a menos de 10 km", FONTES["barragens"]))

    cobertos = [p.nivel for p in perigos if p.coberto]
    fator = min(FATOR_MAXIMO, 1 + sum(PESO_AGRAVAMENTO.get(n, 0) for n in cobertos))
    fontes_usadas = [local.fonte] + sorted({p.fonte for p in perigos if p.nivel != "SEM_DADO"})
    return RiscoLocal(
        local=local,
        perigos=perigos,
        agravamento="ALTO" if "ALTO" in cobertos else "MEDIO" if "MEDIO" in cobertos else "BAIXO",
        fator_agravamento=round(fator, 2),
        analise_de_aceitacao=any(p.nivel == "ALTO" and not p.coberto for p in perigos),
        fontes=list(dict.fromkeys(fontes_usadas)),
        falhas=falhas,
        consultado_em=date.today().isoformat(),
    )


# ---------- consulta completa ----------

ETAPAS = {
    "clima": "Clima de 10 anos (Open-Meteo)",
    "tempestades": "Trovoadas e granizo (Open-Meteo)",
    "relevo": "Relevo do entorno (Open-Meteo Elevation)",
    "sgb": "Setores de risco geológico (SGB)",
    "municipio": "Setores de risco do município (SGB)",
    "barragens": "Barragens num raio de 10 km (OpenStreetMap)",
}


def resumo_fonte(id_: str, valor) -> str:
    match id_:
        case "clima":
            return f"{_num(valor['chuva_forte_ano'])} dia/ano de chuva > {CHUVA_FORTE_MM} mm · {_num(valor['rajada_forte_ano'])} dia/ano de rajada ≥ {RAJADA_FORTE_KMH} km/h"
        case "tempestades":
            return f"{_num(valor['trovoada_ano'])} dia/ano com trovoada · {_num(valor['granizo_ano'])} com granizo"
        case "relevo":
            return f"altitude {_num(valor['altitude_m'], 0)} m · declividade {_num(valor['declividade_pct'], 0)}%"
        case "sgb":
            return f"{len(valor)} setor(es) a menos de 1,5 km" if valor else "nenhum setor a menos de 1,5 km"
        case "municipio":
            return "município sem setorização do SGB" if not valor["mapeado"] else f"{valor['massa_alto']} de deslizamento e {valor['agua_alto']} de inundação em risco alto"
        case "barragens":
            return f"{len(valor)} barragem(ns); a mais próxima a {_num(valor[0]['distancia_m'] / 1000)} km" if valor else "nenhuma"
    return ""


def analisar(local: Local, avisar: Callable[..., None] | None = None, usar_rede: bool = True) -> RiscoLocal:
    """Consulta as fontes em paralelo e avalia. avisar(id, titulo, detalhe, estado) acompanha cada fonte."""
    lat, lon = local.latitude, local.longitude
    tarefas: dict[str, Callable[[], object]] = {
        "clima": lambda: clima(lat, lon, usar_rede),
        "tempestades": lambda: tempestades(lat, lon, usar_rede),
        "municipio": lambda: setores_do_municipio(local.municipio, local.uf, usar_rede),
    }
    if local.precisao == "CEP":
        tarefas |= {
            "relevo": lambda: relevo(lat, lon, usar_rede),
            "sgb": lambda: setores_proximos(lat, lon, usar_rede),
            "barragens": lambda: barragens(lat, lon, usar_rede),
        }
    resultados: dict[str, object] = {}
    falhas: list[str] = []

    def rodar(id_: str):
        if avisar:
            avisar(f"geo_{id_}", ETAPAS[id_])
        try:
            resultados[id_] = tarefas[id_]()
            if avisar:
                avisar(f"geo_{id_}", ETAPAS[id_], resumo_fonte(id_, resultados[id_]), "feito")
        except Exception as erro:  # uma fonte fora do ar não derruba a conversa: o perigo fica SEM_DADO
            falhas.append(f"{ETAPAS[id_]}: {erro.__class__.__name__}")
            if avisar:
                avisar(f"geo_{id_}", f"{ETAPAS[id_]}: indisponível", "o perigo fica sem dado", "falhou")

    with ThreadPoolExecutor(max_workers=len(tarefas)) as executor:
        list(executor.map(rodar, tarefas))
    return avaliar(
        local,
        resultados.get("clima"),
        resultados.get("tempestades"),
        resultados.get("relevo"),
        resultados.get("sgb"),
        resultados.get("municipio"),
        resultados.get("barragens"),
        falhas,
    )


def analisar_cep(cep: str, avisar: Callable[..., None] | None = None, usar_rede: bool = True) -> RiscoLocal:
    if avisar:
        avisar("geo_cep", "Localizando o CEP (ViaCEP + OpenStreetMap)")
    local = localizar_cep(cep, usar_rede)
    if avisar:
        onde = ", ".join(x for x in (local.bairro, f"{local.municipio}/{local.uf}") if x)
        avisar("geo_cep", "CEP localizado", f"{onde} · precisão: {'rua/CEP' if local.precisao == 'CEP' else 'só o município'}", "feito")
    return analisar(local, avisar, usar_rede)


# ---------- clientes da base (pré-calculado por scripts/enriquecer_territorio.py) ----------

_base: dict | None = None


def risco_da_base(territorio_id: str) -> RiscoLocal | None:
    """Risco pré-calculado do território da base; None se o arquivo não existe ou não tem o território."""
    global _base
    if _base is None:
        try:
            _base = json.loads(ARQUIVO_BASE.read_text(encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            _base = {}
    dado = _base.get(territorio_id)
    return RiscoLocal(**dado) if dado else None
