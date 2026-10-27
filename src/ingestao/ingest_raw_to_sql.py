"""Carrega os arquivos de raw/ em tabelas DuckDB sem padronizar os valores."""

from __future__ import annotations

import gzip
import hashlib
import html
import json
import os
from pathlib import Path
import re
import tarfile
import zipfile

import duckdb
import netCDF4
import numpy as np
import pandas as pd


RAIZ = Path(__file__).resolve().parents[2]
BRUTOS = RAIZ / "raw"
BANCO = RAIZ / "raw.duckdb"
TAMANHO_LOTE = 50_000


def nome_sql(nome: str) -> str:
    return '"' + nome.replace('"', '""') + '"'


def origem(caminho: Path, membro: str | None = None) -> str:
    nome = caminho.resolve().relative_to(RAIZ).as_posix()
    return f"{nome}::{membro}" if membro else nome


def formatar_volume(volume: int) -> str:
    if volume >= 1_000_000_000:
        return f"{volume / 1_000_000_000:.2f} GB"
    if volume >= 1_000_000:
        return f"{volume / 1_000_000:.2f} MB"
    return f"{volume / 1_000:.2f} KB"


def validar_arquivos_repetidos(entradas: list[Path]) -> None:
    por_tamanho = {}
    for caminho in entradas:
        por_tamanho.setdefault(caminho.stat().st_size, []).append(caminho)
    for caminhos in por_tamanho.values():
        if len(caminhos) < 2:
            continue
        vistos = {}
        for caminho in caminhos:
            digest = hashlib.sha256()
            with caminho.open("rb") as arquivo:
                for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
                    digest.update(bloco)
            anterior = vistos.get(digest.digest())
            if anterior is not None:
                raise ValueError(f"Arquivos brutos idênticos: {origem(anterior)} e {origem(caminho)}.")
            vistos[digest.digest()] = caminho


def inserir_lote(conexao: duckdb.DuckDBPyConnection, tabela: str, quadro: pd.DataFrame, arquivo: str) -> int:
    if quadro.empty:
        return 0
    quadro["_arquivo_origem"] = arquivo
    if quadro.columns.duplicated().any():
        raise ValueError(f"Colunas repetidas em {arquivo}.")
    conexao.register("_lote", quadro)
    try:
        existente = conexao.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_name = ?", [tabela]
        ).fetchone()[0]
        if not existente:
            conexao.execute(f"CREATE TABLE {nome_sql(tabela)} AS SELECT * FROM _lote LIMIT 0")
        else:
            colunas = {
                item[1] for item in conexao.execute(f"PRAGMA table_info({nome_sql(tabela)})").fetchall()
            }
            tipos = conexao.execute("DESCRIBE SELECT * FROM _lote").fetchall()
            for coluna, tipo, *_ in tipos:
                if coluna not in colunas:
                    conexao.execute(f"ALTER TABLE {nome_sql(tabela)} ADD COLUMN {nome_sql(coluna)} {tipo}")
        conexao.execute(f"INSERT INTO {nome_sql(tabela)} BY NAME SELECT * FROM _lote")
    finally:
        conexao.unregister("_lote")
    return len(quadro)


def carregar_csv_zip(
    conexao: duckdb.DuckDBPyConnection, pasta: str, tabela: str, separador: str, pular: int, codificacao: str,
) -> tuple[int, int]:
    linhas = 0
    arquivos = 0
    for caminho in sorted((BRUTOS / pasta).glob("*.zip")):
        with zipfile.ZipFile(caminho) as pacote:
            for membro in pacote.namelist():
                if not membro.lower().endswith(".csv"):
                    continue
                with pacote.open(membro) as fluxo:
                    leitor = pd.read_csv(
                        fluxo, sep=separador, skiprows=pular, encoding=codificacao,
                        dtype=str, keep_default_na=False, chunksize=TAMANHO_LOTE,
                    )
                    for quadro in leitor:
                        linhas += inserir_lote(conexao, tabela, quadro, origem(caminho, membro))
                arquivos += 1
    return arquivos, linhas


def carregar_ghcn(conexao: duckdb.DuckDBPyConnection) -> tuple[int, int]:
    nomes = ["ID", "DATE", "ELEMENT", "DATA_VALUE", "M_FLAG", "Q_FLAG", "S_FLAG", "OBS_TIME"]
    linhas = 0
    arquivos = 0
    for caminho in sorted((BRUTOS / "ghcn_daily").glob("*.csv.gz")):
        with gzip.open(caminho, "rt", encoding="ascii") as fluxo:
            leitor = pd.read_csv(
                fluxo, header=None, names=nomes, dtype=str,
                keep_default_na=False, chunksize=TAMANHO_LOTE,
            )
            for quadro in leitor:
                linhas += inserir_lote(conexao, "ghcn_daily", quadro, origem(caminho))
        arquivos += 1
    return arquivos, linhas


def carregar_oni(conexao: duckdb.DuckDBPyConnection) -> tuple[int, int]:
    caminho = BRUTOS / "enso" / "oni_cpc_v6.html"
    if not caminho.exists():
        return 0, 0
    pagina = caminho.read_text(encoding="utf-8", errors="replace")
    colunas = ["Year", "DJF", "JFM", "FMA", "MAM", "AMJ", "MJJ", "JJA", "JAS", "ASO", "SON", "OND", "NDJ"]
    linhas = []
    for linha in re.findall(r"<tr[^>]*>.*?</tr>", pagina, flags=re.IGNORECASE | re.DOTALL):
        celulas = re.findall(r"<td\b[^>]*>(.*?)</td>", linha, flags=re.IGNORECASE | re.DOTALL)
        partes = [html.unescape(re.sub(r"<[^>]+>", " ", celula)).strip() or None for celula in celulas]
        if 1 < len(partes) <= len(colunas) and partes[0] and re.fullmatch(r"(?:19|20)\d{2}", partes[0]):
            linhas.append(partes + [None] * (len(colunas) - len(partes)))
    if not linhas:
        raise ValueError(f"Não encontrei os valores ONI em {caminho.name}.")
    return 1, inserir_lote(conexao, "oni", pd.DataFrame(linhas, columns=colunas), origem(caminho))


def carregar_chirps(conexao: duckdb.DuckDBPyConnection) -> tuple[int, int]:
    arquivos = 0
    linhas = 0
    for caminho in sorted((BRUTOS / "chirps_v3_mensal_latam").glob("*.tar.gz")):
        with tarfile.open(caminho, "r:gz") as pacote:
            cabecalho = next(m for m in pacote.getmembers() if m.name.lower().endswith(".hdr"))
            grade = next(m for m in pacote.getmembers() if m.name.lower().endswith(".bil"))
            campos = dict(
                linha.split(None, 1) for linha in pacote.extractfile(cabecalho).read().decode("ascii").splitlines()
            )
            if campos["NBANDS"] != "1" or campos["NBITS"] != "32" or campos["PIXELTYPE"] != "FLOAT":
                raise ValueError(f"Formato BIL inesperado em {caminho.name}.")
            colunas = int(campos["NCOLS"])
            total_linhas = int(campos["NROWS"])
            tipo = "<f4" if campos["BYTEORDER"] == "I" else ">f4"
            longitudes = float(campos["ULXMAP"]) + np.arange(colunas) * float(campos["XDIM"])
            with pacote.extractfile(grade) as fluxo:
                for inicio in range(0, total_linhas, 100):
                    quantidade = min(100, total_linhas - inicio)
                    bloco = fluxo.read(quantidade * colunas * 4)
                    valores = np.frombuffer(bloco, dtype=tipo)
                    if valores.size != quantidade * colunas:
                        raise ValueError(f"Grade BIL incompleta em {caminho.name}.")
                    indices = np.arange(inicio, inicio + quantidade)
                    quadro = pd.DataFrame({
                        "linha": np.repeat(indices, colunas),
                        "coluna": np.tile(np.arange(colunas), quantidade),
                        "latitude": np.repeat(float(campos["ULYMAP"]) - indices * float(campos["YDIM"]), colunas),
                        "longitude": np.tile(longitudes, quantidade),
                        "precipitacao": valores.astype("float32", copy=False),
                    })
                    linhas += inserir_lote(conexao, "chirps", quadro, origem(caminho))
        arquivos += 1
    return arquivos, linhas


def carregar_parquet(conexao: duckdb.DuckDBPyConnection, pasta: str, tabela: str) -> tuple[int, int]:
    arquivos = 0
    linhas = 0
    for caminho in sorted((BRUTOS / "ons" / pasta).glob("*.parquet")):
        quadro = conexao.execute("SELECT * FROM read_parquet(?)", [str(caminho)]).fetchdf()
        linhas += inserir_lote(conexao, tabela, quadro, origem(caminho))
        arquivos += 1
    return arquivos, linhas


def valores_netcdf(variavel: netCDF4.Variable, inicio: int, fim: int):
    valores = np.asarray(variavel[inicio:fim])
    if valores.ndim == 1:
        if valores.dtype.kind == "S":
            return [item.decode("utf-8", errors="replace") for item in valores]
        return valores
    if valores.dtype.kind == "S" and valores.ndim == 2:
        return netCDF4.chartostring(valores).astype(str)
    return [json.dumps(item.tolist()) for item in valores]


def carregar_icoads(
    conexao: duckdb.DuckDBPyConnection, caminhos: list[Path] | None = None,
) -> tuple[int, int]:
    arquivos = 0
    linhas = 0
    lista = caminhos if caminhos is not None else sorted((BRUTOS / "icoads").rglob("*.nc"))
    for caminho in lista:
        with netCDF4.Dataset(caminho) as dados:
            dados.set_auto_maskandscale(False)
            dimensao = "obs" if "obs" in dados.dimensions else next(
                (nome for nome, dim in dados.dimensions.items() if dim.isunlimited()), None
            )
            if dimensao is None:
                dimensao = max(dados.dimensions, key=lambda nome: len(dados.dimensions[nome]))
            total = len(dados.dimensions[dimensao])
            variaveis = {
                nome: var for nome, var in dados.variables.items()
                if var.dimensions and var.dimensions[0] == dimensao
            }
            if not variaveis:
                raise ValueError(f"Não encontrei variáveis de observação em {caminho.name}.")
            for inicio in range(0, total, TAMANHO_LOTE):
                fim = min(inicio + TAMANHO_LOTE, total)
                quadro = pd.DataFrame({
                    nome: valores_netcdf(var, inicio, fim) for nome, var in variaveis.items()
                })
                linhas += inserir_lote(conexao, "icoads", quadro, origem(caminho))
        arquivos += 1
        if arquivos % 25 == 0:
            print(f"icoads: {arquivos}/{len(lista)} arquivo(s), {linhas} linha(s).", flush=True)
    return arquivos, linhas


def carregar_globaltemp(conexao: duckdb.DuckDBPyConnection) -> tuple[int, int]:
    arquivos = 0
    linhas = 0
    caminhos = sorted((BRUTOS / "noaa_globaltemp").glob("*.nc"))
    if len(caminhos) > 1:
        print(f"noaa_globaltemp: usando {caminhos[-1].name}; ignorando {len(caminhos) - 1} versão(ões) anterior(es).")
    for caminho in caminhos[-1:]:
        with netCDF4.Dataset(caminho) as dados:
            dados.set_auto_maskandscale(False)
            tempo = next(nome for nome in dados.dimensions if nome.lower() == "time")
            latitude = next(nome for nome in dados.dimensions if nome.lower() in ("lat", "latitude"))
            longitude = next(nome for nome in dados.dimensions if nome.lower() in ("lon", "longitude"))
            altura = next(nome for nome in dados.dimensions if nome.lower() == "z")
            latitudes = np.asarray(dados.variables[latitude][:])
            longitudes = np.asarray(dados.variables[longitude][:])
            alturas = np.asarray(dados.variables[altura][:])
            campos = {
                nome: var for nome, var in dados.variables.items()
                if set(var.dimensions) == {tempo, altura, latitude, longitude} and len(var.dimensions) == 4
            }
            if not campos:
                raise ValueError(f"Não encontrei variáveis de grade em {caminho.name}.")
            lat_grade, lon_grade = np.meshgrid(latitudes, longitudes, indexing="ij")
            for indice in range(len(dados.dimensions[tempo])):
                for nivel, valor_altura in enumerate(alturas):
                    quadro = pd.DataFrame({
                        tempo: np.repeat(np.asarray(dados.variables[tempo][indice]), lat_grade.size),
                        altura: np.repeat(valor_altura, lat_grade.size),
                        latitude: lat_grade.ravel(),
                        longitude: lon_grade.ravel(),
                    })
                    for nome, var in campos.items():
                        fatias = [slice(None)] * 4
                        fatias[var.dimensions.index(tempo)] = indice
                        fatias[var.dimensions.index(altura)] = nivel
                        bloco = np.asarray(var[tuple(fatias)])
                        dimensoes_grade = [item for item in var.dimensions if item not in (tempo, altura)]
                        eixos = [dimensoes_grade.index(item) for item in (latitude, longitude)]
                        quadro[nome] = np.transpose(bloco, axes=eixos).ravel()
                    linhas += inserir_lote(conexao, "noaa_globaltemp", quadro, origem(caminho))
        arquivos += 1
    return arquivos, linhas


def main() -> None:
    entradas = [
        arquivo for arquivo in BRUTOS.rglob("*")
        if arquivo.is_file() and arquivo.suffix.lower() in (".zip", ".gz", ".html", ".nc", ".parquet")
    ]
    if not entradas:
        raise SystemExit("Não há arquivos de dados em raw/ para converter.")
    validar_arquivos_repetidos(entradas)

    temporario = BANCO.with_name(f"{BANCO.name}.{os.getpid()}.tmp")
    resultados = {}
    conexao = duckdb.connect(str(temporario))
    try:
        etapas = (
            ("oni", carregar_oni),
            ("chirps", carregar_chirps),
            ("inpe", lambda con: carregar_csv_zip(con, "inpe_focos_sat_ref", "inpe", ",", 0, "utf-8")),
            ("inmet", lambda con: carregar_csv_zip(con, "inmet", "inmet", ";", 8, "latin1")),
            ("ghcn_daily", carregar_ghcn),
            ("icoads", carregar_icoads),
            ("noaa_globaltemp", carregar_globaltemp),
            ("ons_balanco", lambda con: carregar_parquet(con, "balanco_energia_subsistema", "ons_balanco")),
            ("ons_ear", lambda con: carregar_parquet(con, "ear_diario_subsistema", "ons_ear")),
        )
        for nome, carregar in etapas:
            arquivos, linhas = carregar(conexao)
            resultados[nome] = (arquivos, linhas)
            print(f"{nome}: {arquivos} arquivo(s), {linhas} linha(s).", flush=True)
        conexao.close()
        os.replace(temporario, BANCO)
    except Exception:
        conexao.close()
        temporario.unlink(missing_ok=True)
        raise

    print(f"Carga total: {sum(linhas for _, linhas in resultados.values())} linhas de {len(entradas)} arquivo(s).")
    print(f"Volume dos arquivos de entrada: {formatar_volume(sum(item.stat().st_size for item in entradas))}.")
    print(f"Volume do banco DuckDB: {formatar_volume(BANCO.stat().st_size)} ({BANCO.name}).")


if __name__ == "__main__":
    main()
