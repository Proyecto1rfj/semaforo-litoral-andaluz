"""Segmentación preliminar del litoral atlántico andaluz en tramos (Ayamonte a Tarifa).

Es una aproximación: 40 puntos equiespaciados sobre una poligonal de la costa. Cuando el
grupo cierre la segmentación definitiva (Capítulo 1, pendiente), basta con reemplazar
data/raw/tramos.csv manteniendo las columnas.
"""
import numpy as np
import pandas as pd

N_TRAMOS = 40

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
