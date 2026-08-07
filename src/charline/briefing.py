"""Deterministic composition for read-only multi-source daily briefings."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


SECTION_ORDER = (
    "calendar",
    "gmail",
    "drive",
    "docs",
    "sheets",
    "research",
    "reminders",
    "developer",
)
SECTION_INDEX = {name: index for index, name in enumerate(SECTION_ORDER)}
STATUSES = {"ok", "empty", "unavailable"}


class BriefingValidationError(ValueError):
    pass


def _aware_timestamp(value: object, label: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise BriefingValidationError(f"{label} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise BriefingValidationError(f"{label} must be an ISO-8601 timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise BriefingValidationError(f"{label} must be timezone-aware")
    return parsed


def _json_copy(value: object, label: str) -> object:
    try:
        encoded = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as error:
        raise BriefingValidationError(f"{label} must contain deterministic JSON values") from error
    return json.loads(encoded)


def _item_sort_key(item: Mapping[str, object]) -> tuple[str, str, str]:
    timestamp = ""
    for field in ("start", "due", "timestamp", "published_at"):
        value = item.get(field)
        if isinstance(value, str):
            timestamp = value
            break
    canonical = json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return timestamp, str(item["handle"]), canonical


def _normalize_item(
    section_name: str,
    raw_item: object,
    *,
    item_index: int,
) -> dict[str, object]:
    if not isinstance(raw_item, Mapping):
        raise BriefingValidationError(f"{section_name}.items[{item_index}] must be an object")
    item = _json_copy(raw_item, f"{section_name}.items[{item_index}]")
    assert isinstance(item, dict)
    for field in ("handle", "title"):
        value = item.get(field)
        if not isinstance(value, str) or not value.strip():
            raise BriefingValidationError(
                f"{section_name}.items[{item_index}].{field} must be a non-empty string"
            )
        item[field] = value.strip()

    for field in ("start", "end", "due", "timestamp", "published_at"):
        if field in item:
            _aware_timestamp(item[field], f"{section_name}.items[{item_index}].{field}")

    if section_name == "calendar":
        start = _aware_timestamp(item.get("start"), f"calendar.items[{item_index}].start")
        end = _aware_timestamp(item.get("end"), f"calendar.items[{item_index}].end")
        if end <= start:
            raise BriefingValidationError(f"calendar.items[{item_index}] end must be after start")
    elif section_name == "research":
        url = item.get("url")
        if not isinstance(url, str) or not url.startswith(("https://", "http://")):
            raise BriefingValidationError(f"research.items[{item_index}].url must be an HTTP URL")
    elif section_name == "reminders" and "due" in item:
        if not isinstance(item.get("done", False), bool):
            raise BriefingValidationError(f"reminders.items[{item_index}].done must be boolean")
    return item


def _normalize_section(raw_section: object, index: int) -> dict[str, object]:
    if not isinstance(raw_section, Mapping):
        raise BriefingValidationError(f"sections[{index}] must be an object")
    name = raw_section.get("name")
    status = raw_section.get("status")
    if name not in SECTION_INDEX:
        raise BriefingValidationError(f"sections[{index}].name is not a supported V1 section")
    if status not in STATUSES:
        raise BriefingValidationError(f"sections[{index}].status is invalid")
    observed_at = raw_section.get("observed_at")
    _aware_timestamp(observed_at, f"sections[{index}].observed_at")
    raw_items = raw_section.get("items")
    if not isinstance(raw_items, list):
        raise BriefingValidationError(f"sections[{index}].items must be a list")
    if status != "ok" and raw_items:
        raise BriefingValidationError(f"{name} {status} section cannot contain items")
    error_code = raw_section.get("error_code")
    if status == "unavailable" and (
        not isinstance(error_code, str) or not error_code.strip()
    ):
        raise BriefingValidationError(f"{name} unavailable section requires error_code")

    normalized = [
        _normalize_item(str(name), item, item_index=item_index)
        for item_index, item in enumerate(raw_items)
    ]
    unique: dict[str, dict[str, object]] = {}
    for item in sorted(normalized, key=_item_sort_key):
        unique.setdefault(str(item["handle"]), item)
    return {
        "name": name,
        "status": status,
        "observed_at": observed_at,
        "error_code": error_code.strip() if isinstance(error_code, str) else None,
        "items": list(unique.values()),
    }


def _alerts(
    sections: list[dict[str, object]],
    *,
    generated_at: datetime,
) -> list[str]:
    alerts: list[str] = []
    for section in sections:
        name = str(section["name"])
        if section["status"] == "unavailable":
            alerts.append(f"source_unavailable:{name}:{section['error_code']}")

        items = section["items"]
        assert isinstance(items, list)
        if name == "calendar":
            ordered = sorted(items, key=lambda item: _aware_timestamp(item["start"], "start"))
            for left_index, left in enumerate(ordered):
                left_end = _aware_timestamp(left["end"], "end")
                for right in ordered[left_index + 1 :]:
                    right_start = _aware_timestamp(right["start"], "start")
                    if right_start >= left_end:
                        break
                    pair = sorted((str(left["handle"]), str(right["handle"])))
                    alerts.append(f"calendar_conflict:{pair[0]}:{pair[1]}")
        elif name == "reminders":
            for item in items:
                if item.get("done", False) or "due" not in item:
                    continue
                if _aware_timestamp(item["due"], "due") < generated_at:
                    alerts.append(f"overdue_reminder:{item['handle']}")
    return sorted(set(alerts))


def _render_markdown(result: Mapping[str, object]) -> str:
    lines = ["# Daily brief", "", f"Status: {result['status']}"]
    for section in result["sections"]:
        lines.extend(("", f"## {str(section['name']).title()} — {section['status']}"))
        items = section["items"]
        if not items:
            lines.append("- No items")
        for item in items:
            title = str(item["title"]).replace("\r", " ").replace("\n", " ")
            lines.append(f"- {title} [{item['handle']}]")
    if result["alerts"]:
        lines.extend(("", "## Alerts"))
        lines.extend(f"- {alert}" for alert in result["alerts"])
    return "\n".join(lines)


def compose_daily_brief(snapshot: Mapping[str, object]) -> dict[str, object]:
    """Validate and compose normalized source snapshots without side effects."""
    if not isinstance(snapshot, Mapping):
        raise BriefingValidationError("snapshot must be an object")
    generated_at = _aware_timestamp(snapshot.get("generated_at"), "generated_at")
    timezone_name = snapshot.get("timezone")
    if not isinstance(timezone_name, str) or not timezone_name:
        raise BriefingValidationError("timezone must be an IANA timezone")
    try:
        timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as error:
        raise BriefingValidationError("timezone must be an IANA timezone") from error
    generated_at = generated_at.astimezone(timezone)

    raw_sections = snapshot.get("sections")
    if not isinstance(raw_sections, list):
        raise BriefingValidationError("sections must be a list")
    sections = [_normalize_section(section, index) for index, section in enumerate(raw_sections)]
    names = [section["name"] for section in sections]
    if len(names) != len(set(names)):
        raise BriefingValidationError("section names must be unique")
    sections.sort(key=lambda section: SECTION_INDEX[str(section["name"])])

    unavailable = sum(section["status"] == "unavailable" for section in sections)
    if not sections:
        status = "empty"
    elif unavailable == len(sections):
        status = "unavailable"
    elif unavailable:
        status = "partial"
    else:
        status = "ok"

    result: dict[str, object] = {
        "generated_at": generated_at.isoformat(),
        "timezone": timezone_name,
        "status": status,
        "sections": sections,
        "alerts": _alerts(sections, generated_at=generated_at),
    }
    result["markdown"] = _render_markdown(result)
    return result
