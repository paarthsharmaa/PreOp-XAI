"""Generate the repeated-split summary and figures from the aggregate export.

Run: uv run --locked python -m pipeline.cli report [--promote]
"""

from collections.abc import Callable
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
from typing import IO

import matplotlib.figure
from pydantic import JsonValue, TypeAdapter

from pipeline.config import ROOT, load_paths

RUN_RECORDS = ("environment.json", "determinism_check.json", "split_check.json",
               "shap_selftest.txt", "run_log.txt")
HERE = Path(__file__).resolve().parent


def promote(output: Path) -> None:
    """Copy aggregate-only results into the committed results/ and verification/ folders."""
    for source in sorted((output / "results").rglob("*")):
        relative = source.relative_to(output / "results")
        if not source.is_file() or source.suffix == ".zip":
            continue
        target = (ROOT / "verification" / relative.name if relative.as_posix() in RUN_RECORDS
                  else ROOT / "results" / relative)
        target.parent.mkdir(parents=True, exist_ok=True)
        _ = shutil.copy2(source, target)
    for figure in sorted((output / "figs").glob("fig*.png")):
        _ = shutil.copy2(figure, ROOT / "results/figures" / figure.name)


def main() -> None:
    """Build the report from a completed aggregate export."""
    paths = load_paths()
    output = paths.report
    if not (paths.export / "main_mortality/study.json").is_file():
        raise SystemExit(f"Missing completed aggregate export: {paths.export}; run protocol first.")
    output.mkdir(parents=True, exist_ok=True)
    _ = shutil.copytree(paths.export, output / "results", dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("*.zip"))
    (output / "figs").mkdir(exist_ok=True)
    _ = subprocess.run([sys.executable, str(HERE / "summarize.py")], cwd=output, check=True)
    # Capture the same live Figure as PNG plus PDF and SVG vectors.
    save_adapter: TypeAdapter[Callable[..., None]] = TypeAdapter(Callable[..., None])
    original_save = save_adapter.validate_python(matplotlib.figure.Figure.savefig)

    def save_vectors(self: matplotlib.figure.Figure, fname: str | os.PathLike[str] | IO[bytes],
                     *, transparent: bool | None = None, **kwargs: JsonValue) -> None:
        original_save(self, fname, transparent=transparent, **kwargs)
        if isinstance(fname, (str, os.PathLike)):
            for extension in (".pdf", ".svg"):
                original_save(self, str(Path(fname).with_suffix(extension)),
                              transparent=transparent, **kwargs)

    matplotlib.figure.Figure.savefig = save_vectors
    previous = Path.cwd()
    try:
        os.chdir(output)
        _ = runpy.run_path(str(HERE / "figs_mover.py"), run_name="__main__")
    finally:
        matplotlib.figure.Figure.savefig = original_save
        os.chdir(previous)
    if "--promote" in sys.argv:
        promote(output)
    print(f"PASS report: {output}")


if __name__ == "__main__":
    main()
