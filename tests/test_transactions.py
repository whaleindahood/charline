import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from charline.transactions import (
    ConfirmationMismatch,
    InvalidTransition,
    OperationDraft,
    TransactionPhase,
    WriteTransaction,
    authorize_write,
    compare_read_back,
)


class TransactionContractTests(unittest.TestCase):
    def test_preview_digest_is_stable_for_equivalent_payload_order(self):
        first = OperationDraft(
            service="gmail",
            action="send",
            account="primary",
            target="person@example.com",
            operation_id="mail-1",
            payload={"subject": "Status", "body": "Done"},
            effect="Send one email",
            critical_fields=("subject", "body"),
        )
        second = OperationDraft(
            service="gmail",
            action="send",
            account="primary",
            target="person@example.com",
            operation_id="mail-1",
            payload={"body": "Done", "subject": "Status"},
            effect="Send one email",
            critical_fields=("subject", "body"),
        )
        self.assertEqual(first.digest, second.digest)

    def test_changed_latest_preview_invalidates_confirmation(self):
        original = OperationDraft(
            service="calendar",
            action="create",
            account="primary",
            target="primary",
            operation_id="event-1",
            payload={"title": "Review", "start": "2026-08-10T15:00:00+03:00"},
            effect="Create one event",
            critical_fields=("title", "start"),
        )
        changed = OperationDraft(
            service="calendar",
            action="create",
            account="primary",
            target="primary",
            operation_id="event-1",
            payload={"title": "Review", "start": "2026-08-10T16:00:00+03:00"},
            effect="Create one event",
            critical_fields=("title", "start"),
        )
        with self.assertRaisesRegex(ConfirmationMismatch, "latest exact preview"):
            authorize_write(
                changed,
                confirmed_digest=original.digest,
                idempotency_key="calendar:create:review:2026-08-10T16:00+03:00",
            )

    def test_authorization_requires_nonempty_idempotency_key(self):
        draft = OperationDraft(
            service="drive",
            action="share",
            account="primary",
            target="file-123",
            operation_id="share-1",
            payload={"recipient": "person@example.com", "role": "reader"},
            effect="Grant read access",
            critical_fields=("recipient", "role"),
        )
        with self.assertRaisesRegex(ValueError, "idempotency_key"):
            authorize_write(draft, confirmed_digest=draft.digest, idempotency_key=" ")

    def test_read_back_reports_only_critical_field_mismatches(self):
        mismatches = compare_read_back(
            expected={"title": "Review", "start": "15:00", "server_note": None},
            observed={"title": "Review", "start": "16:00", "server_note": "generated"},
            critical_fields=("title", "start"),
        )
        self.assertEqual(mismatches, {"start": {"expected": "15:00", "observed": "16:00"}})

    def test_full_transaction_reaches_verified_only_after_read_back(self):
        draft = OperationDraft(
            service="sheets",
            action="update",
            account="primary",
            target="sheet-1:Tasks!A2:B2",
            operation_id="sheet-update-1",
            payload={"range": "Tasks!A2:B2", "values": [["Done", True]]},
            effect="Update one row",
            critical_fields=("range", "values"),
            preconditions={"revision": "17"},
        )
        transaction = WriteTransaction(draft).preview().confirm(draft.digest)
        transaction = transaction.revalidate({"revision": "17"})
        transaction = transaction.start_write("sheets:sheet-update-1")
        transaction = transaction.record_result("updated-range:Tasks!A2:B2")
        transaction = transaction.verify({"range": "Tasks!A2:B2", "values": [["Done", True]]})
        self.assertEqual(transaction.phase, TransactionPhase.VERIFIED)

    def test_write_cannot_start_before_revalidation(self):
        draft = OperationDraft(
            service="docs",
            action="append",
            account="primary",
            target="doc-1",
            operation_id="doc-append-1",
            payload={"text": "Approved"},
            effect="Append one paragraph",
            critical_fields=("text",),
        )
        transaction = WriteTransaction(draft).preview().confirm(draft.digest)
        with self.assertRaisesRegex(InvalidTransition, "CONFIRMED"):
            transaction.start_write("docs:doc-append-1")

    def test_unknown_write_outcome_requires_reconciliation(self):
        draft = OperationDraft(
            service="gmail",
            action="send",
            account="primary",
            target="person@example.com",
            operation_id="mail-unknown-1",
            payload={"subject": "Status", "body": "Done"},
            effect="Send one email",
            critical_fields=("subject", "body"),
        )
        transaction = (
            WriteTransaction(draft)
            .preview()
            .confirm(draft.digest)
            .revalidate({})
            .start_write("gmail:mail-unknown-1")
            .record_unknown()
        )
        with self.assertRaisesRegex(InvalidTransition, "UNKNOWN"):
            transaction.start_write("gmail:mail-unknown-1")
        self.assertEqual(transaction.reconcile_absent().phase, TransactionPhase.PROVEN_ABSENT)


if __name__ == "__main__":
    unittest.main()
