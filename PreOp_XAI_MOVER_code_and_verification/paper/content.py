# -*- coding: utf-8 -*-
"""Paper text. Every quantitative statement is formatted from the aggregate outputs of the MOVER run
(results/*, exported from the data holder's computer) at build time. Citations as [[key]]; inline math as
$latex$; paragraph markers EQ:, FIG:, TAB:."""
import glob as _glob
import json as _json
import os as _os

import numpy as _np

_R = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "..", "results")
_J = lambda *p: _json.load(open(_os.path.join(_R, *p)))
_M, _I = _J("main_mortality", "study.json"), _J("main_icu", "study.json")
_L0 = {"mortality": _J("lag0_mortality", "study.json"), "icu": _J("lag0_icu", "study.json")}
_S = _J("summary.json")
_SC = _J("split_check.json")
_DET = _J("determinism_check.json")
_ENV = _J("environment.json")
FLOW = _J("cohort", "mover_cohort_flow.json")
LABS = _J("cohort", "mover_feature_stats.json")
LABS0 = _J("cohort", "mover_feature_stats_lag0h.json")
RESP = _J("cohort", "mover_respiratory_feasibility.json")["modelled"]
STUDY = {"mortality": _M, "icu": _I}
VF = _M["external_vitaldb"]["flow"]
_REP = {e: [r for r in (_json.load(open(f)) for f in sorted(_glob.glob(_os.path.join(_R, f"repeats_{e}", "seed*.json"))))
            if 1 <= r["seed"] <= 100] for e in STUDY}
assert all(len(v) == 100 for v in _REP.values()) and _DET["identical_except_runtime"]


def f3(x):
    return f"{x:.3f}".replace("-", "−")


def f4(x):
    return f"{x:.4f}".replace("-", "−")


def f2(x):
    return f"{x:.2f}".replace("-", "−")


def pct(x, d=1):
    return f"{100 * x:.{d}f}%"


def n(x):
    return f"{x:,}"


def rng(lo, hi, fmt=f3):
    """Interval text; 'to' instead of an en dash when a bound is negative."""
    if fmt(lo) == fmt(hi):
        return fmt(lo)
    return f"{fmt(lo)} to {fmt(hi)}" if lo < 0 or hi < 0 else f"{fmt(lo)}–{fmt(hi)}"


def ev(e, m):
    return STUDY[e]["evaluation"]["models"][m]


def ex(e, m):
    return STUDY[e]["external_vitaldb"]["models"][m]


def lag(e, m):
    return _L0[e]["evaluation"]["models"][m]


def ci(e, key, src="evaluation", fmt=f3):
    d = STUDY[e][src] if src != "lag0" else _L0[e]["evaluation"]
    iv = d["intervals"][key]
    return rng(iv["lower"], iv["upper"], fmt)


def diff(e, metric, variant="raw", get=ev):
    return get(e, "xgboost")[variant][metric] - get(e, "lr")[variant][metric]


def stab(e, m):
    return STUDY[e]["stability"]["models"][m]


def sel(e, m):
    return STUDY[e]["selection"][m]


def rs(e, m, key):
    return _S[e][m][key]


def q(e, key):
    return _S[e][key]


NS = _S["mortality"]["splits"]
TE = {e: STUDY[e]["partition_events"] for e in STUDY}
PN = _M["partition_n"]
NMOD, DEATHS, ICU = FLOW["mortality_known"], FLOW["mortality_events"], FLOW["icu_flag_yes_among_known"]
_EXC = FLOW["exclusions"]
_DEDUP = FLOW["rows"] - FLOW["exact_duplicates_removed"]
_ELIG = _DEDUP - sum(_EXC[k] for k in ("operation_conflict", "not_adult", "invalid_or_donor_asa", "invalid_anesthesia_boundary"))
_mL, _mX, _iL, _iX = ev("mortality", "lr"), ev("mortality", "xgboost"), ev("icu", "lr"), ev("icu", "xgboost")
_xmL, _xmX, _xiL, _xiX = ex("mortality", "lr"), ex("mortality", "xgboost"), ex("icu", "lr"), ex("icu", "xgboost")
_LABK = ("hemoglobin", "platelets", "creatinine", "bun", "sodium", "potassium", "glucose")
_miss = [LABS["missing_pct"][k] for k in _LABK]
_miss0 = [LABS0["missing_pct"][k] for k in _LABK]
_C = {k: _M["characteristics"][k] for k in ("all", "event", "no_event")}
_CI = _I["characteristics"]["event"]
_CV = _M["external_vitaldb"]["characteristics"]["all"]
_asa12 = lambda c: c["asa_pct"]["1"] + c["asa_pct"]["2"]
_vmiss = [_CV[k]["missing_pct"] for k in _LABK]
_mlab_test = _mL["missing_labs_mean"]
_mlab_ext = _xmL["missing_labs_mean"]

TITLE = ("Explainable Preoperative Risk Prediction on the MOVER Surgical Database: Logistic Regression versus "
         "XGBoost with Calibration, Explanation Stability and External Validation")

CSE = dict(dept="Department of CSE", org="Amity University", city="Noida, India")
AUTHORS = [
    dict(name="Raghav Goel", email="[email]", **CSE),
    dict(name="Bhavya Mansharamani", email="[email]", **CSE),
    dict(name="Subhash Chand Gupta", email="[email]", **CSE),
    dict(name="Prakhar Chandra", email="prakharchandra018@gmail.com", **CSE),
    dict(name="Shipra Saraswat", email="sshipra1510@gmail.com", **CSE),
]

ABSTRACT = (
    "Gradient-boosted trees explained with Shapley additive explanations (SHAP) are increasingly proposed for "
    "preoperative risk prediction, but their advantage over logistic regression (LR), the calibration of their "
    "probabilities, the reproducibility of their explanations and their transportability are rarely examined "
    "together. We executed the leakage-controlled PreOp-XAI protocol on the MOVER EPIC database: one operation per "
    "adult patient, age, sex, ASA class and seven laboratory values collected 30 days to 24 hours before "
    "anaesthesia, a 70/15/15 patient-level split, training-only tuning, validation-only recalibration, exact "
    "interventional SHAP with ten paired bootstrap refits, 100 repeated splits and external validation of the frozen "
    f"models on VitalDB. Among {n(NMOD)} patients, {DEATHS} ({pct(DEATHS / NMOD, 2)}) died in hospital and "
    f"{n(ICU)} ({pct(ICU / NMOD)}) were admitted to an intensive care unit (ICU). Over {NS} splits, median test "
    f"AUROCs of LR and XGBoost were {f3(rs('mortality', 'lr', 'auroc')['median'])} and "
    f"{f3(rs('mortality', 'xgboost', 'auroc')['median'])} for mortality and {f3(rs('icu', 'lr', 'auroc')['median'])} "
    f"and {f3(rs('icu', 'xgboost', 'auroc')['median'])} for ICU admission, with paired differences within "
    f"{f3(max(abs(q('mortality', 'diff_auroc')['p2_5']), abs(q('mortality', 'diff_auroc')['p97_5'])))} in 95% of "
    "splits. Recalibrated risks were well calibrated internally, and ASA class dominated both models’ explanations, "
    f"whose mortality rankings were reproducible across refits (mean Spearman {f2(stab('mortality', 'lr')['spearman_mean'])} "
    f"and {f2(stab('mortality', 'xgboost')['spearman_mean'])}). On {n(VF['modelled_patients'])} VitalDB patients, "
    f"AUROCs fell to {f3(_xmL['raw']['auroc'])}–{f3(_xmX['raw']['auroc'])} for mortality and "
    f"{f3(_xiX['raw']['auroc'])}–{f3(_xiL['raw']['auroc'])} for ICU admission, with marked miscalibration linked to "
    "differences in case mix and laboratory-testing patterns. Boosting offered no measurable advantage, and "
    "internal discrimination and calibration did not transfer to another health system.")

KEYWORDS = ("preoperative risk prediction, explainable artificial intelligence, SHAP, XGBoost, logistic regression, "
            "calibration, external validation, MOVER")

SECTIONS = []
SECTIONS.append(("Introduction", None, [
    "Estimating the risk of death or of a need for intensive care before anaesthesia supports consent, planning of "
    "postoperative care and allocation of critical-care beds. Machine-learning models built from routinely "
    "available electronic health record (EHR) data predict postoperative mortality [[leeck18]], with areas under "
    "the receiver operating characteristic curve (AUROC) above 0.9 in large cohorts [[hill19]], [[lee22npj]], "
    "[[choi22]], and multi-outcome systems such as MySurgeryRisk extend this to major complications [[bihorac19]]. "
    "Gradient-boosted trees such as XGBoost [[chen16]] are usually paired with SHapley Additive exPlanations (SHAP) "
    "[[lundberg17]], [[lundberg20]] so that clinicians can see which inputs drive a prediction [[lundberg18]].",

    "Four questions are often left open: whether boosting outperforms a regularised logistic regression (LR) built "
    "from the same inputs [[christodoulou19]]; whether predicted probabilities are calibrated, since good ranking "
    "does not imply good calibration [[vancalster19]]; whether explanations are reproducible when the model is "
    "refitted on a slightly different sample [[riley23]], [[nogueira18]]; and whether a model and its explanation "
    "transfer to another hospital, where case mix and the processes that generate EHR data differ [[debray15]], "
    "[[agniel18]].",

    "This paper executes the PreOp-XAI pipeline, a fixed, leakage-controlled protocol, on the database for which it "
    "was designed, the Medical Informatics Operating Room Vitals and Events Repository (MOVER) [[samad23]], and "
    "validates the frozen models on the independent VitalDB cohort [[vitaldb22]]. The contributions are: (i) a "
    "paired comparison of LR and XGBoost for in-hospital mortality and ICU admission covering discrimination, "
    "calibration and fixed-threshold performance over 100 repeated splits; (ii) exact interventional SHAP values "
    "for both model families with a paired-refit analysis of explanation stability; (iii) external validation of "
    "the frozen models, recalibration and thresholds in another country’s health system; and (iv) an execution in "
    "which patient-level data never left the data holder’s computer.",
]))

SECTIONS.append(("Related Work", None, [
    "Lee *et al.* predicted in-hospital mortality with a deep neural network from features available at the end of "
    "surgery [[leeck18]], and Hill *et al.* reached an AUROC of 0.932 "
    "in 53,097 patients with an automated model on readily extractable preoperative EHR data [[hill19]]. In a "
    "four-centre study of 454,404 adults, XGBoost models with 12–18 preoperative variables reached AUROCs of up to "
    "0.942 internally and 0.941 externally for 30-day mortality and were explained with SHAP [[lee22npj]]. Hadaya *et al.* found similar "
    "discrimination for boosting and LR in predicting respiratory failure after emergency surgery [[hadaya22]].",

    "The apparent advantage of machine learning over LR largely disappears in comparisons at low risk of bias "
    "[[christodoulou19]]. Riley and Collins showed that models developed on small "
    "samples are unstable across bootstrap refits [[riley23]], sample size should be planned from the number of "
    "events [[riley20]], and Nogueira *et al.* formalised stability measures for selected feature sets "
    "[[nogueira18]]. Calibration should be assessed with intercepts and slopes, not only discrimination [[cox58]], "
    "[[vancalster19]], [[steyerberg14]], and external validation results depend on how related the validation "
    "sample is to the development sample [[debray15]]. In EHR data, whether and when a test is ordered carries "
    "information about the patient [[agniel18]], [[groenwold20]], and reporting should follow TRIPOD+AI "
    "[[collins24]].",
]))

SECTIONS.append(("Data and Methods", None, []))
SECTIONS.append((None, "Development Cohort and Outcomes", [
    "MOVER contains EHR and monitoring data from the University of California, Irvine Medical Center "
    "[[samad23]]; under the data use agreement we used its EPIC EHR tables, whose patient-information table lists "
    f"{n(FLOW['patients'])} patients and {n(FLOW['operations'])} operations. After removing {n(FLOW['exact_duplicates_removed'])} exact duplicate rows, operations were eligible if "
    f"their identifier was not in conflict ({_EXC['operation_conflict']} excluded), the patient was an adult "
    f"({_EXC['not_adult']}), the ASA class was valid and not VI ({_EXC['invalid_or_donor_asa']}), and anaesthesia end "
    f"followed its start ({n(_EXC['invalid_anesthesia_boundary'])}). The first eligible operation of each patient was "
    f"indexed ({n(FLOW['indexed_patients'])} patients). The primary endpoint, in-hospital death, was defined from "
    "the discharge disposition (expired or coroner); transfers to another acute hospital, hospice and missing "
    "dispositions were labelled unknown, not survival, as were stays whose admission and discharge did not span the "
    f"anaesthetic, leaving {n(NMOD)} modelled patients (Fig. 1). The secondary endpoint was ICU admission during the "
    "index hospitalisation, from MOVER’s ICU flag, which is not time-stamped, so preoperative ICU stays cannot be "
    "excluded. The protocol’s optional respiratory endpoint was not feasible: among the modelled patients, "
    f"{RESP['positive_only']} operations had consistent documentation of a respiratory complication in the "
    f"anaesthesia quality-improvement record, {RESP['contradictory']} had contradictory entries and "
    f"{n(RESP['negative_only'])} were documented as complication-free.",
    "FIG:cohort",
]))
SECTIONS.append((None, "Predictors and Preprocessing", [
    "The ten concepts were age, sex, ASA physical status I–V [[mayhew19]] (missing coded as a separate category) "
    "and the most recent preoperative haemoglobin, platelet count, creatinine, blood urea nitrogen (BUN), sodium, "
    "potassium and glucose. Laboratory results were identified by LOINC code and unit, values outside "
    "physiologically plausible ranges were discarded, and, because MOVER provides collection but not result-release "
    "times, results were used only if collected between 30 days and 24 hours before anaesthesia start, a "
    "conservative proxy for availability at the time of prediction. Of "
    f"{n(LABS['candidate_rows'])} candidate results for modelled operations, {n(LABS['unmapped_code_or_unit'])} had an "
    f"unmapped code or unit, {n(LABS['reasons']['eligible'])} met this rule and {n(LABS['reasons']['future_collection'])} were collected after anaesthesia start. Inside every "
    "training fold, numeric values were median-imputed, missingness indicators were added for the seven laboratory "
    "values, sex and ASA were one-hot encoded, and, for LR only, numeric values were standardised [[pedregosa11]], "
    "giving 23 model inputs. No identifiers, procedure or intraoperative data entered the models.",
]))
SECTIONS.append((None, "Models, Selection and Recalibration", [
    f"Patients were split 70/15/15 into training ({n(PN['train'])}), validation ({n(PN['validation'])}) and test "
    f"({n(PN['test'])}) sets with the repository’s default seed (2026), stratified on death; both endpoints used the "
    "same patients. L2-penalised LR models the log-odds as",
    "EQ:s(\\mathbf{x})=\\beta_{0}+\\boldsymbol{\\beta}^{\\top}\\mathbf{x},\\qquad p(\\mathbf{x})=\\sigma\\left(s(\\mathbf{x})\\right),",
    "with $C\\in\\{0.1,1,10\\}$. XGBoost [[chen16]] used 12 settings (depth 2 or 3; 100, 200 or 300 trees; learning "
    "rate 0.03 or 0.1; minimum child weight 5; $\\lambda=5$). Each family was tuned by mean average precision (AP) "
    "over five stratified training folds and refitted on the full training set, without class weighting or "
    "resampling. A logistic recalibration [[cox58]]",
    "EQ:p_{\\mathrm{cal}}(\\mathbf{x})=\\sigma\\left(a+b\\,s(\\mathbf{x})\\right)",
    "was fitted on the validation set, where the operating threshold was also fixed as the highest threshold "
    "retaining at least 80% sensitivity. Test data were used once, after these choices were frozen.",
]))
SECTIONS.append((None, "Evaluation and External Validation", [
    "We report AUROC, AP [[saito15]], the Brier score with the reference of a constant training-prevalence "
    "prediction, calibration-in-the-large (CITL; intercept with the logit as offset), the calibration slope "
    "[[cox58]], [[vancalster19]] and threshold metrics. Uncertainty was estimated with 1,000 bootstrap resamples of "
    "test patients shared by both models, giving percentile intervals for paired differences [[efron93]]. To "
    "quantify split dependence, the entire protocol (splitting, selection, recalibration, thresholding and testing) "
    f"was repeated for split seeds 1–{NS}. For external validation, the frozen MOVER models, recalibration maps and "
    f"thresholds were applied without any update to {n(VF['modelled_patients'])} adult VitalDB patients from Seoul "
    "National University Hospital with a known in-hospital outcome (one operation per patient; ICU admission "
    "defined as an ICU stay of at least one day) [[vitaldb22]], whose laboratory values are the most recent "
    "preoperative results recorded by VitalDB. A sensitivity analysis repeated the primary analysis with laboratory "
    "results collected up to anaesthesia start.",
]))
SECTIONS.append((None, "Explanations and Stability", [
    "SHAP values were computed on the raw log-odds of the validation patients against 64 training patients drawn "
    "with a fixed seed, under the interventional convention [[lundberg20]], [[sundararajan20]]. The players $D$ are "
    "the model inputs. For a background row $\\mathbf{z}$, the value $v_{\\mathbf{z}}(S)$ of a coalition $S$ is the "
    "model output on the hybrid row that takes $\\mathbf{x}$ on $S$ and $\\mathbf{z}$ elsewhere, and",
    "EQ:\\phi_{j}(\\mathbf{x})=\\frac{1}{|B|}\\sum_{\\mathbf{z}\\in B}\\sum_{S\\subseteq D\\setminus\\{j\\}}"
    "\\frac{|S|!\\,(|D|-|S|-1)!}{|D|!}\\left[v_{\\mathbf{z}}(S\\cup\\{j\\})-v_{\\mathbf{z}}(S)\\right].",
    "For LR this reduces to $\\beta_{j}(x_{j}-\\bar{z}_{j})$. For trees, each leaf defines a product game with "
    "closed-form Shapley values, so the values were computed exactly from the XGBoost tree dump; they matched "
    "brute-force enumeration to within $10^{-6}$ and satisfied additivity on every model. As in the repository, values of the one-hot and "
    "missingness columns were summed per concept; because these columns are perturbed independently, the sums are "
    "not concept-level Shapley values. For stability, both models were refitted on ten bootstrap samples of the "
    "training patients with fixed hyperparameters [[riley23]]; from the concept importances (mean absolute SHAP) we "
    "computed the Spearman correlation between refits and the Jaccard overlap of the five most important concepts,",
    "EQ:J(A,B)=\\frac{|A\\cap B|}{|A\\cup B|},",
    "averaged over the 45 refit pairs [[nogueira18]].",
]))
SECTIONS.append((None, "Implementation, Privacy and Deviations", [
    "The PreOp-XAI repository (commit 6baa665) was used unchanged for model fitting, recalibration, evaluation, "
    f"explanation and stability, with scikit-learn {_ENV['packages']['scikit-learn']} and XGBoost "
    f"{_ENV['packages']['xgboost']}. All computation on MOVER ran on the data holder’s computer; only aggregate "
    "results were exported, with calibration cells of fewer than 11 patients suppressed. A second run of the primary "
    "mortality analysis reproduced every exported value. Cohort and label rules were ported to pandas, and missing "
    "ASA was encoded as an explicit category because the repository’s explanation step bypasses its training-time "
    "handling of missing categories. Relative to the protocol, this study (i) used "
    "collection time as a proxy for result availability, (ii) replaced the infeasible respiratory endpoint with ICU "
    "admission, and (iii) added the repeated-split, sensitivity and external analyses.",
]))

# ---------------------------------------------------------------- results
_c = _C["event"], _C["no_event"]
SECTIONS.append(("Results", None, []))
SECTIONS.append((None, "Cohort", [
    f"The median age was {_C['all']['age_median']:.0f} years, {_C['all']['female_pct']:.1f}% were women and "
    f"{_C['all']['asa_pct']['3'] + _C['all']['asa_pct']['4'] + _C['all']['asa_pct']['5']:.1f}% were ASA III–V "
    f"(Table I). Patients who died were older and mostly ASA IV–V ({_c[0]['asa_pct']['4'] + _c[0]['asa_pct']['5']:.1f}% "
    f"versus {_c[1]['asa_pct']['4'] + _c[1]['asa_pct']['5']:.1f}%). Under the 24-hour rule, each laboratory value was "
    f"missing for {min(_miss):.1f}–{max(_miss):.1f}% of patients, but for only "
    f"{min(_c[0][k]['missing_pct'] for k in _LABK):.1f}–{max(_c[0][k]['missing_pct'] for k in _LABK):.1f}% of those "
    f"who died. The VitalDB cohort was healthier ({_asa12(_CV):.1f}% ASA I–II versus {_asa12(_C['all']):.1f}%) and "
    f"almost completely tested ({min(_vmiss):.1f}–{max(_vmiss):.1f}% missing). Each test set held "
    f"{TE['mortality']['test']} deaths; the primary test set held {n(TE['icu']['test'])} ICU admissions, a typical "
    f"value among {_SC['alt_seeds'][1]:,} alternative splits (range {n(_SC['alt_test_icu_min'])}–"
    f"{n(_SC['alt_test_icu_max'])}).",
    "TAB:cohort",
]))
SECTIONS.append((None, "Discrimination", [
    f"For mortality, LR and XGBoost had test AUROCs of {f3(_mL['raw']['auroc'])} (95% CI {ci('mortality', 'lr.raw.auroc')}) "
    f"and {f3(_mX['raw']['auroc'])} ({ci('mortality', 'xgboost.raw.auroc')}), a paired difference of "
    f"{f3(diff('mortality', 'auroc'))} ({ci('mortality', 'paired_xgboost_minus_lr.raw.auroc')}), and AP of "
    f"{f3(_mL['raw']['average_precision'])} and {f3(_mX['raw']['average_precision'])} against a prevalence of "
    f"{f4(STUDY['mortality']['evaluation']['prevalence'])} (Table II, Fig. 2). For ICU admission, AUROCs were "
    f"{f3(_iL['raw']['auroc'])} ({ci('icu', 'lr.raw.auroc')}) and {f3(_iX['raw']['auroc'])} ({ci('icu', 'xgboost.raw.auroc')}), "
    f"with a difference of {f3(diff('icu', 'auroc'))} ({ci('icu', 'paired_xgboost_minus_lr.raw.auroc')}). Over the "
    f"{NS} repeated splits, median mortality AUROCs were {f3(rs('mortality', 'lr', 'auroc')['median'])} and "
    f"{f3(rs('mortality', 'xgboost', 'auroc')['median'])}, 95% of paired differences lay between "
    f"{f3(q('mortality', 'diff_auroc')['p2_5'])} and {f3(q('mortality', 'diff_auroc')['p97_5'])}, and XGBoost was "
    f"ahead in {pct(q('mortality', 'diff_auroc')['share_xgb_better'], 0)} of splits; LR had the higher AP in "
    f"{pct(1 - q('mortality', 'diff_ap')['share_xgb_better'], 0)}. For ICU admission, XGBoost had a higher AUROC in "
    f"{pct(q('icu', 'diff_auroc')['share_xgb_better'], 0)} of splits, but by a median of only "
    f"{f4(q('icu', 'diff_auroc')['median'])} (95% of splits {rng(q('icu', 'diff_auroc')['p2_5'], q('icu', 'diff_auroc')['p97_5'])}), "
    f"and AP did not differ (median {f4(q('icu', 'diff_ap')['median'])}).",
    "TAB:perf",
    "FIG:discrimination",
    "When laboratory results collected up to anaesthesia start were allowed, missingness fell to "
    f"{min(_miss0):.1f}–{max(_miss0):.1f}% and AUROCs rose to {f3(lag('mortality', 'lr')['raw']['auroc'])} (LR) and "
    f"{f3(lag('mortality', 'xgboost')['raw']['auroc'])} (XGBoost) for mortality and to "
    f"{f3(lag('icu', 'lr')['raw']['auroc'])} and {f3(lag('icu', 'xgboost')['raw']['auroc'])} for ICU admission, where "
    f"XGBoost was ahead by {f3(diff('icu', 'auroc', get=lag))} ({ci('icu', 'paired_xgboost_minus_lr.raw.auroc', 'lag0')}). "
    "Part of this gain uses same-day tests that may not be resulted before induction.",
]))
SECTIONS.append((None, "Calibration and Operating Points", [
    f"Validation recalibration slopes were close to one ({f2(sel('mortality', 'lr')['diagnostics']['calibration_slope'])} "
    f"and {f2(sel('mortality', 'xgboost')['diagnostics']['calibration_slope'])} for mortality, "
    f"{f2(sel('icu', 'lr')['diagnostics']['calibration_slope'])} and {f2(sel('icu', 'xgboost')['diagnostics']['calibration_slope'])} "
    "for ICU admission), so the raw models were already well calibrated. On the test set, recalibrated CITL was "
    f"{rng(min(_mL['calibration']['offset_intercept'], _mX['calibration']['offset_intercept']), max(_mL['calibration']['offset_intercept'], _mX['calibration']['offset_intercept']), f2)} "
    f"for mortality and {rng(min(_iL['calibration']['offset_intercept'], _iX['calibration']['offset_intercept']), max(_iL['calibration']['offset_intercept'], _iX['calibration']['offset_intercept']), f2)} "
    "for ICU admission, slopes were "
    f"{rng(min(_mL['calibration']['joint_slope'], _mX['calibration']['joint_slope'], _iL['calibration']['joint_slope'], _iX['calibration']['joint_slope']), max(_mL['calibration']['joint_slope'], _mX['calibration']['joint_slope'], _iL['calibration']['joint_slope'], _iX['calibration']['joint_slope']), f2)} "
    "(Table III, Fig. 3a, c), and all Brier scores were below the prevalence reference. No validation slope was "
    f"non-positive in any repeated split, and 95% of recalibrated mortality test slopes lay between "
    f"{f2(rs('mortality', 'lr', 'test_cal_slope_cal')['p2_5'])} and {f2(rs('mortality', 'lr', 'test_cal_slope_cal')['p97_5'])} (LR). "
    "At the validation-fixed thresholds, LR flagged "
    f"{n(_mL['tp'] + _mL['fp'])} test patients ({pct((_mL['tp'] + _mL['fp']) / PN['test'])}) and detected "
    f"{_mL['tp']} of {TE['mortality']['test']} deaths, a positive predictive value (PPV) of {pct(_mL['ppv'])}; XGBoost "
    f"detected {_mX['tp']} while flagging {n(_mX['tp'] + _mX['fp'])}. For ICU admission, both models detected about "
    f"{pct(_iL['sensitivity'], 0)} of admissions with a specificity near {pct(_iL['specificity'], 0)}. Because the threshold "
    "is set at the target on validation data, test sensitivity reached 80% in "
    f"{pct(rs('mortality', 'lr', 'share_sensitivity_ge_0_8'), 0)}–{pct(rs('mortality', 'xgboost', 'share_sensitivity_ge_0_8'), 0)} "
    "of splits for mortality.",
    "FIG:calibration",
    "TAB:op",
]))
SECTIONS.append((None, "External Validation on VitalDB", [
    f"In VitalDB ({VF['mortality_events']} deaths, {n(VF['icu_events'])} ICU admissions), mortality AUROCs were "
    f"{f3(_xmL['raw']['auroc'])} ({ci('mortality', 'lr.raw.auroc', 'external_vitaldb')}) for LR and "
    f"{f3(_xmX['raw']['auroc'])} ({ci('mortality', 'xgboost.raw.auroc', 'external_vitaldb')}) for XGBoost, and ICU "
    f"AUROCs were {f3(_xiL['raw']['auroc'])} ({ci('icu', 'lr.raw.auroc', 'external_vitaldb')}) and "
    f"{f3(_xiX['raw']['auroc'])} ({ci('icu', 'xgboost.raw.auroc', 'external_vitaldb')}); for ICU admission LR was "
    f"better by {f3(-diff('icu', 'auroc', get=ex))} (paired interval for XGBoost minus LR "
    f"{ci('icu', 'paired_xgboost_minus_lr.raw.auroc', 'external_vitaldb')}). Calibration failed in opposite "
    f"directions (Fig. 3b, d): mortality was underestimated (CITL {f2(_xmL['calibration']['offset_intercept'])} and "
    f"{f2(_xmX['calibration']['offset_intercept'])}, slopes {f2(_xmL['calibration']['joint_slope'])} and "
    f"{f2(_xmX['calibration']['joint_slope'])}), whereas ICU admission was overestimated (CITL "
    f"{f2(_xiL['calibration']['offset_intercept'])} and {f2(_xiX['calibration']['offset_intercept'])}), reflecting "
    f"a lower admission rate ({pct(VF['icu_events'] / VF['modelled_patients'])} versus {pct(ICU / NMOD)}). The MOVER "
    f"thresholds detected only {_xmL['tp']} (LR) and {_xmX['tp']} (XGBoost) of {VF['mortality_events']} deaths but "
    f"{pct(_xiL['sensitivity'], 0)} and {pct(_xiX['sensitivity'], 0)} of ICU admissions at specificities of "
    f"{pct(_xiL['specificity'], 0)} and {pct(_xiX['specificity'], 0)}, and the recalibrated ICU Brier scores "
    f"({f3(_xiL['calibrated']['brier'])} and {f3(_xiX['calibrated']['brier'])}) were worse than that of a constant "
    f"prediction at the development prevalence ({f3(_xiL['training_prevalence_brier'])}). A test patient had on "
    f"average {_mlab_test:.1f} of seven laboratory values missing in MOVER but {_mlab_ext:.1f} in VitalDB.",
]))
_top = lambda e, m: [k for k, v in stab(e, m)["top5_inclusion_frequency"].items() if v >= 0.9]
_LBL = {"age": "age", "sex": "sex", "asa": "ASA", "hemoglobin": "haemoglobin", "platelets": "platelets",
        "creatinine": "creatinine", "bun": "BUN", "sodium": "sodium", "potassium": "potassium", "glucose": "glucose"}
def _prange(e):
    lo, hi = sorted((_asa_share[(e, "lr")], _asa_share[(e, "xgboost")]))
    return pct(lo, 0) if pct(lo, 0) == pct(hi, 0) else f"{pct(lo, 0)}–{pct(hi, 0)}"


def _tops(e, m):
    t = [_LBL[k] for k in _top(e, m)]
    t = ["ASA" if x == "ASA" else x for x in t]
    return (", ".join(t[:-1]) + " and " + t[-1]) if len(t) > 1 else t[0]


_g = lambda e, m: STUDY[e]["explain"]["models"][m]["global_mean_absolute_raw"]
_asa_share = {(e, m): _g(e, m)["asa"] / sum(_g(e, m).values()) for e in STUDY for m in ("lr", "xgboost")}
SECTIONS.append((None, "Explanations and Their Stability", [
    "ASA class had the largest mean absolute SHAP value for both endpoints and both models, in the primary fits and "
    f"in every refit, accounting for {_prange('mortality')} of the summed importance for mortality and "
    f"{_prange('icu')} for ICU admission (Fig. 4). In the primary fits, sex and age "
    "followed, except that glucose ranked second for XGBoost for ICU admission; the laboratory concepts contributed little individually, possibly because their missingness, which "
    "is shared across tests, is split between seven concepts. Mortality rankings were reproducible across the ten "
    f"paired refits, with mean Spearman correlations of {f2(stab('mortality', 'lr')['spearman_mean'])} (LR) and "
    f"{f2(stab('mortality', 'xgboost')['spearman_mean'])} (XGBoost) and top-five Jaccard overlaps of "
    f"{f2(stab('mortality', 'lr')['top5_jaccard_mean'])} and {f2(stab('mortality', 'xgboost')['top5_jaccard_mean'])}"
    f"; {_tops('mortality', 'lr')} were in the top five in at least 90% of LR refits and "
    f"{_tops('mortality', 'xgboost')} in at least 90% of XGBoost refits. ICU-admission rankings were less stable "
    f"(Spearman {f2(stab('icu', 'lr')['spearman_mean'])} and {f2(stab('icu', 'xgboost')['spearman_mean'])}, Jaccard "
    f"{f2(stab('icu', 'lr')['top5_jaccard_mean'])} and {f2(stab('icu', 'xgboost')['top5_jaccard_mean'])}): beyond ASA, the order of the low-importance laboratory concepts "
    "changed between refits, and glucose was in the top five in only "
    f"{pct(stab('icu', 'xgboost')['top5_inclusion_frequency']['glucose'], 0)} of XGBoost refits.",
    "FIG:shap",
]))

SECTIONS.append(("Discussion", None, [
    "With ten routinely available preoperative concepts, XGBoost did not discriminate better than regularised LR "
    "for in-hospital mortality, and its advantage for ICU admission was consistent across splits but around 0.002 "
    "in AUROC, too small to matter clinically and reversed in external validation [[christodoulou19]]. Mortality AUROCs above 0.9 were achieved by both models, comparable with "
    "larger studies using richer predictors [[hill19]], [[lee22npj]], with ASA class separating the few high-risk "
    f"patients: ASA IV–V patients made up {_C['all']['asa_pct']['4'] + _C['all']['asa_pct']['5']:.1f}% of "
    f"the cohort but {_c[0]['asa_pct']['4'] + _c[0]['asa_pct']['5']:.1f}% of deaths.",

    "External validation changed the picture. Discrimination fell to AUROCs near 0.7 and probabilities were "
    "miscalibrated in opposite directions for the two outcomes, so neither the MOVER risk estimates nor its "
    "operating thresholds could be used in Seoul without local updating [[debray15]]. Two differences plausibly "
    "contribute: VitalDB patients were mostly ASA I–II, and their laboratory values were almost always present, "
    "whereas in MOVER the presence of a test at least a day before surgery marked patients at higher risk (Table I). "
    "Missingness indicators thus encode care processes that differ between hospitals [[agniel18]], [[groenwold20]], "
    "and an explanation that is stable internally can attribute risk to such process signals. Explanation "
    "stability, split dependence and external performance should therefore be reported alongside SHAP figures.",

    "The study has limitations. MOVER and VitalDB are single-centre cohorts with different outcome definitions; "
    "ICU admission is not time-stamped in either and partly reflects planned care pathways. Laboratory availability "
    "was approximated by collection time. Transfers and hospice discharges were treated as unknown, which may bias "
    "mortality estimates. Grouped SHAP values are summaries, not concept-level Shapley values, and SHAP describes "
    "model behaviour, not causal effects.",
]))
SECTIONS.append(("Conclusion", None, [
    f"On {n(NMOD)} MOVER patients, a leakage-controlled comparison found no meaningful advantage of XGBoost over "
    "regularised logistic regression for predicting in-hospital mortality or ICU admission from ten preoperative "
    "concepts. Both were well calibrated internally and their mortality explanations, dominated by ASA class, were "
    "reproducible, but discrimination and calibration deteriorated on an independent cohort with a different case "
    "mix and laboratory-testing pattern. Explainable preoperative models should be judged on external calibration "
    "and explanation stability, not only on internal AUROC.",
]))

# ---------------------------------------------------------------- tables
TABLES = {}


def _med(d, lab, dec=1):
    x = d[lab]
    return "–" if x["median"] is None else f"{x['median']:.{dec}f} ({x['q1']:.{dec}f}–{x['q3']:.{dec}f})"


_cols = [_C["all"], _C["event"], _C["no_event"], _CI, _CV]
TABLES["cohort"] = dict(
    caption="Characteristics of the Development (MOVER) and External (VitalDB) Cohorts",
    header=["Variable", f"MOVER all (n = {n(_C['all']['n'])})", f"Died (n = {_C['event']['n']})",
            f"Survived (n = {n(_C['no_event']['n'])})", f"ICU (n = {n(_CI['n'])})", f"VitalDB (n = {n(_CV['n'])})"],
    widths=[1.15, 1.2, 1.15, 1.2, 1.15, 1.2], font=6.5, full=True,
    rows=[["Age, y"] + [f"{c['age_median']:.0f} ({c['age_q1']:.0f}–{c['age_q3']:.0f})" for c in _cols],
          ["Female, %"] + [f"{c['female_pct']:.1f}" for c in _cols],
          ["ASA I / II, %"] + [f"{c['asa_pct']['1']:.1f} / {c['asa_pct']['2']:.1f}" for c in _cols],
          ["ASA III / IV / V, %"] + [f"{c['asa_pct']['3']:.1f} / {c['asa_pct']['4']:.1f} / {c['asa_pct']['5']:.1f}" for c in _cols],
          ["Haemoglobin, g/dL"] + [_med(c, "hemoglobin") for c in _cols],
          ["Platelets, 10⁹/L"] + [_med(c, "platelets", 0) for c in _cols],
          ["Creatinine, mg/dL"] + [_med(c, "creatinine", 2) for c in _cols],
          ["BUN, mg/dL"] + [_med(c, "bun", 0) for c in _cols],
          ["Sodium / potassium, mmol/L"] + [f"{c['sodium']['median']:.0f} / {c['potassium']['median']:.1f}" for c in _cols],
          ["Glucose, mg/dL"] + [_med(c, "glucose", 0) for c in _cols],
          ["Lab missing (range), %"] + [f"{min(c[l]['missing_pct'] for l in _LABK):.1f}–{max(c[l]['missing_pct'] for l in _LABK):.1f}" for c in _cols]],
    note="Medians (interquartile range) of available values; sodium and potassium as medians. Missing ASA: "
         f"{_C['all']['asa_missing_pct']:.2f}% (MOVER), {_CV['asa_missing_pct']:.1f}% (VitalDB). MOVER laboratory values "
         "collected 30 days to 24 hours before anaesthesia. Lab missing: range over the seven laboratory values.")


def _ci_rep(e, m):
    d = rs(e, m, "auroc")
    return f"{f3(d['median'])} ({f3(d['p2_5'])}–{f3(d['p97_5'])})"


_perf_rows = []
for e, labl in (("mortality", "Death"), ("icu", "ICU")):
    for m, ml in (("lr", "LR"), ("xgboost", "XGB")):
        r = ev(e, m)
        _perf_rows.append([labl, ml, f"{f3(r['raw']['auroc'])} ({ci(e, f'{m}.raw.auroc')})",
                           f"{f3(r['raw']['average_precision'])} ({ci(e, f'{m}.raw.average_precision')})",
                           _ci_rep(e, m), f3(lag(e, m)["raw"]["auroc"]),
                           f"{f3(ex(e, m)['raw']['auroc'])} ({ci(e, f'{m}.raw.auroc', 'external_vitaldb')})",
                           f"{f3(ex(e, m)['raw']['average_precision'])} ({ci(e, f'{m}.raw.average_precision', 'external_vitaldb')})"])
    d = q(e, "diff_auroc")
    _perf_rows.append([labl, "Δ", f"{f3(diff(e, 'auroc'))} ({ci(e, 'paired_xgboost_minus_lr.raw.auroc')})",
                       f"{f3(diff(e, 'average_precision'))} ({ci(e, 'paired_xgboost_minus_lr.raw.average_precision')})",
                       f"{f3(d['median'])} ({rng(d['p2_5'], d['p97_5'])})", f3(diff(e, "auroc", get=lag)),
                       f"{f3(diff(e, 'auroc', get=ex))} ({ci(e, 'paired_xgboost_minus_lr.raw.auroc', 'external_vitaldb')})",
                       f"{f3(diff(e, 'average_precision', get=ex))} ({ci(e, 'paired_xgboost_minus_lr.raw.average_precision', 'external_vitaldb')})"])
TABLES["perf"] = dict(
    caption="Discrimination: MOVER Test Set, Repeated Splits, Sensitivity Analysis and External Validation",
    header=["End-point", "Model", "MOVER test AUROC (95% CI)", "MOVER test AP (95% CI)",
            f"AUROC, {NS} splits: median (2.5–97.5th pct.)", "AUROC, labs to t₀", "VitalDB AUROC (95% CI)",
            "VitalDB AP (95% CI)"],
    widths=[0.55, 0.45, 1.25, 1.25, 1.25, 0.65, 1.25, 1.25], font=6.4, full=True, rows=_perf_rows,
    note="Δ: XGBoost minus LR with paired bootstrap interval (or 2.5th–97.5th percentile over splits). Labs to t₀: "
         "sensitivity analysis with laboratory results collected up to anaesthesia start. Prevalence: "
         f"{f4(STUDY['mortality']['evaluation']['prevalence'])} (death) and {f3(STUDY['icu']['evaluation']['prevalence'])} (ICU) "
         f"in the MOVER test set; {f4(VF['mortality_events'] / VF['modelled_patients'])} and "
         f"{f3(VF['icu_events'] / VF['modelled_patients'])} in VitalDB.")

_op = []
for e, labl in (("mortality", "Death"), ("icu", "ICU")):
    for m, ml in (("lr", "LR"), ("xgboost", "XGB")):
        r, x = ev(e, m), ex(e, m)
        _op.append([labl, ml, f"{f2(r['calibration']['offset_intercept'])} / {f2(r['calibration']['joint_slope'])}",
                    f"{f3(r['sensitivity'])} / {f3(r['specificity'])} / {f3(r['ppv'])}",
                    f"{f2(x['calibration']['offset_intercept'])} / {f2(x['calibration']['joint_slope'])}",
                    f"{f3(x['sensitivity'])} / {f3(x['specificity'])} / {f3(x['ppv'])}"])
TABLES["op"] = dict(
    caption="Calibration of Recalibrated Risks and Performance at the Validation-Fixed Threshold",
    header=["End-point", "Model", "MOVER CITL / slope", "MOVER sens. / spec. / PPV", "VitalDB CITL / slope",
            "VitalDB sens. / spec. / PPV"],
    widths=[0.5, 0.42, 0.72, 1.0, 0.72, 1.0], font=6.2, rows=_op,
    note="CITL: calibration-in-the-large (0 is ideal); slope: calibration slope (1 is ideal). Thresholds were fixed "
         "on the MOVER validation set at 80% sensitivity and applied unchanged to VitalDB.")

_st = []
for e, labl in (("mortality", "Death"), ("icu", "ICU")):
    for m, ml in (("lr", "LR"), ("xgboost", "XGB")):
        s = stab(e, m)
        _st.append([labl, ml, f2(s["spearman_mean"]), f2(s["top5_jaccard_mean"]),
                    ", ".join(_LBL[k] for k in _top(e, m)) or "none"])
TABLES["stab"] = dict(
    caption="Explanation Stability over Ten Paired Bootstrap Refits",
    header=["End-point", "Model", "Spear-man", "Top-5 Jaccard", "Top five in ≥ 90% of refits"],
    widths=[0.62, 0.5, 0.6, 0.62, 2.3], font=6.5, rows=_st,
    note="Spearman and Jaccard: means over the 45 refit pairs of the grouped concept importances.")

FIGS = {"cohort": ("../figs/fig1_cohort.png", 6.6, True),
        "discrimination": ("../figs/fig2_discrimination.png", 6.9, True),
        "calibration": ("../figs/fig3_calibration.png", 6.9, True),
        "shap": ("../figs/fig4_shap.png", 6.4, True),
        "repeats": ("../figs/fig5_repeats.png", 3.4, False)}

CAPTIONS = {
    "cohort": "Development cohort selection from MOVER EPIC, the PreOp-XAI evaluation protocol and external "
              "validation on VitalDB. Event counts per partition are shown for both endpoints; the split was "
              "stratified on in-hospital death.",
    "discrimination": "ROC and precision–recall curves on the MOVER test set (solid) and in external validation on "
                      "VitalDB (dashed) for LR (black) and XGBoost (grey), from raw model scores (recalibration "
                      "preserves ranking); AUROC and AP values are given in Table II. Dotted line: chance.",
    "calibration": "Observed outcome proportion against mean recalibrated risk in deciles of predicted risk, with 95% "
                   "Wilson intervals. Mortality panels use logarithmic axes; deciles without a death are drawn on the "
                   "row labelled 0. Dotted line: perfect calibration.",
    "shap": "Grouped mean absolute SHAP values (raw log-odds) on the MOVER validation patients over ten paired "
            "bootstrap refits; bars show the mean and whiskers the range across refits. Concepts are ordered by "
            "their mean normalised importance across the two models.",
    "repeats": f"Paired test-set differences (XGBoost minus LR) over {NS} repeated splits of the MOVER cohort (box: "
               "quartiles; whiskers: 2.5th and 97.5th percentiles).",
}
