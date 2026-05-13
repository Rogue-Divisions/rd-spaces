#!/usr/bin/env python3
"""Install Python browser-test dependencies and Chromium for paint checks."""

from __future__ import annotations

import importlib.util
import subprocess
import sys


def main() -> None:
    if importlib.util.find_spec("playwright") is None:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "playwright"])
    if importlib.util.find_spec("PIL") is None:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pillow"])
    subprocess.check_call([sys.executable, "-m", "playwright", "install", "chromium"])


if __name__ == "__main__":
    main()
