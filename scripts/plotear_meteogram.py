#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------
# Rutas base (ejecutado desde /home/robin/meteo_docker)
# ---------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GRIB = REPO_ROOT / "data" / "ecmwf" / "global" / "ecmwf_ens_global_latest.grib"
DEFAULT_DATA_DIR = REPO_ROOT / "web" / "data"
DEFAULT_IMG_DIR = REPO_ROOT / "web" / "static" / "ecmwf"

# ---------------------------------------------------------------------
# Localidades predefinidas (fácil de ampliar)
# slug: (Nombre visible, lat, lon)
# ---------------------------------------------------------------------
CITIES = {
    "salamanca": ("Salamanca", 40.97, -5.66),
    "madrid": ("Madrid", 40.4168, -3.7038),
    "barcelona": ("Barcelona", 41.3874, 2.1686),
    "valencia": ("Valencia", 39.4699, -0.3763),
    "sevilla": ("Sevilla", 37.3891, -5.9845),

    # Portugal
    "vilanova_de_milfontes": ("Vila Nova de Milfontes", 37.7238, -8.7828),
    "portimao": ("Portimão", 37.1366, -8.5378),
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("plot_ens_local")

# ---------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------
def slugify(text: str) -> str:
    return (
        text.lower()
        .strip()
        .replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
        .replace("ñ", "n")
        .replace(" ", "_")
    )

def _collect_ens_t2m(grib_path: Path, lat: float, lon: float) -> dict[int, list[float]]:
    import cfgrib

    result: dict[int, list[float]] = {}
    datasets = cfgrib.open_datasets(str(grib_path))

    for ds in datasets:
        if "t2m" not in ds.data_vars:
            continue

        da = ds["t2m"].sel(latitude=lat, longitude=lon, method="nearest")

        if "step" in da.dims:
            for i in range(len(da.step)):
                step_h = int(da.step.values[i] / np.timedelta64(1, "h"))
                vals = np.atleast_1d(da.isel(step=i).values - 273.15).flatten().tolist()
                result.setdefault(step_h, []).extend(vals)
        else:
            step_h = int(da.step.values / np.timedelta64(1, "h"))
            vals = np.atleast_1d(da.values - 273.15).flatten().tolist()
            result.setdefault(step_h, []).extend(vals)

    return result

def _compute_daily_stats(step_data: dict[int, list[float]]):
    today = datetime.now(timezone.utc).date()

    dates = []
    labels = []
    tmin = {k: [] for k in ("mn", "p10", "p25", "p50", "p75", "p90", "mx")}
    tmax = {k: [] for k in ("mn", "p10", "p25", "p50", "p75", "p90", "mx")}

    day_to_steps: dict[int, list[int]] = {}
    for sh in sorted(step_data):
        if sh < 6:
            continue
        day_idx = ((sh - 6) // 24) + 1
        day_to_steps.setdefault(day_idx, []).append(sh)

    for day_idx in sorted(day_to_steps):
        available = {sh: np.array(step_data[sh], dtype=float) for sh in sorted(day_to_steps[day_idx])}
        if len(available) < 2:
            continue

        n_mem = min(len(v) for v in available.values())
        if n_mem == 0:
            continue

        arr = np.array([available[sh][:n_mem] for sh in sorted(available)])
        member_tmin = arr.min(axis=0)
        member_tmax = arr.max(axis=0)

        d = today + timedelta(days=day_idx - 1)
        dates.append(d)
        labels.append(d.strftime("%a %d %b"))

        for stats, vals in ((tmin, member_tmin), (tmax, member_tmax)):
            stats["mn"].append(float(np.min(vals)))
            stats["p10"].append(float(np.percentile(vals, 10)))
            stats["p25"].append(float(np.percentile(vals, 25)))
            stats["p50"].append(float(np.percentile(vals, 50)))
            stats["p75"].append(float(np.percentile(vals, 75)))
            stats["p90"].append(float(np.percentile(vals, 90)))
            stats["mx"].append(float(np.max(vals)))

    if not dates:
        raise RuntimeError("No hay suficientes datos para calcular estadísticos diarios.")

    return dates, labels, tmin, tmax

def _save_csv(csv_path: Path, dates, labels, tmin, tmax):
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    headers = [
        "date", "day_label",
        "tmax_min", "tmax_p10", "tmax_p25", "tmax_p50", "tmax_p75", "tmax_p90", "tmax_max",
        "tmin_min", "tmin_p10", "tmin_p25", "tmin_p50", "tmin_p75", "tmin_p90", "tmin_max",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(headers)
        for i, (d, lbl) in enumerate(zip(dates, labels)):
            w.writerow([
                d.strftime("%Y-%m-%d"), lbl,
                round(tmax["mn"][i], 2), round(tmax["p10"][i], 2), round(tmax["p25"][i], 2),
                round(tmax["p50"][i], 2), round(tmax["p75"][i], 2), round(tmax["p90"][i], 2), round(tmax["mx"][i], 2),
                round(tmin["mn"][i], 2), round(tmin["p10"][i], 2), round(tmin["p25"][i], 2),
                round(tmin["p50"][i], 2), round(tmin["p75"][i], 2), round(tmin["p90"][i], 2), round(tmin["mx"][i], 2),
            ])
    log.info("CSV saved → %s", csv_path)

def _plot_from_csv(csv_path: Path, out_png: Path, title: str):
    df = pd.read_csv(csv_path)
    x = range(len(df))

    plt.style.use("default")
    fig, ax = plt.subplots(figsize=(13, 5.5))

    # Tmax
    ax.fill_between(x, df["tmax_p25"], df["tmax_p75"], color="red", alpha=0.22, linewidth=0)
    ax.fill_between(x, df["tmax_p10"], df["tmax_p90"], color="red", alpha=0.08, linewidth=0)
    ax.plot(x, df["tmax_p50"], color="red", linewidth=2.8, label="T. máxima")
    ax.plot(x, df["tmax_p10"], "--", color="red", linewidth=1, alpha=0.7)
    ax.plot(x, df["tmax_p90"], "--", color="red", linewidth=1, alpha=0.7)

    # Tmin
    ax.fill_between(x, df["tmin_p25"], df["tmin_p75"], color="royalblue", alpha=0.22, linewidth=0)
    ax.fill_between(x, df["tmin_p10"], df["tmin_p90"], color="royalblue", alpha=0.08, linewidth=0)
    ax.plot(x, df["tmin_p50"], color="royalblue", linewidth=2.8, label="T. mínima")
    ax.plot(x, df["tmin_p10"], "--", color="royalblue", linewidth=1, alpha=0.7)
    ax.plot(x, df["tmin_p90"], "--", color="royalblue", linewidth=1, alpha=0.7)

    if len(df) > 10:
        ax.axvline(9.5, color="0.6", linewidth=1.5, alpha=0.6)

    ax.grid(which="major", color="0.88", linewidth=0.8)
    ax.set_xticks(list(x))
    ax.set_xticklabels(df["day_label"].tolist())

    ymin = min(df["tmin_p10"].min(), df["tmin_min"].min()) - 2
    ymax = max(df["tmax_p90"].max(), df["tmax_max"].max()) + 2
    ax.set_ylim(ymin, ymax)
    ax.set_xlim(-0.3, len(df) - 0.7)

    ax.set_title(title, fontsize=16, weight="bold")
    ax.set_ylabel("Temperatura (°C)")
    ax.legend(frameon=False, loc="upper left")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    plt.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_png, dpi=200, facecolor="white")
    plt.close()
    log.info("PNG saved → %s", out_png)

def resolve_location(args):
    if args.city:
        key = args.city.lower()
        if key not in CITIES:
            raise SystemExit(f"Ciudad '{args.city}' no existe. Opciones: {', '.join(CITIES.keys())}")
        name, lat, lon = CITIES[key]
        return name, lat, lon, key

    if args.lat is not None and args.lon is not None and args.name:
        slug = slugify(args.name)
        return args.name, float(args.lat), float(args.lon), slug

    raise SystemExit("Usa --city salamanca  o bien --name 'Mi Ciudad' --lat XX --lon YY")

def main():
    p = argparse.ArgumentParser(description="Extrae meteograma local desde GRIB global ENS.")
    p.add_argument("--grib", type=Path, default=DEFAULT_GRIB, help="GRIB global de entrada")
    p.add_argument("--city", type=str, help=f"Ciudad predefinida: {', '.join(CITIES.keys())}")
    p.add_argument("--name", type=str, help="Nombre localidad personalizada")
    p.add_argument("--lat", type=float, help="Latitud localidad personalizada")
    p.add_argument("--lon", type=float, help="Longitud localidad personalizada")
    p.add_argument("--out-csv", type=Path, default=None, help="Ruta CSV salida (opcional)")
    p.add_argument("--out-png", type=Path, default=None, help="Ruta PNG salida (opcional)")
    args = p.parse_args()

    name, lat, lon, slug = resolve_location(args)

    if not args.grib.exists():
        raise SystemExit(f"No existe GRIB: {args.grib}")

    out_csv = args.out_csv or (DEFAULT_DATA_DIR / f"ens_{slug}.csv")
    out_png = args.out_png or (DEFAULT_IMG_DIR / f"ens_meteograma_{slug}.png")

    log.info("Location: %s (lat=%.4f, lon=%.4f)", name, lat, lon)
    log.info("Reading GRIB: %s", args.grib)

    step_data = _collect_ens_t2m(args.grib, lat, lon)
    if not step_data:
        raise SystemExit("No se encontraron datos t2m en el GRIB para esa localidad.")

    dates, labels, tmin, tmax = _compute_daily_stats(step_data)
    _save_csv(out_csv, dates, labels, tmin, tmax)
    _plot_from_csv(out_csv, out_png, f"ECMWF ENS · {name}")

    log.info("Done.")

if __name__ == "__main__":
    main()
