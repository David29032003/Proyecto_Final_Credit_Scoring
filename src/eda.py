"""
src/eda.py
Caso 15 - Caja Rural 360 | Microcredito rural para independientes

Modulo reutilizable para el EDA orientado a riesgo (seccion 6.4).
No repite el pipeline de calidad/features (ver src/quality.py, src/features.py);
aquí solo se agregan funciones de analisis univariado/bivariado orientadas a
bad rate, cosechas (vintages), tendencias temporales e interacciones.

Convenciones:
- Todas las funciones reciben la base y filtrada a la poblacion modelable
  (outcome_available_flag == 1), salvo que se indique lo contrario.
- Las funciones no imprimen ni grafican directamente: devuelven DataFrames
  o figuras de matplotlib para que el notebook decida como mostrarlas/guardarlas.
"""

from __future__ import annotations

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

TARGET = "default_12m_flag"
OUTCOME_FILTER = "outcome_available_flag"

# -------------------------------------------------------------------------------
# 1. Utilidades generales
# -------------------------------------------------------------------------------

def to_modelable(df: pd.DataFrame) -> pd.DataFrame:
    """Filtra la poblacion modelable de pd (regla obligatoria del enunciado 5.2)."""
    return df.loc[df[OUTCOME_FILTER] == 1].copy()

def overall_bad_rate(df: pd.DataFrame) -> float:
    return df[TARGET].mean()

# -------------------------------------------------------------------------------
# 2. Bad rate por segmento categorico
# -------------------------------------------------------------------------------

def bad_rate_by_category(df: pd.DataFrame, col: str, min_n: int = 30) -> pd.DataFrame:
    """Bad rate, conteo y participacion de cartera por categoria de `col`."""
    g = (
        df.groupby(col, observed=True)[TARGET]
        .agg(bad_rate="mean", n="count")
        .assign(share=lambda x: x["n"] / x["n"].sum())
        .sort_values("bad_rate", ascending=False)
    )
    g["flag_low_n"] = g["n"] < min_n
    return g.reset_index()

# -------------------------------------------------------------------------------
# 3. Bad rate por bins numericos (deciles / bins de negocio)
# -------------------------------------------------------------------------------

def bad_rate_by_decile(df: pd.DataFrame, col: str, q: int = 10) -> pd.DataFrame:
    """Bad rate por decil (o q grupos) de una variable numerica contínua."""
    tmp = df[[col, TARGET]].dropna(subset=[col]).copy()
    tmp["bin"] = pd.qcut(tmp[col], q=q, duplicates="drop")
    g = tmp.groupby("bin", observed=True)[TARGET].agg(bad_rate="mean", n="count")
    g["bin_order"] = range(len(g))
    return g.reset_index()

def bad_rate_by_custom_bins(df: pd.DataFrame, col: str, bins: list, labels=None) -> pd.DataFrame:
    """Bad rate usando cortes de negocio predefinidos (mas estables que qcut para
    variables discretas o con colas largas, e.g. prior_delinquencies_24m)."""
    tmp = df[[col, TARGET]].copy()
    tmp["bin"] = pd.cut(tmp[col], bins=bins, labels=labels, include_lowest=True)
    g = tmp.groupby("bin", observed=True)[TARGET].agg(bad_rate="mean", n="count")
    return g.reset_index()

def missing_rate_vs_bad_rate(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """Compara bad rate entre registros con y sin faltante en `col`.
    Util para decidir si el faltante es MAR/MAR y si conviene un missing-flag."""
    tmp = df.copy()
    tmp["is_missing"] = tmp[col].isna().astype(int)
    g = tmp.groupby("is_missing")[TARGET].agg(bad_rate="mean", n="count")
    return g.reset_index()

# 4. Cosechas (vintages) y tendencia temporal
# -------------------------------------------------------------

def vintage_bad_rate(df: pd.DataFrame, date_col: str = "observation_date",
                     freq: str = "Q") -> pd.DataFrame:
    """Bad rate por cosecha de originación (trimestre por defecto)."""
    tmp = df.copy()
    tmp["vintage"] = pd.to_datetime(tmp[date_col]).dt.to_period(freq).astype(str)
    g = tmp.groupby("vintage")[TARGET].agg(bad_rate="mean", n="count").reset_index()
    return g

def approval_rate_trend(df_full: pd.DataFrame, date_col: str = "observation_date",
                        freq: str = "Q") -> pd.DataFrame:
    """Tasa de aprobación por cosecha usando la base completa (incluye rechazados).
    Se cruza con vintage_bad_rate para evaluar si la política de aprobación
    reaccionó al deterioro de bad rate."""
    tmp = df_full.copy()
    tmp["vintage"] = pd.to_datetime(tmp[date_col]).dt.to_period(freq).astype(str)
    g = tmp.groupby("vintage")["approved_flag"].agg(approval_rate="mean", n="count").reset_index()
    return g

# 5. Interacciones / relaciones no lineales
# ------------------------------------------------------------------------------

def two_way_interaction(df: pd.DataFrame, col_a: str, col_b: str,
                        thr_a: float, thr_b: float,
                        label_a=("bajo", "alto"), label_b=("bajo", "alto")) -> pd.DataFrame:
    """Tabla 2x2 de bad rate para evaluar si dos variables de riesgo se
    combinan de forma aditiva o superaditiva (señal de necesidad de reglas
    de política combinadas / interacciones no lineales para el modelo)."""
    tmp = df.copy()
    tmp["_a"] = np.where(tmp[col_a] >= thr_a, label_a[1], label_a[0])
    tmp["_b"] = np.where(tmp[col_b] >= thr_b, label_b[1], label_b[0])
    g = tmp.groupby(["_a", "_b"])[TARGET].agg(bad_rate="mean", n="count").reset_index()
    return g.rename(columns={"_a": col_a, "_b": col_b})

def selection_bias_check(df_full: pd.DataFrame, col: str = "bureau_score") -> pd.DataFrame:
    """Compara la distribución de `col` entre aprobados y rechazados para
    evidenciar el sesgo de selección mencionado en 5.2/6.2."""
    return df_full.groupby("approved_flag")[col].describe()[["count", "mean", "std", "min", "50%", "max"]]

# ------------------------------------------------------------------------------

# 6. Gráficos (devuelven fig, no hacen plt.show())
# -------------------------------------------------------------

def plot_bad_rate_bars(table: pd.DataFrame, x_col: str, y_col: str = "bad_rate",
                       n_col: str = "n", title: str = "", global_rate: float = None,
                       figsize=(8, 4.5)):
    fig, ax = plt.subplots(figsize=figsize)
    ax.bar(table[x_col].astype(str), table[y_col], color="#7A1F28")
    ax.set_ylabel("Bad rate (default)")
    ax.set_title(title)
    ax.tick_params(axis="x", rotation=45)
    if global_rate is not None:
        ax.axhline(global_rate, color="black", linestyle="--", linewidth=1,
                   label=f"Bad rate global ({global_rate:.1%})")
        ax.legend()
    for i, (y, n) in enumerate(zip(table[y_col], table[n_col])):
        ax.text(i, y, f"n={n}", ha="center", va="bottom", fontsize=7)
    fig.tight_layout()
    return fig

def plot_trend_line(table: pd.DataFrame, x_col: str, y_col: str, title: str = "",
                    figsize=(9, 4.5), secondary: pd.DataFrame = None,
                    secondary_y_col: str = None, secondary_label: str = None):
    fig, ax = plt.subplots(figsize=figsize)
    ax.plot(table[x_col], table[y_col], marker="o", color="#7A1F2B", label=y_col)
    ax.set_ylabel(y_col)
    ax.tick_params(axis="x", rotation=45)
    ax.set_title(title)
    if secondary is not None:
        ax2 = ax.twinx()
        ax2.plot(secondary[x_col], secondary[secondary_y_col], marker="s",
                 color="#4472C4", label=secondary_label)
        ax2.set_ylabel(secondary_label)
    fig.tight_layout()
    return fig


def plot_heatmap_2x2(table: pd.DataFrame, col_a: str, col_b: str, val_col: str = "bad_rate",
                     title: str = "", figsize=(5, 4)):
    pivot = table.pivot(index=col_a, columns=col_b, values=val_col)
    fig, ax = plt.subplots(figsize=figsize)
    im = ax.imshow(pivot.values, cmap="Reds")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels(pivot.columns)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels(pivot.index)
    ax.set_xlabel(col_b)
    ax.set_ylabel(col_a)
    ax.set_title(title)
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            ax.text(j, i, f"{pivot.values[i, j]:.1%}", ha="center", va="center")
    fig.colorbar(im, ax=ax, label=val_col)
    fig.tight_layout()
    return fig