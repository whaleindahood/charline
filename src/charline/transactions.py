"""Deterministic transaction contracts for confirmed external writes."""

from __future__ import annotations

import hmac
import json
from dataclasses import dataclass, field, replace
from enum import Enum
from hashlib import sha256
from typing import Iterable, Mapping


class ConfirmationMismatch(ValueError):
    """Raised when confirmation does not match the latest exact preview."""


class PreconditionMismatch(ValueError):
    """Raised when source state changed after preview/confirmation."""


class ReadBackMismatch(ValueError):
    """Raised when returned resource differs from confirmed critical fields."""


class InvalidTransition(RuntimeError):
    """Raised when transaction phases are attempted out of order."""


def _canonical_json(value: object, *, label: str) -> str:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} must contain deterministic JSON values: {error}") from error


@dataclass(frozen=True, init=False)
class OperationDraft:
    """Immutable canonical preview shared by all external-write domains."""

    service: str
    action: str
    account: str
    target: str
    operation_id: str
    effect: str
    critical_fields: tuple[str, ...]
    _payload_json: str = field(repr=False)
    _preconditions_json: str = field(repr=False)

    def __init__(
        self,
        *,
        service: str,
        action: str,
        account: str,
        target: str,
        operation_id: str,
        payload: Mapping[str, object],
        effect: str,
        critical_fields: Iterable[str],
        preconditions: Mapping[str, object] | None = None,
    ) -> None:
        values = {
            "service": service,
            "action": action,
            "account": account,
            "target": target,
            "operation_id": operation_id,
            "effect": effect,
        }
        for label, value in values.items():
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{label} must be a non-empty string")
        if not isinstance(payload, Mapping):
            raise TypeError("payload must be a mapping")
        if preconditions is not None and not isinstance(preconditions, Mapping):
            raise TypeError("preconditions must be a mapping")
        fields = tuple(critical_fields)
        if not fields or any(not isinstance(name, str) or not name.strip() for name in fields):
            raise ValueError("critical_fields must contain non-empty strings")
        if len(set(fields)) != len(fields):
            raise ValueError("critical_fields cannot contain duplicates")

        payload_json = _canonical_json(payload, label="payload")
        preconditions_json = _canonical_json(preconditions or {}, label="preconditions")

        for label, value in values.items():
            object.__setattr__(self, label, value.strip())
        object.__setattr__(self, "critical_fields", fields)
        object.__setattr__(self, "_payload_json", payload_json)
        object.__setattr__(self, "_preconditions_json", preconditions_json)

    @property
    def payload(self) -> dict[str, object]:
        """Return a defensive copy of the canonical payload."""
        return json.loads(self._payload_json)

    @property
    def preconditions(self) -> dict[str, object]:
        return json.loads(self._preconditions_json)

    @property
    def canonical_preview(self) -> str:
        return json.dumps(
            {
                "account": self.account,
                "action": self.action,
                "effect": self.effect,
                "critical_fields": self.critical_fields,
                "operation_id": self.operation_id,
                "payload": self.payload,
                "preconditions": self.preconditions,
                "schema_version": 1,
                "service": self.service,
                "target": self.target,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    @property
    def digest(self) -> str:
        return sha256(self.canonical_preview.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class WriteAuthorization:
    preview_digest: str
    idempotency_key: str


class TransactionPhase(str, Enum):
    DRAFT = "DRAFT"
    PREVIEWED = "PREVIEWED"
    CONFIRMED = "CONFIRMED"
    REVALIDATED = "REVALIDATED"
    WRITE_STARTED = "WRITE_STARTED"
    WRITE_RETURNED = "WRITE_RETURNED"
    UNKNOWN = "UNKNOWN"
    PROVEN_ABSENT = "PROVEN_ABSENT"
    VERIFIED = "VERIFIED"


@dataclass(frozen=True)
class WriteTransaction:
    """Pure session-local state machine; persistence remains owned by Hermes."""

    draft: OperationDraft
    phase: TransactionPhase = TransactionPhase.DRAFT
    confirmed_digest: str | None = None
    idempotency_key: str | None = None
    resource_handle: str | None = None

    def _require(self, expected: TransactionPhase) -> None:
        if self.phase is not expected:
            raise InvalidTransition(
                f"{self.phase.value} transaction cannot perform an operation requiring {expected.value}"
            )

    def preview(self) -> WriteTransaction:
        self._require(TransactionPhase.DRAFT)
        return replace(self, phase=TransactionPhase.PREVIEWED)

    def confirm(self, confirmed_digest: str) -> WriteTransaction:
        self._require(TransactionPhase.PREVIEWED)
        if not isinstance(confirmed_digest, str) or not hmac.compare_digest(
            self.draft.digest, confirmed_digest
        ):
            raise ConfirmationMismatch("confirmation does not match the latest exact preview")
        return replace(
            self,
            phase=TransactionPhase.CONFIRMED,
            confirmed_digest=confirmed_digest,
        )

    def revalidate(self, current_preconditions: Mapping[str, object]) -> WriteTransaction:
        self._require(TransactionPhase.CONFIRMED)
        current = _canonical_json(current_preconditions, label="current_preconditions")
        if current != self.draft._preconditions_json:
            raise PreconditionMismatch("source preconditions changed after confirmation")
        return replace(self, phase=TransactionPhase.REVALIDATED)

    def start_write(self, idempotency_key: str) -> WriteTransaction:
        self._require(TransactionPhase.REVALIDATED)
        authorization = authorize_write(
            self.draft,
            confirmed_digest=self.confirmed_digest or "",
            idempotency_key=idempotency_key,
        )
        return replace(
            self,
            phase=TransactionPhase.WRITE_STARTED,
            idempotency_key=authorization.idempotency_key,
        )

    def record_result(self, resource_handle: str) -> WriteTransaction:
        self._require(TransactionPhase.WRITE_STARTED)
        if not isinstance(resource_handle, str) or not resource_handle.strip():
            raise ValueError("resource_handle must be a non-empty string")
        return replace(
            self,
            phase=TransactionPhase.WRITE_RETURNED,
            resource_handle=resource_handle.strip(),
        )

    def record_unknown(self) -> WriteTransaction:
        self._require(TransactionPhase.WRITE_STARTED)
        return replace(self, phase=TransactionPhase.UNKNOWN)

    def reconcile_found(self, resource_handle: str) -> WriteTransaction:
        self._require(TransactionPhase.UNKNOWN)
        if not isinstance(resource_handle, str) or not resource_handle.strip():
            raise ValueError("resource_handle must be a non-empty string")
        return replace(
            self,
            phase=TransactionPhase.WRITE_RETURNED,
            resource_handle=resource_handle.strip(),
        )

    def reconcile_absent(self) -> WriteTransaction:
        self._require(TransactionPhase.UNKNOWN)
        return replace(self, phase=TransactionPhase.PROVEN_ABSENT)

    def verify(self, observed: Mapping[str, object]) -> WriteTransaction:
        self._require(TransactionPhase.WRITE_RETURNED)
        mismatches = compare_read_back(
            expected=self.draft.payload,
            observed=observed,
            critical_fields=self.draft.critical_fields,
        )
        if mismatches:
            raise ReadBackMismatch(f"critical read-back mismatch: {mismatches}")
        return replace(self, phase=TransactionPhase.VERIFIED)


def authorize_write(
    draft: OperationDraft,
    *,
    confirmed_digest: str,
    idempotency_key: str,
) -> WriteAuthorization:
    """Authorize one write only when confirmation matches the latest draft."""
    if not isinstance(confirmed_digest, str) or not hmac.compare_digest(
        draft.digest, confirmed_digest
    ):
        raise ConfirmationMismatch("confirmation does not match the latest exact preview")
    if not isinstance(idempotency_key, str) or not idempotency_key.strip():
        raise ValueError("idempotency_key must be a non-empty string")
    return WriteAuthorization(draft.digest, idempotency_key.strip())


def compare_read_back(
    *,
    expected: Mapping[str, object],
    observed: Mapping[str, object],
    critical_fields: Iterable[str],
) -> dict[str, dict[str, object]]:
    """Return critical field mismatches; an empty result verifies the write."""
    mismatches: dict[str, dict[str, object]] = {}
    for field_name in critical_fields:
        expected_value = expected.get(field_name)
        observed_value = observed.get(field_name)
        if expected_value != observed_value:
            mismatches[field_name] = {
                "expected": expected_value,
                "observed": observed_value,
            }
    return mismatches
