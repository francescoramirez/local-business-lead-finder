from __future__ import annotations

from leadfinder.digital_presence import (
    FetchResult,
    PresenceAnalyzer,
    analyze_lead_website,
    analyze_leads,
    classify_url,
    normalize_url,
)
from leadfinder.normalize import place_to_lead
from leadfinder.scoring import score_lead
from tests.conftest import synthetic_place

NORMAL_HTML = """
<html><head>
<title>Harbor Cafe — Mar del Plata</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Coffee, pastry, and brunch in the harbor.">
</head><body>
<h1>Welcome to Harbor Cafe</h1>
<p>Come in for espresso, medialunas, and weekend brunch.</p>
<p>Our seasonal menu is coming soon with new pastries.</p>
<p>Spring sale on coffee beans for regulars.</p>
<p>Contact us on the phone listed in Google Maps.</p>
<p>We roast weekly and host acoustic nights on Fridays.</p>
<p>Indoor seating, takeaway, and a small courtyard.</p>
</body></html>
"""

PARKED_HTML = """
<html><head><title>This domain is for sale</title></head>
<body><h1>This domain is for sale</h1>
<p>Buy this domain today from the parking provider.</p>
</body></html>
"""

WEAK_HTML = """
<html><head><title>Welcome</title></head>
<body>ok</body></html>
"""


def _lead(place_id: str, website: str):
    return place_to_lead(
        synthetic_place(
            place_id,
            "Cafe",
            website=website,
            phone="+54 11 0000",
            user_rating_count=20,
        ),
        source_query="cafe en Example City",
        location="Example City",
        search_term="cafe",
        business_preset="cafe",
        place_type="cafe",
        country="AR",
        region="",
    )


def _ok(url: str, body: str = NORMAL_HTML) -> FetchResult:
    return FetchResult(ok=True, status=200, final_url=url, body=body.encode("utf-8"))


def test_normalizes_common_url_shapes() -> None:
    assert normalize_url("example.com") == "https://example.com"
    assert normalize_url("www.example.com/path") == "https://www.example.com/path"
    assert normalize_url("http://example.com") == "http://example.com"
    assert normalize_url("https://example.com") == "https://example.com"
    assert normalize_url("") == ""


def test_classifies_common_url_shapes() -> None:
    assert classify_url("") == "no_website"
    assert classify_url("https://instagram.com/example") == "social_only"
    assert classify_url("https://linktr.ee/example") == "link_aggregator"
    assert classify_url("http://example.test") == "non_https"
    assert classify_url("https://example.test") == "has_website"


def test_http_to_https_redirect_is_not_non_https() -> None:
    def fetch(url: str, method: str) -> FetchResult:
        return _ok("https://cafe.test/", NORMAL_HTML)

    result = PresenceAnalyzer(fetch=fetch).analyze("http://cafe.test")
    assert result.category == "has_website"
    assert result.https is True
    assert result.health.value == "ok"


def test_http_only_stays_non_https() -> None:
    def fetch(url: str, method: str) -> FetchResult:
        return _ok("http://plain.test/", NORMAL_HTML)

    result = PresenceAnalyzer(fetch=fetch).analyze("http://plain.test")
    assert result.category == "non_https"
    assert result.https is False


def test_social_and_aggregator_skip_http() -> None:
    calls: list[tuple[str, str]] = []

    def fetch(url: str, method: str) -> FetchResult:
        calls.append((url, method))
        return _ok(url)

    analyzer = PresenceAnalyzer(fetch=fetch)
    social = analyzer.analyze("https://instagram.com/harbor")
    agg = analyzer.analyze("https://beacons.ai/harbor")
    assert social.category == "social_only"
    assert social.social_platform == "instagram"
    assert agg.category == "link_aggregator"
    assert calls == []


def test_unreachable_reasons() -> None:
    def timeout(url: str, method: str) -> FetchResult:
        return FetchResult(ok=False, error="timeout", final_url=url)

    def boom(url: str, method: str) -> FetchResult:
        return FetchResult(ok=False, status=503, error="http_5xx", final_url=url)

    timed = PresenceAnalyzer(fetch=timeout).analyze("https://down.test")
    server = PresenceAnalyzer(fetch=boom).analyze("https://error.test")
    assert timed.category == "unreachable"
    assert timed.unreachable_reason == "timeout"
    assert server.unreachable_reason == "http_5xx"


def test_redirect_limit_is_unreachable() -> None:
    def fetch(url: str, method: str) -> FetchResult:
        return FetchResult(ok=False, error="redirects", final_url=url)

    result = PresenceAnalyzer(fetch=fetch).analyze("https://loop.test")
    assert result.category == "unreachable"
    assert result.unreachable_reason == "redirects"


def test_parked_requires_strong_signals() -> None:
    def fetch(url: str, method: str) -> FetchResult:
        return _ok(url, PARKED_HTML)

    result = PresenceAnalyzer(fetch=fetch).analyze("https://forsale.test")
    assert result.category == "parked"


def test_false_positive_words_are_not_parked_or_weak() -> None:
    def fetch(url: str, method: str) -> FetchResult:
        return _ok(url, NORMAL_HTML)

    result = PresenceAnalyzer(fetch=fetch).analyze("https://harborcafe.test")
    assert result.category == "has_website"
    assert result.health.value == "ok"


def test_weak_website_needs_multiple_signals() -> None:
    def fetch(url: str, method: str) -> FetchResult:
        return _ok(url, WEAK_HTML)

    result = PresenceAnalyzer(fetch=fetch).analyze("https://thin.test")
    assert result.category == "weak_website"


def test_head_405_falls_back_to_get() -> None:
    calls: list[str] = []

    def fetch(url: str, method: str) -> FetchResult:
        calls.append(method)
        if method == "HEAD":
            return FetchResult(ok=False, status=405, error="method_not_allowed", final_url=url)
        return _ok(url, NORMAL_HTML)

    result = PresenceAnalyzer(fetch=fetch).analyze("https://getonly.test")
    assert result.category == "has_website"
    assert calls == ["HEAD", "GET"]


def test_in_memory_dedupe_skips_second_fetch() -> None:
    calls: list[str] = []

    def fetch(url: str, method: str) -> FetchResult:
        calls.append(method)
        return _ok(url, NORMAL_HTML)

    analyzer = PresenceAnalyzer(fetch=fetch)
    first = analyzer.analyze("https://cafe.test")
    second = analyzer.analyze("https://cafe.test")
    assert first.category == "has_website"
    assert second.from_cache is True
    assert calls == ["HEAD", "GET"]


def test_body_size_limit_does_not_raise() -> None:
    huge = b"<html><head><title>Harbor Cafe</title></head><body>" + (b"coffee " * 50000)

    def fetch(url: str, method: str) -> FetchResult:
        return FetchResult(
            ok=True,
            status=200,
            final_url=url,
            body=huge[: 256 * 1024],
            truncated=True,
        )

    result = PresenceAnalyzer(fetch=fetch).analyze("https://big.test")
    assert result.presence_type.value == "website"


def test_analyze_leads_honors_cancel() -> None:
    seen: list[str] = []

    def fetch(url: str, method: str) -> FetchResult:
        seen.append(url)
        return _ok(url, NORMAL_HTML)

    analyzer = PresenceAnalyzer(fetch=fetch)
    leads = [
        _lead("ChIJ_SYNTHETIC_401", "https://one.test"),
        _lead("ChIJ_SYNTHETIC_402", "https://two.test"),
        _lead("ChIJ_SYNTHETIC_403", "https://three.test"),
    ]

    def cancelled() -> bool:
        return len({item.split("/")[2] for item in seen}) >= 1

    analyze_leads(leads, analyzer=analyzer, max_workers=1, is_cancelled=cancelled)
    hosts = {item.split("/")[2] for item in seen}
    assert len(hosts) < 3


def test_apply_presence_then_score() -> None:
    def fetch(url: str, method: str) -> FetchResult:
        return _ok(url, NORMAL_HTML)

    analyzer = PresenceAnalyzer(fetch=fetch)
    lead = analyze_lead_website(_lead("ChIJ_SYNTHETIC_404", "https://ok.test"), analyzer=analyzer)
    scored = score_lead(lead)
    assert scored.website_status == "has_website"
    assert scored.opportunity_level == "low"
    assert scored.digital_opportunity_score == 0
