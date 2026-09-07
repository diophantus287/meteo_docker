from pathlib import Path
from flask import Blueprint, render_template, url_for, current_app

ecmwf_bp = Blueprint("ecmwf", __name__)


def _list_meteogramas(subdir: str, pattern: str):
    folder = Path(current_app.static_folder) / subdir
    meteogramas = []

    if folder.exists():
        for p in sorted(folder.glob(pattern)):
            label = (
                p.stem.replace("ens_meteograma_", "")
                .replace("ens_simple_", "")
                .replace("ens_meteograma", "")
                .strip("_")
                .replace("_", " ")
                .title()
            ) or "General"

            meteogramas.append(
                {
                    "file": p.name,
                    "label": label,
                    "url": url_for("static", filename=f"{subdir}/{p.name}"),
                }
            )

    return meteogramas


@ecmwf_bp.route("/ecmwf")
def ecmwf():
    meteogramas = _list_meteogramas("ecmwf", "ens_meteograma*.png")
    return render_template("ecmwf.html", meteogramas=meteogramas)


@ecmwf_bp.route("/ecmwf_simple")
def ecmwf_simple():
    meteogramas = _list_meteogramas("ecmwf_simple", "ens_simple*.png")
    return render_template("ecmwf_simple.html", meteogramas=meteogramas)
