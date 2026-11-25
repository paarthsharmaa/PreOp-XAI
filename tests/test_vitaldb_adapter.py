"""VitalDB age top-coding is the same for both source encodings."""

from pathlib import Path

import pandas as pd

from data_prep.vitaldb import build


def _table(ages: list[object]) -> pd.DataFrame:
    count = len(ages)
    frame = pd.DataFrame({
        "caseid": range(1, count + 1), "subjectid": range(1, count + 1), "age": ages, "sex": ["M"] * count,
        "asa": [2.0] * count, "anestart": [0] * count, "aneend": [100] * count, "adm": [-10] * count,
        "dis": [500] * count, "death_inhosp": [0] * count, "icu_days": [0] * count})
    for column in ("preop_hb", "preop_plt", "preop_cr", "preop_bun", "preop_na", "preop_k", "preop_gluc"):
        frame[column] = 1.0
    return frame


def test_exact_and_text_top_coding_match(tmp_path: Path) -> None:
    text, exact = tmp_path / "text.csv", tmp_path / "exact.csv"
    _table(["70", ">89", "89"]).to_csv(text, index=False)
    _table([70.0, 94.0, 89.0]).to_csv(exact, index=False)
    x_text, _, flow_text, _ = build(text)
    x_exact, _, flow_exact, _ = build(exact)
    assert x_text["age"].tolist() == x_exact["age"].tolist() == [70.0, 90.0, 89.0]
    assert flow_text["age_top_coded_gt89_set_to_90"] == flow_exact["age_top_coded_gt89_set_to_90"] == 1
