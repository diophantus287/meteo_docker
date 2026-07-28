from flask import Flask, render_template, request
import os
import random
import math
import tempfile

app = Flask(__name__, template_folder="templates", static_folder="static")

PLOTS_FOLDER = "static/plots"

# Salamanca coordinates
SALAMANCA_LAT = 40.97
SALAMANCA_LON = -5.66

ENS_METEOGRAM_FILE = "ens_meteogram.png"


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
# ENS meteogram helpers
# ---------------------------------------------------------------------------

def _collect_ens_t2m(grib_path):
    """
    Open a GRIB file and extract 2 m temperature at Salamanca for all members
    and all steps.

    Returns
    -------
    dict  {step_hours (int): [celsius_value, ...]}
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
    tmin_stats : dict  {mn, p10, p25, p50, p75, p90, mx}  (list per day)
    tmax_stats : same structure
    """
    import numpy as np
    from datetime import datetime, timedelta, timezone

    today = datetime.now(timezone.utc).date()
    day_labels = []
    tmin_stats = {k: [] for k in ("mn", "p10", "p25", "p50", "p75", "p90", "mx")}
    tmax_stats = {k: [] for k in ("mn", "p10", "p25", "p50", "p75", "p90", "mx")}

    for day in range(1, n_days + 1):
        # 6-hourly steps that fall within this 24-h window
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


def _draw_box_whisker(ax, x, stats, i, color_fill, color_edge, color_median, half_w=0.28):
    """Draw a single box-and-whisker element on *ax* at horizontal position *x*."""
    import matplotlib.patches as mpatches

    mn   = stats["mn"][i]
    p10  = stats["p10"][i]
    p25  = stats["p25"][i]
    p50  = stats["p50"][i]
    p75  = stats["p75"][i]
    p90  = stats["p90"][i]
    mx   = stats["mx"][i]
    cap  = half_w * 0.6

    # Interquartile box (p25–p75)
    rect = mpatches.Rectangle(
        (x - half_w, p25), 2 * half_w, p75 - p25,
        facecolor=color_fill, edgecolor=color_edge,
        linewidth=1.5, alpha=0.75, zorder=3,
    )
    ax.add_patch(rect)

    # Median line
    ax.plot([x - half_w, x + half_w], [p50, p50],
            color=color_median, lw=2.5, zorder=4)

    # Whiskers (p10 and p90) with caps
    for y_inner, y_outer in [(p25, p10), (p75, p90)]:
        ax.plot([x, x], [y_inner, y_outer], color=color_edge, lw=1.5, zorder=2)
        ax.plot([x - cap, x + cap], [y_outer, y_outer], color=color_edge, lw=1.5, zorder=2)

    # Dotted extensions and tick marks for min / max
    for y_whisker, y_ext in [(p10, mn), (p90, mx)]:
        ax.plot([x, x], [y_whisker, y_ext], color=color_edge, lw=1.0, ls=":", zorder=2)
        ax.plot(x, y_ext, marker="_", ms=10, color=color_edge, mew=2.0, zorder=3)


def _plot_ens_meteogram(day_labels, tmin_stats, tmax_stats, output_path):
    """Create and save the ENS meteogram figure."""
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


def _generate_ens_meteogram():
    """
    Download ENS (cf + pf) 2 m temperature data, compute daily Tmin/Tmax
    distributions across all ensemble members, and save the meteogram plot.

    Returns None on success, or an error string on failure.
    """
    try:
        from ecmwf.opendata import Client
        import cfgrib  # noqa: F401 - verify library is available
    except ImportError as exc:
        return f"Dependencia no disponible: {exc}"

    # 6-hourly steps covering 7 forecast days
    steps = list(range(6, 169, 6))
    tempfiles = []

    try:
        client = Client()
        step_data = {}

        for fc_type in ("cf", "pf"):
            fd, path = tempfile.mkstemp(suffix=f"_{fc_type}.grib2")
            os.close(fd)
            tempfiles.append(path)
            client.retrieve(type=fc_type, param="2t", step=steps, target=path)
            for sh, vals in _collect_ens_t2m(path).items():
                step_data.setdefault(sh, []).extend(vals)

        if not step_data:
            return (
                "El archivo ENS GRIB se descargó pero no contiene el campo 2t. "
                "Prueba de nuevo más tarde."
            )

        day_labels, tmin_stats, tmax_stats = _compute_daily_stats(step_data)

        output = os.path.join(app.static_folder, "plots", ENS_METEOGRAM_FILE)
        _plot_ens_meteogram(day_labels, tmin_stats, tmax_stats, output)
        return None

    except Exception as exc:
        return f"Error generando meteograma ENS: {exc}"
    finally:
        for f in tempfiles:
            if os.path.exists(f):
                os.unlink(f)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/ecmwf", methods=["GET", "POST"])
def ecmwf():
    data = None
    error = None
    ens_error = None
    cache_bust = random.randint(10000, 99999)

    meteogram_path = os.path.join(app.static_folder, "plots", ENS_METEOGRAM_FILE)
    meteogram_exists = os.path.exists(meteogram_path)

    if request.method == "POST":
        action = request.form.get("action", "forecast")

        if action == "ens_meteogram":
            ens_error = _generate_ens_meteogram()
            meteogram_exists = os.path.exists(meteogram_path)

        else:  # action == "forecast"
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
        ens_error=ens_error,
        meteogram_exists=meteogram_exists,
        cache_bust=cache_bust,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
