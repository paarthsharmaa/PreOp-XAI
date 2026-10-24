PreOp-XAI on MOVER EPIC - how to run (Windows)
===============================================

What this does
  Runs the complete PreOp-XAI protocol (repository commit in preop_xai/REPO_COMMIT.txt, used unchanged) on
  the de-identified MOVER analysis table in this folder, then tests the frozen models on VitalDB.
  All patient data stay on this computer. The only file meant to leave it is
  export\preopxai_mover_results.zip, which holds aggregate results only (no rows, IDs, dates, predictions or
  per-patient SHAP values; calibration cells with fewer than 11 patients are removed).
  Please confirm this is allowed under your MOVER Data Usage Agreement before sharing it.

Option A - double-click RUN_ME.bat
  Needs Python 3.11 or newer (python.org installer, tick "Add python.exe to PATH").
  First run creates .venv in this folder and installs the packages in requirements.txt (about 300 MB).

Option B - Anaconda Prompt
  conda create -n preopxai python=3.11 -y
  conda activate preopxai
  pip install -r requirements.txt
  cd %USERPROFILE%\Downloads\MOVER\preopxai
  python mover_run.py

Time: roughly 30-90 minutes, most of it the 200 repeated splits (uses up to 10 CPU cores; the computer stays
usable but busy). Keep the laptop plugged in and awake. If it stops, just run it again - finished steps are skipped.
Progress is printed and also written to runs\run_log.txt.

Folder contents
  mover_run.py            orchestrator (steps listed at the top of the file)
  mover_study.py          one analysis (endpoint, split seed) using the repository modules
  preop_xai\              PreOp-XAI repository source, unchanged
  exact_shap.py, shapshim\  exact SHAP back end (checked against brute force by tests\test_exact_shap.py)
  cohort_vitaldb.py, data\  VitalDB adapter and public VitalDB clinical table (external validation)
  data_prep\              scripts that built mover_analysis*.csv from the MOVER EPIC CSVs
  mover_analysis.csv      primary table: laboratory values collected 30 days to 24 h before anaesthesia start
  mover_analysis_lag0h.csv  sensitivity table: 30 days to anaesthesia start
