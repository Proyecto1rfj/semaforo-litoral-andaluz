"""Laboratorio v2: tratamiento astronómico completo (Capítulo 1, versión 2).

1. corrientes: se resta la corriente de marea (análisis armónico 2D de u y v con UTide, ajustado
   con 2000-2018) y se usa la rapidez media diaria del residuo → data/raw/corrientes_no_astronomicas.csv
2. prevista: marea astronómica prevista por tramo hasta 2025-T1 (máximo trimestral) →
   data/raw/marea_prevista_trimestral.csv. Se conoce de antemano, así que sirve para la alerta del
   trimestre siguiente sin fuga de información.
3. validar: residuo meteorológico de REDMAR (marea quitada con el mismo método) contra el residuo
   del reanálisis → resultados/validacion_residuo_redmar.csv

Uso:  python -m src.marea_v2 corrientes | prevista | validar
"""
import sys
import warnings

import numpy as np
import pandas as pd

import config as C
from src import descarga as D

warnings.filterwarnings("ignore")


def _entreno(t):
    return (t.year >= C.ANIOS_TRAIN[0]) & (t.year <= C.ANIOS_TRAIN[1])


def corrientes(tramos_sel=None):
    import utide
    filas, resumen = [], []
    for t in D.tramos().itertuples():
        if tramos_sel and t.tramo not in tramos_sel:
            continue
        ds = D._abrir("corriente", t.tramo)
        u = D._serie_celda(ds, "uo", t.lat, t.lon); v = D._serie_celda(ds, "vo", t.lat, t.lon)
        D._ULTIMA_CELDA.clear()
        u.index = pd.to_datetime(u.index); v.index = u.index
        ok = _entreno(u.index) & u.notna().values & v.notna().values
        coef = utide.solve(u.index[ok], u.values[ok], v.values[ok], lat=t.lat, method="ols",
                           conf_int="none", trend=False, nodal=True, verbose=False)
        rec = utide.reconstruct(u.index, coef, verbose=False)
        ur, vr = u.values - rec.u, v.values - rec.v
        vel_total = pd.Series(np.hypot(u.values, v.values), index=u.index)
        vel_res = pd.Series(np.hypot(ur, vr), index=u.index)
        d = pd.DataFrame({"corriente_nt": vel_res.resample("D").mean(),
                          "corriente_total": vel_total.resample("D").mean()})
        d.index.name = "fecha"
        filas.append(d.reset_index().assign(tramo=t.tramo))
        resumen.append({"tramo": t.tramo, "rapidez_total": vel_total.mean(), "rapidez_residuo": vel_res.mean(),
                        "pct_rapidez_por_marea_y_media": 1 - vel_res.mean() / vel_total.mean()})
        print(f"  {t.tramo}: rapidez media {vel_total.mean():.3f} → sin marea {vel_res.mean():.3f} m/s", flush=True)
    pd.concat(filas).round(4).to_csv(C.RAW / "corrientes_no_astronomicas.csv", index=False)
    r = pd.DataFrame(resumen).round(3)
    C.RESULTADOS.mkdir(exist_ok=True, parents=True)
    r.to_csv(C.RESULTADOS / "corrientes_aporte_marea.csv", index=False)
    print(r.describe().round(3).to_string())


def prevista():
    """Marea astronómica prevista (máximo trimestral) por tramo, 2000-T1 a 2025-T1."""
    import utide
    filas = []
    horas = pd.date_range("2000-01-01", "2025-03-31 23:00", freq="h")
    for t in D.tramos().itertuples():
        ds = D._abrir("nivel", t.tramo)
        z = D._serie_celda(ds, "zos", t.lat, t.lon); D._ULTIMA_CELDA.clear()
        z.index = pd.to_datetime(z.index); z = z - z.mean()
        ok = _entreno(z.index) & z.notna().values
        coef = utide.solve(z.index[ok], z.values[ok], lat=t.lat, method="ols", conf_int="none",
                           trend=False, nodal=True, verbose=False)
        h = pd.Series(utide.reconstruct(horas, coef, verbose=False).h, index=horas)
        q = h.groupby(h.index.to_period("Q")).max()
        filas.append(pd.DataFrame({"tramo": t.tramo, "trimestre": q.index.astype(str), "marea_max_prevista": q.values.round(3)}))
        print(f"  {t.tramo}: pleamar máx. prevista media {q.mean():.2f} m", flush=True)
    pd.concat(filas).to_csv(C.RAW / "marea_prevista_trimestral.csv", index=False)


def validar():
    """Residuo meteorológico: REDMAR contra el reanálisis (máximo y media diaria)."""
    import utide
    nt = pd.read_csv(C.RAW / "nivel_no_astronomico.csv", parse_dates=["fecha"])
    tr = D.tramos()[["tramo", "estacion_redmar"]]
    cop = nt.merge(tr, on="tramo").groupby(["estacion_redmar", "fecha"])[["nivel_nt", "nivel_nt_medio"]].mean()
    filas = []
    for est, info in __import__("src.tramos", fromlist=["REDMAR"]).REDMAR.items():
        h = pd.read_csv(C.RAW / "redmar" / f"{est}.csv", parse_dates=["fecha_hora"], index_col="fecha_hora")["nivel"]
        h = -h.astype(float)                       # la señal SLEV viene invertida (ver descarga.procesar_redmar)
        h = h[~h.index.duplicated()].asfreq("h")
        # limpieza: saltos frente a la mediana móvil de 30 días (mismo criterio que descarga.limpiar_saltos)
        med = h.rolling(24 * 30, center=True, min_periods=24 * 5).median()
        h[(h - med).abs() > 2.5] = np.nan
        h = h - h.mean()
        ok = (h.index.year <= C.ANIOS_TRAIN[1]) & h.notna().values
        coef = utide.solve(h.index[ok], h.values[ok], lat=info["lat"], method="ols", conf_int="none",
                           trend=False, nodal=True, verbose=False)
        r = pd.Series(h.values - utide.reconstruct(h.index, coef, verbose=False).h, index=h.index)
        malo = r.diff().abs().resample("D").max() > 0.4
        dmax, dmed = r.resample("D").max(), r.resample("D").mean()
        n_h = r.resample("D").count()
        ok_d = (n_h >= 20) & ~malo
        red = pd.DataFrame({"red_max": dmax[ok_d], "red_med": dmed[ok_d]})
        c = cop.loc[est]
        j = red.join(c, how="inner").dropna()
        a = lambda s: s - s.mean()
        # eventos: días sobre el percentil 99 del residuo del mareógrafo
        p99 = j.red_max.quantile(0.99)
        ev = j[j.red_max > p99]
        filas.append({"estacion": est, "dias": len(j),
                      "corr_residuo_max_diario": j.red_max.corr(j.nivel_nt),
                      "corr_residuo_medio_diario": j.red_med.corr(j.nivel_nt_medio),
                      "rmse_residuo_max_m": float(np.sqrt(((a(j.red_max) - a(j.nivel_nt)) ** 2).mean())),
                      "eventos_p99": len(ev),
                      "eventos_p99_tambien_p95_en_reanalisis": float((ev.nivel_nt > j.nivel_nt.quantile(0.95)).mean())})
        print(f"  {est}: {filas[-1]}", flush=True)
    out = pd.DataFrame(filas).round(3)
    C.RESULTADOS.mkdir(exist_ok=True, parents=True)
    out.to_csv(C.RESULTADOS / "validacion_residuo_redmar.csv", index=False)
    print(out.to_string(index=False))


if __name__ == "__main__":
    {"corrientes": corrientes, "prevista": prevista, "validar": validar}[sys.argv[1]]()
