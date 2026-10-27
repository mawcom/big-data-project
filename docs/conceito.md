# Conceito do projeto

## Tema

Investigar como episódios de El Niño se relacionam com as chuvas e os focos de fogo detectados no Nordeste brasileiro. O Nordeste é diverso em clima, vegetação e sazonalidade; os resultados serão comparados ao longo do tempo e entre os estados, sem tratar associação estatística como causalidade.

## Pergunta principal

Como a intensidade do El Niño se relaciona com a precipitação e com os focos de fogo detectados em cada estado do Nordeste, e como essas relações variam conforme o mês e o ano?

## Perguntas de pesquisa

1. Meses e episódios de El Niño coincidem com mudanças na chuva do Nordeste, no conjunto e por estado?
2. Meses mais secos coincidem com aumento de focos de fogo detectados, e essa relação varia entre os estados?
3. Há defasagem entre as variações do ONI, da chuva e dos focos de fogo?
4. As relações mudam entre as fases El Niño, La Niña e neutra?

## Escopo temporal e espacial

- Recorte comparável de chuva e fogo: janeiro de 2003 a dezembro de 2025.
- Série mensal completa CHIRPS disponível no repositório: janeiro de 1981 a setembro de 2026; referência para anomalias: climatologia de 1991 a 2020.
- Área: os nove estados da Região Nordeste do Brasil.
- Resolução analítica inicial: mês e estado; agregações regionais também serão produzidas.

O acervo do INPE para o satélite de referência começa em 2003 nesta série anual. A chuva anterior a 2003 entra apenas na climatologia de referência. A série ONI é mantida em sua escala original; a classificação de episódios seguirá a regra do CPC documentada junto ao dado.

## Bases selecionadas

| Base | Fonte e produto | Período | Uso |
|---|---|---:|---|
| ENSO | [NOAA CPC — ONI v6](https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/oni/v6/index.php) | Série histórica publicada pela NOAA | Intensidade e fase do El Niño–Oscilação Sul |
| Precipitação | [CHIRPS v3 mensal, América Latina](https://data.chc.ucsb.edu/products/CHIRPS/v3.0/monthly/latam/bils/) | 1981–set. 2026 | Acumulados mensais e anomalias de chuva no Nordeste |
| Focos de fogo | [INPE Programa Queimadas — satélite de referência](https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/anual/Brasil_sat_ref/) | 2003–2025 | Contagem de focos por estado e mês |
| Estações meteorológicas | [INMET — dados históricos anuais](https://portal.inmet.gov.br/dadoshistoricos) | Arquivos disponíveis desde 2000; recorte comparável 2003–2025 | Chuva e temperatura observadas por estação |
| Energia | [ONS — Balanço de Energia nos Subsistemas](https://dados.ons.org.br/dataset/balanco-energia-subsistema) e [EAR Diário por Subsistema](https://dados.ons.org.br/dataset/ear-diario-por-subsistema) | Séries históricas disponíveis desde 2000; recorte comparável 2003–2025 | Geração e energia armazenada no subsistema Nordeste |

O CHIRPS v3 é um produto mensal de precipitação em grade de 0,05° que combina estimativas de satélite e dados de estações. Os arquivos baixados cobrem a América Latina e serão recortados para o Nordeste no processamento. Os focos do INPE são detecções orbitais de fogo ativo; não equivalem diretamente à área queimada nem a uma contagem perfeita de incêndios. Mudanças de sensor e cobertura também limitam comparações longas.

## Volume e armazenamento

O comando `fetch_raw` baixa as fontes escolhidas em `raw/`, com o intervalo de anos definido por `--range` ou toda a cobertura disponível quando o parâmetro é omitido. As fontes incluem CHIRPS mensal da América Latina, focos anuais do INPE, ONI, INMET, ONS e os produtos globais descritos em [fontes.md](fontes.md). Os arquivos baixados permanecem em `raw/`. O comando `ingest_raw` cria tabelas DuckDB com os registros de origem; recortes e agregações analíticas pertencem às etapas seguintes.

Para coletar ou completar arquivos ausentes:

```powershell
uv run poe fetch_raw --effort medium
```

O comando salva um manifesto em `raw/manifesto_coleta.json` com URLs, tamanhos, hashes e horários de coleta. `raw/`, `clean/` e `parquet/` são ignorados pelo Git.

## Responsabilidade

**Coleta de dados: @Asageki.** A entrega inclui as bases brutas, manifestos, tabelas consultáveis no DuckDB e documentação de fontes, períodos, unidades e limitações.

## Limites de interpretação

- Correlação entre El Niño, precipitação e focos de fogo não demonstra causalidade.
- Chuva e fogo têm sazonalidades diferentes; comparar meses equivalentes e explicitar defasagens é essencial.
- Focos ativos são observações por satélite e não representam por si só área queimada, duração ou severidade.
- CHIRPS é uma estimativa em grade, não uma medição direta em cada município ou estação.
- A análise deve informar cobertura, dados ausentes, definição de episódio ENSO e período de referência usado para cada anomalia.
