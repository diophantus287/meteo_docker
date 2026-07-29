#!/usr/bin/env python3
"""
Batch script: download ENS ECMWF Open Data for Salamanca and save meteogram PNG.

Usage
-----
    python scripts/build_ens_meteogram.py [--output PATH] [--steps-max 168]

    --output     Destination PNG file.
                 Default: web/static/plots/ens_meteogram.png  (relative to
                 the repository root, i.e. one level above this script).
    --steps-max  Last forecast step (hours, multiple of 6).  Default: 168.

Exit codes
----------
    0  success
    1  runtime error (message printed to stderr)
"""

import argparse
import os
import sys
import tempfile

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SALAMANCA_LAT = 40.97
SALAMANCA_LON = -5.66

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_SCRIPT_DIR)
DEFAULT_OUTPUT = os.path.join(_REPO_ROOT, "web", "static", "plots", "ens_meteogram.png")


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _collect_ens_t2m(grib_path):
    """
    Open a GRIB file and extract 2 m temperature at Salamanca for all members
    and all steps.

    Returns
    -------
    dict  {step_hours (int): [celsius_values, ...]}
    """
    import cfgrib
    import numpy as np

    result = {}
    for ds in cfgrib.open_datasets(grib_path):
        if "t2m" not in ds.data_vars:
            continue
        da = ds["t2m"].sel(
            latitude=SALAMANCA_LAT, longitude=SALAMANCA_LON, method="nearest"
        )
        if "step" in da.dims:
            for i in range(len(da.step)):
                sv = da.step.values[i]
                sh = int(sv / np.timedelta64(1, "h"))
                row = da.isel(step=i)
                members = np.atleast_1d(row.values - 273.15).flatten().tolist()
                result.setdefault(sh, []).extend(members)
        else:
            sv = da.step.values
            sh = int(sv / np.timedelta64(1, "h"))
            members = np.atleast_1d(da.values - 273.15).flatten().tolist()
            result.setdefault(sh, []).extend(members)
    return result


def _compute_daily_stats(step_data, n_days=7):
    """
    Derive per-day Tmin / Tmax distributions from 6-hourly ensemble values.

    Parameters
    ----------
    step_data : dict  {step_hours: [celsius_vals]}
    n_days    : int

    Returns
    -------
    day_labels : list[str]
    tmin_stats : dict  {mn, p10, p25, p50, p75, p90, mx}  (list with one value per day)
    tmax_stats : same structure
    """
    import numpy as np
    from datetime import datetime, timedelta, timezone

    today = datetime.now(timezone.utc).date()
    day_labels = []
    tmin_stats = {k: [] for k in ("mn", "p10", "p25", "p50", "p75", "p90", "mx")}
    tmax_stats = {k: [] for k in ("mn", "p10", "p25", "p50", "p75", "p90", "mx")}

    for day in range(1, n_days + 1):
        day_steps = list(range((day - 1) * 24 + 6, day * 24 + 1, 6))
        available = {sh: np.array(step_data[sh]) for sh in day_steps if sh in step_data}

        if len(available) < 2:
            continue

        n_mem = min(len(v) for v in available.values())
        if n_mem == 0:
            continue

        # shape: (n_steps_in_day, n_members)
        arr = np.array([available[sh][:n_mem] for sh in sorted(available)])
        member_tmin = arr.min(axis=0)
        member_tmax = arr.max(axis=0)

        dt = today + timedelta(days=day - 1)
        day_labels.append(dt.strftime("%a\n%d %b"))

        for stats, mvals in [(tmin_stats, member_tmin), (tmax_stats, member_tmax)]:
            stats["mn"].append(float(np.min(mvals)))
            stats["p10"].append(float(np.percentile(mvals, 10)))
            stats["p25"].append(float(np.percentile(mvals, 25)))
            stats["p50"].append(float(np.percentile(mvals, 50)))
            stats["p75"].append(float(np.percentile(mvals, 75)))
            stats["p90"].append(float(np.percentile(mvals, 90)))
            stats["mx"].append(float(np.max(mvals)))

    if not day_labels:
        raise ValueError(
            "No hay suficientes datos ENS para generar el meteograma diario."
        )

    return day_labels, tmin_stats, tmax_stats


# ---------------------------------------------------------------------------
# Plot helpers
# ---------------------------------------------------------------------------

def _draw_box_whisker(ax, x, stats, i, color_fill, color_edge, color_median, half_w=0.28):
    """Draw a single box-and-whisker element on *ax* at horizontal position *x*."""
    import matplotlib.patches as mpatches

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

    ax.plot([x - half_w, x + half_w], [p50, p50],
            color=color_median, lw=2.5, zorder=4)

    for y_inner, y_outer in [(p25, p10), (p75, p90)]:
        ax.plot([x, x], [y_inner, y_outer], color=color_edge, lw=1.5, zorder=2)
        ax.plot([x - cap, x + cap], [y_outer, y_outer], color=color_edge, lw=1.5, zorder=2)

    for y_whisker, y_ext in [(p10, mn), (p90, mx)]:
        ax.plot([x, x], [y_whisker, y_ext], color=color_edge, lw=1.0, ls=":", zorder=2)
        ax.plot(x, y_ext, marker="_", ms=10, color=color_edge, mew=2.0, zorder=3)


def _plot_ens_meteogram(day_labels, tmin_stats, tmax_stats, output_path):
    """Create and save the ENS meteogram figure to *output_path*."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.lines import Line2D
    import numpy as np

    n = len(day_labels)
    x = np.arange(n)
    offset = 0.22

    fig, ax = plt.subplots(figsize=(max(8, n * 1.5), 6))
    fig.patch.set_facecolor("#f5f5f5")
    ax.set_facecolor("#f5f5f5")

    for i in range(n):
        _draw_box_whisker(
            ax, x[i] + offset, tmax_stats, i,
            "#ff6666", "#cc0000", "#880000",
        )
        _draw_box_whisker(
            ax, x[i] - offset, tmin_stats, i,
            "#6699ff", "#0044cc", "#003399",
        )

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
        "Meteograma ENS ECMWF — Salamanca (40.97°N, 5.66°W)",
        fontsize=13, pad=12,
    )
    ax.yaxis.grid(True, ls="--", alpha=0.4, color="gray")
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    legend_elements = [
        mpatches.Patch(fc="#ff6666", ec="#cc0000", alpha=0.75, label="Tmax"),
        mpatches.Patch(fc="#6699ff", ec="#0044cc", alpha=0.75, label="Tmin"),
        Line2D([0], [0], color="gray", lw=4, alpha=0.6, label="Caja: p25–p75"),
        Line2D([0], [0], color="gray", lw=1.5, label="Bigotes: p10–p90"),
        Line2D([0], [0], color="gray", lw=1, ls=":", label="Extremos: mín–máx"),
    ]
    ax.legend(handles=legend_elements, loc="upper right", fontsize=9, framealpha=0.8)

    plt.tight_layout()
    plt.savefig(
        output_path, dpi=100, bbox_inches="tight",
        facecolor=fig.get_facecolor(),
    )
    plt.close(fig)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def build(output_path, steps_max=168):
    """
    Download ENS (cf + pf) 2 m temperature, compute daily Tmin/Tmax
    distributions and save the meteogram PNG.

    Raises on failure so the caller / cron wrapper can log it.
    """
    from ecmwf.opendata import Client

    steps = list(range(6, steps_max + 1, 6))
    tempfiles = []

    try:
        client = Client()
        step_data = {}

        for fc_type in ("cf", "pf"):
            fd, path = tempfile.mkstemp(suffix=f"_{fc_type}.grib2")
            os.close(fd)
            tempfiles.append(path)
            print(f"[ens-batch] Descargando {fc_type} 2t …", flush=True)
            client.retrieve(type=fc_type, param="2t", step=steps, target=path)
            for sh, vals in _collect_ens_t2m(path).items():
                step_data.setdefault(sh, []).extend(vals)

        if not step_data:
            raise ValueError(
                "El archivo ENS GRIB se descargó pero no contiene el campo 2t."
            )

        print("[ens-batch] Calculando estadísticas diarias …", flush=True)
        day_labels, tmin_stats, tmax_stats = _compute_daily_stats(step_data)

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        # Write to a temporary file next to the target, then rename atomically
        tmp_out = output_path + ".tmp"
        try:
            _plot_ens_meteogram(day_labels, tmin_stats, tmax_stats, tmp_out)
            os.replace(tmp_out, output_path)
        except Exception:
            if os.path.exists(tmp_out):
                os.unlink(tmp_out)
            raise
        print(f"[ens-batch] Meteograma guardado en {output_path}", flush=True)

    finally:
        for f in tempfiles:
            if os.path.exists(f):
                os.unlink(f)


def main():
    parser = argparse.ArgumentParser(
        description="Genera el meteograma ENS ECMWF para Salamanca."
    )
    parser.add_argument(
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"Ruta del PNG de salida. Por defecto: {DEFAULT_OUTPUT}",
    )
    parser.add_argument(
        "--steps-max",
        type=int,
        default=168,
        help="Último paso de previsión en horas (múltiplo de 6). Por defecto: 168.",
    )
    args = parser.parse_args()

    try:
        build(args.output, steps_max=args.steps_max)
    except Exception as exc:
        print(f"[ens-batch] ERROR: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
