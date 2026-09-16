"""Perfilado de calidad de datos (sección 6.3).

Cubre completitud, duplicidad, consistencia y lógica de negocio, rangos y
outliers, cardinalidad y estabilidad temporal. Las funciones devuelven tablas
para poder repetir el perfilado sobre cualquier extracción futura.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as cfg
from .risk_appetite import monthly_installment
from .validation import psi, psi_categorical, psi_label

# Salario mínimo de referencia usado solo como control de plausibilidad.
MIN_WAGE_REF = 1_025

# (regla, función que marca VIOLACIONES, severidad, tratamiento adoptado)
CONSISTENCY_RULES = [
    ("dti = cuota de deuda / ingreso", lambda d: (d.monthly_debt_payment / d.monthly_income - d.dti).abs().gt(1e-3),
     "Alta", "Sin violaciones: el dti del archivo es coherente con sus insumos."),
    ("new_customer_flag = 1 <-> relationship_months = 0", lambda d: d.new_customer_flag.eq(1) != d.relationship_months.eq(0),
     "Alta", "Sin violaciones."),
    ("antigüedad laboral <= (edad - 14) * 12", lambda d: d.employment_tenure_months.gt((d.age - 14) * 12),
     "Media", "Se conserva el registro; la derivada antiguedad_relativa se acota a 1 y la winsorización limita el extremo."),
    ("relación con la Caja <= (edad - 18) * 12", lambda d: d.relationship_months.gt((d.age - 18) * 12),
     "Baja", "Se conserva: es plausible una cuenta de ahorros abierta antes de la mayoría de edad. Se marca para revisión de captura."),
    ("edad entre 18 y 75 años", lambda d: ~d.age.between(18, 75), "Bloqueante", "Sin violaciones."),
    ("edad + plazo <= 75 años al vencimiento", lambda d: (d.age + d.term_months / 12).gt(75),
     "Bloqueante", "Sin violaciones."),
    ("cash_income_share dentro de [0, 1]", lambda d: ~d.cash_income_share.between(0, 1), "Alta", "Sin violaciones."),
    ("dti <= 1", lambda d: d.dti.gt(1), "Alta", "Sin violaciones."),
    ("monto solicitado > 0", lambda d: d.requested_amount.le(0), "Bloqueante", "Sin violaciones."),
    ("plazo dentro del catálogo del producto", lambda d: ~d.term_months.isin([6, 9, 12, 18, 24, 36, 48, 60]),
     "Alta", "Sin violaciones."),
    ("bureau_score dentro de [300, 900]", lambda d: ~(d.bureau_score.between(300, 900) | d.bureau_score.isna()),
     "Alta", "Sin violaciones."),
    ("savings_balance >= 0", lambda d: d.savings_balance.lt(0), "Alta", "Sin violaciones."),
    ("default = 1 -> exposición informada", lambda d: d[cfg.TARGET].eq(1) & d.ead_at_default.isna(),
     "Alta", "Sin violaciones: los 671 defaults tienen EAD y LGD."),
    ("default = 0 -> campos post-default vacíos", lambda d: d[cfg.TARGET].eq(0) & d.ead_at_default.notna(),
     "Alta", "Sin violaciones: no hay contaminación de campos post-evento."),
    ("EAD <= monto solicitado", lambda d: d.ead_at_default.gt(d.requested_amount), "Media", "Sin violaciones."),
    ("recuperaciones <= EAD", lambda d: d.recovery_amount_total.gt(d.ead_at_default), "Media", "Sin violaciones."),
    ("cuota estimada <= ingreso mensual",
     lambda d: pd.Series(monthly_installment(d.requested_amount, d.term_months), index=d.index).gt(d.monthly_income),
     "Alta", "Caso aislado: la solicitud es inviable por capacidad y la regla de DTI la deriva a revisión."),
    (f"ingreso mensual >= S/ {MIN_WAGE_REF:,} (referencia)", lambda d: d.monthly_income.lt(MIN_WAGE_REF),
     "Informativa", "Se conservan: en el segmento rural informal un ingreso bajo la referencia es plausible, no un error."),
    ("distancia a agencia > 0", lambda d: d.distance_to_branch_km.le(0), "Alta", "Sin violaciones."),
]


def completeness(df: pd.DataFrame, cols: list[str], by: str | None = None) -> pd.DataFrame:
    """% de faltantes por variable, opcionalmente abierto por muestra o periodo."""
    total = df[cols].isna().mean().rename("total")
    if by is None:
        return total.to_frame().sort_values("total", ascending=False)
    parts = df.groupby(by)[cols].apply(lambda g: g.isna().mean()).T
    out = parts.join(total)
    return out.loc[out["total"].sort_values(ascending=False).index]


def duplicates_report(df: pd.DataFrame, business_key: list[str]) -> pd.DataFrame:
    """Duplicados por identificador, por fila completa y por clave de negocio."""
    rows = [
        ("Identificador duplicado (application_id)", int(df[cfg.ID_COL].duplicated().sum())),
        ("Fila idéntica en todas las columnas (sin ID)", int(df.drop(columns=cfg.ID_COL).duplicated().sum())),
        (f"Clave de negocio duplicada ({' + '.join(business_key)})", int(df.duplicated(subset=business_key).sum())),
    ]
    out = pd.DataFrame(rows, columns=["control", "registros"])
    out["pct"] = out.registros / len(df)
    return out


def consistency_rules(df: pd.DataFrame, rules=CONSISTENCY_RULES) -> pd.DataFrame:
    """Evalúa las reglas de consistencia y lógica de negocio."""
    rows = []
    for name, fn, severity, treatment in rules:
        flags = fn(df).fillna(False)
        rows.append({"regla": name, "severidad": severity, "violaciones": int(flags.sum()),
                     "pct": float(flags.mean()), "tratamiento": treatment})
    return pd.DataFrame(rows).sort_values(["violaciones", "severidad"], ascending=[False, True])


def outlier_report(df: pd.DataFrame, cols: list[str], k: float = 3.0,
                   lower_q: float = 0.01, upper_q: float = 0.99) -> pd.DataFrame:
    """Rangos, asimetría y outliers por regla de Tukey (k*IQR), con los topes propuestos."""
    rows = []
    for c in cols:
        s = pd.to_numeric(df[c], errors="coerce").dropna()
        q1, q3 = s.quantile([0.25, 0.75])
        iqr = q3 - q1
        fuera = (s < q1 - k * iqr) | (s > q3 + k * iqr)
        rows.append({
            "variable": c, "min": s.min(), "p1": s.quantile(lower_q), "mediana": s.median(),
            "p99": s.quantile(upper_q), "max": s.max(), "asimetria": s.skew(),
            "outliers_iqr": int(fuera.sum()), "pct_outliers": float(fuera.mean()),
            "tope_inferior": s.quantile(lower_q), "tope_superior": s.quantile(upper_q),
        })
    return pd.DataFrame(rows).sort_values("pct_outliers", ascending=False)


def cardinality_report(df: pd.DataFrame, cols: list[str], rare_threshold: float = 0.05) -> pd.DataFrame:
    """Cardinalidad y categorías poco frecuentes (candidatas a agrupación)."""
    rows = []
    for c in cols:
        s = df[c]
        n_unique = int(s.nunique(dropna=False))
        rare = ""
        if s.dtype == object or n_unique <= 12:
            vc = s.value_counts(normalize=True, dropna=False)
            chicas = vc[vc < rare_threshold]
            rare = ", ".join(f"{i} ({p:.1%})" for i, p in chicas.items())
        rows.append({"variable": c, "tipo": str(s.dtype), "n_unicos": n_unique,
                     "pct_unicos": n_unique / len(df), "categorias_menores_al_umbral": rare})
    return pd.DataFrame(rows).sort_values("n_unicos")


def temporal_stability(pop: pd.DataFrame, cols: list[str], cat_cols: list[str],
                       sample_col: str = "sample") -> pd.DataFrame:
    """PSI de cada variable entre DEV y las muestras posteriores."""
    ref = pop[pop[sample_col] == cfg.SAMPLE_ORDER[0]]
    rows = []
    for c in cols:
        fn = psi_categorical if c in cat_cols else psi
        row = {"variable": c}
        for s in cfg.SAMPLE_ORDER[1:]:
            row[f"psi_{s.lower()}"] = fn(ref[c], pop.loc[pop[sample_col] == s, c])
        rows.append(row)
    out = pd.DataFrame(rows)
    out["semaforo"] = out[f"psi_{cfg.SAMPLE_ORDER[-1].lower()}"].map(psi_label)
    return out.sort_values(f"psi_{cfg.SAMPLE_ORDER[-1].lower()}", ascending=False)


def target_stability(pop: pd.DataFrame, freq: str = "Y") -> pd.DataFrame:
    """Tasa de default por periodo de originación (estabilidad del target)."""
    periodo = pop[cfg.DATE_COL].dt.to_period(freq)
    out = pop.groupby(periodo).agg(creditos=(cfg.TARGET, "size"), defaults=(cfg.TARGET, "sum"),
                                   default_rate=(cfg.TARGET, "mean"))
    out["var_vs_periodo_previo"] = out["default_rate"].pct_change()
    return out
