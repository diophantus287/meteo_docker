#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import logging
import unicodedata
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_GRIB = REPO_ROOT / "data" / "ecmwf" / "global" / "ecmwf_ens_global_latest.grib"
DEFAULT_DATA_DIR = REPO_ROOT / "web" / "data"

CITIES = {
    "salamanca": ("Salamanca", 40.97, -5.66),
    "madrid": ("Madrid", 40.4168, -3.7038),
    "barcelona": ("Barcelona", 41.3874, 2.1686),
    "valencia": ("Valencia", 39.4699, -0.3763),
    "sevilla": ("Sevilla", 37.3891, -5.9845),
    "vilanova_de_milfontes": ("Vila Nova de Milfontes", 37.7238, -8.7828),
    "portimao": ("Portimão", 37.1366, -8.5378),
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("ens_to_csv")


def slugify(text: str) -> str:
    txt = unicodedata.normalize("NFKD", text)
    txt = txt.encode("ascii", "ignore").decode("ascii")
    return txt.lower().strip().replace(" ", "_")


def _open_ens_datasets(grib_path: Path):
    import cfgrib
    return cfgrib.open_datasets(str(grib_path))


def _extract_step_member_values(datasets, var_name: str, lat: float, lon: float, transform=None) -> dict[int, list[float]]:
    result: dict[int, list[float]] = {}
    for ds in datasets:
        if var_name not in ds.data_vars:
            continue
        try:
            da = ds[var_name].sel(latitude=lat, longitude=lon, method="nearest")
        except Exception:
            continue
        if "step" not in da.dims:
            continue

        for i in range(len(da.step)):
            step_h = int(da.step.values[i] / np.timedelta64(1, "h"))
            vals = np.atleast_1d(da.isel(step=i).values).astype(float).flatten()
            if transform is not None:
                vals = transform(vals)
            result.setdefault(step_h, []).extend(vals.tolist())
    return result


def _compute_daily_temp_stats(step_data_c: dict[int, list[float]]):
    today = datetime.now(timezone.utc).date()
    dates, labels = [], []
    tmin = {k: [] for k in ("mn", "p10", "p25", "p50", "p75", "p90", "mx")}
    tmax = {k: [] for k in ("mn", "p10", "p25", "p50", "p75", "p90", "mx")}

    day_to_steps: dict[int, list[int]] = {}
    for sh in sorted(step_data_c):
        if sh < 6:
            continue
        day_idx = ((sh - 6) // 24) + 1
        day_to_steps.setdefault(day_idx, []).append(sh)

    for day_idx in sorted(day_to_steps):
        steps = sorted(day_to_steps[day_idx])
        available = {sh: np.array(step_data_c[sh], dtype=float) for sh in steps if sh in step_data_c}
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
        raise RuntimeError("No hay suficientes datos de temperatura para estadísticos diarios.")
    return dates, labels, tmin, tmax


def _compute_daily_precip_stats(tp_step_mm: dict[int, list[float]], n_days: int):
    if not tp_step_mm:
        z = [0.0] * n_days
        return {"p10": z.copy(), "p25": z.copy(), "p50": z.copy(), "p75": z.copy(), "p90": z.copy(), "mx": z.copy()}

    sorted_steps = sorted(tp_step_mm)
    n_mem = min(len(tp_step_mm[s]) for s in sorted_steps)
    if n_mem == 0:
        z = [0.0] * n_days
        return {"p10": z.copy(), "p25": z.copy(), "p50": z.copy(), "p75": z.copy(), "p90": z.copy(), "mx": z.copy()}

    tp_acc = {s: np.array(tp_step_mm[s][:n_mem], dtype=float) for s in sorted_steps}

    tp_inc = {}
    prev_s = None
    for s in sorted_steps:
        if prev_s is None:
            inc = np.maximum(tp_acc[s], 0.0)
        else:
            inc = np.maximum(tp_acc[s] - tp_acc[prev_s], 0.0)
        tp_inc[s] = inc
        prev_s = s

    day_member_totals = []
    for day_idx in range(1, n_days + 1):
        day_steps = [s for s in sorted_steps if ((s - 6) // 24 + 1) == day_idx and s >= 6]
        if not day_steps:
            day_member_totals.append(np.zeros(n_mem, dtype=float))
            continue
        acc = np.zeros(n_mem, dtype=float)
        for s in day_steps:
            acc += tp_inc[s]
        day_member_totals.append(acc)

    p = {"p10": [], "p25": [], "p50": [], "p75": [], "p90": [], "mx": []}
    for vals in day_member_totals:
        p["p10"].append(float(np.percentile(vals, 10)))
        p["p25"].append(float(np.percentile(vals, 25)))
        p["p50"].append(float(np.percentile(vals, 50)))
        p["p75"].append(float(np.percentile(vals, 75)))
        p["p90"].append(float(np.percentile(vals, 90)))
        p["mx"].append(float(np.max(vals)))
    return p


def _save_csv(csv_path: Path, dates, labels, tmin, tmax, pr):
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    headers = [
        "date", "day_label",
        "tmax_min", "tmax_p10", "tmax_p25", "tmax_p50", "tmax_p75", "tmax_p90", "tmax_max",
        "tmin_min", "tmin_p10", "tmin_p25", "tmin_p50", "tmin_p75", "tmin_p90", "tmin_max",
        "pr_p10", "pr_p25", "pr_p50", "pr_p75", "pr_p90", "pr_max",
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
                round(pr["p10"][i], 2), round(pr["p25"][i], 2), round(pr["p50"][i], 2),
                round(pr["p75"][i], 2), round(pr["p90"][i], 2), round(pr["mx"][i], 2),
            ])
    log.info("CSV saved → %s", csv_path)


def _resolve_locations(args):
    locations = []
    for city in args.city:
        key = city.lower()
        if key not in CITIES:
            raise SystemExit(f"Ciudad '{city}' no existe. Opciones: {', '.join(CITIES.keys())}")
        name, lat, lon = CITIES[key]
        locations.append((name, float(lat), float(lon), key))

    if args.name is not None or args.lat is not None or args.lon is not None:
        if not (args.name and args.lat is not None and args.lon is not None):
            raise SystemExit("Para localidad personalizada usa --name, --lat y --lon juntos.")
        locations.append((args.name, float(args.lat), float(args.lon), slugify(args.name)))

    if not locations:
        raise SystemExit("Indica al menos una localidad con --city ...")
    return locations


def main():
    p = argparse.ArgumentParser(description="Genera CSV ENS local desde GRIB global (t2m + tp).")
    p.add_argument("--grib", type=Path, default=DEFAULT_GRIB)
    p.add_argument("--city", action="append", default=[])
    p.add_argument("--name", type=str)
    p.add_argument("--lat", type=float)
    p.add_argument("--lon", type=float)
    args = p.parse_args()

    if not args.grib.exists():
        raise SystemExit(f"No existe GRIB: {args.grib}")

    locations = _resolve_locations(args)
    log.info("Opening GRIB once: %s", args.grib)
    datasets = _open_ens_datasets(args.grib)

    for name, lat, lon, slug in locations:
        log.info("Location: %s (lat=%.4f, lon=%.4f)", name, lat, lon)

        t2m_step_c = _extract_step_member_values(datasets, "t2m", lat, lon, transform=lambda a: a - 273.15)
        if not t2m_step_c:
            log.warning("No t2m para %s. Se omite.", name)
            continue

        tp_step_mm = _extract_step_member_values(datasets, "tp", lat, lon, transform=lambda a: np.maximum(a, 0.0) * 1000.0)

        dates, labels, tmin, tmax = _compute_daily_temp_stats(t2m_step_c)
        pr = _compute_daily_precip_stats(tp_step_mm, n_days=len(dates))

        out_csv = DEFAULT_DATA_DIR / f"ens_{slug}.csv"
        _save_csv(out_csv, dates, labels, tmin, tmax, pr)

    log.info("Done.")


if __name__ == "__main__":
    main()
