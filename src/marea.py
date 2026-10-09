"""Nivel del mar no astronómico (sobreelevación meteorológica) por tramo.

El zos horario del reanálisis IBI incluye la marea astronómica, que en este litoral crece de
Tarifa hacia Huelva y termina dominando el máximo trimestral. Aquí se ajusta un análisis
armónico (UTide) a cada serie horaria con los años de entrenamiento (2000-2018), se predice la
marea para todo el periodo y se resta. Lo que queda es el residuo meteorológico: el que sube
con los temporales.

Salida: data/raw/nivel_no_astronomico.csv con fecha, tramo, nivel_nt (máximo diario del residuo)
y nivel_nt_medio (media diaria del residuo).

Uso:  python -m src.marea
"""
import warnings

import numpy as np
import pandas as pd

import config as C
from src import descarga as D

warnings.filterwarnings("ignore")
SALIDA = C.RAW / "nivel_no_astronomico.csv"
SALTO_MAX = 0.4   # m entre horas consecutivas


def residuo_meteorologico(z: pd.Series, lat: float) -> pd.Series:
    """Serie horaria de nivel → residuo sin marea astronómica (misma indexación)."""
    import utide
    z = z.astype(float)
    z = z - z.mean()
    t = z.index
    ent = (t.year >= C.ANIOS_TRAIN[0]) & (t.year <= C.ANIOS_TRAIN[1]) & z.notna().values
    coef = utide.solve(t[ent], z.values[ent], lat=lat, method="ols", conf_int="none",
                       trend=False, nodal=True, verbose=False)
    marea = utide.reconstruct(t, coef, verbose=False).h
    return pd.Series(z.values - marea, index=t)


def procesar(tramos_sel=None):
    filas, dias_malos = [], []
    for t in D.tramos().itertuples():
        if tramos_sel and t.tramo not in tramos_sel:
            continue
        ds = D._abrir("nivel", t.tramo)
        if ds is None:
            print(f"  {t.tramo}: sin archivo de nivel"); continue
        z = D._serie_celda(ds, "zos", t.lat, t.lon)
        D._ULTIMA_CELDA.clear()
        if z is None:
            print(f"  {t.tramo}: sin celda de mar"); continue
        z.index = pd.to_datetime(z.index)
        r = residuo_meteorologico(z, t.lat)
        var_marea = 1 - np.nanvar(r) / np.nanvar(z - z.mean())
        # Control de calidad: el residuo meteorológico cambia lento; un salto de más de SALTO_MAX
        # entre horas consecutivas indica horas desordenadas o corruptas en el reanálisis
        # (p. ej. 26-12-2007). Esos días quedan sin dato.
        malo = (r.diff().abs().resample("D").max() > SALTO_MAX)
        d = pd.DataFrame({"nivel_nt": r.resample("D").max(), "nivel_nt_medio": r.resample("D").mean()})
        d.loc[malo.reindex(d.index, fill_value=False).values] = np.nan
        dias_malos.append((t.tramo, int(malo.sum())))
        d.index = d.index.normalize(); d.index.name = "fecha"
        filas.append(d.reset_index().assign(tramo=t.tramo))
        print(f"  {t.tramo}: marea explica {var_marea:.1%} de la varianza; "
              f"residuo máx {np.nanmax(r):.2f} m", flush=True)
    out = pd.concat(filas, ignore_index=True)
    out.round({"nivel_nt": 4, "nivel_nt_medio": 4}).to_csv(SALIDA, index=False)
    print("Días descartados por saltos horarios:", {k: v for k, v in dias_malos if v})
    print(f"{SALIDA.name}: {len(out):,} filas, {out.tramo.nunique()} tramos")


if __name__ == "__main__":
    procesar()
