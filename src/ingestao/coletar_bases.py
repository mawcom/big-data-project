"""Baixa as bases selecionadas para o estudo de El Niño no Nordeste."""

from __future__ import annotations

import hashlib
import json
import tarfile
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "raw"
MAX_RAW_BYTES = 2 * 1024**3
START_RAIN_YEAR = 1981
END_RAIN_YEAR = 2026
END_RAIN_MONTH = 9
END_FIRE_YEAR = 2025
START_FIRE_YEAR = 2003
USER_AGENT = "big-data-project/1.0 (coleta educacional)"
ONI_URL = "https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/oni/v6/index.php"
CHIRPS_URL = "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/monthly/latam/bils"
INPE_URL = "https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/anual/Brasil_sat_ref"
CHUNK_SIZE = 1024 * 1024


def raw_size() -> int:
    return sum(path.stat().st_size for path in RAW.rglob("*") if path.is_file() and not path.name.endswith(".part"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, destination: Path, validator) -> dict[str, object]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size:
        validator(destination)
        return {
            "url": url,
            "path": destination.relative_to(ROOT).as_posix(),
            "bytes": destination.stat().st_size,
            "sha256": sha256(destination),
            "status": "já existia",
        }

    temporary = destination.with_name(destination.name + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    current_bytes = raw_size()
    try:
        with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as output:
            while chunk := response.read(CHUNK_SIZE):
                current_bytes += len(chunk)
                if current_bytes > MAX_RAW_BYTES:
                    raise ValueError("A coleta ultrapassaria a reserva de 2 GiB para arquivos brutos.")
                output.write(chunk)
        validator(temporary)
        temporary.replace(destination)
    finally:
        temporary.unlink(missing_ok=True)

    return {
        "url": url,
        "path": destination.relative_to(ROOT).as_posix(),
        "bytes": destination.stat().st_size,
        "sha256": sha256(destination),
        "status": "baixado",
    }


def validate_oni(path: Path) -> None:
    content = path.read_bytes()
    if b"Oceanic Ni\xc3\xb1o Index" not in content and b"Oceanic Ni" not in content:
        raise ValueError("A página baixada não contém a tabela histórica ONI esperada.")
    if b"2025" not in content:
        raise ValueError("A página do ONI não contém dados até 2025.")


def validate_zip(path: Path) -> None:
    with zipfile.ZipFile(path) as package:
        if package.testzip() is not None:
            raise ValueError(f"Arquivo ZIP corrompido: {path.name}")


def validate_tar_gz(path: Path) -> None:
    with tarfile.open(path, "r:gz") as package:
        if not package.getmembers():
            raise ValueError(f"Arquivo CHIRPS vazio: {path.name}")


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    if raw_size() > MAX_RAW_BYTES:
        raise ValueError("A pasta raw/ já ultrapassa a reserva de 2 GiB para arquivos brutos.")

    entries = []
    oni_path = RAW / "enso" / "oni_cpc_v6.html"
    entries.append(download(ONI_URL, oni_path, validate_oni))

    for year in range(START_RAIN_YEAR, END_RAIN_YEAR + 1):
        last_month = END_RAIN_MONTH if year == END_RAIN_YEAR else 12
        for month in range(1, last_month + 1):
            stamp = f"{year}{month:02d}"
            filename = f"chirps-v3.0.{stamp}.tar.gz"
            url = f"{CHIRPS_URL}/{filename}"
            destination = RAW / "chirps_v3_mensal_latam" / filename
            entries.append(download(url, destination, validate_tar_gz))
            print(f"CHIRPS {stamp} concluído ({len(entries)} arquivos registrados).")

    for year in range(START_FIRE_YEAR, END_FIRE_YEAR + 1):
        filename = f"focos_br_ref_{year}.zip"
        url = f"{INPE_URL}/{filename}"
        destination = RAW / "inpe_focos_sat_ref" / filename
        entries.append(download(url, destination, validate_zip))
        print(f"INPE {year} concluído ({len(entries)} arquivos registrados).")

    manifest = {
        "collected_at_utc": datetime.now(timezone.utc).isoformat(),
        "periods": {
            "precipitation_monthly": f"{START_RAIN_YEAR}-01 a {END_RAIN_YEAR}-{END_RAIN_MONTH:02d}",
            "fire_reference_satellite": f"{START_FIRE_YEAR} a {END_FIRE_YEAR}",
            "oni": "série histórica disponível na página NOAA CPC ONI v6",
        },
        "total_bytes": sum(item["bytes"] for item in entries),
        "files": entries,
    }
    (RAW / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Coleta concluída: {len(entries)} arquivos, {manifest['total_bytes'] / 1024**3:.2f} GiB baixados.")


if __name__ == "__main__":
    main()
