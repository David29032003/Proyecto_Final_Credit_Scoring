"""Métricas usadas para justificar el esquema temporal (6.2): PSI, AUC univariado
y tamaño de muestra."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score


def psi(expected: pd.Series, actual: pd.Series, bins: int = 10, eps: float = 1e-4) -> float:
    """Population Stability Index con cortes por cuantiles de la muestra de referencia.

    Los faltantes forman su propio bin para que un cambio en la tasa de missing
    también se refleje en el indicador.
    """
    e = pd.Series(expected, dtype="float64")
    a = pd.Series(actual, dtype="float64")
    edges = np.unique(np.nanquantile(e, np.linspace(0, 1, bins + 1)))
    edges[0], edges[-1] = -np.inf, np.inf

    def dist(s):
        b = pd.cut(s, edges).cat.add_categories("missing").fillna("missing")
        return b.value_counts(normalize=True, sort=False)

    de, da = dist(e).clip(lower=eps), dist(a).clip(lower=eps)
    return float(((da - de) * np.log(da / de)).sum())


def psi_categorical(expected: pd.Series, actual: pd.Series, eps: float = 1e-4) -> float:
    """PSI para variables categóricas (cada categoría es un bin; NaN incluido)."""
    de = pd.Series(expected).fillna("missing").value_counts(normalize=True)
    da = pd.Series(actual).fillna("missing").value_counts(normalize=True)
    cats = de.index.union(da.index)
    de, da = de.reindex(cats, fill_value=0).clip(lower=eps), da.reindex(cats, fill_value=0).clip(lower=eps)
    return float(((da - de) * np.log(da / de)).sum())


def psi_label(value: float) -> str:
    if value < 0.10:
        return "Verde"
    return "Ámbar" if value < 0.25 else "Rojo"


def univariate_auc(y: pd.Series, x: pd.Series) -> float:
    """AUC univariado orientado al riesgo (>=0.5); imputa faltantes con la mediana."""
    x = pd.Series(x, dtype="float64")
    auc = roc_auc_score(y, x.fillna(x.median()))
    return max(auc, 1 - auc)


def auc_standard_error(auc: float, n_pos: int, n_neg: int) -> float:
    """Error estándar de Hanley & McNeil (1982) para dimensionar muestras."""
    q1 = auc / (2 - auc)
    q2 = 2 * auc**2 / (1 + auc)
    var = (auc * (1 - auc) + (n_pos - 1) * (q1 - auc**2) + (n_neg - 1) * (q2 - auc**2)) / (n_pos * n_neg)
    return float(np.sqrt(var))
