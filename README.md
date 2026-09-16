# Credit Risk Capstone · Caso 15 · Caja Rural 360

Trabajo Integrador Final de **Credit Risk & Scoring Analytics 2026** (DMC Institute). Caso: **microcrédito rural amortizable y sin garantía** para clientes independientes con ingresos parcialmente en efectivo. El objetivo de la entidad es crecer fuera de agencias sin excluir automáticamente a quien no tiene trazabilidad bancaria.

> Datos 100% sintéticos con fines académicos (`data/raw/`, copia de `Dataset/Caso_15`).

## Avance

Este repositorio contiene las secciones **6.1**, **6.2** y **6.3** del enunciado:

| Sección | Tema | Documento | Notebook |
|---|---|---|---|
| 6.1 | Negocio, ciclo de crédito end-to-end, decisión del modelo, Risk Appetite, supuestos, exclusiones y revisión manual | `reports/01_negocio_y_arquitectura_crediticia.md` | `00_negocio_y_poblacion.ipynb` |
| 6.2 | Target, observation date, performance window, población, sesgos, split temporal y variables disponibles en T0 | `reports/02_definicion_modelo_y_poblacion.md` | `00_negocio_y_poblacion.ipynb` |
| 6.3 | Perfilado de calidad, diccionario técnico, pipeline de faltantes y categóricas, variables derivadas y estabilidad temporal | `reports/03_data_strategy_calidad_features.md` | `01_calidad_y_features.ipynb` |

## Definiciones clave

- **Target:** `default_12m_flag` = 90 o más días de mora en (T0, T0 + 12m], con T0 = `observation_date`.
- **Población PD:** `outcome_available_flag = 1` → 5,783 créditos, 671 defaults (11.60%). Los 1,217 rechazados se excluyen: no son "buenos".
- **Split temporal:** DEV 2021-2023 (10.2%) · VAL 2024 (14.0%) · OOT 2025 (13.4%).
- **Variables prohibidas en PD:** tasa ofrecida (endógena), indicadores de decisión y target, y todos los campos posteriores al default (`data.forbidden_pd_features()`).
- **Tratamiento de datos:** un único pipeline (variables derivadas → winsorización p1-p99 → imputación → one-hot) ajustado solo con DEV y aplicable a una solicitud individual (`pipeline.build_pipeline()`).

## Estructura

```
credit-risk-capstone/
├── data/
│   ├── raw/                  data.csv, diccionario_datos.csv, README.txt (Caso 15)
│   └── processed/            pd_population.csv y pd_population_features.csv
├── notebooks/
│   ├── 00_negocio_y_poblacion.ipynb   evidencia de 6.1 y 6.2
│   └── 01_calidad_y_features.ipynb    evidencia de 6.3
├── src/
│   ├── config.py             rutas, target, split temporal, parámetros de política
│   ├── data.py               carga, catálogo de variables, población PD, split
│   ├── risk_appetite.py      umbrales del apetito, métricas de cartera y semáforo
│   ├── validation.py         PSI y AUC univariado (justificación del split)
│   ├── quality.py            perfilado de calidad y reglas de consistencia
│   ├── features.py           variables derivadas con fórmula y racional
│   ├── pipeline.py           pipeline de winsorización, imputación y encoding
│   ├── data_dictionary.py    diccionario técnico (tratamiento, leakage, uso final)
│   └── diagrams.py           diagrama del ciclo de crédito
├── tests/
│   ├── test_data.py          población, split, catálogo y rangos
│   └── test_features.py      calidad, fórmulas de las derivadas y pipeline
├── reports/
│   ├── 01_negocio_y_arquitectura_crediticia.md
│   ├── 02_definicion_modelo_y_poblacion.md
│   ├── 03_data_strategy_calidad_features.md
│   ├── figures/              fig01-fig10 (PNG)
│   └── tables/               CSV citados en los reportes
└── requirements.txt
```

## Cómo ejecutar

```bash
pip install -r requirements.txt
```

```bash
python -m pytest tests
```

```bash
jupyter notebook notebooks/00_negocio_y_poblacion.ipynb
```

El notebook corre de arriba hacia abajo, desde `notebooks/` o desde la raíz, y regenera `data/processed/`, `reports/tables/` y `reports/figures/`. La semilla está en `src/config.py` (`SEED = 42`). Si no tienes pytest, las pruebas también corren con `python tests/test_data.py`.
