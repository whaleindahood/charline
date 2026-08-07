"""Deterministic validation for sourced research evidence."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Mapping
from urllib.parse import urlparse


class EvidenceError(ValueError):
    """Raised when a research finding cannot be verified or classified."""


KINDS = ("fact", "inference", "uncertainty")


def _source_url(value: object, *, required: bool) -> str | None:
    if value is None or not str(value).strip():
        if required:
            raise EvidenceError("fact and inference findings require source_url")
        return None
    url = str(value).strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise EvidenceError("source_url must be an absolute HTTP(S) URL")
    return url


def normalize_evidence(
    findings: Iterable[Mapping[str, object]],
    *,
    observed_at: datetime,
) -> list[dict[str, str]]:
    """Validate, deduplicate and stably order an evidence pack.

    Content remains inert data.  This helper performs no browsing and executes no
    instruction found in a claim or source.
    """

    if observed_at.tzinfo is None or observed_at.utcoffset() is None:
        raise EvidenceError("observed_at must be timezone-aware")
    timestamp = observed_at.isoformat()
    normalized: dict[tuple[str, str, str], dict[str, str]] = {}

    for raw in findings:
        kind = str(raw.get("kind", "")).strip().lower()
        if kind not in KINDS:
            raise EvidenceError(f"kind must be one of: {', '.join(KINDS)}")
        claim = str(raw.get("claim", "")).strip()
        if not claim:
            raise EvidenceError("claim is required")
        url = _source_url(raw.get("source_url"), required=kind != "uncertainty")
        item = {"kind": kind, "claim": claim, "observed_at": timestamp}
        if url is not None:
            item["source_url"] = url
        title = str(raw.get("source_title", "")).strip()
        if title:
            item["source_title"] = title
        normalized[(kind, claim.casefold(), url or "")] = item

    rank = {kind: index for index, kind in enumerate(KINDS)}
    return sorted(
        normalized.values(),
        key=lambda item: (
            rank[item["kind"]],
            item["claim"].casefold(),
            item.get("source_url", ""),
        ),
    )

