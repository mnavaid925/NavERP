"""CSV import tests for the bank_transaction_import_csv view.

Covers:
- Valid 3-row CSV → 3 BankTransactions created (source=csv_import).
- Re-POST same CSV → 0 new rows (idempotent on external_ref).
- Malformed row (bad amount) → skipped, no 500 / no exception.
- .txt upload → form invalid (clean_csv_file rejects non-.csv files).
"""
import datetime
import io
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

pytestmark = pytest.mark.django_db


def _make_csv(rows):
    """Build a bytes CSV from a list of dicts."""
    import csv as csv_mod
    buf = io.StringIO()
    if rows:
        writer = csv_mod.DictWriter(buf, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    return buf.getvalue().encode("utf-8")


VALID_ROWS = [
    {"date": "2026-01-10", "description": "Client payment", "amount": "500.00",
     "direction": "credit", "external_ref": "REF-001"},
    {"date": "2026-01-11", "description": "Supplier invoice", "amount": "200.00",
     "direction": "debit", "external_ref": "REF-002"},
    {"date": "2026-01-12", "description": "Utility bill", "amount": "75.50",
     "direction": "debit", "external_ref": "REF-003"},
]


class TestBankTransactionCSVImport:
    def _post_csv(self, client, bank_account, csv_bytes, filename="import.csv"):
        url = reverse("accounting:bank_transaction_import_csv")
        upload = SimpleUploadedFile(filename, csv_bytes, content_type="text/csv")
        return client.post(url, {"bank_account": bank_account.pk, "csv_file": upload})

    def test_valid_csv_creates_three_transactions(self, client_a, bank_account):
        from apps.accounting.models import BankTransaction
        before = BankTransaction.objects.filter(tenant=bank_account.tenant).count()

        csv_bytes = _make_csv(VALID_ROWS)
        resp = self._post_csv(client_a, bank_account, csv_bytes)

        assert resp.status_code == 302
        after = BankTransaction.objects.filter(tenant=bank_account.tenant).count()
        assert after - before == 3

    def test_valid_csv_transactions_have_csv_import_source(self, client_a, bank_account):
        from apps.accounting.models import BankTransaction
        csv_bytes = _make_csv(VALID_ROWS)
        self._post_csv(client_a, bank_account, csv_bytes)

        txns = BankTransaction.objects.filter(
            tenant=bank_account.tenant,
            source="csv_import",
        )
        assert txns.count() == 3

    def test_repost_same_csv_is_idempotent(self, client_a, bank_account):
        """Second POST with same external_refs creates 0 new transactions."""
        from apps.accounting.models import BankTransaction
        csv_bytes = _make_csv(VALID_ROWS)
        self._post_csv(client_a, bank_account, csv_bytes)

        before = BankTransaction.objects.filter(tenant=bank_account.tenant).count()
        # Post the same CSV again
        self._post_csv(client_a, bank_account, csv_bytes)
        after = BankTransaction.objects.filter(tenant=bank_account.tenant).count()
        assert after == before  # no new rows

    def test_malformed_row_skipped_no_500(self, client_a, bank_account):
        """A row with an invalid amount is skipped; the rest are imported; no 500."""
        from apps.accounting.models import BankTransaction
        rows = [
            {"date": "2026-01-20", "description": "Good row", "amount": "100.00",
             "direction": "credit", "external_ref": "GOOD-001"},
            {"date": "2026-01-21", "description": "Bad row", "amount": "not-a-number",
             "direction": "credit", "external_ref": "BAD-001"},
        ]
        csv_bytes = _make_csv(rows)
        resp = self._post_csv(client_a, bank_account, csv_bytes)

        # Must not be a 500
        assert resp.status_code != 500
        # Should redirect (success or validation error handled gracefully)
        assert resp.status_code in (200, 302)

        # Only the valid row imported
        txn = BankTransaction.objects.filter(
            tenant=bank_account.tenant, external_ref="GOOD-001"
        ).first()
        assert txn is not None
        bad = BankTransaction.objects.filter(
            tenant=bank_account.tenant, external_ref="BAD-001"
        ).first()
        assert bad is None

    def test_txt_upload_form_invalid(self, client_a, bank_account):
        """Uploading a .txt file must fail form validation — not imported."""
        from apps.accounting.models import BankTransaction
        before = BankTransaction.objects.filter(tenant=bank_account.tenant).count()

        txt_bytes = b"some text content"
        resp = self._post_csv(client_a, bank_account, txt_bytes, filename="data.txt")

        # Form should be re-rendered (200) with validation error or redirect — never a 500
        assert resp.status_code != 500
        # No new transactions
        after = BankTransaction.objects.filter(tenant=bank_account.tenant).count()
        assert after == before

    def test_missing_date_row_skipped(self, client_a, bank_account):
        """A row with an unparseable date is skipped gracefully."""
        from apps.accounting.models import BankTransaction
        rows = [
            {"date": "NOT-A-DATE", "description": "Bad date", "amount": "50.00",
             "direction": "credit", "external_ref": "DATE-001"},
        ]
        csv_bytes = _make_csv(rows)
        resp = self._post_csv(client_a, bank_account, csv_bytes)
        assert resp.status_code != 500
        assert not BankTransaction.objects.filter(
            tenant=bank_account.tenant, external_ref="DATE-001"
        ).exists()
