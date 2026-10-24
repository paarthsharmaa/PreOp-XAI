# Calibration portability and paper-audit failure

This is a local tracked issue, not an upstream issue or a suppressed test.
The original source and scientific settings remain unchanged.

## Reproduction

The full protocol was run with the exact reference Python/package versions and
byte-identical analysis tables. A smaller real-data reproduction is:

```sh
uv run --locked python scripts/reproduce.py protocol environment
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  PYTHONDONTWRITEBYTECODE=1 \
  uv run --locked python outputs/reproduction/runner/mover_study.py \
  mortality 32 outputs/reproduction/diagnostics/seed032 light \
  outputs/reproduction/runner/mover_analysis.csv
```

Inspect `evaluation.models.lr.calibration` in the resulting `study.json`.
The Windows reference has joint slope `0.7586415173149864`; the unchanged local
function returns null parameters and status `optimizer-not-converged`.

An observation-only wrapper around the **unchanged** optimizer captured:

```text
success: false
message: Desired error not necessarily achieved due to precision loss.
gradient infinity norm: 1.513814181255263e-6
requested tolerance: 1e-6
joint parameters: [-0.8012041420562731, 0.7586415185048265]
objective: 202.50526611572297
```

The returned slope is close to the reference, but the original
`preop_xai/evaluate.py:132` explicitly rejects failed optimization. It would be
incorrect to mark that result converged or fill nulls from reference outputs.
Running seed 32 independently reproduces the failure, ruling out concurrent
preparation or stale repeat artifacts as its cause. Disabling NumPy AVX2/FMA3
dispatch and selecting generic OpenBLAS did not change this example.

Evidence: `outputs/reproduction/diagnostics/{native,portable}/optimizer-observation.json`.
The temporary observation script was not part of the production implementation.

## Effect on verification

The original `paper/audit.py:171-172` constructs a NumPy array of mortality LR
test calibration slopes without handling nulls. Three local slopes are unavailable;
the reference has all 100. Consequently its quantile operation raises:

```text
TypeError: '<' not supported between instances of 'NoneType' and 'float'
```

The new paper and all figures have already been generated when the audit fails.
They must not be described as an audit-approved reproduction. In contrast,
the original supplied aggregate bundle passes the original audit **193/193**
in the same fresh uv environment.

The strict comparison of 226 generated aggregate JSON artifacts reports:

- 111 artifacts agree at `rtol=1e-8`, `atol=1e-10`; 115 differ.
- 1,008 reported differing paths, including summary differences.
- 102 numerical fields newly null, representing 34 diagnostic estimates.
- 66 formerly null fields now numerical, representing 22 diagnostic estimates.
- 56 diagnostic status changes; some fits converge here where the reference did
  not, and others exhibit the reverse.
- No missing artifacts, array-length differences, changed selected model
  parameters, partition/event-count changes, or confusion-count/operating-point
  count differences were reported.
- The largest reported non-summary numerical difference is
  `5.624812436932913e-7` in an ICU LR cross-validation AP.
- The reported test discrimination difference is
  `1.0915481807316496e-7` in ICU seed 32 XGBoost AP.
- The summary's mortality LR recalibrated-slope sample count is 97 rather than
  100. Its quantiles therefore cannot be declared identical.

Full evidence: `outputs/reproduction/logs/reference-comparison.json`,
`verify.log`, and `publication-audit.log`. Local full mortality determinism still
passes exactly excluding runtime. All cohort/preprocessing aggregates match.

The evidence identifies numerical portability and strict convergence handling,
not a different dataset or simplified algorithm. It does not establish which
individual native math kernel accounts for each cross-platform difference.

## What would resolve it

An exact reproduction of the original numerical runtime requires access to its
Windows/native-library environment, not just the same Python package versions.
Alternatively, a separately reviewed numerical-portability change could preserve
the likelihood while making its evaluation/optimization more robust. Such a change
needs scientific validation and a new run; it is not included here.

No optimizer failure was relabeled, tolerance relaxed, null filtered to force an
audit pass, reference result substituted, or scientific source edited.
