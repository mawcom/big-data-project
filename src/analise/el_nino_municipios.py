"""Chuva da quadra chuvosa (fev–mai) após El Niños passados, por município.

Uso: python src/analise/el_nino_municipios.py [--ano 2026]

Lê clean/chuva_mensal_municipio.csv (processar_historico_municipios.py) e grava,
uma linha por município, a anomalia de fev–mai do ano seguinte ao El Niño em
relação a 1991–2020: média de todos os El Niños, média dos fortes (pico de ONI
>= 1,5) e quantos ficaram abaixo da média. Saída pequena, pronta para o mapa:
amostras/projecao_el_nino_<ano>/chuva_quadra_municipio.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from projetar_el_nino import (
    AMOSTRAS,
    CLIMATOLOGIA_CHUVA,
    LIMIAR_FORTE,
    RAIZ,
    anos_el_nino,
)

QUADRA = [2, 3, 4, 5]


def calcular(ano: int) -> Path:
    serie = pd.read_csv(RAIZ / "clean" / "chuva_mensal_municipio.csv", dtype={"municipio_codigo_ibge": str})
    dimensao = pd.read_csv(RAIZ / "clean" / "municipios_nordeste.csv", dtype={"municipio_codigo_ibge": str})
    quadra = serie.loc[serie.mes.isin(QUADRA)]
    completos = quadra.groupby("ano").mes.nunique().loc[lambda s: s.eq(len(QUADRA))].index
    total = quadra.loc[quadra.ano.isin(completos)].pivot_table(
        index="ano", columns="municipio_codigo_ibge", values="chuva_media_mm", aggfunc="sum")
    clim = total.loc[CLIMATOLOGIA_CHUVA[0]:CLIMATOLOGIA_CHUVA[1]].mean()

    eventos = anos_el_nino(ano)
    eventos = eventos.loc[eventos.ano.add(1).isin(total.index)]
    fortes = eventos.loc[eventos.pico_oni.ge(LIMIAR_FORTE), "ano"].tolist()
    todos = eventos.ano.tolist()
    anomalia = total.loc[[a + 1 for a in todos]].div(clim) - 1
    anomalia.index = todos

    resultado = pd.DataFrame({
        "chuva_quadra_climatologia_mm": clim.round(1),
        "anomalia_todos_pct": (100 * anomalia.mean()).round(1),
        "anomalia_fortes_pct": (100 * anomalia.loc[fortes].mean()).round(1),
        "fortes_abaixo_da_media": (anomalia.loc[fortes] < 0).sum(),
        "fortes": len(fortes),
        "todos_abaixo_da_media": (anomalia < 0).sum(),
        "todos": len(todos),
        **{f"anomalia_{a}_{a + 1}_pct": (100 * anomalia.loc[a]).round(1) for a in fortes},
    }).rename_axis("municipio_codigo_ibge").reset_index()
    resultado = dimensao[["municipio_codigo_ibge", "municipio_nome", "uf_sigla"]].merge(
        resultado, on="municipio_codigo_ibge", validate="one_to_one")

    destino = AMOSTRAS / f"projecao_el_nino_{ano}"
    destino.mkdir(parents=True, exist_ok=True)
    resultado.to_csv(destino / "chuva_quadra_municipio.csv", index=False)

    print(f"El Niños: {todos}; fortes: {fortes}")
    print(f"{len(resultado)} municípios. Anomalia média dos fortes por UF (mediana dos municípios):")
    print(resultado.groupby("uf_sigla").agg(
        mediana_fortes_pct=("anomalia_fortes_pct", "median"),
        pct_municipios_4_ou_5_abaixo=("fortes_abaixo_da_media", lambda s: round(100 * s.ge(len(fortes) - 1).mean())),
    ).to_string())
    print(f"Saída: {destino / 'chuva_quadra_municipio.csv'}")
    return destino


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ano", type=int, default=pd.Timestamp.now().year)
    calcular(parser.parse_args().ano)


if __name__ == "__main__":
    main()
