"""Throttled HTTP client for regulations.gov API v4 and its file host.

* API calls carry the key in the `X-Api-Key` header only.
* Every call is spaced by `min_interval` seconds; 429 and 5xx are retried with
  exponential backoff (honouring Retry-After); 403 is raised immediately,
  because retrying a rejected key just burns the hourly quota.
* downloads.regulations.gov does not take the key and 403s without a
  browser-like User-Agent and a regulations.gov Referer.
* Each request is appended to logs/requests.jsonl (path, params, status,
  remaining quota). The key is never logged.
"""
from __future__ import annotations

import json
import random
import threading
import time
from datetime import datetime, timezone

import httpx

from . import config

BASE = "https://api.regulations.gov/v4"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")
DOWNLOAD_HEADERS = {"User-Agent": UA, "Referer": "https://www.regulations.gov/", "Accept": "*/*"}


class ApiError(RuntimeError):
    def __init__(self, status: int, path: str, detail: str = ""):
        super().__init__(f"HTTP {status} on {path}{': ' + detail if detail else ''}")
        self.status = status


class AuthError(ApiError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class RegsGovClient:
    def __init__(self, min_interval: float = 1.0, max_tries: int = 6):
        self.min_interval = min_interval
        self.max_tries = max_tries
        self._key: str | None = None
        self._last = 0.0
        self._lock = threading.Lock()
        self._http = httpx.Client(timeout=httpx.Timeout(60.0, read=180.0), follow_redirects=True)
        self.stats = {"api_requests": 0, "downloads": 0, "429s": 0, "retries": 0}
        self.ratelimit_remaining: int | None = None

    # ------------------------------------------------------------- plumbing
    @property
    def key(self) -> str:
        if self._key is None:
            self._key = config.load_key()
        return self._key

    def _throttle(self) -> None:
        with self._lock:
            wait = self.min_interval - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()

    def _log(self, **rec) -> None:
        config.LOGS.mkdir(parents=True, exist_ok=True)
        rec = {"ts": _now(), **rec}
        with open(config.LOGS / "requests.jsonl", "a") as f:
            f.write(json.dumps(rec) + "\n")

    def _backoff(self, attempt: int, resp: httpx.Response | None) -> float:
        if resp is not None and resp.headers.get("Retry-After", "").isdigit():
            return float(resp.headers["Retry-After"])
        return min(300.0, 5.0 * 2 ** attempt) + random.uniform(0, 1)

    # ------------------------------------------------------------------ API
    def get(self, path: str, params: dict | None = None) -> dict:
        params = dict(params or {})
        url = f"{BASE}/{path.lstrip('/')}"
        for attempt in range(self.max_tries):
            self._throttle()
            resp = None
            try:
                resp = self._http.get(url, params=params, headers={"X-Api-Key": self.key, "User-Agent": UA})
            except httpx.TransportError as e:
                self._log(kind="api", path=path, params=params, status=None, error=type(e).__name__)
                self.stats["retries"] += 1
                time.sleep(self._backoff(attempt, None))
                continue
            self.stats["api_requests"] += 1
            rem = resp.headers.get("x-ratelimit-remaining")
            if rem and rem.isdigit():
                self.ratelimit_remaining = int(rem)
            self._log(kind="api", path=path, params=params, status=resp.status_code, ratelimit_remaining=rem)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 403:
                raise AuthError(403, path, "API key missing or rejected")
            if resp.status_code == 404:
                raise ApiError(404, path, "not found")
            if resp.status_code == 429 or resp.status_code >= 500:
                if resp.status_code == 429:
                    self.stats["429s"] += 1
                self.stats["retries"] += 1
                time.sleep(self._backoff(attempt, resp))
                continue
            raise ApiError(resp.status_code, path, resp.text[:300])
        raise ApiError(429, path, f"gave up after {self.max_tries} attempts")

    def get_all(self, path: str, params: dict, page_size: int = 250, max_pages: int = 20) -> tuple[list, dict]:
        """Page through a list endpoint. Returns (records, meta-of-last-page)."""
        out, meta = [], {}
        for page in range(1, max_pages + 1):
            j = self.get(path, {**params, "page[size]": page_size, "page[number]": page})
            out += j.get("data") or []
            meta = j.get("meta") or {}
            if not meta.get("hasNextPage"):
                break
        else:
            meta = {**meta, "ceiling_hit": True}
        return out, meta

    # ------------------------------------------------------------ downloads
    def download(self, url: str) -> tuple[bytes, str]:
        """Unauthenticated GET for an attachment/guidance file. Returns (bytes, content-type)."""
        for attempt in range(self.max_tries):
            self._throttle()
            try:
                resp = self._http.get(url, headers=DOWNLOAD_HEADERS)
            except httpx.TransportError as e:
                self._log(kind="download", url=url, status=None, error=type(e).__name__)
                time.sleep(self._backoff(attempt, None))
                continue
            self.stats["downloads"] += 1
            self._log(kind="download", url=url, status=resp.status_code, bytes=len(resp.content))
            if resp.status_code == 200:
                return resp.content, resp.headers.get("content-type", "")
            if resp.status_code == 429 or resp.status_code >= 500:
                self.stats["429s"] += resp.status_code == 429
                time.sleep(self._backoff(attempt, resp))
                continue
            raise ApiError(resp.status_code, url)
        raise ApiError(429, url, f"gave up after {self.max_tries} attempts")
