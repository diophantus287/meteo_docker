# meteo_docker

Panel web de predicción meteorológica para Salamanca, basado en Flask y Docker.
Incluye un pipeline externo para el meteograma ENS de ECMWF.

---

## Estructura del proyecto

```
meteo_docker/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt              # deps del script ENS
├── scripts/
│   └── build_ens_meteogram.py   # pipeline ENS (ejecutado por GH Actions)
├── .github/
│   └── workflows/
│       └── ens_meteogram.yml    # schedule automático
└── web/                         # montado en /app dentro del contenedor
    ├── app.py
    ├── data/
    │   ├── ens_salamanca.csv    # artefacto generado automáticamente
    │   └── ens_meteograma.json  # artefacto generado automáticamente
    ├── static/
    │   └── plots/
    │       └── ens_meteograma.png  # artefacto generado automáticamente
    └── templates/
        ├── index.html
        └── ecmwf.html
```

---

## Arrancando la aplicación

```bash
docker compose up -d
```

La app queda disponible en `http://localhost:8084` (o a través de Traefik si está configurado).

---

## Meteograma ENS ECMWF

### ¿Cómo funciona?

El script `scripts/build_ens_meteogram.py` descarga los 51 miembros del ENS de ECMWF
(temperatura a 2 m, pasos 6–168 h cada 6 h), calcula estadísticos diarios de Tmax y Tmin
(mín, p10, p25, p50, p75, p90, máx) para el punto más cercano a Salamanca (40.97°N, 5.66°W)
y guarda tres artefactos:

| Archivo | Descripción |
|---|---|
| `web/data/ens_salamanca.csv` | Tabla diaria de estadísticos (°C) |
| `web/data/ens_meteograma.json` | Resumen en JSON para frontend |
| `web/static/plots/ens_meteograma.png` | Gráfico tipo meteograma |

La app Flask **sólo lee** estos artefactos pre-generados; no realiza ninguna descarga ni
procesado GRIB en tiempo de petición.

### Ejecución manual

```bash
# Instalar dependencias del sistema (Debian/Ubuntu)
sudo apt-get install -y libeccodes-dev

# Instalar dependencias Python
pip install -r requirements.txt

# Ejecutar el script (usa rutas por defecto relativas al repo)
python scripts/build_ens_meteogram.py

# Rutas personalizadas
python scripts/build_ens_meteogram.py \
    --csv  /ruta/a/ens_salamanca.csv \
    --json /ruta/a/ens_meteograma.json \
    --png  /ruta/a/ens_meteograma.png
```

### Schedule automático (GitHub Actions)

El workflow `.github/workflows/ens_meteogram.yml` se ejecuta automáticamente:

- **07:30 UTC** — para recoger la corrida del modelo 00z (disponible ~06:30 UTC)
- **19:30 UTC** — para recoger la corrida del modelo 12z (disponible ~18:30 UTC)

Pasos del workflow:
1. Checkout del repositorio
2. Instalación de `libeccodes-dev` y dependencias Python
3. Ejecución de `scripts/build_ens_meteogram.py`
4. Commit y push de los artefactos si han cambiado (con `[skip ci]` para no crear bucles)

También se puede lanzar manualmente desde la pestaña **Actions** del repositorio usando
"Run workflow".

Para que el push automático funcione, el workflow ya tiene configurado
`permissions: contents: write`.

### Actualizar artefactos en el servidor

El servidor monta `./web` como volumen en Docker Compose. Para recoger los nuevos
artefactos publicados por GitHub Actions:

```bash
cd /home/robin/meteo_docker
git pull origin main
```

Después de `git pull` el contenedor sirve automáticamente los archivos actualizados
(el volumen ya está actualizado, sin necesidad de reiniciar el contenedor).

---

## Troubleshooting

### `cfgrib` no puede abrir el archivo GRIB

```
cfgrib could not open /tmp/xxx_cf.grib2: ...
```

Asegúrate de tener `libeccodes-dev` instalado:

```bash
sudo apt-get install -y libeccodes-dev
pip install --upgrade cfgrib eccodes
```

### Sin datos ENS disponibles

El servidor ECMWF puede tardar en publicar la nueva corrida. Si el script falla
con "No ENS data could be parsed", espera 30 minutos y vuelve a intentarlo.

### Artefactos no aparecen en la web

Si la página muestra el aviso de "artefactos no generados":

1. Comprueba que GH Actions haya terminado con éxito en la pestaña **Actions**.
2. Comprueba que el servidor haya hecho `git pull`.
3. Si el contenedor estaba en marcha antes del pull, verifica que el volumen
   refleja los nuevos archivos: `ls -lh web/data/ web/static/plots/ens_meteograma.png`.

### Error al descargar predicción ECMWF (+24 h)

La predicción determinista también usa `cfgrib` dentro del contenedor Docker.
Asegúrate de que la imagen tiene `libeccodes-dev`/`libeccodes0` instalado
(ya está incluido en el `Dockerfile` actual).
