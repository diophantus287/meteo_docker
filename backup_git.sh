#!/bin/bash
set -euo pipefail

# Backup automático/manual del repositorio local a GitHub

REPO_DIR="/home/robin/meteo_docker"
AUTO_MSG="Backup automático - $(date '+%Y-%m-%d %H:%M:%S')"

cd "$REPO_DIR" || { echo "No se pudo acceder al repositorio"; exit 1; }

echo "=== Estado del repositorio ==="
git status --short

# Si no hay cambios, salir limpio
if git diff --quiet && git diff --cached --quiet; then
  echo "No hay cambios para commit."
  exit 0
fi

MSG="$AUTO_MSG"

# Si hay terminal interactiva, pedir mensaje
# (en cron normalmente no hay TTY, así que usa AUTO_MSG)
if [ -t 0 ]; then
  read -r -p "Mensaje de commit (Intro = automático): " USER_MSG
  if [ -n "${USER_MSG// }" ]; then
    MSG="$USER_MSG"
  fi
fi

git add .
git commit -m "$MSG"
git push

echo "Backup completado correctamente en $(date '+%Y-%m-%d %H:%M:%S')"
echo "Commit: $MSG"
