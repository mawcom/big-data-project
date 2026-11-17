"""Série de chuva CHIRPS por município do Nordeste, de todos os meses em raw/.

Uso: python src/limpeza/processar_historico_municipios.py [--desde 1991]

Saídas (CSV limpo, fora do Git, em clean/):
  clean/chuva_mensal_municipio.csv   ano, mes, municipio_codigo_ibge, chuva_media_mm
  clean/municipios_nordeste.csv      dimensão: nome, UF e como a chuva foi obtida
  clean/qualidade_chuva_municipio.json

Usa a mesma malha e a mesma regra espacial de processar_municipios.py. Focos
ficam por UF: por município, as contagens são pequenas demais para comparar
poucos El Niños.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from processar_municipios import dimensao_municipios, lookup_municipio
from processar_piloto import RAIZ, RAW, cabecalho_chirps, dimensao_uf, sha256

CLEAN = RAIZ / "clean"
PASTA_CHIRPS = RAW / "chirps_v3_mensal_latam"


def meses_chirps(desde: int) -> list[tuple[int, int, Path]]:
    meses = []
    for arquivo in sorted(PASTA_CHIRPS.glob("chirps-v3.0.*.tar.gz")):
        if corresponde := re.fullmatch(r"chirps-v3\.0\.(\d{4})(\d{2})\.tar\.gz", arquivo.name):
            ano, mes = int(corresponde.group(1)), int(corresponde.group(2))
            if ano >= desde:
                meses.append((ano, mes, arquivo))
    if not meses:
        raise FileNotFoundError(f"Sem arquivos CHIRPS em {PASTA_CHIRPS}; rode fetch_raw.")
    return meses


def processar(desde: int) -> Path:
    municipios, geometrias = dimensao_municipios(dimensao_uf())
    arquivos = meses_chirps(desde)
    cabecalho, _ = cabecalho_chirps(arquivos[0][2])
    lookup = lookup_municipio(cabecalho, municipios, geometrias)
    ncol = int(cabecalho["NCOLS"])
    indices = lookup.linha.to_numpy() * ncol + lookup.coluna.to_numpy()
    codigos = lookup.municipio_codigo_ibge.to_numpy()
    tipo = "<f4" if cabecalho["BYTEORDER"] == "I" else ">f4"

    partes, entradas = [], []
    for ano, mes, caminho in arquivos:
        campos, grade = cabecalho_chirps(caminho)
        if campos != cabecalho:
            raise ValueError(f"Georreferência da grade CHIRPS mudou em {caminho}")
        valores = np.frombuffer(grade, dtype=tipo)[indices].astype(float)
        valores[~np.isfinite(valores) | (valores < 0)] = np.nan
        media = pd.Series(valores).groupby(codigos).mean().round(2)
        partes.append(pd.DataFrame({"ano": ano, "mes": mes, "municipio_codigo_ibge": media.index,
                                    "chuva_media_mm": media.to_numpy()}))
        entradas.append({"arquivo": caminho.relative_to(RAIZ).as_posix(), "sha256": sha256(caminho)})
        if mes == 12:
            print(f"CHIRPS {ano}: {len(media)} municípios", flush=True)

    chuva = pd.concat(partes, ignore_index=True)
    sem_valor = chuva.groupby("municipio_codigo_ibge").chuva_media_mm.count().loc[lambda s: s.eq(0)].index
    chuva = chuva.loc[~chuva.municipio_codigo_ibge.isin(sem_valor)]
    if chuva.duplicated(["ano", "mes", "municipio_codigo_ibge"]).any():
        raise ValueError("Chaves repetidas na série municipal.")

    metodo = lookup.groupby("municipio_codigo_ibge").agg(
        metodo_chuva=("metodo_chuva", "first"), celulas_chirps=("metodo_chuva", "size"))
    dimensao = municipios.join(metodo, on="municipio_codigo_ibge")
    dimensao.loc[dimensao.municipio_codigo_ibge.isin(sem_valor), "metodo_chuva"] = "sem_celula_valida"

    CLEAN.mkdir(parents=True, exist_ok=True)
    chuva.to_csv(CLEAN / "chuva_mensal_municipio.csv", index=False)
    dimensao.to_csv(CLEAN / "municipios_nordeste.csv", index=False)
    qualidade = {
        "periodo": [f"{arquivos[0][0]}-{arquivos[0][1]:02d}", f"{arquivos[-1][0]}-{arquivos[-1][1]:02d}"],
        "meses": len(arquivos),
        "municipios": int(chuva.municipio_codigo_ibge.nunique()),
        "municipios_sem_celula_valida": sorted(map(str, sem_valor)),
        "municipios_por_celula_mais_proxima": int(metodo.metodo_chuva.eq("celula_mais_proxima").sum()),
        "linhas": len(chuva),
        "metodo_espacial": "centro_da_celula_no_poligono_municipal; municipio_sem_centro_usa_celula_mais_proxima",
        "agregacao": "media_aritmetica_de_celulas_validas; sem_peso_de_area",
        "entradas": entradas,
    }
    (CLEAN / "qualidade_chuva_municipio.json").write_text(
        json.dumps(qualidade, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Pronto: {qualidade['municipios']} municípios, {qualidade['periodo'][0]} a {qualidade['periodo'][1]}, "
          f"{len(chuva)} linhas. Saída: {CLEAN / 'chuva_mensal_municipio.csv'}")
    return CLEAN


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--desde", type=int, default=1991)
    processar(parser.parse_args().desde)


if __name__ == "__main__":
    main()
