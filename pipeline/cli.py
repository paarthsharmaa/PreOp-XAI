"""PreOp-XAI command line.

Run: uv run preopxai --help
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib
from typing import Annotated, Final

import typer

from pipeline.config import ROOT, load_paths

MOVER_FILES: Final = ("patient_information.csv", "patient_labs.csv",
                      "patient_post_op_complications.csv")
VITALDB_COLUMNS: Final = frozenset({
    "caseid", "subjectid", "anestart", "aneend", "adm", "dis", "icu_days", "death_inhosp",
    "age", "sex", "asa", "preop_hb", "preop_plt", "preop_cr", "preop_bun", "preop_na",
    "preop_k", "preop_gluc"})
SCIENTIFIC_PACKAGES: Final = ("scikit-learn", "xgboost", "numpy", "pandas", "scipy", "matplotlib")
PROTOCOL_STEPS: Final = ("environment", "main", "lag0", "rerun", "split_check", "repeats", "export")
WEB: Final = ROOT / "app/web"
HOST: Final = "127.0.0.1"

app = typer.Typer(
    help="PreOp-XAI: explainable preoperative risk prediction on MOVER, validated on VitalDB.",
    no_args_is_help=True,
    add_completion=False,
)
web = typer.Typer(
    help="Dashboard: build the web frontend and serve it with the local API.",
    no_args_is_help=True,
)
app.add_typer(web, name="app")


def digest(path: Path) -> str:
    """Hash a file without loading large raw inputs into memory."""
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def run(args: list[str], name: str) -> None:
    """Capture a subprocess's combined output and propagate its failure."""
    logs = load_paths().logs
    logs.mkdir(parents=True, exist_ok=True)
    print(f"RUN {name}: {' '.join(args)}", flush=True)
    with (logs / f"{name}.log").open("w") as log:
        result = subprocess.run(args, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=False)
    print(f"EXIT {name}: {result.returncode}; {logs / (name + '.log')}", flush=True)
    if result.returncode:
        raise typer.Exit(result.returncode)


def stream(args: list[str], cwd: Path = ROOT) -> None:
    """Run a command with its output on the terminal and propagate its failure."""
    print(f"RUN {' '.join(args)}", flush=True)
    result = subprocess.run(args, cwd=cwd, check=False)
    if result.returncode:
        raise typer.Exit(result.returncode)


def npm(*args: str) -> None:
    """Run npm in the web frontend, installing its locked packages first if needed."""
    executable = shutil.which("npm")
    if executable is None:
        raise SystemExit("npm was not found. The dashboard needs Node.js.")
    if not (WEB / "node_modules").is_dir():
        stream([executable, "ci"], WEB)
    stream([executable, *args], WEB)


def pinned_versions() -> dict[str, str]:
    """Read the exact scientific dependency pins from pyproject.toml."""
    with (ROOT / "pyproject.toml").open("rb") as stream:
        dependencies: list[str] = tomllib.load(stream)["project"]["dependencies"]
    pins = dict(item.split("==", 1) for item in dependencies if "==" in item)
    return {name: pins[name] for name in SCIENTIFIC_PACKAGES}


@app.callback()
def environment() -> None:
    """Set single-threaded numerics and the worker count without changing scientific defaults."""
    _ = os.environ.setdefault("MPLBACKEND", "Agg")
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
        _ = os.environ.setdefault(name, "1")
    _ = os.environ.setdefault("PREOPXAI_WORKERS", "6")


@app.command()
def check() -> None:
    """Check dependency versions and the presence and shape of the raw inputs."""
    paths = load_paths()
    expected = pinned_versions()
    versions = {name: importlib.metadata.version(name) for name in expected}
    if versions != expected:
        raise SystemExit(f"Dependency mismatch: {versions}")
    missing = [str(paths.mover_raw / name) for name in MOVER_FILES
               if not (paths.mover_raw / name).is_file()]
    if not paths.vitaldb_clinical.is_file():
        missing.append(str(paths.vitaldb_clinical))
    if missing:
        raise SystemExit("Missing input files (see data/README.md): " + ", ".join(missing))
    with paths.vitaldb_clinical.open() as stream:
        columns = set(stream.readline().strip().split(","))
    if absent := VITALDB_COLUMNS - columns:
        raise SystemExit(f"VitalDB clinical table lacks columns: {sorted(absent)}")
    metadata = {"python": sys.version, "versions": versions, "cpu_count": os.cpu_count(),
                "mover_raw": str(paths.mover_raw), "vitaldb_clinical": str(paths.vitaldb_clinical),
                "vitaldb_sha256": digest(paths.vitaldb_clinical),
                "thread_environment": {key: os.environ.get(key) for key in
                                       ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                                        "MKL_NUM_THREADS", "PREOPXAI_WORKERS")}}
    paths.logs.mkdir(parents=True, exist_ok=True)
    _ = (paths.logs / "check.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps(metadata, indent=2))


@app.command()
def prepare() -> None:
    """Build the analysis tables from the raw MOVER files."""
    run([sys.executable, "-m", "pipeline.prepare"], "prepare")


@app.command()
def protocol(
    steps: Annotated[list[str] | None, typer.Argument(
        help=f"Steps to run, from: {' '.join(PROTOCOL_STEPS)}. Default: all. Finished steps are skipped.",
        show_default=False)] = None,
) -> None:
    """Run the study: models, metrics, SHAP, stability, repeated splits and the aggregate export."""
    steps = steps or []
    if unknown := [step for step in steps if step not in PROTOCOL_STEPS]:
        raise typer.BadParameter(f"Unknown step(s): {', '.join(unknown)}", param_hint="STEPS")
    run([sys.executable, "-m", "pipeline.protocol", *steps],
        "protocol-" + ("all" if not steps else "-".join(steps)))


@app.command()
def report(
    promote: Annotated[bool, typer.Option(
        help="Also copy the aggregates into results/ and verification/ and refresh the README table.")] = False,
) -> None:
    """Generate the summary and figures from the aggregate export."""
    run([sys.executable, "-m", "pipeline.reporting.stage", *(["--promote"] if promote else [])], "report")
    if promote:
        table()


@app.command()
def table(
    check_only: Annotated[bool, typer.Option("--check", help="Fail if the README table is stale.")] = False,
) -> None:
    """Write the README results table from results/."""
    stream([sys.executable, "-m", "pipeline.reporting.render_table", *(["--check"] if check_only else [])])


@app.command()
def verify() -> None:
    """Run the SHAP self-test and compare the aggregates strictly with results/."""
    run([sys.executable, "-m", "pipeline.verify"], "verify")


@app.command("all")
def all_stages() -> None:
    """Run check, prepare, protocol, report and verify in order."""
    check()
    prepare()
    protocol(None)
    report(promote=False)
    verify()


@app.command("export-models")
def export_models() -> None:
    """Refit the primary split, save it to artifacts/ and verify it against results/."""
    run([sys.executable, "-m", "pipeline.export_models"], "export-models")


@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def test(ctx: typer.Context) -> None:
    """Build the site data, then run the pipeline and dashboard tests. Extra arguments go to pytest."""
    stream([sys.executable, "-m", "app.build_data"])
    stream([sys.executable, "-m", "pytest", "tests", "app/tests", *ctx.args])


@web.command("build")
def web_build(
    static: Annotated[bool, typer.Option(
        help="Build the findings-only static site into app/web/dist-static instead.")] = False,
) -> None:
    """Build the site data and the web frontend."""
    stream([sys.executable, "-m", "app.build_data"])
    npm("run", "build:static" if static else "build")


@web.command("serve")
def web_serve(
    port: Annotated[int, typer.Option(help="Port on 127.0.0.1.")] = 8000,
) -> None:
    """Serve the built frontend and the API on one port, bound to 127.0.0.1 only."""
    import uvicorn

    from app.api.main import create_site

    dist = WEB / "dist"
    if not (dist / "index.html").is_file():
        raise SystemExit("The frontend is not built. Run: uv run preopxai app build")
    print(f"PreOp-XAI: http://{HOST}:{port} (research prototype, not for clinical use)", flush=True)
    uvicorn.run(create_site(dist), host=HOST, port=port)


@web.command("e2e")
def web_e2e() -> None:
    """Build both frontends and run the Playwright smoke tests."""
    web_build(static=False)
    web_build(static=True)
    npm("run", "test:e2e")


@web.command("screenshots")
def web_screenshots() -> None:
    """Build both frontends and regenerate docs/screenshots."""
    web_build(static=False)
    web_build(static=True)
    npm("run", "screenshots")


if __name__ == "__main__":
    app()
