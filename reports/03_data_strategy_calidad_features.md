# 6.3 Data Strategy, calidad y feature engineering

**Caso 15 · Caja Rural 360 · Microcrédito rural para independientes**

> **Evidencia:** `notebooks/01_calidad_y_features.ipynb`; tablas en `reports/tables/` (prefijos `calidad_`, `features_`, `diccionario_`) y figuras `fig08` a `fig10`. El código vive en `src/quality.py`, `src/features.py`, `src/pipeline.py` y `src/data_dictionary.py`, y `tests/test_features.py` verifica las reglas. Parte de la población PD y del catálogo de variables definidos en 6.2.

---

## 1. Resumen

- **La base está limpia en lo estructural.** Sin duplicados de ningún tipo, sin valores imposibles y con solo tres variables con faltantes, ninguna por encima del 8%. De 19 reglas de consistencia y lógica de negocio, 15 se cumplen sin excepción.
- **Los faltantes son informativos, no ruido.** No tener score de buró (3.3%) identifica a un cliente thin-file, y no tener saldo de ahorros (7.7%) identifica a quien no tiene ese producto en la Caja. Por eso se imputan **y** se marcan con un indicador, en lugar de solo rellenarlos.
- **El problema no es la calidad del dato, es la cola.** `savings_balance` llega a S/ 243,909 con una mediana de S/ 2,667 (asimetría 11.2). Se resuelve acotando a p1-p99 dentro del pipeline, sin eliminar registros.
- **Las variables son estables; el target no.** El PSI máximo entre DEV y OOT es 0.017, muy por debajo del umbral de 0.10, mientras el default sube de 8.6% a 13.4%. Confirma, ahora con métricas de calidad, que el deterioro es del entorno y no de la población que solicita.
- **Se crearon 14 variables derivadas** (12 candidatas al modelo y 2 insumos), todas con fórmula y racional documentados, y se descartaron 3 tras medirlas. La mejor aporta información que ninguna variable original tenía: `dti_post`, que incorpora la cuota del crédito que se está evaluando.
- **Todo el tratamiento vive en un solo objeto** de scikit-learn, ajustado únicamente con DEV y capaz de puntuar una solicitud individual, que es como lo usará el servicio de scoring.

---

## 2. Perfilado de calidad

### 2.1 Completitud

| Variable | DEV | VAL | OOT | Total | Naturaleza del faltante |
|---|---|---|---|---|---|
| `savings_balance` | 7.4% | 7.8% | 8.5% | 7.7% | Cliente sin producto de ahorro en la Caja |
| `bureau_score` | 3.7% | 3.1% | 2.6% | 3.3% | Cliente thin-file, sin historial en el sistema |
| `monthly_income` | 2.5% | 2.4% | 2.8% | 2.5% | Ingreso no declarado o no estimado en la evaluación |

Las otras 17 variables candidatas no tienen ningún faltante. Lo relevante para producción es que **la tasa de faltantes es estable entre muestras**: la regla de imputación ajustada en DEV sigue siendo válida en las cosechas siguientes, y una subida repentina de estos porcentajes sería una alerta de monitoreo de datos.

### 2.2 Duplicidad

| Control | Registros |
|---|---|
| Identificador duplicado (`application_id`) | 0 |
| Fila idéntica en todas las columnas | 0 |
| Clave de negocio duplicada (fecha + perfil + monto) | 0 |

No se requiere deduplicación. El control por clave de negocio es el que importa en producción: detecta la misma solicitud reingresada por otro canal, un patrón típico de fraude o de doble captura.

### 2.3 Consistencia y lógica de negocio

De 19 reglas evaluadas sobre la población PD, **15 se cumplen sin excepción**. Los 4 hallazgos:

| Hallazgo | Casos | Severidad | Tratamiento |
|---|---|---|---|
| `relationship_months` mayor a la edad adulta posible | 160 (2.8%) | Baja | Se conservan: es plausible una cuenta de ahorros abierta antes de los 18 años. Se reporta al equipo de captura |
| Ingreso menor a la referencia de S/ 1,025 | 103 (1.8%) | Informativa | Se conservan: en el segmento rural informal es plausible, no es un error |
| Antigüedad laboral mayor a la vida laboral posible | 81 (1.4%) | Media | Se conserva el registro; `antiguedad_relativa` se acota a 1 y la winsorización limita el extremo |
| Cuota estimada mayor al ingreso mensual | 1 | Alta | La solicitud es inviable por capacidad; la regla de DTI de 6.1 la deriva a revisión manual |

Dos resultados son especialmente importantes para el Technical Gate del enunciado:

1. **No hay contaminación post-evento dentro de la población:** todo crédito con `default = 0` tiene los campos post-default vacíos y todo `default = 1` los tiene informados, sin excepción.
2. **Las variables derivadas del propio archivo cuadran con sus insumos:** `dti` reproduce exactamente `monthly_debt_payment / monthly_income`, y `new_customer_flag` es coherente con `relationship_months` en el 100% de los casos. Si no cuadraran, habría que sospechar que fueron calculadas en otro momento del tiempo.

### 2.4 Rangos y outliers

Ninguna variable tiene valores imposibles: todos los mínimos y máximos son plausibles para el producto. Lo que hay son colas largas propias de una cartera de microcrédito:

| Variable | Mediana | p99 | Máximo | Asimetría | Outliers (Tukey k=3) |
|---|---|---|---|---|---|
| `savings_balance` | S/ 2,667 | S/ 29,200 | S/ 243,909 | 11.2 | 176 (3.3%) |
| `distance_to_branch_km` | 9.0 | 55.5 | 150.0 | 3.2 | 123 (2.1%) |
| `monthly_debt_payment` | S/ 862 | S/ 5,159 | S/ 21,396 | 3.2 | 78 (1.4%) |
| `requested_amount` | S/ 6,314 | S/ 29,992 | S/ 78,915 | 2.7 | 74 (1.3%) |

**Decisión: winsorizar, no eliminar.** Son clientes reales del producto y borrarlos sesgaría la PD justo en los perfiles de mayor exposición. Se acotan a p1-p99 con topes ajustados en DEV, de modo que un valor extremo no domine el ajuste de un modelo lineal pero el registro conserve su información de riesgo (`fig08`).

### 2.5 Cardinalidad

Las tres variables categóricas tienen entre 4 y 5 niveles y **ninguna categoría baja del 7%** de la población: no hace falta agrupar categorías raras y un one-hot simple es suficiente, manteniendo la interpretabilidad que el caso exige.

Entre las numéricas, cinco son prácticamente continuas (más del 90% de valores únicos: `cash_income_share`, `requested_amount`, `monthly_debt_payment`, `monthly_income`, `savings_balance`) y cuatro son discretas con pocos niveles y colas ralas (`prior_delinquencies_24m`, `bureau_inquiries_6m`, `active_loans`, `household_dependents`), donde los valores altos no llegan al 5% y deberán agruparse al construir el scorecard.

### 2.6 Estabilidad temporal

| Qué se midió | Resultado |
|---|---|
| PSI de las 20 variables candidatas entre DEV y OOT | Máximo 0.017 (`age`); **ninguna** supera el umbral de alerta de 0.10 |
| PSI entre DEV y VAL | Máximo 0.020 (`employment_tenure_months`) |
| Tasa de default por año de originación | 8.6% → 9.7% → 12.4% → 14.0% → 13.4% (+27.7% en 2023, +13.1% en 2024) |

**La población que solicita no cambió; el riesgo sí** (`fig09`). Para el modelamiento esto tiene dos consecuencias concretas: no hace falta re-ajustar transformaciones ni imputaciones por drift de variables, pero sí habrá que recalibrar el nivel de PD, porque el mismo perfil de cliente incumple más que antes.

---

## 3. Variables derivadas

Todas se calculan solo con insumos de T0 y sin estadísticos de la muestra, para que el mismo código funcione igual en desarrollo y en producción. La cuota del crédito se estima con la **TEA de referencia del producto (30%)** y no con `annual_interest_rate_offer`, que está excluida por endógena (6.2).

| Variable | Fórmula | Racional de negocio | Signo esperado |
|---|---|---|---|
| `cuota_estimada` | `monto × r / (1 − (1+r)^−plazo)`, con `r = (1+TEA_ref)^(1/12) − 1` | Cuota mensual del crédito solicitado; insumo de toda medida de capacidad | Insumo |
| `ingreso_verificable` | `monthly_income × (1 − cash_income_share)` | Parte del ingreso con trazabilidad, lo único sustentable ante una revisión | Insumo |
| `dti_post` | `(monthly_debt_payment + cuota_estimada) / monthly_income` | Carga total si se aprueba. El `dti` original ignora la cuota nueva, que es justo lo que se decide | + |
| `dti_post_verificable` | `(monthly_debt_payment + cuota_estimada) / ingreso_verificable`, tope 10 | Mide la carga contra el ingreso sustentable, sin excluir al cliente por informal | + |
| `excedente_per_capita` | `(monthly_income − monthly_debt_payment − cuota_estimada) / (1 + household_dependents)` | Holgura real del hogar: dos clientes con igual DTI no están igual si uno mantiene a 5 personas | − |
| `colchon_ahorro_meses` | `savings_balance / cuota_estimada` | Cuántas cuotas cubre con ahorros si su ingreso se interrumpe (una mala cosecha) | − |
| `ahorro_sobre_monto` | `savings_balance / requested_amount` | Capacidad de ahorro frente al tamaño del crédito pedido | − |
| `deuda_por_obligacion` | `monthly_debt_payment / (1 + active_loans)` | Separa una deuda grande de varias chicas con el mismo pago total | + |
| `intensidad_busqueda` | `bureau_inquiries_6m / (1 + active_loans)` | Muchas consultas sin deudas nuevas sugieren búsqueda activa de crédito | + |
| `antiguedad_relativa` | `employment_tenure_months / ((age − 14) × 12)`, tope 1 | Normaliza la antigüedad por edad; el tope corrige las inconsistencias detectadas | − |
| `campana_siembra` | 1 si el mes de originación está entre setiembre y diciembre | Marca créditos cuyo repago depende de una cosecha aún no realizada | + |
| `flag_sin_buro` | 1 si `bureau_score` es nulo | El faltante identifica al thin-file; el modelo debe poder distinguirlo del score imputado | ? |
| `flag_sin_ingreso` | 1 si `monthly_income` es nulo | Sin ingreso no hay capacidad calculable; en política obliga a verificación | ? |
| `flag_sin_ahorro` | 1 si `savings_balance` es nulo | Distingue al cliente sin producto de ahorro del que tiene saldo cero | ? |

### 3.1 ¿Aportan señal?

AUC univariado por muestra y PSI DEV→OOT (`features_evaluacion.csv`):

| Variable | AUC DEV | AUC VAL | AUC OOT | PSI OOT | Lectura |
|---|---|---|---|---|---|
| `bureau_score` (original, referencia) | 0.693 | 0.673 | 0.707 | 0.011 | Sigue siendo la variable más fuerte |
| `dti` (original) | 0.571 | 0.533 | 0.613 | 0.010 | Fuerte pero inestable entre muestras |
| **`dti_post`** | 0.570 | 0.538 | 0.580 | 0.007 | Iguala al `dti` y es **más estable**; sostiene la regla de capacidad de 6.1 |
| **`dti_post_verificable`** | 0.547 | 0.526 | 0.555 | 0.005 | Señal moderada; valor principal de política |
| **`deuda_por_obligacion`** | 0.544 | 0.555 | 0.573 | 0.002 | La derivada que **mejor se sostiene fuera de muestra**, y la más estable de todas |
| **`ahorro_sobre_monto`** | 0.537 | 0.545 | 0.526 | 0.009 | Colchón financiero |
| **`excedente_per_capita`** | 0.537 | 0.522 | 0.544 | 0.004 | Holgura del hogar |
| **`colchon_ahorro_meses`** | 0.534 | 0.540 | 0.520 | 0.012 | Ordena el riesgo de forma casi monótona |
| `antiguedad_relativa`, `intensidad_busqueda`, `campana_siembra`, flags | 0.503-0.515 | — | — | ≤ 0.020 | Señal marginal; se conservan por racional, su aporte se decide con el IV del scorecard |

El comportamiento por quintiles (`fig10`) confirma la dirección esperada: `dti_post` va de 6.9% de default en el segundo quintil a 15.3% en el último, y `deuda_por_obligacion` de 7.8% a 12.5%. `colchon_ahorro_meses` baja de 12.4% a 9.1%; `ahorro_sobre_monto` apunta en la misma dirección pero con un quiebre en el tercer quintil, que el binning del scorecard tendrá que resolver.

### 3.2 Descartadas

| Variable | Motivo |
|---|---|
| `loan_to_income` | AUC 0.501 en DEV y muy correlacionada con `dti_post` |
| `monto_vs_mediana_region` | AUC 0.501; además introduce un estadístico de muestra que habría que versionar, sin ganancia |
| `mes_originacion` | Reemplazada por `campana_siembra`: la señal estacional relevante es el tramo de siembra, no el mes como número |

Documentarlas importa tanto como documentar las que quedaron: muestra que la selección se hizo midiendo, no por intuición.

---

## 4. Pipeline reproducible

Un único objeto de scikit-learn encadena todo lo que "aprende" del dato:

```
Pipeline
├── FeatureBuilder            construye las 14 variables derivadas (sin estadísticos de muestra)
└── ColumnTransformer
    ├── numéricas (29)        Winsorizer(p1, p99) → SimpleImputer(mediana) → StandardScaler
    └── categóricas (3)       SimpleImputer(moda) → OneHotEncoder(handle_unknown="ignore")
```

**Se ajusta solo con DEV** y se aplica igual a VAL, OOT y a cualquier solicitud nueva. Entra con un esquema fijo de 21 columnas (las candidatas de 6.2 más la fecha de observación) y sale con una matriz de 42 columnas.

| Control | Resultado |
|---|---|
| Mismas columnas en DEV, VAL y OOT | Sí (42 en las tres) |
| Faltantes tras el pipeline | 0 en las tres muestras |
| Topes aprendidos en DEV y aplicados sin recalcular | El máximo de ahorros en OOT (S/ 66,016) queda acotado al tope de DEV (S/ 29,889) |
| Variables prohibidas en la matriz final | Ninguna |
| Puntuar una solicitud individual | Funciona: entra 1 fila, sale 1 × 42 |

Los dos últimos controles son los que evitan los errores más caros: que una variable de leakage entre por descuido, y que el preprocesamiento de producción difiera del de entrenamiento. Al estar todo en un solo objeto, el servicio de scoring no reimplementa nada.

**Por qué estas decisiones y no otras:**
- **Mediana y no media** para imputar: las variables tienen colas largas y la media quedaría arrastrada por los extremos.
- **Imputar + marcar** en lugar de solo imputar: preserva la información del faltante, que en este caso identifica segmentos de negocio reales (thin-file, sin ahorro en la Caja).
- **Winsorizar y no eliminar:** eliminar sesgaría la población hacia los clientes promedio.
- **One-hot y no target encoding:** con 4-5 niveles bien poblados no hace falta, y el target encoding introduciría riesgo de leakage y una dependencia del target que complica la explicación ante el Comité.
- **Estandarizar** es opcional (`build_pipeline(scale=False)`): sirve para la regresión logística y es indiferente para los modelos de árboles.

---

## 5. Data Dictionary técnico

`reports/tables/diccionario_tecnico.csv` documenta **55 variables** (41 originales del dataset + 14 derivadas) con las columnas que pide el enunciado:

| Columna | Contenido |
|---|---|
| `origen`, `rol`, `fuente`, `momento`, `disponible_T0` | Heredado del catálogo de 6.2 |
| `transformacion` | Winsorización, fórmula de la derivada o "no se transforma" |
| `imputacion` | Mediana o moda de DEV, con indicador de faltante cuando corresponde |
| `encoding` | One-hot para categóricas; no aplica en numéricas |
| `riesgo_leakage` | De "bajo" a "crítico", con el motivo (por ejemplo, `bureau_inquiries_6m` debe excluir la consulta de la propia solicitud) |
| `uso_final` | Modelo PD, modelo con revisión de fairness, solo pricing, filtro, target o descartada |

Vale la pena destacar tres entradas por su riesgo de leakage:

- **`annual_interest_rate_offer` (alto):** incorpora la evaluación de riesgo anterior. Solo pricing.
- **`bureau_inquiries_6m` (medio):** válida únicamente si el conteo excluye la consulta que genera esta misma solicitud.
- **`monthly_income` (medio, pero de otro tipo):** el riesgo no es temporal sino de manipulación, porque es declarado y poco verificable en un segmento con 60% de ingreso en efectivo.

---

## 6. Trazabilidad del requisito 6.3

| Requisito del enunciado | Dónde se evidencia |
|---|---|
| Perfilado de calidad: completitud, duplicidad, consistencia, rangos, outliers, cardinalidad, estabilidad y lógica de negocio | §2 · notebook §2-§7 · `src/quality.py` · tablas `calidad_*.csv` |
| Data Dictionary técnico (transformación, imputación, encoding, leakage, uso final) | §5 · notebook §10 · `src/data_dictionary.py` · `diccionario_tecnico.csv` |
| Pipeline reproducible de faltantes y categóricas | §4 · notebook §9 · `src/pipeline.py` |
| Variables derivadas con racional y fórmula | §3 · notebook §8 · `src/features.py` · `features_derivadas_doc.csv` |
| Estabilidad temporal de variables y del target | §2.6 · notebook §7 · `fig09` · `calidad_estabilidad_psi.csv` |
| Pruebas | `tests/test_features.py` |
