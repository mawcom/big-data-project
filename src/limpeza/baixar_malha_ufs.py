"""Baixa as nove malhas simplificadas do IBGE para o piloto espacial.

O GeoJSON fica em raw/referencias/ e não é versionado. Para análise espacial
definitiva, substituir pela edição da malha original definida pelo grupo.
"""

from __future__ import annotations

import csv
import gzip
import json
from pathlib import Path
import urllib.request


RAIZ = Path(__file__).resolve().parents[2]
DIM_UF = RAIZ / "src" / "bigdata" / "referencias" / "ufs_nordeste.csv"
DESTINO = RAIZ / "raw" / "referencias" / "ufs_ibge.geojson"
BASE_URL = "https://servicodados.ibge.gov.br/api/v3/malhas/estados"


def main() -> None:
    if DESTINO.exists():
        print(f"Malha já disponível: {DESTINO}")
        return
    with DIM_UF.open(encoding="utf-8", newline="") as arquivo:
        ufs = list(csv.DictReader(arquivo, delimiter=";"))
    features = []
    for uf in ufs:
        codigo = uf["uf_codigo_ibge"]
        sigla = uf["uf_sigla"]
        url = f"{BASE_URL}/{sigla}?qualidade=minima&formato=application/vnd.geo+json"
        pedido = urllib.request.Request(
            url, headers={"Accept": "application/vnd.geo+json", "User-Agent": "big-data-project/1.0"}
        )
        with urllib.request.urlopen(pedido, timeout=60) as resposta:
            payload = resposta.read()
            if payload.startswith(b"\x1f\x8b"):
                payload = gzip.decompress(payload)
            geojson = json.loads(payload.decode("utf-8-sig"))
        candidatos = geojson.get("features", [])
        if len(candidatos) != 1 or candidatos[0].get("geometry", {}).get("type") not in {"Polygon", "MultiPolygon"}:
            raise ValueError(f"Resposta geográfica inesperada para {sigla}: {url}")
        feature = candidatos[0]
        if str(feature.get("properties", {}).get("codarea")) != codigo:
            raise ValueError(f"Código de UF diferente do esperado para {sigla}: {url}")
        feature["properties"] = {"CD_UF": codigo, "SIGLA_UF": sigla, "NOME_UF": uf["uf_nome"]}
        features.append(feature)
        print(f"IBGE: {sigla} ({codigo})")
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    temporario = DESTINO.with_suffix(".geojson.part")
    temporario.write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False), encoding="utf-8"
    )
    temporario.replace(DESTINO)
    print(f"Malha de {len(features)} UFs: {DESTINO}")


if __name__ == "__main__":
    main()
