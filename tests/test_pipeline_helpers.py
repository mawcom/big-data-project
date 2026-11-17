"""Testes rápidos de contratos que não exigem Java nem dados baixados."""

from __future__ import annotations

import unittest

import duckdb

from src.bigdata.build_chirps_lookup import anel_contem_ponto, extrair_poligonos
from src.bigdata.export_landing import consulta_para
from src.ingestao.fetch_raw_data import tarefas_coleta


class TestesLanding(unittest.TestCase):
    def test_extrae_competencia_chirps_do_nome_de_origem(self) -> None:
        with duckdb.connect() as conexao:
            conexao.execute(
                "CREATE TABLE chirps(latitude DOUBLE, longitude DOUBLE, precipitacao REAL, _arquivo_origem VARCHAR)"
            )
            conexao.execute(
                "INSERT INTO chirps VALUES (?, ?, ?, ?)",
                [-2.0, -44.0, 12.5, "raw/chirps-v3.0.202401.tar.gz"],
            )
            competencia = conexao.execute(consulta_para("chirps")).fetchone()[-1]
        self.assertEqual(competencia.isoformat(), "2024-01-01")

    def test_coleta_seletiva_nao_consulta_fontes_fora_do_mvp(self) -> None:
        tarefas, erros, periodos = tarefas_coleta(2, {}, (2024, 2024), {"oni"})
        self.assertEqual([tarefa[0] for tarefa in tarefas], ["oni"])
        self.assertEqual(erros, [])
        self.assertEqual(periodos["chirps"], "fonte não selecionada")
        self.assertEqual(periodos["icoads"], "fonte não selecionada")


class TestesGeometria(unittest.TestCase):
    def test_ponto_em_poligono_e_extracao_das_nove_ufs(self) -> None:
        quadrado = [[0, 0], [1, 0], [1, 1], [0, 1]]
        self.assertTrue(anel_contem_ponto(0.5, 0.5, quadrado))
        self.assertFalse(anel_contem_ponto(2.0, 2.0, quadrado))
        geojson = {
            "features": [
                {
                    "properties": {"CD_UF": str(codigo)},
                    "geometry": {"type": "Polygon", "coordinates": [quadrado]},
                }
                for codigo in range(21, 30)
            ]
        }
        self.assertEqual(len(extrair_poligonos(geojson, "CD_UF")), 9)


if __name__ == "__main__":
    unittest.main()


class TestesComposto(unittest.TestCase):
    def test_composto_soma_anomalia_media_a_climatologia(self) -> None:
        import pandas as pd

        from src.analise.projetar_el_nino import composto

        serie = pd.DataFrame({
            "ano": [2000, 2001, 2002, 2003],
            "uf_codigo_ibge": ["23"] * 4,
            "mes": [3] * 4,
            "chuva_media_mm": [60.0, 120.0, 20.0, 200.0],
        })
        clim = pd.Series([100.0], index=pd.MultiIndex.from_tuples([("23", 3)], names=["uf_codigo_ibge", "mes"]))
        resultado = composto("chuva", serie, clim, [2000, 2002], 0).iloc[0]
        self.assertAlmostEqual(resultado.composto, 40.0)  # 100 + média(-40, -80)
        self.assertEqual(resultado.abaixo_da_media, 2)
        self.assertEqual(resultado.episodios, 2)
        seguinte = composto("chuva", serie, clim, [2000, 2002], 1).iloc[0]
        self.assertAlmostEqual(seguinte.composto, 160.0)  # anos +1: 2001 e 2003
