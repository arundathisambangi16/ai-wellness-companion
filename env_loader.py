from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
LOCAL_ENV_PATH = PROJECT_ROOT / ".env"


def _parse_env_line(line: str) -> tuple[str, str] | None:
    clean = line.strip()
    if not clean or clean.startswith("#") or "=" not in clean:
        return None

    key, value = clean.split("=", 1)
    key = key.strip()
    value = value.strip().strip("\"").strip("'")
    if not key:
        return None
    return key, value


def load_local_env(path: Path | None = None, override: bool = False) -> None:
    env_paths = [path] if path else [LOCAL_ENV_PATH]
    for env_path in env_paths:
        if not env_path.exists():
            continue

        try:
            for raw_line in env_path.read_text(encoding="utf-8").splitlines():
                parsed = _parse_env_line(raw_line)
                if not parsed:
                    continue
                key, value = parsed
                if override or not os.getenv(key):
                    os.environ[key] = value
        except Exception:
            return
