# 6.2 Definición del modelo y población

**Caso 15 · Caja Rural 360 · Modelo PD de originación a 12 meses**

> **Evidencia:** `notebooks/00_negocio_y_poblacion.ipynb` (secciones 5, 7, 8 y 9). Las definiciones están implementadas en `src/config.py` y `src/data.py`, y `tests/test_data.py` las verifica, de modo que todo el proyecto usa exactamente la misma población y el mismo split.

---

## 1. Resumen

| Elemento | Definición adoptada |
|---|---|
| Unidad de análisis | Una solicitud de crédito (`application_id`) observada en `observation_date` |
| Observation date (T0) | `observation_date` = fecha de originación; todas las variables se miden en T0 |
| Target | `default_12m_flag` = 1 si el crédito llega a **90 o más días de mora** en **(T0, T0 + 12 meses]** |
| Performance window | Los 12 meses posteriores a T0 |
| Población de desarrollo PD | Créditos aprobados y desembolsados con ventana observable (`outcome_available_flag = 1`): **5,783 créditos, 671 defaults (11.60%)** |
| Población de scoring (producción) | Toda solicitud nueva que pase las validaciones del paso 2 del ciclo (*through-the-door*) |
| Esquema temporal | **DEV 2021-2023 · VAL 2024 · OOT 2025** |
| Variables candidatas PD | 20 disponibles en T0 (5 de ellas con revisión de fairness); 10 prohibidas por leakage o endogeneidad |

---

## 2. Definiciones formales

**Target.** Para cada crédito aprobado *i* con fecha de originación $t_{0,i}$:

$$
Y_i = \mathbb{1}\Big[\max_{t \in (t_{0,i},\ t_{0,i} + 12m]} \mathrm{DPD}_i(t) \ge 90\Big]
$$

Solo está definido cuando el crédito se desembolsó y su ventana de 12 meses es observable (`outcome_available_flag = 1`). Para los rechazados **no existe** Y: su `default_12m_flag = 0` es solo un valor técnico del archivo.

**Observation date.** `observation_date` es el momento de la decisión. Una variable sirve como predictor solo si su valor se conocía en T0: lo declarado en la solicitud, la consulta de buró de ese día, la relación con la Caja a esa fecha y la geocodificación de la dirección. En producción, las consultas de buró y del core deben archivarse con la fecha de la solicitud para poder reproducir el score.

**Por qué una ventana de 12 meses:**
1. Es la definición oficial del enunciado (§5.2) y la convención de PD a un año de Basilea.
2. Cubre toda la vida del 38% de los créditos (plazos de 12 meses o menos) y el tramo de mayor riesgo del resto, porque en microcrédito el default se concentra en las primeras cuotas.
3. Deja cinco cosechas anuales con resultado observado, suficientes para validar en el tiempo.
4. **Limitación:** en plazos de 48 a 60 meses (24% de las solicitudes), la PD a 12 meses subestima el riesgo de toda la vida del crédito.

**Definición de "bueno".** Todo crédito con resultado observado que no llegó a 90 días de mora en la ventana. No existe una categoría "indeterminado" (ver §5).

---

## 3. Población elegible y filtros

Waterfall reproducible (`data.pd_population`, `tables/waterfall_poblacion.csv`):

| Paso | Criterio | Excluidos | Remanentes | % de la base |
|---|---|---|---|---|
| 0 | Solicitudes en `data.csv` (2021-01-01 a 2025-12-27) | — | 7,000 | 100.0% |
| 1 | Duplicados de `application_id` | 0 | 7,000 | 100.0% |
| 2 | `observation_date` nula o fuera de 2021-2025 | 0 | 7,000 | 100.0% |
| 3 | **Rechazados por la política histórica (`approved_flag = 0`), sin resultado observado** | **1,217** | 5,783 | 82.6% |
| 4 | Aprobados sin ventana de performance (`outcome_available_flag = 0`) | 0 | 5,783 | 82.6% |
| 5 | Target nulo o no binario | 0 | 5,783 | 82.6% |
| 6 | Edad menor a 18 años | 0 | 5,783 | 82.6% |
| | **Población PD final** | | **5,783** (671 defaults · 11.60%) | |

Los filtros 1, 2, 4, 5 y 6 no excluyen ningún registro de este archivo, pero se dejan en el código como controles: con otra extracción o en producción sí podrían activarse.

---

## 4. Exclusiones y tratamiento de casos especiales

| Caso | Registros | Tratamiento | Razón |
|---|---|---|---|
| Rechazados | 1,217 (17.4% de las solicitudes) | **Fuera del entrenamiento PD.** Se guardan aparte para analizar el sesgo de selección y la estabilidad de la población | No tienen resultado observado; tratarlos como "buenos" es un error descalificante |
| Columnas que no aplican (garantía, producto revolvente) | 7 columnas 100% vacías | Se eliminan | Producto amortizable sin garantía |
| Thin-file (sin `bureau_score`) | 229 solicitudes / 193 con resultado | **Se mantienen**, con un indicador de faltante | El faltante es informativo; excluirlos contradice el objetivo del caso |
| Ingreso faltante | 170 solicitudes / 145 con resultado | Se mantienen; en la política pasan a revisión manual | 2.4%; su default (9.7%) no es mayor |
| Ahorro faltante | 7.7% | Se mantienen, con indicador de faltante | La tasa de faltantes es parecida entre clientes nuevos y antiguos y entre canales |
| Monto > S/ 20,000 | 294 (4.2%) | Se mantienen en la población; en la política pasan a revisión manual | Son solicitudes del mismo producto; excluirlas sesgaría la PD de los montos altos |
| Antigüedad laboral mayor a la edad laboral posible | 100 | Se mantienen; se marcan como inconsistentes | Es un error de captura en una variable, no en la operación |
| Relación con la Caja mayor a la edad adulta | 205 | Se mantienen; se marcan como inconsistentes | Puede ser una cuenta de ahorro abierta antes de los 18 años |
| Valores extremos de monto o ingreso (p. ej., un monto de S/ 78,915) | Por encima del p99 | Se mantienen | No son errores evidentes |

**Exclusiones de política que no pueden verificarse en este archivo**, porque ya viene depurado: fraude confirmado, refinanciados, colaboradores y clientes con mora vigente. Se asume que se filtraron antes de la extracción; en producción se aplican en el paso 2 del ciclo.

---

## 5. Muestras indeterminadas

- **No es posible construir un segmento indeterminado.** El archivo no trae mora máxima intermedia (30-89 días), curas ni cancelaciones anticipadas (notebook, §7). El target es binario puro.
- **Consecuencia:** los "buenos" incluyen créditos con mora leve que nunca llegaron a 90 días. Eso diluye un poco la separación entre buenos y malos; queda documentado como limitación.
- **Los rechazados no son indeterminados:** son solicitudes *sin resultado*, no con un resultado ambiguo. Por eso se excluyen y no se imputan ni como buenos ni como malos.
- **Ventanas inmaduras:** no hay aprobados sin resultado (`approved_flag` = `outcome_available_flag` en el 100% de los casos). Las cosechas de setiembre a diciembre de 2025 recién cumplen 12 meses entre setiembre y diciembre de 2026, así que se verificó que no muestran el default artificialmente bajo que produce una ventana cortada (2025T4 = 15.9%). Como control adicional puede evaluarse el OOT solo con enero-agosto 2025 (801 créditos, default 12.9%), que ya están maduros.

---

## 6. Sesgos potenciales

| Sesgo | Evidencia | Impacto esperado | Mitigación propuesta |
|---|---|---|---|
| **Selección (reject bias)** | Los rechazados tienen buró medio de 639 vs 671; se aprobó 73.6% en el quintil más bajo de buró vs 89.6% en el más alto | La PD puede **subestimar** el riesgo de perfiles parecidos a los rechazados | La política histórica fue un filtro débil (un logit que la replica logra AUC 0.62), así que la muestra sí cubre la zona de alto riesgo (1,011 aprobados en el quintil más bajo, con default de 24.7%). Además: banda de revisión manual y seguimiento de la población de solicitudes |
| **Cambio de nivel en el tiempo** | Default de 10.2% en DEV vs 13.4% en OOT, con PSI de las variables ≤ 0.02 | Una PD entrenada con años antiguos queda descalibrada hacia abajo (~30%) | Split temporal y recalibración con datos recientes (VAL) |
| **Estacionalidad** | Default por mes de 9.7% a 13.9% | Si una muestra no cubre el año completo, la validación hereda otra mezcla estacional | Muestras de años calendario completos |
| **Política de pricing embebida** | Tasa ofrecida: Spearman de −0.43 con buró; su AUC sube de 0.57 a 0.64 en el tiempo | Leakage de la decisión anterior; el modelo sería inestable si cambia el pricing | `annual_interest_rate_offer` excluida del PD |
| **Medición del ingreso** | 60% del ingreso en efectivo; ingreso declarado o estimado | Ruido y posible inflado, sobre todo en alianza | Descuento sobre el ingreso no verificado; verificación de campo en revisión manual |
| **Muestras pequeñas por segmento** | Thin-file 193; distancia > 50 km 94; Oriente 549 | Estimaciones inestables por segmento | No extrapolar; reportar intervalos de confianza |
| **Proxies de grupos protegidos** | Región, distancia, efectivo, dependientes y edad | Discriminación indirecta (territorial o por informalidad) | Variables marcadas "con revisión de fairness" en el catálogo |
| **Definición del target** | No hay mora de 30-89 días; ventana de 12 meses | "Buenos" contaminados; en plazos largos la PD a 12 meses es menor que la de toda la vida del crédito | Limitación documentada |
| **Datos sintéticos** | 52.9% "dependiente" en un producto para independientes | Los hallazgos podrían no generalizar | Supuesto documentado; no se interpretan los niveles absolutos |

---

## 7. Esquema temporal Development / Validation / Out-of-Time

| Muestra | Periodo (`observation_date`) | Créditos con resultado | Defaults | Default rate | Solicitudes TTD | Error estándar del AUC* | Uso |
|---|---|---|---|---|---|---|---|
| **DEV** | 2021-01-01 a 2023-12-31 | 3,443 (59.5%) | 351 (52.3%) | 10.19% | 4,154 | ±0.016 | Ajuste del modelo (entrenamiento y tuning) |
| **VAL** | 2024-01-01 a 2024-12-31 | 1,151 (19.9%) | 161 (24.0%) | 13.99% | 1,389 | ±0.024 | Comparación de modelos y calibración |
| **OOT** | 2025-01-01 a 2025-12-31 | 1,189 (20.6%) | 159 (23.7%) | 13.37% | 1,457 | ±0.024 | Evaluación final, sin usarse en ninguna decisión previa |

\* Hanley-McNeil para un AUC de 0.70: con ≈160 defaults, el AUC del OOT se estima con un intervalo de ±0.05 (95%).

![Split temporal](figures/fig06_split_temporal.png)

**Justificación:**
1. **El nivel de riesgo cambia en el tiempo.** El default pasa de 10.2% (DEV) a 14.0% (VAL) y 13.4% (OOT), aunque la población no cambia (PSI ≤ 0.02 en todas las candidatas). Un split aleatorio lo esconde: entrenamiento y prueba quedan con 11.7% y 11.4% y el modelo parecería perfectamente calibrado. El split temporal muestra la brecha real de +31% que el modelo enfrentará en producción.
2. **Ciclo agrícola completo.** Cada muestra está formada por años calendario completos, así que todas tienen la misma mezcla estacional (el default por mes de originación va de 9.7% a 13.9%).
3. **Eventos suficientes.** Cada muestra tiene al menos 159 defaults, suficientes para estimar la discriminación y la calibración con un error acotado.
4. **Proporciones estándar** (≈60/20/20) sin sacrificar tamaño de desarrollo.
5. **Simula la operación real.** Se entrena con el pasado, se ajusta y calibra con el año siguiente y se prueba con la cosecha más reciente, que es la más parecida a la población que se va a puntuar.
6. **La relación de riesgo es estable.** El AUC univariado del buró se mueve entre 0.67 y 0.71 por año. Así, el OOT mide sobre todo si el modelo mantiene el ranking y la calibración ante el cambio de nivel, que es la prueba relevante para este caso.

**Reglas de uso de cada muestra (para evitar leakage):**
- **DEV:** aquí se ajusta todo lo que "aprende" del dato: imputaciones, agrupaciones, parámetros e hiperparámetros. El tuning se hace con validación temporal dentro de DEV (por ejemplo, entrenar con 2021 y validar con 2022), nunca con un split aleatorio.
- **VAL:** se comparan modelos, se elige el definitivo y se ajusta la calibración. No se vuelven a estimar agrupaciones ni variables.
- **OOT:** se usa una sola vez, con el modelo y la política ya congelados. Si el resultado obliga a cambiar algo, el cambio se documenta y el OOT deja de ser "ciego" para esa versión.

**Alternativas descartadas:**

| Alternativa | Motivo |
|---|---|
| Split aleatorio estratificado | Mezcla periodos y oculta el cambio de nivel; el enunciado no lo acepta como única validación |
| OOT solo con el segundo semestre de 2025 | ~80 defaults: el intervalo del AUC queda demasiado ancho |
| DEV 2021-2024 y OOT 2025, sin VAL | La calibración y el modelo se tendrían que elegir con DEV (sobreajuste) o con OOT (leakage) |
| Cortes semestrales (p. ej., DEV hasta junio de 2023) | Rompe la simetría estacional entre muestras |

---

## 8. Variables disponibles en el momento de la decisión

El catálogo completo está en `reports/tables/catalogo_variables.csv`: 41 variables con rol, fuente, momento, disponibilidad en T0, uso en PD, uso oficial según el diccionario y % de faltantes. Resumen:

| Grupo | Variables | ¿Disponible en T0? | Uso en PD |
|---|---|---|---|
| **Solicitud (declarado)** | `employment_type`, `monthly_income`, `employment_tenure_months`, `requested_amount`, `term_months` | Sí | Candidatas |
| **Solicitud, sensibles o proxies** | `age`, `region`, `distance_to_branch_km`, `household_dependents`, `cash_income_share` | Sí | **Candidatas con revisión de fairness** |
| **Proceso** | `channel` | Sí | Candidata; uso preferente en reglas operativas |
| **Buró en T0** | `bureau_score`, `prior_delinquencies_24m`, `bureau_inquiries_6m`, `active_loans`, `monthly_debt_payment` | Sí (consulta del día) | Candidatas |
| **Derivada** | `dti` (deuda / ingreso, sin la nueva cuota) | Sí | Candidata |
| **Interno (CRM, core)** | `new_customer_flag`, `relationship_months`, `savings_balance` | Sí | Candidatas |
| **Política histórica** | `annual_interest_rate_offer` | Sí, pero es *resultado* de la evaluación de riesgo anterior | **Excluida** (endógena); solo para pricing |
| **Tiempo, ID, constantes** | `observation_date`, `application_id`, `entity`, `product` | Sí | No (la fecha solo sirve para el split) |
| **No aplican** | `collateral_value`, `ltv`, `credit_limit`, `balance_at_observation`, `utilization_at_observation`, `undrawn_amount_at_observation`, `ccf_observed` | — (100% vacías) | No |
| **Posteriores a la decisión, filtro o target** | `approved_flag`, `outcome_available_flag`, `default_12m_flag` | **No** | Prohibidas |
| **Posteriores al default** | `ead_at_default`, `balance_at_default`, `recovery_amount_total`, `recovery_cost_total`, `months_to_recovery`, `lgd_observed` | **No** | Prohibidas |

**Variables prohibidas como predictor PD** (`data.forbidden_pd_features()`): `annual_interest_rate_offer`, `approved_flag`, `outcome_available_flag`, `default_12m_flag`, `ead_at_default`, `balance_at_default`, `recovery_amount_total`, `recovery_cost_total`, `months_to_recovery`, `lgd_observed`. Un test verifica que ninguna esté entre las candidatas.

**Precisiones sobre la disponibilidad:**
- `dti` usa la deuda del buró en T0 y **no** incluye la cuota del crédito solicitado. El DTI post-crédito que usa la regla de capacidad (6.1) se calcula con una **TEA de referencia** de 30%, no con la tasa ofrecida, para no volver a meter una variable endógena.
- `bureau_inquiries_6m` no debe contar la consulta que genera la propia solicitud; en producción se toma el conteo previo a T0.
- `term_months` y `requested_amount` son los valores **solicitados**. Si se hace una contraoferta, el score se recalcula con los valores ofrecidos.
- `monthly_income` y `cash_income_share` están disponibles, pero son declarados o estimados por el asesor. Son variables "blandas" y manipulables, que se controlan con la verificación en revisión manual y siguiendo su distribución por canal.
- El mes de originación (estacionalidad) está disponible en T0. El año **no** se usa, porque extrapolaría la tendencia.

---

## 9. Trazabilidad del requisito 6.2

| Requisito del enunciado | Dónde se evidencia |
|---|---|
| Target, observation date, performance window, población elegible | §1 a §3 · `src/config.py` · `src/data.py::pd_population` |
| Filtros, exclusiones, indeterminados, sesgos | §3 a §6 · notebook, §5 y §7 · `tables/waterfall_poblacion.csv` |
| Esquema DEV / VAL / OOT justificado (no aleatorio) | §7 · notebook, §8 · `fig06` · `tables/split_temporal.csv`, `psi_variables_split.csv` |
| Variables disponibles en T0 | §8 · `tables/catalogo_variables.csv` · `data.forbidden_pd_features()` |
| Pruebas | `tests/test_data.py` (columnas, población, split, variables prohibidas, rangos) |
