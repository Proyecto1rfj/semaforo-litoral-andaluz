#!/bin/bash
# Doble clic desde Finder: prepara el entorno y descarga los datos públicos del Capítulo 1.
# Se puede cerrar y volver a abrir: retoma donde quedó.
cd "$(dirname "$0")" || exit 1
LOG="data/raw/descarga.log"
mkdir -p data/raw
exec > >(tee -a "$LOG") 2>&1
echo "=== Inicio $(date) ==="

if ! command -v python3 >/dev/null 2>&1; then
  echo "No se encontró python3. Instálalo desde https://www.python.org/downloads/ y vuelve a abrir este archivo."
  read -r -p "Enter para cerrar"; exit 1
fi
python3 --version

if [ ! -d .venv ]; then
  echo ">> Creando entorno virtual .venv"
  python3 -m venv .venv || { echo "No se pudo crear .venv"; read -r -p "Enter para cerrar"; exit 1; }
fi
source .venv/bin/activate
if [ ! -f .venv/.instalado ]; then
  echo ">> Instalando librerías (solo la primera vez, unos minutos)"
  pip install --upgrade pip -q && pip install -r requirements.txt -q && touch .venv/.instalado
fi

echo ">> REDMAR (mareógrafos Huelva, Bonanza y Tarifa)"
python -m src.descarga redmar

echo ">> Copernicus Marine (oleaje, viento, nivel y corrientes)"
if [ ! -f "$HOME/.copernicusmarine/.copernicusmarine-credentials" ]; then
  echo "Falta iniciar sesión en Copernicus Marine (cuenta gratuita en https://data.marine.copernicus.eu/register)."
  echo "Escribe tu usuario y contraseña cuando te los pida:"
  copernicusmarine login
fi
if [ -f "$HOME/.copernicusmarine/.copernicusmarine-credentials" ]; then
  python -m src.descarga copernicus
else
  echo "Sin sesión de Copernicus: se omite esa parte por ahora."
fi

echo ">> Procesando a series diarias"
python -m src.descarga procesar

if [ -f data/raw/copernicus_diario.csv ]; then
  echo ">> Corriendo el flujo completo con datos reales"
  python ejecutar_todo.py
fi
echo "=== Fin $(date) ==="
read -r -p "Listo. Enter para cerrar"
