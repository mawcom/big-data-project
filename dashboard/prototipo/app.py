"""Servidor local do protótipo climático."""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from demo_data import demo_payload


ROOT = Path(__file__).resolve().parents[2]
PROTOTYPE_DIR = ROOT / "dashboard" / "prototipo"
HTML_PATH = PROTOTYPE_DIR / "index.html"
REGION_MAP_PATH = PROTOTYPE_DIR / "static" / "regioes_ibge.geojson"
OBSERVED_PATH = PROTOTYPE_DIR / "static" / "porto_alegre_chuva_maio_2024.json"
OBSERVED_CSV_PATH = ROOT / "amostras" / "porto_alegre_chuva_maio_2024.csv"
LEGACY_DOCS = ROOT / "docs" / "legado"
PILOT_DIR = ROOT / "dashboard" / "piloto_real"
PILOT_SAMPLES = ROOT / "amostras"
RAW_DIR = ROOT / "raw"
SYNC_SCRIPT = ROOT / "src" / "limpeza" / "sincronizar_dados.py"
SYNC_LOCK = threading.Lock()
SYNC_FINGERPRINT: tuple | None = None
SYNC_WARNING: str | None = None
SYNC_STATUS: dict = {}


def assinatura_entradas() -> tuple:
    arquivos = [RAW_DIR / "enso" / "oni_cpc_v6.html", RAW_DIR / "referencias" / "ufs_ibge.geojson"]
    arquivos.extend((RAW_DIR / "chirps_v3_mensal_latam").glob("*.tar.gz"))
    arquivos.extend((RAW_DIR / "inpe_focos_sat_ref").glob("*.zip"))
    return tuple(sorted((str(p.relative_to(ROOT)), p.stat().st_size, p.stat().st_mtime_ns)
                        for p in arquivos if p.is_file()))


def sincronizar_se_preciso() -> str | None:
    global SYNC_FINGERPRINT, SYNC_WARNING, SYNC_STATUS
    with SYNC_LOCK:
        assinatura = assinatura_entradas()
        if assinatura == SYNC_FINGERPRINT:
            return SYNC_WARNING
        resultado = subprocess.run([sys.executable, str(SYNC_SCRIPT)], cwd=ROOT,
                                   capture_output=True, text=True, timeout=900, check=False)
        SYNC_FINGERPRINT = assinatura_entradas()
        try:
            SYNC_STATUS = json.loads(resultado.stdout.strip().splitlines()[-1])
        except (IndexError, json.JSONDecodeError):
            SYNC_STATUS = {}
        if resultado.returncode:
            print(resultado.stdout, resultado.stderr, flush=True)
            SYNC_WARNING = "Alguma base nova não pôde ser processada; confira o terminal do servidor."
        else:
            SYNC_WARNING = None
        return SYNC_WARNING


def anos_disponiveis() -> list[int]:
    anos = []
    for pasta in PILOT_SAMPLES.glob("piloto_*"):
        corresponde = re.fullmatch(r"piloto_(\d{4})", pasta.name)
        if corresponde and (pasta / "fato_mensal_uf.csv").is_file() and (pasta / "qualidade.json").is_file():
            anos.append(int(corresponde.group(1)))
    return sorted(anos)


class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - nome definido pela biblioteca padrão
        route = urlparse(self.path).path
        if route == "/api/data":
            body = json.dumps(demo_payload(), ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if route == "/api/piloto-real":
            try:
                aviso = sincronizar_se_preciso()
            except (OSError, subprocess.TimeoutExpired) as erro:
                print(f"Sincronização interrompida: {erro}", flush=True)
                aviso = "A atualização automática falhou; veja o terminal do servidor."
            linhas = []
            qualidade = {}
            anos = anos_disponiveis()
            for ano in anos:
                pasta = PILOT_SAMPLES / f"piloto_{ano}"
                with (pasta / "fato_mensal_uf.csv").open(encoding="utf-8", newline="") as arquivo:
                    linhas.extend(csv.DictReader(arquivo))
                qualidade[str(ano)] = json.loads((pasta / "qualidade.json").read_text(encoding="utf-8"))
            ano_projetado = anos[-1] + 1 if anos else None
            pasta_projecao = PILOT_SAMPLES / f"projecao_{ano_projetado}" if ano_projetado else None
            projecao = []
            metodo = None
            if pasta_projecao and (pasta_projecao / "projecao_mensal_uf.csv").is_file():
                with (pasta_projecao / "projecao_mensal_uf.csv").open(encoding="utf-8", newline="") as arquivo:
                    projecao = list(csv.DictReader(arquivo))
                metodo = json.loads((pasta_projecao / "metodo.json").read_text(encoding="utf-8"))
            body = json.dumps({"anos_observados": anos, "ano_projetado": ano_projetado,
                               "linhas": linhas, "qualidade": qualidade, "projecao": projecao,
                               "metodo_projecao": metodo, "aviso_sincronizacao": aviso,
                               "anos_pendentes": SYNC_STATUS.get("anos_pendentes", {})}, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if route in {"/piloto-real", "/piloto-real/"}:
            body = (PILOT_DIR / "index.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if route == "/static/ufs_nordeste_ibge.geojson":
            body = (PILOT_DIR / "ufs_nordeste_ibge.geojson").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/geo+json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if route == "/api/observed":
            body = OBSERVED_PATH.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if route == "/sample/porto_alegre_chuva_maio_2024.csv":
            body = OBSERVED_CSV_PATH.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/csv; charset=utf-8")
            self.send_header("Content-Disposition", 'attachment; filename="porto_alegre_chuva_maio_2024.csv"')
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if route == "/static/regioes_ibge.geojson":
            body = REGION_MAP_PATH.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "application/geo+json; charset=utf-8")
            self.send_header("Cache-Control", "public, max-age=86400")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        docs_routes = {
            "/docs/processamento": ROOT / "docs" / "guia-processamento-dados.md",
            "/docs/tema/README.md": LEGACY_DOCS / "tema" / "README.md",
            "/docs/dados-reais/README.md": LEGACY_DOCS / "dados-reais" / "README.md",
            "/docs/arquitetura/README.md": LEGACY_DOCS / "arquitetura" / "README.md",
        }
        if route in docs_routes:
            body = docs_routes[route].read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/markdown; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if route in {"/", "/index.html"}:
            body = HTML_PATH.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_error(404, "Rota não encontrada")

    def log_message(self, format: str, *args: object) -> None:
        print(f"[{self.log_date_time_string()}] {format % args}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Painel local de demonstração climática")
    parser.add_argument("--host", default="127.0.0.1", help="Interface de rede (padrão: apenas local)")
    parser.add_argument("--port", type=int, default=8000, help="Porta HTTP (padrão: 8000)")
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    print("Página inicial: simulação. /piloto-real: anos observados disponíveis e projeção exploratória.")
    print(f"Painel disponível em http://{args.host}:{args.port} — Ctrl+C para encerrar")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
