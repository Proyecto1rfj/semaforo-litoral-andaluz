"""Validación externa del IEECC con daños documentados por temporales (Capítulo 1 v3, OE2).

Pregunta: los tramos donde la Demarcación de Costas tuvo que reparar daños por temporal, ¿estaban en
prioridad alta ese trimestre? Si el índice no tuviera relación con el daño, se esperaría un tercio en
alta (terciles por trimestre).

Entrada: data/validacion/eventos_temporales.csv (eventos con fuente; coordenadas aproximadas del lugar).
Salida: resultados/validacion_danos.csv (por evento) y resultados/validacion_danos_tramos.csv (detalle).

Uso:  python -m src.validacion_danos [panel_alternativo.parquet]
"""
import sys
from math import comb

import numpy as np
import pandas as pd

import config as C

DIST_MAX_KM = 15


def _tramo_mas_cercano(ev, tramos):
    lat0 = np.radians(36.6)
    d = np.hypot((tramos.lat.values[None, :] - ev.lat.values[:, None]) * 111.2,
                 (tramos.lon.values[None, :] - ev.lon.values[:, None]) * 111.2 * np.cos(lat0))
    i = d.argmin(1)
    return tramos.tramo.values[i], d[np.arange(len(ev)), i].round(1)


def _p_hiper(k_alta, n_afect, n_tot, n_alta):
    """P(X >= k_alta) si se eligieran n_afect tramos al azar entre n_tot, con n_alta en clase alta."""
    tot = comb(n_tot, n_afect)
    return sum(comb(n_alta, k) * comb(n_tot - n_alta, n_afect - k) for k in range(k_alta, min(n_afect, n_alta) + 1)) / tot


def validar(panel_path=None, etiqueta="versión 3"):
    ev = pd.read_csv(C.RAW.parent / "validacion" / "eventos_temporales.csv")
    tramos = pd.read_csv(C.RAW / "tramos.csv")
    ev["tramo"], ev["dist_km"] = _tramo_mas_cercano(ev, tramos)
    ev = ev[ev.dist_km <= DIST_MAX_KM]
    panel = pd.read_parquet(panel_path or C.PROCESSED / "panel_ieecc.parquet")
    panel["trimestre"] = panel["trimestre"].astype(str)
    panel["pct_ieecc"] = panel.groupby("trimestre").ieecc.rank(pct=True)
    det = ev.merge(panel[["tramo", "trimestre", "clase", "ieecc", "pct_ieecc"] +
                         [c for c in ["dias_temporal_pleamar", "dias_temporal"] if c in panel]],
                   on=["tramo", "trimestre"], how="left")
    filas = []
    for (e, q), g in det.dropna(subset=["clase"]).groupby(["evento", "trimestre"], sort=False):
        t = g.drop_duplicates("tramo")
        n, k = len(t), int((t.clase == 2).sum())
        n_alta = int((panel[panel.trimestre == q].clase == 2).sum())
        filas.append({"version": etiqueta, "evento": e, "trimestre": q, "tramos_con_danos": n,
                      "en_prioridad_alta": k, "pct_alta": round(100 * k / n, 1),
                      "en_alta_o_media": int((t.clase >= 1).sum()),
                      "percentil_medio_ieecc": round(100 * t.pct_ieecc.mean(), 1),
                      "p_valor_vs_azar": round(_p_hiper(k, n, 40, n_alta), 4)})
    res = pd.DataFrame(filas)
    tot_n, tot_k = res.tramos_con_danos.sum(), res.en_prioridad_alta.sum()
    res = pd.concat([res, pd.DataFrame([{"version": etiqueta, "evento": "Total 2015-2024", "trimestre": "",
                                         "tramos_con_danos": tot_n, "en_prioridad_alta": tot_k,
                                         "pct_alta": round(100 * tot_k / tot_n, 1),
                                         "en_alta_o_media": res.en_alta_o_media.sum(),
                                         "percentil_medio_ieecc": round((res.percentil_medio_ieecc * res.tramos_con_danos).sum() / tot_n, 1),
                                         "p_valor_vs_azar": np.nan}])], ignore_index=True)
    return res, det


def validar_en_el_tiempo(det, n_perm=5000):
    """Segunda lectura: ¿el trimestre del daño fue extremo dentro de la propia historia del tramo?
    Percentil del IEECC y de los días de temporal en pleamar viva frente a los 100 trimestres del tramo,
    con prueba de permutación (mismos tramos, trimestres al azar)."""
    panel = pd.read_parquet(C.PROCESSED / "panel_ieecc.parquet")
    panel["trimestre"] = panel["trimestre"].astype(str)
    cols = [c for c in ["ieecc", "dias_temporal_pleamar", "hs_p95", "nivel_p95"] if c in panel]
    for c in cols:
        panel["pt_" + c] = panel.groupby("tramo")[c].rank(pct=True)
    m = det.dropna(subset=["clase"]).drop_duplicates(["trimestre", "tramo"])[["evento", "trimestre", "tramo"]].merge(
        panel, on=["trimestre", "tramo"])
    rng = np.random.default_rng(C.SEMILLA)
    piv = panel.pivot(index="trimestre", columns="tramo", values="pt_ieecc")
    trims = piv.index.values
    obs = m.pt_ieecc.mean()
    sims = np.array([np.mean([piv.at[rng.choice(trims), t] for t in m.tramo]) for _ in range(n_perm)])
    filas = []
    for e, g in list(m.groupby("evento", sort=False)) + [("Total 2015-2024", m)]:
        f = {"evento": e, "tramos_con_danos": len(g)}
        for c in cols:
            f["percentil_propio_" + c] = round(100 * g["pt_" + c].mean(), 1)
        f["pct_en_25_superior_ieecc"] = round(100 * (g.pt_ieecc > 0.75).mean(), 1)
        if "pt_dias_temporal_pleamar" in g:
            f["pct_en_25_superior_coincidencia"] = round(100 * (g.pt_dias_temporal_pleamar > 0.75).mean(), 1)
        filas.append(f)
    out = pd.DataFrame(filas)
    out["p_valor_permutacion_total"] = np.where(out.evento == "Total 2015-2024", round(float((sims >= obs).mean()), 4), np.nan)
    return out


def pronostico_2025(det_2025):
    """Evento fuera de muestra (marzo de 2025): ¿el pronóstico hecho con datos hasta 2024-T4 lo marcaba?"""
    pred = pd.read_parquet(C.RESULTADOS / "predicciones.parquet")
    pr = pred[pred.trimestre_objetivo == "2025Q1"][["tramo", "clase_pred", "puntaje"]]
    pr["ranking"] = pr.puntaje.rank(ascending=False).astype(int)
    al = pd.read_csv(C.RESULTADOS / "oe4_alerta.csv")
    al = al[al.trimestre_objetivo == "2025Q1"][["tramo", "alerta"]]
    t = det_2025.drop_duplicates("tramo")[["lugar", "municipio", "tramo", "dist_km"]].merge(pr, on="tramo").merge(al, on="tramo")
    t["clase_pronosticada"] = t.clase_pred.map(C.CLASES)
    return t.drop(columns=["clase_pred", "puntaje"])


if __name__ == "__main__":
    ev_all = pd.read_csv(C.RAW.parent / "validacion" / "eventos_temporales.csv")
    res, det = validar()
    salidas = [res]
    if len(sys.argv) > 1:
        r1, _ = validar(sys.argv[1], "versión anterior")
        salidas.append(r1)
    out = pd.concat(salidas, ignore_index=True)
    out.to_csv(C.RESULTADOS / "validacion_danos.csv", index=False)
    det.to_csv(C.RESULTADOS / "validacion_danos_tramos.csv", index=False)
    print("Lectura en el espacio: ¿el tramo dañado estaba en prioridad alta frente al resto ese trimestre?")
    print(out.to_string(index=False))
    tiempo = validar_en_el_tiempo(det)
    tiempo.to_csv(C.RESULTADOS / "validacion_danos_tiempo.csv", index=False)
    print("\nLectura en el tiempo: ¿el trimestre del daño fue extremo dentro de la historia del propio tramo?")
    print(tiempo.to_string(index=False))
    # fuera de muestra
    tramos = pd.read_csv(C.RAW / "tramos.csv")
    e25 = ev_all[ev_all.trimestre == "2025Q1"].copy()
    e25["tramo"], e25["dist_km"] = _tramo_mas_cercano(e25, tramos)
    p25 = pronostico_2025(e25)
    p25.to_csv(C.RESULTADOS / "validacion_danos_2025.csv", index=False)
    import json; _m = json.loads((C.RESULTADOS / "modelo_elegido.json").read_text())["modelo_elegido"]
    print(f"\nFuera de muestra: daños de marzo de 2025 frente al pronóstico 2025-T1 ({_m}, datos hasta 2024-T4)")
    print(p25.to_string(index=False))
