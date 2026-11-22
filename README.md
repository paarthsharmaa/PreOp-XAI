# PreOp-XAI

**Explainable preoperative risk prediction: does gradient boosting actually beat logistic regression?**

PreOp-XAI compares L2 logistic regression with XGBoost for predicting **in-hospital mortality** and
**ICU admission** from ten variables available before surgery. It goes beyond a single AUROC and
tests whether the models stay calibrated, whether their explanations are stable, and whether they
hold up at a different hospital.

- **Development cohort:** MOVER EPIC EMR, 37,196 surgical patients
- **External validation:** VitalDB, 6,019 patients, with models frozen before testing
- **Explanations:** exact interventional SHAP, checked against brute-force Shapley values
- **Robustness:** 1,000 bootstraps, 10 stability refits and 100 repeated splits per endpoint
- **Reproducible:** locked environment, fixed seeds and an automated determinism check

## Research questions

1. Does XGBoost discriminate better than a well-specified logistic regression on routine
   preoperative data?
2. Are predicted probabilities well calibrated after recalibration?
3. Are SHAP explanations stable when the model is refitted?
4. Does performance transport to an independent surgical population?

## Results at a glance

<!-- results:start -->
| Endpoint | Model | MOVER test AUROC (95% CI) | 100-split median AUROC (2.5–97.5%) | VitalDB AUROC (95% CI) | VitalDB calibration slope |
| --- | --- | --- | --- | --- | --- |
| In-hospital mortality | L2 logistic regression | 0.916 (0.865–0.958) | 0.925 (0.882–0.952) | 0.671 (0.567–0.758) | 0.550 |
| In-hospital mortality | XGBoost | 0.923 (0.871–0.961) | 0.927 (0.884–0.951) | 0.687 (0.594–0.768) | 0.541 |
| ICU admission | L2 logistic regression | 0.752 (0.738–0.765) | 0.743 (0.733–0.756) | 0.688 (0.670–0.708) | 1.008 |
| ICU admission | XGBoost | 0.754 (0.740–0.768) | 0.745 (0.736–0.758) | 0.659 (0.639–0.680) | 0.720 |
<!-- results:end -->

*Generated from `results/` by `make table`.*

- **XGBoost and logistic regression perform almost identically** across the 100 repeated splits.
- **Performance falls at external validation**, especially for mortality, where VitalDB has few
  events and calibration transports poorly.
- **Calibration diagnostics have a documented numerical-stability issue.** See
  [Known limitations](docs/KNOWN_LIMITATIONS.md).

| Discrimination | Calibration |
| --- | --- |
| ![ROC and precision-recall curves](results/figures/fig2_discrimination.png) | ![Decile calibration](results/figures/fig3_calibration.png) |

| Cohort and protocol | Grouped SHAP importance |
| --- | --- |
| ![Cohort flow](results/figures/fig1_cohort.png) | ![SHAP importance over refits](results/figures/fig4_shap.png) |

## Pipeline

```mermaid
flowchart LR
    A[(MOVER EPIC)] --> B[Cohort, labels,<br/>lab windows]
    B --> C[Analysis tables]
    C --> D[Train LR + XGBoost<br/>5-fold CV]
    D --> E[Recalibrate +<br/>set threshold]
    E --> F[Test evaluation<br/>1,000 bootstraps]
    E --> G[Exact SHAP +<br/>stability refits]
    E --> H[Frozen-model<br/>validation]
    V[(VitalDB)] --> H
    C --> R[100 repeated splits]
    F & G & H & R --> X[Aggregate export]
    X --> Y[Summary, figures,<br/>verification]
```

## Quickstart

Requires [uv](https://docs.astral.sh/uv/). Python 3.13 and all dependencies come from `uv.lock`.

```sh
make setup      # install the locked environment
make check      # validate dependencies and input files
make prepare    # build analysis tables from raw MOVER files
make protocol   # run the full study
make report     # generate the summary and figures
make verify     # SHAP self-test and strict comparison with results/
make test       # run the test suite
make all        # check, prepare, protocol, report and verify
```

A full run takes about 15 minutes on 16 cores with the default 6 workers. `make verify`, and so
`make all`, currently exits nonzero for the reason given in
[Known limitations](docs/KNOWN_LIMITATIONS.md).

## Dashboard

A local web app presents the findings and explains individual predictions from both models.

| Overview | Findings |
| --- | --- |
| ![Overview page](docs/screenshots/overview-desktop.png) | ![Findings page](docs/screenshots/findings-desktop.png) |

| Patient explorer | What-if change |
| --- | --- |
| ![Patient explorer](docs/screenshots/explorer-desktop.png) | ![What-if change in the explorer](docs/screenshots/explorer-whatif-desktop.png) |

| Methods | Team |
| --- | --- |
| ![Methods page](docs/screenshots/methods-desktop.png) | ![Team page](docs/screenshots/team-desktop.png) |

```sh
make export-models  # refit the primary split, save it to artifacts/ and verify it against results/
make app            # build the site data and start the API and web app on 127.0.0.1
make app-test       # API, SHAP additivity, determinism and traceability tests
make app-e2e        # Playwright smoke tests
make app-static     # build the findings-only static site
```

`make app` needs Node.js as well as uv. Open <http://127.0.0.1:5173>. `docker compose up --build` serves the same app
on <http://127.0.0.1:8080>, with `artifacts/` and `data/vitaldb/` mounted read-only.

- **Traceable numbers.** `app/build_data.py` generates all site data from `results/` and `verification/`, and a test
  recomputes every displayed number from its source.
- **Patient data.** MOVER rows and the SHAP background stay in the gitignored `artifacts/` folder and are used only by
  the local API. Example patients are public VitalDB records or labelled synthetic profiles.
- **Do not deploy the API publicly.** Its artifacts derive from MOVER patient data.
- **Publishing the findings site.** The GitHub Pages workflow runs only when triggered manually. Check first that your
  MOVER data usage agreement permits publishing these aggregates, including calibration deciles that imply small event
  counts.
- **XGBoost log-odds.** XGBoost accumulates margins in float32. The API reports the float64 sum of the same leaves so
  that SHAP values add up exactly, and it computes probabilities from the native margin, as the study did.

VitalDB is used under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Cite Lee HC et al., *Sci Data* 2022;9:279,
[doi:10.1038/s41597-022-01411-5](https://doi.org/10.1038/s41597-022-01411-5). Records were sampled, identifiers removed,
ages above 89 top-coded to 90 and fields renamed.

## Data

MOVER and VitalDB are not distributed here. Obtain them under their own terms and place them as
described in [`data/README.md`](data/README.md). Paths are set in `config/paths.toml` and can be
overridden with environment variables.

Patient-level data, predictions and per-patient SHAP values never enter git. Only aggregate results
are committed, with calibration cells under 11 patients removed, and a test enforces this.

## Repository layout

```text
app/             dashboard: data build, local API and web frontend
src/preopxai/    core modelling, calibration, evaluation, SHAP and stability
data_prep/       MOVER cohort, lab extraction, feature tables, VitalDB adapter
pipeline/        CLI, configuration, protocol, reporting, verification
config/          path configuration
data/            local data (ignored by git)
results/         committed aggregate results and figures
verification/    determinism, SHAP self-test, split check, environment record
docs/            methods, data, architecture, limitations, verification
tests/           pytest suite
```

## Documentation

- [Methods](docs/METHODS.md)
- [Data](docs/DATA.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Known limitations](docs/KNOWN_LIMITATIONS.md)
- [Refactor verification](docs/REFACTOR_VERIFICATION.md)

## Team

B.Tech minor project, AI & Data Science, VIPS.

- **Project group:** Paarth Sharma, Manas Lahora, Yug Sharma
- **Supervisor:** Ms Anjani Gupta

*Research software. Not validated for clinical use.*
