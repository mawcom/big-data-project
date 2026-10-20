"""Baixa observações climáticas globais e brasileiras disponíveis em 2026."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import gzip
import hashlib
import json
import re
import threading
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "raw"
YEAR = 2026
MAX_RAW_BYTES = 20_000_000_000
CHUNK_SIZE = 1024 * 1024
USER_AGENT = "big-data-project/1.0 (coleta educacional)"
BASE_RAW_BYTES = 0
NOVOS_BYTES = 0
TRAVA_ORCAMENTO = threading.Lock()

GHCN_URL = f"https://www.ncei.noaa.gov/pub/data/ghcn/daily/by_year/{YEAR}.csv.gz"
INMET_URL = f"https://portal.inmet.gov.br/uploads/dadoshistoricos/{YEAR}.zip"
ICOADS_CATALOG = "https://www.ncei.noaa.gov/thredds/catalog/international-comprehensive-ocean-atmosphere-dataset-icoads/daily"
ICOADS_FILESERVER = "https://www.ncei.noaa.gov/thredds/fileServer"
NOAAGLOBALTEMP_INDEX = "https://www.ncei.noaa.gov/data/noaa-global-surface-temperature/v6.1/access/gridded/"


def tamanho_raw() -> int:
    return sum(path.stat().st_size for path in RAW.rglob("*") if path.is_file())


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(CHUNK_SIZE), b""):
            digest.update(bloco)
    return digest.hexdigest()


def solicitar(url: str, timeout: int = 60) -> urllib.request.urlopen:
    requisicao = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return urllib.request.urlopen(requisicao, timeout=timeout)


def baixar(url: str, destino: Path, tipo: str, limite: int = MAX_RAW_BYTES) -> dict[str, object]:
    global NOVOS_BYTES
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.exists() and destino.stat().st_size:
        validar(destino, tipo)
        return registro(url, destino, "já existia")

    temporario = destino.with_name(destino.name + ".part")
    temporario.unlink(missing_ok=True)
    bytes_transferidos = 0
    try:
        with solicitar(url, timeout=120) as resposta, temporario.open("wb") as saida:
            while bloco := resposta.read(CHUNK_SIZE):
                with TRAVA_ORCAMENTO:
                    if BASE_RAW_BYTES + NOVOS_BYTES + len(bloco) > limite:
                        raise ValueError(f"O download excederia o limite bruto de {limite / 1024**3:.1f} GiB.")
                    NOVOS_BYTES += len(bloco)
                    bytes_transferidos += len(bloco)
                saida.write(bloco)
        validar(temporario, tipo)
        temporario.replace(destino)
    except Exception:
        with TRAVA_ORCAMENTO:
            NOVOS_BYTES -= bytes_transferidos
        raise
    finally:
        temporario.unlink(missing_ok=True)

    return registro(url, destino, "baixado")


def validar(caminho: Path, tipo: str) -> None:
    with caminho.open("rb") as arquivo:
        assinatura = arquivo.read(8)
    if tipo == "gzip":
        if not assinatura.startswith(b"\x1f\x8b"):
            raise ValueError(f"Arquivo GZIP inválido: {caminho.name}")
        with gzip.open(caminho, "rb") as arquivo:
            arquivo.read(1)
    elif tipo == "zip":
        if not assinatura.startswith(b"PK"):
            raise ValueError(f"Arquivo ZIP inválido: {caminho.name}")
        with zipfile.ZipFile(caminho) as pacote:
            if not pacote.namelist():
                raise ValueError(f"Arquivo ZIP vazio: {caminho.name}")
    elif tipo == "netcdf":
        if not (assinatura.startswith(b"CDF") or assinatura.startswith(b"\x89HDF")):
            raise ValueError(f"Arquivo NetCDF inválido: {caminho.name}")
    elif caminho.stat().st_size == 0:
        raise ValueError(f"Arquivo vazio: {caminho.name}")


def registro(url: str, caminho: Path, estado: str) -> dict[str, object]:
    return {
        "url": url,
        "arquivo": caminho.relative_to(ROOT).as_posix(),
        "bytes": caminho.stat().st_size,
        "sha256": sha256(caminho),
        "estado": estado,
    }


def arquivos_icoads_2026() -> list[tuple[str, str]]:
    arquivos_por_dia: dict[str, tuple[tuple[int, int, int], str]] = {}
    hoje = datetime.now(timezone.utc).date()
    for mes in range(1, hoje.month + 1 if hoje.year == YEAR else 13):
        url = f"{ICOADS_CATALOG}/{YEAR}/{mes:02d}/catalog.xml"
        try:
            with solicitar(url) as resposta:
                catalogo = ElementTree.parse(resposta).getroot()
        except urllib.error.HTTPError as erro:
            if erro.code == 404:
                continue
            raise

        for elemento in catalogo.iter():
            caminho = elemento.attrib.get("urlPath")
            if not caminho:
                continue
            nome = caminho.rsplit("/", 1)[-1]
            encontrado = re.search(r"_d(\d{8})_c(\d{8})\.nc$", nome)
            if not encontrado:
                continue
            data_observacao, data_criacao = encontrado.groups()
            if data_observacao[:4] != str(YEAR) or data_observacao > hoje.strftime("%Y%m%d"):
                continue
            versao = re.search(r"icoads(\d+)\.(\d+)\.(\d+)_", nome)
            ranking = (int(data_criacao), *(int(parte) for parte in versao.groups())) if versao else (int(data_criacao), 0, 0, 0)
            atual = arquivos_por_dia.get(data_observacao)
            if atual is None or ranking > atual[0]:
                arquivos_por_dia[data_observacao] = (ranking, caminho)

    return [
        (data, f"{ICOADS_FILESERVER}/{caminho}")
        for data, (_, caminho) in sorted(arquivos_por_dia.items())
    ]


def baixar_icoads() -> tuple[list[dict[str, object]], list[str]]:
    arquivos = arquivos_icoads_2026()
    if not arquivos:
        raise RuntimeError("A NOAA não publicou arquivos diários do ICOADS para 2026 neste catálogo.")

    registros = []
    falhas = []
    destino_base = RAW / "icoads" / str(YEAR)
    with ThreadPoolExecutor(max_workers=6) as executor:
        futuras = {
            executor.submit(baixar, url, destino_base / f"icoads_{data}.nc", "netcdf"): data
            for data, url in arquivos
        }
        for numero, futura in enumerate(as_completed(futuras), start=1):
            data = futuras[futura]
            try:
                registros.append(futura.result())
                print(f"ICOADS {data}: {numero}/{len(arquivos)}", flush=True)
            except Exception as erro:
                falhas.append(f"{data}: {erro}")
                print(f"ICOADS {data}: falhou ({numero}/{len(arquivos)}): {erro}", flush=True)
    return registros, falhas


def baixar_globaltemp() -> dict[str, object]:
    with solicitar(NOAAGLOBALTEMP_INDEX) as resposta:
        pagina = resposta.read().decode("utf-8", errors="replace")
    nomes = re.findall(r'href="(NOAAGlobalTemp_v6\.1\.0_gridded_s185001_e(\d{6})_c[^"/]+\.nc)"', pagina)
    if not nomes:
        raise RuntimeError("Não encontrei NetCDF na pasta NOAA GlobalTemp v6.1.")
    nome, _ = max(nomes, key=lambda item: item[1])
    url = urllib.parse.urljoin(NOAAGLOBALTEMP_INDEX, nome)
    destino = RAW / "noaa_globaltemp" / nome
    return baixar(url, destino, "netcdf")


def selecionar_fontes(nomes: list[str]) -> list[str]:
    validos = {"icoads", "ghcn_daily", "noaa_globaltemp", "inmet"}
    if "todas" in nomes:
        return ["icoads", "ghcn_daily", "noaa_globaltemp", "inmet"]
    desconhecidos = set(nomes) - validos
    if desconhecidos:
        raise ValueError(f"Fontes desconhecidas: {', '.join(sorted(desconhecidos))}")
    return list(dict.fromkeys(nomes))


def main() -> None:
    global BASE_RAW_BYTES, NOVOS_BYTES
    analisador = argparse.ArgumentParser(description=__doc__)
    analisador.add_argument(
        "--fontes",
        nargs="+",
        default=["todas"],
        choices=["todas", "icoads", "ghcn_daily", "noaa_globaltemp", "inmet"],
        help="Fontes para baixar (padrão: todas).",
    )
    argumentos = analisador.parse_args()
    fontes = selecionar_fontes(argumentos.fontes)
    RAW.mkdir(parents=True, exist_ok=True)
    if tamanho_raw() > MAX_RAW_BYTES:
        raise ValueError("A pasta raw/ já ultrapassa o limite de 20 GiB.")
    BASE_RAW_BYTES = tamanho_raw()
    NOVOS_BYTES = 0

    resultados: list[dict[str, object]] = []
    erros: list[dict[str, str]] = []
    tarefas = {
        "icoads": baixar_icoads,
        "ghcn_daily": lambda: [baixar(
            GHCN_URL,
            RAW / "ghcn_daily" / f"{YEAR}.csv.gz",
            "gzip",
        )],
        "noaa_globaltemp": lambda: [baixar_globaltemp()],
        "inmet": lambda: [baixar(
            INMET_URL,
            RAW / "inmet" / f"{YEAR}.zip",
            "zip",
        )],
    }

    for fonte in fontes:
        try:
            if fonte == "icoads":
                registros, falhas = baixar_icoads()
                resultados.extend(registros)
                if falhas:
                    erros.append({"fonte": fonte, "erro": "; ".join(falhas)})
            else:
                resultados.extend(tarefas[fonte]())
        except Exception as erro:
            erros.append({"fonte": fonte, "erro": str(erro)})
            print(f"Falha em {fonte}: {erro}")

    manifesto = {
        "ano": YEAR,
        "coletado_em_utc": datetime.now(timezone.utc).isoformat(),
        "limite_bytes": MAX_RAW_BYTES,
        "bytes_baixados_ou_reutilizados": sum(int(item["bytes"]) for item in resultados),
        "fontes": resultados,
        "fontes_nao_coletadas": {
            "ana_hidroweb": (
                "Não incluída nesta execução; o acesso à API HidroWeb atual depende de credencial. "
                "A coleta brasileira de 2026 inclui chuva e temperatura horárias do pacote anual do INMET."
            )
        },
        "erros": erros,
        "observacao": (
            "ICOADS contém observações diárias marítimas de 2026 disponíveis no catálogo; "
            "GHCN-Daily é o arquivo global anual de 2026; INMET é o pacote anual de 2026; "
            "NOAA GlobalTemp é a grade global mais recente, com histórico desde 1850 e meses de 2026 disponíveis."
        ),
    }
    caminho_manifesto = RAW / "manifesto_coleta_2026.json"
    caminho_manifesto.write_text(json.dumps(manifesto, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Manifesto: {caminho_manifesto.relative_to(ROOT)}")
    print(f"Fontes concluídas: {len(resultados)} arquivos; falhas: {len(erros)}.")
    if erros:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
