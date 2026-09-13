CASO 15 - Caja Rural 360
Producto: Microcredito rural para independientes

ARCHIVOS
- data.csv: base sintetica a nivel solicitud/cuenta.
- diccionario_datos.csv: leyenda oficial de variables y restricciones de uso.

UNIDAD DE ANALISIS
Una fila = una solicitud de credito observada en observation_date.

TARGET PD OFICIAL
default_12m_flag = 1 si un credito aprobado/desembolsado alcanza 90 o mas dias de mora dentro de los 12 meses posteriores a observation_date; 0 si no.
Para modelar PD se DEBE filtrar outcome_available_flag = 1. Los rechazados tienen default_12m_flag=0 solo por estructura del archivo y NO son buenos observados.

EAD/LGD
ead_at_default y lgd_observed solo existen para cuentas que llegaron a default. Los campos de recuperacion son posteriores al default y NUNCA deben utilizarse como predictores de PD.

VALIDACION TEMPORAL
La base cubre 2021-2025. El equipo debe proponer y justificar desarrollo, validacion y out-of-time usando observation_date; no se impone un corte unico.

CALIDAD DE DATOS
La base contiene faltantes realistas en algunas variables pre-originacion. Deben ser diagnosticados y tratados dentro de un pipeline reproducible.

TASA DE DEFAULT OBSERVADA APROX. EN CREDITOS CON OUTCOME: 11.60%

IMPORTANTE
Los datos son 100% sinteticos y creados exclusivamente con fines academicos. No corresponden a ninguna entidad ni persona real.
