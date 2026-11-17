"""Processa chuva CHIRPS e focos INPE por município do Nordeste para um ano.

Uso: python src/limpeza/processar_municipios.py --ano 2025

Entradas: os mesmos arquivos de raw/ usados por processar_piloto.py, mais a
malha municipal do IBGE (baixada aqui e guardada em raw/referencias/municipios/).
Saídas:
  amostras/piloto_<ano>/fato_mensal_municipio.csv   (município × mês)
  amostras/piloto_<ano>/qualidade_municipios.json
  dashboard/piloto_real/municipios/<UF>.geojson     (malha leve para o mapa)
"""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
import urllib.request
import zipfile

import numpy as np
import pandas as pd

from processar_piloto import (
    RAIZ, RAW, anel_contem_pontos, cabecalho_chirps, dimensao_uf, exigir, normalizar_nome, sha256,
)


MALHAS = RAW / "referencias" / "municipios"
DASHBOARD_MALHAS = RAIZ / "dashboard" / "piloto_real" / "municipios"
IBGE_MALHA = "https://servicodados.ibge.gov.br/api/v3/malhas/estados/{sigla}?intrarregiao=municipio&qualidade=intermediaria&formato=application/vnd.geo+json"
IBGE_NOMES = "https://servicodados.ibge.gov.br/api/v1/localidades/estados/{sigla}/municipios?view=nivelado"


def baixar_json(url: str, accept: str = "application/json") -> dict | list:
    pedido = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": "big-data-project/1.0"})
    with urllib.request.urlopen(pedido, timeout=120) as resposta:
        payload = resposta.read()
    if payload.startswith(b"\x1f\x8b"):
        payload = gzip.decompress(payload)
    return json.loads(payload.decode("utf-8-sig"))


def malha_municipios(sigla: str, uf_codigo: str) -> dict:
    destino = MALHAS / f"{sigla}.geojson"
    if destino.is_file():
        return json.loads(destino.read_text(encoding="utf-8"))
    geojson = baixar_json(IBGE_MALHA.format(sigla=sigla), "application/vnd.geo+json")
    nomes = {str(m["municipio-id"]): m["municipio-nome"] for m in baixar_json(IBGE_NOMES.format(sigla=sigla))}
    features = []
    for feature in geojson.get("features", []):
        codigo = str(feature["properties"]["codarea"])
        if not codigo.startswith(uf_codigo) or codigo not in nomes:
            raise ValueError(f"Município {codigo} inesperado na malha de {sigla}.")
        feature["properties"] = {"CD_MUN": codigo, "NM_MUN": nomes[codigo], "SIGLA_UF": sigla}
        features.append(feature)
    if len(features) != len(nomes):
        raise ValueError(f"Malha de {sigla} tem {len(features)} municípios; a lista do IBGE tem {len(nomes)}.")
    resultado = {"type": "FeatureCollection", "features": features}
    MALHAS.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(resultado, ensure_ascii=False), encoding="utf-8")
    print(f"IBGE: {len(features)} municípios de {sigla}", flush=True)
    return resultado


def poligonos(geometria: dict) -> list:
    return geometria["coordinates"] if geometria["type"] == "MultiPolygon" else [geometria["coordinates"]]


def mascara_geometria(geometria: dict, xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    dentro = np.zeros(xs.size, dtype=bool)
    for poligono in poligonos(geometria):
        parte = anel_contem_pontos(xs, ys, poligono[0])
        for buraco in poligono[1:]:
            parte &= ~anel_contem_pontos(xs, ys, buraco)
        dentro |= parte
    return dentro


def caixa(geometria: dict) -> tuple[float, float, float, float]:
    pontos = [p for poligono in poligonos(geometria) for p in poligono[0]]
    xs, ys = [p[0] for p in pontos], [p[1] for p in pontos]
    return min(xs), min(ys), max(xs), max(ys)


def dimensao_municipios(ufs: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, dict]]:
    linhas, geometrias = [], {}
    for uf in ufs.itertuples():
        for feature in malha_municipios(uf.uf_sigla, uf.uf_codigo_ibge)["features"]:
            p = feature["properties"]
            geometrias[p["CD_MUN"]] = feature["geometry"]
            linhas.append({"municipio_codigo_ibge": p["CD_MUN"], "municipio_nome": p["NM_MUN"],
                           "uf_codigo_ibge": uf.uf_codigo_ibge, "uf_sigla": uf.uf_sigla})
    return pd.DataFrame(linhas), geometrias


def lookup_municipio(campos: dict, municipios: pd.DataFrame, geometrias: dict) -> pd.DataFrame:
    ncol, nlin = int(campos["NCOLS"]), int(campos["NROWS"])
    longitudes = float(campos["ULXMAP"]) + np.arange(ncol) * float(campos["XDIM"])
    latitudes = float(campos["ULYMAP"]) - np.arange(nlin) * float(campos["YDIM"])
    lista, usados = [], set()
    for codigo in municipios.municipio_codigo_ibge:
        geometria = geometrias[codigo]
        x0, y0, x1, y1 = caixa(geometria)
        cols = np.flatnonzero((longitudes >= x0) & (longitudes <= x1))
        lins = np.flatnonzero((latitudes >= y0) & (latitudes <= y1))
        achou = False
        if len(cols) and len(lins):
            grade_linha, grade_coluna = np.meshgrid(lins, cols, indexing="ij")
            linha, coluna = grade_linha.ravel(), grade_coluna.ravel()
            mascara = mascara_geometria(geometria, longitudes[coluna], latitudes[linha])
            for l, c in zip(linha[mascara], coluna[mascara]):
                indice = int(l * ncol + c)
                if indice in usados:
                    continue
                usados.add(indice)
                lista.append((int(l), int(c), codigo, "centro_da_celula"))
                achou = True
        if not achou:
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            c = int(np.abs(longitudes - cx).argmin())
            l = int(np.abs(latitudes - cy).argmin())
            lista.append((l, c, codigo, "celula_mais_proxima"))
    return pd.DataFrame(lista, columns=["linha", "coluna", "municipio_codigo_ibge", "metodo_chuva"])


def chuva_municipios(ano: int, municipios: pd.DataFrame, geometrias: dict) -> tuple[pd.DataFrame, dict]:
    caminhos = [exigir(RAW / "chirps_v3_mensal_latam" / f"chirps-v3.0.{ano}{mes:02d}.tar.gz") for mes in range(1, 13)]
    cabecalho, dados = cabecalho_chirps(caminhos[0])
    lookup = lookup_municipio(cabecalho, municipios, geometrias)
    ncol = int(cabecalho["NCOLS"])
    indices = lookup.linha.to_numpy() * ncol + lookup.coluna.to_numpy()
    tipo = "<f4" if cabecalho["BYTEORDER"] == "I" else ">f4"
    partes = []
    for mes, caminho in enumerate(caminhos, start=1):
        campos, grade = (cabecalho, dados) if mes == 1 else cabecalho_chirps(caminho)
        if campos != cabecalho:
            raise ValueError(f"Georreferência da grade CHIRPS mudou em {caminho}")
        valores = np.frombuffer(grade, dtype=tipo)[indices].astype(float)
        valores[~np.isfinite(valores) | (valores < 0)] = np.nan
        amostra = lookup[["municipio_codigo_ibge"]].assign(chuva_mm=valores)
        por_mun = amostra.groupby("municipio_codigo_ibge").chuva_mm.agg(["mean", "count", "size"]).reset_index()
        por_mun.insert(0, "mes", mes)
        partes.append(por_mun)
        print(f"CHIRPS {ano}-{mes:02d}: {len(por_mun)} municípios", flush=True)
    chuva = pd.concat(partes).rename(columns={"mean": "chuva_media_mm", "count": "celulas_validas", "size": "celulas_chirps"})
    chuva["chuva_media_mm"] = chuva.chuva_media_mm.round(2)
    metodo = lookup.groupby("municipio_codigo_ibge").metodo_chuva.first()
    chuva["metodo_chuva"] = chuva.municipio_codigo_ibge.map(metodo)
    sem_valor = chuva.groupby("municipio_codigo_ibge").celulas_validas.transform("sum").eq(0)
    chuva.loc[sem_valor, "metodo_chuva"] = "sem_celula_valida"
    return chuva, {
        "municipios_sem_celula_valida": sorted(chuva.loc[sem_valor, "municipio_codigo_ibge"].unique().tolist()),
        "celulas_mapeadas": int((lookup.metodo_chuva == "centro_da_celula").sum()),
        "municipios_por_celula_mais_proxima": int(metodo.eq("celula_mais_proxima").sum()),
        "metodo_espacial": "centro_da_celula_no_poligono_municipal; municipio_sem_centro_usa_celula_mais_proxima",
        "agregacao": "media_aritmetica_de_celulas_validas; sem_peso_de_area",
    }


def focos_municipios(ano: int, ufs: pd.DataFrame, municipios: pd.DataFrame, geometrias: dict) -> tuple[pd.DataFrame, dict]:
    caminho = exigir(RAW / "inpe_focos_sat_ref" / f"focos_br_ref_{ano}.zip")
    sigla_por_estado = {normalizar_nome(u.uf_nome): u.uf_sigla for u in ufs.itertuples()}
    chave = municipios.assign(nome=municipios.municipio_nome.map(normalizar_chave))
    por_nome = {(r.uf_sigla, r.nome): r.municipio_codigo_ibge for r in chave.itertuples()}
    caixas = {codigo: caixa(geometrias[codigo]) for codigo in municipios.municipio_codigo_ibge}
    codigos_uf = municipios.groupby("uf_sigla").municipio_codigo_ibge.apply(list).to_dict()
    with zipfile.ZipFile(caminho) as pacote:
        membro = next(n for n in pacote.namelist() if n.lower().endswith(".csv"))
        with pacote.open(membro) as fluxo:
            focos = pd.read_csv(fluxo, dtype=str, usecols=["lat", "lon", "data_pas", "estado", "municipio"], keep_default_na=False)
    focos["data"] = pd.to_datetime(focos.data_pas, errors="coerce")
    focos["uf_sigla"] = focos.estado.map(normalizar_nome).map(sigla_por_estado)
    focos = focos.loc[focos.data.dt.year.eq(ano) & focos.uf_sigla.notna()].copy()
    focos["mes"] = focos.data.dt.month
    focos["municipio_codigo_ibge"] = [por_nome.get((uf, normalizar_chave(nome))) for uf, nome in zip(focos.uf_sigla, focos.municipio)]
    sem_nome = focos.municipio_codigo_ibge.isna()
    nomes_nao_encontrados = sorted(set(focos.loc[sem_nome, "uf_sigla"] + ": " + focos.loc[sem_nome, "municipio"]))
    por_coordenada = 0
    for idx, (uf, lat, lon) in focos.loc[sem_nome, ["uf_sigla", "lat", "lon"]].iterrows():
        x, y = float(lon), float(lat)
        for codigo in codigos_uf[uf]:
            x0, y0, x1, y1 = caixas[codigo]
            if x0 <= x <= x1 and y0 <= y <= y1 and mascara_geometria(geometrias[codigo], np.array([x]), np.array([y]))[0]:
                focos.at[idx, "municipio_codigo_ibge"] = codigo
                por_coordenada += 1
                break
    descartados = int(focos.municipio_codigo_ibge.isna().sum())
    contagem = focos.dropna(subset=["municipio_codigo_ibge"]).groupby(["municipio_codigo_ibge", "mes"]).size().rename("focos_inpe").reset_index()
    return contagem, {
        "arquivo": caminho.relative_to(RAIZ).as_posix(), "sha256": sha256(caminho),
        "focos_nordeste": len(focos), "ligados_pelo_nome": int((~sem_nome).sum()),
        "ligados_pela_coordenada": por_coordenada, "sem_municipio": descartados,
        "nomes_inpe_sem_par_no_ibge": nomes_nao_encontrados[:50],
    }


def normalizar_chave(nome: str) -> str:
    return "".join(c for c in normalizar_nome(nome) if c.isalnum())


def exportar_malhas_dashboard(municipios: pd.DataFrame, geometrias: dict) -> None:
    arredondar = lambda valor: round(valor, 3) if isinstance(valor, float) else [arredondar(v) for v in valor]
    DASHBOARD_MALHAS.mkdir(parents=True, exist_ok=True)
    for sigla, grupo in municipios.groupby("uf_sigla"):
        features = [{"type": "Feature",
                     "properties": {"cd": r.municipio_codigo_ibge, "nome": r.municipio_nome},
                     "geometry": {"type": geometrias[r.municipio_codigo_ibge]["type"],
                                  "coordinates": arredondar(geometrias[r.municipio_codigo_ibge]["coordinates"])}}
                    for r in grupo.itertuples()]
        (DASHBOARD_MALHAS / f"{sigla}.geojson").write_text(
            json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False, separators=(",", ":")),
            encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ano", type=int, default=2025)
    ano = parser.parse_args().ano
    ufs = dimensao_uf()
    municipios, geometrias = dimensao_municipios(ufs)
    chuva, meta_chuva = chuva_municipios(ano, municipios, geometrias)
    focos, meta_focos = focos_municipios(ano, ufs, municipios, geometrias)
    base = municipios.merge(pd.DataFrame({"mes": range(1, 13)}), how="cross")
    fato = (base.merge(chuva, on=["municipio_codigo_ibge", "mes"], how="left", validate="one_to_one")
                .merge(focos, on=["municipio_codigo_ibge", "mes"], how="left", validate="one_to_one"))
    fato["focos_inpe"] = fato.focos_inpe.fillna(0).astype(int)
    fato.insert(0, "ano", ano)
    colunas = ["ano", "mes", "uf_sigla", "municipio_codigo_ibge", "municipio_nome", "chuva_media_mm",
               "celulas_chirps", "metodo_chuva", "focos_inpe"]
    fato = fato[colunas].sort_values(["mes", "uf_sigla", "municipio_codigo_ibge"]).reset_index(drop=True)
    sem_chuva = fato.chuva_media_mm.isna() & fato.metodo_chuva.ne("sem_celula_valida")
    if len(fato) != 12 * len(municipios) or sem_chuva.any():
        raise ValueError("Fato municipal incompleto ou com chuva ausente.")
    uf_csv = RAIZ / "amostras" / f"piloto_{ano}" / "focos_mensais_uf.csv"
    if uf_csv.is_file():
        total_uf = int(pd.read_csv(uf_csv).focos_inpe.sum())
        diferenca = total_uf - int(fato.focos_inpe.sum())
        meta_focos["diferenca_para_total_por_uf"] = diferenca
    destino = RAIZ / "amostras" / f"piloto_{ano}"
    destino.mkdir(parents=True, exist_ok=True)
    fato.to_csv(destino / "fato_mensal_municipio.csv", index=False)
    exportar_malhas_dashboard(municipios, geometrias)
    qualidade = {
        "recorte": {"ano": ano, "municipios": len(municipios), "grao": "municipio_mes"},
        "chirps": meta_chuva, "inpe": meta_focos,
        "malha_ibge": {"pasta": MALHAS.relative_to(RAIZ).as_posix(), "versao": "API v3 malhas, qualidade intermediaria"},
        "limites": ["Municípios menores que uma célula CHIRPS (~5,5 km) usam a célula mais próxima.",
                    "Média de células sem ponderação de área.",
                    "Ilhas oceânicas sem célula CHIRPS válida ficam sem chuva (metodo_chuva = sem_celula_valida).",
                    "Focos são detecções de satélite, não incêndios individuais ou área queimada."],
    }
    (destino / "qualidade_municipios.json").write_text(json.dumps(qualidade, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Pronto: {len(municipios)} municípios × 12 meses; {int(fato.focos_inpe.sum())} focos. "
          f"Nome: {meta_focos['ligados_pelo_nome']}, coordenada: {meta_focos['ligados_pela_coordenada']}, "
          f"sem município: {meta_focos['sem_municipio']}. Célula mais próxima: {meta_chuva['municipios_por_celula_mais_proxima']}.")


if __name__ == "__main__":
    main()
