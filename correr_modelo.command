#!/bin/bash
# Doble clic: completa Copernicus (viento y tramos en tierra), procesa y corre el modelo con datos reales.
cd "$(dirname "$0")" || exit 1
exec > >(tee -a data/raw/modelo.log) 2>&1
echo "=== Inicio $(date) ==="
source ./entorno.sh
python -m src.descarga copernicus
python -m src.descarga procesar
python ejecutar_todo.py
echo "=== Fin $(date) ==="
read -r -p "Listo. Enter para cerrar"
