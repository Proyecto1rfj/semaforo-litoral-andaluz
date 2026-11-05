#!/bin/bash
# Doble clic: explica con SHAP al candidato LambdaMART (y a XGBoost) en las pruebas 2022-2024 y 2025.
# No cambia el modelo del panel ni los resultados existentes; solo agrega archivos en resultados/.
cd "$(dirname "$0")" || exit 1
exec > >(tee -a data/raw/shap.log) 2>&1
echo "=== Inicio SHAP $(date) ==="
source ./entorno.sh
python -m src.analisis_shap
echo "=== Fin $(date) ==="
read -r -p "Enter para cerrar"
