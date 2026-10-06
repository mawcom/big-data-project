"""Geração determinística de observações didáticas simuladas.

Nada aqui é dado observado. A função existe para alimentar a interface enquanto
a ingestão de fontes oficiais ainda não foi implementada.
"""

from __future__ import annotations

import math
from typing import Any

import pandas as pd


REGIONS = ["Sul", "Norte", "Nordeste", "Centro-Oeste", "Sudeste"]
METRICS: dict[str, dict[str, str]] = {
    "rain_anomaly_mm": {"label": "Anomalia de chuva", "unit": "mm"},
    "temperature_anomaly_c": {"label": "Anomalia de temperatura", "unit": "°C"},
    "hotspot_index": {"label": "Índice demonstrativo de focos", "unit": "índice"},
    "extreme_rain_days": {"label": "Dias de chuva intensa", "unit": "dias/mês"},
    "drought_index": {"label": "Índice demonstrativo de seca", "unit": "índice"},
}


def _enso_phase(date: pd.Timestamp) -> str:
    """Fases artificiais para explicar o destaque de períodos no gráfico."""
    year_month = date.strftime("%Y-%m")
    if "2015-03" <= year_month <= "2016-05" or "2023-05" <= year_month <= "2024-05":
        return "El Niño (simulado)"
    if "2010-06" <= year_month <= "2011-05" or "2020-08" <= year_month <= "2022-12":
        return "La Niña (simulada)"
    return "Neutro (simulado)"


def build_demo_frame() -> pd.DataFrame:
    """Cria um quadro mensal didático, reprodutível e claramente sintético."""
    records: list[dict[str, Any]] = []
    dates = pd.date_range("2010-01-01", "2025-12-01", freq="MS")
    for region_index, region in enumerate(REGIONS):
        for date in dates:
            phase = _enso_phase(date)
            month_angle = 2 * math.pi * (date.month - 1) / 12
            long_term_warming = (date.year - 2010) * 0.025
            noise = math.sin((date.year * 12 + date.month) * (region_index + 2))

            # Efeitos construídos para visualização didática; não representam
            # observações nem estimativas calibradas para qualquer região.
            rain_effect = 0.0
            temp_effect = 0.0
            if phase.startswith("El Niño"):
                if region == "Sul":
                    rain_effect, temp_effect = 55.0, 0.35
                elif region in {"Norte", "Nordeste"}:
                    rain_effect, temp_effect = -42.0, 0.65
                else:
                    rain_effect, temp_effect = -18.0, 0.45
            elif phase.startswith("La Niña"):
                if region == "Sul":
                    rain_effect, temp_effect = -35.0, -0.1
                elif region in {"Norte", "Nordeste"}:
                    rain_effect, temp_effect = 22.0, 0.0

            rain_seasonality = 24 * math.sin(month_angle + region_index * 0.7)
            temperature_seasonality = 1.8 * math.sin(month_angle - math.pi / 2)
            rain_anomaly = rain_seasonality + rain_effect + noise * 16
            temperature_anomaly = long_term_warming + temperature_seasonality * 0.22 + temp_effect + noise * 0.22
            drought_index = max(0.0, min(100.0, 48 - rain_anomaly * 0.35 + temperature_anomaly * 8 + noise * 6))
            hotspot_index = max(0.0, 18 + drought_index * 0.8 + temperature_anomaly * 8 + noise * 8)
            extreme_rain_days = max(0, round(1.3 + rain_anomaly / 36 + noise * 0.7))

            records.append({
                "date": date.strftime("%Y-%m-%d"),
                "year": int(date.year),
                "month": int(date.month),
                "region": region,
                "enso_phase": phase,
                "rain_anomaly_mm": round(rain_anomaly, 1),
                "temperature_anomaly_c": round(temperature_anomaly, 2),
                "hotspot_index": round(hotspot_index, 1),
                "extreme_rain_days": int(extreme_rain_days),
                "drought_index": round(drought_index, 1),
                "data_status": "simulado",
            })

    return pd.DataFrame.from_records(records)


def demo_payload() -> dict[str, Any]:
    """Formato usado pela API local do painel."""
    frame = build_demo_frame()
    return {
        "demo": True,
        "regions": REGIONS,
        "metrics": METRICS,
        "years": sorted(frame["year"].unique().tolist()),
        "records": frame.to_dict(orient="records"),
    }
