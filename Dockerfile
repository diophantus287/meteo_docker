FROM python:3.11-slim

# Crear carpeta de la app
WORKDIR /app

# Instalar dependencias del sistema para eccodes/cfgrib
RUN apt-get update && apt-get install -y --no-install-recommends \
    libeccodes-dev \
    libeccodes0 \
    && rm -rf /var/lib/apt/lists/*

# Copiar código
COPY ./web /app

# Instalar Flask y dependencias ECMWF
RUN pip install --no-cache-dir Flask numpy matplotlib

# Exponer puerto
EXPOSE 5000

# Comando para arrancar Flask
CMD ["python", "app.py"]
