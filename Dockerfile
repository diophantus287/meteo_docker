FROM python:3.11-slim

# Crear carpeta de la app
WORKDIR /app

# Copiar código
COPY ./web /app

# Instalar Flask
RUN pip install --no-cache-dir Flask

# Exponer puerto
EXPOSE 5000

# Comando para arrancar Flask
CMD ["python", "app.py"]
