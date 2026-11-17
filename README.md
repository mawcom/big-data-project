# El Niño, chuvas e queimadas no Nordeste

Trabalho de faculdade que investiga como episódios de El Niño se relacionam com a chuva e os focos de fogo detectados no Nordeste brasileiro. A análise compara as séries ao longo do tempo e por estado, considerando a sazonalidade e os limites dos dados observacionais. O projeto terá coleta reproduzível em Python, dados preparados para análise e um dashboard interativo.

O conceito, as perguntas de pesquisa, as fontes e o recorte estão em [docs/conceito.md](docs/conceito.md). O [plano de trabalho original](docs/plano-de-trabalho.pdf) registra a proposta anterior, mais ampla.

> **Estado atual:** há tabelas reais de ONI, CHIRPS e focos INPE para **2023, 2024 e 2025** em `amostras/`. O episódio de El Niño aparece de maio de 2023 a abril de 2024 pelo critério ONI adotado. A página `/piloto-real` descobre os anos processados e exibe a referência sazonal exploratória para o ano seguinte ao último observado. A página inicial em `dashboard/prototipo/` ainda usa dados **simulados** e uma pequena amostra real de chuva de Porto Alegre.

## Recorte de dados

- Período comparável de chuva e fogo: 2003–2025.
- Chuva: CHIRPS v3 mensal, 1991–2025, para calcular anomalias usando a climatologia 1991–2020.
- Fogo: focos do satélite de referência publicados pelo INPE, 2003–2025.
- ENSO: índice ONI mensal/semanal sazonal histórico da NOAA CPC.
- Estações meteorológicas: histórico horário do INMET para chuva e temperatura.
- Energia: dados do ONS por subsistema.
- Dados brutos e derivados não entram no Git.

O papel de coleta está atribuído a **@Asageki**.

## Estrutura do repositório

```text
raw/                  dados brutos, como baixados (fora do Git)
clean/                dados limpos e padronizados (fora do Git)
parquet/              dados em Parquet, particionados por ano (fora do Git)
amostras/             arquivos pequenos versionados, para testar sem baixar tudo
notebooks/            análises e notebooks
src/
  ingestao/           scripts de coleta (download das bases)
  limpeza/            limpeza, padronização e integração (ETL)
  bigdata/            Parquet, PySpark/Dask e benchmark
  analise/            código de apoio às análises estatísticas
dashboard/
  prototipo/          protótipo anterior (dados simulados), mantido como referência
docs/
  plano-de-trabalho.pdf
  legado/             documentos da fase de protótipo
pyproject.toml        dependências Python e tarefas Poe
uv.lock               versões resolvidas pelo uv
```

## Como rodar

Requer Python 3.10 ou mais recente, [uv](https://docs.astral.sh/uv/getting-started/installation/) e um JDK compatível para os jobs Spark. Na pasta do projeto:

```bash
uv sync
uv run poe --help
```

As dependências ficam em `pyproject.toml`; `uv.lock` fixa as versões para reproduzir o ambiente. O `uv sync` cria ou atualiza `.venv`, e os comandos `uv run poe` usam esse ambiente sem ativação manual.

| Tarefa | Comando | Finalidade |
|---|---|---|
| `fetch_raw` | `uv run poe fetch_raw --range 2024 --effort medium` | Baixar as bases selecionadas para um ano ou intervalo. Sem `--range`, seleciona todos os anos disponíveis nos catálogos. |
| `fetch_uf_geometry` | `uv run poe fetch_uf_geometry` | Baixar a malha simplificada das nove UFs pela API do IBGE. |
| `process_pilot` | `uv run poe process_pilot --ano 2024` | Validar os arquivos reais e produzir tabelas mensais e relatório de qualidade em `amostras/piloto_2024/`. |
| `project_2026` | `uv run poe project_2026` | Calcular a referência sazonal de 2026, a faixa de variação e o erro da comparação de 2024 para 2025. |
| `sync_data` | `uv run poe sync_data` | Detectar anos completos em `raw/`, processar apenas os novos ou alterados e atualizar a projeção. O painel também executa essa sincronização ao abrir. |
| `project_next` | `uv run poe project_next` | Refazer manualmente a projeção do ano posterior à última base observada. |
| `ingest_raw` | `uv run poe ingest_raw` | Converter os arquivos presentes em `raw/` em tabelas DuckDB. |
| `export_landing` | `uv run poe export_landing` | Exportar ONI, CHIRPS e INPE do DuckDB para Parquet de landing; aceita CSV apenas para baseline. |
| `build_chirps_lookup` | `uv run poe build_chirps_lookup -- --uf-geojson CAMINHO` | Criar o mapa auditável de células CHIRPS para UFs do Nordeste. |
| `silver_oni` | `uv run poe silver_oni` | Normalizar ONI e classificar a fase ENSO. |
| `silver_chirps` | `uv run poe silver_chirps` | Agregar chuva CHIRPS por UF com lookup espacial auditado. |
| `silver_inpe` | `uv run poe silver_inpe` | Agregar focos INPE por UF/mês. |
| `build_gold` | `uv run poe build_gold` | Produzir a tabela mensal para o front e o resumo regional. |
| `export_dashboard` | `uv run poe export_dashboard` | Gerar JSON leve em `dashboard/data/`. |
| `benchmark` | `uv run poe benchmark -- --csv ARQUIVO` | Comparar CSV/pandas, Parquet/pandas e Parquet/PySpark na mesma agregação CHIRPS. |

O esforço `low` usa 2 threads e blocos de 256 KiB; `medium`, 6 threads e blocos de 1 MiB; `high`, 12 threads e blocos de 4 MiB. O padrão é `medium`. `--range` aceita um ano (`2024`) ou intervalo inclusivo (`2000-2003`). `--sources` limita a coleta às bases necessárias; para o MVP do painel use `--sources oni chirps inpe`. ONI e NOAA GlobalTemp têm arquivos históricos cumulativos: quando o intervalo alcança sua cobertura, o arquivo inteiro é baixado. Sem `--range`, o comando seleciona todos os anos publicados pelas fontes selecionadas. O `fetch_raw` mostra os anos selecionados e a estimativa por fonte com base no piloto de 2024, quando disponível. Ao terminar, informa o volume e grava `raw/manifesto_coleta.json` com as fontes solicitadas.

Para medir o volume do MVP de um ano antes de completar a coleta, use `uv run poe fetch_raw --range 2024 --sources oni chirps inpe --effort low`. Execute os downloads somente após decidir usar espaço e rede para a coleta.

Para reproduzir as bases de **2023–2025**, rode `uv run poe fetch_raw --range 2023-2025 --sources oni chirps inpe --effort low`, `uv run poe fetch_uf_geometry` e `uv run poe sync_data`. Essa rota usa pandas e NumPy; o [guia da frente de processamento](docs/guia-processamento-dados.md) descreve os métodos, resultados observados e como ampliar para a série histórica.

**Quando um ano novo estiver publicado**, rode apenas `uv run poe fetch_raw --range ANO --sources oni chirps inpe --effort low` e atualize `/piloto-real`. A coleta renova o HTML cumulativo do ONI a cada execução; os arquivos anuais já baixados são reaproveitados. O servidor detecta os arquivos completos, processa o ano, preserva os anteriores e calcula a próxima referência sazonal. Uma base incompleta fica pendente; o painel informa quantos arquivos faltam. Para copiar arquivos manualmente, use os mesmos nomes e pastas em `raw/`; o pipeline registra os hashes locais e marca entradas sem manifesto.

O `ingest_raw` recria `raw.duckdb` na raiz do projeto, sem acumular linhas de execuções anteriores, e interrompe a carga se encontrar arquivos brutos idênticos em caminhos diferentes. Para NOAA GlobalTemp, carrega apenas o arquivo cumulativo mais recente se houver várias versões locais. As tabelas são `oni`, `chirps`, `inpe`, `inmet`, `ghcn_daily`, `icoads`, `noaa_globaltemp`, `ons_balanco` e `ons_ear`, conforme os arquivos presentes. Cada tabela inclui `_arquivo_origem`; as colunas dos CSVs mantêm o texto de entrada, e os formatos numéricos mantêm seus valores. Para o CHIRPS, cada célula da grade vira uma linha com `linha`, `coluna`, `latitude`, `longitude` e `precipitacao`. O script informa a quantidade de linhas e o tamanho do banco ao terminar. Registros iguais presentes em arquivos diferentes continuam como dados de origem; sua avaliação cabe à etapa de análise e padronização.

O protótipo do painel pode ser aberto diretamente com `uv run python dashboard/prototipo/app.py` em <http://127.0.0.1:8000>. Para outra porta, acrescente `--port 8080`. Para encerrar, use `Ctrl+C`.

Depois de iniciar o servidor, abra <http://127.0.0.1:8000/piloto-real> para ver os anos reais disponíveis por estado e mês, com mapa das UFs, gráficos de ONI, chuva e focos INPE, além da referência sazonal exploratória. A página inicial continua identificada como protótipo com simulação.

### Com Docker

```bash
docker compose up --build                          # painel em http://localhost:8000/piloto-real
docker compose run --rm app uv run poe sync_data   # qualquer tarefa da tabela acima
```

## Frentes de trabalho

Cada frente é dona de uma etapa do pipeline e entrega algo que a próxima usa.

| Frente | Pasta | Entrega | Depende de | Responsável (GitHub) |
|---|---|---|---|---|
| 1. Coleta de dados | `src/ingestao/`, `raw/` | `raw/` completa e documento de fontes | — | @Asageki |
| 2. Limpeza e integração (ETL) | `src/limpeza/`, `clean/` | `clean/` e a tabela cruzada | frente 1 | a preencher |
| 3. Engenharia de big data | `src/bigdata/`, `parquet/` | `parquet/`, código do pipeline e benchmark | frentes 1 e 2 (começa com amostra) | a preencher |
| 4. Análise estatística | `notebooks/`, `src/analise/` | notebook de análise e tabela de achados | frente 2 | a preencher |
| 5. Dashboard | `dashboard/` | dashboard funcionando | frentes 2 e 4 (começa com dados parciais) | a preencher |
| 6. Conclusões e apresentação | `docs/` | relatório, slides e roteiro | todas (começa cedo, com o esqueleto) | a preencher |

## Documentação

- [Conceito e fontes dos dados](docs/conceito.md)
- [Fontes escolhidas e estado da coleta](docs/fontes.md)
- [Contrato de dados e plano de ingestão para o dashboard](docs/contrato-dados-dashboard.md)
- [Guia de execução e roteiro de apresentação](docs/guia-execucao-apresentacao.md)
- [Guia da frente de processamento de dados](docs/guia-processamento-dados.md)
- [Plano de trabalho](docs/plano-de-trabalho.pdf)
- [Documentos da fase de protótipo](docs/legado/README.md)
