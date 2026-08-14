#!/usr/bin/env python3
"""
Build ECMWF ENS meteogram for Salamanca.

Downloads 51-member ENS 2 m temperature forecasts (steps 6–168 h, every 6 h),
computes daily Tmin / Tmax distributions across all members, and saves:

    web/data/ens_salamanca.csv       – daily stats table
    web/data/ens_meteograma.json     – machine-readable summary
    web/static/plots/ens_meteograma.png – meteogram image
como pue
Usage
-----
    python scripts/build_ens_meteogram.py
    python scripts/build_ens_meteogram.py --csv /tmp/ens.csv --png /tmp/ens.png
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
import earthkit.data as ekd

import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent

DEFAULT_CSV  = REPO_ROOT / "web" / "data" / "ens_salamanca.csv"
DEFAULT_JSON = REPO_ROOT / "web" / "data" / "ens_meteograma.json"
DEFAULT_PNG  = REPO_ROOT / "web" / "static" / "ecmwf" / "ens_meteograma.png"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SALAMANCA_LAT = 40.97
SALAMANCA_LON = -5.66
STEPS = list(range(6, 361, 6))   # 6..360 cada 6h (usa todo lo que exista)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("ens_meteogram")


# ---------------------------------------------------------------------------
# GRIB parsing
# ---------------------------------------------------------------------------

def _collect_ens_t2m(grib_path: str) -> dict[int, list[float]]:
    """
    Parse a GRIB2 file and return ``{step_hours: [celsius_values]}``.

    Handles multi-dataset files (cfgrib returns one xarray.Dataset per
    unique combination of GRIB metadata) and gracefully skips datasets
    that do not contain the ``t2m`` variable.
    """
    import cfgrib  # local import so the module can be imported without cfgrib

    result: dict[int, list[float]] = {}

    try:
        datasets = cfgrib.open_datasets(grib_path)
    except Exception as exc:
        log.warning("cfgrib could not open %s: %s", grib_path, exc)
        return result

    for ds in datasets:
        if "t2m" not in ds.data_vars:
            continue
        try:
            da = ds["t2m"].sel(
                latitude=SALAMANCA_LAT,
                longitude=SALAMANCA_LON,
                method="nearest",
            )
        except Exception as exc:
            log.warning("Could not select Salamanca point: %s", exc)
            continue

        if "step" in da.dims:
            for i in range(len(da.step)):
                sv = da.step.values[i]
                sh = int(sv / np.timedelta64(1, "h"))
                vals = np.atleast_1d(da.isel(step=i).values - 273.15).flatten().tolist()
                result.setdefault(sh, []).extend(vals)
        else:
            sv = da.step.values
            sh = int(sv / np.timedelta64(1, "h"))
            vals = np.atleast_1d(da.values - 273.15).flatten().tolist()
            result.setdefault(sh, []).extend(vals)

    return result


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------

def _compute_daily_stats(
    step_data: dict[int, list[float]],
) -> tuple[list[datetime.date], list[str], dict, dict]:
    """
    Derive per-day Tmin / Tmax distributions from ALL available 6-hourly ENS values.
    Days are inferred from available steps (no fixed n_days limit).
    """
    today = datetime.now(timezone.utc).date()

    dates: list[datetime.date] = []
    day_labels: list[str] = []
    tmin_stats: dict[str, list[float]] = {k: [] for k in ("mn", "p10", "p25", "p50", "p75", "p90", "mx")}
    tmax_stats: dict[str, list[float]] = {k: [] for k in ("mn", "p10", "p25", "p50", "p75", "p90", "mx")}

    if not step_data:
        raise ValueError("No step data available.")

    # Map steps -> forecast day index (1..N), using UTC windows:
    # day 1 => steps 6,12,18,24 ; day 2 => 30..48 ; etc.
    day_to_steps: dict[int, list[int]] = {}
    for sh in sorted(step_data):
        if sh < 6:
            continue
        day_idx = ((sh - 6) // 24) + 1
        day_to_steps.setdefault(day_idx, []).append(sh)

    for day_idx in sorted(day_to_steps):
        day_steps = sorted(day_to_steps[day_idx])
        available = {sh: np.array(step_data[sh], dtype=float) for sh in day_steps if sh in step_data}

        # Need at least 2 times in the day to compute meaningful min/max
        if len(available) < 2:
            log.warning("Day %d: only %d step(s) available, skipping.", day_idx, len(available))
            continue

        n_mem = min(len(v) for v in available.values())
        if n_mem == 0:
            continue

        arr = np.array([available[sh][:n_mem] for sh in sorted(available)])  # shape: (steps_in_day, members)
        member_tmin = arr.min(axis=0)
        member_tmax = arr.max(axis=0)

        dt = today + timedelta(days=day_idx - 1)
        dates.append(dt)
        day_labels.append(dt.strftime("%a\n%d %b"))

        for stats, mvals in ((tmin_stats, member_tmin), (tmax_stats, member_tmax)):
            stats["mn"].append(float(np.min(mvals)))
            stats["p10"].append(float(np.percentile(mvals, 10)))
            stats["p25"].append(float(np.percentile(mvals, 25)))
            stats["p50"].append(float(np.percentile(mvals, 50)))
            stats["p75"].append(float(np.percentile(mvals, 75)))
            stats["p90"].append(float(np.percentile(mvals, 90)))
            stats["mx"].append(float(np.max(mvals)))

    if not dates:
        raise ValueError("No sufficient ENS data to compute daily statistics.")

    return dates, day_labels, tmin_stats, tmax_stats


# ---------------------------------------------------------------------------
# Plot
# ---------------------------------------------------------------------------

def _draw_box_whisker(
    ax,
    x: float,
    stats: dict,
    i: int,
    color_fill: str,
    color_edge: str,
    color_median: str,
    half_w: float = 0.28,
) -> None:
    """Draw a single box-and-whisker element on *ax* at position *x*."""
    mn  = stats["mn"][i]
    p10 = stats["p10"][i]
    p25 = stats["p25"][i]
    p50 = stats["p50"][i]
    p75 = stats["p75"][i]
    p90 = stats["p90"][i]
    mx  = stats["mx"][i]
    cap = half_w * 0.6

    rect = mpatches.Rectangle(
        (x - half_w, p25), 2 * half_w, p75 - p25,
        facecolor=color_fill, edgecolor=color_edge,
        linewidth=1.5, alpha=0.75, zorder=3,
    )
    ax.add_patch(rect)
    ax.plot([x - half_w, x + half_w], [p50, p50], color=color_median, lw=2.5, zorder=4)

    for y_inner, y_outer in [(p25, p10), (p75, p90)]:
        ax.plot([x, x], [y_inner, y_outer], color=color_edge, lw=1.5, zorder=2)
        ax.plot([x - cap, x + cap], [y_outer, y_outer], color=color_edge, lw=1.5, zorder=2)

    for y_whisker, y_ext in [(p10, mn), (p90, mx)]:
        ax.plot([x, x], [y_whisker, y_ext], color=color_edge, lw=1.0, ls=":", zorder=2)
        ax.plot(x, y_ext, marker="_", ms=10, color=color_edge, mew=2.0, zorder=3)


def _plot_meteogram(
    day_labels: list[str],
    tmin_stats: dict,
    tmax_stats: dict,
    run_label: str,
    output_path: Path,
) -> None:
    """Create and save the ENS meteogram PNG."""
    n = len(day_labels)
    x = np.arange(n)
    offset = 0.22

    fig, ax = plt.subplots(figsize=(max(8, n * 1.5), 6))
    fig.patch.set_facecolor("#f5f5f5")
    ax.set_facecolor("#f5f5f5")

    for i in range(n):
        _draw_box_whisker(ax, x[i] + offset, tmax_stats, i, "#ff6666", "#cc0000", "#880000")
        _draw_box_whisker(ax, x[i] - offset, tmin_stats, i, "#6699ff", "#0044cc", "#003399")

    ax.set_xlim(-0.7, n - 0.3)
    all_vals = (
        tmin_stats["mn"] + tmin_stats["mx"]
        + tmax_stats["mn"] + tmax_stats["mx"]
    )
    ax.set_ylim(min(all_vals) - 2, max(all_vals) + 2)
    ax.set_xticks(x)
    ax.set_xticklabels(day_labels, fontsize=10)
    ax.set_ylabel("Temperatura (°C)", fontsize=11)
    ax.set_title(
        f"Meteograma ENS ECMWF — Salamanca (40.97°N, 5.66°W)\n{run_label}",
        fontsize=12, pad=10,
    )
    ax.yaxis.grid(True, ls="--", alpha=0.4, color="gray")
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    #legend_elements = [
    #    mpatches.Patch(fc="#ff6666", ec="#cc0000", alpha=0.75, label="Tmax"),
    #    mpatches.Patch(fc="#6699ff", ec="#0044cc", alpha=0.75, label="Tmin"),
    #    Line2D([0], [0], color="gray", lw=4, alpha=0.6, label="Caja: p25–p75"),
    #    Line2D([0], [0], color="gray", lw=1.5, label="Bigotes: p10–p90"),
    #    Line2D([0], [0], color="gray", lw=1, ls=":", label="Extremos: mín–máx"),
    #]
    #ax.legend(handles=legend_elements, loc="upper right", fontsize=9, framealpha=0.8)

    plt.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_path, dpi=100, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    log.info("PNG saved → %s", output_path)


# ---------------------------------------------------------------------------
# Artifact writers
# ---------------------------------------------------------------------------

def _save_csv(
    csv_path: Path,
    dates: list,
    day_labels: list[str],
    tmin_stats: dict,
    tmax_stats: dict,
) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    headers = [
        "date", "day_label",
        "tmax_min", "tmax_p10", "tmax_p25", "tmax_p50", "tmax_p75", "tmax_p90", "tmax_max",
        "tmin_min", "tmin_p10", "tmin_p25", "tmin_p50", "tmin_p75", "tmin_p90", "tmin_max",
    ]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for i, (d, lbl) in enumerate(zip(dates, day_labels)):
            writer.writerow([
                d.strftime("%Y-%m-%d"),
                lbl.replace("\n", " "),
                round(tmax_stats["mn"][i],  2),
                round(tmax_stats["p10"][i], 2),
                round(tmax_stats["p25"][i], 2),
                round(tmax_stats["p50"][i], 2),
                round(tmax_stats["p75"][i], 2),
                round(tmax_stats["p90"][i], 2),
                round(tmax_stats["mx"][i],  2),
                round(tmin_stats["mn"][i],  2),
                round(tmin_stats["p10"][i], 2),
                round(tmin_stats["p25"][i], 2),
                round(tmin_stats["p50"][i], 2),
                round(tmin_stats["p75"][i], 2),
                round(tmin_stats["p90"][i], 2),
                round(tmin_stats["mx"][i],  2),
            ])
    log.info("CSV saved → %s", csv_path)


def _save_json(
    json_path: Path,
    dates: list,
    tmin_stats: dict,
    tmax_stats: dict,
    generated_at: datetime,
) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    days_list = []
    for i, d in enumerate(dates):
        days_list.append({
            "date": d.strftime("%Y-%m-%d"),
            "tmax": {
                "min": round(tmax_stats["mn"][i],  2),
                "p10": round(tmax_stats["p10"][i], 2),
                "p25": round(tmax_stats["p25"][i], 2),
                "p50": round(tmax_stats["p50"][i], 2),
                "p75": round(tmax_stats["p75"][i], 2),
                "p90": round(tmax_stats["p90"][i], 2),
                "max": round(tmax_stats["mx"][i],  2),
            },
            "tmin": {
                "min": round(tmin_stats["mn"][i],  2),
                "p10": round(tmin_stats["p10"][i], 2),
                "p25": round(tmin_stats["p25"][i], 2),
                "p50": round(tmin_stats["p50"][i], 2),
                "p75": round(tmin_stats["p75"][i], 2),
                "p90": round(tmin_stats["p90"][i], 2),
                "max": round(tmin_stats["mx"][i],  2),
            },
        })
    payload = {
        "generated_at": generated_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "location": {"name": "Salamanca", "lat": SALAMANCA_LAT, "lon": SALAMANCA_LON},
        "days": days_list,
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    log.info("JSON saved → %s", json_path)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def build(csv_path: Path, json_path: Path, png_path: Path) -> None:
    """Download ENS data, compute stats, and save all artifacts."""

    generated_at = datetime.now(timezone.utc)
    run_label = f"Generado: {generated_at.strftime('%Y-%m-%d %H:%M UTC')}"

    step_data = {}
    tmp_files = []

    try:
        log.info("Downloading ENS...")

        ds = ekd.from_source(
            "ecmwf-open-data",
            stream="enfo",
            type="pf",
            param="2t",
            step=STEPS,
            number=range(1, 51),
        )

        fd, tmp_path = tempfile.mkstemp(suffix=".grib")
        os.close(fd)
        tmp_files.append(tmp_path)

        ds.save(tmp_path)

        log.info("Parsing %s...", tmp_path)

        parsed = _collect_ens_t2m(tmp_path)

        if not parsed:
            log.warning("No t2m data found")

        for sh, vals in parsed.items():
            step_data.setdefault(sh, []).extend(vals)

    finally:
        for f in tmp_files:
            if os.path.exists(f):
                os.unlink(f)

    if not step_data:
        log.error(
            "No ENS data could be parsed. "
            "Check that cfgrib and libeccodes are correctly installed."
        )
        sys.exit(1)

    log.info("Steps available: %s", sorted(step_data))

    dates, day_labels, tmin_stats, tmax_stats = _compute_daily_stats(step_data)
    log.info("Daily stats computed for %d days.", len(dates))

    _save_csv(csv_path, dates, day_labels, tmin_stats, tmax_stats)
    _save_json(json_path, dates, tmin_stats, tmax_stats, generated_at)
    _plot_meteogram(day_labels, tmin_stats, tmax_stats, run_label, png_path)

    log.info("All artifacts saved successfully.")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build ECMWF ENS meteogram for Salamanca.")
    p.add_argument("--csv",  type=Path, default=DEFAULT_CSV,  help="Output CSV path")
    p.add_argument("--json", type=Path, default=DEFAULT_JSON, help="Output JSON path")
    p.add_argument("--png",  type=Path, default=DEFAULT_PNG,  help="Output PNG path")
    return p.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    build(args.csv, args.json, args.png)
