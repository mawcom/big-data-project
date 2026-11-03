# Guia de execução e roteiro de apresentação

## O que demonstrar

O projeto mostra uma cadeia completa e auditável, sem apresentar valores simulados como resultados:

```text
fontes oficiais -> manifesto + raw -> DuckDB -> Parquet/Spark -> Gold -> JSON do dashboard
```

A apresentação deve destacar o Maranhão em filtros e exemplos, mantendo os nove estados do Nordeste como escopo comparativo enquanto o grupo não decidir reduzir o estudo.

## Pré-requisitos

- Python 3.10 ou superior e `uv`;
- JDK compatível com a versão instalada do Spark, disponível no `PATH` (`java -version` deve funcionar);
- espaço em disco definido antes da coleta;
- `clean/referencias/chirps_celula_uf/` em Parquet, gerado a partir de limites oficiais de UF. Esse lookup precisa ter `latitude`, `longitude`, `uf_codigo_ibge` e, de preferência, `peso_area`.

O lookup espacial é obrigatório porque evita associar uma célula à UF por uma simples caixa delimitadora. O método usado para gerá-lo, o CRS, a origem dos limites e a regra de peso devem ficar registrados no relatório.

## Ensaio curto: dados de um ano

Use o comando abaixo primeiro: ele limita a coleta ao MVP e permite revisar volume, manifesto e formato antes de baixar toda a série.

```powershell
uv run poe fetch_raw --range 2024 --sources oni chirps inpe --effort low
uv run poe ingest_raw
uv run poe export_landing
uv run poe build_chirps_lookup -- --uf-geojson raw/referencias/ufs_ibge.geojson
uv run poe silver_oni
uv run poe silver_chirps
uv run poe silver_inpe
uv run poe build_gold --inicio 2024-01 --fim 2024-12
uv run poe export_dashboard --inicio 2024-01 --fim 2024-12
```

Esse ensaio valida o fluxo. Ele não produz a climatologia completa de 1991--2020; por isso a qualidade da anomalia aparecerá como `parcial`, o que é o comportamento esperado e deve ser explicado.

## Execução para a série analítica

Para calcular anomalias comparáveis de 2003--2025, a coleta de CHIRPS precisa incluir o período-base de 1991--2020. O INPE só existe para o recorte comparável iniciado em 2003.

```powershell
uv run poe fetch_raw --range 1991-2025 --sources oni chirps inpe --effort medium
uv run poe ingest_raw
uv run poe export_landing
uv run poe build_chirps_lookup -- --uf-geojson raw/referencias/ufs_ibge.geojson
uv run poe silver_oni
uv run poe silver_chirps
uv run poe silver_inpe
uv run poe build_gold --inicio 2003-01 --fim 2025-12
uv run poe export_dashboard --inicio 2003-01 --fim 2025-12
uv run poe export_landing -- --tables chirps --format csv --output clean/benchmark
uv run poe benchmark -- --csv clean/benchmark/chirps/part-00000.csv
```

O exportador grava `metadata.json`, `fato_mensal_uf.json` e `resumo_mensal_nordeste.json` em `dashboard/data/`. São derivados ignorados pelo Git; o front deve exibir período, fonte e campos de qualidade que vêm nesses arquivos.

## Roteiro de 3 minutos para a frente de dados

1. **Problema (20 s).** “Não usamos o dado bruto diretamente no painel: ele é grande, heterogêneo e precisa de rastreabilidade.”
2. **Ingestão (40 s).** Mostrar `raw/manifesto_coleta.json`: URL, hash, tamanho, horário e fontes selecionadas.
3. **Big Data (60 s).** Explicar que Spark lê Parquet e agrega a grade CHIRPS para UF/mês usando o lookup espacial auditado. Mostrar uma partição `parquet/gold/fato_mensal_uf/ano=2024/`.
4. **Contrato com o front (35 s).** Abrir `dashboard/data/metadata.json` e apontar `qualidade_chuva`, `qualidade_fogo`, fontes e recorte. O front recebe JSON pequeno, não o banco bruto.
5. **Evidência de engenharia (25 s).** Mostrar `docs/benchmark_resultados.csv`: mesma agregação executada por pandas e PySpark; comparar tempo, volume e linhas de saída.

## Checklist antes de mostrar

- Confirmar que o dashboard não está consumindo `demo_data.py` na rota apresentada.
- Filtrar Maranhão e uma segunda UF para mostrar a comparação regional.
- Conferir que todo gráfico exibe fonte, período e estado de qualidade.
- Explicar que foco detectado não é área queimada e correlação não prova causalidade.
- Levar uma gravação curta ou capturas da execução como contingência se o ambiente Spark não estiver disponível.
