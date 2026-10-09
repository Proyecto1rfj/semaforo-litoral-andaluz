"""OE1. Integrar las series hidroclimáticas en un panel tramo × trimestre (2000 a 2024).

Pasos:
  1. Leer cada fuente (hoy CSV sintéticos; con datos reales se cambian solo los lectores).
  2. Unir cada tramo con su punto SIMAR y su celda Copernicus (tabla data/raw/tramos.csv).
  3. Agregar de diario/horario a trimestre y medir la cobertura (meta ≥90 %).
  4. Validar el nivel del mar de Copernicus contra los mareógrafos REDMAR.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
import config as C


# ---------- 1. Lectores ----------
# Cada lector devuelve series DIARIAS por tramo. En modo "real" salen de src/descarga.py;
# en modo "sintetico", de los CSV de prueba. El resto del flujo no cambia.

def leer_tramos() -> pd.DataFrame:
    return pd.read_csv(C.RAW / "tramos.csv")


def _leer_simar_portus() -> pd.DataFrame | None:
    """Archivos SIMAR bajados a mano desde Portus (texto separado por tabulaciones, -9999.9 = vacío).
    Cada archivo debe llevar en el nombre el código que figura en tramos.csv (columna punto_simar)."""
    carpeta = C.RAW / "simar"
    archivos = sorted(carpeta.glob("*.txt")) + sorted(carpeta.glob("*.csv")) if carpeta.exists() else []
    if not archivos:
        return None
    tramos = leer_tramos()
    filas = []
    for f in archivos:
        cod = next((c for c in tramos.punto_simar.astype(str) if c in f.name), None)
        if cod is None:
            print(f"  SIMAR: {f.name} no coincide con ningún punto_simar de tramos.csv"); continue
        df = pd.read_csv(f, sep=r"\t|\s{2,}", engine="python", comment="#").replace(-9999.9, np.nan)
        col = {c.lower().replace(" ", ""): c for c in df.columns}
        fecha = pd.to_datetime(dict(year=df[col.get("aa", col.get("año", "AA"))], month=df[col.get("mm", "MM")],
                                    day=df[col.get("dd", "DD")], hour=df[col.get("hh", "HH")]), errors="coerce")
        hs = next((df[c] for k, c in col.items() if k.startswith("hm0")), None)
        tp = next((df[c] for k, c in col.items() if k.startswith("tp")), None)
        vv = next((df[c] for k, c in col.items() if k.startswith("velv")), None)
        d = pd.DataFrame({"fecha": fecha, "hs": hs, "tp": tp, "viento": vv}).dropna(subset=["fecha"])
        d = d.set_index("fecha").resample("D").agg({"hs": "max", "tp": "mean", "viento": "max"})
        for t in tramos.loc[tramos.punto_simar.astype(str) == cod, "tramo"]:
            filas.append(d.reset_index().assign(tramo=t))
    return pd.concat(filas, ignore_index=True) if filas else None


def leer_oleaje_viento() -> pd.DataFrame:
    """fecha, tramo, hs (máx. diario, m), tp (s), viento (máx. diario, m/s).
    Real: SIMAR si están los archivos de Portus; si no, oleaje del reanálisis IBI de Copernicus
    y viento aproximado desde la tensión del viento del mismo modelo."""
    if C.MODO == "sintetico":
        tr = leer_tramos()[["tramo", "punto_simar"]]
        d = pd.read_csv(C.RAW / "simar_sintetico.csv", parse_dates=["fecha"])
        return d.merge(tr, on="punto_simar").drop(columns="punto_simar")
    d = pd.read_csv(C.RAW / "copernicus_diario.csv", parse_dates=["fecha"])
    d = d.rename(columns={"viento_cop": "viento"})[["fecha", "tramo", "hs", "tp", "viento"]]
    d["fuente"] = "Copernicus IBI"
    simar = _leer_simar_portus()
    if simar is not None:          # SIMAR reemplaza a Copernicus en los tramos que lo tengan
        d = pd.concat([d[~d.tramo.isin(simar.tramo.unique())], simar.assign(fuente="SIMAR")])
        print("  Oleaje y viento por fuente:", d.groupby("fuente").tramo.nunique().to_dict())
    return d


def leer_nivel_corriente() -> pd.DataFrame:
    """fecha, tramo, nivel (máx. diario), nivel_medio, corriente (media diaria, m/s)."""
    if C.MODO == "sintetico":
        tr = leer_tramos()[["tramo", "celda_copernicus"]]
        d = pd.read_csv(C.RAW / "copernicus_sintetico.csv", parse_dates=["fecha"])
        d = d.merge(tr, on="celda_copernicus").drop(columns="celda_copernicus")
        return d.assign(nivel_medio=d["nivel"])
    d = pd.read_csv(C.RAW / "copernicus_diario.csv", parse_dates=["fecha"])
    return d[["fecha", "tramo", "nivel", "nivel_medio", "corriente"]]


def leer_redmar() -> pd.DataFrame:
    """fecha, estacion_redmar, nivel (media diaria)."""
    f = C.RAW / ("redmar_sintetico.csv" if C.MODO == "sintetico" else "redmar_diario.csv")
    return pd.read_csv(f, parse_dates=["fecha"]) if f.exists() else pd.DataFrame()


# ---------- 2 y 3. Panel trimestral ----------
def _p95(s):
    return s.quantile(0.95)


def construir_panel() -> pd.DataFrame:
    tramos = leer_tramos()
    simar = leer_oleaje_viento()
    cop = leer_nivel_corriente()
    simar = simar[simar["fecha"].between(C.INICIO, C.FIN)].copy()
    cop = cop[cop["fecha"].between(C.INICIO, C.FIN)].copy()
    for df in (simar, cop):
        df["trimestre"] = df["fecha"].dt.to_period("Q")

    umbral = C.UMBRAL_TEMPORAL_HS
    if umbral is None:   # calibrado con el periodo de entrenamiento, para no usar información futura
        ent = simar[simar["fecha"].dt.year.between(*C.ANIOS_TRAIN)]
        umbral = float(ent["hs"].quantile(C.PERCENTIL_TEMPORAL))
    print(f"  Umbral de temporal (Hs): {umbral:.2f} m")
    s = simar.groupby(["tramo", "trimestre"]).agg(
        hs_p95=("hs", _p95),
        dias_temporal=("hs", lambda x: int((x > umbral).sum())),
        viento_p95=("viento", _p95),
        dias_con_dato=("hs", "count"),
    )
    c = cop.groupby(["tramo", "trimestre"]).agg(
        nivel_max=("nivel", "max"),
        corriente_media=("corriente", "mean"),
    )
    panel = s.join(c, how="outer").reset_index()

    # Cobertura: días con dato SIMAR / días del trimestre
    dias_trim = panel["trimestre"].apply(lambda p: (p.end_time - p.start_time).days + 1)
    panel["cobertura"] = (panel["dias_con_dato"] / dias_trim).round(3)
    panel["cobertura_ok"] = panel["cobertura"] >= C.COBERTURA_MINIMA

    # dias_temporal se escala a la cobertura para no castigar trimestres con vacíos
    panel["dias_temporal"] = (panel["dias_temporal"] / panel["cobertura"]).round(1)

    panel["anio"] = panel["trimestre"].dt.year
    panel["q"] = panel["trimestre"].dt.quarter
    panel = panel.merge(tramos[["tramo", "nombre", "lat", "lon"]], on="tramo")
    f_cal = C.RAW / "calidad_celdas.csv"
    if C.MODO == "real" and f_cal.exists():   # distancia celda-tramo como variable de calidad
        cal = pd.read_csv(f_cal).groupby("tramo").dist_km.max().rename("dist_celda_max_km")
        panel = panel.merge(cal, on="tramo", how="left")
    return panel.sort_values(["tramo", "trimestre"]).reset_index(drop=True)


def resumen_cobertura(panel: pd.DataFrame) -> pd.Series:
    return pd.Series({
        "tramos": panel["tramo"].nunique(),
        "trimestres": panel["trimestre"].nunique(),
        "observaciones": len(panel),
        "cobertura_media": panel["cobertura"].mean().round(3),
        "pct_obs_con_cobertura_ok": (100 * panel["cobertura_ok"].mean()).round(1),
    })


# ---------- 4. Validación del nivel del mar ----------
def validar_nivel_redmar() -> pd.DataFrame:
    """Compara el nivel medio diario del reanálisis (celdas asociadas a cada mareógrafo) con REDMAR.
    Se comparan anomalías (cada serie menos su media), porque el modelo y el mareógrafo usan
    referencias verticales distintas."""
    red = leer_redmar()
    if red.empty:
        return pd.DataFrame({"aviso": ["Sin datos REDMAR"]})
    tramos = leer_tramos()
    cop = leer_nivel_corriente().merge(tramos[["tramo", "estacion_redmar"]], on="tramo")
    cop = cop.groupby(["fecha", "estacion_redmar"])["nivel_medio"].mean().rename("nivel_cop")
    red = red.set_index(["fecha", "estacion_redmar"])["nivel"].rename("nivel_redmar")
    m = pd.concat([cop, red], axis=1).dropna().reset_index()
    def met(g):
        a = g.nivel_cop - g.nivel_cop.mean(); b = g.nivel_redmar - g.nivel_redmar.mean()
        return pd.Series({"n_dias": len(g), "correlacion": round(np.corrcoef(a, b)[0, 1], 3),
                          "rmse_anomalia_m": round(float(np.sqrt(((a - b) ** 2).mean())), 4)})
    return m.groupby("estacion_redmar").apply(met, include_groups=False)


def ejecutar() -> pd.DataFrame:
    C.PROCESSED.mkdir(parents=True, exist_ok=True)
    panel = construir_panel()
    panel.assign(trimestre=panel["trimestre"].astype(str)).to_parquet(C.PROCESSED / "panel_trimestral.parquet")
    print(f"OE1 · Panel trimestral (datos {C.MODO})\n", resumen_cobertura(panel).to_string())
    print("\nValidación nivel del mar vs REDMAR\n", validar_nivel_redmar().to_string())
    return panel


if __name__ == "__main__":
    ejecutar()
