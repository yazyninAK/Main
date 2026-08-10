"""Load a local .env file (KEY=VALUE per line) into os.environ, if present.

Only relevant for local/manual runs (e.g. on your own laptop, via Task
Scheduler). GitHub Actions sets these as real environment variables from
its own secrets, so this is a no-op there (no .env file present).
"""
from __future__ import annotations

import os
import pathlib


def load_env_file(path: str | pathlib.Path | None = None) -> None:
    if path is None:
        path = pathlib.Path(__file__).resolve().parent.parent / ".env"
    else:
        path = pathlib.Path(path)

    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)
