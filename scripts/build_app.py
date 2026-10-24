"""Build a standalone macOS app through the selected PySide6 deployment tool."""
import os
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
environment = os.environ.copy()
environment["PYTHONPATH"] = str(root / "src")
tool = Path(sys.executable).parent / "pyside6-deploy"
try:
    result = subprocess.call(
        [str(tool), "-c", "pysidedeploy.spec", "--force", *sys.argv[1:]],
        cwd=root, env=environment,
    )
finally:
    # Qt rewrites the config with whitespace after empty values on every build.
    spec = root / "pysidedeploy.spec"
    spec.write_text("\n".join(line.rstrip() for line in spec.read_text().splitlines()).rstrip() + "\n")
raise SystemExit(result)
