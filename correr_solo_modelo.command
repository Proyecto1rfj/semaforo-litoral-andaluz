#!/bin/bash
# Doble clic: corre el modelo versión 3 con los datos ya procesados (unos 5 minutos, sin descargas).
cd "$(dirname "$0")" || exit 1
exec > >(tee -a data/raw/modelo.log) 2>&1
echo "=== Inicio $(date) ==="
source ./entorno.sh
python ejecutar_todo.py
echo "=== Fin $(date) ==="
read -r -p "Listo. Enter para cerrar"
