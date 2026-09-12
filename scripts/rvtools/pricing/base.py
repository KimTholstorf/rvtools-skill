"""Small, dependency-free HTTP and cache helpers for public price catalogs."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from urllib.request import Request, urlopen


DEFAULT_TIMEOUT_SECONDS = 20
DEFAULT_CACHE_SECONDS = 24 * 60 * 60


def private_cache_root(environ=None):
    environ = os.environ if environ is None else environ
    for variable in ("RVTOOLS_PLUGIN_DATA", "PLUGIN_DATA", "CLAUDE_PLUGIN_DATA"):
        value = environ.get(variable)
        if value:
            return Path(value).expanduser() / "pricing-cache"
    return Path(tempfile.gettempdir()) / "rvtools-analyzer-pricing-cache"


def fetch_json(url, *, headers=None, timeout=DEFAULT_TIMEOUT_SECONDS):
    request = Request(url, headers=headers or {"Accept": "application/json"})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


class CachedJsonFetcher:
    """Cache filtered public catalog responses without storing workbook data."""

    def __init__(self, *, cache_root=None, max_age_seconds=DEFAULT_CACHE_SECONDS, fetcher=None):
        self.cache_root = Path(cache_root) if cache_root else private_cache_root()
        self.max_age_seconds = max_age_seconds
        self.fetcher = fetcher or fetch_json

    def __call__(self, url, *, headers=None):
        key_material = json.dumps([url, sorted((headers or {}).items())], separators=(",", ":"))
        digest = hashlib.sha256(key_material.encode("utf-8")).hexdigest()
        path = self.cache_root / f"{digest}.json"
        try:
            if path.is_file() and time.time() - path.stat().st_mtime <= self.max_age_seconds:
                return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass

        payload = self.fetcher(url, headers=headers)
        self.cache_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        try:
            self.cache_root.chmod(0o700)
        except OSError:
            pass
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        if hasattr(os, "fchmod"):
            os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, separators=(",", ":"))
        return payload


def money_value(value):
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, dict):
        return None
    units = float(value.get("units") or 0)
    nanos = float(value.get("nanos") or 0)
    return units + nanos / 1_000_000_000


def normalized_text(value):
    return " ".join(str(value or "").casefold().replace("-", " ").replace("_", " ").split())
