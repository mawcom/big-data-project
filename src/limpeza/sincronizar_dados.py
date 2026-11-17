"""Detecta anos brutos completos, processa os novos e atualiza a projeção.

Uso: python src/limpeza/sincronizar_dados.py [--force]
Pode ser chamado pelo painel após o usuário baixar/copiar novas bases em raw/.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys


RAIZ = Path(__file__).resolve().parents[2]
RAW = RAIZ / "raw"
AMOSTRAS = RAIZ / "amostras"
MALHA = RAW / "referencias" / "ufs_ibge.geojson"
ONI = RAW / "enso" / "oni_cpc_v6.html"
# Primeiro ano exibido no painel. A série histórica (1991+ e 2003+) é baixada
# para a análise do El Niño e entra só por processar_historico*.py; sem este
# corte, abrir o painel criaria uma pasta piloto_<ano> para cada ano antigo.
ANO_INICIAL_PAINEL = 2023


def sha256(caminho: Path) -> str:
    digest = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            digest.update(bloco)
    return digest.hexdigest()


def entradas_ano(ano: int) -> list[Path]:
    return [
        ONI, MALHA, RAW / "inpe_focos_sat_ref" / f"focos_br_ref_{ano}.zip",
        *[RAW / "chirps_v3_mensal_latam" / f"chirps-v3.0.{ano}{mes:02d}.tar.gz" for mes in range(1, 13)],
    ]


def descobrir_anos(desde: int = ANO_INICIAL_PAINEL) -> tuple[list[int], dict[int, list[str]]]:
    candidatos = set()
    for arquivo in (RAW / "inpe_focos_sat_ref").glob("focos_br_ref_*.zip"):
        corresponde = re.fullmatch(r"focos_br_ref_(\d{4})\.zip", arquivo.name)
        if corresponde:
            candidatos.add(int(corresponde.group(1)))
    for arquivo in (RAW / "chirps_v3_mensal_latam").glob("chirps-v3.0.*.tar.gz"):
        corresponde = re.fullmatch(r"chirps-v3\.0\.(\d{4})\d{2}\.tar\.gz", arquivo.name)
        if corresponde:
            candidatos.add(int(corresponde.group(1)))
    completos = []
    pendentes = {}
    for ano in sorted(a for a in candidatos if a >= desde):
        ausentes = [p.relative_to(RAIZ).as_posix() for p in entradas_ano(ano) if not p.is_file() or p.stat().st_size == 0]
        if ausentes:
            pendentes[ano] = ausentes
        else:
            completos.append(ano)
    return completos, pendentes


def produto_atualizado(ano: int) -> bool:
    pasta = AMOSTRAS / f"piloto_{ano}"
    qualidade = pasta / "qualidade.json"
    if not all((pasta / nome).is_file() for nome in ("fato_mensal_uf.csv", "resumo_mensal_nordeste.csv", "qualidade.json")):
        return False
    try:
        meta = json.loads(qualidade.read_text(encoding="utf-8"))
        esperados = {
            meta["oni"]["arquivo"]: meta["oni"]["sha256"],
            meta["inpe"]["arquivo"]: meta["inpe"]["sha256"],
            meta["malha_ibge"]["arquivo"]: meta["malha_ibge"]["sha256"],
            **{item["arquivo"]: item["sha256"] for item in meta["chirps"]["arquivos"]},
        }
        if len(esperados) != 15 or meta["saidas"]["linhas_fato"] != 108:
            return False
        return all((RAIZ / nome).is_file() and sha256(RAIZ / nome) == digest for nome, digest in esperados.items())
    except (KeyError, ValueError, OSError, TypeError, json.JSONDecodeError):
        return False


def projecao_atualizada(ano_base: int) -> bool:
    destino = AMOSTRAS / f"projecao_{ano_base + 1}"
    meta_path = destino / "metodo.json"
    if not meta_path.is_file() or not (destino / "projecao_mensal_uf.csv").is_file():
        return False
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta["ano_base"] != ano_base or meta["linhas"] != 108:
            return False
        return all((RAIZ / item["arquivo"]).is_file() and sha256(RAIZ / item["arquivo"]) == item["sha256"] for item in meta["fontes"])
    except (KeyError, ValueError, OSError, TypeError, json.JSONDecodeError):
        return False


def executar(script: Path, *argumentos: str) -> None:
    subprocess.run([sys.executable, str(script), *argumentos], cwd=RAIZ, check=True)


def sincronizar(force: bool = False, desde: int = ANO_INICIAL_PAINEL) -> dict:
    completos, pendentes = descobrir_anos(desde)
    atualizados = []
    falhas = {}
    for ano in completos:
        if not force and produto_atualizado(ano):
            continue
        try:
            executar(RAIZ / "src" / "limpeza" / "processar_piloto.py", "--ano", str(ano))
            atualizados.append(ano)
        except subprocess.CalledProcessError as erro:
            falhas[ano] = f"Processamento falhou (código {erro.returncode})."
    for ano in completos:
        if ano in falhas or not (force or ano in atualizados or not (AMOSTRAS / f"piloto_{ano}" / "fato_mensal_municipio.csv").is_file()):
            continue
        try:
            executar(RAIZ / "src" / "limpeza" / "processar_municipios.py", "--ano", str(ano))
        except subprocess.CalledProcessError as erro:
            falhas[ano] = f"Processamento municipal falhou (código {erro.returncode})."
    disponiveis = [ano for ano in completos if produto_atualizado(ano)]
    ano_base = max((ano for ano in disponiveis if ano - 1 in disponiveis), default=None)
    projecao = None
    if ano_base is not None:
        if force or not projecao_atualizada(ano_base):
            try:
                executar(RAIZ / "src" / "analise" / "projetar_proximo_ano.py", "--ano-base", str(ano_base))
            except subprocess.CalledProcessError as erro:
                falhas[ano_base + 1] = f"Projeção falhou (código {erro.returncode})."
        if projecao_atualizada(ano_base):
            projecao = ano_base + 1
    estado = {"anos_observados": disponiveis, "anos_processados_agora": atualizados,
              "anos_pendentes": {str(ano): faltantes for ano, faltantes in pendentes.items()},
              "ano_projetado": projecao, "falhas": falhas}
    print(json.dumps(estado, ensure_ascii=False))
    return estado


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="Reprocessa todos os anos completos.")
    parser.add_argument("--desde", type=int, default=ANO_INICIAL_PAINEL,
                        help=f"Primeiro ano a processar para o painel (padrão: {ANO_INICIAL_PAINEL}).")
    args = parser.parse_args()
    estado = sincronizar(args.force, args.desde)
    if estado["falhas"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
