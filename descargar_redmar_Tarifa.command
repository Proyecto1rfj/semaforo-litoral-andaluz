#!/bin/bash
# Doble clic: descarga solo el mareógrafo Tarifa (puede correr en paralelo con los demás).
cd "$(dirname "$0")" || exit 1
mkdir -p data/raw
exec > >(tee -a data/raw/redmar_Tarifa.log) 2>&1
echo "=== REDMAR Tarifa inicio $(date) ==="
source .venv/bin/activate
python -m src.descarga redmar Tarifa
echo "=== REDMAR Tarifa fin $(date) ==="
read -r -p "Enter para cerrar"
