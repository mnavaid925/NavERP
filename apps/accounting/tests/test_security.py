"""Security tests for the Accounting module.

Covers:
- @tenant_admin_required gates: bill_approve, payment_confirm, payment_void,
  journal_entry_post, journal_entry_void, fiscal_period_close,
  reconciliation_confirm, invoice_post, currency_create/edit/delete
  → 403 for non-admin member, success for admin.
- Mass-assignment: InvoiceForm/BillForm have no `status` field;
  BankTransactionForm has no `source` field; JournalEntryForm has no
  created_by/approved_by/posted_at/status fields.
- ReconciliationMatchForm(tenant=A) excludes tenant-B journal_line.
- Cross-tenant IDOR: tenant-A admin accessing tenant-B objects → 404.
- POST-only action views: GET → 405.
"""
import datetime
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db


# ================================================================ @tenant_admin_required gates
class TestAdminRequiredGates:
    """Non-admin member must get 403; admin must not get 403."""

    def test_bill_approve_requires_admin(self, member_client, client_a, draft_bill):
        # Member → 403
        url = reverse("accounting:bill_approve", args=[draft_bill.pk])
        resp = member_client.post(url)
        assert resp.status_code == 403

        # Admin → success (302 redirect, not 403)
        resp2 = client_a.post(url)
        assert resp2.status_code != 403

    def test_payment_confirm_requires_admin(self, member_client, draft_payment):
        url = reverse("accounting:payment_confirm", args=[draft_payment.pk])
        resp = member_client.post(url)
        assert resp.status_code == 403

    def test_payment_void_requires_admin(self, member_client, client_a, draft_payment):
        # First confirm as admin
        client_a.post(reverse("accounting:payment_confirm", args=[draft_payment.pk]))
        draft_payment.refresh_from_db()

        if draft_payment.status == "confirmed":
            url = reverse("accounting:payment_void", args=[draft_payment.pk])
            resp = member_client.post(url)
            assert resp.status_code == 403

    def test_journal_entry_post_requires_admin(self, member_client, draft_je):
        url = reverse("accounting:journal_entry_post", args=[draft_je.pk])
        resp = member_client.post(url)
        assert resp.status_code == 403

    def test_journal_entry_void_requires_admin(self, member_client, posted_je):
        url = reverse("accounting:journal_entry_void", args=[posted_je.pk])
        resp = member_client.post(url)
        assert resp.status_code == 403

    def test_fiscal_period_close_requires_admin(self, member_client, open_period):
        url = reverse("accounting:fiscal_period_close", args=[open_period.pk])
        resp = member_client.post(url)
        assert resp.status_code == 403

    def test_reconciliation_confirm_requires_admin(
        self, member_client, client_a, tenant_a, bank_account, draft_payment
    ):
        from apps.accounting.models import BankTransaction, ReconciliationMatch
        txn = BankTransaction.objects.create(
            tenant=tenant_a,
            bank_account=bank_account,
            transaction_date=datetime.date(2026, 1, 15),
            description="Test txn",
            amount=Decimal("100.00"),
            direction="credit",
            source="manual",
        )
        # Confirm payment first so we can create a match
        client_a.post(reverse("accounting:payment_confirm", args=[draft_payment.pk]))
        draft_payment.refresh_from_db()
        match = ReconciliationMatch.objects.create(
            tenant=tenant_a,
            bank_transaction=txn,
            payment=draft_payment,
        )
        url = reverse("accounting:reconciliation_confirm", args=[match.pk])
        resp = member_client.post(url)
        assert resp.status_code == 403

    def test_invoice_post_requires_admin(self, member_client, draft_invoice):
        url = reverse("accounting:invoice_post", args=[draft_invoice.pk])
        resp = member_client.post(url)
        assert resp.status_code == 403

    def test_currency_create_requires_admin(self, member_client):
        url = reverse("accounting:currency_create")
        resp = member_client.post(url, {"code": "JPY", "name": "Yen", "symbol": "¥", "is_active": "on"})
        assert resp.status_code == 403

    def test_currency_edit_requires_admin(self, member_client, usd):
        url = reverse("accounting:currency_edit", args=[usd.pk])
        resp = member_client.post(url, {"code": "USD", "name": "Hacked", "symbol": "$", "is_active": "on"})
        assert resp.status_code == 403

    def test_currency_delete_requires_admin(self, member_client, usd):
        url = reverse("accounting:currency_delete", args=[usd.pk])
        resp = member_client.post(url)
        assert resp.status_code == 403

    def test_admin_can_post_currency(self, client_a):
        """Admin user can access currency_create without 403."""
        url = reverse("accounting:currency_create")
        resp = client_a.get(url)
        assert resp.status_code != 403


# ================================================================ Form mass-assignment
class TestFormFieldExclusions:
    def test_invoice_form_has_no_status_field(self):
        from apps.accounting.forms import InvoiceForm
        form = InvoiceForm(tenant=None)
        assert "status" not in form.fields

    def test_bill_form_has_no_status_field(self):
        from apps.accounting.forms import BillForm
        form = BillForm(tenant=None)
        assert "status" not in form.fields

    def test_bank_transaction_form_has_no_source_field(self):
        from apps.accounting.forms import BankTransactionForm
        form = BankTransactionForm(tenant=None)
        assert "source" not in form.fields

    def test_journal_entry_form_has_no_status_field(self):
        from apps.accounting.forms import JournalEntryForm
        form = JournalEntryForm(tenant=None)
        assert "status" not in form.fields

    def test_journal_entry_form_has_no_created_by_field(self):
        from apps.accounting.forms import JournalEntryForm
        form = JournalEntryForm(tenant=None)
        assert "created_by" not in form.fields

    def test_journal_entry_form_has_no_approved_by_field(self):
        from apps.accounting.forms import JournalEntryForm
        form = JournalEntryForm(tenant=None)
        assert "approved_by" not in form.fields

    def test_journal_entry_form_has_no_posted_at_field(self):
        from apps.accounting.forms import JournalEntryForm
        form = JournalEntryForm(tenant=None)
        assert "posted_at" not in form.fields

    def test_fiscal_period_form_has_no_status_field(self):
        """FiscalPeriod status is excluded — only closeable via admin action."""
        from apps.accounting.forms import FiscalPeriodForm
        form = FiscalPeriodForm(tenant=None)
        assert "status" not in form.fields


# ================================================================ ReconciliationMatchForm cross-tenant scoping
class TestReconciliationMatchFormTenantScope:
    def test_journal_line_queryset_scoped_to_tenant_a(
        self, tenant_a, tenant_b, admin_user, admin_b,
        open_period, gl_cash, gl_income, gl_cash_b
    ):
        """ReconciliationMatchForm(tenant=A) must not include tenant-B journal lines."""
        from apps.accounting.models import JournalEntry, JournalLine
        from apps.accounting.forms import ReconciliationMatchForm

        # Create a JE for tenant_a and tenant_b
        je_a = JournalEntry.objects.create(
            tenant=tenant_a, entry_type="manual", status="posted",
            entry_date=datetime.date(2026, 1, 5),
            description="Tenant A JE", created_by=admin_user,
            approved_by=admin_user,
        )
        line_a = JournalLine.objects.create(
            entry=je_a, gl_account=gl_cash, debit=Decimal("100.00"), credit=Decimal("0.00")
        )

        je_b = JournalEntry.objects.create(
            tenant=tenant_b, entry_type="manual", status="posted",
            entry_date=datetime.date(2026, 1, 5),
            description="Tenant B JE", created_by=admin_b,
            approved_by=admin_b,
        )
        line_b = JournalLine.objects.create(
            entry=je_b, gl_account=gl_cash_b, debit=Decimal("200.00"), credit=Decimal("0.00")
        )

        form = ReconciliationMatchForm(tenant=tenant_a)
        qs = form.fields["journal_line"].queryset
        pks = list(qs.values_list("pk", flat=True))
        assert line_a.pk in pks
        assert line_b.pk not in pks


# ================================================================ Cross-tenant IDOR → 404
class TestCrossTenantIDOR:
    def test_journal_entry_detail_cross_tenant_404(self, client_a, je_b):
        url = reverse("accounting:journal_entry_detail", args=[je_b.pk])
        resp = client_a.get(url)
        assert resp.status_code == 404

    def test_journal_entry_edit_cross_tenant_404(self, client_a, je_b):
        url = reverse("accounting:journal_entry_edit", args=[je_b.pk])
        resp = client_a.get(url)
        assert resp.status_code == 404

    def test_journal_entry_post_cross_tenant_404(self, client_a, je_b):
        url = reverse("accounting:journal_entry_post", args=[je_b.pk])
        resp = client_a.post(url)
        assert resp.status_code == 404

    def test_invoice_detail_cross_tenant_404(self, client_a, invoice_b):
        url = reverse("accounting:invoice_detail", args=[invoice_b.pk])
        resp = client_a.get(url)
        assert resp.status_code == 404

    def test_invoice_edit_cross_tenant_404(self, client_a, invoice_b):
        url = reverse("accounting:invoice_edit", args=[invoice_b.pk])
        resp = client_a.get(url)
        assert resp.status_code == 404

    def test_invoice_delete_cross_tenant_404(self, client_a, invoice_b):
        url = reverse("accounting:invoice_delete", args=[invoice_b.pk])
        resp = client_a.post(url)
        assert resp.status_code == 404

    def test_bill_detail_cross_tenant_404(self, client_a, bill_b):
        url = reverse("accounting:bill_detail", args=[bill_b.pk])
        resp = client_a.get(url)
        assert resp.status_code == 404

    def test_bill_edit_cross_tenant_404(self, client_a, bill_b):
        url = reverse("accounting:bill_edit", args=[bill_b.pk])
        resp = client_a.get(url)
        assert resp.status_code == 404

    def test_payment_detail_cross_tenant_404(self, client_a, payment_b):
        url = reverse("accounting:payment_detail", args=[payment_b.pk])
        resp = client_a.get(url)
        assert resp.status_code == 404

    def test_payment_edit_cross_tenant_404(self, client_a, payment_b):
        url = reverse("accounting:payment_edit", args=[payment_b.pk])
        resp = client_a.get(url)
        assert resp.status_code == 404

    def test_bank_account_detail_cross_tenant_404(self, client_a, bank_account_b):
        url = reverse("accounting:bank_account_detail", args=[bank_account_b.pk])
        resp = client_a.get(url)
        assert resp.status_code == 404


# ================================================================ POST-only action views: GET → 405
class TestPostOnlyActions:
    def test_get_journal_entry_post_returns_405(self, client_a, draft_je):
        url = reverse("accounting:journal_entry_post", args=[draft_je.pk])
        resp = client_a.get(url)
        assert resp.status_code == 405

    def test_get_journal_entry_void_returns_405(self, client_a, posted_je):
        url = reverse("accounting:journal_entry_void", args=[posted_je.pk])
        resp = client_a.get(url)
        assert resp.status_code == 405

    def test_get_invoice_post_returns_405(self, client_a, draft_invoice):
        url = reverse("accounting:invoice_post", args=[draft_invoice.pk])
        resp = client_a.get(url)
        assert resp.status_code == 405

    def test_get_bill_approve_returns_405(self, client_a, draft_bill):
        url = reverse("accounting:bill_approve", args=[draft_bill.pk])
        resp = client_a.get(url)
        assert resp.status_code == 405

    def test_get_payment_confirm_returns_405(self, client_a, draft_payment):
        url = reverse("accounting:payment_confirm", args=[draft_payment.pk])
        resp = client_a.get(url)
        assert resp.status_code == 405

    def test_get_payment_void_returns_405(self, client_a, draft_payment):
        url = reverse("accounting:payment_void", args=[draft_payment.pk])
        resp = client_a.get(url)
        assert resp.status_code == 405

    def test_get_fiscal_period_close_returns_405(self, client_a, open_period):
        url = reverse("accounting:fiscal_period_close", args=[open_period.pk])
        resp = client_a.get(url)
        assert resp.status_code == 405


# ================================================================ Anonymous → redirect to login
class TestAnonymousRedirect:
    def test_anonymous_journal_entry_list_redirects(self):
        c = Client()
        resp = c.get(reverse("accounting:journal_entry_list"))
        assert resp.status_code == 302
        assert "/auth/login/" in resp["Location"] or "/login/" in resp["Location"]

    def test_anonymous_invoice_list_redirects(self):
        c = Client()
        resp = c.get(reverse("accounting:invoice_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]

    def test_anonymous_bill_list_redirects(self):
        c = Client()
        resp = c.get(reverse("accounting:bill_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]
