from __future__ import annotations

from pathlib import Path
from typing import Mapping

import requests


DEFAULT_HEADERS = {
    "User-Agent": "run-totals-research/0.1 (+local research; polite cached requests)"
}


def fetch_url(url: str, out: Path, headers: Mapping[str, str] | None = None, timeout: int = 30) -> Path:
    """Fetch a URL once and write the raw response to disk.

    Keep this layer intentionally small: source-specific parsing belongs in
    feature-building code after the raw artifact is cached.
    """
    out.parent.mkdir(parents=True, exist_ok=True)
    request_headers = dict(DEFAULT_HEADERS)
    if headers:
        request_headers.update(headers)

    response = requests.get(url, headers=request_headers, timeout=timeout)
    response.raise_for_status()
    out.write_bytes(response.content)
    return out

