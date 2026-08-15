#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = REPO_ROOT / "web" / "data"
DEFAULT_IMG_DIR = REPO_ROOT / "web" / "static" / "ecmwf"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("plot_ens_from_csv")


def _draw_box_from_quantiles(ax, x, q10, q25, q50, q75, q90, color, width=0.28, edge="0.25", alpha=0.9):
    # Caja q25-q75
    rect = plt.Rectangle(
        (x - width / 2, q25),
        width,
        max(q75 - q25, 0.001),
        facecolor=color,
        edgecolor=edge,
        linewidth=1.0,
        alpha=alpha,
        zorder=3,
    )
    ax.add_patch(rect)

    # Bigotes q10-q90
    ax.vlines(x, q10, q90, color=edge, linewidth=1.0, zorder=3)

    # Tapas de bigote
    cap = width * 0.35
    ax.hlines(q10, x - cap / 2, x + cap / 2, color=edge, linewidth=1.0, zorder=3)
    ax.hlines(q90, x - cap / 2, x + cap / 2, color=edge, linewidth=1.0, zorder=3)

    # Mediana
    ax.hlines(q50, x - width / 2, x + width / 2, color=edge, linewidth=1.3, zorder=4)


def _plot_one(csv_path: Path, out_png: Path, title: str):
    df = pd.read_csv(csv_path)
    x = np.arange(len(df))

    plt.style.use("default")
    fig, (ax_p, ax_t) = plt.subplots(
        2, 1, figsize=(14, 8.5), sharex=True, gridspec_kw={"height_ratios": [1.2, 1.8]}
    )


    # -------------------- PRECI (arriba) --------------------
    ax_p.set_title("Total Precipitation (mm/24h)", loc="left", fontsize=12, pad=8, color="0.25")

    for i in x:
        p10 = float(df.loc[i, "pr_p10"])
        p25 = float(df.loc[i, "pr_p25"])
        p50 = float(df.loc[i, "pr_p50"])
        p75 = float(df.loc[i, "pr_p75"])
        p90 = float(df.loc[i, "pr_p90"])

        # Caja amarilla estilo ECMWF
        _draw_box_from_quantiles(
            ax_p, i, p10, p25, p50, p75, p90,
            color="#f0c74f", edge="0.35", width=0.22, alpha=0.95
        )
        # Punto verde en la mediana (visual tipo ejemplo)
        ax_p.scatter(i, p50, s=14, color="#3aa657", zorder=5)

    ax_p.set_ylabel("mm")
    ax_p.grid(True, axis="both", color="0.85", linewidth=0.8, alpha=0.55)
    ax_p.set_axisbelow(True)
    ax_p.spines["top"].set_color("0.70")
    ax_p.spines["right"].set_color("0.70")
    ax_p.spines["left"].set_color("0.60")
    ax_p.spines["bottom"].set_color("0.60")



    # --- PRECI: margen superior más ajustado ---
    pmax = float(df["pr_p90"].max())
    if not np.isfinite(pmax) or pmax <= 0:
        ax_p.set_ylim(0, 1.0)
    else:
        # margen pequeño (10%) + mínimo visual
        ax_p.set_ylim(0, pmax * 1.10 + 0.2)

    # -------------------- TEMPERATURA (abajo) --------------------
    ax_t.set_title("2m min/max Temperature (°C) (ENS)", loc="left", fontsize=12, pad=8, color="0.25")

    for i in x:
        # Tmax (rojo) desplazado a la izquierda
        _draw_box_from_quantiles(
            ax_t, i - 0.12,
            float(df.loc[i, "tmax_p10"]),
            float(df.loc[i, "tmax_p25"]),
            float(df.loc[i, "tmax_p50"]),
            float(df.loc[i, "tmax_p75"]),
            float(df.loc[i, "tmax_p90"]),
            color="red",
            edge="0.25",
            width=0.22,
            alpha=0.9,
        )

        # Tmin (azul) desplazado a la derecha
        _draw_box_from_quantiles(
            ax_t, i + 0.12,
            float(df.loc[i, "tmin_p10"]),
            float(df.loc[i, "tmin_p25"]),
            float(df.loc[i, "tmin_p50"]),
            float(df.loc[i, "tmin_p75"]),
            float(df.loc[i, "tmin_p90"]),
            color="#6fa8ff",
            edge="0.25",
            width=0.22,
            alpha=0.9,
        )

    ax_t.set_ylabel("°C")
    ax_t.grid(True, axis="both", color="0.85", linewidth=0.8, alpha=0.55)
    ax_t.set_axisbelow(True)
    ax_t.spines["top"].set_color("0.70")
    ax_t.spines["right"].set_color("0.70")
    ax_t.spines["left"].set_color("0.60")
    ax_t.spines["bottom"].set_color("0.60")

    # --- TEMP: margen dinámico compacto ---
    t_low = float(min(df["tmin_p10"].min(), df["tmin_min"].min()))
    t_high = float(max(df["tmax_p90"].max(), df["tmax_max"].max()))

    if not (np.isfinite(t_low) and np.isfinite(t_high)) or t_high <= t_low:
        ax_t.set_ylim(t_low - 1.0, t_high + 1.0)
    else:
        spread = t_high - t_low
        pad = max(0.6, spread * 0.05)   # 5% con mínimo 0.6°C
        ax_t.set_ylim(t_low - pad, t_high + pad)

    # -------------------- EJE X --------------------
    ax_t.set_xlim(-0.6, len(df) - 0.4)
    ax_t.set_xticks(x)

    # etiquetas más pequeñas y en diagonal (como pediste)
    ax_t.set_xticklabels(
        df["day_label"].tolist(),
        rotation=35,
        ha="right",
        fontsize=8.5
    )
    ax_p.tick_params(axis="x", labelbottom=False)

    fig.suptitle(title, y=0.995, fontsize=13, weight="bold")
    plt.tight_layout(rect=[0, 0, 1, 0.985])

    out_png.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_png, dpi=220, facecolor="white")
    plt.close()
    log.info("PNG saved → %s", out_png)


def main():
    p = argparse.ArgumentParser(description="Pinta meteogramas desde CSV ENS.")
    p.add_argument("--csv", action="append", default=[], help="CSV concreto (repetible)")
    p.add_argument("--all", action="store_true", help="Pintar todos los ens_*.csv de web/data")
    args = p.parse_args()

    csv_files = []
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
        title = f"ECMWF ENS · {slug.replace('_', ' ').title()}"
        out_png = DEFAULT_IMG_DIR / f"ens_meteograma_{slug}.png"
        _plot_one(csv_path, out_png, title)

    log.info("Done.")


if __name__ == "__main__":
    main()
