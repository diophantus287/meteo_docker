#!/bin/bash
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Esperando 150 segundos antes de comenzar..."
sleep 150

# Variables
REMOTE_USER1="screen"
REMOTE_HOST1="192.168.68.104"
REMOTE_FILE1="/home/screen/pantallear/pantalla.png"

REMOTE_USER2="edward"
REMOTE_HOST2="192.168.0.33"
REMOTE_FILE2="/home/edward/01_casa/03_plots/plot_diario.png"

REMOTE_USER3="max"
REMOTE_HOST3="192.168.0.30"
REMOTE_FILE31="/home/max/07_aemet/02_prediccion/csv_elaboracion/plotfechas.png"
REMOTE_FILE32="/home/max/01_plotscasa/casa_total.png"
REMOTE_FILE33="/home/max/01_plotscasa/out_total.png"
REMOTE_FILE34="/home/max/07_aemet/02_prediccion/prediccion_salamanca_IA.png"
REMOTE_FILE35="/home/max/07_aemet/04_UVindex/uv_img/UV_index.png"

LOCAL_FOLDER="/home/robin/meteo_docker/web/static/plots/"

# Crear carpeta local si no existe
mkdir -p "$LOCAL_FOLDER"

# Borrar todos los archivos existentes en la carpeta local
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Limpiando carpeta local: $LOCAL_FOLDER"
rm -f "$LOCAL_FOLDER"/*

# Descargar archivo desde la primera máquina
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Descargando pantalla.png desde $REMOTE_HOST1"
sftp "$REMOTE_USER1@$REMOTE_HOST1" <<EOF
get $REMOTE_FILE1 $LOCAL_FOLDER
bye
EOF

# Descargar archivo desde la segunda máquina
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Descargando plot_diario.png desde $REMOTE_HOST2"

sftp "$REMOTE_USER2@$REMOTE_HOST2" <<EOF
get $REMOTE_FILE2 $LOCAL_FOLDER
bye
EOF


# Descargar archivos desde la tercera máquina
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Descargando archivos desde $REMOTE_HOST3"

FILES=(
"$REMOTE_FILE31"
"$REMOTE_FILE32"
"$REMOTE_FILE33"
"$REMOTE_FILE34"
"$REMOTE_FILE35"
)

for FILE in "${FILES[@]}"; do
    BASENAME=$(basename "$FILE")

    echo "[$(date '+%Y-%m-%d %H:%M:%S')] --> $BASENAME"
    sftp "$REMOTE_USER3@$REMOTE_HOST3" <<EOF
get $FILE $LOCAL_FOLDER
bye
EOF

done

# Renombrar archivos
if [ -f "$LOCAL_FOLDER/plot_diario.png" ]; then
    mv "$LOCAL_FOLDER/plot_diario.png" "$LOCAL_FOLDER/01_plot_diario.png"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Renombrado a 01_plot_diario.png"
fi
if [ -f "$LOCAL_FOLDER/pantalla.png" ]; then
    mv "$LOCAL_FOLDER/pantalla.png" "$LOCAL_FOLDER/02_pantalla.png"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Renombrado a 02_pantalla.png"
fi

if [ -f "$LOCAL_FOLDER/UV_index.png" ]; then
    mv "$LOCAL_FOLDER/UV_index.png" "$LOCAL_FOLDER/31_UV_index.png"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Renombrado a 31_UV_index.png"
fi
if [ -f "$LOCAL_FOLDER/prediccion_salamanca_IA.png" ]; then
    mv "$LOCAL_FOLDER/prediccion_salamanca_IA.png" "$LOCAL_FOLDER/10_prediccion_salamanca.png"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Renombrado a 10_prediccion_salamanca.png"
fi
if [ -f "$LOCAL_FOLDER/plotfechas.png" ]; then
    mv "$LOCAL_FOLDER/plotfechas.png" "$LOCAL_FOLDER/91_plotfechas.png"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Renombrado a 91_plotfechas.png"
fi
if [ -f "$LOCAL_FOLDER/out_total.png" ]; then
    mv "$LOCAL_FOLDER/out_total.png" "$LOCAL_FOLDER/20_out_total.png"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Renombrado a 20_out_total.png"
fi
if [ -f "$LOCAL_FOLDER/casa_total.png" ]; then
    mv "$LOCAL_FOLDER/casa_total.png" "$LOCAL_FOLDER/21_casa_total.png"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Renombrado a 21_casa_total.png"
fi

# Descargar el último archivo del directorio plots_diarios en 192.168.0.30
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Descargando último plot diario desde $REMOTE_HOST3"

LATEST_FILE=$(ssh "$REMOTE_USER3@$REMOTE_HOST3" "ls -t /home/max/07_aemet/03_historico/plots_diarios/*.png 2>/dev/null | head -n 1")

if [ -n "$LATEST_FILE" ]; then
    BASENAME=$(basename "$LATEST_FILE")
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] --> Último archivo: $BASENAME"

    sftp "$REMOTE_USER3@$REMOTE_HOST3" <<EOF
get $LATEST_FILE $LOCAL_FOLDER
bye
EOF

    # Renombrar con prefijo 'zz_'
    if [ -f "$LOCAL_FOLDER/$BASENAME" ]; then
        mv "$LOCAL_FOLDER/$BASENAME" "$LOCAL_FOLDER/90_$BASENAME"
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] Renombrado a 90_$BASENAME"
    fi
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] No se encontró ningún archivo en plots_diarios"
fi
