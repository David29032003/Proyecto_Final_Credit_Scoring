"""Risk Appetite (sección 6.1): umbrales, métricas de cartera y semáforo.

Cada métrica tiene dirección ("min": debe ser >= umbral, "max": debe ser
<= umbral), un umbral verde y un umbral rojo; entre ambos es ámbar.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as cfg

RISK_APPETITE = [
    # dimension, key, metrica, direccion, verde, rojo, racional
    ("Crecimiento", "approval_rate_ttd", "Tasa de aprobación sobre solicitudes (TTD)", "min", 0.70, 0.65,
     "Mandato de crecer fuera de agencias; no caer >13 pp vs. histórico (82.6%)."),
    ("Riesgo", "default_rate_12m", "Default 12m (90+ DPD) de cosechas aprobadas", "max", 0.11, 0.13,
     "Volver a la media histórica (11.6%); 2024-2025 estuvo en 13.4%-14.0%."),
    ("Riesgo", "el_rate", "Expected Loss / monto desembolsado (PD x EAD x LGD)", "max", 0.030, 0.035,
     "Pérdida realizada histórica 2.9%; 2024 llegó a 4.0%."),
    ("Riesgo", "lgd_mean", "LGD media de defaults", "max", 0.65, 0.70,
     "Crédito sin garantía: LGD histórica 62.3%, estable 61%-63%."),
    ("Concentración", "max_region_share", "Mayor participación de una macrorregión en el monto", "max", 0.45, 0.50,
     "Riesgo climático/zonal correlacionado; Lima concentra 41.6%."),
    ("Concentración", "alianza_share", "Participación del canal alianza en el monto", "max", 0.15, 0.20,
     "Riesgo de intermediario (datos inflados); hoy 9.6%."),
    ("Concentración", "new_customer_share", "Participación de clientes nuevos en el monto", "max", 0.50, 0.55,
     "Clientes sin relación: default 12.7% vs 10.7%; hoy 44.8%."),
    ("Concentración", "thin_file_share", "Participación de clientes sin score de buró en el monto", "max", 0.05, 0.08,
     "Espacio para incluir thin-file (hoy 3.2%) con evidencia aún escasa (193 casos)."),
    ("Concentración", "long_term_share", "Participación de plazos > 36 meses en el monto", "max", 0.25, 0.30,
     "Plazos largos exceden la ventana de 12m y el ciclo productivo; hoy 24.1%."),
    ("Concentración", "large_ticket_share", "Participación de montos > S/ 20,000 en el monto", "max", 0.12, 0.15,
     "Tickets fuera del rango de microcrédito; 4.2% de operaciones pero 14.5% del monto."),
    ("Concentración", "remote_share", "Participación de clientes a > 50 km de agencia en el monto", "max", 0.03, 0.05,
     "Costo de servir/cobrar; hoy 1.7%."),
    ("Capacidad de pago", "dti_post_gt60_share", "Monto aprobado con DTI post-crédito > 60%", "max", 0.05, 0.10,
     "Sobreendeudamiento: default 16.8% con DTI post 60%-80%; hoy 21.6% del monto (sin control)."),
    ("Fair lending", "air_region", "Adverse Impact Ratio de aprobación entre macrorregiones", "min", 0.90, 0.80,
     "Regla 4/5; Oriente tiene la menor aprobación (78.8%) con el menor default."),
    ("Fair lending", "air_cash", "Adverse Impact Ratio de aprobación entre quintiles de ingreso en efectivo", "min", 0.90, 0.80,
     "No excluir por falta de trazabilidad bancaria (objetivo del caso)."),
]

APPETITE_COLUMNS = ["dimension", "key", "metrica", "direccion", "verde", "rojo", "racional"]


def appetite_table() -> pd.DataFrame:
    return pd.DataFrame(RISK_APPETITE, columns=APPETITE_COLUMNS)


def traffic_light(value: float, direction: str, green: float, red: float) -> str:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return "N/D"
    if direction == "min":
        return "Verde" if value >= green else ("Ámbar" if value >= red else "Rojo")
    return "Verde" if value <= green else ("Ámbar" if value <= red else "Rojo")


def monthly_installment(amount, term_months, annual_rate=cfg.REFERENCE_ANNUAL_RATE):
    """Cuota de amortización francesa con tasa efectiva anual (TEA) convertida a mensual."""
    amount = np.asarray(amount, dtype="float64")
    n = np.asarray(term_months, dtype="float64")
    r = (1 + np.asarray(annual_rate, dtype="float64")) ** (1 / 12) - 1
    return amount * r / (1 - (1 + r) ** (-n))


def dti_post(df: pd.DataFrame, annual_rate=cfg.REFERENCE_ANNUAL_RATE) -> pd.Series:
    """(Deuda mensual existente + cuota estimada del nuevo crédito) / ingreso mensual."""
    inst = monthly_installment(df["requested_amount"], df["term_months"], annual_rate)
    return (df["monthly_debt_payment"] + inst) / df["monthly_income"]


def _air(approved: pd.Series, groups: pd.Series) -> float:
    rates = approved.groupby(groups, observed=True).mean()
    return float(rates.min() / rates.max())


def portfolio_metrics(apps: pd.DataFrame, approved: pd.Series | None = None) -> dict:
    """Métricas del apetito sobre un conjunto de solicitudes (TTD).

    approved: máscara de aprobación (por defecto, approved_flag histórico).
    La Expected Loss se aproxima con la pérdida realizada EAD x LGD de los defaults.
    """
    approved = apps[cfg.APPROVED_FLAG].eq(1) if approved is None else approved.astype(bool)
    book = apps[approved]
    amount = book["requested_amount"]
    w = amount / amount.sum()
    perf = book[book[cfg.OUTCOME_FILTER].eq(1)]
    loss = (perf["ead_at_default"].fillna(0) * perf["lgd_observed"].fillna(0)).sum()
    region_share = amount.groupby(book["region"]).sum() / amount.sum()
    return {
        "approval_rate_ttd": float(approved.mean()),
        "default_rate_12m": float(perf[cfg.TARGET].mean()),
        "el_rate": float(loss / perf["requested_amount"].sum()),
        "lgd_mean": float(perf.loc[perf[cfg.TARGET].eq(1), "lgd_observed"].mean()),
        "max_region_share": float(region_share.max()),
        "alianza_share": float(w[book["channel"].eq("alianza")].sum()),
        "new_customer_share": float(w[book["new_customer_flag"].eq(1)].sum()),
        "thin_file_share": float(w[book["bureau_score"].isna()].sum()),
        "long_term_share": float(w[book["term_months"].gt(cfg.LONG_TERM_MONTHS)].sum()),
        "large_ticket_share": float(w[book["requested_amount"].gt(cfg.MICRO_MAX_AUTO_AMOUNT)].sum()),
        "remote_share": float(w[book["distance_to_branch_km"].gt(cfg.REMOTE_DISTANCE_KM)].sum()),
        "dti_post_gt60_share": float(w[dti_post(book).gt(cfg.DTI_POST_HARD_MAX)].sum()),
        "air_region": _air(approved, apps["region"]),
        "air_cash": _air(approved, pd.qcut(apps["cash_income_share"], 5)),
    }


def evaluate_appetite(metrics: dict) -> pd.DataFrame:
    """Cruza métricas observadas con el apetito y asigna semáforo."""
    tab = appetite_table()
    tab["valor"] = tab.key.map(metrics)
    tab["semaforo"] = [traffic_light(v, d, g, r) for v, d, g, r in zip(tab.valor, tab.direccion, tab.verde, tab.rojo)]
    return tab
