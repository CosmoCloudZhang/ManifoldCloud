"""CosmoHub's catalogue and query API with in-memory authentication."""

from pathlib import Path
from time import monotonic, sleep
from urllib.parse import urljoin, urlsplit

import requests

from manifoldcloud.core.provenance import atomic_path

API_ORIGIN = "https://api.cosmohub.pic.es"
API_HOST = "api.cosmohub.pic.es"
REDIRECTS = {301, 302, 303, 307, 308}
TIMEOUT = (15, 120)


class CosmoHubError(RuntimeError):
    """An API or transport failure with no response body or request details."""

    def __init__(self, message, status_code=None):
        self.status_code = status_code
        suffix = f" (HTTP {status_code})" if status_code is not None else ""
        super().__init__(f"{message}{suffix}")


def _origin(url):
    """Accept only HTTPS URLs without user information."""
    try:
        parsed = urlsplit(url)
        if (parsed.scheme == "https" and parsed.hostname and parsed.username is None
                and parsed.password is None and not parsed.fragment):
            port = parsed.port
            return parsed.hostname, 443 if port is None else port
    except (TypeError, ValueError):
        pass
    raise CosmoHubError("CosmoHub supplied an invalid HTTPS result URL")


def _join_url(base, location):
    try:
        return urljoin(base, location)
    except (TypeError, ValueError):
        pass
    raise CosmoHubError("CosmoHub supplied an invalid HTTPS result URL")


def _require_success(response, operation):
    if not 200 <= response.status_code < 300:
        raise CosmoHubError(f"CosmoHub {operation} failed", response.status_code)


def _json(response, operation):
    try:
        return response.json()
    except ValueError:
        pass
    raise CosmoHubError(f"CosmoHub {operation} returned invalid JSON", response.status_code)


def _query_id(value):
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    if isinstance(value, str) and value.isascii() and value.isdecimal():
        try:
            return int(value)
        except ValueError:
            pass
    raise CosmoHubError("CosmoHub query ID must be a non-negative integer")


class CosmoHubClient:
    """Talk to the fixed API origin and use its token only on that origin."""

    def __init__(self, session=None):
        self._session = requests.Session() if session is None else session
        # requests otherwise consults netrc when preparing redirects.
        self._session.trust_env = False
        self._token = None

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()

    def close(self):
        """Discard the token and release HTTP connections."""
        self._token = None
        self._session.close()

    def _send(self, method, url, *, operation, headers=None, stream=False, **kwargs):
        try:
            # Start with only explicit headers, without session cookies or auth.
            request = requests.Request(method, url, headers=headers, **kwargs).prepare()
            if _origin(request.url) != _origin(url):
                raise CosmoHubError("CosmoHub result URL changed origin during preparation")
            return self._session.send(request, allow_redirects=False, timeout=TIMEOUT,
                                      stream=stream, proxies={}, verify=True, cert=None)
        except (requests.RequestException, ValueError):
            pass
        raise CosmoHubError(f"CosmoHub {operation} request failed")

    def _rotate_token(self, response):
        token = response.headers.get("X-Token")
        if token:
            if token.strip() != token or any(ord(character) < 33 or ord(character) > 126 for character in token):
                raise CosmoHubError("CosmoHub returned an invalid token header", response.status_code)
            self._token = token

    def _authenticated_headers(self):
        if not self._token:
            raise CosmoHubError("CosmoHub sign-in is required")
        return {"Authorization": f"Token {self._token}"}

    def sign_in(self, email, password):
        """Exchange HTTP Basic credentials once for an in-memory session token."""
        self._token = None
        with self._send("GET", f"{API_ORIGIN}/user", operation="sign-in", auth=(email, password)) as response:
            try:
                _require_success(response, "sign-in")
                self._rotate_token(response)
                if self._token is None:
                    raise CosmoHubError("CosmoHub sign-in returned no session token", response.status_code)
            finally:
                if response.request is not None:
                    response.request.headers.pop("Authorization", None)

    def _api(self, method, path, operation, *, read_json=True, **kwargs):
        with self._send(method, f"{API_ORIGIN}{path}", operation=operation,
                        headers=self._authenticated_headers(), **kwargs) as response:
            self._rotate_token(response)
            _require_success(response, operation)
            if read_json and response.status_code != 204:
                return _json(response, operation)
        return None

    def catalog_metadata(self, catalogue_id):
        """Return the JSON metadata for a catalogue."""
        identifier = _query_id(catalogue_id)
        return self._api("GET", f"/catalogs/{identifier}", "catalogue metadata")

    def check_syntax(self, sql):
        """Check SQL syntax and return the service response."""
        result = self._api("GET", "/catalogs/syntax", "syntax check", params={"sql": sql})
        if result is False or (isinstance(result, dict) and (
            result.get("valid") is False or result.get("success") is False or result.get("error")
        )):
            raise CosmoHubError("CosmoHub rejected the query syntax")
        return result

    def submit(self, sql):
        """Submit SQL as a Parquet query and return its identifier."""
        result = self._api("POST", "/queries", "query submission", json={"sql": sql, "format": "parquet"})
        if not isinstance(result, dict) or "id" not in result:
            raise CosmoHubError("CosmoHub query submission returned no query ID")
        return _query_id(result["id"])

    def poll(self, query_id, *, interval=10, timeout=7200):
        """Return the result URL or raise on failure, cancellation, or timeout."""
        identifier = _query_id(query_id)
        if interval < 0 or timeout < 0:
            raise ValueError("Polling interval and timeout must be non-negative")
        deadline = monotonic() + timeout
        while True:
            result = self._api("GET", "/queries", "query status")
            # The documented fields come from the public app. The live response
            # envelope still needs the mentor's first authorised API check.
            queries = result.get("queries") if isinstance(result, dict) else result
            if not isinstance(queries, list):
                raise CosmoHubError("CosmoHub returned an invalid query list")
            for entry in queries:
                if isinstance(entry, dict) and str(entry.get("id")) == str(identifier):
                    status = entry.get("status")
                    if status == "SUCCEEDED":
                        url = entry.get("download_results")
                        if not isinstance(url, str) or not url:
                            raise CosmoHubError("CosmoHub query succeeded without a result URL")
                        return url
                    if status == "FAILED":
                        raise CosmoHubError("CosmoHub query FAILED")
                    if status == "CANCELLED":
                        raise CosmoHubError("CosmoHub query CANCELLED")
                    if status not in ("PENDING", "PROCESSING"):
                        raise CosmoHubError("CosmoHub returned an unknown query status")
                    break
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise CosmoHubError("CosmoHub query polling timed out")
            sleep(min(interval, remaining))

    def cancel(self, query_id):
        """Request cancellation by numeric query ID."""
        identifier = _query_id(query_id)
        self._api("POST", f"/queries/{identifier}/cancel", "query cancellation", read_json=False)

    def download(self, url, output):
        """Stream the result to disk, dropping authentication at an origin change."""
        output = Path(output)
        url = _join_url(f"{API_ORIGIN}/", url)
        may_send_token = True
        for hop in range(6):
            # Validate every hop even after credentials have been dropped.
            origin = _origin(url)
            may_send_token = may_send_token and origin == (API_HOST, 443)
            headers = self._authenticated_headers() if may_send_token else None
            with self._send("GET", url, operation="result download", headers=headers, stream=True) as response:
                if may_send_token:
                    self._rotate_token(response)
                if response.status_code in REDIRECTS:
                    location = response.headers.get("Location")
                    if not location or hop == 5:
                        raise CosmoHubError("CosmoHub result redirect failed", response.status_code)
                    url = _join_url(url, location)
                    continue
                _require_success(response, "result download")
                try:
                    with atomic_path(output) as part, part.open("wb") as target:
                        for chunk in response.iter_content(chunk_size=1024 * 1024):
                            target.write(chunk)
                    return output
                except requests.RequestException:
                    pass
                raise CosmoHubError("CosmoHub result download was interrupted", response.status_code)
        raise CosmoHubError("CosmoHub result redirect limit exceeded")
