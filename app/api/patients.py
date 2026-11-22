"""Example patients: VitalDB records (public, CC BY 4.0) and labelled synthetic teaching profiles.

MOVER rows are never used here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import numpy as np
from pydantic import ValidationError

from app.api.schemas import ExamplePatient, ObservedOutcome, PatientInput
from data_prep.vitaldb import build
from preopxai.preprocessing import LABS

SELECTION_SEED: Final = 2026
# Outcome groups are sampled separately so that rare deaths appear; the mix does not reflect prevalence.
STRATA: Final = (("death", 3), ("icu", 4), ("neither", 5))
NOTICE: Final = (
    "VitalDB examples were sampled across outcome groups, so their outcome mix does not reflect how common "
    "these outcomes are."
)
ATTRIBUTION: Final = (
    "VitalDB, Lee HC et al., Sci Data 2022;9:279, doi:10.1038/s41597-022-01411-5. Licensed under "
    "CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). Changes: records sampled, identifiers "
    "removed, ages above 89 top-coded to 90, fields renamed."
)
ASA_NAMES: Final = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V"}

SYNTHETIC: Final = (
    (
        "synthetic-healthy",
        "Healthy adult, ASA I",
        "Synthetic teaching profile: a young adult with normal labs.",
        {
            "age": 28,
            "sex": "F",
            "asa": 1,
            "hemoglobin": 13.8,
            "platelets": 260,
            "creatinine": 0.8,
            "bun": 12,
            "sodium": 140,
            "potassium": 4.1,
            "glucose": 92,
        },
    ),
    (
        "synthetic-frail",
        "Frail older adult, ASA IV",
        "Synthetic teaching profile: anaemia, renal impairment and abnormal electrolytes.",
        {
            "age": 84,
            "sex": "M",
            "asa": 4,
            "hemoglobin": 8.6,
            "platelets": 96,
            "creatinine": 3.4,
            "bun": 68,
            "sodium": 129,
            "potassium": 5.7,
            "glucose": 214,
        },
    ),
    (
        "synthetic-missing",
        "Missing labs, ASA III",
        "Synthetic teaching profile: most preoperative labs are missing, which was common in the development cohort.",
        {"age": 62, "sex": "F", "asa": 3, "hemoglobin": 11.7, "creatinine": 1.3},
    ),
    (
        "synthetic-moderate",
        "Moderate risk, ASA III",
        "Synthetic teaching profile: an older adult with mildly abnormal labs.",
        {
            "age": 71,
            "sex": "M",
            "asa": 3,
            "hemoglobin": 11.2,
            "platelets": 180,
            "creatinine": 1.4,
            "bun": 26,
            "sodium": 136,
            "potassium": 4.6,
            "glucose": 128,
        },
    ),
)


def _describe(inputs: PatientInput) -> str:
    sex = "female" if inputs.sex == "F" else "male"
    missing = sum(getattr(inputs, lab) is None for lab in LABS)
    labs = "all labs recorded" if not missing else f"{missing} of {len(LABS)} labs missing"
    return f"{inputs.age:.0f} years, {sex}, ASA {ASA_NAMES[inputs.asa]}, {labs}."


class PatientStore:
    """Deterministic example list. Observed outcomes are served only by a separate request."""

    def __init__(self, vitaldb: Path) -> None:
        self.patients: list[ExamplePatient] = []
        self.outcomes: dict[str, ObservedOutcome] = {}
        self._add_vitaldb(vitaldb)
        for identifier, label, description, inputs in SYNTHETIC:
            self.patients.append(
                ExamplePatient(
                    id=identifier,
                    label=label,
                    source="synthetic",
                    description=description,
                    inputs=PatientInput.model_validate(inputs),
                    has_outcome=False,
                )
            )

    def _add_vitaldb(self, path: Path) -> None:
        X, labels, _, _ = build(path)
        known = labels["mortality"].notna().to_numpy() & (X["asa"] != "unknown").to_numpy()
        X, labels = X[known].reset_index(drop=True), labels[known].reset_index(drop=True)
        death, icu = labels["mortality"].to_numpy() == 1, labels["icu"].to_numpy() == 1
        complete = X[list(LABS)].notna().all(axis=1).to_numpy()
        masks = {"death": death, "icu": icu & ~death, "neither": ~icu & ~death}
        rng = np.random.default_rng(SELECTION_SEED)
        chosen: list[int] = []
        for name, count in STRATA:
            chosen.extend(rng.choice(np.flatnonzero(masks[name] & complete), size=count, replace=False).tolist())
        chosen.extend(
            rng.choice(
                np.flatnonzero(~complete & X[list(LABS)].notna().any(axis=1).to_numpy()), size=1, replace=False
            ).tolist()
        )
        # Shuffled so that list position does not reveal the outcome group.
        rng.shuffle(chosen)
        for number, index in enumerate(chosen, start=1):
            row = X.iloc[index]
            values = {name: (None if row[name] != row[name] else float(row[name])) for name in ("age", *LABS)}
            try:
                inputs = PatientInput.model_validate({**values, "sex": str(row["sex"]), "asa": int(row["asa"])})
            except ValidationError:
                continue
            identifier = f"vitaldb-{number:02d}"
            self.patients.append(
                ExamplePatient(
                    id=identifier,
                    label=f"VitalDB patient {number}",
                    source="vitaldb",
                    description=_describe(inputs),
                    inputs=inputs,
                    has_outcome=True,
                )
            )
            self.outcomes[identifier] = ObservedOutcome(
                id=identifier, mortality=bool(death[index]), icu=bool(icu[index])
            )
