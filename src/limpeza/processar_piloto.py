"""Processa um ano real de ONI, CHIRPS e focos INPE para as UFs do Nordeste.

Uso: python src/limpeza/processar_piloto.py --ano 2024
Entradas ficam em raw/; as saídas pequenas ficam em amostras/piloto_<ano>/.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import tarfile
import unicodedata
import zipfile

import numpy as np
import pandas as pd


RAIZ = Path(__file__).resolve().parents[2]
RAW = RAIZ / "raw"
DIM_UF = RAIZ / "src" / "bigdata" / "referencias" / "ufs_nordeste.csv"
MALHA = RAW / "referencias" / "ufs_ibge.geojson"
JANELAS_ONI = ["DJF", "JFM", "FMA", "MAM", "AMJ", "MJJ", "JJA", "JAS", "ASO", "SON", "OND", "NDJ"]


def sha256(caminho: Path) -> str:
    digest = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def exigir(caminho: Path) -> Path:
    if not caminho.is_file():
        raise FileNotFoundError(f"Entrada ausente: {caminho}. Execute a coleta primeiro.")
    return caminho


def validar_manifesto(ano: int) -> dict:
    caminho = RAW / "manifesto_coleta.json"
    manifesto = json.loads(caminho.read_text(encoding="utf-8")) if caminho.is_file() else {}
    entradas = {item["arquivo"]: item for item in manifesto.get("arquivos", [])}
    esperados = [
        RAW / "enso" / "oni_cpc_v6.html",
        RAW / "inpe_focos_sat_ref" / f"focos_br_ref_{ano}.zip",
        *[RAW / "chirps_v3_mensal_latam" / f"chirps-v3.0.{ano}{mes:02d}.tar.gz" for mes in range(1, 13)],
    ]
    registrados = 0
    sem_registro = []
    for arquivo in esperados:
        nome = arquivo.relative_to(RAIZ).as_posix()
        entrada = entradas.get(nome)
        exigir(arquivo)
        if entrada is None:
            sem_registro.append(nome)
            continue
        if entrada.get("estado") not in {"baixado", "já existia"}:
            raise ValueError(f"Manifesto registra falha para: {nome}")
        if arquivo.stat().st_size != entrada.get("bytes") or sha256(arquivo) != entrada.get("sha256"):
            raise ValueError(f"Arquivo mudou desde a coleta: {nome}")
        registrados += 1
    return {"arquivo": caminho.relative_to(RAIZ).as_posix() if caminho.is_file() else None,
            "arquivos_verificados": registrados, "arquivos_locais_sem_registro": sem_registro,
            "coletado_em_utc": manifesto.get("coletado_em_utc")}


def dimensao_uf() -> pd.DataFrame:
    quadro = pd.read_csv(DIM_UF, sep=";", dtype=str)
    if len(quadro) != 9 or quadro.uf_codigo_ibge.nunique() != 9:
        raise ValueError("A dimensão precisa conter as nove UFs do Nordeste uma vez cada.")
    return quadro


def serie_oni() -> tuple[pd.DataFrame, Path]:
    """Lê o histórico ONI completo e classifica a fase ENSO de cada mês."""
    caminho = exigir(RAW / "enso" / "oni_cpc_v6.html")
    pagina = caminho.read_text(encoding="utf-8", errors="replace")
    registros = []
    for linha in re.findall(r"<tr[^>]*>.*?</tr>", pagina, flags=re.I | re.S):
        celulas = re.findall(r"<td\b[^>]*>(.*?)</td>", linha, flags=re.I | re.S)
        partes = [html.unescape(re.sub(r"<[^>]+>", " ", celula)).strip() for celula in celulas]
        # O ano em curso tem menos de 12 janelas publicadas.
        if len(partes) < 2 or not re.fullmatch(r"(?:19|20)\d{2}", partes[0]):
            continue
        for mes, (janela, texto) in enumerate(zip(JANELAS_ONI, partes[1:13]), start=1):
            try:
                valor = float(texto)
            except ValueError:
                continue
            registros.append((int(partes[0]), mes, janela, valor))
    serie = pd.DataFrame(registros, columns=["ano", "mes", "janela_oni", "oni_c"])
    if serie.empty or serie.duplicated(["ano", "mes"]).any():
        raise ValueError("Tabela ONI vazia ou com meses duplicados; revise o HTML da NOAA.")
    serie = serie.sort_values(["ano", "mes"]).reset_index(drop=True)
    competencias = pd.PeriodIndex.from_fields(year=serie.ano, month=serie.mes, freq="M")
    if len(competencias) != len(pd.period_range(competencias[0], competencias[-1], freq="M")):
        raise ValueError("Há meses ausentes no histórico ONI; a regra de cinco janelas requer sequência contínua.")
    # Episódio histórico: ao menos cinco temporadas trimestrais consecutivas
    # com ONI >= +0,5 (El Niño) ou <= -0,5 (La Niña).
    fase = np.full(len(serie), "neutro", dtype=object)
    for limite, rotulo in ((0.5, "El Niño"), (-0.5, "La Niña")):
        atende = serie.oni_c.ge(limite).to_numpy() if limite > 0 else serie.oni_c.le(limite).to_numpy()
        inicio = None
        for pos in range(len(atende) + 1):
            if pos < len(atende) and atende[pos]:
                if inicio is None:
                    inicio = pos
            elif inicio is not None:
                if pos - inicio >= 5:
                    fase[inicio:pos] = rotulo
                inicio = None
    serie["fase_enso"] = fase
    return serie, caminho


def ler_oni(ano: int) -> tuple[pd.DataFrame, dict]:
    serie, caminho = serie_oni()
    resultado = serie.loc[serie.ano.eq(ano), ["ano", "mes", "janela_oni", "oni_c", "fase_enso"]].copy()
    if len(resultado) != 12:
        raise ValueError(f"ONI de {ano} tem {len(resultado)} meses, não 12.")
    return resultado, {"arquivo": caminho.relative_to(RAIZ).as_posix(), "sha256": sha256(caminho), "linhas_historicas": len(serie)}


def normalizar_nome(valor: str) -> str:
    sem_acentos = unicodedata.normalize("NFKD", str(valor))
    return "".join(c for c in sem_acentos if not unicodedata.combining(c)).upper().strip()


def ler_inpe(ano: int, ufs: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    caminho = exigir(RAW / "inpe_focos_sat_ref" / f"focos_br_ref_{ano}.zip")
    codigos = {normalizar_nome(linha.uf_nome): linha.uf_codigo_ibge for linha in ufs.itertuples()}
    nomes = {linha.uf_codigo_ibge: linha.uf_sigla for linha in ufs.itertuples()}
    totais: dict[tuple[str, int], int] = {}
    lidas = invalidas = fora_periodo = fora_nordeste = 0
    minimo = maximo = None
    with zipfile.ZipFile(caminho) as pacote:
        membros = [nome for nome in pacote.namelist() if nome.lower().endswith(".csv")]
        if len(membros) != 1:
            raise ValueError(f"Esperado um CSV no ZIP anual do INPE: {caminho}")
        with pacote.open(membros[0]) as fluxo:
            for lote in pd.read_csv(fluxo, dtype=str, chunksize=50_000, keep_default_na=False):
                if not {"data_pas", "estado"}.issubset(lote.columns):
                    raise ValueError("CSV INPE sem data_pas/estado; revise o esquema da fonte.")
                lidas += len(lote)
                datas = pd.to_datetime(lote["data_pas"], errors="coerce")
                invalidas += int(datas.isna().sum())
                validas = datas.dropna()
                if not validas.empty:
                    atual_min, atual_max = validas.min(), validas.max()
                    minimo = atual_min if minimo is None else min(minimo, atual_min)
                    maximo = atual_max if maximo is None else max(maximo, atual_max)
                no_ano = datas.dt.year.eq(ano)
                fora_periodo += int((datas.notna() & ~no_ano).sum())
                codigo = lote["estado"].map(normalizar_nome).map(codigos)
                fora_nordeste += int((no_ano & codigo.isna()).sum())
                partes = pd.DataFrame({"uf_codigo_ibge": codigo, "mes": datas.dt.month})
                partes = partes.loc[no_ano & partes.uf_codigo_ibge.notna()]
                for (uf, mes), qtd in partes.groupby(["uf_codigo_ibge", "mes"]).size().items():
                    totais[(uf, int(mes))] = totais.get((uf, int(mes)), 0) + int(qtd)
    completo = minimo is not None and minimo.year == ano and minimo.month == 1 and maximo.year == ano and maximo.month == 12
    if not completo:
        raise ValueError("Arquivo INPE não apresenta registros em janeiro e dezembro; não é seguro preencher meses sem focos com zero.")
    linhas = [
        {"ano": ano, "mes": mes, "uf_codigo_ibge": uf, "uf_sigla": nomes[uf], "focos_inpe": totais.get((uf, mes), 0)}
        for uf in ufs.uf_codigo_ibge for mes in range(1, 13)
    ]
    return pd.DataFrame(linhas), {
        "arquivo": caminho.relative_to(RAIZ).as_posix(), "sha256": sha256(caminho),
        "linhas_lidas": lidas, "datas_invalidas": invalidas, "fora_do_ano": fora_periodo,
        "fora_do_nordeste": fora_nordeste, "focos_nordeste": sum(totais.values()),
        "primeira_data": str(minimo), "ultima_data": str(maximo), "arquivo_anual_com_janeiro_e_dezembro": completo,
    }


def cabecalho_chirps(caminho: Path) -> tuple[dict, bytes]:
    with tarfile.open(caminho, "r:gz") as pacote:
        membros = pacote.getmembers()
        hdr = next((m for m in membros if m.name.lower().endswith(".hdr")), None)
        bil = next((m for m in membros if m.name.lower().endswith(".bil")), None)
        if hdr is None or bil is None:
            raise ValueError(f"Arquivo CHIRPS sem grade ou cabeçalho: {caminho}")
        campos = dict(linha.split(None, 1) for linha in pacote.extractfile(hdr).read().decode("ascii").splitlines())
        if (campos["LAYOUT"], campos["NBANDS"], campos["NBITS"], campos["PIXELTYPE"]) != ("BIL", "1", "32", "FLOAT"):
            raise ValueError(f"Formato CHIRPS inesperado: {caminho}")
        if campos["BYTEORDER"] not in {"I", "M"}:
            raise ValueError(f"Ordem de bytes CHIRPS inesperada: {caminho}")
        dados = pacote.extractfile(bil).read()
    esperado = int(campos["NCOLS"]) * int(campos["NROWS"]) * 4
    if len(dados) != esperado:
        raise ValueError(f"Grade CHIRPS incompleta: {caminho}")
    return campos, dados


def anel_contem_pontos(xs: np.ndarray, ys: np.ndarray, anel: list) -> np.ndarray:
    dentro = np.zeros(xs.size, dtype=bool)
    for (x1, y1), (x2, y2) in zip(anel, anel[1:]):
        cruza = (y1 > ys) != (y2 > ys)
        if not cruza.any():
            continue
        limite = (x2 - x1) * (ys[cruza] - y1) / (y2 - y1) + x1
        dentro[cruza] ^= xs[cruza] < limite
    return dentro


def lookup_uf(campos: dict, ufs: pd.DataFrame) -> pd.DataFrame:
    geojson = json.loads(exigir(MALHA).read_text(encoding="utf-8"))
    features = {f["properties"]["CD_UF"]: f for f in geojson["features"]}
    if set(features) != set(ufs.uf_codigo_ibge):
        raise ValueError("Malha IBGE não contém exatamente as nove UFs da dimensão.")
    ncol, nlin = int(campos["NCOLS"]), int(campos["NROWS"])
    longitudes = float(campos["ULXMAP"]) + np.arange(ncol) * float(campos["XDIM"])
    latitudes = float(campos["ULYMAP"]) - np.arange(nlin) * float(campos["YDIM"])
    lista = []
    usados: set[int] = set()
    for uf in ufs.uf_codigo_ibge:
        geometria = features[uf]["geometry"]
        poligonos = geometria["coordinates"] if geometria["type"] == "MultiPolygon" else [geometria["coordinates"]]
        for poligono in poligonos:
            xs_borda = [p[0] for anel in poligono for p in anel]
            ys_borda = [p[1] for anel in poligono for p in anel]
            cols = np.flatnonzero((longitudes >= min(xs_borda)) & (longitudes <= max(xs_borda)))
            lins = np.flatnonzero((latitudes >= min(ys_borda)) & (latitudes <= max(ys_borda)))
            if not len(cols) or not len(lins):
                continue
            grade_linha, grade_coluna = np.meshgrid(lins, cols, indexing="ij")
            linha, coluna = grade_linha.ravel(), grade_coluna.ravel()
            xs, ys = longitudes[coluna], latitudes[linha]
            mascara = anel_contem_pontos(xs, ys, poligono[0])
            for buraco in poligono[1:]:
                mascara &= ~anel_contem_pontos(xs, ys, buraco)
            for l, c in zip(linha[mascara], coluna[mascara]):
                indice = int(l * ncol + c)
                if indice in usados:
                    raise ValueError("Célula CHIRPS atribuída a mais de uma UF; revise a malha.")
                usados.add(indice)
                lista.append((int(l), int(c), uf))
    resultado = pd.DataFrame(lista, columns=["linha", "coluna", "uf_codigo_ibge"])
    if resultado.empty or set(resultado.uf_codigo_ibge) != set(ufs.uf_codigo_ibge):
        raise ValueError("Nenhuma célula mapeada para uma ou mais UFs.")
    return resultado.sort_values(["uf_codigo_ibge", "linha", "coluna"]).reset_index(drop=True)


def ler_chirps(ano: int, ufs: pd.DataFrame, meses: list[int] | None = None) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    meses = meses or list(range(1, 13))
    caminhos = [exigir(RAW / "chirps_v3_mensal_latam" / f"chirps-v3.0.{ano}{mes:02d}.tar.gz") for mes in meses]
    cabecalho, dados = cabecalho_chirps(caminhos[0])
    lookup = lookup_uf(cabecalho, ufs)
    ncol, nlin = int(cabecalho["NCOLS"]), int(cabecalho["NROWS"])
    indices = lookup.linha.to_numpy() * ncol + lookup.coluna.to_numpy()
    registros = []
    estatisticas = []
    for posicao, (mes, caminho) in enumerate(zip(meses, caminhos)):
        campos, grade = (cabecalho, dados) if posicao == 0 else cabecalho_chirps(caminho)
        if campos != cabecalho:
            raise ValueError(f"Georreferência da grade CHIRPS mudou em {caminho}")
        tipo = "<f4" if campos["BYTEORDER"] == "I" else ">f4"
        valores = np.frombuffer(grade, dtype=tipo)
        if valores.size != ncol * nlin:
            raise ValueError(f"Tamanho CHIRPS inesperado: {caminho}")
        amostra = lookup[["uf_codigo_ibge"]].copy()
        amostra["chuva_mm"] = valores[indices]
        invalidas = ~np.isfinite(amostra.chuva_mm) | amostra.chuva_mm.lt(0)
        amostra.loc[invalidas, "chuva_mm"] = np.nan
        por_uf = amostra.groupby("uf_codigo_ibge").chuva_mm.agg(["mean", "count", "size"])
        for uf, linha in por_uf.iterrows():
            registros.append({"ano": ano, "mes": mes, "uf_codigo_ibge": uf,
                             "chuva_media_mm": round(float(linha["mean"]), 3) if linha["count"] else np.nan,
                             "celulas_validas": int(linha["count"]), "celulas_mapeadas": int(linha["size"]),
                             "cobertura_chuva_pct": round(100 * linha["count"] / linha["size"], 2)})
        estatisticas.append({"mes": mes, "arquivo": caminho.relative_to(RAIZ).as_posix(),
                             "sha256": sha256(caminho), "celulas_sem_valor": int(invalidas.sum())})
        print(f"CHIRPS {ano}-{mes:02d}: {len(amostra)} células mapeadas; {int(invalidas.sum())} inválidas.", flush=True)
    chuva = pd.DataFrame(registros).merge(ufs, on="uf_codigo_ibge", validate="many_to_one")
    return chuva, lookup, {"arquivos": estatisticas, "celulas_mapeadas": len(lookup),
                           "metodo_espacial": "centro_da_celula_em_malha_ibge_simplificada",
                           "agregacao": "media_aritmetica_de_celulas_validas; sem_peso_de_area"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ano", type=int, default=2024)
    args = parser.parse_args()
    ano = args.ano
    meta_manifesto = validar_manifesto(ano)
    ufs = dimensao_uf()
    oni, meta_oni = ler_oni(ano)
    fogo, meta_fogo = ler_inpe(ano, ufs)
    chuva, lookup, meta_chuva = ler_chirps(ano, ufs)
    chaves = ["ano", "mes", "uf_codigo_ibge"]
    fato = chuva.merge(fogo.drop(columns="uf_sigla"), on=chaves, validate="one_to_one")
    fato = fato.merge(oni, on=["ano", "mes"], validate="many_to_one")
    fato.insert(0, "competencia", pd.to_datetime(dict(year=fato.ano, month=fato.mes, day=1)).dt.strftime("%Y-%m-%d"))
    fato["fonte_chuva"] = "CHIRPS v3 mensal"
    fato["fonte_fogo"] = "INPE satelite de referencia"
    fato["fonte_enso"] = "NOAA CPC ONI v6"
    fato["data_status"] = "real_piloto"
    fato["qualidade_chuva"] = np.where(fato.cobertura_chuva_pct.eq(100), "piloto_sem_climatologia", "parcial_celulas_ausentes")
    fato["qualidade_fogo"] = "arquivo_anual_verificado"
    fato["anomalia_chuva_mm"] = np.nan  # Requer base mensal completa de 1991–2020.
    fato = fato.sort_values(["ano", "mes", "uf_codigo_ibge"]).reset_index(drop=True)
    if len(fato) != 108 or fato.duplicated(chaves).any() or fato["chuva_media_mm"].isna().any():
        raise ValueError("Fato mensal incompleto ou com chaves duplicadas.")
    resumo = fato.groupby(["ano", "mes", "janela_oni", "oni_c", "fase_enso"], as_index=False).agg(
        focos_nordeste=("focos_inpe", "sum"),
        chuva_media_ufs_mm=("chuva_media_mm", "mean"),
        ufs_com_chuva=("chuva_media_mm", "count"),
    )
    resumo["chuva_media_ufs_mm"] = resumo["chuva_media_ufs_mm"].round(3)
    if len(resumo) != 12 or resumo.focos_nordeste.sum() != fogo.focos_inpe.sum():
        raise ValueError("Resumo regional inconsistente com o fato mensal.")
    destino = RAIZ / "amostras" / f"piloto_{ano}"
    destino.mkdir(parents=True, exist_ok=True)
    lookup_destino = RAIZ / "clean" / "referencias" / f"chirps_celula_uf_piloto_{ano}.csv"
    lookup_destino.parent.mkdir(parents=True, exist_ok=True)
    lookup.to_csv(lookup_destino, index=False)
    oni.to_csv(destino / "oni_mensal.csv", index=False)
    fogo.to_csv(destino / "focos_mensais_uf.csv", index=False)
    chuva.to_csv(destino / "chuva_mensal_uf.csv", index=False)
    fato.to_csv(destino / "fato_mensal_uf.csv", index=False)
    resumo.to_csv(destino / "resumo_mensal_nordeste.csv", index=False)
    qualidade = {
        "recorte": {"ano": ano, "ufs": ufs.uf_sigla.tolist(), "grao": "uf_mes"},
        "manifesto_coleta": meta_manifesto,
        "oni": meta_oni, "inpe": meta_fogo, "chirps": meta_chuva,
        "lookup_espacial": {"arquivo": lookup_destino.relative_to(RAIZ).as_posix(),
                           "sha256": sha256(lookup_destino), "linhas": len(lookup)},
        "malha_ibge": {"arquivo": MALHA.relative_to(RAIZ).as_posix(), "sha256": sha256(MALHA),
                       "versao": "API v3, qualidade minima, capturada para este piloto"},
        "saidas": {"linhas_fato": len(fato), "linhas_resumo": len(resumo),
                   "meses_por_uf": fato.groupby("uf_sigla").size().to_dict(),
                   "focos_nordeste": int(fato.focos_inpe.sum())},
        "limites": ["Ano único: anomalia de chuva e atribuição climática não calculadas.",
                    "Média de células por UF sem ponderação de área; malha IBGE simplificada.",
                    "Focos são detecções de satélite, não incêndios individuais ou área queimada."],
    }
    (destino / "qualidade.json").write_text(json.dumps(qualidade, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Pronto: {len(fato)} linhas UF/mês; {len(resumo)} meses; {int(fato.focos_inpe.sum())} focos no Nordeste. Saída: {destino}")


if __name__ == "__main__":
    main()
