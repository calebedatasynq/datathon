# Fontes territoriais (risco do local)

Enriquecimento externo opcional, como pede o LEIA-ME do desafio. Código: `agente/territorio.py`.
Consultado em out/2026. Nenhuma fonte exige chave.

| Perigo | Fonte | Granularidade | Limitação |
|---|---|---|---|
| Endereço do CEP | ViaCEP | CEP | só rua, bairro, município e código IBGE |
| Coordenada | Nominatim/OpenStreetMap (ODbL) | CEP ou rua; cai para o município | CEP sem ponto no OSM vira município |
| Vendaval | Open-Meteo Historical Weather (ERA5), 2016–2025 | grade de ~25 km | rajada diária; dias/ano ≥ 75 km/h |
| Granizo e raios | Open-Meteo Historical Forecast, 2023–2025 | grade de ~10 km | códigos de trovoada dos modelos, 3 anos; o ERA5 não traz esses códigos |
| Chuva forte | Open-Meteo ERA5 | ~25 km | dias/ano com ≥ 50 mm |
| Relevo | Open-Meteo Elevation (Copernicus DEM) | 90 m | declividade e baixada num raio de 250 m e 1 km |
| Deslizamento, inundação | SGB/CPRM, setores de risco geológico (WFS) | polígono do setor | muitas capitais (RJ, Salvador, Recife, BH) quase sem setorização: vira SEM_DADO, nunca "baixo" |
| Barragens | OpenStreetMap via Overpass, raio de 10 km | ponto | cadastro incompleto e Overpass lento (limite de 12 s); o SNISB/ANA está publicado como serviço ArcGIS mas retornou 0 registros em out/2026 |

## Níveis (premissas da equipe, calibradas com 10 cidades)
- Vendaval: ALTO ≥ 1,5 dia/ano de rajada ≥ 75 km/h; MEDIO ≥ 0,5.
- Granizo: ALTO ≥ 1,5 dia/ano; MEDIO ≥ 0,5. Raios (trovoada): ALTO ≥ 8; MEDIO ≥ 3.
- Alagamento e deslizamento: setor do SGB de risco alto a até 300 m = ALTO; setor a até 1,5 km = MEDIO; baixada com chuva forte, ou terreno com declividade ≥ 25%, = MEDIO.
- Barragem: de rejeito = ALTO; qualquer uma a até 3 km = MEDIO.
- Cliente da base (coordenada perturbada): só o município; os perigos locais ficam no máximo em MEDIO e barragem fica SEM_DADO.
- Fonte fora do ar: SEM_DADO, nunca BAIXO.

## Efeito no plano (e relação com as Condições Gerais)
- Cobertos: vendaval e granizo (VENDAVAL_EVENTOS_CORRELATOS-1.1; granizo em vidros: QUEBRA_DE_VIDROS-1.1.b); raios (DANOS_ELETRICOS-1.1). Nível alto torna a cobertura essencial e aumenta a faixa de limite sugerida.
- Não cobertos: alagamento/inundação (CG-8.1.l), desmoronamento (CG-8.1.o) e rompimento de barragem (efeito de inundação, CG-8.1.l). O agente avisa que não cobre e, se o nível é alto, marca a elegibilidade como "a confirmar" (aceitação sujeita à análise do risco, CG-13.3).
- O "agravamento" (BAIXO/MEDIO/ALTO e um fator indicativo) é só para a análise da seguradora. O agente nunca informa preço, percentual ou fator; pode dizer que o risco da região entra na análise e pode pesar no custo.
