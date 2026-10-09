#!/bin/bash
# Doble clic: abre el panel del semáforo en el navegador.
cd "$(dirname "$0")" || exit 1
source ./entorno.sh
streamlit run app.py
