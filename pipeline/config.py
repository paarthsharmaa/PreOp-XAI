"""Single source of local paths: config/paths.toml, overridable by environment variables."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import os
from pathlib import Path
import tomllib
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG: Final = ROOT / "config/paths.toml"
CONFIG_VARIABLE: Final = "PREOPXAI_CONFIG"
OVERRIDES: Final = {
    "mover_raw": "PREOPXAI_MOVER_RAW",
    "vitaldb_clinical": "PREOPXAI_VITALDB_CLINICAL",
    "outputs": "PREOPXAI_OUTPUTS",
}


@dataclass(frozen=True)
class Paths:
    """Resolved locations of raw inputs and generated outputs."""

    mover_raw: Path
    vitaldb_clinical: Path
    outputs: Path

    @property
    def tables(self) -> Path:
        """Generated analysis tables and their aggregate cohort statistics."""
        return self.outputs / "tables"

    @property
    def runs(self) -> Path:
        """Patient-level run outputs; never exported."""
        return self.outputs / "runs"

    @property
    def export(self) -> Path:
        """Aggregate-only export of a completed protocol run."""
        return self.outputs / "export"

    @property
    def report(self) -> Path:
        """Generated summary and figures."""
        return self.outputs / "report"

    @property
    def logs(self) -> Path:
        """Stage logs."""
        return self.outputs / "logs"


def _resolve(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else ROOT / path


def load_paths(config: Path | None = None, environ: Mapping[str, str] | None = None) -> Paths:
    """Read the TOML config, then apply any environment overrides."""
    env = os.environ if environ is None else environ
    source = config or Path(env.get(CONFIG_VARIABLE, DEFAULT_CONFIG))
    with source.open("rb") as stream:
        section = tomllib.load(stream)["paths"]
    values = {key: _resolve(env.get(variable) or str(section[key]))
              for key, variable in OVERRIDES.items()}
    return Paths(**values)
