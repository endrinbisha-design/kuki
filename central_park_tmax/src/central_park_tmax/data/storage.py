"""Atomic file writes, checksums/manifests, cached HTTP, and append-only versioned store.

Design rules honored here:
  * Atomic writes (write temp + os.replace) so a crash never leaves a half file.
  * Append-only version stores never overwrite an earlier version.
  * HTTP with timeouts, bounded retries + exponential backoff, and on-disk caching.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time as _time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import requests

from ..logging_config import get_logger

log = get_logger(__name__)


# --------------------------------------------------------------------------------------
# Atomic writes
# --------------------------------------------------------------------------------------
def atomic_write_text(path: Path | str, text: str, encoding: str = "utf-8") -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp_", suffix=path.suffix)
    try:
        with os.fdopen(fd, "w", encoding=encoding) as fh:
            fh.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return path


def atomic_write_bytes(path: Path | str, data: bytes) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp_", suffix=path.suffix)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return path


def write_json(path: Path | str, obj: Any, indent: int = 2) -> Path:
    return atomic_write_text(path, json.dumps(obj, indent=indent, default=str, sort_keys=False))


def read_json(path: Path | str) -> Any:
    with Path(path).open("r", encoding="utf-8") as fh:
        return json.load(fh)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path | str) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def write_manifest(path: Path | str, files: list[Path | str], extra: Optional[dict] = None) -> Path:
    manifest = {
        "created_utc": _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
        "files": [{"path": str(p), "sha256": sha256_file(p), "bytes": Path(p).stat().st_size}
                  for p in files if Path(p).exists()],
    }
    if extra:
        manifest.update(extra)
    return write_json(path, manifest)


# --------------------------------------------------------------------------------------
# Append-only versioned JSONL store (used for NWS report versions, predictions, etc.)
# --------------------------------------------------------------------------------------
class AppendOnlyStore:
    """A JSONL file to which records are only ever appended, never rewritten.

    Used to preserve *every* retrieved NWS report version. Callers may check for an
    identical prior record (by content hash) to avoid exact duplicates, but a differing
    record is always appended as a new version.
    """

    def __init__(self, path: Path | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: dict[str, Any]) -> None:
        line = json.dumps(record, default=str, sort_keys=True)
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def append_if_new(self, record: dict[str, Any], dedupe_key: str = "content_sha256") -> bool:
        """Append unless an existing record shares the same dedupe_key value.

        Returns True if appended (new version), False if an identical version existed.
        """
        target = record.get(dedupe_key)
        if target is not None:
            for existing in self.read_all():
                if existing.get(dedupe_key) == target:
                    return False
        self.append(record)
        return True

    def read_all(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        out: list[dict[str, Any]] = []
        with self.path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
        return out


# --------------------------------------------------------------------------------------
# HTTP with retries, timeout, and simple on-disk caching
# --------------------------------------------------------------------------------------
@dataclass
class HttpClient:
    user_agent: str = "central_park_tmax/0.1 (research)"
    timeout: int = 30
    max_retries: int = 4
    backoff: float = 2.0
    cache_dir: Optional[Path] = None
    cache_enabled: bool = True

    def _cache_path(self, url: str, suffix: str) -> Optional[Path]:
        if not (self.cache_enabled and self.cache_dir):
            return None
        key = sha256_text(url)[:24]
        return Path(self.cache_dir) / f"{key}{suffix}"

    def get_text(self, url: str, headers: Optional[dict] = None,
                 accept: Optional[str] = None, use_cache: bool = True) -> str:
        cache = self._cache_path(url, ".txt")
        if use_cache and cache and cache.exists():
            log.debug("cache hit %s", url)
            return cache.read_text(encoding="utf-8")
        text = self._request(url, headers=headers, accept=accept).text
        if cache is not None:
            atomic_write_text(cache, text)
        return text

    def get_json(self, url: str, headers: Optional[dict] = None, use_cache: bool = True) -> Any:
        txt = self.get_text(url, headers=headers, accept="application/geo+json,application/json",
                            use_cache=use_cache)
        return json.loads(txt)

    def get_bytes(self, url: str, headers: Optional[dict] = None, use_cache: bool = True) -> bytes:
        cache = self._cache_path(url, ".bin")
        if use_cache and cache and cache.exists():
            return cache.read_bytes()
        data = self._request(url, headers=headers).content
        if cache is not None:
            atomic_write_bytes(cache, data)
        return data

    def _request(self, url: str, headers: Optional[dict] = None,
                 accept: Optional[str] = None) -> requests.Response:
        hdrs = {"User-Agent": self.user_agent}
        if accept:
            hdrs["Accept"] = accept
        if headers:
            hdrs.update(headers)
        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = requests.get(url, headers=hdrs, timeout=self.timeout)
                if resp.status_code >= 500 or resp.status_code == 429:
                    raise requests.HTTPError(f"{resp.status_code} for {url}")
                resp.raise_for_status()
                return resp
            except Exception as exc:  # noqa: BLE001 - ret/backoff on any transient error
                last_exc = exc
                if attempt < self.max_retries:
                    wait = self.backoff * (2 ** attempt)
                    log.warning("HTTP attempt %d failed for %s: %s (retry in %.0fs)",
                                attempt + 1, url, exc, wait)
                    _time.sleep(wait)
        raise RuntimeError(f"HTTP GET failed after {self.max_retries + 1} attempts: {url}") from last_exc


def http_client_from_config(cfg) -> HttpClient:
    cache_dir = Path(cfg.paths.raw_dir) / "http_cache"
    return HttpClient(
        user_agent=cfg.http.user_agent,
        timeout=cfg.http.timeout_seconds,
        max_retries=cfg.http.max_retries,
        backoff=cfg.http.backoff_seconds,
        cache_dir=cache_dir,
        cache_enabled=cfg.http.cache_enabled,
    )
