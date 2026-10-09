"""OE2. Construir el IEECC por tramo y trimestre y analizar su sensibilidad (Capítulo 1).

1. Normalización: cada uno de los cuatro indicadores se lleva a 0-1 con mínimo y máximo
   calculados solo en el periodo de entrenamiento (2000-2018), para que la prueba no influya.
   Los valores fuera de ese rango se acotan a 0 y 1.
2. IEECC = suma ponderada de los cuatro indicadores normalizados. Caso base: pesos iguales.
   Alternativa: pesos de entropía (también con 2000-2018).
3. Clases: en cada trimestre los tramos se ordenan por IEECC y se dividen en terciles
   (alta, media, baja), es decir, según su posición frente al resto en ese trimestre.
4. Sensibilidad: pesos de entropía, cada peso al doble y a la mitad, y corte 25/50/25.
   En cada escenario se mide el % de pares tramo-trimestre que cambian de clase frente al
   caso base (meta Tabla 1: menos de 20 %; si se supera, se informa como limitación).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

sys.path.append(str(Path(__file__).resolve().parents[1]))
import config as C

IND = list(C.INDICADORES)
IND_N = [c + "_n" for c in IND]
META_CAMBIO = 20.0


def normalizar(panel: pd.DataFrame) -> pd.DataFrame:
    panel = panel.copy()
    train = panel[panel["anio"].between(*C.ANIOS_TRAIN)]
    for c in IND:
        lo, hi = train[c].min(), train[c].max()
        panel[c + "_n"] = ((panel[c] - lo) / (hi - lo)).clip(0, 1)
        faltan = panel[c + "_n"].isna().sum()
        if faltan:
            print(f"  {c}: {faltan} observaciones sin dato, se asigna el valor medio 0,5")
            panel[c + "_n"] = panel[c + "_n"].fillna(0.5)
    return panel


def pesos_iguales() -> dict:
    return {c: 1 / len(IND_N) for c in IND_N}


def pesos_entropia(panel: pd.DataFrame) -> dict:
    """Método de entropía: más peso a los indicadores que más diferencian a los tramos entre sí."""
    X = panel.loc[panel["anio"].between(*C.ANIOS_TRAIN), IND_N].astype(float) + 1e-9
    P = X / X.sum()
    E = -(P * np.log(P)).sum() / np.log(len(X))
    d = 1 - E
    return {c: float(v) for c, v in (d / d.sum()).items()}


def pesos_escalados(indicador: str, factor: float) -> dict:
    """Multiplica el peso de un indicador por `factor` y reparte el resto en partes iguales."""
    w = pesos_iguales()
    w[indicador] *= factor
    resto = (1 - w[indicador]) / (len(IND_N) - 1)
    return {c: (w[c] if c == indicador else resto) for c in IND_N}


def calcular_ieecc(panel: pd.DataFrame, pesos: dict, cortes=C.CORTES_TERCILES) -> pd.DataFrame:
    panel = panel.copy()
    panel["ieecc"] = sum(panel[c] * w for c, w in pesos.items())
    panel["clase"] = panel.groupby("trimestre")["ieecc"].transform(
        lambda s: pd.qcut(s.rank(method="first"), cortes, labels=False)).astype(int)
    return panel


def tasa_cambio_temporal(panel: pd.DataFrame) -> float:
    """% de tramos cuya clase cambia de un trimestre al siguiente (estabilidad temporal, informativa)."""
    sig = panel.sort_values(["tramo", "trimestre"]).groupby("tramo")["clase"].shift(-1)
    m = sig.notna()
    return float(100 * (panel.loc[m, "clase"] != sig[m]).mean())


def sensibilidad(panel: pd.DataFrame):
    base = calcular_ieecc(panel, pesos_iguales())
    escenarios = {"Pesos de entropía": (pesos_entropia(panel), C.CORTES_TERCILES)}
    nombres = {"hs_p95_n": "oleaje", "nivel_max_n": "nivel del mar",
               "viento_p95_n": "viento", "corriente_media_n": "corrientes"}
    for c in IND_N:
        escenarios[f"Peso de {nombres.get(c, c)} x2"] = (pesos_escalados(c, 2.0), C.CORTES_TERCILES)
        escenarios[f"Peso de {nombres.get(c, c)} x0,5"] = (pesos_escalados(c, 0.5), C.CORTES_TERCILES)
    escenarios["Corte 25/50/25"] = (pesos_iguales(), C.CORTES_ALTERNATIVOS)

    filas, cambios_tramo = [], []
    for nombre, (w, cortes) in escenarios.items():
        alt = calcular_ieecc(panel, w, cortes)
        cambia = base["clase"].values != alt["clase"].values
        rho = np.mean([spearmanr(base.loc[i, "ieecc"], alt.loc[i, "ieecc"])[0]
                       for i in base.groupby("trimestre").groups.values()])
        pct = 100 * cambia.mean()
        filas.append({"escenario": nombre, "pct_cambio_clase_vs_base": round(pct, 1),
                      "cumple_meta_<20%": pct < META_CAMBIO, "spearman_medio_ieecc": round(rho, 3)})
        cambios_tramo.append(pd.Series(cambia, index=base["tramo"]).groupby(level=0).mean().rename(nombre))
    tabla = pd.DataFrame(filas)
    # Tramos que más cambian de clase entre escenarios (los cercanos a los cortes)
    por_tramo = (100 * pd.concat(cambios_tramo, axis=1).mean(axis=1)).round(1).sort_values(ascending=False)
    return tabla, por_tramo.rename("pct_cambio_medio").to_frame()


def ejecutar() -> pd.DataFrame:
    panel = pd.read_parquet(C.PROCESSED / "panel_trimestral.parquet")
    panel = normalizar(panel)
    panel = calcular_ieecc(panel, pesos_iguales())
    panel.to_parquet(C.PROCESSED / "panel_ieecc.parquet")

    C.RESULTADOS.mkdir(parents=True, exist_ok=True)
    w = pd.DataFrame({"iguales": pesos_iguales(), "entropia": pesos_entropia(panel)}).round(3)
    sens, por_tramo = sensibilidad(panel)
    w.to_csv(C.RESULTADOS / "oe2_pesos.csv")
    sens.to_csv(C.RESULTADOS / "oe2_sensibilidad.csv", index=False)
    por_tramo.to_csv(C.RESULTADOS / "oe2_tramos_sensibles.csv")
    print("OE2 · Pesos\n", w.to_string())
    print("\nSensibilidad (meta Tabla 1: < 20 % de cambio de clase por escenario)\n", sens.to_string(index=False))
    print("\nTramos más sensibles (cercanos a los cortes):\n", por_tramo.head(5).to_string())
    print(f"\nEstabilidad temporal (informativa): {tasa_cambio_temporal(panel):.1f} % de tramos cambia de clase entre trimestres")
    return panel


if __name__ == "__main__":
    ejecutar()
