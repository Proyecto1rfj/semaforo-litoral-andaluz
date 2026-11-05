"""Explicaciones SHAP del candidato LambdaMART (y de XGBoost como contraste) para el OE3.

El panel usa la persistencia (plan B), cuyo SHAP es trivial porque es lineal en los indicadores.
Aquí se explica al mejor candidato con los mismos hiperparámetros elegidos en validación:
  - modelo entrenado con 2000-2021 → explicado en la prueba 2022-2024
  - modelo entrenado con 2000-2024 → explicado en la prueba prospectiva 2025
Salidas:
  resultados/oe3_shap_importancia.csv   importancia media |SHAP| por indicador (t y t−1 sumados)
  resultados/oe3_shap_subidas.csv       importancia en los casos que suben a prioridad alta
  resultados/fig_shap_lambdamart.png    figura para el Capítulo II
Uso:  python -m src.analisis_shap
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.append(str(Path(__file__).resolve().parents[1]))
import config as C
from src import modelado as M

NOMBRES = {"hs_p95_n": "Oleaje", "nivel_p95_n": "Nivel del mar no astronómico", "viento_p95_n": "Viento",
           "corriente_media_n": "Corrientes", "dias_temporal_pleamar_n": "Temporal en pleamar viva",
           "dias_temporal_pleamar": "Temporal en pleamar viva", "dias_pleamar_viva_t1": "Pleamar viva prevista (t+1)"}


def grupo(f):
    if f.startswith("q_"):
        return "Trimestre del año"
    base = f.replace("_lag1", "")
    return NOMBRES.get(base, base)


def explicar(modelo, d, fondo):
    v = M.calcular_shap(modelo, d, fondo)
    v = v.abs()
    g = v.T.groupby(grupo).sum().T          # suma t y t−1 de cada indicador
    return v, g


if __name__ == "__main__":
    panel = pd.read_parquet(C.PROCESSED / "panel_ieecc.parquet")
    df = M.preparar(panel)
    tr = df[df.particion == "entrenamiento"]; va = df[df.particion == "validacion"]
    te = df[df.particion == "prueba"]; ps = df[(df.particion == "prospectiva") & df["clase_t1"].notna()]
    tv = pd.concat([tr, va])
    val = pd.read_csv(C.RESULTADOS / "oe3_validacion.csv")
    filas, subidas, figdat = [], [], {}
    for nombre in ["LambdaMART", "XGBoost"]:
        p = json.loads(val.set_index("modelo").loc[nombre, "hiperparametros"])
        params = M._fit(M._crear(nombre, p), tr, d_val=va).params        # recupera n_estimators como en ejecutar()
        for etiqueta, entreno, d in (("prueba 2022-2024", tv, te), ("prospectiva 2025", pd.concat([tv, te]), ps)):
            if not len(d):
                continue
            m = M._fit(M._crear(nombre, params), entreno)
            v, g = explicar(m, d, entreno)
            imp = (g.mean() / g.mean().sum()).sort_values(ascending=False)
            for k, x in imp.items():
                filas.append({"modelo": nombre, "bloque": etiqueta, "indicador": k, "peso_relativo": round(float(x), 3)})
            sube = ((d["clase_t1"] == 2) & (d["clase"] < 2)).values
            if sube.any():
                gi = (g[sube].mean() / g[sube].mean().sum()).sort_values(ascending=False)
                for k, x in gi.items():
                    subidas.append({"modelo": nombre, "bloque": etiqueta, "indicador": k, "peso_relativo": round(float(x), 3),
                                    "casos": int(sube.sum())})
            if nombre == "LambdaMART":
                figdat[etiqueta] = imp
            print(f"{nombre} · {etiqueta}:"); print((imp * 100).round(1).to_string())
    pd.DataFrame(filas).to_csv(C.RESULTADOS / "oe3_shap_importancia.csv", index=False)
    pd.DataFrame(subidas).to_csv(C.RESULTADOS / "oe3_shap_subidas.csv", index=False)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    t = pd.DataFrame(figdat).fillna(0) * 100
    t = t.loc[t.mean(axis=1).sort_values().index]
    fig, ax = plt.subplots(figsize=(8, 4.2), dpi=200)
    y = np.arange(len(t)); h = 0.38
    cols = list(t.columns)
    ax.barh(y + h / 2, t[cols[0]], h, color="#1e3a5f", label=cols[0])
    if len(cols) > 1:
        ax.barh(y - h / 2, t[cols[1]], h, color="#9fb7d3", label=cols[1])
    ax.set_yticks(y); ax.set_yticklabels(t.index, fontsize=9)
    ax.set_xlabel("Peso relativo en la explicación (%)", fontsize=9)
    ax.spines[["top", "right"]].set_visible(False); ax.legend(frameon=False, fontsize=8, loc="lower right")
    ax.tick_params(axis="x", labelsize=8)
    fig.tight_layout(); fig.savefig(C.RESULTADOS / "fig_shap_lambdamart.png", facecolor="white")
    print("Listo: resultados/oe3_shap_importancia.csv, oe3_shap_subidas.csv y fig_shap_lambdamart.png")
