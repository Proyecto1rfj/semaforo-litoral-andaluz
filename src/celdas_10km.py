"""Construye los datos de Copernicus de los tramos de 10 km sin volver a descargar.

Las cajas descargadas para la segmentación anterior (40 puntos, cajas de ±0,04° y ±0,12° en los
tramos que caían en tierra) se solapan y cubren todo el litoral. Para cada tramo nuevo se busca la
celda de mar más cercana entre todas esas cajas y se guarda su serie en
data/raw/copernicus_10km/<grupo>/Txx.nc. Así cada tramo tiene su propia celda.

Uso:  python -m src.celdas_10km [carpeta_origen]   (por defecto data/raw/copernicus)
Luego: COPERNICUS_DIR = "copernicus_10km" en config.py y el flujo normal (procesar, marea, ...).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

import config as C
from src.descarga import GRUPOS

DESTINO = C.RAW / "copernicus_10km"


def _indice(carpeta: Path, var: str) -> pd.DataFrame:
    filas = []
    for f in sorted(carpeta.glob("T*.nc")):
        with xr.open_dataset(f) as ds:
            da = ds[var]
            if "depth" in da.dims:
                da = da.isel(depth=0)
            ok = da.isel(time=slice(0, 48)).notnull().any("time").values
            la, lo = np.meshgrid(ds.latitude.values, ds.longitude.values, indexing="ij")
            for i, j in zip(*np.where(ok)):
                filas.append({"archivo": f, "lat": float(la[i, j]), "lon": float(lo[i, j])})
    return pd.DataFrame(filas).drop_duplicates(["lat", "lon"])


def construir(origen: Path, tramos: pd.DataFrame):
    lat0 = np.radians(36.6)
    calidad = []
    for g, (_, variables) in GRUPOS.items():
        idx = _indice(origen / g, variables[0])
        (DESTINO / g).mkdir(parents=True, exist_ok=True)
        usadas = set()
        for t in tramos.itertuples():
            d = np.hypot((idx.lat - t.lat) * 111.2, (idx.lon - t.lon) * 111.2 * np.cos(lat0))
            k = int(d.values.argmin()); c = idx.iloc[k]
            with xr.open_dataset(c.archivo) as ds:
                sub = ds[variables].sel(latitude=[c.lat], longitude=[c.lon], method="nearest").load()
            sub.to_netcdf(DESTINO / g / f"{t.tramo}.nc")
            calidad.append({"tramo": t.tramo, "grupo": g, "lat": c.lat, "lon": c.lon,
                            "dist_km": round(float(d.iloc[k]), 2), "celda_repetida": (c.lat, c.lon) in usadas})
            usadas.add((c.lat, c.lon))
        print(f"  {g}: {len(tramos)} tramos, {len(usadas)} celdas distintas", flush=True)
    cal = pd.DataFrame(calidad)
    print(cal.groupby("grupo").dist_km.agg(["mean", "max"]).round(1).to_string())
    return cal


if __name__ == "__main__":
    from src.tramos import generar_tramos_km
    origen = Path(sys.argv[1]) if len(sys.argv) > 1 else C.RAW / "copernicus"
    tr = generar_tramos_km()
    tr.to_csv(C.RAW / "tramos.csv", index=False)
    print(f"tramos.csv: {len(tr)} tramos de ~{C.LARGO_TRAMO_KM if hasattr(C, 'LARGO_TRAMO_KM') else 10} km")
    construir(origen, tr)
