import os
import shutil
import time
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor

OUTPUT_DIR = "dados_inmet_raw"
os.makedirs(OUTPUT_DIR, exist_ok=True)

ANOS = list(range(2018, 2027))
CHUNK_SIZE = 16 * 1024 * 1024
TENTATIVAS = 3

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def baixar_e_extrair_ano(ano: int) -> tuple[int, bool]:
    url = f"https://portal.inmet.gov.br/uploads/dadoshistoricos/{ano}.zip"
    dest_zip = os.path.join(OUTPUT_DIR, f"{ano}.zip")
    dest_folder = os.path.join(OUTPUT_DIR, str(ano))
    tmp_folder = dest_folder + ".tmp"

    if os.path.isdir(dest_folder) and os.listdir(dest_folder):
        print(f"[{ano}] Já existe. Pulando...")
        return ano, True

    for tentativa in range(1, TENTATIVAS + 1):
        try:
            print(f"[{ano}] Download (tentativa {tentativa}/{TENTATIVAS})...")
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=300) as resp, open(dest_zip, "wb") as f:
                shutil.copyfileobj(resp, f, length=CHUNK_SIZE)

            shutil.rmtree(tmp_folder, ignore_errors=True)
            with zipfile.ZipFile(dest_zip) as z:
                z.extractall(tmp_folder)
            os.rename(tmp_folder, dest_folder)  # só aparece completo

            os.remove(dest_zip)
            print(f"[{ano}] Pronto.")
            return ano, True

        except Exception as err:
            print(f"[{ano}] Erro: {err}")
            if os.path.exists(dest_zip):
                os.remove(dest_zip)
            shutil.rmtree(tmp_folder, ignore_errors=True)
            time.sleep(5 * tentativa)

    return ano, False

if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=3) as ex:
        resultados = list(ex.map(baixar_e_extrair_ano, ANOS))

    falhas = [a for a, ok in resultados if not ok]
    print(f"\nFalharam: {falhas}" if falhas else "\nTodos os anos baixados.")