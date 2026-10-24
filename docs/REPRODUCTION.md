# Local reproduction evidence

Date: October 24, 2026. Reference: supplied source marked
`6baa665be0635e118fc1edad2065a50e42f9bc81`, not an assumed local Git ancestor.
This workspace's Git branch was initially unborn. Its first commit imports the
existing implementation as one baseline.

## Environment and preservation

- Linux x86-64, AMD Ryzen 7 5800H, 16 logical CPUs, approximately 27 GiB RAM.
- uv 0.13.1; downloaded CPython 3.13.14, not the system Python 3.14.8.
- Exact reference scientific versions: scikit-learn 1.8.0, XGBoost 2.1.4,
  NumPy 2.4.4, pandas 3.0.2, SciPy 1.17.1, Matplotlib 3.10.9.
- Full dependency graph: `outputs/reproduction/logs/dependencies.txt`; exact
  distributions and wheel hashes: committed `uv.lock`.
- Scheduling: six repeat workers, `OMP_NUM_THREADS=1`,
  `OPENBLAS_NUM_THREADS=1`, `MKL_NUM_THREADS=1`.
- Source checksum check covers 102 original Python files in both reference
  trees. Original scientific source was not patched.
- No GPU is needed by the reference CPU histogram training. The machine's
  `nvidia-smi` command segfaulted during inspection; no result relies on it.

## Commands executed

From the repository root:

```sh
uv sync
uv run --locked python scripts/reproduce.py check
uv run --locked python scripts/reproduce.py prepare
uv run --locked python scripts/reproduce.py protocol
uv run --locked python -m scripts.publication --reference
uv run --locked basedpyright scripts
```

The initial protocol monitor had a five-minute deadline and stopped after the
determinism rerun. Process inspection confirmed it had exited before the same
protocol command resumed completed-stage checkpoints with a one-hour monitor
deadline. No historical runs were copied into the new `runner/runs` directory.
The run log records both invocations.

Independent clean-environment verification used a new
`UV_PROJECT_ENVIRONMENT` and new `UV_CACHE_DIR` beneath the task's temporary
directory, then ran:

```sh
uv sync --locked
uv run --locked python scripts/reproduce.py check
uv run --locked python outputs/reproduction/runner/tests/test_exact_shap.py
uv run --locked python -m scripts.publication --reference
```

All four commands exited zero. Logs: `logs/fresh-sync.log`,
`logs/fresh-shap.log`, `logs/check.log`, and `logs/publication-reference-*.log`
under `outputs/reproduction`. This separately exercised binary imports,
brute-force SHAP enumeration, figure rendering, bundled Pandoc, DOCX generation,
and the original independent paper audit.

## Raw preparation

The actual scripts processed the supplied EPIC data, including the entire
3,568,653,054-byte laboratory CSV. Cohort counts reproduced:

- 65,728 information rows, 39,685 patients and 64,354 operations.
- 38,194 indexed patients; 37,196 patients with known mortality.
- 314 deaths and 13,646 ICU admissions in the modelled cohort.

Both tables have 37,196 rows and reproduce the original bytes, not just rounded
metrics:

| Table | SHA256 of both regenerated and supplied file |
| --- | --- |
| `mover_analysis.csv` | `66bc7dc57f03a91c2799dba4353b54f8cb669253ae1426873e16b499ccdde5bb` |
| `mover_analysis_lag0h.csv` | `a0ba4c33227dd745b2a840616a5c3cd64a1c0c56d8f89d600ef0304a4b7d1d3e` |

Evidence: `logs/prepare.log` and `logs/preparation-comparison.json`. The original
primary and lag-0 laboratory mapping, timing, plausibility and tie-conflict
rules were used. Respiratory feasibility was also computed; the reference does
not train a respiratory model because its reviewed labels are insufficient.

## Primary analyses

Both endpoints used the original complete training/calibration/evaluation code.
Each primary full run included exact explanations, ten stability refits,
1,000 paired bootstraps and frozen-model VitalDB evaluation.

| AUROC, rounded as in reference log | LR | XGBoost |
| --- | ---: | ---: |
| Mortality, MOVER test | 0.916 | 0.923 |
| Mortality, VitalDB | 0.671 | 0.687 |
| ICU, MOVER test | 0.752 | 0.754 |
| ICU, VitalDB | 0.688 | 0.659 |
| Mortality, lag-0 | 0.935 | 0.939 |
| ICU, lag-0 | 0.771 | 0.782 |

The first mortality and ICU runs took 47.9 and 53.8 seconds respectively.
The complete mortality rerun was exactly identical excluding runtime according
to the original checker. The seed 1–1,000 split check reproduced the primary
test ICU count 2,049 and alternate range 1,932–2,157.

Evidence: `runner/runs/run_log.txt`, `main_*/study.json`,
`lag0_*/study.json`, `determinism_check.json` and `split_check.json`.
The final export comparison, not this rounded table, decides numerical agreement.

## Publication-reference validation

The separately labeled aggregate-reference run passed **193/193** original
independent paper checks. All four figures were regenerated at 600 dpi with
PDF and SVG sidecars, then inspected as images: readable labels, consistent
serif/grayscale style, no clipped labels or overlapping panels, and original
scientific comparisons retained. This validation alone is not a claim of
retrained results; newly computed publication output has a separate directory.

The original audit notes placeholder email addresses for three paper authors.
Those supplied author fields were not changed. The DOCX audit checks content
and structure, not six-page pagination across different office renderers.

## Scope limitations

The packaged MOVER study fits models in memory and saves predictions, metrics,
SHAP/refit arrays and aggregate evidence, not fitted estimator files. No new
serialization format or algorithm was added.

The separate generic YAML clinical CLI has no supplied study configuration in
this bundle. It was inspected, but not presented as a second verified clinical
protocol. Patient data, private predictions, runtime caches and virtual
environments remain unversioned. No remote push or publication was performed.

## Final new-results verification

The complete original scientific protocol finished all **200 repeated splits**
and exported **241 aggregate files** plus a 429 KiB ZIP. The observed wall interval
from first protocol start to complete export was 15 minutes 33 seconds, including
the monitor interruption/resume.

The documented full-workflow command was then executed in the independent fresh
uv environment:

```sh
uv run --locked python scripts/reproduce.py all
```

Preparation passed again. The original protocol resumed its completed real fits
and reexported. New-results summary, all four PNG/PDF/SVG figures, the paper and
its three data tables were generated. All four **new-results** PNGs were inspected
as images and passed the label/layout visual checks. SVG and PDF headers were
also read to confirm actual vector formats.

The original paper audit **failed**, and independent comparison **failed**.
They were not waived:

| Check | Result |
| --- | --- |
| Fresh locked environment, binary scientific imports | PASS |
| Actual raw-data preparation and original-table hashes | PASS |
| All original scientific stages, including 200 actual repeats | EXECUTED; diagnostic limitations below |
| Exact mortality determinism rerun | PASS |
| Original exact-SHAP brute-force test | PASS |
| New summary, four figures in three formats, DOCX/three tables | GENERATED |
| New paper's original audit | FAIL: null slope causes TypeError |
| Strict aggregate comparison | FAIL: 115 of 226 artifacts differ |
| Supplied-aggregate reference paper audit | PASS: 193/193 |
| Strict basedpyright on integration scripts | PASS: no errors or warnings |
| Original source preservation | PASS: 102 SHA256 checks, empty reference-tree Git diff |

The original SciPy BFGS diagnostic can report precision loss close to its
convergence threshold on this platform. Original code then returns nulls. This
changes the sample counts for some diagnostic summaries and exposes a null-handling
assumption in the paper audit. The evidence and exact seed-32 reproduction are
in `docs/KNOWN_LIMITATIONS.md`; the complete machine-readable differences remain
in `outputs/reproduction/logs/reference-comparison.json`.

Selected model hyperparameters, partition/event counts, and confusion/operating
counts have no reported differences. Remaining finite non-summary discrepancies
are small (largest reported absolute difference approximately `5.62e-7`).
This does not make unavailable diagnostic estimates or changed summary sample
counts equivalent. No tolerance or original check was relaxed.

Accordingly, `all`, new-results `publication`, and `verify` intentionally return
nonzero on this observed outcome. `all` still runs verification after a failed
publication audit so both independent failure records are retained.

To reproduce everything on a fresh checkout, restore the private inputs listed
in README, run `uv sync --locked`, then `uv run --locked python
scripts/reproduce.py all`. To reproduce the passing supplied-aggregate publication
alone, use `uv run --locked python -m scripts.publication --reference`.
