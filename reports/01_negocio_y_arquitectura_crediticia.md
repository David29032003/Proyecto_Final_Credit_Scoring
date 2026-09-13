# 6.1 Entendimiento del negocio y arquitectura crediticia

**Caso 15 · Caja Rural 360 · Microcrédito rural para independientes**

> **Evidencia:** las cifras provienen de `notebooks/00_negocio_y_poblacion.ipynb` (tablas en `reports/tables/`, figuras en `reports/figures/`). Los datos son 100% sintéticos y los montos se interpretan en soles (S/) como supuesto. La matriz de etapas parte del trabajo del equipo en `Ciclo_End_To_End.xlsx`.

---

## 1. Resumen

- **Problema de negocio.** Caja Rural 360 quiere crecer fuera de sus agencias hacia clientes rurales con ingresos parcialmente en efectivo, **sin excluir automáticamente a quien no tiene trazabilidad bancaria** y sin deteriorar la cartera. Hoy el 68.7% de las solicitudes ya llega por web o app.
- **El riesgo se deteriora por frecuencia, no por severidad.** El default 12m subió de **8.6% (2021) a 14.0% (2024) y 13.4% (2025)**, y la pérdida realizada pasó de 1.9% a 4.0% del monto desembolsado. En cambio, la LGD (≈62%), la exposición al default (≈42% del monto) y la composición de la población se mantienen estables.
- **La política histórica no controlaba la capacidad de pago.** Aprobó 82.6% de las solicitudes con un filtro débil basado sobre todo en buró. Aprobó igual a clientes con DTI post-crédito > 60% (default 16.8%), que representan 21.6% del monto aprobado.
- **Qué resuelve el modelo.** Estima la **PD a 12 meses de cada solicitud nueva** y se consume **en línea en el paso 5 del ciclo**: después de las validaciones y del enriquecimiento de datos, antes de las reglas de capacidad, la decisión APPROVE / REVIEW / REJECT, la tasa y el monto.
- **Risk Appetite.** Se proponen 14 métricas con semáforo en cinco dimensiones. La cosecha 2025 queda en **rojo** en default, en tickets > S/ 20,000 y en capacidad de pago. La meta es volver a un default ≤ 11% y un EL ≤ 3% manteniendo la aprobación en al menos 70%.

---

## 2. Ficha del negocio

| Elemento | Descripción | Evidencia en los datos |
|---|---|---|
| **Entidad** | Caja Rural 360: entidad microfinanciera regulada (ficticia, tipo Caja Rural de Ahorro y Crédito). Opera con agencias, asesores de negocio de campo, canales digitales y alianzas locales. | `entity` constante |
| **Producto** | Microcrédito rural amortizable en cuotas fijas, **no revolvente y sin garantía real**. | Los 7 campos de garantía y de producto revolvente están 100% vacíos (`collateral_value`, `ltv`, `credit_limit`, `ccf_observed`, etc.) |
| **Cliente objetivo** | Hogares rurales con actividad económica propia o mixta (agricultura, ganadería, comercio, oficios, transporte), con ingresos estacionales y en parte en efectivo. Muchos no tienen historial en la Caja y algunos tampoco en buró. | Edad mediana 38 años (18-72); 2.2 dependientes en promedio; **60% del ingreso en efectivo** (mediana 61%); 44.5% clientes nuevos; 3.3% sin score de buró |
| **Necesidad financiera** | Capital de trabajo para el ciclo productivo (insumos, semillas, animales, mercadería) y activo productivo menor (moto, herramientas, mejoras). La necesidad es estacional y exige respuesta rápida. | El default por mes de originación va de 9.7% a 13.9%; el pico es octubre, inicio de la campaña agrícola |
| **Canal** | Web (34.9%), app (33.8%), agencia (21.8%) y alianza (9.5%: cooperativas, asociaciones de productores, comercios). La app puede usarse asistida por el asesor de campo. | 68.7% digital; alianza = 667 solicitudes |
| **Monto** | Ticket bajo. Rango propuesto: de S/ 500 a S/ 20,000 con decisión automática; entre S/ 20,000 y S/ 30,000 solo con revisión manual; por encima de S/ 30,000 corresponde a otro producto. | Mediana S/ 6,309; p5-p95 S/ 2,065-18,937; 4.2% de las solicitudes pasa de S/ 20,000 (14.5% del monto aprobado); máximo S/ 78,915 |
| **Plazo** | De 6 a 60 meses. Conviene que el calendario de pagos siga el ciclo de ingresos (cuotas estacionales o periodo de gracia en la siembra). | 8 plazos, cada uno con ≈12% de las solicitudes; 38% a 12 meses o menos; 24.1% a más de 36 meses |
| **Tasa** | Tasa efectiva anual (TEA) fijada según el riesgo por la política histórica. | Mediana 29.3% (p5 18.2%, p95 41.9%) |
| **Garantías** | Sin garantía real. Mitigantes posibles, no registrados en los datos: aval o garante solidario, ahorro vinculado o un aliado que retiene parte de la venta de la cosecha. | LGD observada 62.3%; se recupera 42% de la EAD en ≈12 meses; costo de recuperación 4.4% de la EAD |
| **Moneda** | Soles (supuesto del equipo, contexto peruano). | — |

![Perfil del producto y del cliente](figures/fig02_perfil_producto_cliente.png)

---

## 3. Principales fuentes de riesgo

| # | Riesgo | Descripción | Evidencia | Dónde se mitiga en el ciclo |
|---|---|---|---|---|
| R1 | **Capacidad de pago** | Ingreso volátil y estacional, en gran parte en efectivo y difícil de verificar; sobreendeudamiento. | Default de 17.3% en el quintil más alto de DTI vs 9.2% en el más bajo; 16.8% con DTI post-crédito 60-80% | Paso 4 (DTI post-crédito), paso 6 (regla de capacidad), paso 8 (monto máximo) |
| R2 | **Deterioro del entorno** | Shocks macroeconómicos o climáticos que elevan el default de toda la cartera. | Default de 8.6% a 14.0% con la población estable; sube en todos los quintiles de buró | Pasos 10 y 12 (seguimiento por cosecha y recalibración) |
| R3 | **Información incompleta (thin-file)** | Clientes sin buró o sin relación previa, e ingresos declarados. | 229 sin score (3.3%); clientes nuevos con default de 12.7% vs 10.7%; 2.4% sin ingreso | Pasos 3 y 7 (verificación de campo y revisión manual) |
| R4 | **Fraude e intermediario** | Suplantación en canales remotos; aliados que inflan datos para colocar. | Alianza: default de 11.9% (similar al promedio), pero la **mayor pérdida realizada por canal (3.5% del monto)** | Paso 2 (KYC biométrico, antifraude); límite de concentración por canal |
| R5 | **Concentración geográfica y climática** | Default correlacionado por un evento común en una zona (FEN, sequía, heladas). | Lima concentra 41.6% del monto; el default de Centro subió de 6.4% a 15.5% entre 2021 y 2024 | Límite por macrorregión; alertas por zona (paso 10) |
| R6 | **Recuperación sin garantía** | Solo queda la cobranza, con costo y tiempo altos. | LGD de 62.3% (entre 0.61 y 0.63 cada año); 12 meses de recuperación | Paso 11 (cobranza preventiva); paso 8 (una tasa que cubra la pérdida esperada) |
| R7 | **Sesgo de selección** | La cartera histórica solo tiene resultados de los aprobados. | 1,217 rechazados (17.4%) con buró medio de 639 vs 671 | Banda de revisión manual; seguimiento de la población de solicitudes |
| R8 | **Fair lending territorial** | Excluir por ruralidad, informalidad o región sin evidencia de mayor riesgo. | Oriente: la menor aprobación (78.8%) con el **menor** default (9.5%) | Métricas AIR en el apetito |
| R9 | **Pricing circular** | La tasa histórica ya incorpora la evaluación de riesgo anterior. | Spearman de −0.43 con buró; el default sube de 7.3% a 18.8% entre quintiles de tasa | Tasa excluida como variable del modelo |
| R10 | **Plazo vs. ventana** | Los plazos de 48-60 meses superan la ventana de 12 meses y el ciclo productivo. | 24.1% del monto aprobado está en plazos > 36 meses | Límite de concentración por plazo |

---

## 4. Ciclo de crédito end-to-end

![Ciclo de crédito end-to-end](figures/fig01_ciclo_credito.png)

| Paso | Etapa (matriz del equipo) | ¿Qué se decide? | Datos / sistemas | Modelo o regla | Riesgo clave | Salida |
|---|---|---|---|---|---|---|
| 1. Solicitud | Originación | ¿Se registra la solicitud? ¿Canal remoto o asistido? | Formulario web o app, asesor de campo con tablet, aliado: monto, plazo, destino, ingreso declarado, % en efectivo, dependientes | Validaciones de formato y rango al capturar | Datos inflados (alianza), errores de captura | Solicitud con ID y `observation_date` (T0) |
| 2. Validaciones | Originación | ¿Continúa la evaluación? | RENIEC (biometría facial y huella), listas AML/PEP, dispositivo y geolocalización, duplicados, mora vigente en la Caja o en el sistema | KYC, reglas de fraude y AML, **elegibilidad** (edad de 18 a 75 años al vencimiento, documento válido, sin mora vigente > 30 días, sin fraude confirmado) | Suplantación en zonas sin agencia; selección adversa | Continúa, o se rechaza por política (no llega al modelo) |
| 3. Fuentes de datos | Evaluación y scoring | ¿Qué información existe en T0? | Buró (score, moras 24m, consultas 6m, deudas y cuota), core y CRM (relación, ahorros), geocodificación (distancia a agencia), verificación de campo si hace falta | Consultas archivadas con la fecha de la solicitud | Usar datos que no existían en T0 (leakage); buró incompleto | Registro enriquecido y archivado |
| 4. Cálculo de variables | Evaluación y scoring | — | Variables en T0 | Mismas transformaciones que en el desarrollo: DTI post-crédito, indicadores de faltantes, imputación | Diferencias entre el cálculo del desarrollo y el de producción | Variables listas para el modelo |
| **5. Scoring PD** | Evaluación y scoring | **¿Cuál es la PD a 12 meses?** | Variables del paso 4 | **Modelo PD de originación** | Descalibración por cambio de nivel; sesgo de selección | **PD, score, banda de riesgo, motivos (reason codes)** |
| 6. Reglas de política | Decisión y pricing | ¿Se cumplen la capacidad de pago y los límites? | PD o banda, DTI post-crédito, monto, thin-file, canal, concentración vigente | Reglas duras y blandas (§5 y §8) | Sobreendeudamiento; concentración | Indicadores de política |
| 7. Decisión | Decisión y pricing | APPROVE / REVIEW / REJECT | Banda de riesgo, capacidad de pago e indicadores | Motor de decisión | Exclusión injusta; overrides sin control | Decisión y motivos |
| 8. Pricing y monto | Decisión y pricing | Tasa, monto máximo y plazo o calendario | PD, exposición y severidad esperadas, costo de servir | Tasa ≥ costo de fondeo + costo operativo + pérdida esperada + costo de capital; monto dentro de la capacidad de pago | Precio mal fijado; cuota desalineada con la cosecha | Oferta (monto, tasa, plazo) |
| 9. Desembolso | Desembolso | ¿Se libera el monto total o una parte? | Firma digital, cuenta, billetera o agente, nueva verificación biométrica | Checklist antifraude | Cambio de cuenta, desvío del uso, intermediario que retiene fondos | Crédito activo |
| 10. Seguimiento | Monitoreo | ¿Hay alerta temprana? ¿Conviene reprogramar? | Pagos propios, buró periódico, eventos climáticos por zona | Indicadores de mora temprana por cosecha y seguimiento de la estabilidad y calibración del score | Deterioro silencioso; contagio entre clientes de una zona | Alertas y acciones preventivas |
| 11. Cobranza | Cobranza | ¿Cuándo y por qué canal contactar? ¿Reprogramar? | Días de mora, contactabilidad, ciclo productivo, distancia | Priorización por monto y probabilidad de recuperación | Costo de cobranza mayor que lo recuperado | Recuperación, reprogramación o castigo |
| 12. Retroalimentación | Monitoreo | ¿Recalibrar o reentrenar el modelo? | Resultado a 12 meses de cada cosecha, casos de REVIEW y overrides | Recalibración o reentrenamiento del modelo | Aprender solo de los aprobados | Nueva versión del modelo o de la política |

### 4.1 Decisión que resolverá el modelo y punto de consumo

| Pregunta | Respuesta |
|---|---|
| **Pregunta de negocio** | *¿Cuál es la probabilidad de que esta solicitud nueva, si se aprueba y desembolsa, llegue a 90 o más días de mora en los 12 meses siguientes?* |
| **Tipo de modelo** | Scoring de originación (application scoring): PD a 12 meses con la información disponible en T0. |
| **Momento de consumo** | **Paso 5**, en línea (servicio consultado al momento, con objetivo de menos de 1 segundo), después de las validaciones y del enriquecimiento de datos y antes de las reglas de capacidad y de la decisión. |
| **Salida** | PD calibrada, score, banda de riesgo y motivos principales del score (reason codes). |
| **Decisiones que alimenta** | (i) APPROVE / REVIEW / REJECT, junto con la capacidad de pago; (ii) tasa por banda y monto máximo; (iii) pérdida esperada (PD × EAD × LGD) para el apetito y el pricing. |
| **Quién decide** | El motor decide solo en los extremos. La banda intermedia y los casos de §8 pasan a un analista o al comité de agencia. Los overrides se documentan y se monitorean (hasta 5%). |
| **Qué NO decide** | Fraude o identidad (paso 2), cobranza, gestión de la cartera vigente y provisiones. Tampoco rechaza a nadie por no tener buró. |

Los puntos de corte entre APPROVE, REVIEW y REJECT se fijan cuando el modelo ya está desarrollado y calibrado.

---

## 5. Risk Appetite

El apetito se expresa en métricas cuantitativas con tres zonas: **Verde** (dentro del apetito), **Ámbar** (tolerancia: alerta y plan de acción) y **Rojo** (límite: se escala al Comité de Riesgos y la acción es obligatoria). Las columnas "Histórico" y "2025" miden la cartera aprobada por la política anterior con los mismos umbrales (`reports/tables/risk_appetite.csv`, `src/risk_appetite.py`).

| Dimensión | Métrica | Verde | Rojo | Histórico 2021-25 | Cosecha 2025 | Racional |
|---|---|---|---|---|---|---|
| Crecimiento | Aprobación sobre solicitudes (TTD) | ≥ 70% | < 65% | 82.6% · Verde | 81.6% · Verde | Mandato de crecimiento; no caer más de 13 pp |
| Riesgo | Default 12m de cosechas aprobadas | ≤ 11% | > 13% | 11.6% · Ámbar | **13.4% · Rojo** | Volver a la media histórica |
| Riesgo | Expected Loss / monto desembolsado | ≤ 3.0% | > 3.5% | 2.9% · Verde | 3.4% · Ámbar | La pérdida realizada de 2024 fue 4.0% |
| Riesgo | LGD media de defaults | ≤ 65% | > 70% | 62.3% · Verde | 63.4% · Verde | Sin garantía; estable |
| Concentración | Mayor macrorregión (% del monto) | ≤ 45% | > 50% | 41.6% · Verde | 40.7% · Verde | Riesgo climático correlacionado |
| Concentración | Canal alianza (% del monto) | ≤ 15% | > 20% | 9.6% · Verde | 10.3% · Verde | Riesgo de intermediario |
| Concentración | Clientes nuevos (% del monto) | ≤ 50% | > 55% | 44.8% · Verde | 44.9% · Verde | Default de 12.7% vs 10.7% |
| Concentración | Thin-file (% del monto) | ≤ 5% | > 8% | 3.2% · Verde | 2.5% · Verde | Espacio para inclusión, con evidencia aún escasa |
| Concentración | Plazo > 36 meses (% del monto) | ≤ 25% | > 30% | 24.1% · Verde | 22.4% · Verde | Supera la ventana y el ciclo productivo |
| Concentración | Monto > S/ 20,000 (% del monto) | ≤ 12% | > 15% | 14.5% · Ámbar | **15.7% · Rojo** | Fuera del rango de microcrédito |
| Concentración | Distancia > 50 km (% del monto) | ≤ 3% | > 5% | 1.7% · Verde | 1.6% · Verde | Costo de servir |
| Capacidad | Monto con DTI post-crédito > 60% | ≤ 5% | > 10% | **21.6% · Rojo** | **22.2% · Rojo** | Default de 16.8% con DTI post-crédito de 60-80% |
| Fair lending | AIR de aprobación entre macrorregiones | ≥ 0.90 | < 0.80 | 0.94 · Verde | 0.89 · Ámbar | Regla de 4/5 |
| Fair lending | AIR entre quintiles de ingreso en efectivo | ≥ 0.90 | < 0.80 | 0.99 · Verde | 0.97 · Verde | No excluir por informalidad |

La cosecha 2025 muestra dónde debe actuar la nueva política: default y capacidad de pago en rojo, tickets grandes en rojo y pérdida esperada y equidad territorial en ámbar. El resto de métricas está dentro del apetito.

**Límites por operación (reglas duras):**

| Límite | Valor propuesto | Racional |
|---|---|---|
| Monto automático máximo | S/ 20,000 | Rango de microcrédito |
| Monto máximo absoluto | S/ 30,000 (por encima del p99); más → otro producto | 71 solicitudes superan S/ 30,000 |
| DTI post-crédito | Hasta 45%: aprobación automática; 45-60%: revisión; más de 60%: solo si se reduce el monto o se amplía el plazo | El default sube de 9.4% a 13.4% y a 16.8% por tramo |
| Primer crédito thin-file | Hasta S/ 5,000 y 12 meses; se amplía tras 6 cuotas pagadas a tiempo | Inclusión con exposición acotada (mediana solicitada thin-file: S/ 6,404) |
| Edad | 18 años al solicitar y hasta 75 al vencimiento | Elegibilidad legal y de política |

**Gobierno del apetito.** El Directorio lo aprueba a propuesta del Comité de Riesgos y se revisa cada semestre, o antes si ocurre un evento climático o macroeconómico relevante. Una métrica en Ámbar exige analizar la causa y presentar un plan de acción en 30 días. Una métrica en Rojo exige escalar de inmediato y cambiar la política: subir el punto de corte, bajar montos o restringir el segmento.

---

## 6. Supuestos

| # | Supuesto | Por qué es razonable / cómo se controla |
|---|---|---|
| S1 | `observation_date` es la fecha de solicitud o desembolso (T0), y todas las variables previas a la originación se miden en T0. | Así lo indica el diccionario. En producción, el buró y el core se archivan con la fecha de la solicitud |
| S2 | La ventana de 12 meses está completa para todo `outcome_available_flag = 1` (extracción posterior a diciembre de 2026). | Las últimas cosechas no muestran caída del default (2025T4 = 15.9%) |
| S3 | `requested_amount` ≈ monto desembolsado (no hay un monto aprobado distinto). | Base de la exposición y de la concentración |
| S4 | `term_months` es el plazo solicitado o propuesto antes de la decisión. | Existe también para los rechazados |
| S5 | Amortización francesa mensual. Para la capacidad de pago se usa una TEA de referencia de 30% (≈ la mediana), no la tasa ofrecida. | Evita incluir la tasa, que es endógena, en los cálculos |
| S6 | Los rechazados lo fueron por la política histórica, no porque desistieron. | `approved_flag = 0` ⇔ `outcome_available_flag = 0` |
| S7 | `employment_type` es la actividad principal declarada del hogar rural. | 52.9% figura como "dependiente" en un producto para independientes; no se excluye a nadie por esta variable |
| S8 | Moneda: soles. Los niveles absolutos (ingresos, montos) son sintéticos y no se comparan con estadísticas nacionales. | — |
| S9 | No hay variables protegidas explícitas (sexo, etnia). `age`, `region`, `distance_to_branch_km`, `household_dependents` y `cash_income_share` se tratan como posibles proxies. | Marcadas en el catálogo de variables (6.2) |

---

## 7. Exclusiones

**Del proceso automático (validaciones del paso 2, antes del modelo):** menores de 18 años o edad mayor a 75 al vencimiento; identidad no verificada o fraude confirmado; coincidencia en listas AML/PEP sin debida diligencia reforzada; mora vigente mayor a 30 días en la Caja o calificación deficiente o peor en el sistema; créditos refinanciados o reestructurados (otro producto); colaboradores de la Caja (conflicto de interés); montos mayores a S/ 30,000.

**Del desarrollo del modelo PD (detalle en 6.2):** los 1,217 rechazados, porque no tienen resultado observado, y las 7 columnas que no aplican al producto. La tasa ofrecida y todos los campos posteriores a la decisión o al default quedan fuera como variables.

**Lo que NO es una exclusión:** no tener score de buró, cobrar la mayor parte del ingreso en efectivo, vivir lejos de una agencia o pertenecer a una región determinada. Ese es justamente el mercado objetivo del caso y se atiende con rutas de verificación, no con rechazo automático.

---

## 8. Situaciones que requieren revisión manual

| Disparador | Solicitudes (TTD) | Racional / evidencia | Qué valida el analista o asesor |
|---|---|---|---|
| **Banda de PD intermedia** | Se dimensiona al fijar los puntos de corte | La PD no es concluyente | Capacidad real, referencias, destino del crédito |
| **Sin score de buró (thin-file)** | 229 (3.3%) | Default de 6.7% (13 de 193), pero muy variable por año (de 0% a 12.9%) | Identidad reforzada, visita de campo, ventas o movimientos de billetera; monto inicial acotado |
| **Ingreso faltante** | 170 (2.4%) | Sin ingreso no se puede calcular la capacidad de pago | Estimación del ingreso en campo |
| **Monto > S/ 20,000** | 294 (4.2%) | 14.5% del monto aprobado; fuera del rango de microcrédito | Flujo del negocio y endeudamiento total |
| **Alianza con ingreso atípico** (> p95) | 36 (0.5%) | Riesgo de datos inflados; es el canal con mayor pérdida | Verificación independiente del aliado |
| **Ingreso en efectivo > 80% y monto > S/ 10,000** | 308 (4.4%) | Default de 13.7% con más de 80% en efectivo vs 11.2% | Evidencia de ventas o cosecha; descuento sobre el ingreso no verificado |
| **DTI post-crédito entre 45% y 60%** | 22.8% | Default de 13.4% | Primero se ofrece reducir el monto o ampliar el plazo; si no alcanza, pasa a revisión |
| **Distancia > 50 km** | 106 (1.5%) | Default (8.5%) y LGD no son peores, pero cuesta más atenderlos | Viabilidad de la cobranza remota o por agente local |
| **Evento climático activo en la zona** | Según la alerta | Default correlacionado por zona | Condiciones de la zona: monto, plazo, periodo de gracia |
| **Override pedido por negocio** | Hasta 5% | Disciplina de política | Justificación documentada y aprobación de un nivel superior |

Si se suman todos los disparadores basados en datos, llegan a **22.2%** de las solicitudes, más que el 20% que pueden atender los analistas. Por eso los disparadores "blandos" (efectivo, distancia, historial de buró estresado) solo deberían activar la revisión cuando la PD no sea concluyente. Las inconsistencias de datos (252 casos con antigüedad laboral o relación con la Caja mayor a lo que la edad permite) se corrigen al capturar la solicitud (paso 1), no en revisión manual.

---

## 9. Trazabilidad del requisito 6.1

| Requisito del enunciado | Dónde se evidencia |
|---|---|
| Entidad, producto, cliente, necesidad, canal, monto, plazo, garantías | §2 · notebook, secciones 1 y 2 · `fig02` |
| Principales fuentes de riesgo | §3 · notebook, secciones 4 a 6 |
| Ciclo de crédito end-to-end | §4 · `fig01_ciclo_credito.png` · `src/diagrams.py` |
| Decisión que resuelve el modelo y punto de consumo | §4.1 |
| Risk Appetite cuantitativo | §5 · `src/risk_appetite.py` · `tables/risk_appetite.csv` |
| Supuestos, exclusiones y revisión manual | §6, §7, §8 |
