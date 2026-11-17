"""Consolida a série histórica por UF e mês: chuva CHIRPS, focos INPE e ONI.

Uso: python src/limpeza/processar_historico.py [--desde 1991]

Só entram anos completos: 12 meses CHIRPS para a chuva e o arquivo anual do
satélite de referência para os focos (disponível a partir de 2003). A saída
fica em amostras/historico/ e não cria pastas piloto_<ano>, que o painel
trata como anos de exibição.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from processar_piloto import (
    RAIZ,
    RAW,
    dimensao_uf,
    ler_chirps,
    ler_inpe,
    serie_oni,
    sha256,
)

DESTINO = RAIZ / "amostras" / "historico"


def anos_chirps_completos(desde: int) -> list[int]:
    meses: dict[int, int] = {}
    for arquivo in (RAW / "chirps_v3_mensal_latam").glob("chirps-v3.0.*.tar.gz"):
        if corresponde := re.fullmatch(r"chirps-v3\.0\.(\d{4})\d{2}\.tar\.gz", arquivo.name):
            ano = int(corresponde.group(1))
            meses[ano] = meses.get(ano, 0) + 1
    return sorted(ano for ano, total in meses.items() if total == 12 and ano >= desde)


def anos_inpe_anuais(desde: int) -> list[int]:
    anos = []
    for arquivo in (RAW / "inpe_focos_sat_ref").glob("focos_br_ref_*.zip"):
        if corresponde := re.fullmatch(r"focos_br_ref_(\d{4})\.zip", arquivo.name):
            anos.append(int(corresponde.group(1)))
    return sorted(ano for ano in anos if ano >= desde)


def processar(desde: int) -> Path:
    ufs = dimensao_uf()
    siglas = ufs.set_index("uf_codigo_ibge").uf_sigla
    chuva, focos, entradas = [], [], []
    for ano in anos_chirps_completos(desde):
        quadro, _, meta = ler_chirps(ano, ufs)
        chuva.append(quadro[["ano", "mes", "uf_codigo_ibge", "uf_sigla", "chuva_media_mm", "cobertura_chuva_pct"]])
        entradas += [{"arquivo": item["arquivo"], "sha256": item["sha256"]} for item in meta["arquivos"]]
    for ano in anos_inpe_anuais(desde):
        quadro, meta = ler_inpe(ano, ufs)
        focos.append(quadro[["ano", "mes", "uf_codigo_ibge", "uf_sigla", "focos_inpe"]])
        entradas.append({"arquivo": meta["arquivo"], "sha256": meta["sha256"]})
        print(f"INPE {ano}: {int(quadro.focos_inpe.sum())} focos no Nordeste.", flush=True)
    if not chuva or not focos:
        raise FileNotFoundError("Sem anos completos de CHIRPS ou INPE em raw/; rode fetch_raw antes.")

    chuva = pd.concat(chuva, ignore_index=True).sort_values(["ano", "mes", "uf_codigo_ibge"])
    focos = pd.concat(focos, ignore_index=True).sort_values(["ano", "mes", "uf_codigo_ibge"])
    for nome, quadro in (("chuva", chuva), ("focos", focos)):
        if quadro.duplicated(["ano", "mes", "uf_codigo_ibge"]).any() or len(quadro) != 108 * quadro.ano.nunique():
            raise ValueError(f"Série de {nome} com chaves repetidas ou anos incompletos.")
    if chuva.chuva_media_mm.isna().any():
        raise ValueError("Chuva ausente em alguma UF/mês.")
    if not set(siglas) == set(chuva.uf_sigla):
        raise ValueError("A série de chuva não contém as nove UFs.")

    oni, caminho_oni = serie_oni()
    oni = oni.loc[oni.ano.ge(desde)]

    DESTINO.mkdir(parents=True, exist_ok=True)
    chuva.to_csv(DESTINO / "chuva_mensal_uf.csv", index=False)
    focos.to_csv(DESTINO / "focos_mensais_uf.csv", index=False)
    oni.to_csv(DESTINO / "oni_mensal.csv", index=False)
    qualidade = {
        "chuva": {"anos": [int(chuva.ano.min()), int(chuva.ano.max())], "linhas": len(chuva),
                  "fonte": "CHIRPS v3 mensal, média das células por UF"},
        "focos": {"anos": [int(focos.ano.min()), int(focos.ano.max())], "linhas": len(focos),
                  "fonte": "INPE, arquivo anual do satélite de referência"},
        "oni": {"arquivo": caminho_oni.relative_to(RAIZ).as_posix(), "sha256": sha256(caminho_oni),
                "meses": len(oni)},
        "entradas": entradas,
        "limites": [
            "Média aritmética das células por UF, sem peso de área; malha IBGE simplificada.",
            "Focos são detecções de satélite, não incêndios nem área queimada.",
        ],
    }
    (DESTINO / "qualidade.json").write_text(json.dumps(qualidade, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Pronto: chuva {qualidade['chuva']['anos']}, focos {qualidade['focos']['anos']}. Saída: {DESTINO}")
    return DESTINO


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--desde", type=int, default=1991)
    processar(parser.parse_args().desde)


if __name__ == "__main__":
    main()
