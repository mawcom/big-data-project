# El Niño e Big Data em Python

Trabalho de faculdade que cruza dados meteorológicos do El Niño com indicadores de agricultura, saúde, energia e desastres no Brasil, para mostrar onde o fenômeno causa prejuízo, onde traz benefício e qual a força dessas relações. O resultado será um pipeline de big data em Python, um dashboard interativo e uma conclusão baseada nos dados.

Plano completo: [docs/plano-de-trabalho.pdf](docs/plano-de-trabalho.pdf)

> **Estado atual:** estrutura do repositório pronta. O painel em `dashboard/prototipo/` é um protótipo com dados **simulados** e uma pequena amostra real de chuva (Porto Alegre, maio de 2024). Nada ali é resultado do trabalho.

## Perguntas de pesquisa

Cada uma vira uma página do dashboard.

1. A intensidade do El Niño (índice ONI) muda a chuva e a temperatura de forma diferente em cada região do Brasil?
2. Safras como soja, milho e café variam em anos de El Niño, e a variação é positiva ou negativa conforme a região?
3. Existe defasagem entre o ONI e os casos de dengue (por exemplo, de 2 a 4 meses)?
4. A geração hidrelétrica e o nível dos reservatórios caem em anos de El Niño em alguma região?
5. Desastres naturais (secas e enchentes) são mais frequentes ou mais graves nesses anos?

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
| 1. Coleta de dados | `src/ingestao/`, `raw/` | `raw/` completa e documento de fontes | — | a preencher |
| 2. Limpeza e integração (ETL) | `src/limpeza/`, `clean/` | `clean/` e a tabela cruzada | frente 1 | a preencher |
| 3. Engenharia de big data | `src/bigdata/`, `parquet/` | `parquet/`, código do pipeline e benchmark | frentes 1 e 2 (começa com amostra) | a preencher |
| 4. Análise estatística | `notebooks/`, `src/analise/` | notebook de análise e tabela de achados | frente 2 | a preencher |
| 5. Dashboard | `dashboard/` | dashboard funcionando | frentes 2 e 4 (começa com dados parciais) | a preencher |
| 6. Conclusões e apresentação | `docs/` | relatório, slides e roteiro | todas (começa cedo, com o esqueleto) | a preencher |

## Regras de Git

- Um branch por feature, com nome `feat/<assunto>` (por exemplo, `feat/ingestao-inmet`).
- Abra um PR para `main`; a pessoa da frente 3 revisa.
- Dado grande nunca entra no Git: `raw/`, `clean/` e `parquet/` são ignorados (só o `.gitkeep` fica). Arquivos pequenos de teste vão em `amostras/`.
- Nada de senhas, tokens ou credenciais no repositório.

## Documentação

- [Plano de trabalho](docs/plano-de-trabalho.pdf)
- [Documentos da fase de protótipo](docs/legado/README.md)
