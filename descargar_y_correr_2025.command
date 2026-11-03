#!/bin/bash
# Doble clic: baja 2025 de Copernicus (prueba prospectiva), reprocesa y corre el modelo completo.
# No cambia el entrenamiento: normalización, marea, umbrales y modelos siguen ajustados con 2000-2018/2024.
cd "$(dirname "$0")" || exit 1
exec > >(tee -a data/raw/modelo.log) 2>&1
echo "=== Inicio 2025 $(date) ==="
source ./entorno.sh
python -c "import copernicusmarine" >/dev/null 2>&1 || pip install -q "copernicusmarine>=2.0"
# respaldo de los resultados antes de agregar 2025
R="respaldo_resultados_$(date +%Y-%m-%d_%H%M)_antes_2025"
mkdir -p "$R" && cp -R resultados "$R/" && cp -R data/processed "$R/" && cp data/raw/*.csv "$R/" 2>/dev/null
echo ">> Respaldo en $R"
python -m src.descarga_2025 || { echo "La descarga de 2025 quedó incompleta. Si pide login: copernicusmarine login. Luego vuelve a hacer doble clic."; read -r -p "Enter para cerrar"; exit 1; }
python -m src.descarga procesar
python -m src.marea                  # nivel del mar no astronómico (armónicos 2000-2018)
python -m src.marea_v2 corrientes    # corrientes sin marea
python -m src.marea_v2 prevista      # marea prevista hasta 2026-T1
python -m src.marea_v2 validar       # residuo contra REDMAR
python ejecutar_todo.py
echo "=== Fin 2025 $(date) ==="
read -r -p "Listo. Enter para cerrar"
