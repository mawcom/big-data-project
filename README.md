# El Niño, chuvas e queimadas no Nordeste

Trabalho de faculdade que investiga como episódios de El Niño se relacionam com a chuva e os focos de fogo detectados no Nordeste brasileiro. A análise compara as séries ao longo do tempo e por estado, considerando a sazonalidade e os limites dos dados observacionais. O projeto terá coleta reproduzível em Python, dados preparados para análise e um dashboard interativo.

O conceito, as perguntas de pesquisa, as fontes e o recorte estão em [docs/conceito.md](docs/conceito.md). O [plano de trabalho original](docs/plano-de-trabalho.pdf) registra a proposta anterior, mais ampla.

> **Estado atual:** a estrutura do repositório está pronta. O painel em `dashboard/prototipo/` usa dados **simulados** e uma pequena amostra real de chuva de Porto Alegre, em maio de 2024; nada ali é resultado desta análise.

## Recorte de dados

- Período comparável de chuva e fogo: 2003–2025.
- Chuva: CHIRPS v3 mensal, 1991–2025, para calcular anomalias usando a climatologia 1991–2020.
- Fogo: focos do satélite de referência publicados pelo INPE, 2003–2025.
- ENSO: índice ONI mensal/semanal sazonal histórico da NOAA CPC.
- Limite de armazenamento e análise: 20 GB. Dados brutos e derivados não entram no Git.

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
requirements.txt      dependências Python
```

## Como rodar

Requer Python 3.10 ou mais recente. Na pasta do projeto:

```bash
python -m venv .venv
source .venv/bin/activate        # Windows (PowerShell): .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Para abrir o protótipo do painel:

```bash
python dashboard/prototipo/app.py
```

Abra <http://127.0.0.1:8000>. Para outra porta: `--port 8080`. Para encerrar: `Ctrl+C`.

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
- [Plano de trabalho](docs/plano-de-trabalho.pdf)
- [Documentos da fase de protótipo](docs/legado/README.md)
