"""Publica o subconjunto Gold que o dashboard pode carregar sem ler Parquet."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from src.bigdata.common import DASHBOARD_DATA, PARQUET, ErroDeEntrada, exigir_caminho, iniciar_spark


def competencia(valor: str) -> date:
    try:
        ano, mes = (int(parte) for parte in valor.split("-"))
        return date(ano, mes, 1)
    except (TypeError, ValueError) as erro:
        raise argparse.ArgumentTypeError("Use AAAA-MM, por exemplo 2003-01.") from erro


def salvar_json(caminho: Path, conteudo: dict) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_suffix(caminho.suffix + ".tmp")
    temporario.write_text(json.dumps(conteudo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporario.replace(caminho)


def registros(quadro) -> list[dict]:
    return [json.loads(linha) for linha in quadro.toJSON().collect()]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", type=Path, default=PARQUET / "gold")
    parser.add_argument("--output", type=Path, default=DASHBOARD_DATA)
    parser.add_argument("--inicio", type=competencia, default=date(2003, 1, 1))
    parser.add_argument("--fim", type=competencia, default=date(2025, 12, 1))
    args = parser.parse_args()
    if args.inicio > args.fim:
        raise SystemExit("--inicio deve ser anterior ou igual a --fim.")

    spark = iniciar_spark("el-nino-export-dashboard")
    try:
        from pyspark.sql import functions as F

        fatos = spark.read.parquet(str(exigir_caminho(args.gold / "fato_mensal_uf", "a tabela Gold por UF")))
        resumo = spark.read.parquet(str(exigir_caminho(args.gold / "resumo_mensal_nordeste", "o resumo Gold do Nordeste")))
        inicio = F.lit(args.inicio.isoformat()).cast("date")
        fim = F.lit(args.fim.isoformat()).cast("date")
        fatos = fatos.where(F.col("competencia").between(inicio, fim)).orderBy("competencia", "uf_sigla")
        resumo = resumo.where(F.col("competencia").between(inicio, fim)).orderBy("competencia")
        quantidade_fatos = fatos.count()
        quantidade_resumo = resumo.count()
        if not quantidade_fatos or not quantidade_resumo:
            raise ErroDeEntrada("O período solicitado não contém produtos Gold para publicar.")

        cobertura = fatos.agg(
            F.min("competencia").alias("inicio"), F.max("competencia").alias("fim"),
            F.countDistinct("uf_codigo_ibge").alias("ufs"),
        ).first()
        metadados = {
            "status": "real_com_cobertura_declarada",
            "escopo": "Nordeste por UF/mês; Maranhão destacado",
            "periodo": {"inicio": cobertura.inicio.isoformat(), "fim": cobertura.fim.isoformat()},
            "ufs": cobertura.ufs,
            "fontes": {
                "enso": "NOAA CPC - ONI v6",
                "chuva": "CHIRPS v3 mensal",
                "fogo": "INPE - satélite de referência",
            },
            "versao_pipeline": "0.1.0",
            "avisos": [
                "Associação estatística não demonstra causalidade.",
                "Focos de calor não equivalem a área queimada ou número de incêndios.",
                "Consulte qualidade_chuva e qualidade_fogo antes de comparar períodos.",
            ],
        }
        salvar_json(args.output / "metadata.json", metadados)
        salvar_json(args.output / "fato_mensal_uf.json", {"metadata": metadados, "records": registros(fatos)})
        salvar_json(args.output / "resumo_mensal_nordeste.json", {"metadata": metadados, "records": registros(resumo)})
        print(f"dashboard/data: {quantidade_fatos:,} registros por UF e {quantidade_resumo:,} regionais -> {args.output}")
    finally:
        spark.stop()


if __name__ == "__main__":
    main()
