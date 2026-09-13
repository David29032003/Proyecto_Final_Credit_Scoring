"""Pruebas de las definiciones de 6.1 y 6.2 (población, split, catálogo, apetito).

Ejecutar desde la raíz del repo:  python -m pytest tests  (o  python tests/test_data.py)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src import config as cfg, data, risk_appetite, validation  # noqa: E402

RAW = data.load_raw()
POP, WATERFALL = data.pd_population(RAW)


def test_columnas_requeridas():
    dic = data.load_dictionary()
    assert list(RAW.columns) == dic["variable"].tolist()
    for col in [cfg.ID_COL, cfg.DATE_COL, cfg.TARGET, cfg.OUTCOME_FILTER, cfg.APPROVED_FLAG]:
        assert col in RAW.columns


def test_catalogo_cubre_todas_las_columnas():
    cat = data.variable_catalog()
    assert set(cat["variable"]) == set(RAW.columns)
    assert not cat["variable"].duplicated().any()


def test_poblacion_pd_sin_rechazados_ni_outcome_faltante():
    data.check_population(POP)
    assert len(POP) == int(RAW[cfg.OUTCOME_FILTER].sum())
    assert WATERFALL["remanentes"].iloc[-1] == len(POP)


def test_target_oficial():
    assert POP[cfg.TARGET].isin([0, 1]).all()
    assert abs(POP[cfg.TARGET].mean() - 0.1160) < 0.0005  # README del caso: 11.60%


def test_split_temporal_sin_solapamiento_y_completo():
    assert set(POP["sample"]) == set(cfg.SAMPLE_ORDER)
    years = POP.groupby("sample")[cfg.DATE_COL].agg(lambda s: set(s.dt.year))
    assert years["DEV"] == {2021, 2022, 2023}
    assert years["VAL"] == {2024}
    assert years["OOT"] == {2025}
    for s in cfg.SAMPLE_ORDER:  # eventos suficientes por muestra
        assert POP.loc[POP["sample"] == s, cfg.TARGET].sum() >= 150


def test_features_prohibidas_fuera_de_candidatas():
    cands = set(data.pd_candidate_features())
    forbidden = set(data.forbidden_pd_features())
    assert not cands & forbidden
    post_event = {"ead_at_default", "balance_at_default", "recovery_amount_total", "recovery_cost_total",
                  "months_to_recovery", "lgd_observed", "approved_flag", "default_12m_flag",
                  "annual_interest_rate_offer"}
    assert post_event <= forbidden
    assert all(RAW[c].notna().any() for c in cands)  # ninguna candidata es 100% vacía


def test_rangos_de_variables_candidatas():
    assert RAW["age"].between(18, 100).all()
    assert RAW["cash_income_share"].between(0, 1).all()
    assert RAW["dti"].between(0, 1.5).all()
    assert (RAW["requested_amount"] > 0).all()
    assert RAW["term_months"].isin([6, 9, 12, 18, 24, 36, 48, 60]).all()
    assert RAW["bureau_score"].dropna().between(300, 900).all()


def test_psi_identico_es_cero():
    s = POP["bureau_score"]
    assert validation.psi(s, s) < 1e-9
    assert validation.psi_categorical(POP["region"], POP["region"]) < 1e-9


def test_semaforo_apetito():
    assert risk_appetite.traffic_light(0.10, "max", 0.11, 0.13) == "Verde"
    assert risk_appetite.traffic_light(0.12, "max", 0.11, 0.13) == "Ámbar"
    assert risk_appetite.traffic_light(0.14, "max", 0.11, 0.13) == "Rojo"
    assert risk_appetite.traffic_light(0.66, "min", 0.70, 0.65) == "Ámbar"
    m = risk_appetite.portfolio_metrics(RAW)
    assert abs(m["approval_rate_ttd"] - RAW[cfg.APPROVED_FLAG].mean()) < 1e-12
    assert set(m) == set(risk_appetite.appetite_table()["key"])


if __name__ == "__main__":
    tests = [v for k, v in dict(globals()).items() if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
        print("OK ", t.__name__)
    print(f"{len(tests)} pruebas aprobadas")
