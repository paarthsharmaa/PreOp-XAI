"""Plain journal-style plotting defaults: Times-like serif text, black/grey lines, inward ticks, no titles, no
shadows or rounded boxes. Single column = 3.45 in; double column = 7.0 in."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams.update({
    "font.family": "serif", "font.serif": ["Times New Roman", "TeX Gyre Termes", "Liberation Serif", "DejaVu Serif"],
    "mathtext.fontset": "stix", "font.size": 8, "axes.labelsize": 8, "legend.fontsize": 7, "xtick.labelsize": 7,
    "ytick.labelsize": 7, "axes.linewidth": 0.6, "lines.linewidth": 1.0, "lines.markersize": 3.5,
    "xtick.direction": "in", "ytick.direction": "in", "xtick.top": True, "ytick.right": True,
    "xtick.major.size": 3, "ytick.major.size": 3, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
    "legend.frameon": False, "legend.handlelength": 2.0, "axes.grid": False, "savefig.dpi": 600,
    "figure.dpi": 150, "axes.prop_cycle": matplotlib.cycler(color=["black", "0.45", "0.25", "0.65"])})
COL1, COL2 = 3.45, 7.0


def panel(ax, s):
    ax.text(0.5, -0.30, s, transform=ax.transAxes, ha="center", va="top", fontsize=8)
