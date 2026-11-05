# Semáforo predictivo de exposición climática del litoral atlántico andaluz

Actividad Final de Grado (MII715), Magíster en Ingeniería Industrial UNAB · Grupo 2 (Juan Pablo Mestre, Rubén Ugarte, Felipe Avendaño).

El semáforo ordena los 23 tramos del litoral atlántico de Andalucía (de la desembocadura del Guadiana a Tarifa) según su exposición climática esperada en el trimestre siguiente, para focalizar la inspección y el mantenimiento preventivo. Usa solo datos abiertos (reanálisis IBI de Copernicus Marine, validado con mareógrafos REDMAR y boyas de Puertos del Estado), un índice de exposición por tramo y trimestre (IEECC) y modelos de clasificación y ordenamiento evaluados con partición temporal frente a una línea base de persistencia. Mide exposición relativa: no evalúa el estado de las estructuras ni predice daños.

Marco metodológico: Design Science Research (versión liviana) con CRISP-ML(Q) como proceso técnico y enfoque mixto con predominio cuantitativo.

## Estado actual (Capítulo II, 5 de noviembre de 2026)

- **Datos reales** 2000 a 2024 para modelar y 2025 como prueba prospectiva, en **23 tramos de unos 10 km**; cada tramo tiene su propia celda del reanálisis. La segmentación anterior de 40 puntos quedó en la rama `tramos-40` ([`docs/segmentacion_10km.md`](docs/segmentacion_10km.md)).
- **La marea astronómica se trata en tres capas.** Se resta del nivel del mar y de las corrientes (UTide, ajustado con 2000-2018), se cuentan los días de temporal en pleamar viva como quinto indicador y la pleamar viva prevista para el trimestre siguiente entra al modelo.
- **OE1:** 100 % de cobertura. El residuo meteorológico del nivel del mar coincide con REDMAR (correlación 0,93 en Huelva, 0,88 en Bonanza y 0,81 en Tarifa) y el oleaje con tres boyas de Puertos del Estado (correlación 0,94 a 0,96; 97 % a 100 % de los extremos detectados).
- **OE2:** 5 de los 12 escenarios de sensibilidad cumplen la meta de menos de 20 % de cambio de clase; los saltos entre alta y baja no pasan de 5,3 %.
- **OE3:** en la prueba 2022-2024, LambdaMART supera a la persistencia en exactitud balanceada (0,627 contra 0,602) y en sensibilidad de la clase alta (0,677 contra 0,646), y queda apenas bajo en NDCG de los 6 primeros (0,953 contra 0,959). En validación no la supera en ambas métricas, así que la persistencia queda como referencia operativa (plan B). En la prueba prospectiva 2025, LambdaMART y XGBoost sí la superan (LambdaMART: NDCG 0,958 contra 0,945; sensibilidad 0,750 contra 0,500).
- **Cambios de clase y SHAP:** LambdaMART acierta 43 % de los cambios de clase en 2022-2024 y 52 % en 2025. En su explicación SHAP pesan sobre todo las corrientes (32 %) y el oleaje (23 % a 26 %).
- **Validación con daños reales** (`src/validacion_danos.py`): el índice detecta cuándo la exposición es extrema; dónde ocurre el daño depende también de la vulnerabilidad de cada frente, que el índice no mide.
- **OE4:** panel con ranking, mapa semáforo, mapa de calor, ficha por tramo con SHAP, alerta del trimestre siguiente y pestaña de desempeño.

Detalle de las pruebas que llevaron a esta versión: [`docs/laboratorio_v3_historial.md`](docs/laboratorio_v3_historial.md).

## Cómo correrlo

Requiere Python 3.11 o superior. Los datos procesados ya vienen en el repositorio, así que no hace falta descargar nada para reproducir los resultados.

```bash
git clone https://github.com/Proyecto1rfj/semaforo-litoral-andaluz.git
cd semaforo-litoral-andaluz
python3 -m venv .venv
source .venv/bin/activate          # en Windows: .venv\Scripts\activate
pip install -r requirements_completo.txt
python ejecutar_todo.py            # OE1 → OE2 → OE3 → intervalos, tendencias y alerta (unos 5 minutos)
streamlit run app.py               # OE4: panel en el navegador
```

En Mac basta con doble clic en `correr_solo_modelo.command` (usa los datos ya procesados) y luego en `abrir_panel.command`. `correr_modelo.command` además descarga y reprocesa los datos crudos. Los `.py` no se abren con doble clic ni arrastrándolos a la Terminal. Si XGBoost falla al cargar en un Mac con Anaconda, `entorno.sh` instala aparte un `libomp` compatible.

Los notebooks de `notebooks/` recorren lo mismo paso a paso, con tablas para revisar cada fase.

### Datos crudos (opcional)

Solo hacen falta para reprocesar desde cero (por ejemplo, si cambian los tramos o se agrega una variable). Para correr el modelo y el panel basta con lo que ya trae el repositorio.

- **REDMAR**: la caché mensual (Huelva, Bonanza y Tarifa) ya está en `data/raw/redmar/meses/`.
- **Copernicus IBI** (unos 2,5 GB en netCDF): un solo archivo, `datos_crudos_copernicus.zip`, en la carpeta compartida del grupo (enlace: PENDIENTE). Se descomprime en la raíz del repositorio; ya trae la ruta `data/raw/copernicus/<grupo>/Txx.nc`. Después:

```bash
python -m src.descarga procesar    # regenera copernicus_diario.csv y redmar_diario.csv
python -m src.marea                # nivel del mar no astronómico (unos 10 minutos)
python -m src.marea_v2 corrientes  # corrientes sin marea (unos 15 minutos)
python -m src.marea_v2 prevista    # marea prevista por día y trimestre
python -m src.marea_v2 validar     # residuo contra REDMAR
python ejecutar_todo.py
```

Fuentes: E.U. Copernicus Marine Service Information (reanálisis IBI de oleaje y física) y Puertos del Estado (REDMAR). Los datos se comparten con fines académicos y citando su origen.

## Estructura y relación con los OE

| Archivo | OE | Qué hace |
|---|---|---|
| `config.py` | todos | Ventana, partición, indicadores, umbrales e interruptores de la versión 3 (`NIVEL_INDICE`, `CORRIENTE_INDICE`, `NORMALIZACION`, `COINCIDENCIA`) |
| `src/tramos.py` | OE1 | Segmentación en tramos de 10 km (y la anterior de 40 puntos) y mareógrafos REDMAR |
| `src/celdas_10km.py` | OE1 | Arma la celda de Copernicus de cada tramo de 10 km desde las descargas existentes |
| `src/descarga.py` | OE1 | Descarga Copernicus y REDMAR y las procesa a series diarias |
| `src/marea.py` | OE1 | Nivel del mar no astronómico |
| `src/marea_v2.py` | OE1 | Corrientes sin marea, marea prevista y validación del residuo con REDMAR |
| `src/integracion.py` | OE1 | Une fuentes por tramo, agrega por trimestre, mide cobertura y calcula la coincidencia temporal-pleamar |
| `src/ieecc.py` | OE2 | Normaliza los cinco indicadores con 2000-2018, calcula el IEECC, clases por terciles y sensibilidad |
| `src/modelado.py` | OE3 | RF, SVM, XGBoost y LambdaMART contra persistencia y clase mayoritaria; selección en validación; cambios de clase; SHAP |
| `src/analisis.py` | OE2-OE4 | Intervalos de confianza por bootstrap, tendencias de Mann-Kendall y alerta del panel |
| `src/validacion_danos.py` | OE2 | Validación del índice con daños documentados por temporales (en el espacio y en el tiempo) |
| `src/validacion_boya.py` | OE1 | Validación del oleaje del reanálisis con boyas de Puertos del Estado (doble clic: `validar_boya.command`) |
| `src/analisis_shap.py` | OE3 | SHAP de LambdaMART y XGBoost en las pruebas 2022-2024 y 2025 (doble clic: `analizar_shap.command`) |
| `app.py` | OE4 | Panel: mapa semáforo, ranking, ficha (IEECC, clases, SHAP y alerta), mapa de calor y métricas |
| `src/datos_sinteticos.py` | (apoyo) | Datos de prueba para correr sin descargas |
| `data/` | | Datos procesados reales |
| `docs/` | | Historial del laboratorio, segmentación, cambios del Capítulo 1 y vista estática del semáforo |
| `resultados/` | | Métricas, intervalos, tendencias, alerta, predicciones, SHAP y modelo elegido |

## Decisiones incorporadas (Capítulo 1 versión 3)

- IEECC con cinco indicadores: oleaje (p95 del máximo diario), nivel del mar no astronómico (p95 del máximo diario), viento (p95), corrientes no astronómicas (media) y días de temporal en pleamar viva. Normalización de 0 a 1 con mínimo y máximo de 2000-2018, pesos iguales y clases por terciles dentro de cada trimestre.
- Temporal: Hs sobre el percentil 95 de 2000-2018 (1,89 m) o marejada ciclónica sobre el p95 del tramo. Pleamar viva: pleamar diaria prevista sobre el p75 del tramo.
- Sensibilidad: pesos de entropía, cada peso al doble y a la mitad, y corte 25/50/25; meta de menos de 20 % de cambio de clase. Se informan también los saltos entre alta y baja y el cambio en la clase alta.
- Entradas del modelo: los cinco indicadores de t y t−1, el trimestre del año y los días de pleamar viva previstos para t+1, sin identificador de tramo.
- Pregunta del OE3: ¿hay capacidad predictiva más allá de la persistencia? Selección en validación, resultado en prueba con intervalos de confianza del 95 % por bootstrap en bloques de trimestres.
- LambdaMART en LightGBM; parada temprana en XGBoost y LambdaMART; SVM con escalamiento de Platt dentro del pipeline.
- Persistencia = misma clase y misma posición (IEECC de t) en t+1. Los modelos se reentrenan con 2000-2021 antes de la prueba; el pronóstico vigente (2025-T1) usa todo el periodo.

## Datos públicos reales (Capítulo 1)

`src/descarga.py` baja las fuentes públicas. Solo hace falta para actualizar o ampliar los datos; los ya procesados vienen en `data/`.

| Fuente | Qué aporta | Cómo se obtiene |
|---|---|---|
| Copernicus Marine, reanálisis IBI (oleaje, 1/36°, horario) | Hs (VHM0), Tp (VTPK), dirección | Automático, con cuenta gratuita |
| Copernicus Marine, reanálisis IBI (física, horario) | Nivel del mar (zos) y corrientes de superficie (uo, vo) | Automático, misma cuenta |
| Copernicus IBI, tensión del viento | Viento | Automático, misma cuenta |
| Copernicus Marine in situ (IBI) | Oleaje medido en boyas de Puertos del Estado (Golfo de Cádiz, Cádiz y Sevilla) para validar | Automático, misma cuenta |
| REDMAR (THREDDS de Puertos del Estado) | Nivel del mar observado en Huelva, Bonanza y Tarifa, desde 2007 | Automático, sin cuenta |
| SIMAR (Portus) | Descartado en el Capítulo II: es un retroanálisis (otro modelo) y solo se descarga a mano | — |

Pasos:

```bash
source .venv/bin/activate
pip install -r requirements_completo.txt
copernicusmarine login                 # una vez, con el usuario de marine.copernicus.eu
python -m src.descarga copernicus      # cajas por tramo × 4 grupos (reanudable)
python -m src.celdas_10km              # una celda de mar por tramo de 10 km
python -m src.descarga redmar          # lo más lento: miles de archivos diarios (reanudable)
python -m src.descarga procesar        # deja copernicus_diario.csv y redmar_diario.csv
python ejecutar_todo.py                # desde aquí el flujo usa datos reales
streamlit run app.py
```

Cuando existe `data/raw/copernicus_diario.csv`, `config.MODO` pasa a `"real"` y el panel deja de mostrar el aviso de datos sintéticos.

**SIMAR.** Portus no ofrece descarga automática (y al 8-oct-2026 su API respondía con error). Los archivos se bajan desde https://portus.puertos.es > Datos Históricos > Oleaje y se dejan en `data/raw/simar/`. El nombre de cada archivo debe contener el código que figura en la columna `punto_simar` de `tramos.csv` (hay que reemplazar los códigos provisionales SIMAR_01... por los reales). Los tramos con archivo SIMAR usan SIMAR; el resto sigue con Copernicus.

**Tramos.** `tramos.csv` tiene 23 tramos de unos 10 km sobre una poligonal simplificada de la costa (226 km). Los netCDF de cada tramo se arman con `python -m src.celdas_10km` a partir de `data/raw/copernicus/` y quedan en `data/raw/copernicus_10km/`.

**Notas de método:**
- Las series horarias se resumen a diarias: Hs y nivel no astronómico con el máximo diario, Tp y corriente no astronómica con la media.
- REDMAR se lee cada 1 minuto y se promedia por hora.
- La validación compara anomalías, porque el modelo y el mareógrafo usan referencias verticales distintas.
- El umbral de temporal se calibra solo: percentil 95 de Hs en 2000-2018.
- La señal SLEV de REDMAR viene invertida (correlación negativa con el reanálisis) y se invierte al procesarla.
