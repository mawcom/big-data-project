"""Convenções compartilhadas pelos jobs de engenharia de dados."""

from __future__ import annotations

from pathlib import Path


RAIZ = Path(__file__).resolve().parents[2]
RAW_DUCKDB = RAIZ / "raw.duckdb"
CLEAN = RAIZ / "clean"
PARQUET = RAIZ / "parquet"
DASHBOARD_DATA = RAIZ / "dashboard" / "data"
REFERENCIAS = Path(__file__).resolve().parent / "referencias"


class ErroDeEntrada(RuntimeError):
    """Indica que uma etapa foi chamada sem a entrada rastreável exigida."""


def exigir_caminho(caminho: Path, descricao: str) -> Path:
    """Retorna um caminho existente ou falha com orientação acionável."""
    if not caminho.exists():
        raise ErroDeEntrada(f"Não encontrei {descricao}: {caminho}")
    return caminho


def exigir_colunas(quadro, colunas: tuple[str, ...] | list[str], descricao: str) -> None:
    """Garante contrato mínimo antes de executar uma transformação Spark."""
    ausentes = sorted(set(colunas) - set(quadro.columns))
    if ausentes:
        disponiveis = ", ".join(sorted(quadro.columns))
        raise ErroDeEntrada(
            f"{descricao} não possui as colunas exigidas: {', '.join(ausentes)}. "
            f"Colunas encontradas: {disponiveis}."
        )


def iniciar_spark(nome_app: str):
    """Inicia Spark com UTC e Parquet Zstandard para resultados reprodutíveis."""
    try:
        from pyspark.sql import SparkSession
    except ImportError as erro:  # pragma: no cover - depende do ambiente de execução
        raise ErroDeEntrada(
            "PySpark não está disponível. Execute `uv sync` e confira o JDK compatível."
        ) from erro

    return (
        SparkSession.builder.appName(nome_app)
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.parquet.compression.codec", "zstd")
        .getOrCreate()
    )


def garantir_chave_unica(quadro, chaves: tuple[str, ...] | list[str], descricao: str) -> None:
    """Interrompe a etapa quando há duas linhas para a mesma observação lógica."""
    duplicadas = quadro.groupBy(*chaves).count().where("count > 1").limit(1).count()
    if duplicadas:
        raise ErroDeEntrada(f"{descricao} possui chaves duplicadas: {', '.join(chaves)}.")


def ler_dimensao_uf(spark):
    """Lê a dimensão de UFs do recorte Nordeste versionada no código."""
    caminho = exigir_caminho(REFERENCIAS / "ufs_nordeste.csv", "a dimensão de UFs do Nordeste")
    return spark.read.option("header", True).option("sep", ";").csv(str(caminho))
