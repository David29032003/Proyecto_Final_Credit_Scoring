"""Variables derivadas (sección 6.3).

Todas se calculan únicamente con información disponible en T0 (ver catálogo de
6.2), de forma determinística y sin usar estadísticos de la muestra, para que el
mismo código sirva en desarrollo y en producción sin diferencias.

La cuota del nuevo crédito se estima con la TEA de referencia del producto
(`cfg.REFERENCE_ANNUAL_RATE`) y no con `annual_interest_rate_offer`, que es
endógena al riesgo y está excluida del modelo.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config as cfg
from .risk_appetite import monthly_installment

# Tope para ratios con denominador pequeño (ingreso verificable cercano a cero).
DTI_VERIFICABLE_CAP = 10.0

# feature, fórmula, racional de negocio, signo esperado sobre el riesgo, uso
FEATURE_DOC = [
    ("cuota_estimada",
     "monto * r / (1 - (1+r)^-plazo), con r = (1+TEA_ref)^(1/12) - 1",
     "Cuota mensual del crédito solicitado. Es el insumo de todas las medidas de capacidad de pago.",
     "-", "Insumo (no predictor)"),
    ("ingreso_verificable",
     "monthly_income * (1 - cash_income_share)",
     "Parte del ingreso con trazabilidad (depósitos, transferencias). En un cliente rural informal es lo único que la Caja puede sustentar ante una revisión.",
     "-", "Insumo (no predictor)"),
    ("dti_post",
     "(monthly_debt_payment + cuota_estimada) / monthly_income",
     "Carga de deuda total si se aprueba el crédito. El `dti` del dataset solo mide la deuda vigente e ignora la cuota nueva, que es justo lo que decide la aprobación.",
     "+", "Predictor y regla de política"),
    ("dti_post_verificable",
     "(monthly_debt_payment + cuota_estimada) / ingreso_verificable, acotado a 10",
     "Versión exigente del DTI: mide la carga contra el ingreso sustentable. Penaliza al cliente cuya capacidad depende de efectivo no verificable, sin excluirlo por ser informal.",
     "+", "Predictor"),
    ("excedente_per_capita",
     "(monthly_income - monthly_debt_payment - cuota_estimada) / (1 + household_dependents)",
     "Excedente mensual por miembro del hogar tras pagar todas las cuotas. Es la métrica clásica de microfinanzas: dos clientes con igual DTI no tienen la misma holgura si uno mantiene a 5 personas.",
     "-", "Predictor"),
    ("colchon_ahorro_meses",
     "savings_balance / cuota_estimada",
     "Cuántas cuotas podría pagar el cliente con sus ahorros si su ingreso se interrumpe. Clave en un producto con ingreso estacional (una mala cosecha).",
     "-", "Predictor"),
    ("ahorro_sobre_monto",
     "savings_balance / requested_amount",
     "Capacidad de ahorro frente al tamaño del crédito pedido. Señal de disciplina financiera y de que el monto solicitado es proporcional al cliente.",
     "-", "Predictor"),
    ("deuda_por_obligacion",
     "monthly_debt_payment / (1 + active_loans)",
     "Cuota promedio por obligación vigente. Separa al cliente con varias deudas chicas del que tiene una deuda grande con el mismo pago total.",
     "+", "Predictor"),
    ("intensidad_busqueda",
     "bureau_inquiries_6m / (1 + active_loans)",
     "Consultas al buró por obligación vigente. Muchas consultas sin deudas nuevas sugieren búsqueda activa de crédito, señal temprana de estrés de liquidez.",
     "+", "Predictor"),
    ("antiguedad_relativa",
     "employment_tenure_months / ((age - 14) * 12), acotado a 1",
     "Qué proporción de su vida laboral posible lleva el cliente en la actividad actual. Normaliza la antigüedad por edad: 24 meses valen distinto a los 20 que a los 55 años. El tope en 1 corrige de paso las 100 inconsistencias detectadas en 6.3.",
     "-", "Predictor"),
    ("campana_siembra",
     "1 si el mes de observation_date está entre setiembre y diciembre",
     "Marca las originaciones de la campaña agrícola grande (siembra), cuyo repago depende de una cosecha aún no realizada. El default por mes de originación es más alto en ese tramo.",
     "+", "Predictor"),
    ("flag_sin_buro",
     "1 si bureau_score es nulo",
     "Cliente thin-file. El faltante es informativo (perfil sin historial), no un error: el modelo debe poder distinguirlo en lugar de recibir un valor imputado indistinguible de un score real.",
     "?", "Predictor (indicador de faltante)"),
    ("flag_sin_ingreso",
     "1 si monthly_income es nulo",
     "Sin ingreso declarado no hay capacidad de pago calculable; en política obliga a verificación en campo.",
     "?", "Predictor (indicador de faltante)"),
    ("flag_sin_ahorro",
     "1 si savings_balance es nulo",
     "Distingue al cliente sin producto de ahorro en la Caja del que tiene saldo cero.",
     "?", "Predictor (indicador de faltante)"),
]

FEATURE_DOC_COLUMNS = ["feature", "formula", "racional", "signo_esperado", "uso"]

# Derivadas que se ofrecen al modelo (las de uso "Insumo" quedan fuera).
DERIVED_INPUTS = ["cuota_estimada", "ingreso_verificable"]
DERIVED_FEATURES = [f[0] for f in FEATURE_DOC]
DERIVED_CANDIDATES = [f[0] for f in FEATURE_DOC if not f[4].startswith("Insumo")]

# Derivadas evaluadas y descartadas (se documentan para trazabilidad).
DISCARDED_DOC = [
    ("loan_to_income", "requested_amount / monthly_income",
     "Sin poder discriminante (AUC 0.501 en DEV) y muy correlacionada con dti_post."),
    ("monto_vs_mediana_region", "requested_amount / mediana del monto en la región (ajustada en DEV)",
     "AUC 0.501 en DEV; además introduce un estadístico de muestra que hay que versionar, sin ganancia."),
    ("mes_originacion", "mes calendario de observation_date",
     "Reemplazada por campana_siembra: la señal estacional relevante es el tramo de siembra, no el mes como número."),
]


def feature_doc() -> pd.DataFrame:
    return pd.DataFrame(FEATURE_DOC, columns=FEATURE_DOC_COLUMNS)


def discarded_doc() -> pd.DataFrame:
    return pd.DataFrame(DISCARDED_DOC, columns=["feature", "formula", "motivo_descarte"])


def build_features(df: pd.DataFrame, annual_rate: float = cfg.REFERENCE_ANNUAL_RATE) -> pd.DataFrame:
    """Agrega las variables derivadas de 6.3. No modifica el DataFrame original."""
    x = df.copy()
    cuota = pd.Series(monthly_installment(x["requested_amount"], x["term_months"], annual_rate), index=x.index)
    deuda_total = x["monthly_debt_payment"] + cuota

    x["cuota_estimada"] = cuota
    x["ingreso_verificable"] = x["monthly_income"] * (1 - x["cash_income_share"])
    x["dti_post"] = deuda_total / x["monthly_income"]
    x["dti_post_verificable"] = (deuda_total / x["ingreso_verificable"]).clip(upper=DTI_VERIFICABLE_CAP)
    x["excedente_per_capita"] = (x["monthly_income"] - deuda_total) / (1 + x["household_dependents"])
    x["colchon_ahorro_meses"] = x["savings_balance"] / cuota
    x["ahorro_sobre_monto"] = x["savings_balance"] / x["requested_amount"]
    x["deuda_por_obligacion"] = x["monthly_debt_payment"] / (1 + x["active_loans"])
    x["intensidad_busqueda"] = x["bureau_inquiries_6m"] / (1 + x["active_loans"])
    x["antiguedad_relativa"] = (x["employment_tenure_months"] / ((x["age"] - 14) * 12)).clip(upper=1)
    x["campana_siembra"] = x[cfg.DATE_COL].dt.month.isin([9, 10, 11, 12]).astype(int)
    x["flag_sin_buro"] = x["bureau_score"].isna().astype(int)
    x["flag_sin_ingreso"] = x["monthly_income"].isna().astype(int)
    x["flag_sin_ahorro"] = x["savings_balance"].isna().astype(int)
    return x.replace([np.inf, -np.inf], np.nan)
