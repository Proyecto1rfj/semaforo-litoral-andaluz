"""Análisis que agrega el Capítulo 1 versión 3.

1. Intervalos de confianza del 95 % por remuestreo en bloques de trimestres (prueba 2022-2024),
   para cada modelo y para su diferencia con la persistencia → resultados/oe3_intervalos.csv
2. Tendencias 2000-2024 por tramo e indicador (Mann-Kendall y pendiente de Sen, medias anuales)
   → resultados/oe2_tendencias.csv
3. Alerta absoluta del panel: temporal en t (algún día con Hs sobre el umbral) y mareas vivas de
   gran amplitud previstas para t+1 (pleamar máxima sobre el percentil 75 del propio tramo en
   2000-2018) → resultados/oe4_alerta.csv

Uso:  python -m src.analisis  (también lo corre ejecutar_todo.py)
"""
import numpy as np
import pandas as pd
from scipy.stats import kendalltau, theilslopes
from sklearn.metrics import balanced_accuracy_score, ndcg_score

import config as C

B = 2000
RNG = np.random.default_rng(C.SEMILLA)


def _metricas(g):
    y, p = g["clase_t1"].astype(int), g["clase_pred"].astype(int)
    alta = y == 2
    nd = [ndcg_score([q["ieecc_t1"].values], [q["puntaje"].values], k=C.K_NDCG)
          for _, q in g.groupby("trimestre_objetivo")]
    cam = g[g["clase"] != g["clase_t1"]]
    return {"exactitud_balanceada": balanced_accuracy_score(y, p),
            "sensibilidad_alta": (p[alta] == 2).mean(),
            f"ndcg@{C.K_NDCG}": float(np.mean(nd)),
            "acierto_en_cambios": (cam["clase_pred"] == cam["clase_t1"]).mean() if len(cam) else np.nan}


def intervalos():
    p = pd.read_parquet(C.RESULTADOS / "predicciones_prueba_todos.parquet").dropna(subset=["clase_t1"])
    p = p[p.modelo != "Clase mayoritaria"]
    trims = np.array(sorted(p.trimestre_objetivo.unique()))
    por_q = {(m, q): g for (m, q), g in p.groupby(["modelo", "trimestre_objetivo"])}
    modelos = list(dict.fromkeys(p.modelo))
    base = {m: _metricas(p[p.modelo == m]) for m in modelos}
    boot = {m: [] for m in modelos}
    for _ in range(B):
        muestra = RNG.choice(trims, size=len(trims), replace=True)
        for m in modelos:
            g = pd.concat([por_q[(m, q)].assign(trimestre_objetivo=f"{q}_{i}") for i, q in enumerate(muestra)])
            boot[m].append(_metricas(g))
    filas = []
    for m in modelos:
        bm = pd.DataFrame(boot[m]); bp = pd.DataFrame(boot["Persistencia"])
        for k in base[m]:
            dif = bm[k] - bp[k]
            filas.append({"modelo": m, "metrica": k, "valor": base[m][k],
                          "ic95_inf": bm[k].quantile(.025), "ic95_sup": bm[k].quantile(.975),
                          "dif_vs_persistencia": base[m][k] - base["Persistencia"][k],
                          "dif_ic95_inf": dif.quantile(.025), "dif_ic95_sup": dif.quantile(.975),
                          "diferencia_significativa": (dif.quantile(.025) > 0) or (dif.quantile(.975) < 0)})
    out = pd.DataFrame(filas)
    out.round(3).to_csv(C.RESULTADOS / "oe3_intervalos.csv", index=False)
    return out


def tendencias():
    panel = pd.read_parquet(C.PROCESSED / "panel_ieecc.parquet")
    filas = []
    for (t, ind), g in panel.melt(id_vars=["tramo", "anio"], value_vars=list(C.INDICADORES)).groupby(["tramo", "variable"]):
        a = g.groupby("anio")["value"].mean()
        tau, pv = kendalltau(a.index, a.values)
        pend = theilslopes(a.values, a.index)[0]
        filas.append({"tramo": t, "indicador": ind, "tau": tau, "p_valor": pv,
                      "pendiente_sen_por_decada": pend * 10, "significativa": pv < 0.05})
    out = pd.DataFrame(filas)
    out.round(4).to_csv(C.RESULTADOS / "oe2_tendencias.csv", index=False)
    return out


def alerta():
    """Alerta absoluta para el trimestre siguiente, con lo que se sabe de antemano:
    - mareas vivas: pleamar máxima prevista en t+1 sobre el percentil 75 del mismo trimestre del año
      en 2000-2018 para ese tramo (la marea astronómica se conoce con certeza);
    - estación de temporales: en 2000-2018, ese tramo tuvo al menos un día de temporal en al menos
      la mitad de los años para ese trimestre del año (probabilidad climatológica).
    alta = ambas señales; media = una; sin alerta = ninguna. El temporal observado en t se informa aparte."""
    panel = pd.read_parquet(C.PROCESSED / "panel_ieecc.parquet")[["tramo", "trimestre", "anio", "q", "dias_temporal"]]
    panel["trimestre"] = panel["trimestre"].astype(str)
    ent = panel[panel.anio.between(*C.ANIOS_TRAIN)]
    prob = (ent.assign(t=ent.dias_temporal > 0).groupby(["tramo", "q"]).t.mean().rename("prob_temporal_clim").reset_index())
    mp = pd.read_csv(C.RAW / "marea_prevista_trimestral.csv")
    per = pd.PeriodIndex(mp.trimestre, freq="Q"); mp["q"] = per.quarter; mp["anio"] = per.year
    p75 = mp[mp.anio.between(*C.ANIOS_TRAIN)].groupby(["tramo", "q"]).marea_max_prevista.quantile(0.75).rename("p75").reset_index()
    mp = mp.merge(p75, on=["tramo", "q"])
    mp["mareas_vivas"] = mp.marea_max_prevista > mp.p75
    mp = mp.merge(prob, on=["tramo", "q"])
    mp["estacion_temporales"] = mp.prob_temporal_clim >= 0.5
    mp["alerta"] = np.select([mp.mareas_vivas & mp.estacion_temporales, mp.mareas_vivas | mp.estacion_temporales],
                             ["alta", "media"], "sin alerta")
    obs = panel.assign(temporal_observado=panel.dias_temporal > 0)[["tramo", "trimestre", "temporal_observado"]]
    a = mp.rename(columns={"trimestre": "trimestre_objetivo"}).merge(
        obs.rename(columns={"trimestre": "trimestre_objetivo"}), on=["tramo", "trimestre_objetivo"], how="left")
    a.to_csv(C.RESULTADOS / "oe4_alerta.csv", index=False)
    # verificación 2022-2024: ¿la alerta coincide con temporales observados en t+1?
    pr = a[a.anio.between(*C.ANIOS_TEST)]
    print("Prueba 2022-2024, % de trimestres con temporal observado según alerta:",
          pr.groupby("alerta").temporal_observado.mean().round(2).to_dict())
    return a


def ejecutar():
    i = intervalos()
    print("\nIntervalos de confianza 95 % (prueba 2022-2024, bootstrap por trimestres)")
    print(i.round(3).to_string(index=False))
    t = tendencias()
    print("\nTendencias 2000-2024: tramos con tendencia significativa (p<0,05) y pendiente de Sen mediana por década")
    print(t.groupby("indicador").agg(tramos_signif=("significativa", "sum"), pendiente_mediana=("pendiente_sen_por_decada", "median")).round(4).to_string())
    a = alerta()
    ult = a[a.trimestre_objetivo == a.trimestre_objetivo.max()]
    print(f"\nAlerta para {ult.trimestre_objetivo.iloc[0]}:", ult.alerta.value_counts().to_dict())


if __name__ == "__main__":
    ejecutar()
