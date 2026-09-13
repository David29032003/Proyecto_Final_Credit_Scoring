"""Carga, catálogo de variables, población de modelamiento y split temporal.

Materializa las definiciones de la sección 6.2: target, población, exclusiones,
esquema DEV/VAL/OOT y disponibilidad de variables en el momento de la decisión.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as cfg

# -----------------------------------------------------------------------------
# Catálogo de variables: rol, fuente, momento de disponibilidad y uso en PD.
# "T0" = observation_date (momento de la decisión de originación).
# uso_pd:
#   Candidata                -> disponible en T0 y permitida como predictor
#   Candidata (fairness)     -> disponible y permitida, pero requiere revisar
#                               riesgo de discriminación indirecta antes de usarla
#   Excluida                 -> disponible en T0 pero NO se usa en PD (endógena)
#   Filtro / Target / No     -> no es predictor
# -----------------------------------------------------------------------------
_CATALOG = [
    # variable, rol, fuente, momento, disponible_T0, uso_pd, racional
    ("application_id", "ID", "Sistema de originación", "T0", "Sí", "No",
     "Identificador; sin contenido de riesgo."),
    ("observation_date", "Tiempo", "Sistema de originación", "T0", "Sí", "No",
     "Solo para split temporal y seguimiento de cosechas."),
    ("entity", "Metadato", "Constante", "T0", "Sí", "No", "Constante (1 valor)."),
    ("product", "Metadato", "Constante", "T0", "Sí", "No", "Constante (1 valor)."),
    ("age", "Solicitud", "Documento de identidad / RENIEC", "T0", "Sí", "Candidata (fairness)",
     "Característica protegida en marcos de fair lending; sin reglas de rechazo por edad fuera de la elegibilidad legal."),
    ("region", "Solicitud", "Dirección declarada", "T0", "Sí", "Candidata (fairness)",
     "Riesgo de discriminación territorial (énfasis del caso)."),
    ("channel", "Proceso", "Canal de captación", "T0", "Sí", "Candidata",
     "Variable de proceso; útil para reglas operativas (fraude, verificación)."),
    ("employment_type", "Solicitud", "Declarado", "T0", "Sí", "Candidata",
     "Tipo de actividad económica declarada."),
    ("monthly_income", "Solicitud", "Declarado / estimado por asesor", "T0", "Sí", "Candidata",
     "Disponible pero difícil de verificar cuando es en efectivo; 2.4% faltante."),
    ("employment_tenure_months", "Solicitud", "Declarado", "T0", "Sí", "Candidata",
     "Antigüedad de la actividad; 100 casos inconsistentes con la edad."),
    ("bureau_score", "Buró", "Consulta a buró en T0", "T0", "Sí", "Candidata",
     "3.3% sin score (thin-file): el faltante es informativo y NO excluye."),
    ("prior_delinquencies_24m", "Buró", "Consulta a buró en T0", "T0", "Sí", "Candidata",
     "Historial de mora de los 24 meses previos a T0."),
    ("bureau_inquiries_6m", "Buró", "Consulta a buró en T0", "T0", "Sí", "Candidata",
     "Consultas previas a T0 (sin contar la consulta de esta solicitud)."),
    ("active_loans", "Buró", "Consulta a buró en T0", "T0", "Sí", "Candidata", "Obligaciones vigentes en T0."),
    ("monthly_debt_payment", "Buró", "Consulta a buró en T0", "T0", "Sí", "Candidata",
     "Cuota de deudas existentes; no incluye la cuota del crédito solicitado."),
    ("dti", "Derivada", "Buró / ingreso declarado", "T0", "Sí", "Candidata",
     "= monthly_debt_payment / monthly_income. No incluye la nueva cuota."),
    ("savings_balance", "Interno", "Core de ahorros / declarado", "T0", "Sí", "Candidata",
     "7.7% faltante."),
    ("new_customer_flag", "Interno", "CRM", "T0", "Sí", "Candidata", "Relación previa con la Caja."),
    ("relationship_months", "Interno", "CRM", "T0", "Sí", "Candidata",
     "0 para clientes nuevos (consistente); 205 casos exceden la edad adulta."),
    ("requested_amount", "Solicitud", "Declarado", "T0", "Sí", "Candidata",
     "Monto solicitado (no el aprobado)."),
    ("term_months", "Solicitud", "Declarado", "T0", "Sí", "Candidata",
     "Supuesto: plazo solicitado/propuesto antes de la decisión (existe también en rechazados)."),
    ("annual_interest_rate_offer", "Política", "Motor de pricing histórico", "T0 (output de política)", "Sí", "Excluida",
     "Endógena: resulta de la evaluación de riesgo previa (corr. Spearman -0.43 con bureau_score)."),
    ("collateral_value", "No aplica", "-", "-", "No", "No", "100% vacío: producto sin garantía."),
    ("ltv", "No aplica", "-", "-", "No", "No", "100% vacío: producto sin garantía."),
    ("credit_limit", "No aplica", "-", "-", "No", "No", "100% vacío: producto no revolvente."),
    ("balance_at_observation", "No aplica", "-", "-", "No", "No", "100% vacío: producto no revolvente."),
    ("utilization_at_observation", "No aplica", "-", "-", "No", "No", "100% vacío: producto no revolvente."),
    ("undrawn_amount_at_observation", "No aplica", "-", "-", "No", "No", "100% vacío: producto no revolvente."),
    ("distance_to_branch_km", "Solicitud", "Geocodificación de la dirección", "T0", "Sí", "Candidata (fairness)",
     "Proxy de ruralidad/territorio; más relevante para costo de servir y cobranza."),
    ("household_dependents", "Solicitud", "Declarado", "T0", "Sí", "Candidata (fairness)",
     "Proxy de situación familiar."),
    ("cash_income_share", "Solicitud", "Declarado / evaluación del asesor", "T0", "Sí", "Candidata (fairness)",
     "Proxy de informalidad: no debe penalizar por sí misma sin evidencia de riesgo (objetivo del caso)."),
    ("approved_flag", "Decisión", "Decisión histórica", "Post-decisión", "No", "No",
     "Resultado de la decisión que el modelo busca reemplazar; genera sesgo de selección."),
    ("outcome_available_flag", "Filtro", "Performance", "T0+12m", "No", "Filtro",
     "Filtro obligatorio de población PD (=1)."),
    ("default_12m_flag", "Target PD", "Performance", "T0+12m", "No", "Target", "90+ DPD en (T0, T0+12m]."),
    ("ead_at_default", "Post-default", "Performance", "Fecha de default", "No", "No", "Exposición al default."),
    ("balance_at_default", "Post-default", "Performance", "Fecha de default", "No", "No",
     "Idéntica a ead_at_default en el 100% de defaults."),
    ("ccf_observed", "No aplica", "-", "-", "No", "No", "100% vacío: producto no revolvente."),
    ("recovery_amount_total", "Post-default", "Workout", "Post-default", "No", "No", "Recuperaciones."),
    ("recovery_cost_total", "Post-default", "Workout", "Post-default", "No", "No", "Costos de recuperación."),
    ("months_to_recovery", "Post-default", "Workout", "Post-default", "No", "No", "Tiempo de workout."),
    ("lgd_observed", "Post-default", "Workout", "Post-default", "No", "No", "Severidad observada."),
]

CATALOG_COLUMNS = ["variable", "rol", "fuente", "momento", "disponible_T0", "uso_pd", "racional"]


def load_raw(path=cfg.RAW_DATA_FILE) -> pd.DataFrame:
    """Lee data.csv (con BOM) y tipa la fecha de observación."""
    df = pd.read_csv(path, encoding="utf-8-sig")
    df[cfg.DATE_COL] = pd.to_datetime(df[cfg.DATE_COL], errors="coerce")
    return df


def load_dictionary(path=cfg.DICTIONARY_FILE) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8-sig")


def variable_catalog(dictionary: pd.DataFrame | None = None) -> pd.DataFrame:
    """Catálogo propio + uso oficial del diccionario, para trazabilidad."""
    cat = pd.DataFrame(_CATALOG, columns=CATALOG_COLUMNS)
    if dictionary is None:
        dictionary = load_dictionary()
    off = dictionary[["variable", "uso_modelamiento"]].rename(columns={"uso_modelamiento": "uso_oficial"})
    return cat.merge(off, on="variable", how="left")


def pd_candidate_features(catalog: pd.DataFrame | None = None) -> list[str]:
    """Variables disponibles en T0 y permitidas para el modelo PD."""
    cat = catalog if catalog is not None else variable_catalog()
    return cat.loc[cat.uso_pd.str.startswith("Candidata"), "variable"].tolist()


def fairness_review_features(catalog: pd.DataFrame | None = None) -> list[str]:
    cat = catalog if catalog is not None else variable_catalog()
    return cat.loc[cat.uso_pd.eq("Candidata (fairness)"), "variable"].tolist()


def forbidden_pd_features(catalog: pd.DataFrame | None = None) -> list[str]:
    """Lista de variables prohibidas como predictor PD (leakage, endógenas, targets)."""
    cat = catalog if catalog is not None else variable_catalog()
    mask = cat.uso_pd.isin(["Excluida", "Filtro", "Target"]) | cat.rol.isin(["Decisión", "Post-default"])
    return cat.loc[mask, "variable"].tolist()


def assign_sample(dates: pd.Series, splits: dict = cfg.TEMPORAL_SPLITS) -> pd.Series:
    """Etiqueta DEV/VAL/OOT según observation_date (límites inclusivos)."""
    out = pd.Series(np.nan, index=dates.index, dtype="object")
    for name, (start, end) in splits.items():
        mask = dates.between(pd.Timestamp(start), pd.Timestamp(end))
        out[mask] = name
    return out


def pd_population(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Aplica los filtros de población PD y devuelve (población, waterfall)."""
    steps = []

    def log(criterio, before, after):
        steps.append({"paso": len(steps), "criterio": criterio,
                      "excluidos": len(before) - len(after), "remanentes": len(after)})

    start, end = cfg.TEMPORAL_SPLITS[cfg.SAMPLE_ORDER[0]][0], cfg.TEMPORAL_SPLITS[cfg.SAMPLE_ORDER[-1]][1]
    x = df.copy()
    steps.append({"paso": 0, "criterio": "Solicitudes en data.csv", "excluidos": 0, "remanentes": len(x)})

    y = x.drop_duplicates(subset=cfg.ID_COL, keep="first")
    log("Duplicados de application_id", x, y); x = y

    y = x[x[cfg.DATE_COL].between(pd.Timestamp(start), pd.Timestamp(end))]
    log("observation_date nula o fuera de 2021-2025", x, y); x = y

    y = x[x[cfg.APPROVED_FLAG].eq(1)]
    log("Rechazados por la política histórica (approved_flag=0): sin performance", x, y); x = y

    y = x[x[cfg.OUTCOME_FILTER].eq(1)]
    log("Aprobados sin ventana de performance (outcome_available_flag=0)", x, y); x = y

    y = x[x[cfg.TARGET].isin([0, 1])]
    log("Target nulo o no binario", x, y); x = y

    y = x[x["age"].ge(18)]
    log("Edad < 18 (fuera de elegibilidad legal)", x, y); x = y

    x = x.assign(sample=assign_sample(x[cfg.DATE_COL]))
    waterfall = pd.DataFrame(steps)
    waterfall["pct_base"] = waterfall.remanentes / waterfall.remanentes.iloc[0]
    return x.reset_index(drop=True), waterfall


def sample_summary(pop: pd.DataFrame) -> pd.DataFrame:
    g = pop.groupby("sample")
    out = pd.DataFrame({
        "desde": g[cfg.DATE_COL].min().dt.date,
        "hasta": g[cfg.DATE_COL].max().dt.date,
        "n": g.size(),
        "defaults": g[cfg.TARGET].sum(),
        "default_rate": g[cfg.TARGET].mean(),
    }).reindex(cfg.SAMPLE_ORDER)
    out["pct_n"] = out.n / out.n.sum()
    out["pct_defaults"] = out.defaults / out.defaults.sum()
    return out


def check_population(pop: pd.DataFrame) -> None:
    """Invariantes de la población PD; lanza AssertionError si alguna falla."""
    assert pop[cfg.OUTCOME_FILTER].eq(1).all(), "Hay registros sin outcome"
    assert pop[cfg.APPROVED_FLAG].eq(1).all(), "Hay rechazados en la población PD"
    assert pop[cfg.TARGET].isin([0, 1]).all(), "Target no binario"
    assert not pop[cfg.ID_COL].duplicated().any(), "IDs duplicados"
    assert pop["sample"].notna().all(), "Registros sin muestra temporal"
    bounds = pop.groupby("sample")[cfg.DATE_COL].agg(["min", "max"]).reindex(cfg.SAMPLE_ORDER)
    for a, b in zip(cfg.SAMPLE_ORDER[:-1], cfg.SAMPLE_ORDER[1:]):
        assert bounds.loc[a, "max"] < bounds.loc[b, "min"], f"Solapamiento temporal {a}/{b}"
