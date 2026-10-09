"""OE3. Evaluar modelos de clasificación y ordenamiento t → t+1 contra la persistencia.

Diseño (Capítulo 1):
  - Entradas: los cuatro indicadores normalizados del trimestre t, sus valores en t−1 y el
    trimestre del año. No se usa el identificador del tramo.
  - Objetivo: clase del IEECC en t+1 (0 baja, 1 media, 2 alta).
  - Partición por el trimestre objetivo: entrenamiento 2000-2018, validación 2019-2021, prueba 2022-2024.
  - Líneas base: persistencia (la clase y la posición de t se repiten) y clase mayoritaria.
  - Modelos: Random Forest, SVM (probabilidades con escalamiento de Platt) y XGBoost como
    referencia + LambdaMART en LightGBM (exploratorio). Hiperparámetros ajustados con el bloque de
    validación y parada temprana en XGBoost y LambdaMART.
  - Métricas: exactitud balanceada, F1 macro, matriz de confusión, sensibilidad y precisión de la
    clase alta, NDCG@10 y precisión en los primeros 10 tramos del ranking (más Spearman, informativa).
  - Se elige UN modelo con el bloque de validación (no con la prueba, para no contaminar la
    evaluación final). Si ninguno supera a la persistencia, la persistencia queda como
    referencia operativa del prototipo (plan B del OE3).
"""
import json
import sys
from itertools import product
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (balanced_accuracy_score, confusion_matrix, f1_score, ndcg_score,
                             precision_score, recall_score)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC
from xgboost import XGBClassifier

sys.path.append(str(Path(__file__).resolve().parents[1]))
import config as C
from src.ieecc import IND_N

# ---------------------------------------------------------------- datos
FEATURES = IND_N + [c + "_lag1" for c in IND_N] + ["q_1", "q_2", "q_3", "q_4"]


def preparar(panel: pd.DataFrame) -> pd.DataFrame:
    df = panel.sort_values(["tramo", "trimestre"]).copy()
    g = df.groupby("tramo")
    for c in IND_N:
        df[c + "_lag1"] = g[c].shift(1)
    for k in range(1, 5):
        df[f"q_{k}"] = (df["q"] == k).astype(int)
    df["clase_t1"] = g["clase"].shift(-1)
    df["ieecc_t1"] = g["ieecc"].shift(-1)
    df["trimestre_objetivo"] = (pd.PeriodIndex(df["trimestre"], freq="Q") + 1).astype(str)
    df["anio_objetivo"] = pd.PeriodIndex(df["trimestre_objetivo"], freq="Q").year
    df = df.dropna(subset=[c + "_lag1" for c in IND_N])

    def particion(a):
        if C.ANIOS_TRAIN[0] <= a <= C.ANIOS_TRAIN[1]:
            return "entrenamiento"
        if C.ANIOS_VALID[0] <= a <= C.ANIOS_VALID[1]:
            return "validacion"
        if C.ANIOS_TEST[0] <= a <= C.ANIOS_TEST[1]:
            return "prueba"
        return "pronostico"          # 2025-T1: trimestre siguiente al último dato
    df["particion"] = df["anio_objetivo"].map(particion)
    return df.sort_values(["trimestre", "tramo"]).reset_index(drop=True)


# ---------------------------------------------------------------- modelos
class Persistencia:
    nombre, tipo = "Persistencia", "base"
    def fit(self, X, y, **kw): return self
    def score(self, X): return X["ieecc"].values
    def clase(self, X): return None          # usa la clase de t (se resuelve en evaluar)


class Mayoritaria:
    nombre, tipo = "Clase mayoritaria", "base"
    def fit(self, X, y, **kw):
        self.c = int(pd.Series(y).mode()[0]); return self
    def score(self, X): return np.zeros(len(X))
    def clase(self, X): return np.full(len(X), self.c)


class Clasificador:
    tipo = "clasificador"
    def __init__(self, nombre, fabrica, params):
        self.nombre, self.fabrica, self.params = nombre, fabrica, dict(params)
    def fit(self, X, y, eval_data=None, **kw):
        if self.nombre == "XGBoost" and eval_data is not None and "n_estimators" not in self.params:
            Xv, yv = eval_data
            self.m = self.fabrica(n_estimators=1000, early_stopping_rounds=C.PARADA_TEMPRANA, **self.params)
            self.m.fit(X[FEATURES], y.astype(int), eval_set=[(Xv[FEATURES], yv.astype(int))], verbose=False)
            self.params["n_estimators"] = int(self.m.best_iteration) + 1   # se usa al reentrenar
        else:
            self.m = self.fabrica(**self.params).fit(X[FEATURES], y.astype(int))
        return self
    def proba(self, X): return self.m.predict_proba(X[FEATURES])
    def score(self, X): return self.proba(X)[:, 2]          # probabilidad de prioridad alta
    def clase(self, X): return self.proba(X).argmax(1)


class LambdaMART:
    """LambdaMART en LightGBM (Ke et al., 2017): cada trimestre es una consulta y los tramos se ordenan."""
    nombre, tipo = "LambdaMART", "ranker"
    def __init__(self, params): self.params = dict(params)
    def fit(self, X, y, grupos=None, eval_data=None):
        import lightgbm as lgb
        base = dict(objective="lambdarank", metric="ndcg", eval_at=[C.K_NDCG], random_state=C.SEMILLA,
                    verbose=-1, n_jobs=-1)
        if eval_data is not None and "n_estimators" not in self.params:
            Xv, yv, gv = eval_data
            self.m = lgb.LGBMRanker(n_estimators=1000, **base, **self.params)
            self.m.fit(X[FEATURES], y.astype(int), group=grupos,
                       eval_set=[(Xv[FEATURES], yv.astype(int))], eval_group=[gv],
                       callbacks=[lgb.early_stopping(C.PARADA_TEMPRANA, verbose=False)])
            self.params["n_estimators"] = int(self.m.best_iteration_ or self.m.n_estimators)
        else:
            self.m = lgb.LGBMRanker(**base, **self.params)
            self.m.fit(X[FEATURES], y.astype(int), group=grupos)
        return self
    def score(self, X): return self.m.predict(X[FEATURES])
    def clase(self, X): return None          # terciles del puntaje dentro del trimestre


def _rf(**p): return RandomForestClassifier(n_estimators=300, class_weight="balanced",
                                            random_state=C.SEMILLA, n_jobs=-1, **p)
def _svm(**p): return make_pipeline(StandardScaler(), CalibratedClassifierCV(
    SVC(class_weight="balanced", random_state=C.SEMILLA, **p), ensemble=False))
def _xgb(**p): return XGBClassifier(**{"objective": "multi:softprob", "n_estimators": 300, "learning_rate": 0.05,
                                      "subsample": 0.8, "colsample_bytree": 0.8, "random_state": C.SEMILLA, **p})

GRILLAS = {
    "Random Forest": (_rf, {"max_depth": [4, 8, None], "min_samples_leaf": [5, 20]}),
    "SVM": (_svm, {"C": [0.5, 1, 4], "gamma": ["scale", 0.05]}),
    "XGBoost": (_xgb, {"max_depth": [3, 5], "min_child_weight": [1, 5]}),
    "LambdaMART": (None, {"num_leaves": [7, 15], "min_child_samples": [20, 50], "learning_rate": [0.05]}),
}


def _combinaciones(grilla):
    claves = list(grilla)
    return [dict(zip(claves, v)) for v in product(*grilla.values())]


def _crear(nombre, params):
    if nombre == "LambdaMART":
        return LambdaMART(params)
    return Clasificador(nombre, GRILLAS[nombre][0], params)


def _grupos(d):
    return d.groupby("trimestre", sort=False).size().values   # d viene ordenado por trimestre


def _fit(modelo, d, d_val=None):
    """Entrena; si se entrega d_val, XGBoost y LambdaMART lo usan para la parada temprana."""
    if modelo.tipo == "ranker":
        ev = (d_val, d_val["clase_t1"], _grupos(d_val)) if d_val is not None else None
        return modelo.fit(d, d["clase_t1"], grupos=_grupos(d), eval_data=ev)
    if modelo.tipo == "clasificador":
        ev = (d_val, d_val["clase_t1"]) if d_val is not None else None
        return modelo.fit(d, d["clase_t1"], eval_data=ev)
    return modelo.fit(d, d["clase_t1"])


# ---------------------------------------------------------------- evaluación
def _clase_pred(modelo, d, score):
    c = modelo.clase(d)
    if c is not None:
        return c
    if isinstance(modelo, Persistencia):
        return d["clase"].values
    s = pd.Series(score, index=d.index)
    return s.groupby(d["trimestre"]).transform(
        lambda x: pd.qcut(x.rank(method="first"), C.CORTES_TERCILES, labels=False)).values


def evaluar(modelo, d, matrices=None, etiqueta="") -> dict:
    score = modelo.score(d)
    pred = _clase_pred(modelo, d, score)
    y = d["clase_t1"].astype(int).values
    ndcg, rho, top = [], [], []
    for _, idx in d.groupby("trimestre").indices.items():
        ndcg.append(ndcg_score([d["ieecc_t1"].values[idx]], [score[idx]], k=C.K_NDCG))
        orden = idx[np.argsort(-score[idx], kind="stable")][:C.K_TOP]
        top.append((y[orden] == 2).mean())             # precisión en los primeros tramos
        if np.std(score[idx]) > 0:
            rho.append(spearmanr(score[idx], d["ieecc_t1"].values[idx])[0])
    if matrices is not None:
        cm = confusion_matrix(y, pred, labels=[0, 1, 2])
        for i, real in enumerate(["baja", "media", "alta"]):
            for j, pr in enumerate(["baja", "media", "alta"]):
                matrices.append({"conjunto": etiqueta, "modelo": modelo.nombre, "real": real,
                                 "predicha": pr, "n": int(cm[i, j])})
    return {
        "modelo": modelo.nombre,
        "exactitud_balanceada": balanced_accuracy_score(y, pred),
        "f1_macro": f1_score(y, pred, average="macro"),
        "sensibilidad_alta": recall_score(y, pred, labels=[2], average="macro", zero_division=0),
        "precision_alta": precision_score(y, pred, labels=[2], average="macro", zero_division=0),
        f"ndcg@{C.K_NDCG}": np.mean(ndcg),
        f"precision@{C.K_TOP}": np.mean(top),
        "spearman_ranking": np.mean(rho) if rho else np.nan,
    }


# ---------------------------------------------------------------- explicación
def calcular_shap(modelo, d_explicar, d_fondo) -> pd.DataFrame | None:
    """Contribución de cada entrada al puntaje de prioridad alta (SHAP)."""
    import shap
    X = d_explicar[FEATURES]
    if isinstance(modelo, Persistencia):
        # La persistencia ordena por el IEECC de t, que es lineal en los indicadores normalizados.
        # Para una función lineal, el valor SHAP exacto de cada variable es peso × (valor − media de fondo).
        from src.ieecc import pesos_iguales
        w = pesos_iguales()
        vals = pd.DataFrame(0.0, index=d_explicar.index, columns=FEATURES)
        for c in IND_N:
            vals[c] = w[c] * (d_explicar[c] - d_fondo[c].mean())
        return vals
    if isinstance(modelo, Mayoritaria):
        return None
    if modelo.nombre == "SVM":
        fondo = shap.kmeans(d_fondo[FEATURES], 20)
        exp = shap.KernelExplainer(lambda z: modelo.m.predict_proba(pd.DataFrame(z, columns=FEATURES))[:, 2], fondo)
        vals = exp.shap_values(X, nsamples=150, silent=True)
    else:
        vals = shap.TreeExplainer(modelo.m).shap_values(X)
        vals = np.asarray(vals)
        if vals.ndim == 3:                       # multiclase: (n, f, clases) → clase alta
            vals = vals[:, :, 2] if vals.shape[2] == 3 else vals[2]
    return pd.DataFrame(vals, columns=FEATURES, index=d_explicar.index)


def analizar_cambios(p: pd.DataFrame) -> pd.DataFrame:
    """Desempeño solo en los pares tramo-trimestre cuya clase cambia de t a t+1.
    La persistencia falla todos esos casos por definición; lo que un modelo acierte ahí es su aporte."""
    p = p.dropna(subset=["clase_t1"]).copy()
    p["cambia"] = p["clase"] != p["clase_t1"]
    p["acierto"] = p["clase_pred"] == p["clase_t1"]
    p["sube_a_alta"] = (p["clase_t1"] == 2) & (p["clase"] < 2)
    p["sale_de_alta"] = (p["clase"] == 2) & (p["clase_t1"] < 2)
    filas = []
    for m, g in p.groupby("modelo", sort=False):
        c = g[g.cambia]
        sube, sale = g[g.sube_a_alta], g[g.sale_de_alta]
        filas.append({
            "modelo": m, "casos_con_cambio": len(c),
            "acierto_en_cambios": c.acierto.mean(),
            "detecta_subida_a_alta": (sube.clase_pred == 2).mean() if len(sube) else np.nan,
            "detecta_salida_de_alta": (sale.clase_pred < 2).mean() if len(sale) else np.nan,
            "acierto_sin_cambio": g[~g.cambia].acierto.mean(),
        })
    return pd.DataFrame(filas).round(3)


# ---------------------------------------------------------------- flujo completo
def ejecutar():
    panel = pd.read_parquet(C.PROCESSED / "panel_ieecc.parquet")
    df = preparar(panel)
    tr = df[df.particion == "entrenamiento"]
    va = df[df.particion == "validacion"]
    te = df[df.particion == "prueba"]
    tv = pd.concat([tr, va])
    pr = df[df.particion == "pronostico"]
    print(f"OE3 · filas entrenamiento {len(tr)}, validación {len(va)}, prueba {len(te)}, pronóstico {len(pr)}")

    # 1. Ajuste de hiperparámetros en validación
    mejores, filas_val = {}, []
    for nombre, (_, grilla) in GRILLAS.items():
        res = []
        for p in _combinaciones(grilla):
            m = _fit(_crear(nombre, p), tr, d_val=va)
            r = evaluar(m, va)
            res.append((r[f"ndcg@{C.K_NDCG}"], r["sensibilidad_alta"], m.params, r))
        best = max(res, key=lambda x: (x[0], x[1]))
        mejores[nombre] = best[2]
        filas_val.append({**best[3], "hiperparametros": json.dumps(best[2])})
        print(f"  {nombre:14s} NDCG@{C.K_NDCG} val = {best[0]:.3f}  {best[2]}")
    for base in (Persistencia(), Mayoritaria()):
        filas_val.append({**evaluar(_fit(base, tr), va), "hiperparametros": ""})
    val = pd.DataFrame(filas_val).round(3)

    # 2. Selección (plan B si nadie supera a la persistencia)
    ndcg_col = f"ndcg@{C.K_NDCG}"
    cand = val[~val.modelo.isin(["Persistencia", "Clase mayoritaria"])].sort_values(
        [ndcg_col, "sensibilidad_alta"], ascending=False).iloc[0]
    ref = val.loc[val.modelo == "Persistencia", ndcg_col].iloc[0]
    elegido = cand.modelo if cand[ndcg_col] > ref else "Persistencia"

    # 3. Reentrenar con 2000-2021 y evaluar todos en prueba (2022-2024)
    def nuevo(nombre):
        if nombre == "Persistencia": return Persistencia()
        if nombre == "Clase mayoritaria": return Mayoritaria()
        return _crear(nombre, mejores[nombre])
    filas_te, modelos_tv, matrices, pred_todos = [], {}, [], []
    for nombre in list(GRILLAS) + ["Persistencia", "Clase mayoritaria"]:
        m = _fit(nuevo(nombre), tv)
        modelos_tv[nombre] = m
        filas_te.append(evaluar(m, te, matrices, "prueba 2022-2024"))
        o = te[["tramo", "trimestre_objetivo", "clase", "clase_t1"]].copy()
        o["modelo"] = nombre
        o["clase_pred"] = _clase_pred(m, te, m.score(te))
        pred_todos.append(o)
    prueba = pd.DataFrame(filas_te).round(3)
    cambios = analizar_cambios(pd.concat(pred_todos))
    # Metas de la Tabla 1 (OE3): superar a la persistencia en NDCG y en sensibilidad de la clase alta
    pers = prueba.set_index("modelo").loc["Persistencia"]
    prueba["supera_persistencia_ndcg_y_sens"] = ((prueba[f"ndcg@{C.K_NDCG}"] > pers[f"ndcg@{C.K_NDCG}"])
                                                 & (prueba["sensibilidad_alta"] > pers["sensibilidad_alta"]))

    # 4. Predicciones para el panel: prueba (modelo 2000-2021) + pronóstico 2025-T1 (modelo con todo)
    m_final = modelos_tv[elegido]
    m_todo = _fit(nuevo(elegido), pd.concat([tv, te]))
    salidas = []
    for d, m in ((te, m_final), (pr, m_todo)):
        o = d[["tramo", "nombre", "lat", "lon", "trimestre", "trimestre_objetivo", "particion",
               "ieecc", "clase", "clase_t1", "ieecc_t1"]].copy()
        o["puntaje"] = m.score(d)
        o["clase_pred"] = _clase_pred(m, d, o["puntaje"].values)
        if isinstance(m, Clasificador):
            p = m.proba(d)
            o[["prob_baja", "prob_media", "prob_alta"]] = p
        o["ranking"] = o.groupby("trimestre_objetivo")["puntaje"].rank(ascending=False, method="first").astype(int)
        salidas.append(o)
    pred = pd.concat(salidas)

    sh = [calcular_shap(m_final, te, tr), calcular_shap(m_todo, pr, tv)]
    C.RESULTADOS.mkdir(parents=True, exist_ok=True)
    (C.RESULTADOS / "shap.parquet").unlink(missing_ok=True)   # nunca dejar explicaciones de una corrida anterior
    if sh[0] is not None:
        shap_df = pd.concat(sh)
        shap_df[["tramo", "trimestre_objetivo"]] = pred[["tramo", "trimestre_objetivo"]].values
        shap_df.to_parquet(C.RESULTADOS / "shap.parquet")

    val.to_csv(C.RESULTADOS / "oe3_validacion.csv", index=False)
    cambios.to_csv(C.RESULTADOS / "oe3_cambios_clase.csv", index=False)
    pd.concat(pred_todos).to_parquet(C.RESULTADOS / "predicciones_prueba_todos.parquet")
    prueba.to_csv(C.RESULTADOS / "oe3_prueba.csv", index=False)
    pd.DataFrame(matrices).to_csv(C.RESULTADOS / "oe3_matrices_confusion.csv", index=False)
    pred.to_parquet(C.RESULTADOS / "predicciones.parquet")
    joblib.dump(m_todo, C.RESULTADOS / "modelo_elegido.joblib")
    info = {"modelo_elegido": elegido, "hiperparametros": mejores.get(elegido, {}),
            "ndcg_val_candidato": float(cand[ndcg_col]), "ndcg_val_persistencia": float(ref),
            "plan_b_activado": elegido == "Persistencia", "features": FEATURES}
    (C.RESULTADOS / "modelo_elegido.json").write_text(json.dumps(info, indent=2, ensure_ascii=False))

    print("\nValidación (2019-2021)\n", val.drop(columns="hiperparametros").to_string(index=False))
    print("\nPrueba (2022-2024)\n", prueba.to_string(index=False))
    print("\nTramos que cambian de clase en t+1 (prueba; matriz de riesgos del Capítulo 1)\n",
          cambios.to_string(index=False))
    print(f"\nModelo elegido para el panel: {elegido}"
          + ("  (plan B: ningún modelo superó a la persistencia)" if elegido == "Persistencia" else ""))
    return val, prueba, pred


if __name__ == "__main__":
    ejecutar()
