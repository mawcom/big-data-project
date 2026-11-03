"""Agrega CHIRPS mensal para UF usando um mapa de células previamente auditado.

O arquivo de referência deve ter `latitude`, `longitude`, `uf_codigo_ibge` e,
opcionalmente, `peso_area`. Ele é o artefato espacial auditável que liga cada
célula CHIRPS à UF; a etapa não usa caixa delimitadora como substituto de limite.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from src.bigdata.common import CLEAN, ErroDeEntrada, exigir_caminho, exigir_colunas, iniciar_spark, ler_dimensao_uf


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=CLEAN / "landing" / "chirps")
    parser.add_argument(
        "--lookup", type=Path, default=CLEAN / "referencias" / "chirps_celula_uf",
        help="Parquet de mapeamento célula CHIRPS -> UF, gerado a partir de limites oficiais.",
    )
    parser.add_argument("--output", type=Path, default=CLEAN / "silver" / "chirps_uf_mes")
    args = parser.parse_args()

    spark = iniciar_spark("el-nino-silver-chirps")
    try:
        from pyspark.sql import functions as F

        bruto = spark.read.parquet(str(exigir_caminho(args.input, "o Parquet landing de CHIRPS")))
        referencia = spark.read.parquet(str(exigir_caminho(args.lookup, "o mapa de células CHIRPS por UF")))
        exigir_colunas(bruto, ("competencia", "latitude", "longitude", "precipitacao"), "CHIRPS landing")
        exigir_colunas(referencia, ("latitude", "longitude", "uf_codigo_ibge"), "mapa célula -> UF")

        peso = F.col("peso_area").cast("double") if "peso_area" in referencia.columns else F.lit(1.0)
        referencia = (
            referencia.select(
                F.round(F.col("latitude").cast("double"), 5).alias("_latitude"),
                F.round(F.col("longitude").cast("double"), 5).alias("_longitude"),
                F.col("uf_codigo_ibge").cast("string").alias("uf_codigo_ibge"),
                F.when(peso > 0, peso).otherwise(F.lit(None)).alias("peso_area"),
            )
            .where(F.col("peso_area").isNotNull())
            .dropDuplicates(["_latitude", "_longitude", "uf_codigo_ibge"])
        )
        limites = referencia.agg(
            F.min("_latitude").alias("lat_min"), F.max("_latitude").alias("lat_max"),
            F.min("_longitude").alias("lon_min"), F.max("_longitude").alias("lon_max"),
        ).first()
        if any(valor is None for valor in limites):
            raise ErroDeEntrada("O mapa célula -> UF não possui células válidas.")

        chuva = (
            bruto.select(
                F.to_date("competencia").alias("competencia"),
                F.round(F.col("latitude").cast("double"), 5).alias("_latitude"),
                F.round(F.col("longitude").cast("double"), 5).alias("_longitude"),
                F.when(F.col("precipitacao").cast("double") >= 0, F.col("precipitacao").cast("double"))
                .alias("precipitacao_mm"),
            )
            .where(F.col("competencia").isNotNull())
            .where(F.col("_latitude").between(limites.lat_min, limites.lat_max))
            .where(F.col("_longitude").between(limites.lon_min, limites.lon_max))
        )
        combinado = chuva.join(F.broadcast(referencia), ["_latitude", "_longitude"], "inner")
        if combinado.limit(1).count() == 0:
            raise ErroDeEntrada(
                "Nenhuma célula CHIRPS foi associada ao mapa de UFs. Confira CRS, coordenadas e precisão do lookup."
            )

        ufs = ler_dimensao_uf(spark).select("uf_codigo_ibge")
        silver = (
            combinado.join(F.broadcast(ufs), "uf_codigo_ibge", "inner")
            .where(F.col("precipitacao_mm").isNotNull())
            .groupBy("competencia", "uf_codigo_ibge")
            .agg(
                (F.sum(F.col("precipitacao_mm") * F.col("peso_area")) / F.sum("peso_area")).alias("precipitacao_mm"),
                F.count(F.lit(1)).alias("celulas_chirps_validas"),
                F.sum("peso_area").alias("peso_total"),
            )
            .withColumn("ano", F.year("competencia"))
            .withColumn("qualidade_chuva", F.lit("ok"))
            .withColumn("fonte_chuva", F.lit("CHIRPS v3 mensal"))
        )
        silver.write.mode("overwrite").partitionBy("ano").parquet(str(args.output))
        print(f"silver/chirps_uf_mes: {silver.count():,} linha(s) -> {args.output}")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
