# Fontes de dados

Os arquivos originais ficam em `raw/` e não são versionados. A coleta usa `uv run poe fetch_raw --range 2024 --effort medium` para um ano, `--range 2000-2003` para um intervalo inclusivo ou nenhum `--range` para selecionar todos os anos publicados. ONI e NOAA GlobalTemp são arquivos históricos cumulativos e são baixados inteiros quando o intervalo solicitado alcança sua cobertura. O download não é executado automaticamente.

| Fonte | Produto e formato | Cobertura encontrada nos catálogos |
|---|---|---|
| NOAA CPC | [ONI v6](https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/oni/v6/index.php), HTML cumulativo | Série histórica desde 1950 |
| Climate Hazards Center | [CHIRPS v3 mensal da América Latina](https://data.chc.ucsb.edu/products/CHIRPS/v3.0/monthly/latam/bils/), grade BIL em TAR.GZ | Janeiro de 1981 a setembro de 2026 |
| INPE | [Focos do satélite de referência](https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/anual/Brasil_sat_ref/), CSV em ZIP anual | 2003 a 2025 |
| INMET | [Histórico de estações automáticas](https://portal.inmet.gov.br/dadoshistoricos), CSVs em ZIP anual | 2000 a 2026 |
| NOAA NCEI | [GHCN-Daily](https://www.ncei.noaa.gov/pub/data/ghcn/daily/by_year/), CSV.GZ anual | 1763 a 2026 |
| NOAA NCEI | [ICOADS diário](https://www.ncei.noaa.gov/data/international-comprehensive-ocean-atmosphere/v3/archive/nrt/daily/), NetCDF | 2015 a 2026, conforme arquivos disponíveis |
| NOAA NCEI | [NOAA GlobalTemp v6.1](https://www.ncei.noaa.gov/data/noaa-global-surface-temperature/v6.1/access/gridded/), NetCDF cumulativo | Série histórica desde 1850 |
| ONS | [Balanço de energia por subsistema](https://dados.ons.org.br/dataset/balanco-energia-subsistema), Parquet anual | 2000 a 2026 |
| ONS | [Energia armazenada por subsistema](https://dados.ons.org.br/dataset/ear-diario-por-subsistema), Parquet anual | 2000 a 2026 |

## Piloto de 2024 e estimativa

O piloto foi coletado com o antigo script exclusivo de 2024. O mesmo recorte anual agora pode ser solicitado com `fetch_raw --range 2024`. Ele seleciona os 12 meses CHIRPS, os arquivos anuais de INPE, INMET, GHCN-Daily e dos dois produtos ONS, além dos arquivos diários NetCDF disponíveis do ICOADS e das séries cumulativas ONI e NOAA GlobalTemp.

O piloto inicial registrou 378 arquivos e 1,85 GB, sem falhas. A coleta com `--range 2024` acrescentou os arquivos cumulativos ONI e GlobalTemp, totalizando 380 arquivos e 1,87 GB. Os manifestos registram tamanho e SHA-256 de cada arquivo; a conferência local não encontrou divergências. Os 361 NetCDF do ICOADS somam 1,52 GB. A descoberta usa o [índice oficial de arquivos da NOAA](https://www.ncei.noaa.gov/data/international-comprehensive-ocean-atmosphere/v3/archive/nrt/daily/). O índice não oferece NetCDF para 01/03 e 18 a 21/12/2024; em 18 e 19/12 há arquivos `.dat.gz`, que não entram nesta conversão. Os 361 NetCDF cobrem os demais dias do ano bissexto. Os totais medidos no piloto estão em `fetch_raw_data.py`, que não depende do manifesto local para estimar o volume. O tamanho real pode variar entre anos.

Uma consulta aos catálogos sem restrição de anos encontrou cerca de 19,34 GB de ICOADS e 14,47 GB de GHCN-Daily em arquivos brutos. O intervalo permite escolher o volume que será baixado.

## Entrega SQL

O destino escolhido é `raw.duckdb`, criado por `uv run poe ingest_raw`. Há uma tabela por fonte disponível em `raw/`, com `_arquivo_origem` para rastrear o arquivo de entrada. As colunas dos CSVs são guardadas como texto; Parquet e NetCDF preservam os tipos numéricos da fonte. CHIRPS gera uma linha por célula da grade, com a posição e a precipitação. Normalização, padronização, agregações e cruzamentos analíticos pertencem às etapas seguintes.

A carga inicial dos 378 arquivos de 2024 gerou 141.832.427 linhas. Após acrescentar as séries cumulativas ONI e GlobalTemp, o banco passou a ter nove tabelas, 147.330.136 linhas e 4,63 GB. São 39.216.000 células CHIRPS, 38.470.116 observações GHCN-Daily, 58.859.668 observações ICOADS, 4.962.960 leituras INMET, 278.299 focos INPE, 43.920 linhas do balanço ONS, 1.464 da energia armazenada ONS, 77 anos de ONI e 5.497.632 células GlobalTemp. O ONI inclui os valores disponíveis do ano ainda incompleto. A tabela CHIRPS de 2024 ocupou cerca de 417 MB em blocos do DuckDB; aplicada aos 549 meses então disponíveis, essa medida indica aproximadamente 19 GB para essa tabela, dependendo da compressão dos demais anos.
