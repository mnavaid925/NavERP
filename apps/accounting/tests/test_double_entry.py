"""Double-entry invariant tests for the Accounting module.

Covers:
- Posting a balanced draft JE → status=posted, posted_at set.
- Posting an unbalanced JE → stays draft, rejected.
- Posting a zero-total JE → rejected.
- Posting into a closed FiscalPeriod → rejected.
- journal_entry_void → original void, reversal JE exists with swapped lines, ledger balanced.
- Posted JE immutability: GET edit → 302; POST delete → not deleted.
- GLAccount.balance() only counts posted lines (draft lines excluded).
"""
import datetime
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.django_db


# ================================================================ Post balanced JE
class TestJournalEntryPost:
    def test_post_balanced_je_sets_status_and_posted_at(self, client_a, draft_je, tenant_a, admin_user):
        """Posting a balanced draft JE via the view sets status=posted and posted_at."""
        url = reverse("accounting:journal_entry_post", args=[draft_je.pk])
        resp = client_a.post(url)
        # Should redirect to detail after success
        assert resp.status_code == 302
        draft_je.refresh_from_db()
        assert draft_je.status == "posted"
        assert draft_je.posted_at is not None

    def test_post_unbalanced_je_stays_draft(self, client_a, tenant_a, admin_user, open_period, gl_cash, gl_income):
        """An unbalanced JE must not be posted — stays draft."""
        from apps.accounting.models import JournalEntry, JournalLine
        je = JournalEntry.objects.create(
            tenant=tenant_a, entry_type="manual", status="draft",
            fiscal_period=open_period, entry_date=datetime.date(2026, 1, 15),
            description="Unbalanced JE", created_by=admin_user,
        )
        JournalLine.objects.create(entry=je, gl_account=gl_cash, debit=Decimal("100.00"), credit=Decimal("0.00"))
        JournalLine.objects.create(entry=je, gl_account=gl_income, debit=Decimal("0.00"), credit=Decimal("50.00"))

        url = reverse("accounting:journal_entry_post", args=[je.pk])
        resp = client_a.post(url)
        # Redirect back to detail (rejected)
        assert resp.status_code == 302
        je.refresh_from_db()
        assert je.status == "draft"
        assert je.posted_at is None

    def test_post_zero_total_je_stays_draft(self, client_a, tenant_a, admin_user, open_period, gl_cash, gl_income):
        """A zero-total JE (no lines) must be rejected."""
        from apps.accounting.models import JournalEntry
        je = JournalEntry.objects.create(
            tenant=tenant_a, entry_type="manual", status="draft",
            fiscal_period=open_period, entry_date=datetime.date(2026, 1, 15),
            description="Zero JE", created_by=admin_user,
        )
        url = reverse("accounting:journal_entry_post", args=[je.pk])
        resp = client_a.post(url)
        assert resp.status_code == 302
        je.refresh_from_db()
        assert je.status == "draft"

    def test_post_into_closed_period_rejected(self, client_a, tenant_a, admin_user, closed_period, gl_cash, gl_income):
        """Posting a JE into a closed FiscalPeriod must be rejected."""
        from apps.accounting.models import JournalEntry, JournalLine
        je = JournalEntry.objects.create(
            tenant=tenant_a, entry_type="manual", status="draft",
            fiscal_period=closed_period, entry_date=datetime.date(2025, 12, 20),
            description="Closed period JE", created_by=admin_user,
        )
        JournalLine.objects.create(entry=je, gl_account=gl_cash, debit=Decimal("200.00"), credit=Decimal("0.00"))
        JournalLine.objects.create(entry=je, gl_account=gl_income, debit=Decimal("0.00"), credit=Decimal("200.00"))

        url = reverse("accounting:journal_entry_post", args=[je.pk])
        resp = client_a.post(url)
        assert resp.status_code == 302
        je.refresh_from_db()
        assert je.status == "draft"

    def test_is_balanced_helper_correct(self, draft_je):
        """is_balanced() returns True for the balanced fixture."""
        assert draft_je.is_balanced() is True

    def test_is_balanced_false_for_unbalanced(self, tenant_a, admin_user, open_period, gl_cash, gl_income):
        from apps.accounting.models import JournalEntry, JournalLine
        je = JournalEntry.objects.create(
            tenant=tenant_a, entry_type="manual", status="draft",
            fiscal_period=open_period, entry_date=datetime.date(2026, 1, 15),
            description="Unbalanced", created_by=admin_user,
        )
        JournalLine.objects.create(entry=je, gl_account=gl_cash, debit=Decimal("100.00"), credit=Decimal("0.00"))
        assert je.is_balanced() is False


# ================================================================ Void a posted JE
class TestJournalEntryVoid:
    def test_void_creates_reversal_and_marks_original_void(self, client_a, posted_je, tenant_a):
        """Voiding a posted JE creates a reversal and marks original void."""
        from apps.accounting.models import JournalEntry
        url = reverse("accounting:journal_entry_void", args=[posted_je.pk])
        resp = client_a.post(url)
        assert resp.status_code == 302

        posted_je.refresh_from_db()
        assert posted_je.status == "void"

        reversal = JournalEntry.objects.filter(reversal_of=posted_je).first()
        assert reversal is not None
        assert reversal.status == "posted"
        assert reversal.entry_type == "reversal"

    def test_void_reversal_has_swapped_debits_credits(self, client_a, posted_je):
        """Reversal JE has debits and credits swapped vs original."""
        from apps.accounting.models import JournalEntry
        orig_lines = list(posted_je.lines.all().order_by("id"))
        url = reverse("accounting:journal_entry_void", args=[posted_je.pk])
        client_a.post(url)

        reversal = JournalEntry.objects.filter(reversal_of=posted_je).first()
        rev_lines = list(reversal.lines.all().order_by("id"))

        assert len(orig_lines) == len(rev_lines)
        for orig, rev in zip(orig_lines, rev_lines):
            assert rev.debit == orig.credit
            assert rev.credit == orig.debit

    def test_void_ledger_remains_balanced(self, client_a, posted_je, gl_cash, gl_income):
        """After void, posted debit sum == posted credit sum on each account."""
        from django.db.models import Sum
        from apps.accounting.models import JournalLine
        url = reverse("accounting:journal_entry_void", args=[posted_je.pk])
        client_a.post(url)

        agg = JournalLine.objects.filter(entry__status="posted").aggregate(
            total_debit=Sum("debit"), total_credit=Sum("credit")
        )
        total_d = agg["total_debit"] or Decimal("0")
        total_c = agg["total_credit"] or Decimal("0")
        assert total_d == total_c


# ================================================================ Posted JE immutability
class TestPostedJEImmutability:
    def test_get_edit_posted_je_redirects(self, client_a, posted_je):
        """GET on edit view for a posted JE returns 302 to detail."""
        url = reverse("accounting:journal_entry_edit", args=[posted_je.pk])
        resp = client_a.get(url)
        assert resp.status_code == 302
        assert f"/journal-entries/{posted_je.pk}/" in resp["Location"]

    def test_delete_posted_je_not_deleted(self, client_a, posted_je):
        """POST to delete a posted JE is blocked — JE still exists."""
        from apps.accounting.models import JournalEntry
        url = reverse("accounting:journal_entry_delete", args=[posted_je.pk])
        resp = client_a.post(url)
        assert resp.status_code == 302
        assert JournalEntry.objects.filter(pk=posted_je.pk).exists()


# ================================================================ GLAccount.balance() aggregate
class TestGLAccountBalance:
    def test_balance_only_counts_posted_lines(self, tenant_a, admin_user, open_period, gl_cash, gl_income):
        """GLAccount.balance() aggregates only posted journal lines — draft lines excluded."""
        from apps.accounting.models import JournalEntry, JournalLine

        # Posted entry: +300 to cash account (debit normal)
        je_posted = JournalEntry.objects.create(
            tenant=tenant_a, entry_type="manual", status="posted",
            fiscal_period=open_period, entry_date=datetime.date(2026, 1, 10),
            description="Posted",
            created_by=admin_user, approved_by=admin_user,
            posted_at=timezone.now(),
        )
        JournalLine.objects.create(entry=je_posted, gl_account=gl_cash, debit=Decimal("300.00"), credit=Decimal("0.00"))
        JournalLine.objects.create(entry=je_posted, gl_account=gl_income, debit=Decimal("0.00"), credit=Decimal("300.00"))

        # Draft entry: should NOT affect balance
        je_draft = JournalEntry.objects.create(
            tenant=tenant_a, entry_type="manual", status="draft",
            fiscal_period=open_period, entry_date=datetime.date(2026, 1, 10),
            description="Draft",
            created_by=admin_user,
        )
        JournalLine.objects.create(entry=je_draft, gl_account=gl_cash, debit=Decimal("999.00"), credit=Decimal("0.00"))
        JournalLine.objects.create(entry=je_draft, gl_account=gl_income, debit=Decimal("0.00"), credit=Decimal("999.00"))

        # Cash is asset (debit-normal): balance = debit - credit over posted lines
        balance = gl_cash.balance()
        assert balance == Decimal("300.00")

    def test_income_account_credit_normal_balance(self, tenant_a, admin_user, open_period, gl_income, gl_cash):
        """Income account (credit-normal) balance = credit - debit over posted lines."""
        from apps.accounting.models import JournalEntry, JournalLine
        je = JournalEntry.objects.create(
            tenant=tenant_a, entry_type="manual", status="posted",
            fiscal_period=open_period, entry_date=datetime.date(2026, 1, 10),
            description="Revenue",
            created_by=admin_user, approved_by=admin_user,
            posted_at=timezone.now(),
        )
        JournalLine.objects.create(entry=je, gl_account=gl_cash, debit=Decimal("200.00"), credit=Decimal("0.00"))
        JournalLine.objects.create(entry=je, gl_account=gl_income, debit=Decimal("0.00"), credit=Decimal("200.00"))

        # Income is credit-normal: balance = credit - debit
        balance = gl_income.balance()
        assert balance == Decimal("200.00")

    def test_empty_account_balance_is_zero(self, gl_cash):
        """An account with no journal lines has balance == 0."""
        assert gl_cash.balance() == Decimal("0")
