"""Superficial digital-presence checks. Not a crawler or security scanner.

Limits (documented, enforced):
- timeout: 5.0s per request (connect+read)
- max redirects: 5
- max body read: 256 KiB
- methods: HEAD, then GET if HEAD is missing/unusable
- no JavaScript, no asset downloads, no internal link following
"""

from __future__ import annotations

import logging
import ssl
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from enum import Enum
from html.parser import HTMLParser
from threading import Lock
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

from leadfinder.models import Lead, SearchProgress

LOGGER = logging.getLogger("leadfinder")

CONNECT_READ_TIMEOUT = 5.0
MAX_REDIRECTS = 5
MAX_BODY_BYTES = 256 * 1024
MAX_WORKERS = 4
USER_AGENT = "leadfinder/0.3 (digital-presence-check; not a crawler)"

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
        "l.facebook.com",
    }
)
AGGREGATOR_HOSTS = frozenset(
    {
        "linktr.ee",
        "linktree.com",
        "beacons.ai",
        "bio.link",
        "bio.site",
        "carrd.co",
        "tap.bio",
        "taplink.ai",
        "lnk.bio",
        "solo.to",
        "campsite.bio",
    }
)
PARKING_HOSTS = frozenset(
    {
        "sedoparking.com",
        "parkingcrew.net",
        "hugedomains.com",
        "afternic.com",
        "dan.com",
    }
)
PARKED_TITLE_PHRASES = (
    "domain for sale",
    "this domain is for sale",
    "domain is for sale",
    "buy this domain",
    "domain may be for sale",
    "parked domain",
    "this domain is parked",
)
WEAK_EXACT_TITLES = frozenset(
    {
        "home",
        "index",
        "welcome",
        "untitled",
        "new site",
        "default page",
        "apache2 ubuntu default page",
        "welcome to nginx",
        "iis windows server",
    }
)
SOCIAL_LABELS = {
    "instagram.com": "instagram",
    "facebook.com": "facebook",
    "fb.com": "facebook",
    "m.facebook.com": "facebook",
    "l.facebook.com": "facebook",
    "tiktok.com": "tiktok",
    "linkedin.com": "linkedin",
    "twitter.com": "twitter",
    "x.com": "twitter",
    "youtube.com": "youtube",
    "youtu.be": "youtube",
    "wa.me": "whatsapp",
    "api.whatsapp.com": "whatsapp",
}


class PresenceType(str, Enum):
    NO_WEBSITE = "no_website"
    WEBSITE = "website"
    SOCIAL = "social"
    LINK_AGGREGATOR = "link_aggregator"
    UNKNOWN = "unknown"


class HealthStatus(str, Enum):
    OK = "ok"
    UNREACHABLE = "unreachable"
    NON_HTTPS = "non_https"
    PARKED = "parked"
    WEAK = "weak"
    UNKNOWN = "unknown"
    NOT_APPLICABLE = "not_applicable"


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class DigitalPresenceResult:
    presence_type: PresenceType
    health: HealthStatus
    reachable: bool | None
    final_url: str
    https: bool | None
    social_platform: str
    link_aggregator: str
    title: str
    reason: str
    confidence: Confidence
    unreachable_reason: str = ""
    signals: tuple[str, ...] = ()
    from_cache: bool = False

    @property
    def category(self) -> str:
        if self.presence_type is PresenceType.NO_WEBSITE:
            return "no_website"
        if self.presence_type is PresenceType.SOCIAL:
            return "social_only"
        if self.presence_type is PresenceType.LINK_AGGREGATOR:
            return "link_aggregator"
        if self.health is HealthStatus.UNREACHABLE:
            return "unreachable"
        if self.health is HealthStatus.NON_HTTPS:
            return "non_https"
        if self.health is HealthStatus.PARKED:
            return "parked"
        if self.health is HealthStatus.WEAK:
            return "weak_website"
        if self.presence_type is PresenceType.WEBSITE and self.health is HealthStatus.OK:
            return "has_website"
        return "unknown"


@dataclass
class FetchResult:
    ok: bool
    status: int = 0
    final_url: str = ""
    body: bytes = b""
    error: str = ""
    truncated: bool = False


FetchFn = Callable[[str, str], FetchResult]
ProgressFn = Callable[[SearchProgress], None]
CancelFn = Callable[[], bool]


class _LimitedRedirectHandler(HTTPRedirectHandler):
    max_repeats = MAX_REDIRECTS
    max_redirs = MAX_REDIRECTS


class _HTMLSignals(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.viewport = False
        self.meta_description = ""
        self.texts: list[str] = []
        self._in_title = False
        self._skip = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = {key.lower(): (value or "") for key, value in attrs}
        if tag == "title":
            self._in_title = True
        if tag in {"script", "style", "noscript"}:
            self._skip += 1
        if tag == "meta":
            name = data.get("name", "").lower()
            if name == "viewport":
                self.viewport = True
            if name == "description":
                self.meta_description = data.get("content", "")

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if tag in {"script", "style", "noscript"} and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if self._skip:
            return
        if self._in_title:
            self.title += data
        else:
            text = data.strip()
            if text:
                self.texts.append(text)


def format_presence_report(result: DigitalPresenceResult) -> str:
    type_label = {
        PresenceType.NO_WEBSITE: "No website",
        PresenceType.WEBSITE: "Website",
        PresenceType.SOCIAL: "Social",
        PresenceType.LINK_AGGREGATOR: "Link aggregator",
        PresenceType.UNKNOWN: "Unknown",
    }[result.presence_type]
    if result.reachable is True:
        reachable = "yes"
    elif result.reachable is False:
        reachable = "no"
    else:
        reachable = "n/a"
    if result.https is True:
        https = "yes"
    elif result.https is False:
        https = "no"
    else:
        https = "n/a"
    skip = {"normal_website", "website_listed"}
    signals = ", ".join(item for item in result.signals if item not in skip) or "none"
    return (
        "Digital Presence\n"
        f"Type: {type_label}\n"
        f"Health: {result.health.value}\n"
        f"Reachable: {reachable}\n"
        f"HTTPS: {https}\n"
        f"Final URL: {result.final_url or '(none)'}\n"
        f"Opportunity signals: {signals}\n"
        f"{result.reason}"
    )


def hostname(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.netloc or parsed.path).lower()
    if host.startswith("www."):
        host = host[4:]
    return host.split(":")[0].split("/")[0]


def matches_host(url: str, hosts: frozenset[str]) -> str:
    host = hostname(url)
    for item in hosts:
        if host == item or host.endswith("." + item):
            return item
    return ""


def normalize_url(value: str) -> str:
    raw = value.strip()
    if not raw:
        return ""
    if raw.startswith("//"):
        raw = "https:" + raw
    parsed = urlparse(raw)
    if not parsed.scheme:
        raw = "https://" + raw.lstrip("/")
        parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    host = parsed.netloc
    return parsed._replace(netloc=host).geturl()


def classify_url(url: str) -> str:
    """Host-only classification. Does not perform HTTP."""
    return classify_presence(url).category


def classify_presence(url: str) -> DigitalPresenceResult:
    normalized = normalize_url(url)
    if not url.strip() or not normalized:
        if not url.strip():
            return DigitalPresenceResult(
                presence_type=PresenceType.NO_WEBSITE,
                health=HealthStatus.NOT_APPLICABLE,
                reachable=None,
                final_url="",
                https=None,
                social_platform="",
                link_aggregator="",
                title="",
                reason="No website listed in Google Places.",
                confidence=Confidence.HIGH,
                signals=("no_website",),
            )
        return DigitalPresenceResult(
            presence_type=PresenceType.UNKNOWN,
            health=HealthStatus.UNKNOWN,
            reachable=None,
            final_url=url.strip(),
            https=None,
            social_platform="",
            link_aggregator="",
            title="",
            reason="URL is missing or invalid.",
            confidence=Confidence.LOW,
            unreachable_reason="invalid_url",
            signals=("invalid_url",),
        )
    aggregator = matches_host(normalized, AGGREGATOR_HOSTS)
    if aggregator:
        return DigitalPresenceResult(
            presence_type=PresenceType.LINK_AGGREGATOR,
            health=HealthStatus.OK,
            reachable=None,
            final_url=normalized,
            https=normalized.startswith("https://"),
            social_platform="",
            link_aggregator=aggregator,
            title="",
            reason=f"Link-in-bio host ({aggregator}).",
            confidence=Confidence.HIGH,
            signals=("link_aggregator", aggregator),
        )
    social = matches_host(normalized, SOCIAL_HOSTS)
    if social:
        platform = SOCIAL_LABELS.get(social, social.split(".")[0])
        return DigitalPresenceResult(
            presence_type=PresenceType.SOCIAL,
            health=HealthStatus.OK,
            reachable=None,
            final_url=normalized,
            https=normalized.startswith("https://"),
            social_platform=platform,
            link_aggregator="",
            title="",
            reason=f"Social profile used as website ({platform}).",
            confidence=Confidence.HIGH,
            signals=("social_only", platform),
        )
    https = normalized.startswith("https://")
    return DigitalPresenceResult(
        presence_type=PresenceType.WEBSITE,
        health=HealthStatus.NON_HTTPS if not https else HealthStatus.OK,
        reachable=None,
        final_url=normalized,
        https=https,
        social_platform="",
        link_aggregator="",
        title="",
        reason="Website listed; not probed." if https else "Listed URL is HTTP, not HTTPS.",
        confidence=Confidence.LOW if https else Confidence.MEDIUM,
        signals=("http_only",) if not https else ("website_listed",),
    )


def _read_limited(response: object) -> tuple[bytes, bool]:
    chunks: list[bytes] = []
    total = 0
    truncated = False
    while total < MAX_BODY_BYTES:
        reader = getattr(response, "read", None)
        if reader is None:
            break
        chunk = reader(min(8192, MAX_BODY_BYTES - total))
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
    extra = getattr(response, "read", None)
    if extra is not None:
        leftover = extra(1)
        if leftover:
            truncated = True
    return b"".join(chunks), truncated


def _map_os_error(error: OSError) -> str:
    name = type(error).__name__.lower()
    text = str(error).lower()
    if "timed out" in text or "timeout" in name:
        return "timeout"
    if "name or service not known" in text or "getaddrinfo" in text or "nodename" in text:
        return "dns"
    if "refused" in text:
        return "refused"
    if "ssl" in name or "certificate" in text:
        return "tls"
    return "network"


def default_fetch(url: str, method: str) -> FetchResult:
    context = ssl.create_default_context()
    opener = build_opener(HTTPSHandler(context=context), _LimitedRedirectHandler)
    request = Request(url, method=method, headers={"User-Agent": USER_AGENT})
    try:
        with opener.open(request, timeout=CONNECT_READ_TIMEOUT) as response:
            status = int(getattr(response, "status", 200) or 200)
            final_url = str(getattr(response, "geturl", lambda: url)())
            body, truncated = _read_limited(response) if method == "GET" else (b"", False)
            if status >= 500:
                return FetchResult(ok=False, status=status, final_url=final_url, error="http_5xx")
            if status >= 400:
                return FetchResult(ok=False, status=status, final_url=final_url, error="http_4xx")
            return FetchResult(
                ok=True,
                status=status,
                final_url=final_url or url,
                body=body,
                truncated=truncated,
            )
    except HTTPError as error:
        if error.code in {405, 501} and method == "HEAD":
            raise
        final_url = str(getattr(error, "url", url) or url)
        if error.code >= 500:
            return FetchResult(ok=False, status=error.code, final_url=final_url, error="http_5xx")
        if error.code in {405, 501}:
            return FetchResult(
                ok=False, status=error.code, final_url=final_url, error="method_not_allowed"
            )
        return FetchResult(ok=False, status=error.code, final_url=final_url, error="http_4xx")
    except TimeoutError:
        return FetchResult(ok=False, final_url=url, error="timeout")
    except ssl.SSLError:
        return FetchResult(ok=False, final_url=url, error="tls")
    except URLError as error:
        reason = error.reason
        if isinstance(reason, OSError):
            return FetchResult(ok=False, final_url=url, error=_map_os_error(reason))
        text = str(reason).lower()
        if "timed out" in text:
            return FetchResult(ok=False, final_url=url, error="timeout")
        return FetchResult(
            ok=False,
            final_url=url,
            error="dns" if "not known" in text else "network",
        )
    except ValueError:
        return FetchResult(ok=False, final_url=url, error="invalid_url")


def _probe(url: str, fetch: FetchFn) -> FetchResult:
    try:
        head = fetch(url, "HEAD")
    except HTTPError as error:
        if error.code in {405, 501}:
            return fetch(url, "GET")
        raise
    if head.error == "method_not_allowed" or (not head.ok and head.status in {405, 501}):
        return fetch(url, "GET")
    if not head.ok:
        # One GET fallback for flaky HEAD implementations.
        get = fetch(url, "GET")
        if get.ok or get.error:
            return get
        return head
    get = fetch(url, "GET")
    if get.ok:
        return get
    # Reachable via HEAD even if GET failed; keep HEAD success with empty body.
    return FetchResult(
        ok=True,
        status=head.status,
        final_url=head.final_url or url,
        body=b"",
        error="",
    )


def _parse_html(body: bytes) -> _HTMLSignals:
    parser = _HTMLSignals()
    try:
        parser.feed(body.decode("utf-8", errors="ignore"))
        parser.close()
    except Exception:  # noqa: BLE001
        LOGGER.warning("HTML parse failed; keeping partial signals", exc_info=True)
        return parser
    return parser


def _word_count(texts: list[str]) -> int:
    return len(" ".join(texts).split())


def _parked_signals(final_url: str, title: str, visible: str) -> list[str]:
    signals: list[str] = []
    parking = matches_host(final_url, PARKING_HOSTS)
    if parking:
        signals.append(f"parking_host:{parking}")
    lowered_title = title.lower()
    lowered_visible = visible.lower()
    for phrase in PARKED_TITLE_PHRASES:
        if phrase in lowered_title:
            signals.append(f"parked_title:{phrase}")
        elif phrase in lowered_visible and "domain" in lowered_visible:
            signals.append(f"parked_body:{phrase}")
    return signals


def _weak_signals(title: str, viewport: bool, word_count: int, body_len: int) -> list[str]:
    signals: list[str] = []
    exact = title.strip().lower()
    if exact in WEAK_EXACT_TITLES:
        signals.append("generic_title")
    if not viewport:
        signals.append("no_viewport")
    if word_count < 40:
        signals.append("very_little_text")
    if body_len < 800:
        signals.append("tiny_html")
    return signals


def _friendly_unreachable(code: str) -> str:
    return {
        "timeout": "The site did not respond in time.",
        "dns": "The domain could not be resolved.",
        "refused": "The connection was refused.",
        "tls": "The HTTPS connection failed.",
        "http_5xx": "The server returned a persistent error.",
        "http_4xx": "The listed page was not found.",
        "redirects": "The site redirected too many times.",
        "invalid_url": "The listed URL is invalid.",
        "network": "The site could not be reached.",
    }.get(code, "The site could not be reached.")


class PresenceAnalyzer:
    """Session-scoped analyzer with in-memory URL cache. Does not persist HTML."""

    def __init__(self, fetch: FetchFn | None = None) -> None:
        self._fetch = fetch or default_fetch
        self._cache: dict[str, DigitalPresenceResult] = {}
        self._lock = Lock()
        self.fetch_calls = 0

    def analyze(self, url: str) -> DigitalPresenceResult:
        classified = classify_presence(url)
        if classified.presence_type in {
            PresenceType.NO_WEBSITE,
            PresenceType.SOCIAL,
            PresenceType.LINK_AGGREGATOR,
            PresenceType.UNKNOWN,
        }:
            return classified
        key = classified.final_url or normalize_url(url)
        with self._lock:
            cached = self._cache.get(key)
        if cached is not None:
            copy = DigitalPresenceResult(**{**cached.__dict__, "from_cache": True})
            return copy
        result = self._inspect_website(key)
        with self._lock:
            self._cache[key] = result
            self.fetch_calls += 1
        return result

    def _inspect_website(self, url: str) -> DigitalPresenceResult:
        fetched = _probe(url, self._fetch)
        if not fetched.ok:
            return DigitalPresenceResult(
                presence_type=PresenceType.WEBSITE,
                health=HealthStatus.UNREACHABLE,
                reachable=False,
                final_url=fetched.final_url or url,
                https=None,
                social_platform="",
                link_aggregator="",
                title="",
                reason=_friendly_unreachable(fetched.error),
                confidence=Confidence.MEDIUM,
                unreachable_reason=fetched.error or "network",
                signals=("unreachable", fetched.error),
            )
        final_url = fetched.final_url or url
        https = final_url.startswith("https://")
        parser = _parse_html(fetched.body)
        title = parser.title.strip()
        visible = " ".join(parser.texts)
        words = _word_count(parser.texts)
        if not fetched.body:
            if not https:
                return DigitalPresenceResult(
                    presence_type=PresenceType.WEBSITE,
                    health=HealthStatus.NON_HTTPS,
                    reachable=True,
                    final_url=final_url,
                    https=False,
                    social_platform="",
                    link_aggregator="",
                    title="",
                    reason="Site stays on HTTP after redirects.",
                    confidence=Confidence.HIGH,
                    signals=("http_only",),
                )
            return DigitalPresenceResult(
                presence_type=PresenceType.WEBSITE,
                health=HealthStatus.OK,
                reachable=True,
                final_url=final_url,
                https=True,
                social_platform="",
                link_aggregator="",
                title="",
                reason="A standalone website responded over HTTPS.",
                confidence=Confidence.LOW,
                signals=("normal_website", "html_not_downloaded"),
            )
        parked = _parked_signals(final_url, title, visible)
        # Conservatively require a parking host or two parked phrases.
        parked_phrases = [item for item in parked if item.startswith("parked_")]
        if matches_host(final_url, PARKING_HOSTS) or len(parked_phrases) >= 2:
            return DigitalPresenceResult(
                presence_type=PresenceType.WEBSITE,
                health=HealthStatus.PARKED,
                reachable=True,
                final_url=final_url,
                https=https,
                social_platform="",
                link_aggregator="",
                title=title,
                reason="Page looks like a domain placeholder or parking page.",
                confidence=Confidence.MEDIUM,
                signals=tuple(["parked", *parked]),
            )
        if not https:
            return DigitalPresenceResult(
                presence_type=PresenceType.WEBSITE,
                health=HealthStatus.NON_HTTPS,
                reachable=True,
                final_url=final_url,
                https=False,
                social_platform="",
                link_aggregator="",
                title=title,
                reason="Site stays on HTTP after redirects.",
                confidence=Confidence.HIGH,
                signals=("http_only",),
            )
        weak = _weak_signals(title, parser.viewport, words, len(fetched.body))
        strong_weak = {"generic_title", "very_little_text", "tiny_html"}
        weak_hits = [item for item in weak if item in strong_weak]
        if len(weak_hits) >= 2 and words < 80:
            return DigitalPresenceResult(
                presence_type=PresenceType.WEBSITE,
                health=HealthStatus.WEAK,
                reachable=True,
                final_url=final_url,
                https=True,
                social_platform="",
                link_aggregator="",
                title=title,
                reason="Very little commercial page content was detected.",
                confidence=Confidence.LOW,
                signals=tuple(["weak_website", *weak]),
            )
        return DigitalPresenceResult(
            presence_type=PresenceType.WEBSITE,
            health=HealthStatus.OK,
            reachable=True,
            final_url=final_url,
            https=True,
            social_platform="",
            link_aggregator="",
            title=title,
            reason="A standalone website responded over HTTPS.",
            confidence=Confidence.MEDIUM,
            signals=("normal_website",),
        )


def apply_presence(lead: Lead, result: DigitalPresenceResult) -> Lead:
    lead.website_status = result.category
    lead.presence_type = result.presence_type.value
    lead.website_health = result.health.value
    lead.final_url = result.final_url
    lead.presence_title = result.title
    lead.presence_signals = "; ".join(result.signals)
    lead.social_platform = result.social_platform
    if result.https is True:
        lead.https = "yes"
    elif result.https is False:
        lead.https = "no"
    else:
        lead.https = "unknown"
    if result.reachable is True:
        lead.reachable = "yes"
    elif result.reachable is False:
        lead.reachable = "no"
    else:
        lead.reachable = "unknown"
    return lead


def analyze_lead_website(
    lead: Lead,
    *,
    probe: bool = True,
    analyzer: PresenceAnalyzer | None = None,
) -> Lead:
    if not probe:
        return apply_presence(lead, classify_presence(lead.website))
    engine = analyzer or PresenceAnalyzer()
    return apply_presence(lead, engine.analyze(lead.website))


def analyze_leads(
    leads: list[Lead],
    *,
    analyzer: PresenceAnalyzer | None = None,
    probe: bool = True,
    max_workers: int = MAX_WORKERS,
    is_cancelled: CancelFn | None = None,
    on_progress: ProgressFn | None = None,
) -> list[Lead]:
    engine = analyzer or PresenceAnalyzer()
    workers = max(1, min(max_workers, 8))
    total = len(leads)
    done = 0

    def emit() -> None:
        if on_progress:
            on_progress(
                SearchProgress(
                    message=f"Analyzing websites {done} / {total}",
                    analyzed=done,
                    analyze_total=total,
                    leads_count=total,
                )
            )

    emit()
    if not leads:
        return leads

    def work(lead: Lead) -> Lead:
        return analyze_lead_website(lead, probe=probe, analyzer=engine)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(work, lead) for lead in leads]
        for future in as_completed(futures):
            if not future.cancelled():
                future.result()
                done += 1
                emit()
            if is_cancelled and is_cancelled():
                for pending in futures:
                    pending.cancel()
                break
    return leads


def derived_tags(lead: Lead) -> tuple[str, ...]:
    tags: list[str] = []
    if lead.website_status == "no_website":
        tags.append("no-web")
    if lead.website_status == "social_only":
        tags.append("social-only")
    if lead.website_status == "unreachable":
        tags.append("unreachable")
    if lead.website_status == "non_https":
        tags.append("http-only")
    if lead.opportunity_level == "high":
        tags.append("high-opportunity")
    return tuple(tags)
