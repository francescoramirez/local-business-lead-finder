from __future__ import annotations

import ssl
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from leadfinder.models import Lead

SOCIAL_HOSTS = frozenset(
    {
        "facebook.com",
        "fb.com",
        "instagram.com",
        "twitter.com",
        "x.com",
        "tiktok.com",
        "youtube.com",
        "youtu.be",
        "wa.me",
        "api.whatsapp.com",
        "linkedin.com",
        "m.facebook.com",
    }
)
AGGREGATOR_HOSTS = frozenset(
    {
        "linktr.ee",
        "linktree.com",
        "beacons.ai",
        "bio.link",
        "carrd.co",
        "tap.bio",
        "lnk.bio",
        "solo.to",
    }
)


def _host(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.netloc or parsed.path).lower()
    if host.startswith("www."):
        host = host[4:]
    return host.split(":")[0]


def classify_url(url: str) -> str:
    if not url.strip():
        return "no_website"
    host = _host(url)
    if any(host == item or host.endswith("." + item) for item in AGGREGATOR_HOSTS):
        return "link_aggregator"
    if any(host == item or host.endswith("." + item) for item in SOCIAL_HOSTS):
        return "social_only"
    parsed = urlparse(url)
    if parsed.scheme and parsed.scheme != "https":
        return "non_https"
    return "has_website"


def probe_url(url: str, *, timeout: float = 5.0) -> str:
    """Cheap reachability check. HEAD then GET. No crawling, no exploit probes."""
    classified = classify_url(url)
    if classified in {"no_website", "social_only", "link_aggregator"}:
        return classified
    request = Request(url, method="HEAD", headers={"User-Agent": "leadfinder/0.1"})
    context = ssl.create_default_context()
    try:
        with urlopen(request, timeout=timeout, context=context) as response:
            if 200 <= getattr(response, "status", 200) < 400:
                return classified
    except HTTPError as error:
        if error.code in {405, 501}:
            return _get_probe(url, timeout, context, classified)
        return "unreachable"
    except (URLError, TimeoutError, ValueError, ssl.SSLError):
        return _get_probe(url, timeout, context, classified)
    return classified


def _get_probe(url: str, timeout: float, context: ssl.SSLContext, fallback: str) -> str:
    request = Request(url, method="GET", headers={"User-Agent": "leadfinder/0.1"})
    try:
        with urlopen(request, timeout=timeout, context=context) as response:
            if 200 <= getattr(response, "status", 200) < 400:
                return fallback
    except (HTTPError, URLError, TimeoutError, ValueError, ssl.SSLError):
        return "unreachable"
    return "unreachable"


def analyze_lead_website(lead: Lead, *, probe: bool = True) -> Lead:
    if not lead.website:
        lead.website_status = "no_website"
        return lead
    lead.website_status = probe_url(lead.website) if probe else classify_url(lead.website)
    return lead
