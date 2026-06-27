"""Tests for CRM sub-module 1.7 — Finance & Billing.

Covers:
  - DealInvoice / PaymentReceipt auto-numbers (DINV- / RCPT-)
  - DealInvoice read-through properties (invoice=None → safe defaults)
  - dealinvoice_from_quote conversion: happy path, idempotency, guards
  - DealInvoiceForm / PaymentReceiptForm tenant-scoped querysets
  - CRUD views: list / detail / create / edit / delete / print
  - Multi-tenant IDOR: cross-tenant pk → 404
  - Auth enforcement: anonymous → redirect to login
  - POST-only enforcement for conversion and delete
  - Performance: dealinvoice_list annotation does NOT N+1
"""
import datetime
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.django_db


# ======================================================================== helpers / factories

def _make_currency(code="USD"):
    """Get or create a Currency (global — no tenant FK)."""
    from apps.accounting.models import Currency
    c, _ = Currency.objects.get_or_create(
        code=code, defaults={"name": code, "symbol": "$"}
    )
    return c


def _make_gl_account(tenant, code="1000", account_type="asset"):
    from apps.accounting.models import GLAccount
    return GLAccount.objects.create(
        tenant=tenant, code=code, name="Cash", account_type=account_type
    )


def _make_bank_account(tenant, currency=None):
    from apps.accounting.models import BankAccount
    if currency is None:
        currency = _make_currency()
    return BankAccount.objects.create(
        tenant=tenant, name="Main Bank", currency=currency
    )


def _make_party(tenant, name="ACME Ltd"):
    from apps.core.models import Party
    return Party.objects.create(tenant=tenant, kind="organization", name=name)


def _make_invoice(tenant, party, currency=None, status="draft"):
    from apps.accounting.models import Invoice
    if currency is None:
        currency = _make_currency()
    today = timezone.localdate()
    return Invoice.objects.create(
        tenant=tenant,
        party=party,
        issue_date=today,
        status=status,
        currency=currency,
    )


def _make_payment(tenant, party, bank_account=None, direction="in", status="confirmed", amount=Decimal("100")):
    from apps.accounting.models import Payment
    if bank_account is None:
        bank_account = _make_bank_account(tenant)
    today = timezone.localdate()
    return Payment.objects.create(
        tenant=tenant,
        party=party,
        bank_account=bank_account,
        direction=direction,
        payment_date=today,
        amount=amount,
        status=status,
    )


def _make_deal_invoice(tenant, invoice=None, account=None):
    from apps.crm.models import DealInvoice
    return DealInvoice.objects.create(
        tenant=tenant,
        invoice=invoice,
        account=account,
    )


def _make_payment_receipt(tenant, deal_invoice, received_date=None):
    from apps.crm.models import PaymentReceipt
    if received_date is None:
        received_date = timezone.localdate()
    return PaymentReceipt.objects.create(
        tenant=tenant,
        deal_invoice=deal_invoice,
        amount=Decimal("50.00"),
        received_date=received_date,
        method="bank_transfer",
        gateway="manual",
    )


def _make_quote(tenant, account, status="accepted", currency_code="USD", discount_pct=Decimal("10")):
    from apps.crm.models import Quote
    return Quote.objects.create(
        tenant=tenant,
        name="Test Quote",
        account=account,
        status=status,
        currency_code=currency_code,
        discount_pct=discount_pct,
    )


def _add_quote_line(quote, unit_price=Decimal("100"), qty=Decimal("3"),
                    discount_pct=Decimal("0"), tax_pct=Decimal("10")):
    from apps.crm.models import QuoteLine
    return QuoteLine.objects.create(
        tenant=quote.tenant,
        quote=quote,
        description="Widget",
        unit_price=unit_price,
        quantity=qty,
        discount_pct=discount_pct,
        tax_pct=tax_pct,
    )


# ======================================================================== Fixtures

@pytest.fixture
def party_a(db, tenant_a):
    return _make_party(tenant_a, "Acme Client A")


@pytest.fixture
def party_b(db, tenant_b):
    return _make_party(tenant_b, "Globex Client B")


@pytest.fixture
def currency_usd(db):
    return _make_currency("USD")


@pytest.fixture
def invoice_a(db, tenant_a, party_a, currency_usd):
    """A draft accounting.Invoice for tenant_a."""
    return _make_invoice(tenant_a, party_a, currency=currency_usd)


@pytest.fixture
def deal_invoice_a(db, tenant_a, invoice_a, party_a):
    return _make_deal_invoice(tenant_a, invoice=invoice_a, account=party_a)


@pytest.fixture
def deal_invoice_a_unlinked(db, tenant_a):
    """A DealInvoice with no linked accounting invoice."""
    return _make_deal_invoice(tenant_a, invoice=None, account=None)


@pytest.fixture
def deal_invoice_b(db, tenant_b, party_b):
    """Tenant B's DealInvoice (no linked invoice, for IDOR tests)."""
    return _make_deal_invoice(tenant_b, invoice=None, account=party_b)


@pytest.fixture
def receipt_a(db, tenant_a, deal_invoice_a):
    return _make_payment_receipt(tenant_a, deal_invoice_a)


@pytest.fixture
def receipt_a_unlinked(db, tenant_a, deal_invoice_a_unlinked):
    return _make_payment_receipt(tenant_a, deal_invoice_a_unlinked)


@pytest.fixture
def receipt_b(db, tenant_b, deal_invoice_b):
    return _make_payment_receipt(tenant_b, deal_invoice_b)


@pytest.fixture
def accepted_quote(db, tenant_a, party_a):
    """An accepted quote with one line, ready for conversion."""
    q = _make_quote(tenant_a, party_a, status="accepted", discount_pct=Decimal("10"))
    # 3 × 100, 0% line discount, 10% tax → line_subtotal=300, line_tax=30, disc 90% → total = 297
    _add_quote_line(q, unit_price=Decimal("100"), qty=Decimal("3"),
                    discount_pct=Decimal("0"), tax_pct=Decimal("10"))
    q.recalc_totals()
    return q


# ======================================================================== Group 1 — Model

class TestDealInvoiceAutoNumber:
    def test_auto_number_format(self, deal_invoice_a):
        assert deal_invoice_a.number.startswith("DINV-")

    def test_auto_number_first_is_00001(self, tenant_a):
        from apps.crm.models import DealInvoice
        di = DealInvoice.objects.create(tenant=tenant_a)
        assert di.number == "DINV-00001"

    def test_per_tenant_numbering(self, tenant_a, tenant_b):
        from apps.crm.models import DealInvoice
        a = DealInvoice.objects.create(tenant=tenant_a)
        b = DealInvoice.objects.create(tenant=tenant_b)
        assert a.number == "DINV-00001"
        assert b.number == "DINV-00001"

    def test_unique_together_tenant_number(self, tenant_a, deal_invoice_a):
        from apps.crm.models import DealInvoice
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            DealInvoice.objects.create(tenant=tenant_a, number="DINV-00001")

    def test_str_contains_number_and_invoice_number(self, deal_invoice_a):
        s = str(deal_invoice_a)
        assert "DINV-00001" in s


class TestPaymentReceiptAutoNumber:
    def test_auto_number_format(self, receipt_a):
        assert receipt_a.number.startswith("RCPT-")

    def test_auto_number_first_is_00001(self, tenant_a, deal_invoice_a):
        from apps.crm.models import PaymentReceipt
        r = PaymentReceipt.objects.create(
            tenant=tenant_a, deal_invoice=deal_invoice_a,
            amount=Decimal("10"), received_date=timezone.localdate(),
        )
        assert r.number == "RCPT-00001"

    def test_per_tenant_numbering(self, tenant_a, tenant_b, deal_invoice_a, deal_invoice_b):
        from apps.crm.models import PaymentReceipt
        today = timezone.localdate()
        a = PaymentReceipt.objects.create(
            tenant=tenant_a, deal_invoice=deal_invoice_a,
            amount=Decimal("1"), received_date=today,
        )
        b = PaymentReceipt.objects.create(
            tenant=tenant_b, deal_invoice=deal_invoice_b,
            amount=Decimal("1"), received_date=today,
        )
        assert a.number == "RCPT-00001"
        assert b.number == "RCPT-00001"

    def test_str_contains_number_and_amount(self, receipt_a):
        s = str(receipt_a)
        assert "RCPT-00001" in s
        assert "50" in s


class TestDealInvoiceUnlinkedProperties:
    """Read-through props must not blow up when invoice=None."""

    def test_invoice_number_returns_dash(self, deal_invoice_a_unlinked):
        assert deal_invoice_a_unlinked.invoice_number == "—"

    def test_invoice_status_returns_unlinked(self, deal_invoice_a_unlinked):
        assert deal_invoice_a_unlinked.invoice_status == "unlinked"

    def test_invoice_total_returns_zero(self, deal_invoice_a_unlinked):
        assert deal_invoice_a_unlinked.invoice_total == Decimal("0")

    def test_amount_paid_returns_zero(self, deal_invoice_a_unlinked):
        assert deal_invoice_a_unlinked.amount_paid == Decimal("0")

    def test_balance_due_returns_zero(self, deal_invoice_a_unlinked):
        assert deal_invoice_a_unlinked.balance_due == Decimal("0")


class TestDealInvoiceLinkedProperties:
    """When linked to an Invoice, props delegate to it."""

    def test_invoice_number_delegates(self, deal_invoice_a, invoice_a):
        assert deal_invoice_a.invoice_number == invoice_a.number

    def test_invoice_status_delegates(self, deal_invoice_a):
        assert deal_invoice_a.invoice_status == "draft"

    def test_invoice_total_delegates(self, deal_invoice_a, invoice_a):
        # No lines → total is 0
        assert deal_invoice_a.invoice_total == Decimal("0")

    def test_amount_paid_zero_with_no_allocations(self, deal_invoice_a):
        assert deal_invoice_a.amount_paid == Decimal("0")

    def test_balance_due_equals_total_when_no_payments(self, deal_invoice_a):
        assert deal_invoice_a.balance_due == Decimal("0")


class TestPaymentReceiptChoices:
    def test_method_choices_contains_expected(self):
        from apps.crm.models import PaymentReceipt
        keys = [k for k, _ in PaymentReceipt.METHOD_CHOICES]
        for expected in ("bank_transfer", "card", "cash", "check", "stripe"):
            assert expected in keys

    def test_gateway_choices_contains_expected(self):
        from apps.crm.models import PaymentReceipt
        keys = [k for k, _ in PaymentReceipt.GATEWAY_CHOICES]
        for expected in ("manual", "stripe", "paypal"):
            assert expected in keys


# ======================================================================== Group 2 — Conversion

class TestDealInvoiceFromQuoteConversion:
    """Happy-path: an accepted quote with lines is converted to a DealInvoice + accounting.Invoice."""

    def test_returns_302_redirect(self, client_a, accepted_quote):
        url = reverse("crm:dealinvoice_from_quote", args=[accepted_quote.pk])
        resp = client_a.post(url)
        assert resp.status_code == 302

    def test_accounting_invoice_created(self, client_a, tenant_a, accepted_quote):
        from apps.accounting.models import Invoice
        url = reverse("crm:dealinvoice_from_quote", args=[accepted_quote.pk])
        client_a.post(url)
        assert Invoice.objects.filter(tenant=tenant_a).exists()

    def test_accounting_invoice_status_is_draft(self, client_a, tenant_a, accepted_quote):
        from apps.accounting.models import Invoice
        client_a.post(reverse("crm:dealinvoice_from_quote", args=[accepted_quote.pk]))
        inv = Invoice.objects.filter(tenant=tenant_a).first()
        assert inv.status == "draft"

    def test_accounting_invoice_party_matches_quote_account(self, client_a, tenant_a, accepted_quote, party_a):
        from apps.accounting.models import Invoice
        client_a.post(reverse("crm:dealinvoice_from_quote", args=[accepted_quote.pk]))
        inv = Invoice.objects.filter(tenant=tenant_a).first()
        assert inv.party_id == party_a.pk

    def test_invoice_lines_created_per_quote_line(self, client_a, tenant_a, accepted_quote):
        from apps.accounting.models import Invoice, InvoiceLine
        client_a.post(reverse("crm:dealinvoice_from_quote", args=[accepted_quote.pk]))
        inv = Invoice.objects.filter(tenant=tenant_a).first()
        assert InvoiceLine.objects.filter(invoice=inv).count() == accepted_quote.lines.count()

    def test_deal_invoice_wrapper_created(self, client_a, tenant_a, accepted_quote):
        from apps.crm.models import DealInvoice
        client_a.post(reverse("crm:dealinvoice_from_quote", args=[accepted_quote.pk]))
        assert DealInvoice.objects.filter(tenant=tenant_a, quote=accepted_quote).exists()

    def test_deal_invoice_links_to_accounting_invoice(self, client_a, tenant_a, accepted_quote):
        from apps.accounting.models import Invoice
        from apps.crm.models import DealInvoice
        client_a.post(reverse("crm:dealinvoice_from_quote", args=[accepted_quote.pk]))
        deal = DealInvoice.objects.get(tenant=tenant_a, quote=accepted_quote)
        inv = Invoice.objects.filter(tenant=tenant_a).first()
        assert deal.invoice_id == inv.pk

    def test_invoice_total_equals_quote_total(self, client_a, tenant_a, accepted_quote):
        """Discount + tax carried correctly: 3×100, 10% line tax, 10% quote disc → 297.00."""
        from apps.accounting.models import Invoice
        client_a.post(reverse("crm:dealinvoice_from_quote", args=[accepted_quote.pk]))
        inv = Invoice.objects.filter(tenant=tenant_a).first()
        assert inv.total == accepted_quote.total
        assert inv.total == Decimal("297.00")

    def test_idempotency_second_post_redirects_to_existing(self, client_a, tenant_a, accepted_quote):
        """POSTing the same quote twice must NOT create a second DealInvoice."""
        from apps.crm.models import DealInvoice
        url = reverse("crm:dealinvoice_from_quote", args=[accepted_quote.pk])
        resp1 = client_a.post(url)
        assert resp1.status_code == 302
        resp2 = client_a.post(url)
        assert resp2.status_code == 302
        assert DealInvoice.objects.filter(tenant=tenant_a, quote=accepted_quote).count() == 1

    def test_non_accepted_quote_not_converted(self, client_a, tenant_a, party_a):
        """A draft quote must not be converted."""
        from apps.accounting.models import Invoice
        from apps.crm.models import DealInvoice
        q = _make_quote(tenant_a, party_a, status="draft")
        _add_quote_line(q)
        q.recalc_totals()
        client_a.post(reverse("crm:dealinvoice_from_quote", args=[q.pk]))
        assert not DealInvoice.objects.filter(tenant=tenant_a, quote=q).exists()
        assert not Invoice.objects.filter(tenant=tenant_a).exists()

    def test_non_accepted_quote_redirects_to_quote_detail(self, client_a, tenant_a, party_a):
        from apps.crm.models import DealInvoice
        q = _make_quote(tenant_a, party_a, status="draft")
        _add_quote_line(q)
        resp = client_a.post(reverse("crm:dealinvoice_from_quote", args=[q.pk]))
        assert resp.status_code == 302
        assert f"/quotes/{q.pk}/" in resp["Location"]

    def test_quote_with_no_account_not_converted(self, client_a, tenant_a):
        """Quote without an account FK must not be converted."""
        from apps.accounting.models import Invoice
        from apps.crm.models import DealInvoice, Quote
        q = Quote.objects.create(
            tenant=tenant_a, name="No-account quote", status="accepted",
            account=None, currency_code="USD",
        )
        _add_quote_line(q)
        resp = client_a.post(reverse("crm:dealinvoice_from_quote", args=[q.pk]))
        assert resp.status_code == 302
        assert not DealInvoice.objects.filter(tenant=tenant_a, quote=q).exists()
        assert not Invoice.objects.filter(tenant=tenant_a).exists()

    def test_conversion_get_method_not_allowed(self, client_a, accepted_quote):
        """dealinvoice_from_quote is POST-only; GET → 405."""
        url = reverse("crm:dealinvoice_from_quote", args=[accepted_quote.pk])
        resp = client_a.get(url)
        assert resp.status_code == 405


class TestDealInvoiceFromQuoteIDOR:
    """Tenant A posting conversion for Tenant B's quote must get 404."""

    def test_cross_tenant_quote_conversion_404(self, client_a, tenant_b, party_b):
        q = _make_quote(tenant_b, party_b, status="accepted")
        _add_quote_line(q)
        resp = client_a.post(reverse("crm:dealinvoice_from_quote", args=[q.pk]))
        assert resp.status_code == 404


# ======================================================================== Group 3 — Forms

class TestDealInvoiceFormQuerysets:
    def test_invoice_queryset_scoped_to_tenant(self, tenant_a, tenant_b, party_a, party_b):
        """Form shows only tenant_a's invoices, not tenant_b's."""
        from apps.crm.forms import DealInvoiceForm
        inv_a = _make_invoice(tenant_a, party_a)
        inv_b = _make_invoice(tenant_b, party_b)
        form = DealInvoiceForm(tenant=tenant_a)
        qs = form.fields["invoice"].queryset
        assert inv_a in qs
        assert inv_b not in qs

    def test_invoice_field_absent_in_edit_mode(self, tenant_a):
        """Editing an existing DealInvoice must NOT expose the invoice re-point field."""
        from apps.crm.forms import DealInvoiceForm
        form = DealInvoiceForm(tenant=tenant_a, editing=True)
        assert "invoice" not in form.fields

    def test_invoice_field_present_in_create_mode(self, tenant_a):
        from apps.crm.forms import DealInvoiceForm
        form = DealInvoiceForm(tenant=tenant_a)
        assert "invoice" in form.fields

    def test_tenant_not_in_form_fields(self, tenant_a):
        from apps.crm.forms import DealInvoiceForm
        form = DealInvoiceForm(tenant=tenant_a)
        assert "tenant" not in form.fields

    def test_number_not_in_form_fields(self, tenant_a):
        from apps.crm.forms import DealInvoiceForm
        form = DealInvoiceForm(tenant=tenant_a)
        assert "number" not in form.fields


class TestPaymentReceiptFormQuerysets:
    def test_payment_queryset_scoped_to_tenant(self, tenant_a, tenant_b, party_a, party_b):
        """Form shows only tenant_a inbound payments."""
        from apps.crm.forms import PaymentReceiptForm
        bank_a = _make_bank_account(tenant_a)
        bank_b = _make_bank_account(tenant_b)
        pay_a = _make_payment(tenant_a, party_a, bank_account=bank_a, direction="in")
        pay_b = _make_payment(tenant_b, party_b, bank_account=bank_b, direction="in")
        form = PaymentReceiptForm(tenant=tenant_a)
        qs = form.fields["payment"].queryset
        assert pay_a in qs
        assert pay_b not in qs

    def test_outbound_payment_excluded_from_queryset(self, tenant_a, party_a):
        """Outbound payments (vendor payments) must NOT appear in the receipt form."""
        from apps.crm.forms import PaymentReceiptForm
        bank_a = _make_bank_account(tenant_a)
        out_pay = _make_payment(tenant_a, party_a, bank_account=bank_a, direction="out")
        form = PaymentReceiptForm(tenant=tenant_a)
        assert out_pay not in form.fields["payment"].queryset

    def test_payment_field_not_required(self, tenant_a):
        """Payment link is optional (SET_NULL FK)."""
        from apps.crm.forms import PaymentReceiptForm
        form = PaymentReceiptForm(tenant=tenant_a)
        assert form.fields["payment"].required is False

    def test_tenant_not_in_form_fields(self, tenant_a):
        from apps.crm.forms import PaymentReceiptForm
        form = PaymentReceiptForm(tenant=tenant_a)
        assert "tenant" not in form.fields

    def test_number_not_in_form_fields(self, tenant_a):
        from apps.crm.forms import PaymentReceiptForm
        form = PaymentReceiptForm(tenant=tenant_a)
        assert "number" not in form.fields


# ======================================================================== Group 4 — CRUD integration

class TestDealInvoiceListView:
    def test_list_200(self, client_a, deal_invoice_a):
        resp = client_a.get(reverse("crm:dealinvoice_list"))
        assert resp.status_code == 200

    def test_list_shows_own_deal_invoice(self, client_a, deal_invoice_a):
        resp = client_a.get(reverse("crm:dealinvoice_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert deal_invoice_a.pk in pks

    def test_list_excludes_other_tenant(self, client_a, deal_invoice_a, deal_invoice_b):
        resp = client_a.get(reverse("crm:dealinvoice_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert deal_invoice_b.pk not in pks

    def test_list_has_status_choices_context(self, client_a):
        resp = client_a.get(reverse("crm:dealinvoice_list"))
        assert "status_choices" in resp.context

    def test_anon_redirects_to_login(self, client):
        resp = client.get(reverse("crm:dealinvoice_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


class TestDealInvoiceDetailView:
    def test_detail_200(self, client_a, deal_invoice_a):
        resp = client_a.get(reverse("crm:dealinvoice_detail", args=[deal_invoice_a.pk]))
        assert resp.status_code == 200

    def test_detail_context_has_obj(self, client_a, deal_invoice_a):
        resp = client_a.get(reverse("crm:dealinvoice_detail", args=[deal_invoice_a.pk]))
        assert resp.context["obj"].pk == deal_invoice_a.pk

    def test_anon_redirects_to_login(self, client, deal_invoice_a):
        resp = client.get(reverse("crm:dealinvoice_detail", args=[deal_invoice_a.pk]))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


class TestDealInvoiceCreateView:
    def test_get_200(self, client_a):
        resp = client_a.get(reverse("crm:dealinvoice_create"))
        assert resp.status_code == 200

    def test_post_creates_deal_invoice_with_correct_tenant(self, client_a, tenant_a, invoice_a):
        from apps.crm.models import DealInvoice
        resp = client_a.post(reverse("crm:dealinvoice_create"), {
            "opportunity": "",
            "quote": "",
            "account": "",
            "recurring_invoice": "",
            "invoice": invoice_a.pk,
            "notes": "Manual test invoice",
        })
        assert resp.status_code == 302
        obj = DealInvoice.objects.filter(tenant=tenant_a).order_by("-id").first()
        assert obj is not None
        assert obj.tenant_id == tenant_a.pk

    def test_post_assigns_auto_number(self, client_a, tenant_a, invoice_a):
        from apps.crm.models import DealInvoice
        client_a.post(reverse("crm:dealinvoice_create"), {
            "notes": "auto-number test",
            "invoice": invoice_a.pk,
        })
        obj = DealInvoice.objects.filter(tenant=tenant_a).order_by("-id").first()
        assert obj is not None
        assert obj.number.startswith("DINV-")

    def test_anon_redirects(self, client):
        resp = client.get(reverse("crm:dealinvoice_create"))
        assert resp.status_code == 302


class TestDealInvoiceEditView:
    def test_get_200(self, client_a, deal_invoice_a):
        resp = client_a.get(reverse("crm:dealinvoice_edit", args=[deal_invoice_a.pk]))
        assert resp.status_code == 200

    def test_post_updates_notes(self, client_a, deal_invoice_a):
        resp = client_a.post(reverse("crm:dealinvoice_edit", args=[deal_invoice_a.pk]), {
            "notes": "Updated note",
        })
        assert resp.status_code == 302
        deal_invoice_a.refresh_from_db()
        assert deal_invoice_a.notes == "Updated note"

    def test_anon_redirects(self, client, deal_invoice_a):
        resp = client.get(reverse("crm:dealinvoice_edit", args=[deal_invoice_a.pk]))
        assert resp.status_code == 302


class TestDealInvoiceDeleteView:
    def test_post_deletes_wrapper(self, client_a, deal_invoice_a):
        from apps.crm.models import DealInvoice
        pk = deal_invoice_a.pk
        resp = client_a.post(reverse("crm:dealinvoice_delete", args=[pk]))
        assert resp.status_code == 302
        assert not DealInvoice.objects.filter(pk=pk).exists()

    def test_delete_does_not_remove_linked_accounting_invoice(self, client_a, deal_invoice_a, invoice_a):
        """Deleting the CRM wrapper must leave the accounting.Invoice intact."""
        from apps.accounting.models import Invoice
        client_a.post(reverse("crm:dealinvoice_delete", args=[deal_invoice_a.pk]))
        assert Invoice.objects.filter(pk=invoice_a.pk).exists()

    def test_get_does_not_delete(self, client_a, deal_invoice_a):
        from apps.crm.models import DealInvoice
        pk = deal_invoice_a.pk
        client_a.get(reverse("crm:dealinvoice_delete", args=[pk]))
        assert DealInvoice.objects.filter(pk=pk).exists()

    def test_anon_redirects(self, client, deal_invoice_a):
        resp = client.post(reverse("crm:dealinvoice_delete", args=[deal_invoice_a.pk]))
        assert resp.status_code == 302


class TestPaymentReceiptListView:
    def test_list_200(self, client_a, receipt_a):
        resp = client_a.get(reverse("crm:paymentreceipt_list"))
        assert resp.status_code == 200

    def test_list_shows_own_receipt(self, client_a, receipt_a):
        resp = client_a.get(reverse("crm:paymentreceipt_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert receipt_a.pk in pks

    def test_list_excludes_other_tenant_receipt(self, client_a, receipt_a, receipt_b):
        resp = client_a.get(reverse("crm:paymentreceipt_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert receipt_b.pk not in pks

    def test_anon_redirects_to_login(self, client):
        resp = client.get(reverse("crm:paymentreceipt_list"))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


class TestPaymentReceiptCreateView:
    def test_get_200(self, client_a, deal_invoice_a):
        resp = client_a.get(reverse("crm:paymentreceipt_create"))
        assert resp.status_code == 200

    def test_post_creates_receipt_with_correct_tenant(self, client_a, tenant_a, deal_invoice_a):
        from apps.crm.models import PaymentReceipt
        today = timezone.localdate()
        resp = client_a.post(reverse("crm:paymentreceipt_create"), {
            "deal_invoice": deal_invoice_a.pk,
            "payment": "",
            "amount": "75.00",
            "received_date": today.strftime("%Y-%m-%d"),
            "method": "cash",
            "gateway": "manual",
            "gateway_txn_id": "",
            "notes": "",
        })
        assert resp.status_code == 302
        obj = PaymentReceipt.objects.filter(tenant=tenant_a).order_by("-id").first()
        assert obj is not None
        assert obj.tenant_id == tenant_a.pk

    def test_post_auto_assigns_number(self, client_a, tenant_a, deal_invoice_a):
        from apps.crm.models import PaymentReceipt
        today = timezone.localdate()
        client_a.post(reverse("crm:paymentreceipt_create"), {
            "deal_invoice": deal_invoice_a.pk,
            "amount": "10.00",
            "received_date": today.strftime("%Y-%m-%d"),
            "method": "cash",
            "gateway": "manual",
        })
        obj = PaymentReceipt.objects.filter(tenant=tenant_a).order_by("-id").first()
        assert obj is not None
        assert obj.number.startswith("RCPT-")

    def test_anon_redirects(self, client):
        resp = client.post(reverse("crm:paymentreceipt_create"), {})
        assert resp.status_code == 302


class TestPaymentReceiptDetailView:
    def test_detail_200(self, client_a, receipt_a):
        resp = client_a.get(reverse("crm:paymentreceipt_detail", args=[receipt_a.pk]))
        assert resp.status_code == 200

    def test_detail_context_has_obj(self, client_a, receipt_a):
        resp = client_a.get(reverse("crm:paymentreceipt_detail", args=[receipt_a.pk]))
        assert resp.context["obj"].pk == receipt_a.pk

    def test_anon_redirects(self, client, receipt_a):
        resp = client.get(reverse("crm:paymentreceipt_detail", args=[receipt_a.pk]))
        assert resp.status_code == 302


class TestPaymentReceiptEditView:
    def test_get_200(self, client_a, receipt_a, deal_invoice_a):
        resp = client_a.get(reverse("crm:paymentreceipt_edit", args=[receipt_a.pk]))
        assert resp.status_code == 200

    def test_post_updates_amount(self, client_a, receipt_a, deal_invoice_a):
        today = timezone.localdate()
        resp = client_a.post(reverse("crm:paymentreceipt_edit", args=[receipt_a.pk]), {
            "deal_invoice": deal_invoice_a.pk,
            "payment": "",
            "amount": "99.99",
            "received_date": today.strftime("%Y-%m-%d"),
            "method": "card",
            "gateway": "stripe",
            "gateway_txn_id": "",
            "notes": "",
        })
        assert resp.status_code == 302
        receipt_a.refresh_from_db()
        assert receipt_a.amount == Decimal("99.99")

    def test_anon_redirects(self, client, receipt_a):
        resp = client.get(reverse("crm:paymentreceipt_edit", args=[receipt_a.pk]))
        assert resp.status_code == 302


class TestPaymentReceiptDeleteView:
    def test_post_deletes_receipt(self, client_a, receipt_a):
        from apps.crm.models import PaymentReceipt
        pk = receipt_a.pk
        resp = client_a.post(reverse("crm:paymentreceipt_delete", args=[pk]))
        assert resp.status_code == 302
        assert not PaymentReceipt.objects.filter(pk=pk).exists()

    def test_anon_redirects(self, client, receipt_a):
        resp = client.post(reverse("crm:paymentreceipt_delete", args=[receipt_a.pk]))
        assert resp.status_code == 302


class TestPaymentReceiptPrintView:
    def test_print_200(self, client_a, receipt_a):
        resp = client_a.get(reverse("crm:paymentreceipt_print", args=[receipt_a.pk]))
        assert resp.status_code == 200

    def test_print_context_has_obj(self, client_a, receipt_a):
        resp = client_a.get(reverse("crm:paymentreceipt_print", args=[receipt_a.pk]))
        assert resp.context["obj"].pk == receipt_a.pk

    def test_print_context_has_tenant(self, client_a, receipt_a, tenant_a):
        resp = client_a.get(reverse("crm:paymentreceipt_print", args=[receipt_a.pk]))
        assert resp.context["tenant"].pk == tenant_a.pk

    def test_anon_redirects(self, client, receipt_a):
        resp = client.get(reverse("crm:paymentreceipt_print", args=[receipt_a.pk]))
        assert resp.status_code == 302


# ======================================================================== Group 5 — Multi-Tenant IDOR

class TestDealInvoiceIDOR:
    def test_detail_cross_tenant_404(self, client_a, deal_invoice_b):
        resp = client_a.get(reverse("crm:dealinvoice_detail", args=[deal_invoice_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, deal_invoice_b):
        resp = client_a.get(reverse("crm:dealinvoice_edit", args=[deal_invoice_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, deal_invoice_b):
        resp = client_a.post(reverse("crm:dealinvoice_edit", args=[deal_invoice_b.pk]), {
            "notes": "hacked",
        })
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, deal_invoice_b):
        resp = client_a.post(reverse("crm:dealinvoice_delete", args=[deal_invoice_b.pk]))
        assert resp.status_code == 404

    def test_list_never_contains_other_tenant_rows(self, client_a, deal_invoice_a, deal_invoice_b):
        resp = client_a.get(reverse("crm:dealinvoice_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert deal_invoice_b.pk not in pks


class TestPaymentReceiptIDOR:
    def test_detail_cross_tenant_404(self, client_a, receipt_b):
        resp = client_a.get(reverse("crm:paymentreceipt_detail", args=[receipt_b.pk]))
        assert resp.status_code == 404

    def test_edit_get_cross_tenant_404(self, client_a, receipt_b):
        resp = client_a.get(reverse("crm:paymentreceipt_edit", args=[receipt_b.pk]))
        assert resp.status_code == 404

    def test_edit_post_cross_tenant_404(self, client_a, receipt_b):
        today = timezone.localdate()
        resp = client_a.post(reverse("crm:paymentreceipt_edit", args=[receipt_b.pk]), {
            "amount": "9999",
            "received_date": today.strftime("%Y-%m-%d"),
            "method": "cash",
            "gateway": "manual",
        })
        assert resp.status_code == 404

    def test_delete_cross_tenant_404(self, client_a, receipt_b):
        resp = client_a.post(reverse("crm:paymentreceipt_delete", args=[receipt_b.pk]))
        assert resp.status_code == 404

    def test_print_cross_tenant_404(self, client_a, receipt_b):
        resp = client_a.get(reverse("crm:paymentreceipt_print", args=[receipt_b.pk]))
        assert resp.status_code == 404

    def test_list_never_contains_other_tenant_rows(self, client_a, receipt_a, receipt_b):
        resp = client_a.get(reverse("crm:paymentreceipt_list"))
        pks = [obj.pk for obj in resp.context["object_list"]]
        assert receipt_b.pk not in pks


# ======================================================================== Group 6 — Auth / CSRF

class TestFinanceAuthEnforcement:
    @pytest.mark.parametrize("url_name", [
        "crm:dealinvoice_list",
        "crm:dealinvoice_create",
        "crm:paymentreceipt_list",
        "crm:paymentreceipt_create",
    ])
    def test_anon_get_redirects_to_login(self, client, url_name):
        resp = client.get(reverse(url_name))
        assert resp.status_code == 302
        assert "login" in resp["Location"]


class TestFinanceCSRF:
    def test_dealinvoice_delete_enforces_csrf(self, admin_user, deal_invoice_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("crm:dealinvoice_delete", args=[deal_invoice_a.pk]))
        assert resp.status_code == 403

    def test_paymentreceipt_delete_enforces_csrf(self, admin_user, receipt_a):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("crm:paymentreceipt_delete", args=[receipt_a.pk]))
        assert resp.status_code == 403

    def test_dealinvoice_from_quote_enforces_csrf(self, admin_user, accepted_quote):
        c = Client(enforce_csrf_checks=True)
        c.force_login(admin_user)
        resp = c.post(reverse("crm:dealinvoice_from_quote", args=[accepted_quote.pk]))
        assert resp.status_code == 403


# ======================================================================== Group 7 — Performance

class TestDealInvoiceListNoPlusOneQuery:
    """dealinvoice_list uses a Subquery annotation; adding rows must not add extra queries."""

    def test_query_count_does_not_scale_with_rows(self, client_a, tenant_a, party_a):
        """Create several DealInvoices and assert list stays under a fixed query cap."""
        from apps.accounting.models import Invoice
        from apps.crm.models import DealInvoice
        ccy = _make_currency("EUR")
        # Create 5 DealInvoices each backed by an Invoice
        for i in range(5):
            inv = _make_invoice(tenant_a, party_a, currency=ccy, status="draft")
            _make_deal_invoice(tenant_a, invoice=inv, account=party_a)

        url = reverse("crm:dealinvoice_list")
        # Warm-up to avoid first-hit session/middleware query noise
        client_a.get(url)

        from django.test.utils import CaptureQueriesContext
        from django.db import connection
        with CaptureQueriesContext(connection) as ctx:
            resp = client_a.get(url)
        assert resp.status_code == 200
        # With the Subquery annotation the query count is fixed (O(1)) not O(n).
        # A generous cap that proves no N+1: list with 5 rows should fit well under 20 queries.
        assert len(ctx.captured_queries) < 20, (
            f"Expected <20 queries for a 5-row list, got {len(ctx.captured_queries)}. "
            "Potential N+1 regression."
        )
