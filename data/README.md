# Data

Nothing in this folder is committed except this file. MOVER and VitalDB are used under
their own access terms, so obtain them yourself and place them as shown.

```text
data/
├── mover/EPIC_EMR/EMR/
│   ├── patient_information.csv             used: cohort, timing, mortality, ICU flag
│   ├── patient_labs.csv                    used: seven preoperative laboratory concepts (~3.6 GB)
│   ├── patient_post_op_complications.csv   used: respiratory endpoint feasibility count
│   ├── patient_coding.csv                  not used
│   ├── patient_history.csv                 not used
│   ├── patient_lda.csv                     not used
│   ├── patient_medications.csv             not used
│   ├── patient_procedure events.csv        not used
│   └── patient_visit.csv                   not used
└── vitaldb/
    ├── vitaldb_cases.csv                   used: external validation cohort and predictors
    └── vitaldb_labs.csv                    not used
```

## Where to get it

- **MOVER** (EPIC EMR tables): <https://mover.ics.uci.edu>. Access requires an approved
  data usage agreement.
- **VitalDB** (clinical information and laboratory tables): <https://vitaldb.net/dataset/>.

## Notes

- `vitaldb_cases.csv` already holds the preoperative laboratory columns the model needs
  (`preop_hb`, `preop_plt`, `preop_cr`, `preop_bun`, `preop_na`, `preop_k`, `preop_gluc`), so
  the long-format `vitaldb_labs.csv` is not read.
- Ages above 89 are top-coded to 90 in the VitalDB adapter, whichever way the file stores them.
- To keep the data elsewhere, edit `config/paths.toml` or set `PREOPXAI_MOVER_RAW` and
  `PREOPXAI_VITALDB_CLINICAL`.
- Generated tables and run outputs go to `outputs/`, which is also ignored by git.
