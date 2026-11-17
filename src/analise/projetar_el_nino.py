"""Projeção de chuva e focos para um ano de El Niño, validada nos meses já observados.

Uso: python src/analise/projetar_el_nino.py [--ano 2026]

Entradas: amostras/historico/ (processar_historico.py) e amostras/parcial_<ano>/
(processar_parcial.py). Regras comparadas, todas por UF e mês e fixadas antes
de olhar os dados do ano em curso:

- climatologia: média histórica do mês (chuva 1991–2020; focos de 2003 até o
  ano anterior). É a referência a bater: "não sei nada sobre o ano".
- persistência: o valor do mesmo mês no ano anterior (regra do project_2026).
- análogo: o valor do último El Niño (ano 0 e, depois, o ano +1).
- composto: climatologia + anomalia média dos El Niños passados no mesmo mês
  do ciclo (ano 0 = ano com El Niño ativo em ago-set-out; ano +1 = o seguinte).
- composto_forte: o mesmo, só com El Niños de pico de ONI >= 1,5. Cenário
  acrescentado depois de ver que o sinal na quadra chuvosa vem desses episódios.

Se o composto erra menos que a climatologia, saber que o ano é de El Niño
ajuda a prever. A projeção cobre os meses ainda não observados até junho do
ano seguinte (quadra chuvosa do norte do Nordeste). A faixa é o intervalo
entre o 1º e o 3º quartil dos El Niños passados, não uma probabilidade.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "limpeza"))
from processar_piloto import serie_oni, sha256

RAIZ = Path(__file__).resolve().parents[2]
AMOSTRAS = RAIZ / "amostras"
HISTORICO = AMOSTRAS / "historico"
CHAVES = ["uf_codigo_ibge", "mes"]
MEDIDAS = {"chuva": "chuva_media_mm", "focos": "focos_inpe"}
REGRAS = ["climatologia", "persistencia", "analogo", "composto", "composto_forte"]
LIMIAR_FORTE = 1.5  # pico de ONI; 2026 passa de +2,5
CLIMATOLOGIA_CHUVA = (1991, 2020)
MES_FINAL_PROJECAO = 6  # junho do ano seguinte: fim da quadra chuvosa do norte do NE


def ler_historico() -> tuple[dict[str, pd.DataFrame], list[Path]]:
    caminhos = {"chuva": HISTORICO / "chuva_mensal_uf.csv", "focos": HISTORICO / "focos_mensais_uf.csv"}
    for caminho in caminhos.values():
        if not caminho.is_file():
            raise FileNotFoundError(f"Falta {caminho}; rode processar_historico.py.")
    series = {nome: pd.read_csv(c, dtype={"uf_codigo_ibge": str}) for nome, c in caminhos.items()}
    return series, list(caminhos.values())


def ler_parcial(ano: int) -> tuple[pd.DataFrame, Path]:
    caminho = AMOSTRAS / f"parcial_{ano}" / "fato_mensal_uf.csv"
    if not caminho.is_file():
        raise FileNotFoundError(f"Falta {caminho}; rode processar_parcial.py --ano {ano}.")
    quadro = pd.read_csv(caminho, dtype={"uf_codigo_ibge": str})
    return quadro[CHAVES + ["uf_sigla", "uf_nome", "oni_c", "fase_enso", *MEDIDAS.values()]], caminho


def anos_el_nino(antes_de: int) -> pd.DataFrame:
    """Anos com El Niño ativo em ago-set-out (ASO), a fase de crescimento do episódio.

    Esse ano é o "ano 0" do ciclo. Alinhar pelo mês de início deixaria de
    fora o segundo semestre de 2015 (episódio iniciado em out/2014) e contaria
    2018–19 duas vezes.
    """
    oni, _ = serie_oni()
    em_nino = oni.fase_enso.eq("El Niño")
    anos = sorted(int(a) for a in oni.loc[em_nino & oni.mes.eq(9), "ano"] if a < antes_de)
    linhas = []
    for ano in anos:
        ciclo = oni.loc[(oni.ano.eq(ano) | (oni.ano.eq(ano + 1) & oni.mes.le(6))) & em_nino]
        linhas.append({"ano": ano, "pico_oni": float(ciclo.oni_c.max()),
                       "meses_com_el_nino_no_ano_0": int(ciclo.ano.eq(ano).sum())})
    return pd.DataFrame(linhas)


def episodios_validos(inicios: pd.DataFrame, serie: pd.DataFrame) -> list[int]:
    anos = set(serie.ano)
    return [int(a) for a in inicios.ano if a in anos and a + 1 in anos]


def climatologia(nome: str, serie: pd.DataFrame, ano: int) -> tuple[pd.Series, list[int]]:
    inicio, fim = CLIMATOLOGIA_CHUVA if nome == "chuva" else (int(serie.ano.min()), ano - 1)
    base = serie.loc[serie.ano.between(inicio, fim)]
    return base.groupby(CHAVES)[MEDIDAS[nome]].mean(), [inicio, fim]


def composto(nome: str, serie: pd.DataFrame, clim: pd.Series, episodios: list[int], deslocamento: int) -> pd.DataFrame:
    """Anomalia de cada El Niño no ano 0 (deslocamento 0) ou +1 (deslocamento 1)."""
    coluna = MEDIDAS[nome]
    linhas = []
    for inicio in episodios:
        ano = serie.loc[serie.ano.eq(inicio + deslocamento)].set_index(CHAVES)[coluna]
        linhas.append((ano - clim).rename(inicio))
    anomalias = pd.concat(linhas, axis=1)
    valores = anomalias.add(clim, axis=0).clip(lower=0)
    return pd.DataFrame({
        "composto": (clim + anomalias.mean(axis=1)).clip(lower=0),
        "q1": valores.quantile(0.25, axis=1),
        "q3": valores.quantile(0.75, axis=1),
        "abaixo_da_media": (anomalias < 0).sum(axis=1),
        "episodios": anomalias.shape[1],
    })


def metricas(erro: pd.Series, observado: pd.Series) -> dict:
    total = float(observado.sum())
    return {
        "mae": round(float(erro.abs().mean()), 2),
        "vies": round(float(erro.mean()), 2),
        "erro_relativo_pct": round(100 * float(erro.abs().sum()) / total, 1) if total else None,
    }


def resumir(tabela: pd.DataFrame) -> dict:
    resumo: dict = {}
    recortes = {"todos_os_meses": tabela, **dict(tuple(tabela.groupby("periodo")))}
    for recorte, grupo in recortes.items():
        resumo[recorte] = {"meses": sorted(int(m) for m in grupo.mes.unique())}
        for nome in MEDIDAS:
            observado = grupo[f"{nome}_observado"]
            por_uf = {}
            for sigla, sub in grupo.groupby("uf_sigla"):
                obs = sub[f"{nome}_observado"]
                por_uf[sigla] = {regra: metricas(sub[f"{nome}_{regra}"] - obs, obs) for regra in REGRAS}
            resumo[recorte][nome] = {
                "nordeste_uf_mes": {regra: metricas(grupo[f"{nome}_{regra}"] - observado, observado) for regra in REGRAS},
                "ufs_em_que_composto_bate_climatologia": sum(
                    v["composto"]["mae"] < v["climatologia"]["mae"] for v in por_uf.values()),
                "por_uf": por_uf,
            }
    return resumo


def projetar(ano: int) -> Path:
    series, caminhos_historico = ler_historico()
    parcial, caminho_parcial = ler_parcial(ano)
    observados = sorted(int(m) for m in parcial.mes.unique())
    em_nino = parcial.loc[parcial.fase_enso.eq("El Niño"), "mes"]
    inicio_atual = int(em_nino.min()) if not em_nino.empty else None
    inicios = anos_el_nino(ano)
    restantes = [m for m in range(1, 13) if m not in observados]
    meses_seguinte = list(range(1, MES_FINAL_PROJECAO + 1))

    validacao = parcial[CHAVES + ["uf_sigla"]].copy()
    projecao_partes: list[pd.DataFrame] = []
    info: dict = {}
    for nome, serie in series.items():
        coluna = MEDIDAS[nome]
        clim, periodo_clim = climatologia(nome, serie, ano)
        episodios = episodios_validos(inicios, serie)
        analogo = max(episodios)
        comp0 = composto(nome, serie, clim, episodios, 0)
        comp1 = composto(nome, serie, clim, episodios, 1)
        fortes = [a for a in episodios if float(inicios.set_index("ano").pico_oni[a]) >= LIMIAR_FORTE]
        forte0 = composto(nome, serie, clim, fortes, 0).composto
        forte1 = composto(nome, serie, clim, fortes, 1).composto
        por_ano = serie.set_index(["ano", *CHAVES])[coluna]
        info[nome] = {"climatologia": periodo_clim, "episodios": episodios, "episodios_fortes": fortes,
                      "analogo": analogo}

        # Validação: meses observados do ano em curso (ano 0 do ciclo).
        chave = pd.MultiIndex.from_frame(validacao[CHAVES])
        validacao[f"{nome}_observado"] = parcial[coluna].to_numpy()
        validacao[f"{nome}_climatologia"] = clim.reindex(chave).to_numpy()
        validacao[f"{nome}_persistencia"] = por_ano.loc[ano - 1].reindex(chave).to_numpy()
        validacao[f"{nome}_analogo"] = por_ano.loc[analogo].reindex(chave).to_numpy()
        validacao[f"{nome}_composto"] = comp0.composto.reindex(chave).to_numpy()
        validacao[f"{nome}_composto_forte"] = forte0.reindex(chave).to_numpy()

        # Projeção: resto do ano em curso (ano 0) + jan..jun do seguinte (ano +1).
        for ano_alvo, meses, comp, forte, ano_analogo in ((ano, restantes, comp0, forte0, analogo),
                                                          (ano + 1, meses_seguinte, comp1, forte1, analogo + 1)):
            bloco = comp.loc[comp.index.get_level_values("mes").isin(meses)].copy()
            bloco["composto_forte"] = forte.reindex(bloco.index)
            bloco["climatologia"] = clim.reindex(bloco.index)
            bloco["analogo"] = por_ano.loc[ano_analogo].reindex(bloco.index).to_numpy()
            bloco = bloco.add_prefix(f"{nome}_").reset_index().assign(ano=ano_alvo)
            projecao_partes.append(bloco)

    validacao["periodo"] = np.where(validacao.mes >= (inicio_atual or 13), "durante_el_nino", "antes_el_nino")
    if validacao.drop(columns="periodo").isna().any().any():
        raise ValueError("Validação com valores ausentes; confira o histórico e o ano parcial.")
    resumo = resumir(validacao)

    projecao = pd.concat(projecao_partes).groupby(["ano", *CHAVES], as_index=False).first()
    nomes = parcial.drop_duplicates("uf_codigo_ibge").set_index("uf_codigo_ibge")[["uf_sigla", "uf_nome"]]
    projecao = projecao.join(nomes, on="uf_codigo_ibge")
    projecao.insert(0, "competencia",
                    pd.to_datetime({"year": projecao.ano, "month": projecao.mes, "day": 1}).dt.strftime("%Y-%m-%d"))
    for nome in MEDIDAS:
        casas = 1 if nome == "chuva" else 0
        for sufixo in ("composto", "composto_forte", "q1", "q3", "climatologia"):
            projecao[f"{nome}_{sufixo}"] = projecao[f"{nome}_{sufixo}"].round(casas)
        for sufixo in ("composto", "composto_forte"):
            razao = projecao[f"{nome}_{sufixo}"] / projecao[f"{nome}_climatologia"]
            projecao[f"{nome}_anomalia_{sufixo}_pct"] = (100 * (razao - 1)).round(1)
    projecao["metodo"] = "composto_el_nino"
    projecao["data_status"] = "projecao_exploratoria"
    colunas = ["competencia", "ano", "mes", "uf_codigo_ibge", "uf_sigla", "uf_nome"]
    for nome in MEDIDAS:
        colunas += [f"{nome}_{c}" for c in ("composto", "q1", "q3", "climatologia", "anomalia_composto_pct",
                                              "abaixo_da_media", "episodios", "composto_forte",
                                              "anomalia_composto_forte_pct", "analogo")]
    projecao = projecao[colunas + ["metodo", "data_status"]].sort_values(["competencia", "uf_codigo_ibge"])
    projecao = projecao.reset_index(drop=True)
    if projecao.duplicated(["competencia", "uf_codigo_ibge"]).any() or projecao[colunas].isna().any().any():
        raise ValueError("Projeção com chaves repetidas ou valores ausentes.")

    oni = parcial.drop_duplicates("mes").set_index("mes").oni_c.dropna()
    metodo = {
        "titulo": f"El Niño {ano}: validação e projeção de chuva e focos no Nordeste",
        "ano": ano,
        "inicio_el_nino_ano_corrente_mes": inicio_atual,
        "oni_ano_corrente": {int(m): float(v) for m, v in oni.items()},
        "el_ninos_passados": inicios.to_dict(orient="records"),
        "series": info,
        "regras": {
            "climatologia": "Média do mês por UF (chuva 1991–2020; focos do início da série ao ano anterior).",
            "persistencia": f"Valor do mesmo mês em {ano - 1}.",
            "analogo": "Valor do último El Niño com dados (ano 0, depois o ano +1).",
            "composto": "Climatologia + média das anomalias dos El Niños passados no mesmo mês do ciclo, limitada a zero.",
            "composto_forte": (f"Igual ao composto, só com El Niños de pico de ONI >= {LIMIAR_FORTE}. "
                               "Cenário escolhido depois de ver os dados, porque o El Niño em curso é forte."),
            "faixa": "q1 e q3: 1º e 3º quartis dos El Niños passados (climatologia + anomalia de cada um).",
            "abaixo_da_media": "Quantos El Niños passados ficaram abaixo da climatologia naquele mês e UF.",
        },
        "validacao": {
            "descricao": (f"Erro das regras nos meses observados de {ano}. vies = média de (previsto - observado); "
                          "erro_relativo_pct = soma dos erros absolutos / soma do observado."),
            **resumo,
        },
        "projecao": {"inicio": projecao.competencia.min(), "fim": projecao.competencia.max(), "linhas": len(projecao)},
        "fontes": [{"arquivo": c.relative_to(RAIZ).as_posix(), "sha256": sha256(c)}
                   for c in (*caminhos_historico, caminho_parcial)],
        "limites": [
            "Poucos episódios (10 para chuva e 6 para focos); a faixa entre quartis é grosseira.",
            ("Os El Niños são alinhados pelo calendário (ano 0 = El Niño ativo em ago-set-out); "
             "episódios que começam tarde têm o 1º semestre do ano 0 ainda neutro."),
            "O composto não escala pela intensidade; o composto_forte tem só 5 episódios de chuva e 3 de focos.",
            ("Na validação, os meses durante o El Niño caem na estação seca da maior parte do Nordeste; "
             "o teste diz mais sobre focos do que sobre chuva."),
            "Focos do ano corrente vêm dos arquivos mensais preliminares do INPE.",
            "Não é previsão meteorológica operacional nem atribuição causal.",
        ],
    }

    destino = AMOSTRAS / f"projecao_el_nino_{ano}"
    destino.mkdir(parents=True, exist_ok=True)
    validacao.to_csv(destino / "validacao_mensal_uf.csv", index=False)
    projecao.to_csv(destino / "projecao_mensal_uf.csv", index=False)
    (destino / "metodo.json").write_text(json.dumps(metodo, ensure_ascii=False, indent=2), encoding="utf-8")
    imprimir_resumo(metodo, projecao)
    print(f"Saída em {destino}")
    return destino


def imprimir_resumo(metodo: dict, projecao: pd.DataFrame) -> None:
    for nome, dados in metodo["series"].items():
        print(f"{nome}: climatologia {dados['climatologia']}, El Niños {dados['episodios']}")
    validacao = metodo["validacao"]
    print(f"Erro relativo nos meses observados de {metodo['ano']} ({' | '.join(REGRAS)}):")
    for recorte in ("antes_el_nino", "durante_el_nino", "todos_os_meses"):
        if recorte not in validacao:
            continue
        for nome in MEDIDAS:
            r = validacao[recorte][nome]
            erros = " | ".join(f"{r['nordeste_uf_mes'][regra]['erro_relativo_pct']}%" for regra in REGRAS)
            print(f"  {recorte:16} {nome:5} {erros}  "
                  f"(composto bate a climatologia em {r['ufs_em_que_composto_bate_climatologia']}/9 UFs)")
    print("Projeção, Nordeste (chuva: média das UFs; focos: soma):")
    resumo = projecao.groupby("competencia").agg(
        chuva_composto=("chuva_composto", "mean"), chuva_forte=("chuva_composto_forte", "mean"),
        chuva_climatologia=("chuva_climatologia", "mean"),
        focos_composto=("focos_composto", "sum"), focos_forte=("focos_composto_forte", "sum"),
        focos_climatologia=("focos_climatologia", "sum"),
    ).round(1)
    print(resumo.to_string())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ano", type=int, default=pd.Timestamp.now().year)
    projetar(parser.parse_args().ano)


if __name__ == "__main__":
    main()
