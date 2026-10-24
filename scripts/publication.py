"""Regenerate original figures and paper, adding vector exports at save time.

Run: uv run --locked python scripts/reproduce.py publication
Optional aggregate-only reproduction: uv run --locked python -m scripts.publication --reference
"""

import os
import importlib.metadata
from pathlib import Path
import runpy
import shutil
import sys
from typing import IO, Callable

import matplotlib.figure
from pydantic import JsonValue, TypeAdapter

from scripts.reproduce import BUNDLE, OUT, RUNNER, run


def main() -> None:
    """Build from newly computed exports, or explicitly selected reference aggregates."""
    reference = "--reference" in sys.argv
    output = OUT / ("publication-reference" if reference else "publication")
    results = BUNDLE / "results" if reference else RUNNER / "export"
    if not (results / "main_mortality/study.json").is_file():
        raise SystemExit(f"Missing completed aggregate export: {results}; run protocol first.")
    output.mkdir(parents=True, exist_ok=True)
    for name in ("code", "paper"):
        _ = shutil.copytree(BUNDLE / name, output / name, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("__pycache__", "out"))
    _ = shutil.copytree(results, output / "results", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("*.zip"))
    (output / "figs").mkdir(exist_ok=True)
    run([sys.executable, "code/summarize.py"], output, output.name + "-summary")
    # Preserve original figure geometry/data; capture the same live Figure as vectors.
    save_adapter: TypeAdapter[Callable[..., None]] = TypeAdapter(Callable[..., None])
    original_save = save_adapter.validate_python(getattr(matplotlib.figure.Figure, "savefig"))

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
        sys.path.insert(0, str(output / "code"))
        _ = runpy.run_path(str(output / "code/figs_mover.py"), run_name="__main__")
    finally:
        matplotlib.figure.Figure.savefig = original_save
        os.chdir(previous)
    pandoc = Path(str(importlib.metadata.distribution("pypandoc-binary").locate_file(
        "pypandoc/files/pandoc.exe" if os.name == "nt" else "pypandoc/files/pandoc")))
    os.environ["PATH"] = str(pandoc.parent) + os.pathsep + os.environ["PATH"]
    paper = output / "paper"
    document = "out/PreOp_XAI_MOVER_IEEE.docx"
    run([sys.executable, "build_paper.py", document], paper, output.name + "-paper")
    run([sys.executable, "audit.py", document], paper, output.name + "-audit")
    print(f"PASS publication: {output}")


if __name__ == "__main__":
    main()
