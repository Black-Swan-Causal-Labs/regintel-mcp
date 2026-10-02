"""Paths and API-key loading.

The key is read from the environment or a `.env` file and held only in memory.
It is sent as the `X-Api-Key` header (never as a URL parameter), so it cannot
leak into request logs, cached URLs or error messages.
"""
from __future__ import annotations

import os
from pathlib import Path

KEY_NAMES = ("REGULATIONS_GOV_API_KEY", "REGGOV_API_KEY")


def project_root() -> Path:
    """REGINTEL_HOME if set, else the repository checkout this package lives in."""
    env = os.environ.get("REGINTEL_HOME")
    return Path(env).expanduser().resolve() if env else Path(__file__).resolve().parent.parent


ROOT = project_root()
DATA = ROOT / "data"
RAW = DATA / "raw"
CACHE_DB = DATA / "cache.sqlite"
LOGS = ROOT / "logs"
OUTPUT = ROOT / "output"


class MissingKeyError(RuntimeError):
    pass


def load_key() -> str:
    for n in KEY_NAMES:
        if os.environ.get(n):
            return os.environ[n].strip()
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            line = line.strip()
            for n in KEY_NAMES:
                if line.startswith(n + "="):
                    v = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if v:
                        return v
    raise MissingKeyError(
        "No regulations.gov API key. Put REGULATIONS_GOV_API_KEY=<key> in "
        f"{ROOT / '.env'} or the environment (get one at https://open.gsa.gov/api/regulationsgov/)."
    )
