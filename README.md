# Semáforo predictivo de exposición climática del litoral atlántico andaluz

Proyecto de Grado MII712, Magíster en Ingeniería Industrial UNAB · Grupo 3 (Juan Pablo Mestre, Rubén Ugarte, Felipe Avendaño).

El semáforo ordena los tramos del litoral atlántico de Andalucía (de la desembocadura del Guadiana a Tarifa) según su exposición climática esperada en el trimestre siguiente, para focalizar la inspección y el mantenimiento preventivo. Usa solo datos abiertos (Copernicus Marine y REDMAR de Puertos del Estado), un índice de exposición por tramo y trimestre (IEECC) y modelos de clasificación y ordenamiento evaluados con partición temporal frente a una línea base de persistencia.

## Estado actual (versión 3, 9 de octubre de 2026)

Esta rama sigue el Capítulo 1 versión 3. La versión anterior quedó en la rama `version-1`.

- Corre de punta a punta con **datos reales** 2000 a 2024 para **23 tramos de unos 10 km** (Capítulo 1). La segmentación anterior de 40 puntos quedó en la rama `tramos-40`; la comparación está en [`docs/segmentacion_10km.md`](docs/segmentacion_10km.md).
- **La marea astronómica se trata en tres capas.** Se resta del nivel del mar y de las corrientes (análisis armónico con UTide, ajustado con 2000-2018), se cuentan los días de temporal en pleamar viva como quinto indicador y la pleamar viva prevista para el trimestre siguiente entra al modelo, porque se conoce de antemano.
- **OE1:** 100 % de cobertura; cada tramo tiene su propia celda del reanálisis. El residuo meteorológico coincide con el de los mareógrafos (correlación 0,93 en Huelva, 0,88 en Bonanza y 0,81 en Tarifa).
- **OE2:** 3 de los 10 escenarios originales cumplen la meta de menos de 20 % de cambio de clase (más los 2 del nuevo indicador); los saltos entre alta y baja no pasan de 5,3 %. Se informa como limitación: sin la marea, la exposición del litoral es pareja entre tramos.
- **OE3:** en la prueba 2022-2024, LambdaMART supera a la persistencia en exactitud balanceada (0,635 contra 0,595) y en sensibilidad de la clase alta (0,677 contra 0,646), y queda apenas bajo en NDCG de los 6 primeros (0,954 contra 0,959). Nada es estadísticamente significativo y en validación no la supera en ambas métricas, así que la persistencia queda como referencia operativa.
- **Validación con daños reales** (`src/validacion_danos.py`, obras de emergencia por temporal 2015-2024, fuentes en `data/validacion/eventos_temporales.csv`): el trimestre del daño queda en el percentil 86 de la historia del propio tramo (permutación, p < 0,001), pero solo el 31 % de los tramos dañados estaba en prioridad alta frente al resto (azar: 33 %). El índice detecta cuándo la exposición es extrema; dónde ocurre el daño depende también de la vulnerabilidad de cada frente, que el índice no mide.
- **OE4:** panel con ranking, mapa semáforo, mapa de calor, ficha por tramo y alerta del trimestre siguiente.
- **Tendencias 2000-2024:** el nivel del mar no astronómico sube en 15 de 23 tramos (mediana +1,9 cm por década) y el viento baja en 5.
- **Pendiente:** enlace al zip de datos crudos.

Detalle de las pruebas que llevaron a esta versión: [`docs/laboratorio_v3_historial.md`](docs/laboratorio_v3_historial.md).

## Cómo correrlo

Requiere Python 3.11 o superior. Los datos procesados ya vienen en el repositorio, así que no hace falta descargar nada para reproducir los resultados.

```bash
git clone https://github.com/Proyecto1rfj/semaforo-litoral-andaluz.git
cd semaforo-litoral-andaluz
python3 -m venv .venv
source .venv/bin/activate          # en Windows: .venv\Scripts\activate
pip install -r requirements.txt
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
| `app.py` | OE4 | Panel: mapa semáforo, ranking, ficha (IEECC, clases, SHAP y alerta), mapa de calor y métricas |
| `src/datos_sinteticos.py` | (apoyo) | Datos de prueba para correr sin descargas |
| `data/` | | Datos procesados reales |
| `docs/` | | Resúmenes para el grupo, historial del laboratorio y vista estática del semáforo |
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
| Copernicus IBI, tensión del viento | Viento (fuente principal; SIMAR solo como contraste) | Automático, misma cuenta |
| REDMAR (THREDDS de Puertos del Estado) | Nivel del mar observado en Huelva, Bonanza y Tarifa, desde 2007 | Automático, sin cuenta |
| SIMAR (Portus) | Oleaje y viento por nodo, desde 1958 | Manual, punto a punto en Portus |

Pasos:

```bash
source .venv/bin/activate
pip install -r requirements.txt
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
