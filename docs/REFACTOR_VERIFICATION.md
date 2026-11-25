# Refactor verification

The restructure was checked against a baseline of commit `e4345ec`, run in an
isolated folder before any file was changed. Comparison tolerance: `rtol=1e-8`, `atol=1e-10`.
Runtime and OS metadata are excluded.

## Stage results

| Stage | Baseline exit | Baseline time | Refactored exit | Refactored time |
| --- | --- | --- | --- | --- |
| `check` | 0 | 0 s | 0 | 0 s |
| `prepare` | 0 | 55 s | 0 | 53 s |
| `protocol environment main` | 0 | 103 s | 0 | 104 s |

## Analysis tables

| Table | Rows | DataFrame equal | SHA-256 equal | SHA-256 |
| --- | --- | --- | --- | --- |
| `mover_analysis.csv` | 37196 | yes | yes | `66bc7dc57f03a91c2799dba4353b54f8cb669253ae1426873e16b499ccdde5bb` |
| `mover_analysis_lag0h.csv` | 37196 | yes | yes | `a0ba4c33227dd745b2a840616a5c3cd64a1c0c56d8f89d600ef0304a4b7d1d3e` |

The cohort flow, feature statistics and respiratory feasibility JSON files are also identical.

## Main-stage outputs

Every file in both main runs was compared, including patient-level arrays, which stay local.

| Type | Compared | Different |
| --- | --- | --- |
| `.csv` | 8 | 0 |
| `.json` | 10 | 0 |
| `.npz` | 14 | 0 |
| `.png` | 32 | 0 |
| **Total** | **64** | **0** |

## Key numbers

| Endpoint | Model | Test AUROC before | after | VitalDB AUROC before | after | VitalDB calibration slope before | after |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Mortality | LR | 0.916449 | 0.916449 | 0.670966 | 0.670966 | 0.550192 | 0.550192 |
| Mortality | XGBoost | 0.923359 | 0.923359 | 0.686695 | 0.686695 | 0.541178 | 0.541178 |
| ICU | LR | 0.751582 | 0.751582 | 0.688089 | 0.688089 | 1.007683 | 1.007683 |
| ICU | XGBoost | 0.754035 | 0.754035 | 0.658729 | 0.658729 | 0.720314 | 0.720314 |

## VitalDB input

The baseline used the earlier `vitaldb_clinical_data.csv`, which stores eight ages as `>89`. The refactored pipeline reads
`data/vitaldb/vitaldb_cases.csv`, which stores those patients' exact ages. All other columns match. The adapter now
top-codes ages above 89 to 90 for either encoding, so the feature matrix, cohort flow and external results are unchanged.

## Exact SHAP

The brute-force self-test passes: the largest tree error is below `1e-6`, and the linear error is about `1e-15`.

## Full pipeline

`all` ran once from an empty output folder on commit `6e1b7f0` and took 818 s (13.6 min) with 6 workers.

| Check | Result |
| --- | --- |
| `check`, `prepare`, `protocol`, `report` | exit 0 |
| Same-machine determinism rerun | identical |
| Refactored full run vs the pre-refactor full Linux run (225 JSON files) | no differences |
| Repeated-split `summary.json` vs the pre-refactor Linux run | identical |
| `verify` against committed Windows results | **exit 1: 115 of 226 artifacts differ** |

The `verify` failure existed before the refactor and is explained in [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md).

## Typer CLI migration

After the move to the `preopxai` command, `prepare` and `protocol environment main` were run
again from an empty output folder and compared with the same baseline at `rtol=1e-8`,
`atol=1e-10`.

| Check | Result |
| --- | --- |
| `prepare`, `protocol environment main` | exit 0, 54 s and 104 s |
| Analysis tables | DataFrame and SHA-256 equal |
| Cohort flow, feature statistics, respiratory feasibility | identical |
| Main-stage outputs (64 files) | equal; only `runtime_s` in `study.json` differs |
| `export-models` | PASS; saved models byte-identical to the previous export |
