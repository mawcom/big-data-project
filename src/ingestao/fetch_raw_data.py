"""Baixa as bases escolhidas para o projeto com concorrência configurável."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile


RAIZ = Path(__file__).resolve().parents[2]
BRUTOS = RAIZ / "raw"
AGENTE = "big-data-project/1.0 (coleta educacional)"
PERFIS = {
    "low": (2, 256 * 1024),
    "medium": (6, 1024 * 1024),
    "high": (12, 4 * 1024 * 1024),
}
COBERTURA = {
    "oni": "1950 até a última publicação (série cumulativa)",
    "chirps": "anos disponíveis no catálogo",
    "inpe": "anos disponíveis no catálogo",
    "inmet": "anos disponíveis no catálogo",
    "ghcn_daily": "anos disponíveis no catálogo",
    "icoads": "anos disponíveis no catálogo",
    "noaa_globaltemp": "1850 até a última publicação (série cumulativa)",
    "ons_balanco": "anos disponíveis no catálogo",
    "ons_ear": "anos disponíveis no catálogo",
}
AMOSTRAS_2024 = {
    "chirps": 12,
    "inpe": 1,
    "inmet": 1,
    "ghcn_daily": 1,
    "ons_balanco": 1,
    "ons_ear": 1,
}
VOLUMES_PILOTO_2024 = {
    "chirps": 35_432_484,
    "inpe": 10_727_110,
    "inmet": 102_772_199,
    "ghcn_daily": 176_504_452,
    "ons_balanco": 2_086_316,
    "ons_ear": 30_477,
}
def formatar_volume(volume: int) -> str:
    if volume >= 1_000_000_000:
        return f"{volume / 1_000_000_000:.2f} GB"
    if volume >= 1_000_000:
        return f"{volume / 1_000_000:.2f} MB"
    return f"{volume / 1_000:.2f} KB"


def tamanho_remoto(url: str) -> int | None:
    pedido = urllib.request.Request(url, headers={"User-Agent": AGENTE}, method="HEAD")
    try:
        with urllib.request.urlopen(pedido, timeout=20) as resposta:
            tamanho = resposta.headers.get("Content-Length")
            return int(tamanho) if tamanho is not None else None
    except (urllib.error.URLError, TimeoutError):
        return None


def interpretar_intervalo(valor: str) -> tuple[int, int]:
    encontrado = re.fullmatch(r"(\d{4})(?:-(\d{4}))?", valor)
    if not encontrado:
        raise argparse.ArgumentTypeError("Use --range ANO ou --range ANO-ANO, por exemplo 2024-2025.")
    inicio = int(encontrado.group(1))
    fim = int(encontrado.group(2) or encontrado.group(1))
    if inicio > fim:
        raise argparse.ArgumentTypeError("O ano inicial de --range deve ser menor ou igual ao final.")
    return inicio, fim


def selecionar_anos(anos: range | list[int], intervalo: tuple[int, int] | None) -> list[int]:
    if intervalo is None:
        return list(anos)
    return [ano for ano in anos if intervalo[0] <= ano <= intervalo[1]]


def descrever_anos(anos: list[int]) -> str:
    if not anos:
        return "sem arquivos no intervalo"
    if len(anos) == 1:
        return str(anos[0])
    return f"{min(anos)} a {max(anos)}"


def apresentar_previsao(
    tarefas: list[tuple[str, str, Path]], estimativas: dict[str, int], periodos: dict[str, str],
) -> None:
    contagens = {fonte: sum(tarefa[0] == fonte for tarefa in tarefas) for fonte in COBERTURA}
    total_estimado = 0
    fontes_sem_estimativa = []
    print("Previsão da coleta (tamanho dos arquivos; piloto de 2024 e metadados atuais):")
    for fonte, cobertura in COBERTURA.items():
        periodo = periodos.get(fonte, cobertura)
        quantidade = contagens[fonte]
        if not quantidade:
            tamanho = "0 MB (sem arquivo no intervalo)"
        elif fonte in estimativas:
            estimativa = estimativas[fonte]
            total_estimado += estimativa
            tamanho = f"~{formatar_volume(estimativa)} (índice da fonte)"
        elif fonte in AMOSTRAS_2024 and fonte in VOLUMES_PILOTO_2024 and quantidade:
            estimativa = round(VOLUMES_PILOTO_2024[fonte] * quantidade / AMOSTRAS_2024[fonte])
            total_estimado += estimativa
            tamanho = f"~{formatar_volume(estimativa)}"
        elif fonte in ("oni", "noaa_globaltemp") and quantidade:
            _, url, caminho = next(tarefa for tarefa in tarefas if tarefa[0] == fonte)
            estimativa = tamanho_remoto(url)
            if estimativa is None:
                if caminho.exists():
                    estimativa = caminho.stat().st_size
                    total_estimado += estimativa
                    tamanho = f"~{formatar_volume(estimativa)} (arquivo local)"
                else:
                    fontes_sem_estimativa.append(fonte)
                    tamanho = "indisponível (servidor não informou o tamanho)"
            else:
                total_estimado += estimativa
                tamanho = f"~{formatar_volume(estimativa)} (servidor)"
        else:
            fontes_sem_estimativa.append(fonte)
            tamanho = "indisponível"
        print(f"  {fonte}: {periodo}; {quantidade} arquivo(s); armazenamento esperado: {tamanho}")
    complemento = f"; sem estimativa: {', '.join(fontes_sem_estimativa)}" if fontes_sem_estimativa else ""
    print(f"Total estimado das fontes mensuráveis: ~{formatar_volume(total_estimado)}{complemento}.")


def abrir(url: str, timeout: int = 120):
    pedido = urllib.request.Request(url, headers={"User-Agent": AGENTE})
    return urllib.request.urlopen(pedido, timeout=timeout)


def verificar(caminho: Path) -> None:
    with caminho.open("rb") as arquivo:
        inicio = arquivo.read(8)
    nome = caminho.name.removesuffix(".part").lower()
    if caminho.stat().st_size == 0:
        raise ValueError(f"Arquivo vazio: {caminho.name}")
    if nome.endswith(".zip") and not zipfile.is_zipfile(caminho):
        raise ValueError(f"Arquivo ZIP inválido: {caminho.name}")
    if nome.endswith(".tar.gz"):
        with tarfile.open(caminho, "r:gz") as pacote:
            if not pacote.getmembers():
                raise ValueError(f"Arquivo TAR.GZ vazio: {caminho.name}")
    if nome.endswith(".csv.gz") and not inicio.startswith(b"\x1f\x8b"):
        raise ValueError(f"Arquivo GZIP inválido: {caminho.name}")
    if nome.endswith(".nc") and not (inicio.startswith(b"CDF") or inicio.startswith(b"\x89HDF")):
        raise ValueError(f"Arquivo NetCDF inválido: {caminho.name}")
    if nome.endswith(".parquet") and inicio[:4] != b"PAR1":
        raise ValueError(f"Arquivo Parquet inválido: {caminho.name}")
    if nome.endswith(".html") and b"Oceanic Ni" not in caminho.read_bytes():
        raise ValueError(f"Página ONI inválida: {caminho.name}")


def resumo(url: str, caminho: Path, estado: str, tamanho_bloco: int) -> dict:
    digest = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(tamanho_bloco), b""):
            digest.update(bloco)
    return {
        "url": url,
        "arquivo": caminho.relative_to(RAIZ).as_posix(),
        "bytes": caminho.stat().st_size,
        "sha256": digest.hexdigest(),
        "estado": estado,
    }


def baixar_arquivo(tarefa: tuple[str, str, Path], tamanho_bloco: int) -> dict:
    fonte, url, destino = tarefa
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.exists() and destino.stat().st_size:
        verificar(destino)
        return {"fonte": fonte, **resumo(url, destino, "já existia", tamanho_bloco)}

    temporario = destino.with_name(destino.name + ".part")
    temporario.unlink(missing_ok=True)
    try:
        for tentativa in range(1, 4):
            try:
                with abrir(url) as resposta, temporario.open("wb") as saida:
                    while bloco := resposta.read(tamanho_bloco):
                        saida.write(bloco)
                verificar(temporario)
                temporario.replace(destino)
                return {"fonte": fonte, **resumo(url, destino, "baixado", tamanho_bloco)}
            except (urllib.error.URLError, TimeoutError):
                if tentativa == 3:
                    raise
                temporario.unlink(missing_ok=True)
                time.sleep(tentativa)
    finally:
        temporario.unlink(missing_ok=True)


def descobrir_globaltemp() -> tuple[str, str, Path]:
    indice = "https://www.ncei.noaa.gov/data/noaa-global-surface-temperature/v6.1/access/gridded/"
    with abrir(indice) as resposta:
        pagina = resposta.read().decode("utf-8", errors="replace")
    nomes = re.findall(r'href="(NOAAGlobalTemp_v6\.1\.0_gridded_s185001_e(\d{6})_c[^"/]+\.nc)"', pagina)
    if not nomes:
        raise RuntimeError("Não encontrei o NetCDF do NOAA GlobalTemp v6.1.")
    nome, _ = max(nomes, key=lambda item: item[1])
    return "noaa_globaltemp", urllib.parse.urljoin(indice, nome), BRUTOS / "noaa_globaltemp" / nome


def anos_disponiveis(url: str, padrao: str) -> list[int]:
    with abrir(url, timeout=30) as resposta:
        pagina = resposta.read().decode("utf-8", errors="replace")
    anos = sorted({int(ano) for ano in re.findall(padrao, pagina)})
    if not anos:
        raise ValueError(f"Não encontrei arquivos no catálogo {url}.")
    return anos


def descobrir_ghcn(intervalo: tuple[int, int] | None) -> tuple[list[tuple[str, str, Path]], int]:
    base = "https://www.ncei.noaa.gov/pub/data/ghcn/daily/by_year/"
    with abrir(base, timeout=30) as resposta:
        pagina = resposta.read().decode("utf-8", errors="replace")
    arquivos = re.findall(
        r'<a href="(\d{4})\.csv\.gz">[^<]+</a></td>\s*<td[^>]*>[^<]*</td>\s*<td[^>]*>(\d+)</td>',
        pagina,
    )
    if not arquivos:
        raise ValueError("Não encontrei arquivos e tamanhos no catálogo GHCN-Daily.")
    selecionados = [(int(ano), int(tamanho)) for ano, tamanho in arquivos
                    if intervalo is None or intervalo[0] <= int(ano) <= intervalo[1]]
    tarefas = [
        ("ghcn_daily", f"{base}{ano}.csv.gz", BRUTOS / "ghcn_daily" / f"{ano}.csv.gz")
        for ano, _ in selecionados
    ]
    return tarefas, sum(tamanho for _, tamanho in selecionados)


def descobrir_icoads(
    trabalhadores: int, ano: int = 2026, estimativas: dict[str, int] | None = None,
) -> tuple[list[tuple[str, str, Path]], list[dict]]:
    indice_base = "https://www.ncei.noaa.gov/data/international-comprehensive-ocean-atmosphere/v3/archive/nrt/daily"
    hoje = datetime.now(timezone.utc).date()
    ultimo_mes = hoje.month if hoje.year == ano else 12
    arquivos_por_dia = {}
    erros = []

    def ler_mes(mes: int):
        url = f"{indice_base}/{ano}/{mes:02d}/"
        try:
            with abrir(url, timeout=20) as resposta:
                return mes, url, resposta.read().decode("utf-8", errors="replace"), None
        except urllib.error.HTTPError as erro:
            if erro.code == 404:
                return mes, url, None, None
            return mes, url, None, str(erro)
        except (urllib.error.URLError, TimeoutError) as erro:
            return mes, url, None, str(erro)

    meses = range(1, ultimo_mes + 1)
    with ThreadPoolExecutor(max_workers=trabalhadores) as executor:
        for mes, url, pagina, erro in executor.map(ler_mes, meses):
            if erro:
                erros.append({"fonte": "icoads", "arquivo": f"indice_{ano}_{mes:02d}", "erro": erro})
                continue
            if pagina is None:
                continue
            arquivos = re.findall(
                r'<a href="([^"/]+\.nc)">[^<]+</a></td>\s*<td[^>]*>[^<]*</td>\s*<td[^>]*>(\d+)</td>',
                pagina,
            )
            if not arquivos and '.nc"' in pagina:
                erros.append({"fonte": "icoads", "arquivo": f"indice_{ano}_{mes:02d}", "erro": "Não consegui ler os tamanhos dos arquivos NetCDF."})
            for nome, tamanho in arquivos:
                encontrado = re.search(r"_d(\d{8})_c(\d{8})\.nc$", nome)
                if not encontrado:
                    continue
                data, criacao = encontrado.groups()
                if not data.startswith(str(ano)) or (ano == hoje.year and data > hoje.strftime("%Y%m%d")):
                    continue
                atual = arquivos_por_dia.get(data)
                prioridade = ("_updated_" in nome, criacao)
                if atual is None or prioridade > atual[0]:
                    arquivos_por_dia[data] = (prioridade, urllib.parse.urljoin(url, nome), int(tamanho))

    tarefas = [
        ("icoads", url, BRUTOS / "icoads" / str(ano) / f"icoads_{data}.nc")
        for data, (_, url, _) in sorted(arquivos_por_dia.items())
    ]
    if estimativas is not None and arquivos_por_dia:
        estimativas["icoads"] = estimativas.get("icoads", 0) + sum(
            item[2] for item in arquivos_por_dia.values()
        )
    return tarefas, erros


def descobrir_ons(
    fonte: str, produto: str, pasta: str, intervalo: tuple[int, int] | None,
) -> list[tuple[str, str, Path]]:
    url = f"https://dados.ons.org.br/api/3/action/package_show?id={produto}"
    with abrir(url) as resposta:
        recursos = json.load(resposta)["result"]["resources"]
    por_ano = {}
    for recurso in recursos:
        encontrado = re.search(r"(?<!\d)(\d{4})(?!\d)", recurso["name"])
        if recurso["format"].lower() != "parquet" or not encontrado:
            continue
        ano = int(encontrado.group(1))
        if ano in por_ano:
            raise RuntimeError(f"ONS {produto}: encontrei mais de um Parquet para {ano}.")
        por_ano[ano] = recurso["url"]
    if not por_ano:
        raise RuntimeError(f"ONS {produto}: não encontrei arquivos Parquet anuais.")
    return [
        (fonte, por_ano[ano], BRUTOS / "ons" / pasta / f"{ano}.parquet")
        for ano in selecionar_anos(sorted(por_ano), intervalo)
    ]


def tarefas_coleta(
    trabalhadores: int, estimativas: dict[str, int], intervalo: tuple[int, int] | None = None,
) -> tuple[list[tuple[str, str, Path]], list[dict], dict[str, str]]:
    tarefas = []
    erros = []
    periodos = {}
    ano_atual = datetime.now(timezone.utc).year
    if intervalo is None or (intervalo[0] <= ano_atual and intervalo[1] >= 1950):
        tarefas.append((
            "oni",
            "https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/oni/v6/index.php",
            BRUTOS / "enso" / "oni_cpc_v6.html",
        ))
        periodos["oni"] = "série cumulativa desde 1950"
    else:
        periodos["oni"] = "sem arquivos no intervalo"

    def consultar_catalogo(fonte: str, url: str, padrao: str) -> list[int]:
        try:
            return anos_disponiveis(url, padrao)
        except Exception as erro:
            erros.append({"fonte": fonte, "arquivo": "catalogo", "erro": str(erro)})
            return []

    chirps = "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/monthly/latam/bils/"
    meses_chirps = consultar_catalogo("chirps", chirps, r"chirps-v3\.0\.(\d{6})\.tar\.gz")
    meses_chirps = [mes for mes in meses_chirps if intervalo is None or intervalo[0] <= mes // 100 <= intervalo[1]]
    periodos["chirps"] = descrever_anos(sorted({mes // 100 for mes in meses_chirps}))
    for mes in meses_chirps:
        nome = f"chirps-v3.0.{mes}.tar.gz"
        tarefas.append(("chirps", chirps + nome, BRUTOS / "chirps_v3_mensal_latam" / nome))

    inpe = "https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/anual/Brasil_sat_ref/"
    anos_inpe = selecionar_anos(consultar_catalogo("inpe", inpe, r"focos_br_ref_(\d{4})\.zip"), intervalo)
    periodos["inpe"] = descrever_anos(anos_inpe)
    for ano in anos_inpe:
        nome = f"focos_br_ref_{ano}.zip"
        tarefas.append(("inpe", inpe + nome, BRUTOS / "inpe_focos_sat_ref" / nome))

    anos_inmet = selecionar_anos(consultar_catalogo(
        "inmet", "https://portal.inmet.gov.br/dadoshistoricos", r"dadoshistoricos/(\d{4})\.zip",
    ), intervalo)
    periodos["inmet"] = descrever_anos(anos_inmet)
    for ano in anos_inmet:
        tarefas.append(("inmet", f"https://portal.inmet.gov.br/uploads/dadoshistoricos/{ano}.zip", BRUTOS / "inmet" / f"{ano}.zip"))

    try:
        arquivos_ghcn, estimativas["ghcn_daily"] = descobrir_ghcn(intervalo)
        tarefas.extend(arquivos_ghcn)
        periodos["ghcn_daily"] = descrever_anos([int(item[2].name[:4]) for item in arquivos_ghcn])
    except Exception as erro:
        erros.append({"fonte": "ghcn_daily", "arquivo": "catalogo", "erro": str(erro)})
        periodos["ghcn_daily"] = "catálogo indisponível"

    indice = "https://www.ncei.noaa.gov/data/international-comprehensive-ocean-atmosphere/v3/archive/nrt/daily/"
    anos_icoads = selecionar_anos(consultar_catalogo("icoads", indice, r'href="(\d{4})(?:/)?"'), intervalo)
    for ano in anos_icoads:
        icoads, falhas_icoads = descobrir_icoads(trabalhadores, ano, estimativas)
        tarefas.extend(icoads)
        erros.extend(falhas_icoads)
    periodos["icoads"] = descrever_anos(anos_icoads)

    if intervalo is None or (intervalo[0] <= ano_atual and intervalo[1] >= 1850):
        try:
            tarefas.append(descobrir_globaltemp())
            periodos["noaa_globaltemp"] = "série cumulativa desde 1850"
        except Exception as erro:
            erros.append({"fonte": "noaa_globaltemp", "arquivo": "catalogo", "erro": str(erro)})
    else:
        periodos["noaa_globaltemp"] = "sem arquivos no intervalo"

    for fonte, produto, pasta in (
        ("ons_balanco", "balanco-energia-subsistema", "balanco_energia_subsistema"),
        ("ons_ear", "ear-diario-por-subsistema", "ear_diario_subsistema"),
    ):
        try:
            arquivos_ons = descobrir_ons(fonte, produto, pasta, intervalo)
            tarefas.extend(arquivos_ons)
            periodos[fonte] = descrever_anos([int(item[2].stem) for item in arquivos_ons])
        except Exception as erro:
            erros.append({"fonte": fonte, "arquivo": "catalogo", "erro": str(erro)})
            periodos[fonte] = "catálogo indisponível"
    return tarefas, erros, periodos


def executar_tarefas(
    tarefas: list[tuple[str, str, Path]],
    erros: list[dict],
    esforco: str,
    caminho_manifesto: Path,
    ano: int | None = None,
) -> None:
    trabalhadores, tamanho_bloco = PERFIS[esforco]
    BRUTOS.mkdir(parents=True, exist_ok=True)

    registros = []
    with ThreadPoolExecutor(max_workers=trabalhadores) as executor:
        futuras = {executor.submit(baixar_arquivo, tarefa, tamanho_bloco): tarefa for tarefa in tarefas}
        for numero, futura in enumerate(as_completed(futuras), start=1):
            fonte, _, destino = futuras[futura]
            try:
                registros.append(futura.result())
                print(f"{numero}/{len(tarefas)}: {fonte} {destino.name}", flush=True)
            except Exception as erro:
                erros.append({"fonte": fonte, "arquivo": destino.name, "erro": str(erro)})
                print(f"{numero}/{len(tarefas)}: falha em {fonte} {destino.name}: {erro}", flush=True)

    manifesto = {
        "coletado_em_utc": datetime.now(timezone.utc).isoformat(),
        "esforco": esforco,
        "total_bytes": sum(item["bytes"] for item in registros),
        "bytes_por_fonte": {
            fonte: sum(item["bytes"] for item in registros if item["fonte"] == fonte)
            for fonte in sorted({item["fonte"] for item in registros})
        },
        "arquivos": sorted(registros, key=lambda item: item["arquivo"]),
        "erros": erros,
    }
    if ano is not None:
        manifesto["ano"] = ano
    caminho_manifesto.write_text(json.dumps(manifesto, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Manifesto: {caminho_manifesto.relative_to(RAIZ)}; arquivos: {len(registros)}; falhas: {len(erros)}.")
    print(f"Carga total dos arquivos: {formatar_volume(manifesto['total_bytes'])}.")
    if erros:
        raise SystemExit(1)


def main() -> None:
    analisador = argparse.ArgumentParser(description=__doc__)
    analisador.add_argument(
        "--effort", choices=PERFIS, default="medium",
        help="low: 2 threads/256 KiB; medium: 6 threads/1 MiB; high: 12 threads/4 MiB",
    )
    analisador.add_argument(
        "--range", dest="intervalo", type=interpretar_intervalo,
        help="Ano ou intervalo inclusivo, por exemplo 2024 ou 2000-2003; sem ele, seleciona todos os anos disponíveis.",
    )
    argumentos = analisador.parse_args()
    trabalhadores, _ = PERFIS[argumentos.effort]
    estimativas = {}
    tarefas, erros, periodos = tarefas_coleta(trabalhadores, estimativas, argumentos.intervalo)
    apresentar_previsao(tarefas, estimativas, periodos)
    executar_tarefas(tarefas, erros, argumentos.effort, BRUTOS / "manifesto_coleta.json")


if __name__ == "__main__":
    main()
