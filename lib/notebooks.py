"""Execute notebooks in place, and guard that they are committed WITH their outputs.

This repo is read far more often than it is run. Almost everyone meets it by scrolling
it on GitHub, and GitHub renders a notebook's *saved* outputs -- so an unexecuted
notebook is a blank page to most of its audience. Outputs are part of the artifact
here, not build residue.

    python lib/notebooks.py run     # execute every notebook, save outputs in place
    python lib/notebooks.py check   # exit 1 if any notebook is missing its outputs
"""
from __future__ import annotations

import sys
from pathlib import Path

import nbformat
from nbclient import NotebookClient

ROOT = Path(__file__).resolve().parent.parent
NB_DIR = ROOT / "notebooks"
TIMEOUT = 900


def notebooks() -> list[Path]:
    return sorted(p for p in NB_DIR.glob("*.ipynb") if ".ipynb_checkpoints" not in str(p))


def run(paths: list[Path]) -> int:
    failed = []
    for path in paths:
        print(f">> executing {path.relative_to(ROOT)}")
        nb = nbformat.read(path, as_version=4)
        client = NotebookClient(
            nb,
            timeout=TIMEOUT,
            kernel_name="python3",
            allow_errors=False,
            resources={"metadata": {"path": str(path.parent)}},
        )
        try:
            client.execute()
        except Exception as exc:  # noqa: BLE001 -- report, keep going, fail at the end
            print(f"!! {path.name}: {type(exc).__name__}: {exc}")
            failed.append(path.name)
            continue
        nbformat.write(nb, path)
        print(f"   ok, outputs saved")
    if failed:
        print(f"\n!! {len(failed)} notebook(s) failed: {', '.join(failed)}")
        return 1
    print(f"\nOK -- {len(paths)} notebook(s) executed with outputs saved")
    return 0


def check(paths: list[Path]) -> int:
    problems = []
    for path in paths:
        nb = nbformat.read(path, as_version=4)
        code = [c for c in nb.cells if c.cell_type == "code" and c.source.strip()]
        bare = [i for i, c in enumerate(code) if not c.get("outputs") and c.get("execution_count") is None]
        if not code:
            continue
        if bare:
            problems.append(f"{path.name}: {len(bare)}/{len(code)} code cell(s) never executed")
            continue
        errors = [o for c in code for o in c.get("outputs", []) if o.get("output_type") == "error"]
        if errors:
            problems.append(f"{path.name}: {len(errors)} cell(s) committed with an error output")
    for p in problems:
        print(f"!! {p}")
    if problems:
        print("\nrun 'make notebooks' before committing")
        return 1
    print(f"OK -- {len(paths)} notebook(s) carry their outputs")
    return 0


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "check"
    picked = [Path(a).resolve() for a in sys.argv[2:]] or notebooks()
    sys.exit({"run": run, "check": check}[mode](picked))
