# Data

See [`data/README.md`](../data/README.md) for the expected layout and download sources.

## Inputs the pipeline reads

| File | Used for |
| --- | --- |
| `patient_information.csv` | Eligibility, index operation, anaesthesia times, age, sex, ASA, mortality and ICU labels |
| `patient_labs.csv` | Haemoglobin, platelets, creatinine, BUN, sodium, potassium, glucose |
| `patient_post_op_complications.csv` | Aggregate feasibility count for a respiratory endpoint (not modelled) |
| `vitaldb_cases.csv` | External cohort, outcomes and the same ten predictors |

The other six MOVER files and `vitaldb_labs.csv` are not read.

## Generated tables

`prepare` writes these to `outputs/tables/`:

| File | Contents |
| --- | --- |
| `mover_analysis.csv` | Primary table, labs from 30 days to 24 hours before anaesthesia start |
| `mover_analysis_lag0h.csv` | Sensitivity table, labs from 30 days to anaesthesia start |
| `mover_cohort_flow.json` | Aggregate cohort flow |
| `mover_feature_stats*.json` | Aggregate feature statistics |
| `mover_respiratory_feasibility.json` | Aggregate respiratory endpoint counts |

The analysis tables contain one row per patient with no identifiers or dates, but they
are still patient-level and must stay out of git.

## What may be committed

Only aggregates: metrics, intervals, model settings, SHAP summaries, curve coordinates and
decile calibration. Calibration cells describing fewer than 11 patients are removed at
export. `tests/test_data_guard.py` fails if any file under `data/`, any non-aggregate CSV,
or any pickle or array file is tracked.

`artifacts/` holds the fitted models and the 64-row MOVER SHAP background. It is ignored by
git, excluded from Docker build contexts and read only by the local API.

Check that sharing these aggregates is permitted under your MOVER data usage agreement
before making the repository public.
