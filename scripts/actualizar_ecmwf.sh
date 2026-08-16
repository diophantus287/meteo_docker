#!/bin/bash
set -euo pipefail
# -e  : salir si cualquier comando falla
# -u  : error si se usa una variable no definida
# -o pipefail : si falla un comando de un pipe, falla todo el script

START_TS=$(date +%s)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Inicio actualizar_ecmwf.sh"

# Ir a la raíz del proyecto
cd /home/robin/meteo_docker

# Activar entorno virtual Python
source .venv/bin/activate

# 1) Descargar/actualizar GRIB ENS global
# flock evita solapes de cron (si ya hay uno corriendo, no entra)
# timeout corta el proceso si supera 90 minutos
flock -n /tmp/ecmwf.lock timeout 90m python scripts/build_ens_meteogram.py

# 2) Extraer series locales a CSV (abre GRIB una sola vez para todas las ciudades)
python scripts/ens_to_csv.py \
  --city salamanca \
  --city vilanova_de_milfontes \
  --city portimao

# 3) Generar PNGs desde todos los CSV ens_*.csv encontrados en web/data
python scripts/plot_ens_from_csv.py --all

END_TS=$(date +%s)
ELAPSED=$((END_TS - START_TS))
MIN=$((ELAPSED / 60))
SEC=$((ELAPSED % 60))

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Fin OK"
echo "Duración total: ${ELAPSED}s (${MIN}m ${SEC}s)"
