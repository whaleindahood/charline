from datetime import datetime, timezone

import pytest

from charline.research import EvidenceError, normalize_evidence


NOW = datetime(2026, 8, 7, 12, 0, tzinfo=timezone.utc)


def test_fact_requires_verifiable_http_source():
    with pytest.raises(EvidenceError, match="source_url"):
        normalize_evidence(
            [{"kind": "fact", "claim": "A changed", "source_url": ""}],
            observed_at=NOW,
        )


def test_pack_is_deduplicated_sorted_and_explicitly_classified():
    findings = normalize_evidence(
        [
            {
                "kind": "inference",
                "claim": "Option B is likely safer",
                "source_url": "https://example.com/b",
            },
            {
                "kind": "fact",
                "claim": "Option A costs 10",
                "source_url": "https://example.com/a",
            },
            {
                "kind": "fact",
                "claim": "Option A costs 10",
                "source_url": "https://example.com/a",
            },
            {"kind": "uncertainty", "claim": "Migration duration is unknown"},
        ],
        observed_at=NOW,
    )

    assert [item["kind"] for item in findings] == [
        "fact",
        "inference",
        "uncertainty",
    ]
    assert len(findings) == 3
    assert findings[0]["observed_at"] == "2026-08-07T12:00:00+00:00"


def test_observed_at_must_be_timezone_aware():
    with pytest.raises(EvidenceError, match="timezone-aware"):
        normalize_evidence([], observed_at=datetime(2026, 8, 7, 12, 0))

