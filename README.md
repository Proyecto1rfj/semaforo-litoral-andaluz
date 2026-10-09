# Semáforo predictivo de exposición climática del litoral atlántico andaluz

Proyecto de Grado MII712, Magíster en Ingeniería Industrial UNAB · Grupo 3 (Juan Pablo Mestre, Rubén Ugarte, Felipe Avendaño).

El semáforo ordena los tramos del litoral atlántico de Andalucía (de la desembocadura del Guadiana a Tarifa) según su exposición climática esperada en el trimestre siguiente, para focalizar la inspección y el mantenimiento preventivo. Usa solo datos abiertos (Copernicus Marine y REDMAR de Puertos del Estado), un índice de exposición por tramo y trimestre (IEECC) y modelos de clasificación y ordenamiento evaluados con partición temporal frente a una línea base de persistencia.

## Estado actual (9 de octubre de 2026)

- Corre de punta a punta con **datos reales** 2000 a 2024 para 40 tramos provisorios.
- El nivel del mar del índice es ahora el **no astronómico** (residuo meteorológico): se le resta a la serie horaria de Copernicus la marea astronómica ajustada por análisis armónico con 2000-2018 (`src/marea.py`, UTide). Con el nivel total, la marea dominaba el indicador y lo ponía en contra del oleaje (correlación −0,12); sin marea la correlación con el oleaje es 0,71.
- Resultados frente a la Tabla 1 del Capítulo 1: OE1 cumple (100 % de cobertura), OE2 cumple en 8 de 10 escenarios de sensibilidad (antes 2 de 10; fallan nivel x2 con 27,5 % y viento x2 con 22,2 %), OE4 cumple. En OE3 los modelos mejoran mucho en prueba (Random Forest: exactitud balanceada 0,754 y sensibilidad de clase alta 0,897, antes 0,645 y 0,756), pero la persistencia sigue arriba (0,782 y 0,936), así que se mantiene el plan B.
- La parte de Tarifa (T35 a T40) queda casi siempre en clase alta, por el oleaje y las corrientes del Estrecho.
- Pendientes del grupo: segmentación definitiva de tramos de 10 km, fuente del viento (SIMAR o Copernicus) y ajustes al texto del Capítulo 1.

El detalle está en [`docs/resumen_semaforo_grupo3.pdf`](docs/resumen_semaforo_grupo3.pdf). Una vista del semáforo con los resultados actuales está en [`docs/semaforo_vista_estatica.html`](docs/semaforo_vista_estatica.html) (descargarla y abrirla en el navegador).

## Cómo correrlo

Requiere Python 3.11 o superior. Los datos procesados ya vienen en el repositorio, así que no hace falta descargar nada para reproducir los resultados.

```bash
git clone https://github.com/Proyecto1rfj/semaforo-litoral-andaluz.git
cd semaforo-litoral-andaluz
python3 -m venv .venv
source .venv/bin/activate          # en Windows: .venv\Scripts\activate
pip install -r requirements.txt
python ejecutar_todo.py            # OE1 → OE2 → OE3 (menos de un minuto)
streamlit run app.py               # OE4: panel en el navegador
```

En Mac también se puede hacer doble clic en `correr_modelo.command` y `abrir_panel.command`. Si XGBoost falla al cargar en un Mac con Anaconda, `entorno.sh` instala aparte un `libomp` compatible.

Los notebooks de `notebooks/` recorren lo mismo paso a paso, con tablas para revisar cada fase.

### Datos crudos (opcional)

Solo hacen falta para reprocesar desde cero (por ejemplo, si cambian los tramos o se agrega una variable). Para correr el modelo y el panel basta con lo que ya trae el repositorio.

- **REDMAR**: la caché mensual (Huelva, Bonanza y Tarifa) ya está en `data/raw/redmar/meses/`.
- **Copernicus IBI** (unos 2,5 GB en netCDF): un solo archivo, `datos_crudos_copernicus.zip`, en la carpeta compartida del grupo (enlace: PENDIENTE). Se descomprime en la raíz del repositorio; ya trae la ruta `data/raw/copernicus/<grupo>/Txx.nc`. Después:

```bash
python -m src.descarga procesar    # regenera copernicus_diario.csv y redmar_diario.csv
python -m src.marea                # nivel del mar no astronómico (unos 10 minutos)
python ejecutar_todo.py
```

Fuentes: E.U. Copernicus Marine Service Information (reanálisis IBI de oleaje y física) y Puertos del Estado (REDMAR). Los datos se comparten con fines académicos y citando su origen.

## Estructura y relación con los OE

| Archivo | OE | Qué hace |
|---|---|---|
| `config.py` | todos | Ventana 2000-2024, partición temporal, indicadores, umbrales, cortes y semilla |
| `src/datos_sinteticos.py` | (apoyo) | Crea datos de prueba en `data/raw/` |
| `src/integracion.py` | OE1 | Une fuentes por tramo, agrega a trimestre, mide cobertura (≥90 %) y valida nivel del mar con REDMAR |
| `src/ieecc.py` | OE2 | Normaliza los cuatro indicadores con 2000-2018, calcula el IEECC, clases por terciles en cada trimestre y sensibilidad (10 escenarios) |
| `src/modelado.py` | OE3 | RF, SVM, XGBoost y LambdaMART (LightGBM) vs persistencia y clase mayoritaria; selección en validación; plan B; SHAP |
| `src/descarga.py` | OE1 | Descarga Copernicus y REDMAR y las procesa a series diarias |
| `src/tramos.py` | OE1 | Segmentación preliminar de los 40 tramos y mareógrafos REDMAR |
| `app.py` | OE4 | Panel: mapa semáforo, ranking, ficha del tramo (IEECC, clases, SHAP) y mapa de calor tramo × trimestre |
| `data/` | | Datos procesados reales: series diarias por tramo, REDMAR, panel trimestral e IEECC |
| `docs/` | | Resumen para el grupo y vista estática del semáforo |
| `resultados/` | | Tablas de métricas, predicciones, SHAP y modelo elegido |

## Decisiones ya incorporadas

- IEECC con los cuatro indicadores del Capítulo 1 (oleaje, nivel del mar, viento, corrientes), normalizados de 0 a 1 con mínimo y máximo de 2000-2018 y sumados con pesos iguales; clases por terciles dentro de cada trimestre.
- Sensibilidad: pesos de entropía, cada peso al doble y a la mitad, y corte 25/50/25; meta de menos de 20 % de cambio de clase por escenario.
- Entradas del modelo: los cuatro indicadores de t y t−1 más el trimestre del año, sin identificador de tramo.
- LambdaMART en LightGBM; parada temprana con el bloque de validación en XGBoost y LambdaMART; SVM con escalamiento de Platt.
- Métricas: exactitud balanceada, F1 macro, matriz de confusión, sensibilidad y precisión de la clase alta, NDCG@10 y precisión en los 10 primeros tramos.
- Panel: ranking, mapa semáforo, mapa de calor tramo × trimestre y ficha por tramo (IEECC, clase actual, clase predicha y SHAP).
- La distancia entre la celda de Copernicus usada y el punto del tramo queda en data/raw/calidad_celdas.csv.
- Partición por trimestre objetivo: entrenamiento 2000-2018, validación 2019-2021, prueba 2022-2024. El pronóstico vigente es 2025-T1.
- Los pesos de entropía se calculan solo con el periodo de entrenamiento.
- El escalado del SVM se ajusta dentro del pipeline, solo con datos de entrenamiento.
- Persistencia = misma clase y misma posición (IEECC de t) en t+1.
- Los modelos se reentrenan con 2000-2021 antes de evaluar la prueba; el pronóstico vigente usa todo el periodo.

## Datos públicos reales (Capítulo 1)

`src/descarga.py` baja las fuentes públicas. Solo hace falta para actualizar o ampliar los datos; los ya procesados vienen en `data/`.

| Fuente | Qué aporta | Cómo se obtiene |
|---|---|---|
| Copernicus Marine, reanálisis IBI (oleaje, 1/36°, horario) | Hs (VHM0), Tp (VTPK), dirección | Automático, con cuenta gratuita |
| Copernicus Marine, reanálisis IBI (física, horario) | Nivel del mar (zos) y corrientes de superficie (uo, vo) | Automático, misma cuenta |
| Copernicus IBI, tensión del viento | Viento aproximado (solo si falta SIMAR) | Automático, misma cuenta |
| REDMAR (THREDDS de Puertos del Estado) | Nivel del mar observado en Huelva, Bonanza y Tarifa, desde 2007 | Automático, sin cuenta |
| SIMAR (Portus) | Oleaje y viento por nodo, desde 1958 | Manual, punto a punto en Portus |

Pasos:

```bash
source .venv/bin/activate
pip install -r requirements.txt
copernicusmarine login                 # una vez, con el usuario de marine.copernicus.eu
python -m src.descarga copernicus      # 40 tramos × 4 grupos (reanudable)
python -m src.descarga redmar          # lo más lento: miles de archivos diarios (reanudable)
python -m src.descarga procesar        # deja copernicus_diario.csv y redmar_diario.csv
python ejecutar_todo.py                # desde aquí el flujo usa datos reales
streamlit run app.py
```

Cuando existe `data/raw/copernicus_diario.csv`, `config.MODO` pasa a `"real"` y el panel deja de mostrar el aviso de datos sintéticos.

**SIMAR.** Portus no ofrece descarga automática (y al 8-oct-2026 su API respondía con error). Los archivos se bajan desde https://portus.puertos.es > Datos Históricos > Oleaje y se dejan en `data/raw/simar/`. El nombre de cada archivo debe contener el código que figura en la columna `punto_simar` de `tramos.csv` (hay que reemplazar los códigos provisionales SIMAR_01... por los reales). Los tramos con archivo SIMAR usan SIMAR; el resto sigue con Copernicus.

**Tramos.** `tramos.csv` es una segmentación preliminar: 40 puntos equiespaciados entre Ayamonte y Tarifa. Cuando el grupo cierre la segmentación, se reemplaza el archivo manteniendo las columnas y se vuelve a descargar.

**Notas de método:**
- Las series horarias se resumen a diarias: Hs y nivel con el máximo diario, Tp y corriente con la media.
- REDMAR se lee cada 1 minuto y se promedia por hora.
- La validación compara anomalías, porque el modelo y el mareógrafo usan referencias verticales distintas.
- El umbral de temporal (indicador auxiliar, no entra al índice) se calibra solo: percentil 95 de Hs en 2000-2018.
- La señal SLEV de REDMAR viene invertida (correlación negativa con el reanálisis) y se invierte al procesarla.
