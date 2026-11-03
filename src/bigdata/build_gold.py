"""Cria a tabela mensal Gold por UF e o resumo regional do Nordeste."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from src.bigdata.common import (
    CLEAN,
    PARQUET,
    ErroDeEntrada,
    exigir_caminho,
    exigir_colunas,
    garantir_chave_unica,
    iniciar_spark,
    ler_dimensao_uf,
)


def competencia(valor: str) -> date:
    try:
        ano, mes = (int(parte) for parte in valor.split("-"))
        return date(ano, mes, 1)
    except (TypeError, ValueError) as erro:
        raise argparse.ArgumentTypeError("Use AAAA-MM, por exemplo 2003-01.") from erro


def ler_silver(spark, caminho: Path, colunas: tuple[str, ...], descricao: str):
    quadro = spark.read.parquet(str(exigir_caminho(caminho, descricao)))
    exigir_colunas(quadro, colunas, descricao)
    return quadro


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chirps", type=Path, default=CLEAN / "silver" / "chirps_uf_mes")
    parser.add_argument("--inpe", type=Path, default=CLEAN / "silver" / "inpe_uf_mes")
    parser.add_argument("--oni", type=Path, default=CLEAN / "silver" / "oni")
    parser.add_argument("--output", type=Path, default=PARQUET / "gold")
    parser.add_argument("--inicio", type=competencia, default=date(2003, 1, 1))
    parser.add_argument("--fim", type=competencia, default=date(2025, 12, 1))
    args = parser.parse_args()
    if args.inicio > args.fim:
        raise SystemExit("--inicio deve ser anterior ou igual a --fim.")

    spark = iniciar_spark("el-nino-build-gold")
    try:
        from pyspark.sql import functions as F

        ufs = (
            ler_dimensao_uf(spark)
            .select(
                F.col("uf_codigo_ibge").cast("string"), "uf_sigla", "uf_nome", "regiao",
                F.col("destaque_maranhao").cast("boolean").alias("destaque_maranhao"),
            )
        )
        chirps = ler_silver(
            spark, args.chirps,
            ("competencia", "uf_codigo_ibge", "precipitacao_mm", "celulas_chirps_validas", "peso_total"),
            "Silver de CHIRPS por UF/mês",
        )
        inpe = ler_silver(
            spark, args.inpe, ("competencia", "uf_codigo_ibge", "focos_inpe"),
            "Silver de focos INPE por UF/mês",
        )
        oni = ler_silver(spark, args.oni, ("competencia", "oni", "fase_enso"), "Silver de ONI")
        garantir_chave_unica(chirps, ("competencia", "uf_codigo_ibge"), "Silver de CHIRPS")
        garantir_chave_unica(inpe, ("competencia", "uf_codigo_ibge"), "Silver de INPE")
        garantir_chave_unica(oni, ("competencia",), "Silver de ONI")

        chirps = chirps.withColumn("competencia", F.to_date("competencia")).drop("ano")
        inpe = inpe.withColumn("competencia", F.to_date("competencia")).drop("ano")
        oni = oni.withColumn("competencia", F.to_date("competencia"))
        base_climatica = chirps.where(F.year("competencia").between(1991, 2020))
        climatologia = (
            base_climatica.groupBy("uf_codigo_ibge", F.month("competencia").alias("mes"))
            .agg(
                F.avg("precipitacao_mm").alias("climatologia_mm_1991_2020"),
                F.countDistinct(F.year("competencia")).alias("anos_climatologia"),
            )
        )
        chirps = (
            chirps.withColumn("mes", F.month("competencia"))
            .join(climatologia, ["uf_codigo_ibge", "mes"], "left")
            .drop("mes")
        )
        calendario = (
            spark.createDataFrame([(args.inicio, args.fim)], "inicio date, fim date")
            .select(F.explode(F.sequence("inicio", "fim", F.expr("interval 1 month"))).alias("competencia"))
            .withColumn("ano", F.year("competencia"))
            .withColumn("mes", F.month("competencia"))
        )
        fato = (
            calendario.crossJoin(F.broadcast(ufs))
            .join(chirps, ["competencia", "uf_codigo_ibge"], "left")
            .join(inpe, ["competencia", "uf_codigo_ibge"], "left")
            .join(oni.select("competencia", "oni", "fase_enso", "janela_oni", "fonte_enso"), "competencia", "left")
            .withColumn("anomalia_chuva_mm", F.col("precipitacao_mm") - F.col("climatologia_mm_1991_2020"))
            .withColumn(
                "anomalia_chuva_pct",
                F.when(F.col("climatologia_mm_1991_2020") > 0,
                       F.col("anomalia_chuva_mm") / F.col("climatologia_mm_1991_2020") * 100),
            )
            .withColumn(
                "qualidade_chuva",
                F.when(F.col("precipitacao_mm").isNull(), F.lit("ausente"))
                .when(F.col("anos_climatologia") == 30, F.coalesce(F.col("qualidade_chuva"), F.lit("ok")))
                .otherwise(F.lit("parcial")),
            )
            .withColumn(
                "qualidade_fogo",
                F.when(F.col("focos_inpe").isNull(), F.lit("ausente"))
                .otherwise(F.coalesce(F.col("qualidade_fogo"), F.lit("ok"))),
            )
            .withColumn(
                "data_status",
                F.when(F.col("precipitacao_mm").isNotNull() | F.col("focos_inpe").isNotNull(), F.lit("real"))
                .otherwise(F.lit("indisponivel")),
            )
            .withColumn("versao_pipeline", F.lit("0.1.0"))
            .withColumn("atualizado_em_utc", F.current_timestamp())
            .select(
                "competencia", "ano", "mes", "uf_codigo_ibge", "uf_sigla", "uf_nome", "regiao", "destaque_maranhao",
                "oni", "janela_oni", "fase_enso", "fonte_enso", "precipitacao_mm", "climatologia_mm_1991_2020",
                "anomalia_chuva_mm", "anomalia_chuva_pct", "focos_inpe", "celulas_chirps_validas", "peso_total",
                "anos_climatologia", "qualidade_chuva", "qualidade_fogo", "fonte_chuva", "fonte_fogo",
                "data_status", "versao_pipeline", "atualizado_em_utc",
            )
        )
        reais = fato.where(F.col("data_status") == "real").limit(1).count()
        if not reais:
            raise ErroDeEntrada("A camada Gold ficaria sem observações reais; confira as entradas Silver e o período.")
        fato.write.mode("overwrite").partitionBy("ano").parquet(str(args.output / "fato_mensal_uf"))

        regional_base = fato.groupBy("competencia", "ano", "mes").agg(
            F.sum(F.when(F.col("precipitacao_mm").isNotNull(), F.col("precipitacao_mm") * F.col("peso_total"))).alias("chuva_ponderada"),
            F.sum(F.when(F.col("precipitacao_mm").isNotNull(), F.col("peso_total"))).alias("peso_total"),
            F.sum("focos_inpe").alias("focos_inpe"),
            F.first("oni", ignorenulls=True).alias("oni"),
            F.first("janela_oni", ignorenulls=True).alias("janela_oni"),
            F.first("fase_enso", ignorenulls=True).alias("fase_enso"),
            F.count(F.when(F.col("precipitacao_mm").isNotNull(), 1)).alias("ufs_chuva_com_dado"),
            F.count(F.when(F.col("focos_inpe").isNotNull(), 1)).alias("ufs_fogo_com_dado"),
        )
        regional = (
            regional_base.withColumn(
                "precipitacao_mm",
                F.when(F.col("peso_total") > 0, F.col("chuva_ponderada") / F.col("peso_total")),
            )
            .withColumn("qualidade_chuva", F.when(F.col("ufs_chuva_com_dado") == 9, "ok").when(F.col("ufs_chuva_com_dado") == 0, "ausente").otherwise("parcial"))
            .withColumn("qualidade_fogo", F.when(F.col("ufs_fogo_com_dado") == 9, "ok").when(F.col("ufs_fogo_com_dado") == 0, "ausente").otherwise("parcial"))
            .withColumn("data_status", F.when((F.col("ufs_chuva_com_dado") + F.col("ufs_fogo_com_dado")) > 0, "real").otherwise("indisponivel"))
            .withColumn("regiao", F.lit("Nordeste"))
            .withColumn("versao_pipeline", F.lit("0.1.0"))
            .withColumn("atualizado_em_utc", F.current_timestamp())
            .select(
                "competencia", "ano", "mes", "regiao", "oni", "janela_oni", "fase_enso", "precipitacao_mm",
                "focos_inpe", "ufs_chuva_com_dado", "ufs_fogo_com_dado", "qualidade_chuva", "qualidade_fogo",
                "data_status", "versao_pipeline", "atualizado_em_utc",
            )
        )
        regional.write.mode("overwrite").partitionBy("ano").parquet(str(args.output / "resumo_mensal_nordeste"))
        print(f"gold/fato_mensal_uf: {fato.count():,} linha(s) -> {args.output / 'fato_mensal_uf'}")
        print(f"gold/resumo_mensal_nordeste: {regional.count():,} linha(s) -> {args.output / 'resumo_mensal_nordeste'}")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
