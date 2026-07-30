from pathlib import Path
from datetime import datetime
import csv

from flask import Flask, render_template, url_for

app = Flask(__name__)

# Ajusta si tu estructura es distinta
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STATIC_PLOT_REL = "ecmwf/ens_meteograma.png"          # dentro de web/static/
CSV_PATH = DATA_DIR / "ens_salamanca.csv"
PLOT_PATH = BASE_DIR / "static" / STATIC_PLOT_REL



def _fmt_mtime(path: Path) -> str | None:
    if not path.exists():
        return None
    ts = datetime.fromtimestamp(path.stat().st_mtime)
    return ts.strftime("%Y-%m-%d %H:%M:%S")


def _read_stats_csv(csv_path: Path) -> list[dict]:
    if not csv_path.exists():
        return []

    rows: list[dict] = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            # Convierte a float para que el template formatee con "%.1f"
            rows.append({
                "day": r.get("date", ""),
                "tmax_min": float(r.get("tmax_min", "nan")),
                "tmax_p10": float(r.get("tmax_p10", "nan")),
                "tmax_p25": float(r.get("tmax_p25", "nan")),
                "tmax_p50": float(r.get("tmax_p50", "nan")),
                "tmax_p75": float(r.get("tmax_p75", "nan")),
                "tmax_p90": float(r.get("tmax_p90", "nan")),
                "tmax_max": float(r.get("tmax_max", "nan")),
                "tmin_min": float(r.get("tmin_min", "nan")),
                "tmin_p10": float(r.get("tmin_p10", "nan")),
                "tmin_p25": float(r.get("tmin_p25", "nan")),
                "tmin_p50": float(r.get("tmin_p50", "nan")),
                "tmin_p75": float(r.get("tmin_p75", "nan")),
                "tmin_p90": float(r.get("tmin_p90", "nan")),
                "tmin_max": float(r.get("tmin_max", "nan")),
            })
    return rows

@app.route("/")
def index():
    plots_dir = BASE_DIR / "static" / "plots"

    plots = []
    if plots_dir.exists():
        plots = sorted(
            f.name
            for f in plots_dir.iterdir()
            if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".gif", ".webp")
        )

    cache_id = int(datetime.now().timestamp())

    return render_template(
        "index.html",
        plots=plots,
        cache_id=cache_id,
    )

@app.route("/ecmwf")
def ecmwf():
    plot_url = url_for("static", filename=STATIC_PLOT_REL) if PLOT_PATH.exists() else None
    updated_at = _fmt_mtime(PLOT_PATH) or _fmt_mtime(CSV_PATH)

    return render_template(
        "ecmwf.html",
        plot_url=plot_url,
        updated_at=updated_at,
    )



@app.route("/ecmwf_stats")
def ecmwf_stats():
    rows = _read_stats_csv(CSV_PATH)
    updated_at = _fmt_mtime(CSV_PATH)

    return render_template(
        "ecmwf_stats.html",
        rows=rows,
        updated_at=updated_at,
    )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
