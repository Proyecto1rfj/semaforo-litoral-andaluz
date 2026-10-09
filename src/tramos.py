"""Segmentación del litoral atlántico andaluz en tramos de unos 10 km (Ayamonte a Tarifa).

La costa se representa con una poligonal simplificada; se mide su largo en kilómetros, se divide
en tramos de LARGO_TRAMO_KM y cada tramo se representa por el punto medio de su segmento.
Con 10 km cada tramo abarca unas tres celdas del reanálisis IBI (0,027°, unos 3 km), así que
ningún par de tramos comparte celda, y la escala coincide con la de las obras de Costas.
generar_tramos(n) mantiene la segmentación anterior de n puntos equiespaciados.
"""
import numpy as np
import pandas as pd

N_TRAMOS = 40          # segmentación anterior (puntos equiespaciados)
LARGO_TRAMO_KM = 10   # segmentación del Capítulo 1

COSTA = [
    ("Ayamonte", 37.20, -7.40), ("Isla Cristina", 37.19, -7.32), ("Punta Umbría", 37.17, -6.96),
    ("Mazagón", 37.13, -6.83), ("Matalascañas", 37.00, -6.56), ("Desembocadura Guadalquivir", 36.80, -6.40),
    ("Chipiona", 36.74, -6.44), ("Rota", 36.62, -6.36), ("Cádiz", 36.53, -6.30),
    ("Sancti Petri", 36.40, -6.21), ("Conil", 36.28, -6.09), ("Barbate", 36.18, -5.92),
    ("Zahara", 36.13, -5.84), ("Tarifa", 36.01, -5.60),
]

# Mareógrafos REDMAR del tramo de estudio (código en el THREDDS de Puertos del Estado)
REDMAR = {
    "Huelva": {"thredds": "tidegauge_hue5", "lat": 37.132, "lon": -6.834},
    "Bonanza": {"thredds": "tidegauge_bon2", "lat": 36.80, "lon": -6.34},
    "Tarifa": {"thredds": "tidegauge_tari", "lat": 36.01, "lon": -5.60},
}


def generar_tramos(n: int = N_TRAMOS) -> pd.DataFrame:
    lat = np.array([c[1] for c in COSTA]); lon = np.array([c[2] for c in COSTA])
    dist = np.r_[0, np.cumsum(np.hypot(np.diff(lat), np.diff(lon)))]
    pos = np.linspace(0, dist[-1], n)
    t_lat, t_lon = np.interp(pos, dist, lat), np.interp(pos, dist, lon)
    ref = [COSTA[np.argmin(np.abs(dist - p))][0] for p in pos]
    df = pd.DataFrame({
        "tramo": [f"T{i + 1:02d}" for i in range(n)],
        "nombre": [f"{r} ({i + 1})" for i, r in enumerate(ref)],
        "lat": t_lat.round(4), "lon": t_lon.round(4),
    })
    # punto_simar: código del nodo SIMAR asignado (completar al descargar desde Portus)
    df["punto_simar"] = [f"SIMAR_{i + 1:02d}" for i in range(n)]
    df["celda_copernicus"] = [f"IBI_{i + 1:02d}" for i in range(n)]
    est = list(REDMAR)
    d = np.array([[np.hypot(r.lat - REDMAR[e]["lat"], r.lon - REDMAR[e]["lon"]) for e in est]
                  for r in df.itertuples()])
    df["estacion_redmar"] = [est[i] for i in d.argmin(1)]
    return df


def _km(lat, lon):
    lat0 = np.radians(36.6)
    return np.c_[np.asarray(lon) * 111.2 * np.cos(lat0), np.asarray(lat) * 111.2]


def generar_tramos_km(largo_km: float = LARGO_TRAMO_KM) -> pd.DataFrame:
    """Tramos de unos largo_km a lo largo de la poligonal; punto representativo = mitad del tramo."""
    lat = np.array([c[1] for c in COSTA]); lon = np.array([c[2] for c in COSTA])
    xy = _km(lat, lon)
    dist = np.r_[0, np.cumsum(np.hypot(*np.diff(xy, axis=0).T))]
    n = max(1, int(round(dist[-1] / largo_km)))
    bordes = np.linspace(0, dist[-1], n + 1)
    medios = (bordes[:-1] + bordes[1:]) / 2
    t_lat, t_lon = np.interp(medios, dist, lat), np.interp(medios, dist, lon)
    ref = [COSTA[np.argmin(np.abs(dist - p))][0] for p in medios]
    df = pd.DataFrame({
        "tramo": [f"T{i + 1:02d}" for i in range(n)],
        "nombre": [f"{r} ({i + 1})" for i, r in enumerate(ref)],
        "lat": t_lat.round(4), "lon": t_lon.round(4),
        "km_inicio": bordes[:-1].round(1), "km_fin": bordes[1:].round(1),
    })
    df["punto_simar"] = [f"SIMAR_{i + 1:02d}" for i in range(n)]
    df["celda_copernicus"] = [f"IBI_{i + 1:02d}" for i in range(n)]
    est = list(REDMAR)
    d = np.array([[np.hypot(r.lat - REDMAR[e]["lat"], r.lon - REDMAR[e]["lon"]) for e in est] for r in df.itertuples()])
    df["estacion_redmar"] = [est[i] for i in d.argmin(1)]
    return df
