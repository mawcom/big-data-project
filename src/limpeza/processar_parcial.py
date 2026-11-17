"""Processa os meses já publicados de um ano em curso (CHIRPS + focos INPE).

Uso: python src/limpeza/processar_parcial.py --ano 2026

O ano corrente ainda não tem o arquivo anual de focos do satélite de
referência. Os arquivos mensais do INPE trazem todos os satélites; aqui só
entra o AQUA_M-T, que é o satélite de referência (em set/2025 o filtro
reproduziu exatamente o arquivo anual, UF por UF). Só são processados meses
com CHIRPS e INPE publicados e com o mês de focos encerrado.

Saída em amostras/parcial_<ano>/, separada de piloto_<ano>/ para não ser
confundida com um ano completo.
"""

from __future__ import annotations

import argparse
import calendar
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from processar_piloto import (
    RAIZ,
    RAW,
    dimensao_uf,
    ler_chirps,
    normalizar_nome,
    serie_oni,
    sha256,
)

SATELITE_REFERENCIA = "AQUA_M-T"
PASTA_MENSAL = RAW / "inpe_focos_mensal"


def meses_disponiveis(ano: int) -> list[int]:
    meses = []
    for mes in range(1, 13):
        chirps = RAW / "chirps_v3_mensal_latam" / f"chirps-v3.0.{ano}{mes:02d}.tar.gz"
        inpe = PASTA_MENSAL / f"focos_mensal_br_{ano}{mes:02d}.csv"
        if not (chirps.is_file() and inpe.is_file()):
            break
        meses.append(mes)
    if not meses:
        raise FileNotFoundError(f"Sem CHIRPS e INPE mensal para {ano}-01; rode fetch_raw com inpe_mensal.")
    return meses


def ler_inpe_mensal(ano: int, mes: int, ufs: pd.DataFrame) -> tuple[dict[str, int], dict]:
    caminho = PASTA_MENSAL / f"focos_mensal_br_{ano}{mes:02d}.csv"
    codigos = {normalizar_nome(linha.uf_nome): linha.uf_codigo_ibge for linha in ufs.itertuples()}
    totais = {uf: 0 for uf in ufs.uf_codigo_ibge}
    lidas = referencia = fora_mes = 0
    minimo = maximo = None
    for lote in pd.read_csv(caminho, dtype=str, chunksize=200_000, keep_default_na=False,
                            usecols=["data_hora_gmt", "satelite", "estado"]):
        lidas += len(lote)
        datas = pd.to_datetime(lote["data_hora_gmt"], errors="coerce")
        validas = datas.dropna()
        if not validas.empty:
            minimo = validas.min() if minimo is None else min(minimo, validas.min())
            maximo = validas.max() if maximo is None else max(maximo, validas.max())
        no_mes = datas.dt.year.eq(ano) & datas.dt.month.eq(mes)
        fora_mes += int((datas.notna() & ~no_mes).sum())
        filtro = no_mes & lote["satelite"].eq(SATELITE_REFERENCIA)
        referencia += int(filtro.sum())
        codigo = lote.loc[filtro, "estado"].map(normalizar_nome).map(codigos).dropna()
        for uf, qtd in codigo.value_counts().items():
            totais[uf] += int(qtd)
    ultimo_dia = calendar.monthrange(ano, mes)[1]
    if minimo is None or minimo.day != 1 or maximo.day != ultimo_dia or maximo.month != mes:
        raise ValueError(f"{caminho.name} não cobre o mês inteiro ({minimo} a {maximo}); mês ainda aberto?")
    if referencia == 0:
        raise ValueError(f"{caminho.name} não tem focos do {SATELITE_REFERENCIA}; o satélite de referência mudou?")
    return totais, {"mes": mes, "arquivo": caminho.relative_to(RAIZ).as_posix(), "sha256": sha256(caminho),
                    "linhas_lidas": lidas, "focos_satelite_referencia_brasil": referencia,
                    "fora_do_mes": fora_mes, "primeira_data": str(minimo), "ultima_data": str(maximo)}


def processar(ano: int) -> Path:
    ufs = dimensao_uf()
    meses = meses_disponiveis(ano)
    chuva, _, meta_chuva = ler_chirps(ano, ufs, meses)
    focos, meta_fogo = [], []
    for mes in meses:
        totais, meta = ler_inpe_mensal(ano, mes, ufs)
        focos += [{"ano": ano, "mes": mes, "uf_codigo_ibge": uf, "focos_inpe": qtd} for uf, qtd in totais.items()]
        meta_fogo.append(meta)
        print(f"INPE {ano}-{mes:02d}: {sum(totais.values())} focos {SATELITE_REFERENCIA} no Nordeste.", flush=True)
    oni, caminho_oni = serie_oni()
    oni = oni.loc[oni.ano.eq(ano) & oni.mes.isin(meses), ["ano", "mes", "janela_oni", "oni_c", "fase_enso"]]

    chaves = ["ano", "mes", "uf_codigo_ibge"]
    fato = chuva.merge(pd.DataFrame(focos), on=chaves, validate="one_to_one")
    fato = fato.merge(oni, on=["ano", "mes"], how="left", validate="many_to_one")
    fato.insert(0, "competencia", pd.to_datetime({"year": fato.ano, "month": fato.mes, "day": 1}).dt.strftime("%Y-%m-%d"))
    fato["fonte_chuva"] = "CHIRPS v3 mensal"
    fato["fonte_fogo"] = f"INPE mensal, satelite {SATELITE_REFERENCIA}"
    fato["fonte_enso"] = "NOAA CPC ONI v6"
    fato["data_status"] = "real_parcial"
    fato["qualidade_fogo"] = "mensal_preliminar"
    fato = fato.sort_values(chaves).reset_index(drop=True)
    if len(fato) != 9 * len(meses) or fato.duplicated(chaves).any() or fato.chuva_media_mm.isna().any():
        raise ValueError("Fato parcial incompleto ou com chaves duplicadas.")

    destino = RAIZ / "amostras" / f"parcial_{ano}"
    destino.mkdir(parents=True, exist_ok=True)
    fato.to_csv(destino / "fato_mensal_uf.csv", index=False)
    qualidade = {
        "recorte": {"ano": ano, "meses": meses, "ufs": ufs.uf_sigla.tolist(), "grao": "uf_mes"},
        "oni": {"arquivo": caminho_oni.relative_to(RAIZ).as_posix(), "sha256": sha256(caminho_oni),
                "meses_com_oni": sorted(oni.mes.tolist())},
        "inpe": {"satelite": SATELITE_REFERENCIA, "arquivos": meta_fogo},
        "chirps": meta_chuva,
        "saidas": {"linhas_fato": len(fato), "focos_nordeste": int(fato.focos_inpe.sum())},
        "limites": [
            "Ano incompleto: só os meses listados em recorte.meses.",
            "Focos mensais são preliminares; o arquivo anual consolidado pode diferir.",
            "ONI dos últimos meses pode faltar enquanto a janela trimestral não fecha.",
        ],
    }
    (destino / "qualidade.json").write_text(json.dumps(qualidade, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Pronto: {ano} parcial, meses {meses[0]}–{meses[-1]}, {len(fato)} linhas UF/mês. Saída: {destino}")
    return destino


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ano", type=int, default=pd.Timestamp.now().year)
    processar(parser.parse_args().ano)


if __name__ == "__main__":
    main()
