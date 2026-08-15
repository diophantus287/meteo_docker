from pathlib import Path
from flask import Blueprint, render_template, url_for, current_app

ecmwf_bp = Blueprint("ecmwf", __name__)

@ecmwf_bp.route("/ecmwf")
def ecmwf():
    static_ecmwf = Path(current_app.static_folder) / "ecmwf"
    meteogramas = []

    if static_ecmwf.exists():
        for p in sorted(static_ecmwf.glob("ens_meteograma*.png")):
            label = (
                p.stem.replace("ens_meteograma", "")
                .strip("_")
                .replace("_", " ")
                .title()
            ) or "General"

            meteogramas.append({
                "file": p.name,
                "label": label,
                "url": url_for("static", filename=f"ecmwf/{p.name}"),
            })

    return render_template("ecmwf.html", meteogramas=meteogramas)
