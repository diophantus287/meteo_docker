#!/bin/bash
set -euo pipefail

START_TS=$(date +%s)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Inicio actualizar_ecmwf.sh"

cd /home/robin/meteo_docker
source .venv/bin/activate

python scripts/build_ens_meteogram.py

END_TS=$(date +%s)
ELAPSED=$((END_TS - START_TS))
MIN=$((ELAPSED / 60))
SEC=$((ELAPSED % 60))

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Fin OK"
echo "Duración total: ${ELAPSED}s (${MIN}m ${SEC}s)"
