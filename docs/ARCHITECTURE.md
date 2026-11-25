# Architecture

```mermaid
flowchart LR
    A[(MOVER EPIC CSVs)] --> B[prepare<br/>data_prep/]
    B --> C[(outputs/tables)]
    C --> D[protocol<br/>pipeline/protocol.py]
    E[(VitalDB cases)] --> D
    D --> F[(outputs/runs<br/>patient-level)]
    D --> G[(outputs/export<br/>aggregate only)]
    G --> H[report<br/>summary + figures]
    H --> I[verify<br/>strict comparison]
    H -. make promote .-> J[(results/ + verification/)]
```

## Folders

| Path | Role |
| --- | --- |
| `src/preopxai/` | Core package: splits, training, calibration, evaluation, exact SHAP, stability, single-study runner (`study.py`) |
| `data_prep/` | MOVER cohort, lab extraction, feature tables, VitalDB adapter |
| `pipeline/` | CLI, path config, preparation, protocol, verification |
| `pipeline/reporting/` | Summary, figures, README table |
| `config/` | Path configuration |
| `results/` | Committed aggregate results and figures |
| `verification/` | Determinism check, SHAP self-test, split check, environment record, run log |
| `tests/` | pytest suite |
| `app/` | Dashboard: `build_data.py`, FastAPI backend (`api/`), React frontend (`web/`) and its tests |

## Stages

| Stage | Command | Output |
| --- | --- | --- |
| `check` | `make check` | Dependency and input validation |
| `prepare` | `make prepare` | Analysis tables |
| `protocol` | `make protocol` | Models, metrics, SHAP, stability, repeats, export |
| `report` | `make report` | `summary.json`, figures as PNG, PDF and SVG |
| `verify` | `make verify` | SHAP self-test and strict comparison with `results/` |
| `all` | `make all` | All of the above, in order |
| `export-models` | `make export-models` | Primary-split models in `artifacts/`, verified against `results/` (not part of `all`) |
| `app` | `make app` | Site data, local API and web app |

Protocol steps are `environment main lag0 rerun split_check repeats export`. Finished steps
are skipped, so an interrupted run can resume. To start clean, point `PREOPXAI_OUTPUTS` at an
empty folder.

## Configuration

`pipeline/config.py` is the only place paths are resolved. It reads `config/paths.toml`, and
`PREOPXAI_MOVER_RAW`, `PREOPXAI_VITALDB_CLINICAL`, `PREOPXAI_OUTPUTS` or `PREOPXAI_CONFIG`
override it. `PREOPXAI_WORKERS` changes parallelism only (default 6).

## Modules outside the main pipeline

`src/preopxai/` also contains a YAML-configured workflow (`cli.py`, `config.py`, `workflow.py`,
`cohort.py`, `labels.py`, `features.py`, `audit.py`, `status.py`, `demo.py`, `inference.py`).
It needs `typer`, `pyyaml` and `polars`, which are not in the locked environment, and the
pipeline does not call it.
