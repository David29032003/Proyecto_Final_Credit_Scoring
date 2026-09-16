"""Data Dictionary técnico (sección 6.3).

Toma el catálogo de variables de 6.2 (rol, fuente, disponibilidad en T0 y uso en
PD) y lo enriquece con las decisiones de tratamiento: transformación, imputación,
encoding, riesgo de leakage y uso final. Incluye también las variables derivadas
creadas en 6.3.
"""
from __future__ import annotations

import pandas as pd

from . import data as data_mod
from . import features as feat

CAT_COLS = ["region", "channel", "employment_type"]

_WINSOR = "Winsorización p1-p99 (topes ajustados en DEV)"
_MEDIANA = "Mediana de DEV"
_ONEHOT = "One-hot; una categoría no vista en producción queda en todo ceros"

# Especificaciones por defecto según el rol/uso que trae el catálogo de 6.2.
_DEFAULTS = {
    "Candidata": dict(transformacion=_WINSOR, imputacion=_MEDIANA, encoding="No aplica (numérica)",
                      riesgo_leakage="Bajo: medida en T0", uso_final="Modelo PD"),
    "Candidata (fairness)": dict(transformacion=_WINSOR, imputacion=_MEDIANA, encoding="No aplica (numérica)",
                                 riesgo_leakage="Bajo: medida en T0",
                                 uso_final="Modelo PD sujeto a revisión de discriminación indirecta"),
    "Excluida": dict(transformacion="No se transforma", imputacion="No aplica", encoding="No aplica",
                     riesgo_leakage="Alto: incorpora la evaluación de riesgo de la política anterior",
                     uso_final="Solo análisis de pricing"),
    "Filtro": dict(transformacion="No se transforma", imputacion="No aplica", encoding="No aplica",
                   riesgo_leakage="Posterior a la decisión", uso_final="Filtro de población PD"),
    "Target": dict(transformacion="No se transforma", imputacion="No aplica", encoding="No aplica",
                   riesgo_leakage="Es el target (T0 + 12m)", uso_final="Variable objetivo del modelo PD"),
    "No": dict(transformacion="No se transforma", imputacion="No aplica", encoding="No aplica",
               riesgo_leakage="No aplica", uso_final="No se usa"),
}

# Ajustes específicos que se apartan del comportamiento por defecto.
_OVERRIDES = {
    "observation_date": dict(riesgo_leakage="Ninguno si solo se usa para cortes temporales",
                             uso_final="Split DEV/VAL/OOT y seguimiento de cosechas"),
    "application_id": dict(uso_final="Trazabilidad del scoring"),
    "monthly_income": dict(imputacion=f"{_MEDIANA} + indicador flag_sin_ingreso",
                           riesgo_leakage="Medio: declarado y poco verificable; el riesgo es de manipulación, no temporal"),
    "bureau_score": dict(imputacion=f"{_MEDIANA} + indicador flag_sin_buro",
                         riesgo_leakage="Bajo, siempre que la consulta se archive con la fecha de la solicitud"),
    "savings_balance": dict(imputacion=f"{_MEDIANA} + indicador flag_sin_ahorro"),
    "bureau_inquiries_6m": dict(riesgo_leakage="Medio: debe excluir la consulta generada por esta misma solicitud"),
    "employment_tenure_months": dict(transformacion=f"{_WINSOR}; las inconsistencias con la edad se acotan en antiguedad_relativa"),
    "dti": dict(transformacion=f"{_WINSOR}; se complementa con dti_post, que sí incluye la cuota nueva"),
    "requested_amount": dict(riesgo_leakage="Bajo: es el monto solicitado; si hay contraoferta, el score se recalcula"),
    "term_months": dict(riesgo_leakage="Bajo: es el plazo solicitado; si hay contraoferta, el score se recalcula"),
    "approved_flag": dict(riesgo_leakage="Crítico: es la decisión que el modelo debe reemplazar",
                          uso_final="Solo análisis de sesgo de selección"),
    "ead_at_default": dict(uso_final="No usar en PD; insumo de exposición"),
    "balance_at_default": dict(uso_final="No usar en PD; insumo de exposición"),
    "recovery_amount_total": dict(uso_final="No usar en PD; insumo de severidad"),
    "recovery_cost_total": dict(uso_final="No usar en PD; insumo de severidad"),
    "months_to_recovery": dict(uso_final="No usar en PD; insumo de severidad"),
    "lgd_observed": dict(uso_final="No usar en PD; insumo de severidad"),
}
_POST_DEFAULT_LEAKAGE = "Crítico: se conoce después del incumplimiento"


def _spec_for(row) -> dict:
    spec = dict(_DEFAULTS.get(row.uso_pd, _DEFAULTS["No"]))
    if row.variable in CAT_COLS:
        spec.update(transformacion="No se transforma", imputacion="Moda de DEV", encoding=_ONEHOT)
    if row.rol == "Post-default":
        spec.update(riesgo_leakage=_POST_DEFAULT_LEAKAGE)
    if row.rol == "No aplica":
        spec.update(uso_final="Descartada: 100% vacía en este producto")
    spec.update(_OVERRIDES.get(row.variable, {}))
    return spec


def technical_dictionary() -> pd.DataFrame:
    """Diccionario técnico completo: variables originales + derivadas de 6.3."""
    base = data_mod.variable_catalog()
    specs = pd.DataFrame([_spec_for(r) for r in base.itertuples()], index=base.index)
    base = pd.concat([base, specs], axis=1)
    base.insert(1, "origen", "Original del dataset")

    doc = feat.feature_doc()
    derivadas = pd.DataFrame({
        "variable": doc.feature,
        "origen": "Derivada en 6.3",
        "rol": "Derivada",
        "fuente": "Calculada a partir de variables de T0",
        "momento": "T0",
        "disponible_T0": "Sí",
        "uso_pd": ["Insumo" if u.startswith("Insumo") else "Candidata" for u in doc.uso],
        "racional": doc.racional,
        "uso_oficial": "No aplica (no está en el diccionario oficial)",
        "transformacion": doc.formula,
        "imputacion": [("No aplica (sin faltantes)" if f.startswith("flag_") else _MEDIANA) for f in doc.feature],
        "encoding": "No aplica (numérica)",
        "riesgo_leakage": "Bajo: solo usa insumos de T0 y no depende de estadísticos de la muestra",
        "uso_final": doc.uso,
    })
    return pd.concat([base, derivadas], ignore_index=True)
