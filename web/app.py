from pathlib import Path
from datetime import datetime
from flask import Flask, render_template

from ecmwf_routes import ecmwf_bp

app = Flask(__name__)
app.register_blueprint(ecmwf_bp)

BASE_DIR = Path(__file__).resolve().parent


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
    return render_template("index.html", plots=plots, cache_id=cache_id)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
