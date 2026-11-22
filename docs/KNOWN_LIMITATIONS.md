# Known limitations

## Numerical stability of the calibration diagnostics

`make verify` currently **fails**: 115 of 226 aggregate JSON artifacts differ from the committed
`results/` at `rtol=1e-8`, `atol=1e-10`. The tolerances have not been loosened and the committed
results have not been overwritten to make the check pass.

The committed `results/` were generated on Windows 11. The comparison run was on Linux, with the
same Python, dependency versions, inputs and seeds.

**What differs**

1. **Calibration optimiser outcomes.** Test-set calibration slope and intercept are fitted with
   SciPy BFGS. On some repeated splits the optimiser stops with a precision-loss warning, and the
   pipeline then records the diagnostic as `optimizer-not-converged` and stores no value. Which
   fits fail depends on the platform:

   | Platform | Non-converged fits (of 800) | ICU | Mortality |
   | --- | --- | --- | --- |
   | Windows (committed) | 26 | 24 | 2 |
   | Linux | 38 | 33 | 5 |

   Summary statistics of calibration slope and intercept are therefore computed over slightly
   different sets of splits. For example, the median calibrated slope for ICU XGBoost is 1.0012 on
   Windows and 0.9994 on Linux.

2. **Small floating-point shifts.** Where both platforms produce a value, the largest absolute
   difference in the per-run artifacts is about `6e-7`. This affects CV scores, recalibration
   parameters, thresholds, calibration bins and some SHAP summaries. The pattern is consistent with
   platform floating-point differences, but that cause has not been isolated.

**What does not differ**

- All eight primary test and VitalDB AUROCs are equal.
- The median AUROCs over the 100 repeated splits are equal.
- The split check and the same-machine determinism check are unchanged.
- On one machine, repeated runs are identical, including a full run before and after the
  repository restructure.

**How to read it:** discrimination results are stable across platforms. Calibration slope and
intercept summaries from repeated splits should be quoted to about two decimal places, with the
number of converged fits stated.

## Study design

- **Few mortality events.** The primary test set has 47 deaths, so mortality intervals are wide.
- **External validation has 41 deaths.** VitalDB mortality estimates are imprecise, and mortality
  calibration transports poorly.
- **Two sources, no prospective test.** MOVER is from one health system and VitalDB from one
  hospital. Neither validation is prospective.
- **Laboratory timing is a proxy.** Collection time is used because result-availability time is
  not available.
- **Restricted predictors.** The model uses ten routinely available variables by design.
  Comorbidities, medications and procedure type are not included.
- **Unknown outcomes are excluded.** Patients transferred or discharged to hospice have unknown
  in-hospital mortality and are not modelled.
- **Research use only.** These models are not validated for clinical decisions.

## Software

- The committed results were produced on Windows and the verification run on Linux. Windows was
  not rerun during the restructure.
- The YAML workflow in `src/preopxai/` needs packages outside the locked environment and is not
  part of the pipeline. See [ARCHITECTURE.md](ARCHITECTURE.md).
- Linux wheels need glibc and OpenMP (`libgomp`). Other operating systems are not tested with this
  layout.
