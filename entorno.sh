# Activa el entorno y, si hace falta, usa un libomp nuevo para XGBoost.
# Motivo: Anaconda trae un libomp antiguo (/opt/anaconda3/lib) y XGBoost 3 no carga con él.
source .venv/bin/activate
python -c "import lightgbm" >/dev/null 2>&1 || pip install -q "lightgbm>=4.0"
OMP="$HOME/.semaforo_omp"
if ! python -c "import xgboost, lightgbm" >/dev/null 2>&1; then
  if [ ! -f "$OMP/lib/libomp.dylib" ]; then
    echo ">> Instalando libomp actualizado para XGBoost (una sola vez, fuera de Anaconda base)"
    CONDA="$(command -v conda || echo /opt/anaconda3/bin/conda)"
    "$CONDA" create -y -p "$OMP" --override-channels -c conda-forge "llvm-openmp>=18"
  fi
  export DYLD_LIBRARY_PATH="$OMP/lib"
fi
python -c "import xgboost, lightgbm; print('XGBoost', xgboost.__version__, '| LightGBM', lightgbm.__version__, 'OK')" || { echo "XGBoost o LightGBM no cargan"; read -r -p "Enter para cerrar"; exit 1; }
