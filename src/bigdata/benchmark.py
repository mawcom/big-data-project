"""Mede a mesma agregação CHIRPS por UF em pandas e PySpark.

O job usa o landing CHIRPS e o mesmo lookup espacial usado na produção. Assim,
o benchmark mede uma operação volumosa e não a pequena tabela Gold final.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from time import perf_counter

import pandas as pd

from src.bigdata.common import CLEAN, ErroDeEntrada, exigir_caminho, iniciar_spark


def tamanho_em_bytes(caminho: Path) -> int:
    return sum(item.stat().st_size for item in caminho.rglob("*") if item.is_file())


def executar_pandas(chirps: Path, lookup: Path) -> tuple[float, int]:
    inicio = perf_counter()
    chuva = pd.read_parquet(chirps, columns=["competencia", "latitude", "longitude", "precipitacao"])
    mapa = pd.read_parquet(lookup)
    for quadro in (chuva, mapa):
        quadro["latitude"] = quadro["latitude"].astype(float).round(5)
        quadro["longitude"] = quadro["longitude"].astype(float).round(5)
    if "peso_area" not in mapa:
        mapa["peso_area"] = 1.0
    combinado = chuva.merge(mapa[["latitude", "longitude", "uf_codigo_ibge", "peso_area"]], how="inner")
    combinado = combinado[combinado["precipitacao"] >= 0]
    combinado["ponderada"] = combinado["precipitacao"] * combinado["peso_area"]
    resultado = combinado.groupby(["competencia", "uf_codigo_ibge"], as_index=False).agg(
        ponderada=("ponderada", "sum"), peso=("peso_area", "sum")
    )
    resultado["precipitacao_mm"] = resultado["ponderada"] / resultado["peso"]
    return perf_counter() - inicio, len(resultado)


def executar_pandas_csv(chirps_csv: Path, lookup: Path) -> tuple[float, int]:
    inicio = perf_counter()
    chuva = pd.read_csv(chirps_csv, usecols=["competencia", "latitude", "longitude", "precipitacao"])
    mapa = pd.read_parquet(lookup)
    for quadro in (chuva, mapa):
        quadro["latitude"] = quadro["latitude"].astype(float).round(5)
        quadro["longitude"] = quadro["longitude"].astype(float).round(5)
    if "peso_area" not in mapa:
        mapa["peso_area"] = 1.0
    combinado = chuva.merge(mapa[["latitude", "longitude", "uf_codigo_ibge", "peso_area"]], how="inner")
    combinado = combinado[combinado["precipitacao"] >= 0]
    combinado["ponderada"] = combinado["precipitacao"] * combinado["peso_area"]
    resultado = combinado.groupby(["competencia", "uf_codigo_ibge"], as_index=False).agg(
        ponderada=("ponderada", "sum"), peso=("peso_area", "sum")
    )
    resultado["precipitacao_mm"] = resultado["ponderada"] / resultado["peso"]
    return perf_counter() - inicio, len(resultado)


def executar_spark(chirps: Path, lookup: Path) -> tuple[float, int]:
    spark = iniciar_spark("el-nino-benchmark")
    try:
        from pyspark.sql import functions as F

        inicio = perf_counter()
        chuva = spark.read.parquet(str(chirps)).select(
            "competencia", F.round(F.col("latitude").cast("double"), 5).alias("latitude"),
            F.round(F.col("longitude").cast("double"), 5).alias("longitude"), F.col("precipitacao").cast("double").alias("precipitacao"),
        )
        mapa = spark.read.parquet(str(lookup))
        peso = F.col("peso_area").cast("double") if "peso_area" in mapa.columns else F.lit(1.0)
        mapa = mapa.select(
            F.round(F.col("latitude").cast("double"), 5).alias("latitude"),
            F.round(F.col("longitude").cast("double"), 5).alias("longitude"), "uf_codigo_ibge", peso.alias("peso_area"),
        )
        resultado = (
            chuva.where(F.col("precipitacao") >= 0).join(F.broadcast(mapa), ["latitude", "longitude"], "inner")
            .groupBy("competencia", "uf_codigo_ibge")
            .agg(
                F.sum(F.col("precipitacao") * F.col("peso_area")).alias("ponderada"),
                F.sum("peso_area").alias("peso"),
            )
            .withColumn("precipitacao_mm", F.col("ponderada") / F.col("peso"))
        )
        linhas = resultado.count()
        return perf_counter() - inicio, linhas
    finally:
        spark.stop()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chirps", type=Path, default=CLEAN / "landing" / "chirps")
    parser.add_argument("--lookup", type=Path, default=CLEAN / "referencias" / "chirps_celula_uf")
    parser.add_argument("--csv", type=Path, help="Baseline CSV do mesmo landing CHIRPS; inclua para o comparativo de três motores.")
    parser.add_argument("--output", type=Path, default=Path("docs") / "benchmark_resultados.csv")
    args = parser.parse_args()
    chirps = exigir_caminho(args.chirps, "o Parquet landing de CHIRPS")
    lookup = exigir_caminho(args.lookup, "o mapa de células CHIRPS por UF")

    tamanho = tamanho_em_bytes(chirps)
    resultados = []
    if args.csv is not None:
        csv_landing = exigir_caminho(args.csv, "o CSV de baseline CHIRPS")
        segundos, linhas = executar_pandas_csv(csv_landing, lookup)
        resultados.append({"motor": "pandas_csv", "operacao": "agregacao_chirps_uf_mes", "bytes_entrada": csv_landing.stat().st_size, "linhas_saida": linhas, "segundos": round(segundos, 3)})
        print(f"pandas_csv: {segundos:.3f}s; {linhas:,} linha(s) de saída")
    for motor, funcao in (("pandas_parquet", executar_pandas), ("pyspark_parquet", executar_spark)):
        segundos, linhas = funcao(chirps, lookup)
        resultados.append({"motor": motor, "operacao": "agregacao_chirps_uf_mes", "bytes_entrada": tamanho, "linhas_saida": linhas, "segundos": round(segundos, 3)})
        print(f"{motor}: {segundos:.3f}s; {linhas:,} linha(s) de saída")
    if len({resultado["linhas_saida"] for resultado in resultados}) != 1:
        raise ErroDeEntrada("Pandas e PySpark produziram números de grupos diferentes; não publique o benchmark.")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=list(resultados[0]))
        escritor.writeheader()
        escritor.writerows(resultados)
    print(f"benchmark: resultado gravado em {args.output}")


if __name__ == "__main__":
    main()
