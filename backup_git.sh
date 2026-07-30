#!/bin/bash
# === Backup automático del repositorio local a GitHub ===

# Directorio del proyecto
REPO_DIR="/home/robin/meteo_docker"

# Mensaje de commit con fecha y hora
MSG="Backup automático - $(date '+%Y-%m-%d %H:%M:%S')"

# Ir al repositorio
cd "$REPO_DIR" || { echo "❌ No se pudo acceder al repositorio"; exit 1; }

# Mostrar estado
echo "=== Estado del repositorio ==="
git status

# Añadir todos los cambios
git add .

# Crear commit
git commit -m "$MSG"

# Subir a GitHub
git push

echo "Backup completado correctamente en $(date '+%Y-%m-%d %H:%M:%S')"
