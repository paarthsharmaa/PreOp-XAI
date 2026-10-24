"""All figures, drawn only from the aggregate outputs exported from the MOVER run (results/...).
Fig. 1 cohort flow and protocol; Fig. 2 ROC/PR (MOVER test and VitalDB external); Fig. 3 decile calibration;
Fig. 4 grouped SHAP importance over paired refits.
Run from the project root: python3 code/figs_mover.py"""
import glob
import json
import sys

import numpy as np

sys.path.insert(0, "code")
from figstyle import plt, COL1, COL2, panel
from matplotlib.patches import FancyArrowPatch, Rectangle

R = "results"
M = json.load(open(f"{R}/main_mortality/study.json"))
I = json.load(open(f"{R}/main_icu/study.json"))
STUDY = {"mortality": M, "icu": I}
FLOW = json.load(open(f"{R}/cohort/mover_cohort_flow.json"))
LABS = json.load(open(f"{R}/cohort/mover_feature_stats.json"))
VF = M["external_vitaldb"]["flow"]
EP = {"mortality": "In-hospital death", "icu": "ICU admission"}
SHORT = {"mortality": "Death", "icu": "ICU"}
CONCEPTS = ["age", "sex", "asa", "hemoglobin", "platelets", "creatinine", "bun", "sodium", "potassium", "glucose"]
LABEL = {"age": "Age", "sex": "Sex", "asa": "ASA class", "hemoglobin": "Haemoglobin", "platelets": "Platelets",
         "creatinine": "Creatinine", "bun": "BUN", "sodium": "Sodium", "potassium": "Potassium", "glucose": "Glucose"}
MOD = {"lr": "LR", "xgboost": "XGBoost"}
f = lambda n: f"{n:,}"


def pbox(ax, data):
    """Box = quartiles, line = median, whiskers = exact 2.5th and 97.5th percentiles."""
    from matplotlib.cbook import boxplot_stats
    stats = boxplot_stats(data)
    for st, v in zip(stats, data):
        st["whislo"], st["whishi"] = np.quantile(v, [0.025, 0.975])
    ax.bxp(stats, widths=0.5, showfliers=False, medianprops=dict(color="black"), boxprops=dict(lw=0.6),
           whiskerprops=dict(lw=0.6), capprops=dict(lw=0.6))


# ============================================================== Fig. 1: cohort flow and protocol
fig = plt.figure(figsize=(COL2, 2.6))
ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 140); ax.set_ylim(0, 55); ax.axis("off")


def box(x, y, w, h, text, fill="white", fs=6.2, bold=False):
    ax.add_patch(Rectangle((x, y), w, h, fc=fill, ec="black", lw=0.7))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, linespacing=1.2,
            fontweight="bold" if bold else "normal")


def arrow(x0, y0, x1, y1):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>", mutation_scale=7, lw=0.7, color="black",
                                 shrinkA=0, shrinkB=0))


ex = FLOW["exclusions"]
dedup = FLOW["rows"] - FLOW["exact_duplicates_removed"]
elig = dedup - ex["operation_conflict"] - ex["not_adult"] - ex["invalid_or_donor_asa"] - ex["invalid_anesthesia_boundary"]
assert elig - ex["later_eligible_operation"] - ex["ambiguous_first_operation_time"] == FLOW["indexed_patients"]
assert FLOW["indexed_patients"] - FLOW["unlinked"] - FLOW["unknown_disposition"] == FLOW["mortality_known"]
box(2, 46, 40, 7, f"MOVER EPIC patient_information\n{f(FLOW['rows'])} rows, {f(FLOW['patients'])} patients")
box(2, 34, 40, 7, f"Eligible operations\n{f(elig)}")
box(2, 22, 40, 7, f"First eligible operation per patient\n{f(FLOW['indexed_patients'])} patients")
box(2, 6, 40, 10, f"Development cohort: {f(FLOW['mortality_known'])} patients\nin-hospital death {FLOW['mortality_events']} "
    f"({100 * FLOW['mortality_events'] / FLOW['mortality_known']:.2f}%)\nICU admission {f(FLOW['icu_flag_yes_among_known'])} "
    f"({100 * FLOW['icu_flag_yes_among_known'] / FLOW['mortality_known']:.1f}%)", fill="0.9")
for y0, y1 in ((46, 41), (34, 29), (22, 16)):
    arrow(22, y0, 22, y1)
side = [(43.5, f"Removed: {f(FLOW['exact_duplicates_removed'])} duplicate rows; {ex['operation_conflict']} conflicting,\n"
               f"{ex['not_adult']} age < 18 y, {ex['invalid_or_donor_asa']} ASA VI/invalid, {f(ex['invalid_anesthesia_boundary'])} invalid\nanaesthesia times"),
        (31.5, f"Later operations of the same patient\nset aside ({f(ex['later_eligible_operation'])})"),
        (19.0, f"Outcome unknown: stay not spanning\nanaesthesia ({FLOW['unlinked']}), transfer/hospice/\nmissing disposition ({FLOW['unknown_disposition']})")]
for y, t in side:
    ax.plot([22, 44], [y, y], color="black", lw=0.6)
    ax.text(45, y, t, ha="left", va="center", fontsize=5.7, linespacing=1.15)
ax.text(2, 2.6, f"Predictors: age, sex, ASA, latest of 7 laboratory values collected 30 d to 24 h before anaesthesia "
        f"(LOINC- and unit-mapped)", fontsize=5.6, ha="left", va="center")

PX = 82
P, E, EI = M["partition_n"], M["partition_events"], I["partition_events"]
parts = [("Training (70%)", "train", "5-fold CV selection by AP:\nLR (3 C values), XGBoost (12 settings)"),
         ("Validation (15%)", "validation", "logistic recalibration; threshold at\n80% sensitivity; SHAP and 10 refits"),
         ("Test (15%)", "test", "single evaluation after freezing;\n1,000 paired bootstraps")]
for k, (name, key, task) in enumerate(parts):
    y = 41 - 10.5 * k
    box(PX, y, 19, 8, f"{name}\nn = {f(P[key])}\ndeaths {E[key]}, ICU {f(EI[key])}", fill="0.9" if k == 2 else "white", fs=5.9)
    box(PX + 21, y, 36, 8, task, fs=5.9)
    arrow(PX + 19, y + 4, PX + 21, y + 4)
ax.text(PX + 28, 52, "Patient-level split (seed 2026, stratified on death)", ha="center", va="center", fontsize=6.4,
        fontweight="bold")
ax.plot([42, 78.5, 78.5], [11, 11, 45], color="black", lw=0.6)
for k in range(3):
    yy = 45 - 10.5 * k
    ax.plot([78.5, 80], [yy, yy], color="black", lw=0.6)
    arrow(80, yy, PX, yy)
box(PX, 2, 57, 9, f"External validation of the frozen, MOVER-recalibrated models and thresholds:\nVitalDB (Seoul) "
    f"{f(VF['modelled_patients'])} patients, deaths {VF['mortality_events']}, ICU stay {f(VF['icu_events'])}",
    fill="0.9", fs=5.9)
arrow(PX + 28.5, 20, PX + 28.5, 11)
fig.savefig("figs/fig1_cohort.png"); plt.close(fig)

# ============================================================== Fig. 2: ROC and PR, internal test and external
LS = {("test", "lr"): dict(color="black", ls="-"), ("test", "xgboost"): dict(color="0.5", ls="-"),
      ("external", "lr"): dict(color="black", ls="--"), ("external", "xgboost"): dict(color="0.5", ls="--")}
fig, ax = plt.subplots(1, 4, figsize=(COL2, 2.0))
fig.subplots_adjust(left=0.06, right=0.99, bottom=0.38, top=0.97, wspace=0.42)
for j, e in enumerate(EP):
    S = STUDY[e]
    a, b = ax[2 * j], ax[2 * j + 1]
    for src, res in (("test", S["evaluation"]), ("external", S["external_vitaldb"])):
        for m in MOD:
            c = S["figure_data"][src][m]["curves"]
            tag = "MOVER" if src == "test" else "VitalDB"
            a.plot(c["fpr"], c["tpr"], drawstyle="steps-post", lw=0.9, **LS[(src, m)], label=f"{tag} {MOD[m]}")
            b.plot(c["recall"], c["precision"], drawstyle="steps-post", lw=0.9, **LS[(src, m)])
    a.plot([0, 1], [0, 1], ls=":", color="0.6", lw=0.7)
    a.set(xlim=(0, 1), ylim=(0, 1.01), xlabel="1 − specificity", ylabel="Sensitivity")
    b.set(xlim=(0, 1), ylim=(0, 1.01), xlabel="Recall", ylabel="Precision")
    if j == 0:
        a.legend(loc="lower right", fontsize=5.8, handlelength=1.8)
    panel(a, f"({'abcd'[2 * j]}) {SHORT[e]}, ROC")
    panel(b, f"({'abcd'[2 * j + 1]}) {SHORT[e]}, precision–recall")
    for q in (a, b):
        q.set_xticks([0, 0.5, 1]); q.set_yticks([0, 0.5, 1])
fig.savefig("figs/fig2_discrimination.png"); plt.close(fig)

# ============================================================== Fig. 3: decile calibration (recalibrated risks)
fig, ax = plt.subplots(1, 4, figsize=(COL2, 1.9))
fig.subplots_adjust(left=0.065, right=0.99, bottom=0.355, top=0.97, wspace=0.42)
FLOOR = 3e-5   # deciles without a death are drawn on a separate "0" row below the log axis
for k, (e, src) in enumerate((("mortality", "test"), ("mortality", "external"), ("icu", "test"), ("icu", "external"))):
    a = ax[k]
    for m, mk, col in (("lr", "o", "black"), ("xgboost", "s", "0.5")):
        d = STUDY[e]["figure_data"][src][m]["deciles_cal"]
        pr = np.array([x["predicted"] for x in d]); ob = np.array([x["observed"] for x in d])
        nn = np.array([x["n"] for x in d])
        z = 1.96   # Wilson 95% interval for the observed proportion
        cen = (ob + z * z / (2 * nn)) / (1 + z * z / nn)
        half = z * np.sqrt(ob * (1 - ob) / nn + z * z / (4 * nn * nn)) / (1 + z * z / nn)
        lo, hi = np.maximum(cen - half, 0), cen + half
        if e == "mortality":
            obp = np.where(ob > 0, ob, FLOOR)
            a.errorbar(pr, obp, yerr=[np.maximum(obp - np.maximum(lo, FLOOR), 0), hi - obp], fmt=mk, color=col,
                       mfc="white", ms=3, elinewidth=0.5, capsize=1.2, label=MOD[m])
        else:
            a.errorbar(pr, ob, yerr=[ob - lo, hi - ob], fmt=mk + "-", color=col, mfc="white", ms=3, lw=0.7,
                       elinewidth=0.5, capsize=1.2, label=MOD[m])
    if e == "mortality":
        a.set_xscale("log"); a.set_yscale("log")
        a.plot([1e-4, 0.2], [1e-4, 0.2], ls=":", color="0.6", lw=0.7)
        a.set(xlim=(1e-4, 0.2), ylim=(1.8e-5, 0.2))
        a.axhline(6e-5, color="0.75", lw=0.5, ls="-")
        a.set_yticks([FLOOR, 1e-4, 1e-3, 1e-2, 1e-1], ["0", "$10^{-4}$", "$10^{-3}$", "$10^{-2}$", "$10^{-1}$"])
        a.minorticks_off()
    else:
        a.plot([0, 1], [0, 1], ls=":", color="0.6", lw=0.7)
        a.set(xlim=(0, 1), ylim=(0, 1))
        a.set_xticks([0, 0.5, 1]); a.set_yticks([0, 0.5, 1])
    a.set(xlabel="Mean predicted risk", ylabel="Observed proportion")
    a.legend(loc="upper left", fontsize=5.8, handlelength=1.2)
    panel(a, f"({'abcd'[k]}) {SHORT[e]}, {'MOVER test' if src == 'test' else 'VitalDB'}")
fig.savefig("figs/fig3_calibration.png"); plt.close(fig)

# ============================================================== Fig. 4: grouped SHAP importance over paired refits
fig, ax = plt.subplots(1, 2, figsize=(COL2, 2.05))
fig.subplots_adjust(left=0.1, right=0.99, bottom=0.27, top=0.98, wspace=0.42)
for k, e in enumerate(EP):
    a = ax[k]
    imp = {m: np.array(STUDY[e]["figure_data"]["shap_refit_importance"][m]) for m in MOD}   # refits x concepts
    order = np.argsort(-(imp["lr"].mean(0) / imp["lr"].mean(0).sum() + imp["xgboost"].mean(0) / imp["xgboost"].mean(0).sum()))
    yy = np.arange(len(CONCEPTS))
    for d, m in ((-0.2, "lr"), (0.2, "xgboost")):
        mu, lo, hi = imp[m].mean(0)[order], imp[m].min(0)[order], imp[m].max(0)[order]
        a.barh(yy + d, mu, height=0.38, color="white" if m == "lr" else "0.55", edgecolor="black", lw=0.5,
               xerr=[mu - lo, hi - mu], error_kw=dict(lw=0.6, capsize=1.5), label=MOD[m])
    a.set_yticks(yy, [LABEL[CONCEPTS[i]] for i in order]); a.invert_yaxis()
    a.set_xlabel("Mean |SHAP| on validation patients (log-odds)")
    a.legend(loc="lower right", fontsize=6.8)
    a.tick_params(axis="y", which="both", right=False)
    panel(a, f"({'ab'[k]}) {EP[e]}: mean and range over 10 paired refits")
    a.texts[-1].set_position((0.5, -0.2))
fig.savefig("figs/fig4_shap.png"); plt.close(fig)

print("figures written")
