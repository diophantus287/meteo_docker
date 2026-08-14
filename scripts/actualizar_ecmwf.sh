#!/bin/bash

set -e

# Ir al proyecto
cd /home/robin/meteo_docker

# Activar entorno virtual
source .venv/bin/activate

# Ejecutar el script
python scripts/build_ens_meteogram.py
