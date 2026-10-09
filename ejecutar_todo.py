"""Corre el flujo completo de la versión 3: OE1 → OE2 → OE3 → intervalos, tendencias y alerta.
Luego abrir el panel con:  streamlit run app.py
"""
import config as C
from src import analisis, datos_sinteticos, ieecc, integracion, modelado

if __name__ == "__main__":
    if not (C.RAW / "tramos.csv").exists():
        datos_sinteticos.generar()
    integracion.ejecutar()
    print("\n" + "-" * 70)
    ieecc.ejecutar()
    print("\n" + "-" * 70)
    modelado.ejecutar()
    print("\n" + "-" * 70)
    analisis.ejecutar()
    print("\nListo. Panel:  streamlit run app.py")
