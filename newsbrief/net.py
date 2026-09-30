"""Bounded public HTTP access. No cookies, credentials, or automatic private redirects."""
import ipaddress
import socket
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler

USER_AGENT = "MorningNewsCards/1.0 (personal news digest; contact via repository)"


class FetchError(Exception):
    def __init__(self, code="network"):
        self.code = str(code)
        super().__init__(self.code)


def public_url(url, resolve=False):
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("https", "http") or not parsed.hostname or parsed.username or parsed.password:
            return False
        if parsed.port not in (None, 80, 443):
            return False
        host = parsed.hostname.lower()
        if host == "localhost" or host.endswith((".local", ".internal", ".localhost")):
            return False
        try:
            if not ipaddress.ip_address(host).is_global:
                return False
        except ValueError:
            pass
        if resolve:
            addresses = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80))
            if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
                return False
        return True
    except (ValueError, OSError):
        return False


class PublicRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if req.has_header("X-goog-api-key") and urlparse(newurl).hostname != urlparse(req.full_url).hostname:
            raise FetchError("credential_redirect")
        if not public_url(newurl, resolve=True):
            raise FetchError("unsafe_redirect")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url, *, data=None, headers=None, limit=3_000_000, retries=1, timeout=15):
    if not public_url(url, resolve=True):
        raise FetchError("unsafe_url")
    request = Request(url, data=data, headers={"User-Agent": USER_AGENT, **(headers or {})})
    for attempt in range(retries + 1):
        try:
            with build_opener(PublicRedirect()).open(request, timeout=timeout) as response:
                body = response.read(limit + 1)
                if len(body) > limit:
                    raise FetchError("too_large")
                return body, response.geturl()
        except HTTPError as exc:
            # Never include a response body, request headers, or API key in an exception.
            if attempt < retries and exc.code in (429, 500, 502, 503, 504):
                time.sleep(2 ** attempt)
                continue
            raise FetchError(exc.code) from None
        except (URLError, TimeoutError, OSError):
            if attempt < retries:
                time.sleep(2 ** attempt)
                continue
            raise FetchError("network") from None
    raise FetchError()
