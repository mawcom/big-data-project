"""Projeta o ano após a última base observada usando persistência sazonal.

Com apenas os dois anos anteriores, esta é uma referência exploratória. A
faixa é a diferença observada entre eles, sem significado probabilístico.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

import numpy as np
import pandas as pd


RAIZ = Path(__file__).resolve().parents[2]
AMOSTRAS = RAIZ / "amostras"
CHAVES = ["uf_codigo_ibge", "mes"]


def sha256(caminho: Path) -> str:
    digest = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def anos_processados() -> list[int]:
    anos = []
    for pasta in AMOSTRAS.glob("piloto_*"):
        corresponde = re.fullmatch(r"piloto_(\d{4})", pasta.name)
        if corresponde and (pasta / "fato_mensal_uf.csv").is_file() and (pasta / "qualidade.json").is_file():
            anos.append(int(corresponde.group(1)))
    return sorted(anos)


def ler_ano(ano: int) -> tuple[pd.DataFrame, Path]:
    caminho = AMOSTRAS / f"piloto_{ano}" / "fato_mensal_uf.csv"
    if not caminho.is_file():
        raise FileNotFoundError(f"Falta {caminho}; processe {ano} antes.")
    quadro = pd.read_csv(caminho, dtype={"uf_codigo_ibge": str, "uf_sigla": str})
    if len(quadro) != 108 or quadro.duplicated(CHAVES).any() or set(quadro.mes) != set(range(1, 13)):
        raise ValueError(f"{ano} não contém 9 UFs × 12 meses com chaves únicas.")
    if quadro[["chuva_media_mm", "focos_inpe"]].isna().any().any():
        raise ValueError(f"Medidas ausentes em {ano}.")
    return quadro, caminho


def projetar(ano_base: int | None = None) -> Path:
    anos = anos_processados()
    if ano_base is None:
        if len(anos) < 2:
            raise ValueError("São necessários dois anos observados completos para a referência sazonal.")
        ano_base = anos[-1]
    ano_anterior = ano_base - 1
    ano_projetado = ano_base + 1
    anterior, caminho_anterior = ler_ano(ano_anterior)
    recente, caminho_recente = ler_ano(ano_base)
    campos = CHAVES + ["uf_sigla", "uf_nome", "chuva_media_mm", "focos_inpe"]
    combinado = anterior[campos].merge(
        recente[campos], on=CHAVES, how="outer", suffixes=("_anterior", "_base"),
        validate="one_to_one", indicator=True,
    )
    if len(combinado) != 108 or not combinado._merge.eq("both").all():
        raise ValueError("Os anos de entrada não têm as mesmas UFs e meses.")
    if not combinado.uf_sigla_anterior.eq(combinado.uf_sigla_base).all():
        raise ValueError("Siglas de UF inconsistentes entre anos.")
    medidas = combinado[["chuva_media_mm_anterior", "chuva_media_mm_base", "focos_inpe_anterior", "focos_inpe_base"]]
    if (medidas < 0).any().any():
        raise ValueError("Medidas negativas nas entradas.")

    saida = pd.DataFrame({
        "competencia": pd.to_datetime(dict(year=ano_projetado, month=combinado.mes, day=1)).dt.strftime("%Y-%m-%d"),
        "ano": ano_projetado, "mes": combinado.mes,
        "uf_codigo_ibge": combinado.uf_codigo_ibge,
        "uf_sigla": combinado.uf_sigla_base,
        "uf_nome": combinado.uf_nome_base,
        "ano_base": ano_base, "ano_anterior": ano_anterior,
        "chuva_anterior_mm": combinado.chuva_media_mm_anterior,
        "chuva_base_mm": combinado.chuva_media_mm_base,
        "focos_anterior": combinado.focos_inpe_anterior,
        "focos_base": combinado.focos_inpe_base,
    })
    delta_chuva = (saida.chuva_base_mm - saida.chuva_anterior_mm).abs()
    delta_focos = (saida.focos_base - saida.focos_anterior).abs()
    saida["chuva_referencia_mm"] = saida.chuva_base_mm.round(3)
    saida["chuva_faixa_min_mm"] = (saida.chuva_base_mm - delta_chuva).clip(lower=0).round(3)
    saida["chuva_faixa_max_mm"] = (saida.chuva_base_mm + delta_chuva).round(3)
    saida["focos_referencia"] = saida.focos_base.astype(int)
    saida["focos_faixa_min"] = (saida.focos_base - delta_focos).clip(lower=0).astype(int)
    saida["focos_faixa_max"] = (saida.focos_base + delta_focos).astype(int)
    saida["metodo"] = "persistencia_sazonal"
    saida["data_status"] = "projecao_exploratoria"
    saida = saida.sort_values(["mes", "uf_codigo_ibge"]).reset_index(drop=True)
    if saida.duplicated(["competencia", "uf_codigo_ibge"]).any():
        raise ValueError("Projeção gerou chaves repetidas.")

    erros_por_uf = {}
    for sigla, grupo in saida.groupby("uf_sigla"):
        erros_por_uf[sigla] = {
            "mae_chuva_mm": round(float(np.mean(np.abs(grupo.chuva_base_mm - grupo.chuva_anterior_mm))), 3),
            "mae_focos": round(float(np.mean(np.abs(grupo.focos_base - grupo.focos_anterior))), 1),
        }
    metadados = {
        "titulo": f"Referência sazonal exploratória de {ano_projetado}",
        "ano_base": ano_base, "ano_anterior": ano_anterior, "ano_projetado": ano_projetado,
        "metodo": f"Para cada UF e mês, referência {ano_projetado} = valor observado em {ano_base}. Faixa = referência +/- |valor {ano_base} - valor {ano_anterior}|, limitada a zero.",
        "interpretacao": "A faixa mostra a variação entre dois anos, não probabilidade, confiança ou atribuição climática.",
        "avaliacao": f"Erro da mesma regra ao usar {ano_anterior} como referência para {ano_base}; só um ano de comparação.",
        "erros_por_uf": erros_por_uf,
        "fontes": [
            {"arquivo": caminho_anterior.relative_to(RAIZ).as_posix(), "sha256": sha256(caminho_anterior)},
            {"arquivo": caminho_recente.relative_to(RAIZ).as_posix(), "sha256": sha256(caminho_recente)},
        ],
        "linhas": len(saida),
        "limites": [
            "ONI e fase ENSO não são projetados.",
            "Só dois anos de referência; sazonalidade e mudanças estruturais podem variar muito.",
            "Os valores projetados não são observações nem previsões meteorológicas operacionais.",
        ],
    }
    destino = AMOSTRAS / f"projecao_{ano_projetado}"
    destino.mkdir(parents=True, exist_ok=True)
    saida.to_csv(destino / "projecao_mensal_uf.csv", index=False)
    (destino / "metodo.json").write_text(json.dumps(metadados, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Projeção exploratória de {ano_projetado}: {len(saida)} linhas UF/mês; saída em {destino}")
    return destino


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ano-base", type=int, help="Ano observado de referência; padrão: o mais recente.")
    args = parser.parse_args()
    projetar(args.ano_base)


if __name__ == "__main__":
    main()
