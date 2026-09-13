"""Configuración central del proyecto (Caso 15 - Caja Rural 360).

Constantes que definen target, población, esquema temporal y parámetros de
política, para que notebooks y tests usen exactamente la misma versión.
"""
from pathlib import Path

# --- Rutas -------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
RAW_DATA_FILE = DATA_RAW / "data.csv"
DICTIONARY_FILE = DATA_RAW / "diccionario_datos.csv"
REPORTS = ROOT / "reports"
FIGURES = REPORTS / "figures"
TABLES = REPORTS / "tables"

SEED = 42

# --- Campos estructurales ----------------------------------------------------
ID_COL = "application_id"
DATE_COL = "observation_date"
TARGET = "default_12m_flag"
OUTCOME_FILTER = "outcome_available_flag"
APPROVED_FLAG = "approved_flag"

# --- Definición de default (oficial, sección 5.2 del enunciado) -------------
DEFAULT_DPD_THRESHOLD = 90
PERFORMANCE_WINDOW_MONTHS = 12

# --- Esquema temporal (sección 6.2) ------------------------------------------
# Años calendario completos: cada muestra cubre un ciclo agrícola entero.
# Los límites son inclusivos y se aplican sobre observation_date.
TEMPORAL_SPLITS = {
    "DEV": ("2021-01-01", "2023-12-31"),
    "VAL": ("2024-01-01", "2024-12-31"),
    "OOT": ("2025-01-01", "2025-12-31"),
}
SAMPLE_ORDER = ["DEV", "VAL", "OOT"]

# Control de madurez: cosechas OOT con 12 meses de ventana ya cumplidos a la
# fecha de elaboración (setiembre 2026).
OOT_MATURE_END = "2025-08-31"

# --- Parámetros de negocio usados en el Risk Appetite (sección 6.1) ----------
MICRO_MAX_AUTO_AMOUNT = 20_000   # S/ ; tope de aprobación automática
MAX_AMOUNT_HARD = 30_000         # S/ ; por encima -> otro producto
REMOTE_DISTANCE_KM = 50
HIGH_CASH_SHARE = 0.80
LONG_TERM_MONTHS = 36
# TEA de referencia del producto (~ mediana histórica) para estimar la cuota
# sin usar la tasa ofrecida, que es endógena al riesgo.
REFERENCE_ANNUAL_RATE = 0.30
DTI_POST_AUTO_MAX = 0.45         # capacidad de pago: aprobación automática
DTI_POST_HARD_MAX = 0.60         # por encima -> solo con ajuste de monto/plazo
