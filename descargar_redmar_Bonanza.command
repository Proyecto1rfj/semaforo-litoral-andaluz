#!/bin/bash
# Doble clic: descarga solo el mareógrafo Bonanza (puede correr en paralelo con los demás).
cd "$(dirname "$0")" || exit 1
mkdir -p data/raw
exec > >(tee -a data/raw/redmar_Bonanza.log) 2>&1
echo "=== REDMAR Bonanza inicio $(date) ==="
source .venv/bin/activate
python -m src.descarga redmar Bonanza
echo "=== REDMAR Bonanza fin $(date) ==="
read -r -p "Enter para cerrar"
