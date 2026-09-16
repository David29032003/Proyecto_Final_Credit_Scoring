"""Pruebas de la sección 6.3 (calidad, variables derivadas y pipeline).

Ejecutar desde la raíz del repo:  python -m pytest tests  (o  python tests/test_features.py)
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import config as cfg, data, data_dictionary, features, pipeline, quality  # noqa: E402

RAW = data.load_raw()
POP, _ = data.pd_population(RAW)
DEV = POP[POP["sample"] == "DEV"]
COLS_IN = pipeline.pipeline_input_columns()


def _toy() -> pd.DataFrame:
    """Solicitud de control con valores redondos para verificar fórmulas."""
    return pd.DataFrame([{
        cfg.DATE_COL: pd.Timestamp("2023-10-15"), "requested_amount": 10_000.0, "term_months": 12.0,
        "monthly_debt_payment": 500.0, "monthly_income": 4_000.0, "cash_income_share": 0.75,
        "household_dependents": 3, "savings_balance": 2_000.0, "active_loans": 3,
        "bureau_inquiries_6m": 4, "employment_tenure_months": 60, "age": 34, "bureau_score": 650.0,
    }])


def test_build_features_crea_todas_y_no_muta_la_entrada():
    antes = POP.copy()
    x = features.build_features(POP)
    assert all(c in x.columns for c in features.DERIVED_FEATURES)
    assert len(x) == len(POP)
    pd.testing.assert_frame_equal(POP, antes)  # la función no modifica su entrada


def test_cuota_amortiza_el_credito():
    """La cuota estimada debe dejar saldo cero al final del plazo (amortización francesa)."""
    t = _toy()
    cuota = float(features.build_features(t)["cuota_estimada"].iloc[0])
    r = (1 + cfg.REFERENCE_ANNUAL_RATE) ** (1 / 12) - 1
    saldo = float(t["requested_amount"].iloc[0])
    for _ in range(int(t["term_months"].iloc[0])):
        saldo = saldo * (1 + r) - cuota
    assert abs(saldo) < 1e-6 * float(t["requested_amount"].iloc[0])
    assert cuota * t["term_months"].iloc[0] > t["requested_amount"].iloc[0]  # paga intereses


def test_formulas_de_las_derivadas():
    x = features.build_features(_toy()).iloc[0]
    cuota = x["cuota_estimada"]
    assert x["ingreso_verificable"] == 4_000.0 * 0.25
    assert np.isclose(x["dti_post"], (500.0 + cuota) / 4_000.0)
    assert np.isclose(x["dti_post_verificable"], (500.0 + cuota) / 1_000.0)
    assert np.isclose(x["excedente_per_capita"], (4_000.0 - 500.0 - cuota) / 4)
    assert np.isclose(x["colchon_ahorro_meses"], 2_000.0 / cuota)
    assert np.isclose(x["ahorro_sobre_monto"], 2_000.0 / 10_000.0)
    assert np.isclose(x["deuda_por_obligacion"], 500.0 / 4)
    assert np.isclose(x["intensidad_busqueda"], 4 / 4)
    assert np.isclose(x["antiguedad_relativa"], 60 / ((34 - 14) * 12))
    assert x["campana_siembra"] == 1  # octubre
    assert x["flag_sin_buro"] == 0 and x["flag_sin_ingreso"] == 0 and x["flag_sin_ahorro"] == 0


def test_topes_y_flags_de_faltantes():
    t = _toy()
    t.loc[0, ["bureau_score", "monthly_income", "savings_balance"]] = np.nan
    t.loc[0, "employment_tenure_months"] = 600      # inconsistente con la edad
    x = features.build_features(t).iloc[0]
    assert x["flag_sin_buro"] == 1 and x["flag_sin_ingreso"] == 1 and x["flag_sin_ahorro"] == 1
    assert x["antiguedad_relativa"] == 1.0          # acotada
    assert pd.isna(x["dti_post"])                   # sin ingreso no hay capacidad calculable

    t2 = _toy()
    t2.loc[0, "cash_income_share"] = 0.9999         # ingreso verificable casi nulo
    assert features.build_features(t2)["dti_post_verificable"].iloc[0] == features.DTI_VERIFICABLE_CAP


def test_derivadas_no_usan_variables_prohibidas():
    """build_features debe funcionar sin ninguna columna prohibida presente."""
    sin_prohibidas = POP.drop(columns=data.forbidden_pd_features())
    x = features.build_features(sin_prohibidas)
    assert all(c in x.columns for c in features.DERIVED_FEATURES)


def test_pipeline_se_ajusta_en_dev_y_aplica_igual():
    pipe = pipeline.build_pipeline()
    pipe.fit(DEV[COLS_IN])
    matrices = {s: pipe.transform(POP.loc[POP["sample"] == s, COLS_IN]) for s in cfg.SAMPLE_ORDER}
    columnas = [list(m.columns) for m in matrices.values()]
    assert columnas[0] == columnas[1] == columnas[2]
    for m in matrices.values():
        assert m.isna().sum().sum() == 0
    prohibidas = set(data.forbidden_pd_features())
    assert not prohibidas & set(matrices["DEV"].columns)
    # Una solicitud individual, como la puntuará el servicio de scoring.
    assert pipe.transform(RAW.iloc[[0]][COLS_IN]).shape == (1, matrices["DEV"].shape[1])


def test_winsorizer_usa_topes_del_ajuste():
    w = pipeline.Winsorizer(0.01, 0.99)
    train = pd.DataFrame({"x": list(range(100))})
    w.fit(train)
    fuera = pd.DataFrame({"x": [-500, 500]})
    z = w.transform(fuera)
    assert z["x"].iloc[0] == w.lower_["x"] and z["x"].iloc[1] == w.upper_["x"]
    assert z["x"].max() <= train["x"].max()


def test_quality_reportes():
    assert quality.duplicates_report(RAW, [cfg.DATE_COL, "age", "requested_amount"])["registros"].sum() == 0
    reglas = quality.consistency_rules(POP)
    assert len(reglas) == len(quality.CONSISTENCY_RULES)
    bloqueantes = reglas[reglas.severidad == "Bloqueante"]
    assert bloqueantes["violaciones"].sum() == 0          # nada que impida usar la población
    comp = quality.completeness(POP, data.pd_candidate_features())
    assert np.isclose(comp.loc["bureau_score", "total"], POP["bureau_score"].isna().mean())
    estab = quality.temporal_stability(POP, data.pd_candidate_features(), ["region", "channel", "employment_type"])
    assert (estab["psi_oot"] < 0.10).all()               # ninguna variable con drift material


def test_diccionario_tecnico_cubre_todo():
    dic = data_dictionary.technical_dictionary()
    assert set(RAW.columns) | set(features.DERIVED_FEATURES) <= set(dic["variable"])
    assert not dic["variable"].duplicated().any()
    for col in ["transformacion", "imputacion", "encoding", "riesgo_leakage", "uso_final"]:
        assert dic[col].notna().all() and (dic[col].astype(str).str.len() > 0).all()
    tasa = dic[dic.variable == "annual_interest_rate_offer"].iloc[0]
    assert "Alto" in tasa["riesgo_leakage"] and "pricing" in tasa["uso_final"]


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
        print("OK ", t.__name__)
    print(f"{len(tests)} pruebas aprobadas")
