"""Run the same desktop recovery check supported by the standalone app."""
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from remyplayer.app import main

if __name__ == "__main__":
    with TemporaryDirectory(prefix="remyplayer-desktop-") as temporary:
        raise SystemExit(main(["--check-desktop", "--data-dir", temporary]))
