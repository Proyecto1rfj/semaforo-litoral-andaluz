"""Parámetros del semáforo predictivo (un solo lugar para cambiar decisiones de diseño)."""
from pathlib import Path

BASE = Path(__file__).resolve().parent
RAW = BASE / "data" / "raw"
PROCESSED = BASE / "data" / "processed"
RESULTADOS = BASE / "resultados"

# Ventana temporal y partición (Capítulo 1)
INICIO, FIN = "2000-01-01", "2024-12-31"
ANIOS_TRAIN = (2000, 2018)
ANIOS_VALID = (2019, 2021)
ANIOS_TEST = (2022, 2024)

# Indicadores del IEECC (Capítulo 1: oleaje, nivel del mar, viento y corrientes), con valores
# extremos por trimestre porque el daño lo producen los temporales más que las condiciones medias
INDICADORES = {
    "hs_p95": "Oleaje: altura significativa, percentil 95 del máximo diario (m)",
    "nivel_p95": "Nivel del mar no astronómico: percentil 95 del máximo diario (m)",
    "viento_p95": "Viento: velocidad, percentil 95 (m/s)",
    "corriente_media": "Corrientes no astronómicas: velocidad media (m/s)",
}
# Qué nivel del mar entra al índice: "no_astronomico" (residuo meteorológico, sin marea astronómica,
# src/marea.py) o "total" (zos del reanálisis con marea). La marea astronómica es predecible y crece
# de Tarifa a Huelva; con "total" dominaba el indicador y fijaba un gradiente que no es exposición.
NIVEL_INDICE = "no_astronomico"
# Laboratorio v2: corrientes sin la corriente de marea (src/marea_v2.py corrientes). "total" = versión 1.
CORRIENTE_INDICE = "no_astronomico"
# Normalización de los indicadores: "percentiles" (posición en la distribución 2000-2018, robusta a un
# extremo aislado) o "minmax" (versión 1).
NORMALIZACION = "minmax"

# Indicador auxiliar (se calcula y se muestra, pero no entra al índice)
AUXILIARES = {"dias_temporal": "Días con Hs sobre el umbral de temporal"}
UMBRAL_TEMPORAL_HS = None  # m; None = percentil 95 de Hs máxima diaria de todos los tramos en 2000-2018
PERCENTIL_TEMPORAL = 0.95
COBERTURA_MINIMA = 0.90    # meta OE1: ≥90 % de días con dato por tramo y trimestre

# Discretización del IEECC
CORTES_TERCILES = [0, 1 / 3, 2 / 3, 1]
CORTES_ALTERNATIVOS = [0, 0.25, 0.75, 1]   # sensibilidad 25/50/25
CLASES = {0: "baja", 1: "media", 2: "alta"}
COLORES = {0: "#2e9d5b", 1: "#e8b400", 2: "#d1373f"}

K_NDCG = 10        # NDCG en los 10 primeros del ranking
K_TOP = 10         # precisión en los primeros tramos: cuántos de los 10 primeros quedaron en clase alta
PARADA_TEMPRANA = 30   # rondas sin mejora en validación (XGBoost y LambdaMART)
SEMILLA = 42

# Modo de datos: "real" cuando existe la salida de src/descarga.py, si no "sintetico"
MODO = "real" if (RAW / "copernicus_diario.csv").exists() else "sintetico"
