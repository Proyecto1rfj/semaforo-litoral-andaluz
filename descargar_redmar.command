#!/bin/bash
# Doble clic: descarga solo los mareógrafos REDMAR (sin cuenta). Reanudable por mes.
cd "$(dirname "$0")" || exit 1
mkdir -p data/raw
exec > >(tee -a data/raw/redmar.log) 2>&1
echo "=== REDMAR inicio $(date) ==="
source .venv/bin/activate
python -m src.descarga redmar && python -c "from src.descarga import procesar_redmar; procesar_redmar()"
echo "=== REDMAR fin $(date) ==="
read -r -p "Enter para cerrar"
