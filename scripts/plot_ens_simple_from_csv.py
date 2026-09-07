#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = REPO_ROOT / "web" / "data"
DEFAULT_IMG_DIR = REPO_ROOT / "web" / "static" / "ecmwf_simple"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("plot_ens_simple_from_csv")


def _pick_first_existing(df: pd.DataFrame, candidates: list[str]) -> str:
    for c in candidates:
        if c in df.columns:
            return c
    raise KeyError(f"No existe ninguna columna de {candidates}")


def _to_datetime_series(df: pd.DataFrame) -> pd.Series:
    # Intentamos varias columnas posibles de fecha
    for c in ["date", "fecha", "valid_date", "day", "day_label"]:
        if c in df.columns:
            s = pd.to_datetime(df[c], errors="coerce")
            if s.notna().any():
                return s
    # Fallback: índice diario empezando hoy
    base = pd.Timestamp.now().normalize()
    return pd.Series([base + pd.Timedelta(days=i) for i in range(len(df))], index=df.index)


def _plot_one(csv_path: Path, out_png: Path, title: str) -> None:
    df = pd.read_csv(csv_path)

    col_tmin = _pick_first_existing(df, ["tmin_p50", "t2m_min_p50", "temp_min_p50"])
    col_tmax = _pick_first_existing(df, ["tmax_p50", "t2m_max_p50", "temp_max_p50"])
    col_pr = _pick_first_existing(df, ["pr_p50", "tp_p50", "precip_p50", "precipitation_p50"])

    x_dt = _to_datetime_series(df)

    tmin = pd.to_numeric(df[col_tmin], errors="coerce")
    tmax = pd.to_numeric(df[col_tmax], errors="coerce")
    pr = pd.to_numeric(df[col_pr], errors="coerce").fillna(0)

    fig, ax1 = plt.subplots(figsize=(12, 6.5))
    ax2 = ax1.twinx()

    # Precipitación (eje derecho)
    ax2.bar(
        x_dt,
        pr,
        width=0.7,
        color="#4c78a8",
        alpha=0.28,
        label="Precipitación p50 (%)",
        zorder=1,
    )

    # Temperatura (eje izquierdo)
    ax1.plot(x_dt, tmin, color="#2ca02c", linewidth=2.0, marker="o", ms=4, label="T mín p50 (°C)", zorder=3)
    ax1.plot(x_dt, tmax, color="#d62728", linewidth=2.0, marker="o", ms=4, label="T máx p50 (°C)", zorder=3)

    # Etiquetas de temperatura
    for xd, v in zip(x_dt, tmin):
        if np.isfinite(v):
            ax1.text(xd, v + 0.35, f"{v:.0f}", color="#2ca02c", fontsize=8, ha="center", va="bottom")
    for xd, v in zip(x_dt, tmax):
        if np.isfinite(v):
            ax1.text(xd, v - 0.35, f"{v:.0f}", color="#d62728", fontsize=8, ha="center", va="top")

    # Ejes y formato
    ax1.set_ylabel("Temperatura (°C)")
    ax2.set_ylabel("Precipitación p50 (%)", color="#4c78a8")
    ax2.tick_params(axis="y", colors="#4c78a8")

    # Rango temperatura compacto
    t_low = np.nanmin([tmin.min(), tmax.min()])
    t_high = np.nanmax([tmin.max(), tmax.max()])
    if np.isfinite(t_low) and np.isfinite(t_high) and t_high > t_low:
        pad = max(0.8, (t_high - t_low) * 0.08)
        ax1.set_ylim(t_low - pad, t_high + pad)

    # Rango precipitación
    pmax = float(pr.max()) if len(pr) else 0.0
    ax2.set_ylim(0, 100 if pmax <= 100 else pmax * 1.1)

    ax1.grid(True, axis="both", linestyle="--", color="0.82", alpha=0.8)
    ax1.set_axisbelow(True)

    # Fechas
    ax1.xaxis.set_major_locator(mdates.DayLocator(interval=1))
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%a\n%d/%m"))
    plt.setp(ax1.get_xticklabels(), rotation=0, ha="center", fontsize=9)

    # Título
    plot_ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    fig.suptitle(f"{title} · Plot: {plot_ts}", y=0.98, fontsize=13, weight="bold")

    # Leyenda combinada
    h1, l1 = ax1.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax1.legend(h1 + h2, l1 + l2, loc="upper left", frameon=True)

    fig.tight_layout(rect=[0, 0, 1, 0.96])

    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, dpi=180, facecolor="white")
    plt.close(fig)
    log.info("PNG saved -> %s", out_png)


def main() -> None:
    p = argparse.ArgumentParser(description="Pinta meteogramas simples desde CSV ENS (p50).")
    p.add_argument("--csv", action="append", default=[], help="CSV concreto (repetible)")
    p.add_argument("--all", action="store_true", help="Pintar todos los ens_*.csv de web/data")
    args = p.parse_args()

    csv_files: list[Path] = []
    if args.all:
        csv_files.extend(sorted(DEFAULT_DATA_DIR.glob("ens_*.csv")))
    for c in args.csv:
        csv_files.append(Path(c))

    if not csv_files:
        raise SystemExit("Usa --all o al menos un --csv ruta.csv")

    for csv_path in csv_files:
        if not csv_path.exists():
            log.warning("No existe CSV: %s", csv_path)
            continue

        slug = csv_path.stem.replace("ens_", "", 1)
        title = f"ECMWF ENS SIMPLE · {slug.replace('_', ' ').title()}"
        out_png = DEFAULT_IMG_DIR / f"ens_simple_{slug}.png"
        _plot_one(csv_path, out_png, title)

    log.info("Done.")


if __name__ == "__main__":
    main()
