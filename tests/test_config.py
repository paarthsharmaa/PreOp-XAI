"""Path configuration: defaults, file selection and environment overrides."""

from pathlib import Path

from pipeline.config import ROOT, load_paths


def _write(path: Path, outputs: str = "custom-out") -> Path:
    _ = path.write_text(f'[paths]\nmover_raw = "raw"\nvitaldb_clinical = "/abs/v.csv"\noutputs = "{outputs}"\n')
    return path


def test_default_config_points_at_data() -> None:
    paths = load_paths(environ={})
    assert paths.mover_raw == ROOT / "data/mover/EPIC_EMR/EMR"
    assert paths.vitaldb_clinical == ROOT / "data/vitaldb/vitaldb_cases.csv"
    assert paths.outputs == ROOT / "outputs"
    assert paths.tables == ROOT / "outputs/tables"


def test_relative_and_absolute_values(tmp_path: Path) -> None:
    paths = load_paths(_write(tmp_path / "paths.toml"), environ={})
    assert paths.mover_raw == ROOT / "raw"
    assert paths.vitaldb_clinical == Path("/abs/v.csv")


def test_config_variable_selects_file(tmp_path: Path) -> None:
    config = _write(tmp_path / "paths.toml", "elsewhere")
    assert load_paths(environ={"PREOPXAI_CONFIG": str(config)}).outputs == ROOT / "elsewhere"


def test_environment_overrides_file(tmp_path: Path) -> None:
    config = _write(tmp_path / "paths.toml")
    paths = load_paths(config, environ={"PREOPXAI_MOVER_RAW": "/m", "PREOPXAI_OUTPUTS": "/o",
                                        "PREOPXAI_VITALDB_CLINICAL": "/v.csv"})
    assert (paths.mover_raw, paths.outputs, paths.vitaldb_clinical) == (Path("/m"), Path("/o"), Path("/v.csv"))


def test_example_config_has_every_key() -> None:
    paths = load_paths(ROOT / "config/paths.example.toml", environ={})
    assert paths.mover_raw == Path("/path/to/mover/EPIC_EMR/EMR")
