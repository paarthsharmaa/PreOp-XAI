# PreOp-XAI: reproducible MOVER execution

This repository preserves the supplied implementation. The integration scripts
execute it in `outputs/reproduction/`, without changing either reference tree.
No synthetic patients or replacement algorithms are used.

**Observed limitation:** the complete scientific protocol runs on this machine,
but verification is not fully green. The newly generated paper audit encounters
null calibration diagnostics from genuine SciPy optimizer precision-loss failures;
115 of 226 aggregate JSON artifacts differ at the verifier's strict tolerance.
`all`, `publication`, and `verify` therefore return nonzero. See
`docs/REPRODUCTION.md` for evidence and `docs/KNOWN_LIMITATIONS.md` for the exact
reproduction. The separate supplied-aggregate paper audit passes 193/193.

## Setup

Install **uv**, then run from this repository root:

```sh
uv sync --locked
uv run --locked python scripts/reproduce.py check
```

`.python-version` selects CPython 3.13.14. `uv.lock` fixes the entire environment;
the six scientific dependency versions match the supplied Windows execution
record. The original Windows environment under `MOVER/preopxai/.venv` is not used.
The Linux installation downloads CPU-capable binary wheels; XGBoost's Linux wheel
also installs NCCL, but this workflow does not need CUDA or a GPU. On Linux the
wheels require a working glibc loader and OpenMP runtime (`libgomp`). This machine's
NixOS `nix-ld` configuration provides them. Other operating systems have not been
validated here.

Paper generation needs Pandoc. The pinned `pypandoc-binary` dependency supplies
its executable; the wrapper adds only its directory to the paper process's PATH.
No global Python packages or global Pandoc installation are required. Original
serif/STIX figure styles are retained, with installed serif font fallback.
LibreOffice is optional for viewing the DOCX, not needed for its structural audit.

## Real inputs

These files are deliberately **not versioned**. Restore authorized local copies
at these exact paths on a fresh checkout:

| Location | Purpose |
| --- | --- |
| `MOVER/EPIC_EMR/EMR/patient_information.csv` | Cohort, anaesthesia boundaries, mortality and ICU flags |
| `MOVER/EPIC_EMR/EMR/patient_labs.csv` | Seven laboratory concepts; approximately 3.57 GB |
| `MOVER/EPIC_EMR/EMR/patient_post_op_complications.csv` | Respiratory endpoint feasibility |
| `MOVER/preopxai/mover_analysis.csv` | Reference primary 24-hour-lag analysis table |
| `MOVER/preopxai/mover_analysis_lag0h.csv` | Reference lag-0 analysis table |
| `MOVER/preopxai/data/vitaldb_clinical_data.csv` | Frozen-model external validation |

`check` verifies the three analysis/VitalDB SHA256 values against the original
`verification/environment.json`, dependency versions, and all 102 original Python
source hashes. `prepare` regenerates the analysis tables from raw EPIC inputs and
requires exact DataFrame equality with the supplied tables. It also records
generated and reference file hashes. `PREOPXAI_RAW=/absolute/path` can relocate
the three raw files without changing source.

## Execute

```sh
# All available stages, in dependency order:
uv run --locked python scripts/reproduce.py all

# Or run individual stages:
uv run --locked python scripts/reproduce.py prepare
uv run --locked python scripts/reproduce.py protocol
uv run --locked python scripts/reproduce.py publication
uv run --locked python scripts/reproduce.py verify
```

`prepare` runs the original cohort script, original lab extractor over bounded
128 MiB byte ranges, candidate concatenation, original primary and lag-0 feature
scripts, and respiratory feasibility. An isolated temporary HOME supplies the
original scripts' hardcoded paths. Intermediate patient pickles are removed when
preparation exits. Cohort and analysis outputs remain local under `runner/`.

`protocol` runs the unchanged `mover_run.py`: exact-SHAP brute-force self-test;
primary mortality and ICU analyses; external VitalDB evaluation; 1,000 paired
bootstraps; validation explanations; 10 paired stability refits; lag-0 sensitivity;
full mortality determinism rerun; split checks for seeds 1–1,000; 100 repeated
splits per endpoint; and the original suppressed aggregate export.

Training and resampling use seed 2026; primary split seed is 2026 and repeated
split seeds are 1–100. Each fit retains the original five-fold CV and all
3 LR / 12 XGBoost candidate settings. No quick mode or reduced repeat count is
used. The wrapper defaults to six repeat workers and one OpenMP/BLAS thread per
process. Set `PREOPXAI_WORKERS` to change scheduling, not scientific settings.
Do not set the reference's `PREOPXAI_TEST_REPEATS` override for a full reproduction.

The original runner resumes stages whose completed JSON exists. To regenerate
everything rather than resume, move the entire `outputs/reproduction` directory
aside first. Do not run two writers into that directory concurrently. The
reference export step replaces only its staged `runner/export`, never an
original export.

Specific protocol stages can be requested, respecting the order above:

```sh
uv run --locked python scripts/reproduce.py protocol environment main
uv run --locked python scripts/reproduce.py protocol lag0 rerun split_check
uv run --locked python scripts/reproduce.py protocol repeats export
```

The preserved instructions estimate 30–90 minutes for the protocol; local timings
and hardware are recorded in the execution evidence. Allow several GB of working
space beyond raw data and environment downloads. Keep the machine awake.

## Publication and verification

`publication` consumes **newly computed** `runner/export`, runs the original
summary and figure scripts, builds the IEEE DOCX from the original template,
and runs the original independent paper audit. Each original live Matplotlib
figure is saved as 600-dpi PNG plus PDF and SVG; figure data and scientific
comparisons are unchanged. The audit recomputes paper values from aggregates,
checks claims and document structure, and verifies embedded figure bytes.

If only the supplied aggregate bundle is available, explicitly run:

```sh
uv run --locked python -m scripts.publication --reference
```

This writes `publication-reference`, never claims new training, and does not
require patient inputs. It is separate from the main workflow.

`verify` reruns the original exact-SHAP brute-force test and compares every
reference aggregate JSON to regenerated outputs (excluding OS/environment and
elapsed-runtime metadata). It reports all differing paths at numeric tolerances
`rtol=1e-8`, `atol=1e-10`; a difference produces a nonzero exit, not a hidden pass.
The exact determinism rerun and paper audit remain independent checks.
`all` runs numerical verification even when the publication audit fails, retains
both failure logs, and returns nonzero if either stage fails.

```sh
uv run --locked basedpyright scripts
# Independently provision a fresh environment without touching .venv:
UV_PROJECT_ENVIRONMENT=/absolute/new/environment uv sync --locked
UV_PROJECT_ENVIRONMENT=/absolute/new/environment uv run --locked python scripts/reproduce.py check
```

## Output locations

All generated clinical artifacts are ignored by Git:

| Under `outputs/reproduction/` | Contents |
| --- | --- |
| `logs/` | Stage logs, input/source check, preparation and reference comparisons |
| `runner/mover_analysis*.csv` | Regenerated de-identified analysis tables |
| `runner/runs/main_*` | Study JSON, predictions, metrics, tables, calibration and explanation plots, private SHAP/refit arrays |
| `runner/runs/lag0_*`, `rerun_mortality`, `repeats_*` | Sensitivity, determinism, 200 repeated-split results |
| `runner/export/` | Original aggregate-only export and ZIP, with calibration cells below 11 suppressed |
| `publication/results/summary.json` | Regenerated repeated-split summary |
| `publication/figs/fig{1,2,3,4}_*` | Cohort, discrimination, calibration and grouped-SHAP figures (PNG/PDF/SVG) |
| `publication/paper/out/PreOp_XAI_MOVER_IEEE.docx` | Regenerated paper and its three data tables |

The reference study fits real models in memory but does **not** serialize fitted
estimators. Reproduction retains the artifacts the original emits rather than
inventing a new model format. Private predictions and local explanation plots
remain local; only explicitly reviewed aggregate artifacts should be shared.

## Reference inventory

- `MOVER/preopxai/`: original data-holder runner, adapters, preparation and
  `preop_xai` modules. Its source is byte-identical to `run_on_mover/`.
- `PreOp_XAI_MOVER_code_and_verification/`: original source bundle, aggregate
  reference results, four figures, paper/template and verification records.
- `reference-source.sha256.json`: original Python source checksum inventory.
- `scripts/`: integration only; no reference scientific source is modified.

No notebooks were found outside the pre-existing Windows environment. The
general upstream `preop_xai/cli.py` also defines a separate YAML-configured
clinical workflow; its study configuration files are not supplied in this
bundle. The actual MOVER runner uses the packaged model/calibration/evaluation/
explanation/stability modules directly, as the reference run did.
