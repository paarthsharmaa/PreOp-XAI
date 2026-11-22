"""Build the dashboard's JSON from committed aggregate results. No number is typed here.

Run: uv run --locked python -m app.build_data

Every number in site.json has an entry in provenance.json naming its source file and location, or the operation
that derives it from such sources. MOVER counts from 1 to 10 are written as "<11".
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
import csv
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Final

import app  # noqa: F401
from pipeline.config import ROOT

OUTPUT: Final = ROOT / "app/web/public/data"
ENDPOINTS: Final = {"mortality": "In-hospital mortality", "icu": "ICU admission"}
MODELS: Final = {"lr": "Logistic regression", "xgboost": "XGBoost"}
CONCEPTS: Final = {
    "age": "Age",
    "sex": "Sex",
    "asa": "ASA class",
    "hemoglobin": "Haemoglobin",
    "platelets": "Platelets",
    "creatinine": "Creatinine",
    "bun": "BUN",
    "sodium": "Sodium",
    "potassium": "Potassium",
    "glucose": "Glucose",
}
SOURCES: Final = {
    "mover": {
        "name": "MOVER",
        "detail": "Medical Informatics Operating Room Vitals and Events Repository, University of "
        "California, Irvine. EPIC EMR tables, used under a data usage agreement. Only aggregate results appear "
        "on this site.",
        "url": "https://mover.ics.uci.edu",
    },
    "vitaldb": {
        "name": "VitalDB",
        "detail": "Lee HC, Park Y, Yoon SB, Yang SM, Park D, Jung CW. VitalDB, a high-fidelity "
        "multi-parameter vital signs database in surgical patients. Sci Data. 2022;9(1):279.",
        "url": "https://doi.org/10.1038/s41597-022-01411-5",
        "licence": "CC BY 4.0",
        "licence_url": "https://creativecommons.org/licenses/by/4.0/",
        "changes": "Changes made: one case per patient selected, identifiers removed, ages above 89 top-coded to "
        "90, fields renamed and results aggregated. Example records in the local demo are a sample.",
    },
}
CURVE_POINTS: Final = 120
SMALL_CELL: Final = 11


def _top3_overlap(*values: float) -> int:
    """Shared top-three concepts, from importances listed in CONCEPTS order for LR and then XGBoost."""
    names = list(CONCEPTS)
    first, second = (dict(zip(names, values[i : i + len(names)], strict=True)) for i in (0, len(names)))
    return len(set(ranked(first)[:3]) & set(ranked(second)[:3]))


def _always_top5(*values: float) -> int:
    """Concepts in the top five in every refit, from frequencies listed per fit in CONCEPTS order."""
    size = len(CONCEPTS)
    return sum(all(values[i] == 1 for i in range(start, len(values), size)) for start in range(size))


def ranked(values: dict[str, float]) -> list[str]:
    return sorted(values, key=lambda concept: (-values[concept], concept))


OPS: Final[dict[str, Callable[..., float]]] = {
    "diff": lambda a, b: a - b,
    "ratio": lambda a, b: a / b,
    "count": lambda *values: len(values),
    "top3_overlap": _top3_overlap,
    "always_top5": _always_top5,
    "pct": lambda a: a * 100,
    "share_count": lambda share, n: round(share * n),
    "sum": lambda *values: sum(values),
    "missing_fits": lambda splits, *counts: sum(splits - count for count in counts),
    "total_fits": lambda splits, *counts: splits * len(counts),
}


@dataclass(frozen=True)
class V:
    """A number with its origin: a source reference, or an operation over other traced numbers."""

    value: Any
    ref: str | None = None
    op: str | None = None
    args: tuple[V, ...] = ()

    def spec(self) -> dict[str, Any]:
        if self.op:
            return {"op": self.op, "args": [arg.spec() for arg in self.args]}
        return {"ref": self.ref}


@dataclass(frozen=True)
class Series:
    """A list taken from one source array, optionally thinned to the listed indices."""

    values: list[float]
    ref: str
    indices: list[int] | None = None


@dataclass(frozen=True)
class Masked:
    """A small MOVER count that is published only as "<11"."""

    ref: str


@dataclass(frozen=True)
class Note:
    """Generated sentence whose inserted values are all traced."""

    template: str
    args: dict[str, tuple[V, str]]

    @property
    def text(self) -> str:
        return self.template.format(**{key: format(value.value, spec) for key, (value, spec) in self.args.items()})


def derive(op: str, *args: V) -> V:
    return V(OPS[op](*[arg.value for arg in args]), op=op, args=args)


def compact(value: Any) -> Any:
    """Six significant digits are enough for display and keep the JSON small."""
    return float(f"{value:.6g}") if isinstance(value, float) else value


class Sources:
    """Read-only access to committed results by file and '/'-separated location."""

    def __init__(self, root: Path = ROOT) -> None:
        self.root = root
        self._cache: dict[str, Any] = {}

    def read(self, file: str) -> Any:
        if file not in self._cache:
            path = self.root / file
            if path.suffix == ".json":
                self._cache[file] = json.loads(path.read_text())
            elif path.suffix == ".csv":
                with path.open(newline="") as stream:
                    self._cache[file] = {
                        row["comparison"]: {key: float(item) for key, item in row.items() if key != "comparison"}
                        for row in csv.DictReader(stream)
                    }
            else:
                self._cache[file] = _parse_selftest(path.read_text())
        return self._cache[file]

    def lookup(self, ref: str) -> Any:
        file, _, pointer = ref.partition("#")
        node = self.read(file)
        for part in pointer.split("/"):
            if part:
                node = node[int(part)] if isinstance(node, list) else node[part]
        return node

    def v(self, file: str, pointer: str) -> V:
        ref = f"{file}#{pointer}"
        return V(self.lookup(ref), ref=ref)

    def count(self, file: str, pointer: str) -> V | Masked:
        """A MOVER count, masked when it describes fewer than eleven patients."""
        value = self.v(file, pointer)
        return Masked(value.ref or "") if 0 < value.value < SMALL_CELL else value

    def series(self, file: str, pointer: str, indices: list[int] | None = None) -> Series:
        ref = f"{file}#{pointer}"
        values = self.lookup(ref)
        return Series([values[i] for i in indices] if indices is not None else list(values), ref, indices)


def _parse_selftest(text: str) -> dict[str, Any]:
    tree = [float(match) for match in re.findall(r"tree trial \d+:.*= ([0-9.e+-]+)", text)]
    linear = re.search(r"linear: max \|exact - brute force\| = ([0-9.e+-]+)", text)
    if not tree or linear is None:
        raise ValueError("Unexpected SHAP self-test format.")
    return {
        "tree_max_error": max(tree),
        "tree_trials": len(tree),
        "linear_max_error": float(linear.group(1)),
        "passed": text.strip().endswith("PASS"),
    }


def thin(length: int) -> list[int]:
    """Evenly spaced indices that always keep both curve ends."""
    if length <= CURVE_POINTS:
        return list(range(length))
    step = (length - 1) / (CURVE_POINTS - 1)
    return sorted({round(i * step) for i in range(CURVE_POINTS)})


def metric(src: Sources, metrics: str, intervals: str, model: str, group: str, name: str) -> dict[str, V]:
    key = f"{model}.{group}.{name}"
    return {
        "v": src.v(metrics, f"models/{model}/{group}/{name}"),
        "lo": src.v(intervals, f"{key}/lower"),
        "hi": src.v(intervals, f"{key}/upper"),
    }


def model_block(src: Sources, run: str, sub: str, figure: str, model: str) -> dict[str, Any]:
    metrics, intervals = f"{run}/{sub}metrics.json", f"{run}/{sub}intervals.csv"
    study = f"{run}/study.json"
    base = f"figure_data/{figure}/{model}"
    curves = src.lookup(f"{study}#{base}/curves")
    roc, pr = thin(len(curves["fpr"])), thin(len(curves["recall"]))
    deciles = src.lookup(f"{study}#{base}/deciles_cal")
    return {
        "auroc": metric(src, metrics, intervals, model, "raw", "auroc"),
        "ap": metric(src, metrics, intervals, model, "calibrated", "average_precision"),
        "brier": metric(src, metrics, intervals, model, "calibrated", "brier"),
        "slope": src.v(metrics, f"models/{model}/calibration/joint_slope"),
        "citl": src.v(metrics, f"models/{model}/calibration/offset_intercept"),
        "roc": {
            "fpr": src.series(study, f"{base}/curves/fpr", roc),
            "tpr": src.series(study, f"{base}/curves/tpr", roc),
        },
        "pr": {
            "recall": src.series(study, f"{base}/curves/recall", pr),
            "precision": src.series(study, f"{base}/curves/precision", pr),
        },
        "deciles": [
            {
                "predicted": src.v(study, f"{base}/deciles_cal/{i}/predicted"),
                "observed": src.v(study, f"{base}/deciles_cal/{i}/observed"),
            }
            for i in range(len(deciles))
        ],
    }


def evaluation(src: Sources, run: str, sub: str, figure: str) -> dict[str, Any]:
    metrics, intervals = f"{run}/{sub}metrics.json", f"{run}/{sub}intervals.csv"
    return {
        "n": src.v(metrics, "n"),
        "events": src.v(metrics, "events"),
        "prevalence": src.v(metrics, "prevalence"),
        "bootstraps": src.v(metrics, "bootstrap_resamples"),
        "auroc_difference": {
            "v": derive("diff", src.v(metrics, "models/xgboost/raw/auroc"), src.v(metrics, "models/lr/raw/auroc")),
            "lo": src.v(intervals, "paired_xgboost_minus_lr.raw.auroc/lower"),
            "hi": src.v(intervals, "paired_xgboost_minus_lr.raw.auroc/upper"),
        },
        "models": {model: model_block(src, run, sub, figure, model) for model in MODELS},
    }


def shap_block(src: Sources, run: str) -> dict[str, Any]:
    file, stability, study = f"{run}/explain/explain.json", f"{run}/stability/stability.json", f"{run}/study.json"
    out: dict[str, Any] = {
        "background_n": src.v(file, "background_n"),
        "explained_n": src.v(file, "n_explained"),
        "refits": src.v(stability, "requested_refits"),
        "models": {},
    }
    for model in MODELS:
        order = ranked(src.lookup(f"{file}#models/{model}/global_mean_absolute_raw"))
        refits = src.lookup(f"{study}#figure_data/shap_refit_importance/{model}")
        positions = {concept: index for index, concept in enumerate(CONCEPTS)}
        out["models"][model] = {
            "order": order,
            "concepts": {
                concept: {
                    "importance": src.v(file, f"models/{model}/global_mean_absolute_raw/{concept}"),
                    "missingness": src.v(file, f"models/{model}/missingness_mean_absolute_raw/{concept}"),
                    "top5_frequency": src.v(stability, f"models/{model}/top5_inclusion_frequency/{concept}"),
                    "refits": [
                        src.v(study, f"figure_data/shap_refit_importance/{model}/{i}/{positions[concept]}")
                        for i in range(len(refits))
                    ],
                }
                for concept in CONCEPTS
            },
            "spearman": src.v(stability, f"models/{model}/spearman_mean"),
            "jaccard": src.v(stability, f"models/{model}/top5_jaccard_mean"),
            "successful_refits": src.v(stability, f"models/{model}/successful_refits"),
            "baseline": src.v(file, f"models/{model}/baseline_raw_mean"),
        }
    return out


def repeats_block(src: Sources, endpoint: str) -> dict[str, Any]:
    summary = "results/summary.json"
    splits = src.v(summary, f"{endpoint}/splits")
    low, high = src.lookup(f"{summary}#{endpoint}/seeds")
    points = [
        {
            "seed": src.v(f"results/repeats_{endpoint}/seed{seed:03d}.json", "seed"),
            **{
                model: src.v(f"results/repeats_{endpoint}/seed{seed:03d}.json", f"test/{model}/raw/auroc")
                for model in MODELS
            },
        }
        for seed in range(low, high + 1)
    ]
    diff = {
        key: src.v(summary, f"{endpoint}/diff_auroc/{key}") for key in ("median", "p2_5", "p97_5", "share_xgb_better")
    }
    return {
        "splits": splits,
        "points": points,
        "difference": diff,
        "xgb_wins": derive("share_count", diff["share_xgb_better"], splits),
        "auroc": {
            model: {key: src.v(summary, f"{endpoint}/{model}/auroc/{key}") for key in ("median", "p2_5", "p97_5")}
            for model in MODELS
        },
    }


def lag0_block(src: Sources, endpoint: str) -> dict[str, Any]:
    out: dict[str, Any] = {"models": {}}
    for model in MODELS:
        primary = metric(
            src,
            f"results/main_{endpoint}/metrics.json",
            f"results/main_{endpoint}/intervals.csv",
            model,
            "raw",
            "auroc",
        )
        lag0 = metric(
            src,
            f"results/lag0_{endpoint}/metrics.json",
            f"results/lag0_{endpoint}/intervals.csv",
            model,
            "raw",
            "auroc",
        )
        out["models"][model] = {"primary": primary, "lag0": lag0, "change": derive("diff", lag0["v"], primary["v"])}
    out["missing_primary"] = src.v("results/cohort/mover_feature_stats.json", "missing_pct/hemoglobin")
    out["missing_lag0"] = src.v("results/cohort/mover_feature_stats_lag0h.json", "missing_pct/hemoglobin")
    return out


def external_block(block: dict[str, Any], test: dict[str, Any]) -> dict[str, Any]:
    return {
        model: {
            "drop": derive("diff", test["models"][model]["auroc"]["v"], block["models"][model]["auroc"]["v"]),
            "test_auroc": test["models"][model]["auroc"]["v"],
            "external_auroc": block["models"][model]["auroc"]["v"],
            "slope": block["models"][model]["slope"],
            "citl": block["models"][model]["citl"],
            "test_slope": test["models"][model]["slope"],
            "test_citl": test["models"][model]["citl"],
        }
        for model in MODELS
    }


def _interval_verdict(low: float, high: float) -> str:
    if low <= 0 <= high:
        return "The interval includes zero, so this split does not separate the two models."
    return "The interval excludes zero, favouring XGBoost." if low > 0 else "The interval excludes zero, favouring LR."


def takeaways(entry: dict[str, Any]) -> dict[str, Note]:
    test, ext, shap, rep, lag0 = entry["test"], entry["external"], entry["shap"], entry["repeats"], entry["lag0"]
    lr, xgb = test["models"]["lr"], test["models"]["xgboost"]
    diff = test["auroc_difference"]
    rep_diff = rep["difference"]
    transport = entry["transport"]
    lr_top, xgb_top = shap["models"]["lr"]["order"], shap["models"]["xgboost"]["order"]
    shared = [concept for concept in lr_top[:3] if concept in xgb_top[:3]]
    shared_names = ", ".join(CONCEPTS[concept] for concept in shared) or "no concept"
    first_ranked = (
        f"Both models rank {CONCEPTS[lr_top[0]]} first."
        if lr_top[0] == xgb_top[0]
        else f"LR ranks {CONCEPTS[lr_top[0]]} first and XGBoost ranks {CONCEPTS[xgb_top[0]]} first."
    )
    verdict = _interval_verdict(diff["lo"].value, diff["hi"].value).replace("{", "").replace("}", "")
    consistent = rep_diff["p2_5"].value > 0 or rep_diff["p97_5"].value < 0
    repeat_verdict = (
        "The middle 95% of differences excludes zero." if consistent else "The middle 95% of differences includes zero."
    )
    unstable = sorted(
        {
            concept
            for model in MODELS
            for concept in CONCEPTS
            if 0 < shap["models"][model]["concepts"][concept]["top5_frequency"].value < 1
        }
    )
    unstable_text = ", ".join(CONCEPTS[concept] for concept in unstable) or "no concept"
    worse = max(MODELS, key=lambda model: transport[model]["drop"].value)
    return {
        "roc": Note(
            "AUROC was {lr} for LR and {xgb} for XGBoost on {n} held-out patients. The paired difference was "
            "{d} (95% CI {lo} to {hi}). " + verdict,
            {
                "lr": (lr["auroc"]["v"], ".3f"),
                "xgb": (xgb["auroc"]["v"], ".3f"),
                "n": (test["n"], ","),
                "d": (diff["v"], "+.3f"),
                "lo": (diff["lo"], "+.3f"),
                "hi": (diff["hi"], "+.3f"),
            },
        ),
        "pr": Note(
            "Average precision was {lr} for LR and {xgb} for XGBoost, against an event rate of {rate}%. "
            "A model with no skill would score about the event rate.",
            {
                "lr": (lr["ap"]["v"], ".3f"),
                "xgb": (xgb["ap"]["v"], ".3f"),
                "rate": (derive("pct", test["prevalence"]), ".1f"),
            },
        ),
        "calibration": Note(
            "After recalibration the test-set slope was {ls} for LR and {xs} for XGBoost, where the "
            "ideal is one. Calibration-in-the-large was {lc} and {xc}, where the ideal is zero.",
            {
                "ls": (lr["slope"], ".2f"),
                "xs": (xgb["slope"], ".2f"),
                "lc": (lr["citl"], "+.2f"),
                "xc": (xgb["citl"], "+.2f"),
            },
        ),
        "shap": Note(
            first_ranked + " The models share {shared} of their top three concepts: " + shared_names + ".",
            {
                "shared": (
                    derive(
                        "top3_overlap",
                        *[
                            shap["models"][model]["concepts"][concept]["importance"]
                            for model in MODELS
                            for concept in CONCEPTS
                        ],
                    ),
                    "d",
                )
            },
        ),
        "stability": Note(
            "Across {refits} refits, mean rank agreement (Spearman) was {ls} for LR and {xs} for XGBoost. "
            "Concepts that moved in and out of the top five: " + unstable_text + ".",
            {
                "refits": (shap["refits"], "d"),
                "ls": (shap["models"]["lr"]["spearman"], ".2f"),
                "xs": (shap["models"]["xgboost"]["spearman"], ".2f"),
            },
        ),
        "repeats": Note(
            "XGBoost had the higher AUROC in {wins} of {n} repeated splits, with a median difference of "
            "{m} (middle 95%: {lo} to {hi}). " + repeat_verdict,
            {
                "wins": (rep["xgb_wins"], "d"),
                "n": (rep["splits"], "d"),
                "m": (rep_diff["median"], "+.4f"),
                "lo": (rep_diff["p2_5"], "+.4f"),
                "hi": (rep_diff["p97_5"], "+.4f"),
            },
        ),
        "lag0": Note(
            "Allowing labs up to anaesthesia start cut missing haemoglobin from {a}% to {b}%. AUROC changed by "
            "{l} for LR and {x} for XGBoost. This window can include results not yet available before surgery, so "
            "it is a sensitivity check only.",
            {
                "a": (lag0["missing_primary"], ".1f"),
                "b": (lag0["missing_lag0"], ".1f"),
                "l": (lag0["models"]["lr"]["change"], "+.3f"),
                "x": (lag0["models"]["xgboost"]["change"], "+.3f"),
            },
        ),
        "external": Note(
            "At VitalDB, AUROC fell by {l} for LR and {x} for XGBoost, with the larger fall for "
            + MODELS[worse]
            + ". Calibration slope was {ls} and {xs}, where the ideal is one.",
            {
                "l": (transport["lr"]["drop"], ".3f"),
                "x": (transport["xgboost"]["drop"], ".3f"),
                "ls": (transport["lr"]["slope"], ".2f"),
                "xs": (transport["xgboost"]["slope"], ".2f"),
            },
        ),
    }


def endpoint_block(src: Sources, endpoint: str, label: str) -> dict[str, Any]:
    run = f"results/main_{endpoint}"
    test = evaluation(src, run, "", "test")
    external = evaluation(src, run, "external_vitaldb/", "external")
    entry: dict[str, Any] = {
        "label": label,
        "test": test,
        "external": external,
        "transport": external_block(external, test),
        "shap": shap_block(src, run),
        "repeats": repeats_block(src, endpoint),
        "lag0": lag0_block(src, endpoint),
        "base_rate": {"n": src.v(f"{run}/study.json", "n"), "events": src.v(f"{run}/study.json", "events")},
        "thresholds": {model: src.v(f"{run}/study.json", f"selection/{model}/threshold") for model in MODELS},
    }
    entry["base_rate"]["rate"] = V(
        entry["base_rate"]["events"].value / entry["base_rate"]["n"].value,
        op="ratio",
        args=(entry["base_rate"]["events"], entry["base_rate"]["n"]),
    )
    entry["takeaways"] = takeaways(entry)
    return entry


def cohort_block(src: Sources) -> dict[str, Any]:
    flow = "results/cohort/mover_cohort_flow.json"
    data = src.read(flow)
    start = derive("diff", src.v(flow, "rows"), src.v(flow, "exact_duplicates_removed"))
    removed = sum(data["exclusions"].values())
    if start.value - removed != data["indexed_patients"]:
        raise ValueError("MOVER cohort flow does not close.")
    if data["indexed_patients"] - data["unlinked"] - data["unknown_disposition"] != data["mortality_known"]:
        raise ValueError("MOVER outcome flow does not close.")
    labels = {
        "operation_conflict": "Conflicting operation records",
        "not_adult": "Not an adult",
        "invalid_or_donor_asa": "ASA VI, donor or invalid ASA",
        "invalid_anesthesia_boundary": "Invalid anaesthesia times",
        "ambiguous_first_operation_time": "Ambiguous first operation",
        "later_eligible_operation": "Later operation of the same patient",
    }
    mover = [
        {"label": "Source operation records", "n": src.v(flow, "rows"), "kind": "start"},
        {"label": "Exact duplicates", "n": src.count(flow, "exact_duplicates_removed"), "kind": "out"},
        {"label": "Unique records", "n": start, "kind": "keep"},
        *[
            {"label": labels[key], "n": src.count(flow, f"exclusions/{key}"), "kind": "out"}
            for key in data["exclusions"]
            if data["exclusions"][key] > 0
        ],
        {"label": "Indexed patients", "n": src.v(flow, "indexed_patients"), "kind": "keep"},
        {"label": "Not linked to an outcome", "n": src.count(flow, "unlinked"), "kind": "out"},
        {"label": "Unknown discharge disposition", "n": src.count(flow, "unknown_disposition"), "kind": "out"},
        {"label": "Modelled patients", "n": src.v(flow, "mortality_known"), "kind": "final"},
    ]
    ext = "results/main_mortality/study.json"
    prefix = "external_vitaldb/flow"
    vital = src.lookup(f"{ext}#{prefix}")
    if (
        vital["source_cases"]
        - vital["excluded_age_under_18_or_missing_cases"]
        - vital["excluded_invalid_anesthesia_boundary_cases"]
        - vital["excluded_asa_vi_cases"]
        != vital["eligible_cases"]
    ):
        raise ValueError("VitalDB cohort flow does not close.")
    if vital["indexed_patients"] - vital["unknown_outcome_invalid_linkage"] != vital["modelled_patients"]:
        raise ValueError("VitalDB outcome flow does not close.")
    vitaldb = [
        {"label": "Source cases", "n": src.v(ext, f"{prefix}/source_cases"), "kind": "start"},
        {
            "label": "Under 18 or age missing",
            "n": src.v(ext, f"{prefix}/excluded_age_under_18_or_missing_cases"),
            "kind": "out",
        },
        {
            "label": "Invalid anaesthesia times",
            "n": src.v(ext, f"{prefix}/excluded_invalid_anesthesia_boundary_cases"),
            "kind": "out",
        },
        {"label": "ASA VI", "n": src.v(ext, f"{prefix}/excluded_asa_vi_cases"), "kind": "out"},
        {"label": "Eligible cases", "n": src.v(ext, f"{prefix}/eligible_cases"), "kind": "keep"},
        {
            "label": "Later cases of the same patient",
            "n": derive("diff", src.v(ext, f"{prefix}/eligible_cases"), src.v(ext, f"{prefix}/indexed_patients")),
            "kind": "out",
        },
        {"label": "Indexed patients", "n": src.v(ext, f"{prefix}/indexed_patients"), "kind": "keep"},
        {
            "label": "Invalid outcome linkage",
            "n": src.v(ext, f"{prefix}/unknown_outcome_invalid_linkage"),
            "kind": "out",
        },
        {"label": "Modelled patients", "n": src.v(ext, f"{prefix}/modelled_patients"), "kind": "final"},
    ]
    stats = "results/cohort/mover_feature_stats.json"
    return {
        "mover": mover,
        "vitaldb": vitaldb,
        "mover_events": {"mortality": src.v(flow, "mortality_events"), "icu": src.v(flow, "icu_flag_yes_among_known")},
        "vitaldb_events": {
            "mortality": src.v(ext, f"{prefix}/mortality_events"),
            "icu": src.v(ext, f"{prefix}/icu_events"),
        },
        "missing_labs": {lab: src.v(stats, f"missing_pct/{lab}") for lab in list(CONCEPTS)[3:]},
        "typical": {
            name: {key: src.v(ext, f"characteristics/all/{name}/{key}") for key in ("median", "q1", "q3")}
            for name in list(CONCEPTS)[3:]
        },
    }


def overview_block(endpoints: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    m, i = endpoints["mortality"], endpoints["icu"]

    def consistent(entry: dict[str, Any]) -> bool:
        return entry["repeats"]["difference"]["p2_5"].value > 0 or entry["repeats"]["difference"]["p97_5"].value < 0

    beat = "Almost identical" if not (consistent(m) or consistent(i)) else "In part"
    drops = [entry["transport"][model]["drop"].value for entry in (m, i) for model in MODELS]
    frequencies = [
        entry["shap"]["models"][model]["concepts"][concept]["top5_frequency"]
        for entry in (m, i)
        for model in MODELS
        for concept in CONCEPTS
    ]
    always = derive("always_top5", *frequencies)
    concepts = derive("count", *frequencies[: len(CONCEPTS)])
    moved = any(0 < item.value < 1 for item in frequencies)
    return [
        {
            "question": "Does XGBoost beat logistic regression?",
            "answer": beat,
            "detail": Note(
                "XGBoost had the higher AUROC in {mw} of {n} repeated splits for mortality and {iw} of {n} for ICU "
                "admission. The median differences were {md} and {id}.",
                {
                    "n": (m["repeats"]["splits"], "d"),
                    "mw": (m["repeats"]["xgb_wins"], "d"),
                    "iw": (i["repeats"]["xgb_wins"], "d"),
                    "md": (m["repeats"]["difference"]["median"], "+.4f"),
                    "id": (i["repeats"]["difference"]["median"], "+.4f"),
                },
            ),
            "link": "repeats",
        },
        {
            "question": "Are the explanations stable?",
            "answer": "Partly" if moved else "Yes",
            "detail": Note(
                "Across {r} refits, mean rank agreement ranged from {low} to {high}. {k} of {c} concepts stayed "
                "in the top five in every refit of every model.",
                {
                    "r": (m["shap"]["refits"], "d"),
                    "k": (always, "d"),
                    "c": (concepts, "d"),
                    "low": (_extreme(min, m, i, "spearman"), ".2f"),
                    "high": (_extreme(max, m, i, "spearman"), ".2f"),
                },
            ),
            "link": "stability",
        },
        {
            "question": "Does it transfer to another hospital?",
            "answer": "Only partly" if min(drops) > 0 else "Yes",
            "detail": Note(
                "At VitalDB, mortality AUROC fell by {ml} (LR) and {mx} (XGBoost), and ICU AUROC by {il} and {ix}. "
                "Mortality calibration slope was {sl} and {sx}.",
                {
                    "ml": (m["transport"]["lr"]["drop"], ".3f"),
                    "mx": (m["transport"]["xgboost"]["drop"], ".3f"),
                    "il": (i["transport"]["lr"]["drop"], ".3f"),
                    "ix": (i["transport"]["xgboost"]["drop"], ".3f"),
                    "sl": (m["transport"]["lr"]["slope"], ".2f"),
                    "sx": (m["transport"]["xgboost"]["slope"], ".2f"),
                },
            ),
            "link": "external",
        },
    ]


def _extreme(pick: Callable[..., V], m: dict[str, Any], i: dict[str, Any], key: str) -> V:
    values = [entry["shap"]["models"][model][key] for entry in (m, i) for model in MODELS]
    return pick(values, key=lambda item: item.value)


def methods_block(src: Sources) -> dict[str, Any]:
    env, det, split, test = (
        "verification/environment.json",
        "verification/determinism_check.json",
        "verification/split_check.json",
        "verification/shap_selftest.txt",
    )
    packages = src.lookup(f"{env}#packages")
    summary = "results/summary.json"
    fits = [
        src.v(summary, f"{endpoint}/{model}/{key}/n")
        for endpoint in ENDPOINTS
        for model in MODELS
        for key in ("test_cal_slope_raw", "test_cal_slope_cal")
    ]
    splits = src.v(summary, "mortality/splits")
    return {
        "environment": {
            "python": str(src.lookup(f"{env}#python")).split()[0],
            "platform": src.lookup(f"{env}#platform"),
            "packages": packages,
        },
        "determinism": {
            "identical": src.lookup(f"{det}#identical_except_runtime"),
            "differences": V(len(src.lookup(f"{det}#differences")), ref=f"{det}#differences"),
        },
        "selftest": {
            "tree_max_error": src.v(test, "tree_max_error"),
            "tree_trials": src.v(test, "tree_trials"),
            "linear_max_error": src.v(test, "linear_max_error"),
            "passed": src.lookup(f"{test}#passed"),
        },
        "split_check": {
            "primary_events": src.v(split, "primary_test_icu"),
            "low": src.v(split, "alt_test_icu_min"),
            "median": src.v(split, "alt_test_icu_median"),
            "high": src.v(split, "alt_test_icu_max"),
            "seeds": src.v(split, "alt_seeds/1"),
        },
        "limitation": {
            "non_converged": derive("missing_fits", splits, *fits),
            "total_fits": derive("total_fits", splits, *fits),
        },
    }


def emit(node: Any, path: str, provenance: dict[str, Any]) -> Any:
    """Convert traced values to plain JSON while recording where each came from."""
    if isinstance(node, V):
        provenance[path] = node.spec()
        return compact(node.value)
    if isinstance(node, Masked):
        provenance[path] = {"ref": node.ref, "masked": True}
        return f"<{SMALL_CELL}"
    if isinstance(node, Series):
        provenance[path] = {"ref": node.ref, "indices": node.indices}
        return [compact(value) for value in node.values]
    if isinstance(node, Note):
        provenance[path] = {
            "template": node.template,
            "args": {key: {**value.spec(), "format": spec} for key, (value, spec) in node.args.items()},
        }
        return node.text
    if isinstance(node, dict):
        return {key: emit(value, f"{path}/{key}", provenance) for key, value in node.items()}
    if isinstance(node, Sequence) and not isinstance(node, str):
        return [emit(value, f"{path}/{index}", provenance) for index, value in enumerate(node)]
    return node


def build(root: Path = ROOT) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return the site data and its provenance map."""
    src = Sources(root)
    endpoints = {key: endpoint_block(src, key, label) for key, label in ENDPOINTS.items()}
    site = {
        "notice": "Research prototype, not for clinical use.",
        "labels": {"models": MODELS, "concepts": CONCEPTS, "ci": "95% CI"},
        "sources": SOURCES,
        "overview": overview_block(endpoints),
        "cohort": cohort_block(src),
        "endpoints": endpoints,
        "methods": methods_block(src),
    }
    provenance: dict[str, Any] = {}
    return emit(site, "", provenance), provenance


def main() -> None:
    site, provenance = build()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    _ = (OUTPUT / "site.json").write_text(json.dumps(site, separators=(",", ":"), ensure_ascii=False))
    _ = (OUTPUT / "provenance.json").write_text(json.dumps(provenance, separators=(",", ":"), ensure_ascii=False))
    sizes = {path.name: path.stat().st_size for path in OUTPUT.glob("*.json")}
    print(f"Wrote {sizes} with {len(provenance)} traced entries.")


if __name__ == "__main__":
    main()
