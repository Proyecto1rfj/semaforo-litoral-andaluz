"""Genera datos SINTÉTICOS con la misma forma que tendrán las descargas reales.

Sirve solo para que el código corra de punta a punta mientras llegan los datos de
SIMAR, REDMAR y Copernicus. Ningún resultado obtenido con estos datos se reporta.

Archivos que crea en data/raw/:
  tramos.csv              tramo, nombre, lat, lon, punto_simar, celda_copernicus, estacion_redmar
  simar_sintetico.csv     fecha, punto_simar, hs, tp, viento
  copernicus_sintetico.csv fecha, celda_copernicus, nivel, corriente
  redmar_sintetico.csv    fecha, estacion_redmar, nivel
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
import config as C

from src.tramos import N_TRAMOS, generar_tramos as _tramos


def generar(semilla: int = C.SEMILLA) -> None:
    rng = np.random.default_rng(semilla)
    C.RAW.mkdir(parents=True, exist_ok=True)
    tramos = _tramos()
    tramos.to_csv(C.RAW / "tramos.csv", index=False)

    fechas = pd.date_range(C.INICIO, C.FIN, freq="D")
    n_d, n_t = len(fechas), N_TRAMOS
    doy = fechas.dayofyear.values
    estacion = np.cos(2 * np.pi * (doy - 15) / 365.25)              # máximo en enero

    # Tormentosidad regional que varía año a año y trimestre a trimestre (proceso AR(1))
    trimestres = fechas.to_period("Q")
    tq = pd.factorize(trimestres)[0]
    reg = np.zeros(tq.max() + 1)
    for i in range(1, len(reg)):
        reg[i] = 0.6 * reg[i - 1] + rng.normal(0, 0.25)
    reg_d = reg[tq]

    # Exposición propia de cada tramo (fachadas abiertas más expuestas) + deriva lenta
    base = rng.normal(0, 0.25, n_t) + np.linspace(-0.1, 0.25, n_t)
    deriva = np.cumsum(rng.normal(0, 0.03, (tq.max() + 1, n_t)), axis=0)[tq]
    # Sensibilidad distinta de cada tramo a los temporales del suroeste
    sens = rng.uniform(0.6, 1.4, n_t)

    log_hs = (0.15 + 0.35 * estacion[:, None] + base[None, :] + deriva
              + sens[None, :] * reg_d[:, None] + rng.normal(0, 0.35, (n_d, n_t)))
    # Temporales puntuales
    temporal = rng.random((n_d, n_t)) < (0.02 + 0.02 * (estacion[:, None] > 0))
    log_hs += temporal * rng.gamma(2, 0.25, (n_d, n_t))
    hs = np.exp(log_hs)
    tp = 6 + 2.2 * np.sqrt(hs) + rng.normal(0, 0.8, (n_d, n_t))
    viento = 3 + 2.4 * hs + rng.normal(0, 1.2, (n_d, n_t))

    anios = (fechas.year.values - 2000)[:, None]
    marea_met = 0.08 * (hs - hs.mean()) + rng.normal(0, 0.05, (n_d, n_t))
    nivel = 1.9 + 0.003 * anios + 0.05 * estacion[:, None] + marea_met + rng.normal(0, 0.03, (n_d, n_t))
    corriente = np.clip(0.18 + 0.05 * base[None, :] + 0.03 * hs + rng.normal(0, 0.04, (n_d, n_t)), 0.01, None)

    # Vacíos de registro: días sueltos y algunos bloques largos (boyas fuera de servicio)
    falta = rng.random((n_d, n_t)) < 0.02
    for _ in range(25):
        j = rng.integers(n_t); i0 = rng.integers(n_d - 60)
        falta[i0:i0 + rng.integers(15, 60), j] = True

    def largo(mat, ids, col_id, col_val):
        d = pd.DataFrame(mat, index=fechas, columns=ids)
        d = d.stack().rename(col_val).reset_index()
        d.columns = ["fecha", col_id, col_val]
        return d

    simar = largo(np.where(falta, np.nan, hs), tramos.punto_simar, "punto_simar", "hs")
    simar["tp"] = np.where(falta, np.nan, tp).ravel()
    simar["viento"] = np.where(falta, np.nan, viento).ravel()
    simar = simar.dropna(subset=["hs"]).round({"hs": 3, "tp": 3, "viento": 3})
    simar.to_csv(C.RAW / "simar_sintetico.csv", index=False)

    cop = largo(nivel, tramos.celda_copernicus, "celda_copernicus", "nivel")
    cop["corriente"] = corriente.ravel()
    cop.round({"nivel": 4, "corriente": 4}).to_csv(C.RAW / "copernicus_sintetico.csv", index=False)

    # REDMAR: promedio de las celdas cercanas a cada mareógrafo + error de medida
    red = []
    for est, g in tramos.groupby("estacion_redmar"):
        cols = [tramos.index.get_loc(i) for i in g.index]
        red.append(pd.DataFrame({"fecha": fechas, "estacion_redmar": est,
                                 "nivel": nivel[:, cols].mean(1) + rng.normal(0, 0.04, n_d)}))
    pd.concat(red).round({"nivel": 4}).to_csv(C.RAW / "redmar_sintetico.csv", index=False)
    print(f"Datos sintéticos creados en {C.RAW} ({len(simar):,} filas SIMAR)")


if __name__ == "__main__":
    generar()
