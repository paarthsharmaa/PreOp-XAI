# PreOp-XAI on MOVER EPIC, with external validation on VitalDB

Paper: `PreOp_XAI_MOVER_IEEE.docx` (6 pages, IEEE A4 conference template; 4 figures, 3 tables, 28 references).

## What was run where
* **On the data holder's Windows PC** (`run_on_mover/`): MOVER EPIC CSVs -> `data_prep/` scripts (cohort, labels,
  LOINC/unit-mapped labs, respiratory feasibility) -> de-identified analysis tables -> `mover_run.py`
  (exact-SHAP self-test, main analyses for death and ICU admission, VitalDB external validation, lag-0 sensitivity
  analysis, determinism rerun, split check, 100 repeated splits per endpoint) -> aggregate export only.
  Python 3.13.14, scikit-learn 1.8.0, XGBoost 2.1.4, numpy 2.4.4, pandas 3.0.2 (`verification/environment.json`).
  PreOp-XAI repository commit 6baa665 used unchanged (`run_on_mover/preop_xai`).
* **In the cloud, from the aggregate export only** (`results/`): `code/summarize.py` (repeated-split summary),
  `code/figs_mover.py` (all figures), `paper/build_paper.py` (docx), `paper/audit.py` (193 independent checks).

No patient-level MOVER data are included here. `results/` contains aggregate metrics, intervals, curve
coordinates, decile summaries and SHAP summaries; calibration cells with < 11 patients were removed. Confirm that
sharing these aggregates is allowed under your MOVER Data Usage Agreement before publishing them.

## Reproduce the cloud side
```
python3 code/summarize.py
python3 code/figs_mover.py
cd paper && python3 build_paper.py out/PreOp_XAI_MOVER_IEEE.docx && python3 audit.py out/PreOp_XAI_MOVER_IEEE.docx
```
A rerun from this bundle reproduced `summary.json` and all four figures byte for byte, and the audit passes.

## Verification
* `verification/shap_selftest.txt` - exact SHAP vs brute-force enumeration (max error < 1e-6).
* `verification/determinism_check.json` - second run of the main mortality analysis: identical.
* `verification/audit_report.txt` - every number in the paper recomputed from the raw exports, qualitative
  claims re-derived, structure checked (authors, sections, figures, tables, citation order).
* `verification/run_log.txt` - log of the Windows run.
