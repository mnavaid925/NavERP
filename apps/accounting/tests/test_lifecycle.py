"""Lifecycle / payment status tests for the Accounting module.

Covers:
- Confirming a payment with a full allocation → invoice becomes paid.
- Voiding the payment reverts invoice to sent/partial.
- amount_paid() ignores allocations on non-confirmed payments.
- AR/AP aging bucket: invoice 45 days past due lands in 31-60 bucket;
  not-yet-due invoice lands in current.
"""
import datetime
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

pytestmark = pytest.mark.django_db


# ================================================================ Payment lifecycle → invoice status
class TestPaymentConfirmAndVoid:
    def test_confirm_payment_with_full_allocation_marks_invoice_paid(
        self, client_a, tenant_a, admin_user, sent_invoice,
        draft_payment, gl_cash, gl_ar, open_period
    ):
        """Confirming a payment that fully covers the invoice moves it to paid."""
        from apps.accounting.models import PaymentAllocation

        # Invoice total = 500, payment amount = 500 — full coverage
        assert sent_invoice.total == Decimal("500.00")

        # Allocate the full payment amount to the invoice
        alloc = PaymentAllocation.objects.create(
            payment=draft_payment,
            invoice=sent_invoice,
            allocated_amount=Decimal("500.00"),
        )

        # Confirm the payment via the view
        url = reverse("accounting:payment_confirm", args=[draft_payment.pk])
        resp = client_a.post(url)
        assert resp.status_code == 302

        draft_payment.refresh_from_db()
        assert draft_payment.status == "confirmed"

        sent_invoice.refresh_from_db()
        assert sent_invoice.status == "paid"

    def test_void_confirmed_payment_reverts_invoice_to_sent(
        self, client_a, tenant_a, admin_user, sent_invoice,
        draft_payment, gl_cash, gl_ar, open_period
    ):
        """Voiding a confirmed payment (with full allocation) reverts invoice to sent."""
        from apps.accounting.models import PaymentAllocation

        PaymentAllocation.objects.create(
            payment=draft_payment,
            invoice=sent_invoice,
            allocated_amount=Decimal("500.00"),
        )

        # First confirm
        client_a.post(reverse("accounting:payment_confirm", args=[draft_payment.pk]))
        draft_payment.refresh_from_db()
        assert draft_payment.status == "confirmed"
        sent_invoice.refresh_from_db()
        assert sent_invoice.status == "paid"

        # Then void
        url = reverse("accounting:payment_void", args=[draft_payment.pk])
        resp = client_a.post(url)
        assert resp.status_code == 302

        draft_payment.refresh_from_db()
        assert draft_payment.status == "void"

        # Invoice should revert: amount_paid() is now 0 (void payment), so back to sent
        sent_invoice.refresh_from_db()
        assert sent_invoice.status == "sent"

    def test_partial_payment_moves_invoice_to_partial(
        self, client_a, tenant_a, sent_invoice, draft_payment, gl_cash, gl_ar, open_period
    ):
        """Confirming a partial payment sets invoice to partial."""
        from apps.accounting.models import Payment, PaymentAllocation
        # Adjust payment amount to partial
        draft_payment.amount = Decimal("200.00")
        draft_payment.save()

        PaymentAllocation.objects.create(
            payment=draft_payment,
            invoice=sent_invoice,
            allocated_amount=Decimal("200.00"),
        )

        client_a.post(reverse("accounting:payment_confirm", args=[draft_payment.pk]))
        sent_invoice.refresh_from_db()
        assert sent_invoice.status == "partial"


# ================================================================ amount_paid() ignores unconfirmed
class TestAmountPaidIgnoresUnconfirmed:
    def test_amount_paid_excludes_draft_payment_allocation(self, sent_invoice, draft_payment):
        """amount_paid() returns 0 when the only allocation is on a draft payment."""
        from apps.accounting.models import PaymentAllocation

        # Allocate but do NOT confirm the payment
        PaymentAllocation.objects.create(
            payment=draft_payment,
            invoice=sent_invoice,
            allocated_amount=Decimal("500.00"),
        )
        # draft_payment is still status=draft — allocation must NOT count
        assert sent_invoice.amount_paid() == Decimal("0.00")

    def test_amount_paid_excludes_void_payment_allocation(
        self, client_a, sent_invoice, draft_payment, gl_cash, gl_ar, open_period
    ):
        """amount_paid() returns 0 after the payment is voided."""
        from apps.accounting.models import PaymentAllocation

        PaymentAllocation.objects.create(
            payment=draft_payment,
            invoice=sent_invoice,
            allocated_amount=Decimal("500.00"),
        )
        # Confirm then void
        client_a.post(reverse("accounting:payment_confirm", args=[draft_payment.pk]))
        client_a.post(reverse("accounting:payment_void", args=[draft_payment.pk]))

        sent_invoice.refresh_from_db()
        # Void payment allocation must not count
        assert sent_invoice.amount_paid() == Decimal("0.00")


# ================================================================ AR / AP Aging buckets
class TestAgingBuckets:
    """Call the _aging() helper directly (or via views) with injected dates."""

    def _make_invoice(self, tenant, party, due_date, total_amount, usd):
        """Helper to create a sent invoice with known total (injected)."""
        from apps.accounting.models import Invoice, InvoiceLine
        inv = Invoice.objects.create(
            tenant=tenant,
            party=party,
            issue_date=datetime.date(2026, 1, 1),
            due_date=due_date,
            status="sent",
            currency=usd,
        )
        InvoiceLine.objects.create(
            invoice=inv,
            description="Item",
            quantity=Decimal("1"),
            unit_price=total_amount,
        )
        inv.recalc_totals()
        return inv

    def test_invoice_45_days_overdue_lands_in_d31_60(self, tenant_a, customer_party, usd):
        """An invoice due 45 days ago lands in the 31-60 day bucket."""
        from apps.accounting.views import _aging
        today = datetime.date(2026, 3, 1)
        due = today - datetime.timedelta(days=45)

        inv = self._make_invoice(tenant_a, customer_party, due, Decimal("100.00"), usd)

        # Annotate paid_agg manually (simulate what the view does with annotate)
        inv.paid_agg = Decimal("0")

        _, totals = _aging([inv], "due_date", today)
        assert totals["d31_60"] == Decimal("100.00")
        assert totals["current"] == Decimal("0")

    def test_invoice_not_yet_due_lands_in_current(self, tenant_a, customer_party, usd):
        """An invoice with future due date lands in the current bucket."""
        from apps.accounting.views import _aging
        today = datetime.date(2026, 3, 1)
        due = today + datetime.timedelta(days=10)

        inv = self._make_invoice(tenant_a, customer_party, due, Decimal("250.00"), usd)
        inv.paid_agg = Decimal("0")

        _, totals = _aging([inv], "due_date", today)
        assert totals["current"] == Decimal("250.00")
        assert totals["d31_60"] == Decimal("0")

    def test_fully_paid_invoice_excluded_from_aging(self, tenant_a, customer_party, usd):
        """An invoice whose amount equals paid_agg should be excluded (balance <= 0)."""
        from apps.accounting.views import _aging
        today = datetime.date(2026, 3, 1)
        due = today - datetime.timedelta(days=10)

        inv = self._make_invoice(tenant_a, customer_party, due, Decimal("300.00"), usd)
        inv.paid_agg = Decimal("300.00")  # fully paid

        _, totals = _aging([inv], "due_date", today)
        assert totals["total"] == Decimal("0")

    def test_ar_aging_view_accessible(self, client_a):
        """AR aging view returns 200."""
        url = reverse("accounting:ar_aging")
        resp = client_a.get(url)
        assert resp.status_code == 200

    def test_ap_aging_view_accessible(self, client_a):
        """AP aging view returns 200."""
        url = reverse("accounting:ap_aging")
        resp = client_a.get(url)
        assert resp.status_code == 200
