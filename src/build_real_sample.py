"""Extrai chuva observada de maio de 2024 do Atlas Pluviométrico do SGB.

O ZIP oficial fica em data/raw (ignorado pelo Git). O CSV pequeno e o JSON do
painel são derivados reproduzíveis e podem ser versionados.
"""

from __future__ import annotations

import hashlib
import json
import re
import urllib.request
import zipfile
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "data" / "raw" / "sgb" / "porto_alegre_diarios_1975_2024.zip"
SAMPLE_CSV = ROOT / "data" / "sample" / "porto_alegre_chuva_maio_2024.csv"
PANEL_JSON = ROOT / "src" / "static" / "porto_alegre_chuva_maio_2024.json"
SOURCE_PAGE = "https://rigeo.sgb.gov.br/items/bc33cf6b-674e-407f-83a0-6eb06160fa72"
ARCHIVE_URL = "https://rigeo.sgb.gov.br/bitstreams/b72a78e2-3b2e-4a28-8f4a-ed4e496ce0e0/download"
ARCHIVE_SHA256 = "65d58709cf90d2b7b746b0e14e6946a632cd7f00f9feb1cc634da48c207c0f85"
ENTRY_PATTERN = re.compile(r"^03051011-(202405\d{2})-(CP|SP)\.txt$")
MAX_BYTES = 30 * 1024 * 1024


def download_archive() -> None:
    if ARCHIVE.exists():
        return
    ARCHIVE.parent.mkdir(parents=True, exist_ok=True)
    temporary = ARCHIVE.with_suffix(".zip.part")
    request = urllib.request.Request(ARCHIVE_URL, headers={"User-Agent": "clima-em-foco/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response, temporary.open("wb") as output:
            total = 0
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_BYTES:
                    raise ValueError("O download excedeu o limite esperado de 30 MB.")
                output.write(chunk)
        temporary.replace(ARCHIVE)
    finally:
        temporary.unlink(missing_ok=True)


def archive_hash() -> str:
    digest = hashlib.sha256()
    with ARCHIVE.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_daily_rain(name: str, content: bytes) -> dict[str, object]:
    match = ENTRY_PATTERN.fullmatch(name)
    if not match:
        raise ValueError(f"Nome de arquivo inesperado: {name}")
    lines = content.decode("cp1252").splitlines()
    key = "Precipitação Total no Pluviograma (mm):"
    values = [line.split(":", 1)[1].strip() for line in lines if key in line]
    if len(values) != 1:
        raise ValueError(f"Total de chuva ausente ou duplicado: {name}")
    rain_mm = float(values[0].replace(",", "."))
    if rain_mm < 0 or (match.group(2) == "SP" and rain_mm != 0):
        raise ValueError(f"Chuva incompatível com o arquivo: {name}")
    return {
        "date": pd.Timestamp(match.group(1)).strftime("%Y-%m-%d"),
        "rain_mm": round(rain_mm, 2),
        "record_type": match.group(2),
        "source_entry": name,
    }


def main() -> None:
    download_archive()
    actual_hash = archive_hash()
    if actual_hash != ARCHIVE_SHA256:
        raise ValueError(
            "O hash do ZIP não corresponde à edição registrada. "
            f"Esperado: {ARCHIVE_SHA256}; obtido: {actual_hash}."
        )

    records = []
    with zipfile.ZipFile(ARCHIVE) as package:
        for item in package.infolist():
            if ENTRY_PATTERN.fullmatch(item.filename):
                records.append(extract_daily_rain(item.filename, package.read(item)))

    table = pd.DataFrame.from_records(records).sort_values("date").reset_index(drop=True)
    expected_dates = pd.date_range("2024-05-01", "2024-05-31").strftime("%Y-%m-%d").tolist()
    if table["date"].tolist() != expected_dates:
        raise ValueError("A amostra de maio de 2024 está incompleta ou contém dias repetidos.")

    SAMPLE_CSV.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(SAMPLE_CSV, index=False, float_format="%.2f")
    peak = table.loc[table["rain_mm"].idxmax()]
    payload = {
        "source": "Serviço Geológico do Brasil — Atlas Pluviométrico do Brasil",
        "source_page": SOURCE_PAGE,
        "archive_url": ARCHIVE_URL,
        "archive_sha256": actual_hash,
        "station": "Porto Alegre — Jardim Botânico",
        "station_code": "03051011",
        "period": "2024-05",
        "measure": "Precipitação Total no Pluviograma (mm)",
        "date_note": "A data segue o nome e o cabeçalho do arquivo diário do SGB; não equivale necessariamente ao dia civil de 00h a 24h.",
        "summary": {
            "days": int(len(table)),
            "rainy_days": int((table["rain_mm"] > 0).sum()),
            "total_mm": round(float(table["rain_mm"].sum()), 2),
            "peak_date": str(peak["date"]),
            "peak_mm": round(float(peak["rain_mm"]), 2),
        },
        "records": table[["date", "rain_mm", "record_type"]].to_dict(orient="records"),
    }
    PANEL_JSON.parent.mkdir(parents=True, exist_ok=True)
    PANEL_JSON.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Amostra gerada: {len(table)} dias; {payload['summary']['total_mm']:.2f} mm no mês.")
    print(f"CSV: {SAMPLE_CSV}")
    print(f"JSON: {PANEL_JSON}")


if __name__ == "__main__":
    main()
