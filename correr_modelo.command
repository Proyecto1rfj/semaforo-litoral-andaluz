#!/bin/bash
# Doble clic: completa Copernicus, procesa, quita la marea astronómica y corre el modelo (versión 3).
cd "$(dirname "$0")" || exit 1
exec > >(tee -a data/raw/modelo.log) 2>&1
echo "=== Inicio $(date) ==="
source ./entorno.sh
python -m src.descarga copernicus
python -m src.descarga procesar
python -m src.marea                  # nivel del mar no astronómico
python -m src.marea_v2 corrientes    # corrientes sin marea
python -m src.marea_v2 prevista      # marea prevista (alerta y modelo)
python -m src.marea_v2 validar       # residuo contra REDMAR
python ejecutar_todo.py
echo "=== Fin $(date) ==="
read -r -p "Listo. Enter para cerrar"
