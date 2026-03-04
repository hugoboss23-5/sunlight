"""
SUNLIGHT OCDS Data Fetcher

Fetches procurement data from real OCDS publisher APIs.
Each country's OCDS API is different — this module normalizes access.

Supported sources:
- UK Contracts Finder (contracts.open-contracting.org)
- Colombia SECOP II (api.colombiacompra.gov.co)
- Paraguay DNCP (contrataciones.gov.py)
- Mexico (api.datos.gob.mx — CompraNet)
- Generic OCDS API (any conformant endpoint)

Usage:
    fetcher = OCDSFetcher("GB")
    releases = fetcher.fetch(limit=1000)
"""

from __future__ import annotations
import json
import logging
import time
from dataclasses import dataclass
from typing import Optional, Iterator
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from urllib.parse import urlencode, urljoin

logger = logging.getLogger(__name__)


@dataclass
class OCDSSource:
    """Configuration for an OCDS data source."""
    country_code: str
    country_name: str
    base_url: str
    api_type: str  # "ocds_api", "bulk_json", "csv"
    releases_path: str = "/api/v1/releases"
    packages_path: str = ""
    page_size: int = 100
    rate_limit_seconds: float = 1.0
    headers: dict = None
    notes: str = ""

    def __post_init__(self):
        if self.headers is None:
            self.headers = {}


# Registry of known OCDS sources
OCDS_SOURCES = {
    "GB": OCDSSource(
        country_code="GB",
        country_name="United Kingdom",
        base_url="https://www.contractsfinder.service.gov.uk",
        api_type="contracts_finder",
        releases_path="/Published/Notices/OCDS/Search",
        page_size=100,
        rate_limit_seconds=1.0,
        notes="UK Contracts Finder — published notices in OCDS format",
    ),
    "CO": OCDSSource(
        country_code="CO",
        country_name="Colombia",
        base_url="https://api.colombiacompra.gov.co",
        api_type="ocds_api",
        releases_path="/releases",
        page_size=100,
        rate_limit_seconds=0.5,
        notes="Colombia SECOP II via Colombia Compra Eficiente",
    ),
    "PY": OCDSSource(
        country_code="PY",
        country_name="Paraguay",
        base_url="https://contrataciones.gov.py",
        api_type="ocds_api",
        releases_path="/datos/api/v3/doc/ocds/releases",
        page_size=50,
        rate_limit_seconds=1.0,
        notes="Paraguay DNCP — national procurement authority",
    ),
    "MX": OCDSSource(
        country_code="MX",
        country_name="Mexico",
        base_url="https://api.datos.gob.mx",
        api_type="ocds_api",
        releases_path="/v1/contratacionesabiertas",
        page_size=100,
        rate_limit_seconds=1.0,
        notes="Mexico CompraNet via datos.gob.mx",
    ),
}


class FetchError(Exception):
    """Raised when OCDS data fetch fails."""
    pass


class OCDSFetcher:
    """
    Fetches OCDS releases from a country's procurement data API.

    Handles pagination, rate limiting, error recovery, and normalization
    of different API response formats into standard OCDS releases.
    """

    def __init__(self, country_code: str, source: Optional[OCDSSource] = None):
        if source:
            self.source = source
        elif country_code in OCDS_SOURCES:
            self.source = OCDS_SOURCES[country_code]
        else:
            raise ValueError(
                f"No OCDS source configured for '{country_code}'. "
                f"Available: {', '.join(OCDS_SOURCES.keys())}. "
                f"Or provide a custom OCDSSource."
            )

    def fetch(self, limit: int = 500, offset: int = 0) -> list[dict]:
        """
        Fetch OCDS releases up to limit.

        Returns list of OCDS release dicts.
        """
        releases = []
        for batch in self._paginate(limit=limit, offset=offset):
            releases.extend(batch)
            logger.info(f"Fetched {len(releases)} releases so far...")
            if len(releases) >= limit:
                break
        return releases[:limit]

    def fetch_iter(self, limit: int = 5000) -> Iterator[list[dict]]:
        """
        Yield batches of OCDS releases. Memory-efficient for large datasets.
        """
        count = 0
        for batch in self._paginate(limit=limit, offset=0):
            yield batch
            count += len(batch)
            if count >= limit:
                break

    def _paginate(self, limit: int, offset: int) -> Iterator[list[dict]]:
        """Handle pagination for different API types."""
        if self.source.api_type == "contracts_finder":
            yield from self._paginate_contracts_finder(limit, offset)
        elif self.source.api_type == "ocds_api":
            yield from self._paginate_generic_ocds(limit, offset)
        elif self.source.api_type == "bulk_json":
            yield from self._fetch_bulk_json(limit)
        else:
            raise FetchError(f"Unknown API type: {self.source.api_type}")

    def _paginate_contracts_finder(self, limit: int, offset: int) -> Iterator[list[dict]]:
        """UK Contracts Finder specific pagination."""
        page = 1
        fetched = 0

        while fetched < limit:
            params = {
                "publishedFrom": "2024-01-01T00:00:00Z",
                "publishedTo": "2025-12-31T23:59:59Z",
                "size": min(self.source.page_size, limit - fetched),
                "page": page,
            }
            url = f"{self.source.base_url}{self.source.releases_path}?{urlencode(params)}"

            try:
                data = self._http_get(url)
            except FetchError as e:
                logger.warning(f"Fetch failed at page {page}: {e}")
                break

            # Contracts Finder returns {"releases": [...]}
            releases = self._extract_releases(data)
            if not releases:
                break

            yield releases
            fetched += len(releases)
            page += 1

            time.sleep(self.source.rate_limit_seconds)

    def _paginate_generic_ocds(self, limit: int, offset: int) -> Iterator[list[dict]]:
        """Generic OCDS API pagination (offset-based or cursor-based)."""
        current_offset = offset
        fetched = 0

        while fetched < limit:
            params = {
                "limit": min(self.source.page_size, limit - fetched),
                "offset": current_offset,
            }
            url = f"{self.source.base_url}{self.source.releases_path}?{urlencode(params)}"

            try:
                data = self._http_get(url)
            except FetchError as e:
                logger.warning(f"Fetch failed at offset {current_offset}: {e}")
                break

            releases = self._extract_releases(data)
            if not releases:
                break

            yield releases
            fetched += len(releases)
            current_offset += len(releases)

            # Check for next page link
            next_url = None
            if isinstance(data, dict):
                links = data.get("links", {})
                next_url = links.get("next")
            if not next_url and len(releases) < self.source.page_size:
                break

            time.sleep(self.source.rate_limit_seconds)

    def _fetch_bulk_json(self, limit: int) -> Iterator[list[dict]]:
        """Fetch from a bulk JSON endpoint (single large response)."""
        url = f"{self.source.base_url}{self.source.releases_path}"
        data = self._http_get(url)
        releases = self._extract_releases(data)
        yield releases[:limit]

    def _extract_releases(self, data) -> list[dict]:
        """
        Extract releases from various OCDS response formats.

        Handles:
        - Standard release package: {"releases": [...]}
        - Array of release packages: [{"releases": [...]}, ...]
        - Direct array of releases: [{...}, {...}]
        - Contracts Finder format: {"releases": [...]}
        """
        if isinstance(data, list):
            # Could be array of packages or array of releases
            releases = []
            for item in data:
                if isinstance(item, dict) and "releases" in item:
                    releases.extend(item["releases"])
                elif isinstance(item, dict) and "ocid" in item:
                    releases.append(item)
            return releases

        if isinstance(data, dict):
            if "releases" in data:
                return data["releases"]
            if "results" in data:
                # Some APIs wrap in results
                results = data["results"]
                if isinstance(results, list):
                    return self._extract_releases(results)
            if "ocid" in data:
                return [data]

        return []

    def _http_get(self, url: str, retries: int = 3) -> dict:
        """HTTP GET with retry and error handling."""
        headers = {"Accept": "application/json", "User-Agent": "SUNLIGHT/1.0"}
        headers.update(self.source.headers)

        for attempt in range(retries):
            try:
                req = Request(url, headers=headers)
                with urlopen(req, timeout=30) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except HTTPError as e:
                if e.code == 429:
                    wait = (attempt + 1) * 5
                    logger.warning(f"Rate limited, waiting {wait}s...")
                    time.sleep(wait)
                elif e.code >= 500:
                    logger.warning(f"Server error {e.code}, retrying...")
                    time.sleep(2)
                else:
                    raise FetchError(f"HTTP {e.code}: {e.reason} for {url}")
            except URLError as e:
                logger.warning(f"Connection error: {e.reason}, retrying...")
                time.sleep(2)
            except json.JSONDecodeError as e:
                raise FetchError(f"Invalid JSON from {url}: {e}")

        raise FetchError(f"Failed after {retries} retries: {url}")


# ---------------------------------------------------------------------------
# File-based loading (for offline / pre-downloaded data)
# ---------------------------------------------------------------------------

def load_releases_from_file(filepath: str) -> list[dict]:
    """
    Load OCDS releases from a local JSON file.

    Supports:
    - Release package: {"releases": [...]}
    - Array of releases: [{...}, {...}]
    - Newline-delimited JSON (one release per line)
    """
    with open(filepath, "r") as f:
        first_char = f.read(1)
        f.seek(0)

        if first_char == "[":
            data = json.load(f)
            if isinstance(data, list) and data and "releases" in data[0]:
                # Array of release packages
                releases = []
                for pkg in data:
                    releases.extend(pkg.get("releases", []))
                return releases
            return data

        if first_char == "{":
            data = json.load(f)
            if "releases" in data:
                return data["releases"]
            return [data]

        # Try newline-delimited
        releases = []
        f.seek(0)
        for line in f:
            line = line.strip()
            if line:
                releases.append(json.loads(line))
        return releases


def load_releases_from_directory(dirpath: str) -> list[dict]:
    """Load all JSON files from a directory as OCDS releases."""
    import os
    releases = []
    for filename in sorted(os.listdir(dirpath)):
        if filename.endswith(".json"):
            filepath = os.path.join(dirpath, filename)
            releases.extend(load_releases_from_file(filepath))
    return releases
