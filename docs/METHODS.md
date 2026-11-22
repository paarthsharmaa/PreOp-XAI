# Methods

## Question

Does XGBoost improve on L2 logistic regression for preoperative prediction of in-hospital
mortality and ICU admission, and are its probabilities, explanations and performance
reliable enough to trust across data splits and across hospitals?

## Cohort (MOVER EPIC)

- Adults with a valid ASA class (ASA VI and donors excluded) and a valid anaesthesia interval.
- One index operation per patient: the first eligible operation.
- Mortality comes from discharge disposition. Transfers, hospice and unknown dispositions are
  treated as unknown, not as survival, and are excluded from modelling.
- Final cohort: 37,196 patients, 314 deaths, 13,646 ICU admissions.

## Predictors

Age, sex, ASA class and the latest preoperative haemoglobin, platelets, creatinine, BUN,
sodium, potassium and glucose.

- Laboratory identity is fixed by LOINC code and unit, with plausibility limits.
- Primary window: 30 days to 24 hours before anaesthesia start. Sensitivity window: 30 days
  to anaesthesia start.
- If the latest values for a concept conflict, that concept is set to missing.

## Modelling

| Step | Setting |
| --- | --- |
| Split | 70/15/15 train/validation/test, stratified on mortality, seed 2026 |
| Preprocessing | Median imputation, missingness indicators, one-hot encoding; scaling for LR only; fitted inside each fold |
| Logistic regression | L2, `C` in {0.1, 1, 10}, L-BFGS, 3,000 iterations |
| XGBoost | Depth {2, 3}, trees {100, 200, 300}, learning rate {0.03, 0.1}, `min_child_weight` 5, `reg_lambda` 5, `hist` |
| Selection | 5-fold stratified CV on training data, scored by average precision; ties keep the simpler candidate |
| Recalibration | Unpenalised logistic recalibration of log-odds on the validation set |
| Operating point | Highest validation threshold with sensitivity of at least 0.80 |

## Evaluation

- AUROC, average precision, Brier score, calibration slope and intercept, and operating-point
  metrics on the held-out test set.
- 1,000 paired bootstrap resamples for intervals and model differences.
- 100 repeated splits (seeds 1–100) per endpoint, repeating the whole fit.
- A lag-0 sensitivity analysis and a split check over seeds 1–1,000.

## Explanation

- Exact interventional SHAP on the log-odds scale, using 64 background rows from training data.
- The implementation in `src/preopxai/exact_shap.py` is checked against brute-force Shapley
  enumeration.
- Stability is measured over 10 paired bootstrap refits with fixed hyperparameters.

## External validation

Models and their MOVER recalibration are frozen, then applied to 6,019 VitalDB patients.
VitalDB follows the same eligibility logic where its fields allow. The lowest case
identifier is indexed for each patient because cross-case chronology is not recoverable.
