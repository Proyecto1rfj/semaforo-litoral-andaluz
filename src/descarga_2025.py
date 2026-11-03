"""Descarga 2025 del reanálisis IBI de Copernicus para la prueba prospectiva (correr en el Mac).

Baja el año 2025 en la MISMA celda de mar que ya usa cada tramo (data/raw/calidad_celdas.csv) y lo
guarda como data/raw/copernicus_10km/<grupo>/Txx_2025.nc, con las mismas coordenadas que Txx.nc.
Como descarga._abrir une todos los Txx*.nc del tramo, el resto del flujo no cambia.
No toca los archivos 2000-2024. Es reanudable: si un Txx_2025.nc ya existe, lo salta.

Si el reanálisis multianual ("_my_") no llega a diciembre de 2025, completa lo que falta con el
producto interino ("_myint_"), como se hizo antes con 2024.

Uso:  python -m src.descarga_2025
"""
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import xarray as xr

sys.path.append(str(Path(__file__).resolve().parents[1]))
import config as C
from src import descarga as D

INI, FIN = "2025-01-01T00:00:00", "2025-12-31T23:00:00"
CAJA = 0.02            # media celda alrededor de la celda ya elegida (0,027°)
TMP = C.RAW / "_tmp_2025"


def _bajar(dataset_id, variables, lat, lon, ini, fin, nombre):
    import copernicusmarine as cm
    TMP.mkdir(parents=True, exist_ok=True)
    f = TMP / nombre
    cm.subset(dataset_id=dataset_id, variables=variables,
              minimum_longitude=lon - CAJA, maximum_longitude=lon + CAJA,
              minimum_latitude=lat - CAJA, maximum_latitude=lat + CAJA,
              start_datetime=ini, end_datetime=fin,
              output_directory=TMP, output_filename=nombre, overwrite=True, disable_progress_bar=True)
    return f


def _a_celda(f, ref, variables):
    """Deja el archivo en la celda de referencia, con sus coordenadas exactas y sin dimensiones extra."""
    with xr.open_dataset(f) as ds:
        sub = ds[variables]
        if "depth" in sub.dims:
            sub = sub.isel(depth=0)
        sub = sub.sel(latitude=ref.latitude.values, longitude=ref.longitude.values, method="nearest").load()
    sub = sub.assign_coords(latitude=ref.latitude.values, longitude=ref.longitude.values)
    sub = sub.drop_vars([c for c in sub.coords if c not in ref.coords])
    return sub


def descargar():
    tr = pd.read_csv(C.RAW / "tramos.csv")
    dir_cop = C.RAW / C.COPERNICUS_DIR
    for g, (dataset_id, variables) in D.GRUPOS.items():
        for t in tr.itertuples():
            destino = dir_cop / g / f"{t.tramo}_2025.nc"
            if destino.exists():
                continue
            with xr.open_dataset(dir_cop / g / f"{t.tramo}.nc") as ref:
                ref = ref.load()
            lat, lon = float(ref.latitude.values[0]), float(ref.longitude.values[0])
            print(f"Copernicus 2025 {g:9s} {t.tramo} ...", flush=True)
            partes = []
            try:
                partes.append(_a_celda(_bajar(dataset_id, variables, lat, lon, INI, FIN, f"{g}_{t.tramo}_my.nc"), ref, variables))
            except Exception as e:
                print(f"   reanálisis multianual sin 2025 ({str(e)[:90]}); se usa el interino")
            ultimo = pd.Timestamp(partes[0].time.values[-1]) if partes else pd.Timestamp(INI) - pd.Timedelta(hours=1)
            if ultimo < pd.Timestamp("2025-12-31"):
                paso = pd.Timedelta(days=1) if "P1D" in dataset_id else pd.Timedelta(hours=1)
                ini2 = (ultimo + paso).strftime("%Y-%m-%dT%H:%M:%S")
                try:
                    partes.append(_a_celda(_bajar(dataset_id.replace("_my_", "_myint_"), variables, lat, lon,
                                                  ini2, FIN, f"{g}_{t.tramo}_myint.nc"), ref, variables))
                    print(f"   completado con el interino desde {ini2[:10]}")
                except Exception as e:
                    print(f"   ERROR interino {g} {t.tramo}: {e}")
            if not partes:
                continue
            out = xr.concat(partes, dim="time") if len(partes) > 1 else partes[0]
            out = out.sel(time=slice(INI, FIN))
            _, i = np.unique(out.time.values, return_index=True)
            out = out.isel(time=np.sort(i))
            out.to_netcdf(destino)
            print(f"   {destino.name}: {str(out.time.values[0])[:10]} a {str(out.time.values[-1])[:10]}", flush=True)


def resumen():
    dir_cop = C.RAW / C.COPERNICUS_DIR
    tr = pd.read_csv(C.RAW / "tramos.csv")
    falta = [(g, t) for g in D.GRUPOS for t in tr.tramo if not (dir_cop / g / f"{t}_2025.nc").exists()]
    if falta:
        print(f"\nFALTAN {len(falta)} archivos de 2025: {falta[:6]} ... vuelve a correr (es reanudable)")
        return False
    print("\n2025 completo en los 4 grupos y los", len(tr), "tramos")
    return True


if __name__ == "__main__":
    descargar()
    sys.exit(0 if resumen() else 1)
