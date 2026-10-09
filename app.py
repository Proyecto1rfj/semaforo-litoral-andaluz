"""OE4. Panel del semáforo predictivo (Streamlit).

Ejecutar desde la carpeta del proyecto:
    streamlit run app.py
"""
import json

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

import config as C

st.set_page_config(page_title="Semáforo de exposición climática", layout="wide")


@st.cache_data
def cargar():
    pred = pd.read_parquet(C.RESULTADOS / "predicciones.parquet")
    panel = pd.read_parquet(C.PROCESSED / "panel_ieecc.parquet")
    shap_path = C.RESULTADOS / "shap.parquet"
    shap = pd.read_parquet(shap_path) if shap_path.exists() else None
    info = json.loads((C.RESULTADOS / "modelo_elegido.json").read_text())
    val = pd.read_csv(C.RESULTADOS / "oe3_validacion.csv")
    prueba = pd.read_csv(C.RESULTADOS / "oe3_prueba.csv")
    sens = pd.read_csv(C.RESULTADOS / "oe2_sensibilidad.csv")
    extra = {k: pd.read_csv(C.RESULTADOS / f) for k, f in
             [("alerta", "oe4_alerta.csv"), ("intervalos", "oe3_intervalos.csv"), ("cambios", "oe3_cambios_clase.csv"),
              ("tendencias", "oe2_tendencias.csv"), ("residuo", "validacion_residuo_redmar.csv")]
             if (C.RESULTADOS / f).exists()}
    return pred, panel, shap, info, val, prueba, sens, extra


pred, panel, shap, info, val, prueba, sens, extra = cargar()
sintetico = C.MODO == "sintetico"

# ---------------- cabecera
st.title("Semáforo predictivo de exposición climática")
st.caption("Litoral atlántico andaluz · prioridad relativa de los tramos para el trimestre siguiente")
if sintetico:
    st.warning("Datos SINTÉTICOS de prueba. Los resultados no son reales ni se reportan.")

trimestres = sorted(pred["trimestre_objetivo"].unique())
t_obj = st.sidebar.selectbox("Trimestre a priorizar", trimestres, index=len(trimestres) - 1,
                             format_func=lambda t: f"{t} (pronóstico vigente)" if t == trimestres[-1] else t)
st.sidebar.markdown(f"**Modelo del panel:** {info['modelo_elegido']}")
if info.get("plan_b_activado"):
    st.sidebar.info("Ningún modelo superó a la persistencia, así que queda como referencia operativa del prototipo (Capítulo 1, Tabla 1). La ficha muestra cuánto aporta cada indicador al IEECC del tramo.")

d = pred[pred["trimestre_objetivo"] == t_obj].sort_values("ranking").copy()
d["Prioridad"] = d["clase_pred"].map(C.CLASES)
d["Real"] = d["clase_t1"].map(C.CLASES)
d["Actual (t)"] = d["clase"].map(C.CLASES)
ALERTA_ICONO = {"alta": "Alerta alta", "media": "Alerta media", "sin alerta": "Sin alerta"}
if "alerta" in extra:
    al = extra["alerta"][extra["alerta"]["trimestre_objetivo"] == t_obj][
        ["tramo", "alerta", "prob_temporal_clim", "marea_max_prevista", "p75", "mareas_vivas", "estacion_temporales"]]
    d = d.merge(al, on="tramo", how="left")
    d["Alerta"] = d["alerta"].map(ALERTA_ICONO)
es_clasif = "prob_alta" in d.columns and d["prob_alta"].notna().all()
etq_puntaje = "Prob. prioridad alta" if es_clasif else "Puntaje de prioridad"

tab_panel, tab_metricas = st.tabs(["Panel", "Desempeño y sensibilidad"])

with tab_panel:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tramos en prioridad alta", int((d["clase_pred"] == 2).sum()))
    c2.metric("Trimestre de origen (t)", d["trimestre"].iloc[0])
    c4.metric("Tramos en alerta alta", int((d.get("alerta") == "alta").sum()) if "alerta" in d else "s/d")
    if d["clase_t1"].notna().all():
        acierto = ((d["clase_pred"] == 2) & (d["clase_t1"] == 2)).sum() / max((d["clase_t1"] == 2).sum(), 1)
        c3.metric("Altos reales detectados", f"{acierto:.0%}")
    else:
        c3.metric("Altos reales detectados", "por observar")

    izq, der = st.columns([1.1, 1])
    with izq:
        st.subheader("Mapa semáforo")
        d["puntaje_size"] = d["puntaje"] - d["puntaje"].min() + 0.05
        kw = dict(lat="lat", lon="lon", color="Prioridad", size="puntaje_size", size_max=16, zoom=7.2,
                  hover_name="nombre", hover_data={"ranking": True, "puntaje": ":.2f", "ieecc": ":.2f",
                                                   "lat": False, "lon": False},
                  color_discrete_map={C.CLASES[k]: v for k, v in C.COLORES.items()}, height=520)
        try:
            fig = px.scatter_map(d, map_style="open-street-map", **kw)
        except AttributeError:   # plotly < 5.24
            fig = px.scatter_mapbox(d, mapbox_style="open-street-map", **kw)
        fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), legend_title_text="")
        st.plotly_chart(fig, width="stretch")

    with der:
        st.subheader("Ranking de inspección")
        cols = ["ranking", "tramo", "nombre", "puntaje", "ieecc", "Actual (t)", "Prioridad", "Real"] + (["Alerta"] if "Alerta" in d else [])
        tabla = d[cols].rename(columns={"ranking": "#", "puntaje": etq_puntaje, "ieecc": "IEECC (t)",
                                        "Prioridad": "Predicha (t+1)"})
        st.dataframe(tabla, hide_index=True, height=520,
                     column_config={etq_puntaje: st.column_config.ProgressColumn(
                         etq_puntaje, min_value=float(d["puntaje"].min()), max_value=float(d["puntaje"].max()),
                         format="%.2f")})

    # ---------------- ficha del tramo
    st.subheader("Ficha del tramo")
    tramo = st.selectbox("Tramo", d["tramo"], format_func=lambda t: f"{t} · {d.set_index('tramo').loc[t, 'nombre']}")
    fila = d.set_index("tramo").loc[tramo]
    f1, f2 = st.columns(2)
    with f1:
        st.markdown(f"**Ranking:** {int(fila['ranking'])} de {len(d)}")
        st.markdown(f"**IEECC en {fila['trimestre']}:** {fila['ieecc']:.2f} · **Clase actual:** {fila['Actual (t)']}"
                    f" · **Clase predicha para {t_obj}:** {fila['Prioridad']}")
        ind = panel[(panel["tramo"] == tramo) & (panel["trimestre"].astype(str) == str(fila["trimestre"]))]
        if not ind.empty:
            r = ind.iloc[0]
            st.caption("Indicadores en t: " + " · ".join(
                f"{v.split(':')[0]} {r[k]:.2f}" for k, v in C.INDICADORES.items() if k in r))
        if "alerta" in d and pd.notna(fila.get("alerta")):
            st.markdown(f"**Alerta para {t_obj}:** {ALERTA_ICONO[fila['alerta']]}")
            st.caption(f"Probabilidad climatológica de temporal en esta época: {fila['prob_temporal_clim']:.0%} · "
                       f"pleamar máxima prevista {fila['marea_max_prevista']:.2f} m (umbral de pleamar viva del tramo "
                       f"{fila['p75']:.2f} m). La alerta es alta cuando coinciden la estación de temporales y las pleamares vivas.")
        if shap is not None:
            s = shap[(shap["tramo"] == tramo) & (shap["trimestre_objetivo"] == t_obj)]
            s = s.drop(columns=["tramo", "trimestre_objetivo"]).iloc[0].astype(float)
            s = s.reindex(s.abs().sort_values(ascending=False).index)[:8][::-1]
            fig_s = go.Figure(go.Bar(x=s.values, y=s.index, orientation="h",
                                     marker_color=["#d1373f" if v > 0 else "#2e9d5b" for v in s.values]))
            fig_s.update_layout(title="Qué empuja la prioridad (SHAP)", height=330,
                                margin=dict(l=0, r=0, t=40, b=0))
            st.plotly_chart(fig_s, width="stretch")
        else:
            st.info("El modelo del panel es la persistencia: la prioridad repite la posición del trimestre actual.")
    with f2:
        h = panel[panel["tramo"] == tramo].copy()
        h["fecha"] = pd.PeriodIndex(h["trimestre"], freq="Q").to_timestamp()
        fig_h = px.line(h, x="fecha", y="ieecc", title="Evolución del IEECC 2000-2024", height=380)
        for k, (y0, y1) in enumerate([(0, 1 / 3), (1 / 3, 2 / 3), (2 / 3, 1)]):
            fig_h.add_hrect(y0=y0, y1=y1, fillcolor=C.COLORES[k], opacity=0.08, line_width=0)
        fig_h.update_layout(margin=dict(l=0, r=0, t=40, b=0), yaxis_range=[0, 1], xaxis_title="")
        st.plotly_chart(fig_h, width="stretch")
    st.caption("Las franjas son orientativas: la clase se define por tercil dentro de cada trimestre.")

    # ---------------- mapa de calor tramo × trimestre
    st.subheader("Mapa de calor: clase por tramo y trimestre (2000-2024)")
    hm = panel.assign(trimestre=panel["trimestre"].astype(str)).pivot(index="tramo", columns="trimestre", values="clase")
    nombres = panel.drop_duplicates("tramo").set_index("tramo")["nombre"]
    fig_hm = go.Figure(go.Heatmap(
        z=hm.values, x=hm.columns, y=[f"{t} · {nombres[t]}" for t in hm.index],
        colorscale=[[0, C.COLORES[0]], [0.33, C.COLORES[0]], [0.34, C.COLORES[1]], [0.66, C.COLORES[1]],
                    [0.67, C.COLORES[2]], [1, C.COLORES[2]]], zmin=0, zmax=2, showscale=False,
        hovertemplate="%{y}<br>%{x}: clase %{z}<extra></extra>"))
    fig_hm.update_layout(height=max(420, 16 * len(hm)), margin=dict(l=0, r=0, t=10, b=0),
                         yaxis=dict(autorange="reversed", tickfont=dict(size=9)), xaxis=dict(tickfont=dict(size=9)))
    st.plotly_chart(fig_hm, width="stretch")
    st.caption("Verde = baja, amarillo = media, rojo = alta. Una franja roja continua indica exposición persistente; "
               "un rojo aislado, un episodio puntual.")

with tab_metricas:
    st.subheader("Validación 2019-2021 (selección del modelo)")
    st.dataframe(val, hide_index=True)
    st.subheader("Prueba 2022-2024 (modelos reentrenados con 2000-2021)")
    st.dataframe(prueba, hide_index=True)
    mc = C.RESULTADOS / "oe3_matrices_confusion.csv"
    if mc.exists():
        st.subheader(f"Matriz de confusión en prueba: {info['modelo_elegido']}")
        m = pd.read_csv(mc)
        m = m[m["modelo"] == info["modelo_elegido"]].pivot(index="real", columns="predicha", values="n")
        st.dataframe(m.reindex(index=["baja", "media", "alta"], columns=["baja", "media", "alta"]))
    if "intervalos" in extra:
        st.subheader("Intervalos de confianza del 95 % (bootstrap por trimestres) y diferencia con la persistencia")
        st.dataframe(extra["intervalos"], hide_index=True)
    if "cambios" in extra:
        st.subheader("Tramos que cambian de clase en t+1 (donde la persistencia falla siempre)")
        st.dataframe(extra["cambios"], hide_index=True)
    st.subheader("Sensibilidad del IEECC (meta: menos de 20 % de cambio por escenario)")
    st.dataframe(sens, hide_index=True)
    if "tendencias" in extra:
        st.subheader("Tendencias 2000-2024 por indicador (Mann-Kendall y pendiente de Sen)")
        t = extra["tendencias"]
        st.dataframe(t.groupby("indicador").agg(tramos_con_tendencia=("significativa", "sum"),
                                                pendiente_mediana_por_decada=("pendiente_sen_por_decada", "median")).round(4))
    if "residuo" in extra:
        st.subheader("Validación del nivel del mar no astronómico contra REDMAR")
        st.dataframe(extra["residuo"], hide_index=True)
