from __future__ import annotations

from leadfinder.website import classify_url


def test_classifies_common_url_shapes() -> None:
    assert classify_url("") == "no_website"
    assert classify_url("https://instagram.com/example") == "social_only"
    assert classify_url("https://linktr.ee/example") == "link_aggregator"
    assert classify_url("http://example.test") == "non_https"
    assert classify_url("https://example.test") == "has_website"
