"""Normaliza a série ONI em uma dimensão mensal pronta para a camada Gold."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.bigdata.common import CLEAN, ErroDeEntrada, exigir_caminho, exigir_colunas, iniciar_spark


JANELAS = ("DJF", "JFM", "FMA", "MAM", "AMJ", "MJJ", "JJA", "JAS", "ASO", "SON", "OND", "NDJ")


def localizar_coluna(quadro, nome: str) -> str:
    for coluna in quadro.columns:
        if coluna.casefold() == nome.casefold():
            return coluna
    raise ErroDeEntrada(f"Não encontrei a coluna {nome} na tabela ONI.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=CLEAN / "landing" / "oni")
    parser.add_argument("--output", type=Path, default=CLEAN / "silver" / "oni")
    args = parser.parse_args()

    spark = iniciar_spark("el-nino-silver-oni")
    try:
        from pyspark.sql import functions as F
        from pyspark.sql.window import Window

        entrada = exigir_caminho(args.input, "o Parquet landing de ONI")
        bruto = spark.read.parquet(str(entrada))
        ano = localizar_coluna(bruto, "Year")
        colunas = [localizar_coluna(bruto, janela) for janela in JANELAS]
        exigir_colunas(bruto, [ano, *colunas], "ONI landing")

        pares = ", ".join(f"'{janela}', `{coluna}`" for janela, coluna in zip(JANELAS, colunas))
        meses_centro = F.create_map(*sum(([F.lit(janela), F.lit(indice + 1)] for indice, janela in enumerate(JANELAS)), []))
        mensal = (
            bruto.select(F.col(ano).cast("int").alias("ano_oni"), F.expr(f"stack(12, {pares}) AS (janela_oni, oni_text)"))
            .withColumn("oni", F.regexp_replace(F.trim("oni_text"), ",", ".").cast("double"))
            .withColumn("mes", meses_centro[F.col("janela_oni")])
            .withColumn("competencia", F.make_date("ano_oni", "mes", F.lit(1)))
            .drop("oni_text", "ano_oni", "mes")
            .where(F.col("competencia").isNotNull())
        )

        janela = Window.orderBy("competencia").rowsBetween(-2, 2)
        mensal = (
            mensal.withColumn("janelas_validas", F.count("oni").over(janela))
            .withColumn("janelas_el_nino", F.sum(F.when(F.col("oni") >= 0.5, 1).otherwise(0)).over(janela))
            .withColumn("janelas_la_nina", F.sum(F.when(F.col("oni") <= -0.5, 1).otherwise(0)).over(janela))
            .withColumn(
                "fase_enso",
                F.when(F.col("janelas_validas") < 5, F.lit("indisponivel"))
                .when(F.col("janelas_el_nino") == 5, F.lit("el_nino"))
                .when(F.col("janelas_la_nina") == 5, F.lit("la_nina"))
                .otherwise(F.lit("neutro")),
            )
            .withColumn("fonte_enso", F.lit("NOAA CPC - ONI v6"))
            .select("competencia", "janela_oni", "oni", "fase_enso", "fonte_enso")
            .orderBy("competencia")
        )
        mensal.write.mode("overwrite").parquet(str(args.output))
        print(f"silver/oni: {mensal.count():,} competência(s) -> {args.output}")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
