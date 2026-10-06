"""Servidor local do protótipo climático."""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from demo_data import demo_payload


ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = ROOT / "src" / "index.html"
REGION_MAP_PATH = ROOT / "src" / "static" / "regioes_ibge.geojson"
OBSERVED_PATH = ROOT / "src" / "static" / "porto_alegre_chuva_maio_2024.json"
OBSERVED_CSV_PATH = ROOT / "data" / "sample" / "porto_alegre_chuva_maio_2024.csv"


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
            "/docs/tema/README.md": ROOT / "docs" / "tema" / "README.md",
            "/docs/dados-reais/README.md": ROOT / "docs" / "dados-reais" / "README.md",
            "/docs/arquitetura/README.md": ROOT / "docs" / "arquitetura" / "README.md",
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
    print("Protótipo com dados SIMULADOS. Não use como monitoramento ou evidência científica.")
    print(f"Painel disponível em http://{args.host}:{args.port} — Ctrl+C para encerrar")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor encerrado.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
