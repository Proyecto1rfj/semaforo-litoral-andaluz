"""Validación del oleaje del reanálisis IBI con la boya Golfo de Cádiz (red exterior de Puertos del Estado).

Hace para el oleaje lo mismo que src/marea_v2.py validar hace con REDMAR para el nivel del mar:
contrasta el modelo con una medición independiente.

Pasos (correr en el Mac, con `copernicusmarine login` hecho):
  1. Baja el índice del producto in situ del IBI de Copernicus y busca boyas con altura significativa
     (VHM0) dentro del golfo de Cádiz.
  2. Descarga el archivo histórico de la boya con el registro más largo.
  3. Baja la altura de ola horaria del reanálisis IBI en la celda de la boya (2003 a 2024).
  4. Compara hora a hora y por máximo diario: correlación, sesgo, error cuadrático medio y
     porcentaje de días extremos de la boya (sobre su p99) que el reanálisis también marca (sobre su p95).

Salida: resultados/validacion_oleaje_boya.csv
Uso:    python -m src.validacion_boya
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

sys.path.append(str(Path(__file__).resolve().parents[1]))
import config as C

DATASETS_INSITU = ["cmems_obs-ins_ibi_phybgcwav_mynrt_na_irr", "cmems_obs-ins_glo_phybgcwav_mynrt_na_irr"]
OLEAJE_IBI = "cmems_mod_ibi_wav_my_0.027deg_PT1H-i"
CAJA_GOLFO = dict(lat_min=35.8, lat_max=37.3, lon_min=-7.8, lon_max=-6.0)
INI, FIN = "2003-01-01T00:00:00", "2024-12-31T23:00:00"
DIR = C.RAW / "boya"


def _cm():
    import copernicusmarine as cm
    return cm


def buscar_boya():
    cm = _cm()
    DIR.mkdir(parents=True, exist_ok=True)
    for ds in DATASETS_INSITU:
        try:
            cm.get(dataset_id=ds, index_parts=True, output_directory=DIR / "indice", no_directories=True,
                   overwrite=True, disable_progress_bar=True)
        except Exception as e:  # noqa: BLE001
            print(f"  {ds}: no se pudo bajar el índice ({e})"); continue
        idx = DIR / "indice" / "index_history.txt"
        if not idx.exists():
            print(f"  {ds}: sin index_history.txt"); continue
        cols = ["product_id", "file_name", "lat_min", "lat_max", "lon_min", "lon_max",
                "time_start", "time_end", "institution", "date_update", "data_mode", "parameters"]
        df = pd.read_csv(idx, comment="#", header=None, names=cols, skipinitialspace=True)
        for c in ["lat_min", "lat_max", "lon_min", "lon_max"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        g = CAJA_GOLFO
        sel = df[df.parameters.astype(str).str.contains("VHM0")
                 & (df.lat_max >= g["lat_min"]) & (df.lat_min <= g["lat_max"])
                 & (df.lon_max >= g["lon_min"]) & (df.lon_min <= g["lon_max"])].copy()
        if sel.empty:
            print(f"  {ds}: no hay boyas con VHM0 en el golfo de Cádiz"); continue
        sel["anios"] = (pd.to_datetime(sel.time_end, errors="coerce")
                        - pd.to_datetime(sel.time_start, errors="coerce")).dt.days / 365.25
        sel = sel.sort_values("anios", ascending=False)
        print("  Candidatas:"); print(sel[["file_name", "institution", "time_start", "time_end", "anios"]].head(8).to_string(index=False))
        sel.to_csv(DIR / "candidatas.csv", index=False)
        return ds, sel.iloc[0]
    raise SystemExit("No se encontró una boya con oleaje en el golfo de Cádiz.")


def bajar_boya(ds, fila):
    cm = _cm()
    nombre = Path(str(fila.file_name).strip()).name
    destino = DIR / "datos" / nombre
    if destino.exists():
        return destino
    lista = DIR / "lista.txt"
    lista.write_text(str(fila.file_name).strip() + "\n")
    cm.get(dataset_id=ds, file_list=str(lista), output_directory=DIR / "datos", no_directories=True,
           overwrite=True, disable_progress_bar=True)
    if not destino.exists():
        raise SystemExit(f"La descarga de {nombre} no dejó el archivo esperado")
    return destino


def leer_boya(f):
    ds = xr.open_dataset(f)
    v = ds["VHM0"]
    if "VHM0_QC" in ds:
        v = v.where(ds["VHM0_QC"].isin([1, 2]))
    for d in [d for d in v.dims if d.upper() != "TIME"]:
        v = v.max(d, skipna=True)
    s = v.to_series().dropna()
    s.index = pd.to_datetime(s.index)
    lat = float(np.nanmean(ds["LATITUDE"].values)); lon = float(np.nanmean(ds["LONGITUDE"].values))
    nombre = ds.attrs.get("platform_name", ds.attrs.get("platform_code", f.stem))
    return s.resample("1h").mean().dropna(), lat, lon, nombre


def bajar_modelo(lat, lon, etiqueta):
    cm = _cm()
    f = DIR / f"ibi_oleaje_{etiqueta}.nc"
    if f.exists():
        return f
    kw = dict(variables=["VHM0"], minimum_longitude=lon - 0.02, maximum_longitude=lon + 0.02,
              minimum_latitude=lat - 0.02, maximum_latitude=lat + 0.02,
              start_datetime=INI, end_datetime=FIN, output_directory=DIR,
              output_filename=f.name, overwrite=True, disable_progress_bar=True)
    try:
        cm.subset(dataset_id=OLEAJE_IBI, **kw)
    except Exception:  # noqa: BLE001  (el multianual puede no llegar a fin de 2024)
        kw["end_datetime"] = "2023-12-31T23:00:00"
        cm.subset(dataset_id=OLEAJE_IBI, **kw)
    return f


def leer_modelo(f, lat, lon):
    ds = xr.open_dataset(f)
    v = ds["VHM0"]
    la = "latitude" if "latitude" in v.dims else "lat"; lo = "longitude" if "longitude" in v.dims else "lon"
    d2 = (ds[la] - lat) ** 2 + (ds[lo] - lon) ** 2
    s = v.where(d2 == d2.min()).max([la, lo], skipna=True).to_series().dropna()
    s.index = pd.to_datetime(s.index)
    return s


def comparar(b, m):
    j = pd.concat({"boya": b, "modelo": m}, axis=1, sort=True).dropna()
    dia = j.resample("1D").max().dropna()
    ext = dia.boya > dia.boya.quantile(0.99)
    fila = dict(
        horas_comparadas=len(j), dias_comparados=len(dia),
        desde=str(j.index.min().date()), hasta=str(j.index.max().date()),
        correlacion_horaria=round(j.boya.corr(j.modelo), 3),
        sesgo_m=round((j.modelo - j.boya).mean(), 3),
        ecm_m=round(float(np.sqrt(((j.modelo - j.boya) ** 2).mean())), 3),
        correlacion_max_diario=round(dia.boya.corr(dia.modelo), 3),
        extremos_boya=int(ext.sum()),
        extremos_tambien_en_modelo=round(float((dia.modelo[ext] > dia.modelo.quantile(0.95)).mean()), 3),
    )
    return fila


if __name__ == "__main__":
    print(">> 1. Buscando boyas con oleaje en el golfo de Cádiz…")
    ds, _ = buscar_boya()
    cand = pd.read_csv(DIR / "candidatas.csv")
    cand = cand[(cand.institution.astype(str).str.contains("Puertos")) & (cand.anios > 10)].head(3)
    filas = []
    for _, fila in cand.iterrows():
        etiqueta = Path(str(fila.file_name)).stem
        print(f">> 2. {etiqueta}: descargando la boya…")
        f = bajar_boya(ds, fila)
        b, lat, lon, nombre = leer_boya(f)
        b = b[(b.index >= INI) & (b.index <= FIN)]
        if len(b) < 24 * 365:
            print(f"   {nombre}: menos de un año con dato en 2003-2024, se omite"); continue
        print(f"   {nombre} ({lat:.3f}, {lon:.3f}): {len(b):,} horas con dato entre 2003 y 2024")
        print(">> 3. Descargando el oleaje del reanálisis IBI en la celda de la boya…")
        m = leer_modelo(bajar_modelo(lat, lon, etiqueta), lat, lon)
        print(">> 4. Comparando…")
        r = comparar(b, m); r = {"boya": nombre, "archivo": etiqueta, "lat": round(lat, 3), "lon": round(lon, 3), **r}
        for k, v in r.items():
            print(f"   {k}: {v}")
        filas.append(r)
    out = C.RESULTADOS / "validacion_oleaje_boya.csv"
    pd.DataFrame(filas).to_csv(out, index=False)
    print(f"Listo: {out}")
