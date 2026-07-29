from flask import Flask, render_template, request
import csv
import math
import os
import random
import tempfile
from datetime import datetime, timezone

app = Flask(__name__, template_folder="templates", static_folder="static")

PLOTS_FOLDER = "static/plots"

# Salamanca coordinates
SALAMANCA_LAT = 40.97
SALAMANCA_LON = -5.66

ENS_METEOGRAM_FILE = "ens_meteograma.png"
ENS_CSV_FILE = os.path.join(app.root_path, "data", "ens_salamanca.csv")


@app.route("/")
def index():

    plots = sorted(
        f for f in os.listdir(PLOTS_FOLDER)
        if f.lower().endswith(".png")
    )

    return render_template(
        "index.html",
        plots=plots,
        cache_id=random.randint(10000, 99999)
    )


# ---------------------------------------------------------------------------
# ENS artifact helpers (read pre-built files; no GRIB processing here)
# ---------------------------------------------------------------------------

def _read_ens_csv():
    """
    Read web/data/ens_salamanca.csv and return a list of row dicts.
    Returns an empty list if the file does not exist or cannot be parsed.
    """
    if not os.path.exists(ENS_CSV_FILE):
        return []
    rows = []
    try:
        with open(ENS_CSV_FILE, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)
    except Exception:
        return []
    return rows


def _ens_last_updated():
    """
    Return a human-readable last-modified timestamp for the ENS PNG artifact.
    Returns None if the file does not exist.
    """
    png_path = os.path.join(app.static_folder, "plots", ENS_METEOGRAM_FILE)
    if not os.path.exists(png_path):
        return None
    mtime = os.path.getmtime(png_path)
    dt = datetime.fromtimestamp(mtime, tz=timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M UTC")


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/ecmwf", methods=["GET", "POST"])
def ecmwf():
    data = None
    error = None
    cache_bust = random.randint(10000, 99999)

    meteogram_path = os.path.join(app.static_folder, "plots", ENS_METEOGRAM_FILE)
    meteogram_exists = os.path.exists(meteogram_path)
    ens_rows = _read_ens_csv()
    ens_last_updated = _ens_last_updated()

    if request.method == "POST":
        target = None
        try:
            # Imports are deferred to this block so that ImportError is caught and
            # shown to the user if the optional packages are not installed.
            from ecmwf.opendata import Client
            import cfgrib

            fd, target = tempfile.mkstemp(suffix=".grib2")
            os.close(fd)

            client = Client()
            client.retrieve(
                type="fc",
                step=24,
                param=["2t", "tp", "10u", "10v"],
                target=target,
            )

            all_vars = {}
            for ds in cfgrib.open_datasets(target):
                point = ds.sel(latitude=SALAMANCA_LAT, longitude=SALAMANCA_LON, method="nearest")
                for var in ds.data_vars:
                    try:
                        all_vars[var] = float(point[var])
                    except (ValueError, TypeError):
                        pass

            t2m = all_vars.get("t2m")
            tp = all_vars.get("tp")
            u10 = all_vars.get("u10")
            v10 = all_vars.get("v10")

            if t2m is None and tp is None and u10 is None and v10 is None:
                error = (
                    "El archivo GRIB se descargó pero no contiene las variables "
                    "esperadas (2t, tp, 10u, 10v). "
                    "Prueba de nuevo más tarde o comprueba la disponibilidad del modelo."
                )
            else:
                if u10 is not None and v10 is not None:
                    wind_speed = round(math.sqrt(u10**2 + v10**2), 2)
                else:
                    wind_speed = None
                data = {
                    "temperature": round(t2m - 273.15, 1) if t2m is not None else None,
                    "precipitation": round(tp * 1000, 1) if tp is not None else None,
                    "u10": round(u10, 2) if u10 is not None else None,
                    "v10": round(v10, 2) if v10 is not None else None,
                    "wind_speed": wind_speed,
                }

        except ImportError as exc:
            error = f"Dependencia no disponible: {exc}"
        except Exception as exc:
            error = f"Error al obtener datos ECMWF: {exc}"
        finally:
            if target and os.path.exists(target):
                os.unlink(target)

    return render_template(
        "ecmwf.html",
        data=data,
        error=error,
        meteogram_exists=meteogram_exists,
        ens_rows=ens_rows,
        ens_last_updated=ens_last_updated,
        cache_bust=cache_bust,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
