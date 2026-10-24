"""Run checks with a deadline, including tests of native multimedia objects."""
from pathlib import Path
import os
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
environment = os.environ.copy()
environment.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    bootstrap = (
        "import faulthandler, sys, unittest; "
        "faulthandler.dump_traceback_later(15, repeat=True); "
        "suite = unittest.defaultTestLoader.discover('tests'); "
        "result = unittest.TextTestRunner(verbosity=2).run(suite); "
        "faulthandler.cancel_dump_traceback_later(); "
        "sys.exit(not result.wasSuccessful())"
    )
    result = subprocess.run(
        [sys.executable, "-c", bootstrap],
        cwd=root, env=environment, timeout=45,
    )
    raise SystemExit(result.returncode)
except subprocess.TimeoutExpired:
    print("Tests exceeded 45 seconds; child process stopped.", file=sys.stderr)
    raise SystemExit(1)
