"""Beeswarm is only an auxiliary repository figure; the paper's figures are drawn separately."""
import matplotlib.pyplot as plt
import numpy as np


def beeswarm(explanation, show=False):
    v = np.asarray(explanation.values)
    order = np.argsort(np.abs(v).mean(0))
    fig, ax = plt.subplots(figsize=(6, 0.25 * len(order) + 1))
    for k, j in enumerate(order):
        ax.scatter(v[:, j], np.full(len(v), k) + np.random.default_rng(0).uniform(-.2, .2, len(v)), s=3, c="k")
    ax.set_yticks(range(len(order)), [explanation.feature_names[j] for j in order], fontsize=6)
    ax.set_xlabel("SHAP value (log-odds)")
