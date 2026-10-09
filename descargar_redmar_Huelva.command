#!/bin/bash
# Doble clic: descarga solo el mareógrafo Huelva (puede correr en paralelo con los demás).
cd "$(dirname "$0")" || exit 1
mkdir -p data/raw
exec > >(tee -a data/raw/redmar_Huelva.log) 2>&1
echo "=== REDMAR Huelva inicio $(date) ==="
source .venv/bin/activate
python -m src.descarga redmar Huelva
echo "=== REDMAR Huelva fin $(date) ==="
read -r -p "Enter para cerrar"
