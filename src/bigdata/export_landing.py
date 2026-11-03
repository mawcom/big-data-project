"""Exporta as tabelas brutas relevantes do DuckDB para Parquet de landing.

Esta etapa não limpa nem agrega dados. Ela apenas cria uma ponte colunar entre
o landing auditável (`raw.duckdb`) e os jobs Spark.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb

from src.bigdata.common import CLEAN, RAW_DUCKDB, ErroDeEntrada, exigir_caminho


TABELAS_PERMITIDAS = ("oni", "chirps", "inpe")


def consulta_para(tabela: str) -> str:
    """Retorna a projeção landing, preservando todas as colunas de origem."""
    if tabela == "chirps":
        return r"""
            SELECT *,
                CAST(
                    try_strptime(
                        regexp_extract(_arquivo_origem, 'chirps-v3\.0\.([0-9]{6})', 1),
                        '%Y%m'
                    ) AS DATE
                ) AS competencia
            FROM chirps
        """
    return f"SELECT * FROM {tabela}"


def tabelas_disponiveis(conexao: duckdb.DuckDBPyConnection) -> set[str]:
    return {
        linha[0]
        for linha in conexao.execute("SELECT table_name FROM information_schema.tables").fetchall()
    }


def exportar_tabela(conexao: duckdb.DuckDBPyConnection, tabela: str, destino: Path, formato: str) -> int:
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.unlink(missing_ok=True)
    caminho_sql = str(destino).replace("'", "''")
    consulta = consulta_para(tabela)
    linhas = conexao.execute(f"SELECT count(*) FROM ({consulta})").fetchone()[0]
    opcoes = "(FORMAT PARQUET, COMPRESSION ZSTD)" if formato == "parquet" else "(FORMAT CSV, HEADER)"
    conexao.execute(f"COPY ({consulta}) TO '{caminho_sql}' {opcoes}")
    return linhas


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=RAW_DUCKDB, help="Banco DuckDB de landing.")
    parser.add_argument("--output", type=Path, default=CLEAN / "landing", help="Raiz Parquet de landing.")
    parser.add_argument("--format", choices=("parquet", "csv"), default="parquet", help="Formato de saída; CSV é apenas baseline de benchmark.")
    parser.add_argument(
        "--tables", nargs="+", choices=TABELAS_PERMITIDAS, default=list(TABELAS_PERMITIDAS),
        help="Tabelas a exportar; o padrão cobre o MVP do painel.",
    )
    args = parser.parse_args()

    banco = exigir_caminho(args.database, "o banco raw.duckdb; rode `uv run poe ingest_raw` antes")
    with duckdb.connect(str(banco), read_only=True) as conexao:
        existentes = tabelas_disponiveis(conexao)
        faltantes = sorted(set(args.tables) - existentes)
        if faltantes:
            raise ErroDeEntrada(
                f"O banco não possui as tabelas necessárias: {', '.join(faltantes)}. "
                "Confira a coleta e a carga de dados brutos."
            )
        for tabela in args.tables:
            destino = args.output / tabela / f"part-00000.{args.format}"
            linhas = exportar_tabela(conexao, tabela, destino, args.format)
            print(f"landing/{tabela}: {linhas:,} linha(s) -> {destino}")


if __name__ == "__main__":
    main()
