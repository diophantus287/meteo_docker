#!/bin/bash

# Configuración
REPO_DIR="/home/robin/meteo_docker"
GITHUB_USER="diophantus287"
REPO_NAME="meteo_docker"

# Entrar en la carpeta
cd "$REPO_DIR" || exit 1

# Inicializar Git
git init

# Rama principal
git branch -M main

# Añadir remoto
git remote remove origin 2>/dev/null
git remote add origin git@github.com:${GITHUB_USER}/${REPO_NAME}.git

echo "Repositorio Git inicializado."
echo
echo "Ahora ejecuta:"
echo "git add ."
echo "git commit -m 'Primer commit'"
echo "git push -u origin main"
git add .
git commit -m "Primer commit"
git push -u origin main
