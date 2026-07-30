import pandas as pd
import matplotlib.pyplot as plt

CSV = "web/data/ens_salamanca.csv"
OUT = "web/static/ecmwf/ens_meteograma.png"

df = pd.read_csv(CSV)
print(df.columns)

plt.style.use("default")

fig, ax = plt.subplots(figsize=(13, 5.5))

x = range(len(df))

# ---------- Tmax ----------
ax.fill_between(
    x,
    df["tmax_p25"],
    df["tmax_p75"],
    color="red",
    alpha=0.22,
    linewidth=0,
)

ax.fill_between(
    x,
    df["tmax_p10"],
    df["tmax_p90"],
    color="red",
    alpha=0.08,
    linewidth=0,
)

ax.plot(
    x,
    df["tmax_p50"],
    color="red",
    linewidth=2.8,
    label="T. máxima",
)

ax.plot(
    x,
    df["tmax_p10"],
    "--",
    color="red",
    linewidth=1,
    alpha=0.7,
)

ax.plot(
    x,
    df["tmax_p90"],
    "--",
    color="red",
    linewidth=1,
    alpha=0.7,
)

# ---------- Tmin ----------
ax.fill_between(
    x,
    df["tmin_p25"],
    df["tmin_p75"],
    color="royalblue",
    alpha=0.22,
    linewidth=0,
)

ax.fill_between(
    x,
    df["tmin_p10"],
    df["tmin_p90"],
    color="royalblue",
    alpha=0.08,
    linewidth=0,
)

ax.plot(
    x,
    df["tmin_p50"],
    color="royalblue",
    linewidth=2.8,
    label="T. mínima",
)

ax.plot(
    x,
    df["tmin_p10"],
    "--",
    color="royalblue",
    linewidth=1,
    alpha=0.7,
)

ax.plot(
    x,
    df["tmin_p90"],
    "--",
    color="royalblue",
    linewidth=1,
    alpha=0.7,
)

# Separación entre corto y medio plazo
ax.axvline(
    9.5,
    color="0.6",
    linewidth=1.5,
    alpha=0.6,
)

# Rejilla
ax.grid(
    which="major",
    color="0.88",
    linewidth=0.8,
)

# Etiquetas eje X
labels = [
    s.replace("Thu ", "")
     .replace("Fri ", "")
     .replace("Sat ", "")
     .replace("Sun ", "")
     .replace("Mon ", "")
     .replace("Tue ", "")
     .replace("Wed ", "")
    for s in df["day_label"]
]

ax.set_xticks(list(x))
ax.set_xticklabels(labels)

# Límites
ymin = min(df["tmin_p10"].min(), df["tmin_min"].min()) - 2
ymax = max(df["tmax_p90"].max(), df["tmax_max"].max()) + 2

ax.set_ylim(ymin, ymax)
ax.set_xlim(-0.3, len(df) - 0.7)

# Títulos
ax.set_title(
    "ECMWF ENS · Salamanca",
    fontsize=16,
    weight="bold",
)

ax.set_ylabel("Temperatura (°C)")

# Leyenda
ax.legend(
    frameon=False,
    loc="upper left",
)

# Quitar bordes superiores
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)

plt.tight_layout()
print(OUT)
plt.savefig(
    OUT,
    dpi=200,
    facecolor="white",
)

plt.close()
