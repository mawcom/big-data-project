"""Gera o lookup espacial célula CHIRPS -> UF a partir de um GeoJSON oficial.

Por padrão, a atribuição usa o centro da célula dentro do polígono da UF. Isso
é rastreável e evita caixas delimitadoras, mas não substitui pesos por área
quando o estudo exigir máxima precisão junto às fronteiras.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.bigdata.common import CLEAN, ErroDeEntrada, exigir_caminho, exigir_colunas, iniciar_spark


CODIGOS_NORDESTE = {"21", "22", "23", "24", "25", "26", "27", "28", "29"}


def codigo_uf(valor: object) -> str | None:
    try:
        codigo = str(int(str(valor))).zfill(2)
    except (TypeError, ValueError):
        return None
    return codigo if codigo in CODIGOS_NORDESTE else None


def anel_contem_ponto(longitude: float, latitude: float, anel: list[list[float]]) -> bool:
    """Implementa ray casting; os pontos da borda são tratados como internos."""
    dentro = False
    for atual, anterior in zip(anel, anel[1:] + anel[:1]):
        x1, y1 = atual
        x2, y2 = anterior
        if min(y1, y2) <= latitude <= max(y1, y2) and min(x1, x2) <= longitude <= max(x1, x2):
            produto = (x2 - x1) * (latitude - y1) - (y2 - y1) * (longitude - x1)
            if abs(produto) < 1e-12:
                return True
        cruza = (y1 > latitude) != (y2 > latitude)
        if cruza:
            limite = (x2 - x1) * (latitude - y1) / (y2 - y1) + x1
            if longitude < limite:
                dentro = not dentro
    return dentro


def poligono_contem_ponto(longitude: float, latitude: float, poligono: list[list[list[float]]]) -> bool:
    return bool(poligono) and anel_contem_ponto(longitude, latitude, poligono[0]) and not any(
        anel_contem_ponto(longitude, latitude, buraco) for buraco in poligono[1:]
    )


def extrair_poligonos(geojson: dict, propriedade_codigo: str) -> dict[str, list[list[list[list[float]]]]]:
    """Converte Polygon/MultiPolygon GeoJSON no formato compacto usado pela UDF."""
    resultado: dict[str, list[list[list[list[float]]]]] = {}
    for feature in geojson.get("features", []):
        codigo = codigo_uf(feature.get("properties", {}).get(propriedade_codigo))
        if codigo is None:
            continue
        geometria = feature.get("geometry") or {}
        if geometria.get("type") == "Polygon":
            poligonos = [geometria.get("coordinates", [])]
        elif geometria.get("type") == "MultiPolygon":
            poligonos = geometria.get("coordinates", [])
        else:
            continue
        resultado.setdefault(codigo, []).extend(poligonos)
    if set(resultado) != CODIGOS_NORDESTE:
        faltantes = ", ".join(sorted(CODIGOS_NORDESTE - set(resultado)))
        raise ErroDeEntrada(
            f"O GeoJSON não contém todas as UFs do Nordeste na propriedade {propriedade_codigo}. "
            f"Faltantes: {faltantes or 'nenhuma'} ."
        )
    return resultado


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--chirps", type=Path, default=CLEAN / "landing" / "chirps")
    parser.add_argument("--uf-geojson", type=Path, required=True, help="GeoJSON oficial de limites de UF.")
    parser.add_argument("--codigo-property", default="CD_UF", help="Propriedade GeoJSON que contém o código IBGE de UF.")
    parser.add_argument("--output", type=Path, default=CLEAN / "referencias" / "chirps_celula_uf")
    args = parser.parse_args()

    geojson = json.loads(exigir_caminho(args.uf_geojson, "o GeoJSON oficial de UFs").read_text(encoding="utf-8"))
    poligonos = extrair_poligonos(geojson, args.codigo_property)
    spark = iniciar_spark("el-nino-build-chirps-lookup")
    try:
        from pyspark.sql import functions as F
        from pyspark.sql.types import StringType

        chuva = spark.read.parquet(str(exigir_caminho(args.chirps, "o Parquet landing de CHIRPS")))
        exigir_colunas(chuva, ("latitude", "longitude"), "CHIRPS landing")

        def localizar_uf(latitude: float | None, longitude: float | None) -> str | None:
            if latitude is None or longitude is None:
                return None
            for codigo, unidades in poligonos.items():
                if any(poligono_contem_ponto(longitude, latitude, unidade) for unidade in unidades):
                    return codigo
            return None

        pertence_a_uf = F.udf(localizar_uf, StringType())
        lookup = (
            chuva.select(
                F.round(F.col("latitude").cast("double"), 5).alias("latitude"),
                F.round(F.col("longitude").cast("double"), 5).alias("longitude"),
            )
            .dropDuplicates()
            .withColumn("uf_codigo_ibge", pertence_a_uf("latitude", "longitude"))
            .where(F.col("uf_codigo_ibge").isNotNull())
            .withColumn("peso_area", F.lit(1.0))
            .withColumn("metodo_espacial", F.lit("centro_da_celula_no_poligono"))
        )
        if lookup.limit(1).count() == 0:
            raise ErroDeEntrada("Nenhuma célula CHIRPS caiu nas UFs do Nordeste. Confira CRS e GeoJSON.")
        lookup.write.mode("overwrite").parquet(str(args.output))
        print(f"referencias/chirps_celula_uf: {lookup.count():,} célula(s) -> {args.output}")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
