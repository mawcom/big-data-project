# Contrato de dados e plano de ingestão para o dashboard

## Objetivo

Este documento define a entrega da frente de ingestão para o dashboard sobre a relação entre ENOS (El Niño/La Niña), chuva e focos de fogo. Ele transforma as fontes brutas em tabelas rastreáveis, particionadas e prontas para consumo pelo front-end.

O recorte analítico já documentado no repositório é **Nordeste, por UF e mês, de 2003 a 2025**. O Maranhão deve ser a UF de validação obrigatória e pode ser o destaque inicial da interface. Caso a decisão do grupo seja restringir o estudo apenas ao Maranhão, ela deve ser registrada antes de executar a carga completa: não se deve apresentar o dashboard como "Brasil" enquanto os dados cobrirem somente o Nordeste.

## Situação de partida

| Camada | Situação | Observação |
|---|---|---|
| Coleta bruta | Parcialmente implementada | `fetch_raw_data.py` descobre e baixa fontes, valida formatos e grava manifesto com hash SHA-256. |
| Landing local | Implementada | `ingest_raw_to_sql.py` recria `raw.duckdb` com uma tabela por fonte e `_arquivo_origem`. |
| Limpeza e integração | Não implementada | `src/limpeza/` ainda está vazio. |
| Parquet e Spark | Implementados, aguardando dados/JDK | Jobs Spark criam lookup espacial, Silver e Gold; `pyspark` e `pyarrow` estão travados no ambiente. |
| Camada para dashboard | Implementada, sem dados reais publicados | O exportador produz JSON pequeno e metadados a partir da Gold. |
| Dashboard existente | Apenas protótipo | O painel usa séries simuladas; a pequena amostra de Porto Alegre não pertence ao recorte do estudo. |

Assim, `raw.duckdb` é uma camada de inspeção e auditoria, não a fonte que o front-end deve consultar.

## Escopo da primeira entrega utilizável

Para responder à pergunta principal com dados reais, a primeira versão deve priorizar somente as fontes indispensáveis:

| Domínio | Fonte bruta | Saída mensal esperada | Papel no painel |
|---|---|---|---|
| ENOS | ONI/CPC | valor ONI e fase ENOS por mês | filtro, faixas temporais e contexto climático |
| Chuva | CHIRPS v3 mensal | precipitação, climatologia e anomalia por UF | mapa, série temporal e comparação entre UFs |
| Fogo | INPE, satélite de referência | quantidade de focos por UF | série temporal e comparação com chuva/ENOS |
| Validação complementar | INMET | indicadores por estação, separados da grade CHIRPS | controle de qualidade; não substituir CHIRPS sem regra documentada |
| Contexto opcional | ONS | indicadores mensais do subsistema Nordeste | página de energia, quando a pergunta correspondente for mantida |

GHCN-Daily, ICOADS e NOAA GlobalTemp já podem ser coletados pelo script, mas não são necessários para a primeira tabela do dashboard. Eles aumentam muito o volume e devem ficar fora do MVP até haver uma pergunta, uma métrica e uma visualização aprovadas para eles.

## Arquitetura de dados proposta

```text
Fontes oficiais
      |
      v
raw/ (Bronze, arquivo original + manifesto SHA-256)
      |
      v
raw.duckdb (landing para auditoria e exploração local)
      |
      v
Spark / Silver: tipagem, qualidade, datas, UF e recorte espacial
      |
      v
Parquet / Gold: fatos mensais por UF e agregados do Nordeste
      |
      v
API ou arquivos de publicação do dashboard
```

### Convenções de armazenamento

- `raw/`: imutável, fora do Git. Cada execução atualiza `raw/manifesto_coleta.json` com URL, tamanho, hash, estado e horário de coleta.
- `clean/silver/`: Parquet limpo por fonte, por exemplo `clean/silver/chirps/ano=2024/` e `clean/silver/inpe/ano=2024/`.
- `parquet/gold/`: produtos prontos para leitura analítica, por exemplo `parquet/gold/fato_mensal_uf/ano=2024/` e `parquet/gold/resumo_mensal_nordeste/ano=2024/`.
- Dados e artefatos de execução não são versionados. O código, o esquema, os testes, o manifesto de exemplo sem dados e os resultados do benchmark são versionados.

O particionamento por `ano` é o padrão inicial. Não particionar por UF: são somente nove valores e isso criaria arquivos pequenos demais. Para o front-end, produzir arquivos consolidados pequenos ou uma API de agregados evita que o navegador leia todo o conjunto Parquet.

## Modelo Gold: contrato do front-end

### Dimensões

`dim_tempo_enso`

| Campo | Tipo | Regra |
|---|---|---|
| `competencia` | date | primeiro dia do mês, no formato `YYYY-MM-01` |
| `ano`, `mes` | int | derivados de `competencia` |
| `oni` | decimal | valor publicado pelo CPC, sem reescala |
| `fase_enso` | string | `el_nino`, `la_nina`, `neutro` ou `indisponivel` |
| `janela_oni` | string | janela sazonal original publicada pelo ONI |

A regra de fase deve seguir a regra do CPC adotada pelo grupo: limiar de +0,5 ou -0,5 sustentado por cinco janelas sobrepostas. Como o ONI é sazonal, a transformação para mês precisa preservar `janela_oni` e ser documentada; não rotular simplesmente cada valor isolado como episódio.

`dim_uf`

| Campo | Tipo | Regra |
|---|---|---|
| `uf_codigo_ibge` | string | chave canônica de UF, sem conversão para número no front-end |
| `uf_sigla`, `uf_nome` | string | nome e sigla oficiais padronizados |
| `regiao` | string | `Nordeste` para este recorte |
| `destaque_maranhao` | boolean | verdadeiro somente para a UF MA; serve à interface, não altera o dado |

### Fato mensal por UF

`fato_mensal_uf` é a fonte mínima para a maior parte das visualizações.

| Campo | Tipo | Definição |
|---|---|---|
| `competencia`, `uf_codigo_ibge` | chave | junção com as duas dimensões |
| `precipitacao_mm` | decimal | soma/agregado CHIRPS no mês e UF |
| `climatologia_mm_1991_2020` | decimal | média do mesmo mês na base de referência |
| `anomalia_chuva_mm` | decimal | `precipitacao_mm - climatologia_mm_1991_2020` |
| `anomalia_chuva_pct` | decimal | percentual calculado somente quando a climatologia for maior que zero |
| `focos_inpe` | long | contagem de focos do satélite de referência |
| `celulas_chirps_validas` | long | cobertura usada no agregado; permite expor qualidade |
| `estacoes_inmet_validas` | int | quantidade de estações válidas, quando disponível |
| `qualidade_chuva`, `qualidade_fogo` | string | `ok`, `parcial`, `ausente` ou `revisar` |
| `fonte_chuva`, `fonte_fogo`, `versao_pipeline` | string | rastreabilidade exibível no rodapé do painel |
| `atualizado_em_utc` | timestamp | data/hora da execução Gold |

`resumo_mensal_nordeste` deriva da mesma tabela e tem a mesma semântica, agregada para a região. Nenhum valor do dashboard pode ser chamado de observado se `qualidade_*` for `ausente` ou se `data_status` não for `real`.

## Transformações obrigatórias

1. **Validar a coleta.** Ler o manifesto, confirmar hash, tamanho maior que zero e cobertura esperada antes de processar cada fonte.
2. **Padronizar tempo.** Converter todas as fontes ao mês civil e salvar `competencia` como data. Não fazer join por texto de mês/ano.
3. **Padronizar território.** Usar chave IBGE de UF. Para o CHIRPS, recortar a grade pelo limite das UFs, e não apenas por uma caixa delimitadora; registrar células e peso/área utilizados.
4. **Tipar e validar valores.** Nulos, duplicatas, datas inválidas, precipitação negativa, coordenadas fora do domínio e focos sem UF devem gerar métricas de qualidade e não ser silenciosamente descartados.
5. **Calcular climatologia e anomalia.** Para cada UF e mês, usar 1991--2020 como referência, manter tanto o acumulado quanto a anomalia e registrar meses faltantes no período-base.
6. **Agregar fogo.** Manter somente a semântica de focos detectados pelo satélite de referência; não chamar a métrica de área queimada ou número de incêndios.
7. **Juntar no Gold.** Fazer `dim_tempo_enso` + `dim_uf` + fatos mensais, sem preencher artificialmente medidas ausentes. A ausência deve permanecer visível ao dashboard.

## Implementação Spark

Os jobs abaixo estão em `src/bigdata/`. A execução requer JDK compatível e os insumos declarados no guia de execução.

| Job | Entrada | Saída | Responsabilidade |
|---|---|---|---|
| `export_landing.py` | `raw.duckdb` | `clean/landing/` | expor ONI, CHIRPS e INPE em Parquet sem alterar a origem |
| `build_chirps_lookup.py` | CHIRPS landing + GeoJSON oficial | `clean/referencias/` | associar células à UF por polígono, sem caixa delimitadora |
| `silver_oni.py`, `silver_chirps.py`, `silver_inpe.py` | landing + lookup | `clean/silver/` | normalizar cada domínio para mês/UF |
| `build_gold.py` | Silver + dimensões | `parquet/gold/` | criar fatos de consumo e resumo regional |
| `export_dashboard.py` | Gold | `dashboard/data/` ou API | materializar somente os campos e agregações solicitados pelo front |
| `benchmark.py` | CHIRPS landing + lookup | `docs/benchmark_resultados.csv` | comparar CSV/pandas, Parquet/pandas e Parquet/PySpark |

O ganho de Big Data deve aparecer onde há volume: leitura/recorte das grades CHIRPS e agregações por UF/mês. A tabela Gold final é pequena; usar Spark nela apenas para demonstrar a cadeia reprodutível não é, por si só, justificativa de desempenho.

O benchmark usa a mesma agregação CHIRPS por UF em três leituras: CSV/pandas, Parquet/pandas e Parquet/PySpark. Ele registra volume lido, número de linhas e tempo de parede; memória e configuração da máquina devem ser anotadas junto ao resultado antes da apresentação.

## Contrato de publicação para o front-end

Antes de substituir o protótipo, o time de front deve receber uma amostra Gold real, pequena e versionada, com o mesmo esquema da produção. A interface deve consumir uma destas opções, escolhida pelo grupo:

1. **API de agregados (preferida):** `GET /api/serie?uf=MA&inicio=2003-01&fim=2025-12` e `GET /api/resumo?ano=2024`, com resposta JSON e metadados de cobertura.
2. **Exportação estática:** JSON/CSV compacto gerado por `export_dashboard.py`, com um `metadata.json` que declara período, fontes, data de atualização e versão do pipeline.

O contrato não deve expor `raw.duckdb`, arquivos brutos ou resultados simulados como se fossem a base final. Enquanto o protótipo existir, seu selo de dado simulado deve permanecer visível.

## Critérios de aceite da entrega de ingestão

- Execução reproduzível a partir de um comando documentado e de uma faixa temporal explícita.
- Manifesto de coleta com URL, hash, tamanho, horário e falhas por arquivo.
- Parquet Silver e Gold particionados por ano, com esquema documentado.
- Cobertura de 2003--2025 ou lista explícita de competências ausentes, incluindo Maranhão.
- Validações automatizadas para chaves, cobertura, tipos, valores inválidos e duplicidade.
- Amostra Gold real e `metadata.json` para o front-end.
- Dashboard sem dados simulados na rota de produção e com fonte/período/limitações visíveis.
- Benchmark reproduzível de pandas versus Parquet versus PySpark.

## Decisões que o grupo precisa fechar

1. O produto final cobre os nove estados do Nordeste com Maranhão em destaque ou somente o Maranhão? A documentação atual diz Nordeste; o pedido do projeto menciona Brasil/Maranhão.
2. O dashboard mantém apenas chuva e focos (MVP) ou também energia, agricultura, saúde e desastres? O plano em PDF é mais amplo que o escopo ativo do repositório.
3. Qual forma de publicação o front-end terá: API ou exportação estática? A escolha define o formato final de `export_dashboard.py`.
4. Qual ambiente executará Spark (local, laboratório, Databricks ou outro)? Isso define Java, memória, paralelismo e instruções de execução.

## Referências internas

- `README.md`: objetivo atual, comandos existentes, estrutura e frentes.
- `docs/conceito.md`: perguntas, período comparável e limites de interpretação.
- `docs/fontes.md`: catálogos, volumes do piloto e modelo DuckDB de landing.
- `docs/plano-de-trabalho.pdf`: requisito de Parquet, PySpark/Dask, benchmark e visualizações.
