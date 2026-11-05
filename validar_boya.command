#!/bin/bash
# Doble clic: valida el oleaje del reanálisis IBI con la boya Golfo de Cádiz (Puertos del Estado).
# No cambia el modelo ni los resultados del semáforo; solo agrega resultados/validacion_oleaje_boya.csv
cd "$(dirname "$0")" || exit 1
exec > >(tee -a data/raw/boya.log) 2>&1
echo "=== Inicio validación boya $(date) ==="
source ./entorno.sh
python -m src.validacion_boya || echo "Algo falló. Si pide login: copernicusmarine login. Luego vuelve a hacer doble clic."
echo "=== Fin $(date) ==="
read -r -p "Enter para cerrar"
