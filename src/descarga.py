"""Descarga de los datos públicos del Capítulo 1 (correr en el Mac, con internet).

Fuentes automáticas:
  1. Copernicus Marine, reanálisis IBI (cuenta gratuita, `copernicusmarine login` una vez)
       - Oleaje:     cmems_mod_ibi_wav_my_0.027deg_PT1H-i      VHM0 (Hs), VTPK (Tp), VMDR (dirección)
       - Viento*:    cmems_mod_ibi_phy-mflux_my_0.027deg_P1D-m taum (tensión del viento, diaria)
       - Nivel:      cmems_mod_ibi_phy-ssh_my_0.027deg_PT1H-m  zos
       - Corrientes: cmems_mod_ibi_phy-cur_my_0.027deg_PT1H-m  uo, vo (superficie)
     Se baja una caja pequeña (±0,04°) alrededor de cada tramo, horario 2000-2024.
  2. REDMAR (Puertos del Estado, THREDDS abierto): mareógrafos Huelva, Bonanza y Tarifa,
     archivos diarios desde 2007, leídos por OPeNDAP cada 1 minuto y promediados por hora.

Fuente manual:
  3. SIMAR (Portus). No tiene descarga automática: se baja punto a punto en
     https://portus.puertos.es > Datos Históricos > Oleaje / Viento, y los .txt se dejan en
     data/raw/simar/. Mientras no estén, el oleaje sale de Copernicus y el viento de la
     tensión del viento (*aproximación, ver leer_oleaje_viento en integracion.py).

Uso:
    python -m src.descarga copernicus     # ~40 tramos × 4 grupos, reanudable
    python -m src.descarga redmar         # 3 mareógrafos, reanudable (es lo más lento)
    python -m src.descarga procesar       # pasa todo a CSV diarios en data/raw/
    python -m src.descarga todo
"""
import sys
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import quote, urljoin
from urllib.request import urlopen

import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
import config as C
from src.tramos import REDMAR, generar_tramos

INICIO, FIN = "2000-01-01T00:00:00", "2024-12-31T23:00:00"
CAJA = 0.04          # grados alrededor del punto del tramo
DIR_COP = C.RAW / "copernicus"
DIR_RED = C.RAW / "redmar"

GRUPOS = {
    "oleaje": ("cmems_mod_ibi_wav_my_0.027deg_PT1H-i", ["VHM0", "VTPK", "VMDR"]),
    "viento": ("cmems_mod_ibi_phy-mflux_my_0.027deg_P1D-m", ["taum"]),   # tensión del viento, diaria
    "nivel": ("cmems_mod_ibi_phy-ssh_my_0.027deg_PT1H-m", ["zos"]),
    "corriente": ("cmems_mod_ibi_phy-cur_my_0.027deg_PT1H-m", ["uo", "vo"]),
}


def tramos() -> pd.DataFrame:
    f = C.RAW / "tramos.csv"
    if not f.exists():
        C.RAW.mkdir(parents=True, exist_ok=True)
        generar_tramos().to_csv(f, index=False)
    return pd.read_csv(f)


# ======================================================================= Copernicus
def _subset(dataset_id, variables, t, destino, caja=CAJA):
    import copernicusmarine as cm
    kw = dict(variables=variables,
              minimum_longitude=t.lon - caja, maximum_longitude=t.lon + caja,
              minimum_latitude=t.lat - caja, maximum_latitude=t.lat + caja,
              start_datetime=INICIO, end_datetime=FIN,
              output_directory=destino.parent, output_filename=destino.name,
              overwrite=True, disable_progress_bar=True)
    try:
        cm.subset(dataset_id=dataset_id, **kw)
    except Exception as e:
        # Si el reanálisis no llega a dic-2024, el tramo final está en el producto "interim" (myint)
        if "_my_" in dataset_id and ("time" in str(e).lower() or "date" in str(e).lower()):
            kw["end_datetime"] = None
            cm.subset(dataset_id=dataset_id, **kw)
            kw.update(start_datetime=None, end_datetime=FIN,
                      output_filename=destino.stem + "_int.nc")
            cm.subset(dataset_id=dataset_id.replace("_my_", "_myint_"), **kw)
        else:
            raise


def descargar_copernicus(grupos=None):
    tr = tramos()
    for g in grupos or GRUPOS:
        dataset_id, variables = GRUPOS[g]
        (DIR_COP / g).mkdir(parents=True, exist_ok=True)
        for t in tr.itertuples():
            destino = DIR_COP / g / f"{t.tramo}.nc"
            if destino.exists():
                continue
            print(f"Copernicus {g:9s} {t.tramo} ...", flush=True)
            try:
                _subset(dataset_id, variables, t, destino)
            except Exception as e:
                print(f"   ERROR {g} {t.tramo}: {e}\n   (revisa el dataset_id con "
                      f"`copernicusmarine describe --contains IBI_MULTIYEAR`)")


def _tiene_mar(f, var):
    """True si el archivo tiene al menos una celda con datos (no todo tierra)."""
    import xarray as xr
    try:
        with xr.open_dataset(f) as ds:
            da = ds[var]
            if "depth" in da.dims:
                da = da.isel(depth=0)
            return bool(da.isel(time=slice(0, 24)).notnull().any())
    except Exception:
        return False


def reparar_tramos_en_tierra(caja_amplia=0.12):
    """Los tramos cuyo punto cae en tierra quedan sin celdas de mar: se vuelven a bajar con una
    caja más amplia y luego se toma la celda de mar más cercana al punto."""
    tr = tramos()
    for g, (dataset_id, variables) in GRUPOS.items():
        for t in tr.itertuples():
            f = DIR_COP / g / f"{t.tramo}.nc"
            if f.exists() and not _tiene_mar(f, variables[0]):
                print(f"Copernicus {g:9s} {t.tramo}: sin celdas de mar, se amplía la caja a ±{caja_amplia}°", flush=True)
                try:
                    _subset(dataset_id, variables, t, f, caja=caja_amplia)
                except Exception as e:
                    print(f"   ERROR {g} {t.tramo}: {e}")


def _serie_celda(ds, var, lat, lon):
    """Elige la celda marina más cercana al tramo con datos válidos y devuelve su serie."""
    import xarray as xr
    da = ds[var]
    if "depth" in da.dims:
        da = da.isel(depth=0)
    valida = da.isel(time=slice(0, 48)).notnull().any("time")
    lat2, lon2 = xr.broadcast(da["latitude"], da["longitude"])
    d = np.hypot(lat2 - lat, (lon2 - lon) * np.cos(np.radians(lat))).where(valida)
    if d.isnull().all():
        return None
    idx = np.unravel_index(int(np.nanargmin(d.values)), d.shape)
    # se guarda la celda elegida y su distancia al punto del tramo (variable de calidad, Capítulo 1)
    _ULTIMA_CELDA.update(lat=float(lat2.values[idx]), lon=float(lon2.values[idx]),
                         dist_km=round(float(d.values[idx]) * 111.2, 2))
    return da.isel(latitude=idx[0], longitude=idx[1]).to_series()


_ULTIMA_CELDA = {}


def _abrir(g, tramo):
    import xarray as xr
    fs = sorted((DIR_COP / g).glob(f"{tramo}*.nc"))
    if not fs:
        return None
    return xr.open_mfdataset(fs, combine="by_coords") if len(fs) > 1 else xr.open_dataset(fs[0])


def procesar_copernicus():
    """Pasa las series horarias a diarias por tramo → data/raw/copernicus_diario.csv
    y registra la celda usada y su distancia al tramo → data/raw/calidad_celdas.csv"""
    filas, calidad = [], []
    for t in tramos().itertuples():
        partes = {}
        def anotar(grupo):
            if _ULTIMA_CELDA:
                calidad.append({"tramo": t.tramo, "grupo": grupo, **_ULTIMA_CELDA})
                _ULTIMA_CELDA.clear()
        ds = _abrir("oleaje", t.tramo)
        if ds is not None:
            hs = _serie_celda(ds, "VHM0", t.lat, t.lon)
            tp = _serie_celda(ds, "VTPK", t.lat, t.lon)
            anotar("oleaje")
            if hs is not None:
                partes["hs"] = hs.resample("D").max()
                partes["tp"] = tp.resample("D").mean()
        ds = _abrir("viento", t.tramo)
        if ds is not None:
            tau = _serie_celda(ds, "taum", t.lat, t.lon)
            anotar("viento")
            if tau is not None:
                # U10 ≈ sqrt(τ / (ρ_aire · Cd)), con ρ_aire = 1,225 kg/m³ y Cd = 1,3e-3 (media diaria)
                u10 = np.sqrt(tau.clip(lower=0) / (1.225 * 1.3e-3))
                partes["viento_cop"] = u10.resample("D").mean()
        ds = _abrir("nivel", t.tramo)
        if ds is not None:
            z = _serie_celda(ds, "zos", t.lat, t.lon)
            anotar("nivel")
            if z is not None:
                partes["nivel"] = z.resample("D").max()
                partes["nivel_medio"] = z.resample("D").mean()
        ds = _abrir("corriente", t.tramo)
        if ds is not None:
            u = _serie_celda(ds, "uo", t.lat, t.lon)
            v = _serie_celda(ds, "vo", t.lat, t.lon)
            anotar("corriente")
            if u is not None:
                partes["corriente"] = np.hypot(u, v).resample("D").mean()
        if partes:
            df = pd.DataFrame(partes)
            df.index = pd.to_datetime(df.index).normalize()
            df.index.name = "fecha"
            filas.append(df.reset_index().assign(tramo=t.tramo))
            print(f"  {t.tramo}: {', '.join(partes)}")
    if not filas:
        print("Sin archivos de Copernicus todavía: nada que procesar."); return
    out = pd.concat(filas, ignore_index=True)
    out.round({c: 4 for c in out.columns if c not in ("fecha", "tramo")}).to_csv(C.RAW / "copernicus_diario.csv", index=False)
    print(f"copernicus_diario.csv: {len(out):,} filas, {out.tramo.nunique()} tramos")
    cal = pd.DataFrame(calidad)
    cal.to_csv(C.RAW / "calidad_celdas.csv", index=False)
    print("Distancia celda-tramo (km) por grupo:\n", cal.groupby("grupo").dist_km.describe()[["mean", "max"]].round(1).to_string())


# ======================================================================= REDMAR
THREDDS = "https://opendap.puertos.es/thredds"
NS = {"t": "http://www.unidata.ucar.edu/namespaces/thredds/InvCatalog/v1.0",
      "x": "http://www.w3.org/1999/xlink"}


def _catalogo(url):
    raiz = ET.parse(urlopen(url, timeout=60)).getroot()
    refs = [urljoin(url, r.get("{%s}href" % NS["x"])) for r in raiz.iter("{%s}catalogRef" % NS["t"])]
    datos = [d.get("urlPath") for d in raiz.iter("{%s}dataset" % NS["t"]) if d.get("urlPath")]
    return refs, datos


def _meses_estacion(carpeta, anio_ini=2000, anio_fin=2024):
    """Devuelve [(anio, mes, url_catalogo_mes)] disponibles en el THREDDS."""
    anios, _ = _catalogo(f"{THREDDS}/catalog/{carpeta}/catalog.xml")
    out = []
    for url_anio in anios:
        anio = url_anio.rstrip("/").split("/")[-2]
        if not anio.isdigit() or not anio_ini <= int(anio) <= anio_fin:
            continue
        meses, _ = _catalogo(url_anio)
        for url_mes in meses:
            out.append((anio, url_mes.rstrip("/").split("/")[-2], url_mes))
    return out


def _get(url, intentos=3):
    import time
    for i in range(intentos):
        try:
            with urlopen(url, timeout=60) as r:
                return r.read().decode("utf-8", "replace")
        except Exception:
            if i == intentos - 1:
                raise
            time.sleep(2 * (i + 1))


def _leer_dia_ascii(url_path):
    """Lee un archivo diario por OPeNDAP en texto (sin librería netCDF), un dato por minuto,
    y devuelve medias horarias. Los corchetes del pedido van codificados: el servidor (Tomcat)
    rechaza los corchetes sin codificar."""
    base = f"{THREDDS}/dodsC/{url_path}"
    dds = _get(base + ".dds")
    import re
    m = re.search(r"TIME\[TIME = (\d+)\]", dds)
    if not m:
        return None
    n = int(m.group(1))
    if n < 2:
        return None
    paso = max(1, round(n / 1440))                 # ~1 dato por minuto
    rango = f"[0:{paso}:{n - 1}]"
    q = quote(f"TIME{rango},SLEV{rango}[0:1:0],SLEV_QC{rango}[0:1:0]", safe=",")
    txt = _get(f"{base}.ascii?{q}")
    bloques = txt.split("---------------------------------------------", 1)[1]
    def valores(nombre):
        seg = bloques.split(nombre + "[", 1)[1].split("\n\n", 1)[0]
        lineas = seg.split("\n")[1:]
        if nombre == "TIME":
            return np.array([float(x) for x in ",".join(lineas).split(",") if x.strip()])
        return np.array([float(l.split(",")[1]) for l in lineas if "," in l])
    t = valores("TIME"); z = valores("SLEV"); qc = valores("SLEV_QC")
    z = np.where(np.isin(qc, [1, 2, 8]) & (np.abs(z) < 50), z, np.nan)   # 1 bueno, 2 prob. bueno, 8 interpolado
    idx = pd.Timestamp("1950-01-01") + pd.to_timedelta(t, unit="D")
    return pd.Series(z, index=idx.round("s")).resample("h").mean()


def _leer_dia(url_path, local=False):
    """Lectura de un .nc4 ya descargado (requiere netCDF4). Para el servidor se usa _leer_dia_ascii."""
    import netCDF4
    with netCDF4.Dataset(url_path) as nc:
        tv = nc["TIME"]
        n = len(tv)
        if n < 2:
            return None
        dt_seg = float(tv[-1] - tv[0]) * 86400 / (n - 1)
        paso = max(1, int(round(60 / dt_seg))) if dt_seg > 0 else 1
        t = netCDF4.num2date(tv[::paso], tv.units, only_use_cftime_datetimes=False)
        z = np.ma.filled(nc["SLEV"][::paso, 0].astype(float), np.nan)
        if "SLEV_QC" in nc.variables:
            qc = np.ma.filled(nc["SLEV_QC"][::paso, 0], 9)
            z = np.where(np.isin(qc, [1, 2, 8]), z, np.nan)
    s = pd.Series(z, index=pd.to_datetime([str(x) for x in t]))
    return s.resample("h").mean()


def descargar_redmar(hilos=8, solo=None):
    """Descarga mes a mes (cada mes queda guardado; si se corta, retoma desde el último mes).
    `solo`: nombre de un mareógrafo para bajarlo aparte (permite correr varios en paralelo)."""
    for est, info in REDMAR.items():
        if solo and est.lower() != solo.lower():
            continue
        destino = DIR_RED / f"{est}.csv"
        if destino.exists():
            print(f"REDMAR {est}: ya descargado"); continue
        cache = DIR_RED / "meses" / est
        cache.mkdir(parents=True, exist_ok=True)
        meses = _meses_estacion(info["thredds"])
        print(f"REDMAR {est}: {len(meses)} meses disponibles", flush=True)
        for anio, mes, url_mes in meses:
            f_mes = cache / f"{anio}_{mes}.csv"
            if f_mes.exists() and f_mes.stat().st_size > 40:   # mes ya bajado con datos
                continue
            _, paths = _catalogo(url_mes)
            # solo el archivo diario principal (…_AAAAMMDD.nc4); desde 2018 el servidor agrega
            # variantes _analysis_2hz, _analysis_HM y _analysis_event que no se usan
            import re
            paths = [p for p in paths if re.search(r"_\d{8}\.nc4$", p)]
            series, errores = [], 0
            with ThreadPoolExecutor(hilos) as ex:
                for fut in as_completed([ex.submit(_leer_dia_ascii, p) for p in paths]):
                    try:
                        s_ = fut.result()
                        if s_ is not None:
                            series.append(s_)
                    except Exception:
                        errores += 1
            if errores == len(paths) and paths:
                print(f"   {est} {anio}-{mes}: todos los días fallaron, se reintentará en la próxima corrida", flush=True)
                continue
            h = (pd.concat(series).sort_index() if series else pd.Series(dtype=float)).rename("nivel")
            h.index.name = "fecha_hora"
            h.round(4).to_frame().to_csv(f_mes)
            print(f"   {est} {anio}-{mes}: {len(paths)} días, {int(h.notna().sum())} horas, errores {errores}", flush=True)
        partes = [pd.read_csv(f, parse_dates=["fecha_hora"], index_col="fecha_hora")
                  for f in sorted(cache.glob("*.csv"))]
        h = pd.concat(partes).sort_index()
        h = h[~h.index.duplicated()]
        h.to_csv(destino)
        print(f"   guardado {destino.name}: {int(h['nivel'].notna().sum()):,} horas con dato", flush=True)


def limpiar_saltos(h: pd.Series, umbral_m: float = 2.5) -> pd.Series:
    """Quita horas que se alejan más de `umbral_m` de la mediana móvil de 30 días.
    Ejemplo: Huelva el 26-nov-2007 (puesta en marcha) marca ~10-11 m cuando el resto del
    periodo oscila entre 3 y 7 m, señal de otra referencia vertical o de calibración."""
    med = h.rolling("30D", center=True, min_periods=24).median()
    return h[(h - med).abs() <= umbral_m]


def redmar_desde_carpeta(carpeta, estacion):
    """Alternativa si los .nc4 ya se bajaron a mano: python -m src.descarga redmar_local "<carpeta>" Huelva"""
    fs = sorted(Path(carpeta).rglob("*.nc4"))
    print(f"REDMAR {estacion}: {len(fs)} archivos locales")
    series = [s for s in (_leer_dia(str(f)) for f in fs) if s is not None]
    DIR_RED.mkdir(parents=True, exist_ok=True)
    h = pd.concat(series).sort_index()
    h = h[~h.index.duplicated()].rename("nivel").to_frame()
    h.index.name = "fecha_hora"
    h.round(4).to_csv(DIR_RED / f"{estacion}.csv")
    print(f"   guardado {estacion}.csv: {h['nivel'].notna().sum():,} horas con dato")


def procesar_redmar():
    filas = []
    for est in REDMAR:
        f = DIR_RED / f"{est}.csv"
        if f.exists():
            h = pd.read_csv(f, parse_dates=["fecha_hora"], index_col="fecha_hora")["nivel"].dropna()
            h = limpiar_saltos(h)
            d = h.resample("D").mean().dropna()
            # La señal SLEV de los archivos MIR2Z (radar, tiempo real) correlaciona -0,83 a -0,94 con el
            # nivel del reanálisis: crece cuando el mar baja (comportamiento de distancia sensor-agua).
            # Se invierte para expresarla como nivel; la validación usa anomalías, así que el cero no importa.
            filas.append(pd.DataFrame({"fecha": d.index, "estacion_redmar": est, "nivel": -d.values}))
    if filas:
        pd.concat(filas).round({"nivel": 4}).to_csv(C.RAW / "redmar_diario.csv", index=False)
        print("redmar_diario.csv listo")


if __name__ == "__main__":
    accion = sys.argv[1] if len(sys.argv) > 1 else "todo"
    if accion in ("copernicus", "todo"):
        descargar_copernicus()
        reparar_tramos_en_tierra()
    if accion in ("redmar", "todo"):
        descargar_redmar(solo=sys.argv[2] if accion == "redmar" and len(sys.argv) > 2 else None)
    if accion == "redmar_local":
        redmar_desde_carpeta(sys.argv[2], sys.argv[3])
    if accion in ("procesar", "todo"):
        procesar_copernicus()
        procesar_redmar()
