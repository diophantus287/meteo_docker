#!/bin/bash
set -euo pipefail

START_TS=$(date +%s)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Inicio actualizar_ecmwf.sh"

cd /home/robin/meteo_docker
source .venv/bin/activate

# 1) Descargar GRIB global
#python scripts/build_ens_meteogram.py

# 2) Extraer y plotear localidades
python scripts/plotear_meteogram.py --city salamanca
python scripts/plotear_meteogram.py --city vilanova_de_milfontes
python scripts/plotear_meteogram.py --city portimao 
# Ejemplos adicionales:
# python scripts/plotear_meteogram.py --city madrid
# python scripts/plotear_meteogram.py --name "Ciudad Rodrigo" --lat 40.60 --lon -6.53

END_TS=$(date +%s)
ELAPSED=$((END_TS - START_TS))
MIN=$((ELAPSED / 60))
SEC=$((ELAPSED % 60))

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Fin OK"
echo "Duración total: ${ELAPSED}s (${MIN}m ${SEC}s)"
