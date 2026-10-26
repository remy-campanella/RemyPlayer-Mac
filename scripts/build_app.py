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
if result == 0 and "--dry-run" not in sys.argv and "--init" not in sys.argv:
    bundle = root / "dist" / "RemyPlayer.app"
    # Deployment may overlay an older bundle and retain excluded data files.
    # Remove only generated copies of local icon design backups before sealing.
    for backup in bundle.rglob("icon.old.*"):
        if backup.is_file():
            backup.unlink()
    # Re-seal the final copied bundle; the deploy tool's pre-copy signature can
    # be rejected by taskgated after rebuilding over an existing application.
    subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(bundle)], check=True)
    subprocess.run(["codesign", "--verify", "--deep", "--strict", str(bundle)], check=True)
raise SystemExit(result)
