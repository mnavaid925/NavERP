"""Tests for the 2.4 Recurring Invoicing feature, the 2.3 Payment Schedule report, and the
navigation ``?query`` / ``#fragment`` deep-link support used to wire the Accounting sidebar."""
import datetime
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.accounting.models import (
    Bill, BillLine, Invoice, PaymentTerm, RecurringInvoice, add_months,
)

pytestmark = pytest.mark.django_db


# ----------------------------------------------------------------- add_months / advance
def test_add_months_clamps_to_month_end():
    assert add_months(datetime.date(2026, 1, 31), 1) == datetime.date(2026, 2, 28)  # non-leap
    assert add_months(datetime.date(2024, 1, 31), 1) == datetime.date(2024, 2, 29)  # leap
    assert add_months(datetime.date(2026, 12, 15), 1) == datetime.date(2027, 1, 15)  # year rollover
    assert add_months(datetime.date(2026, 3, 31), 3) == datetime.date(2026, 6, 30)


@pytest.mark.parametrize("cadence,start,expected", [
    ("weekly", datetime.date(2026, 1, 1), datetime.date(2026, 1, 8)),
    ("monthly", datetime.date(2026, 1, 15), datetime.date(2026, 2, 15)),
    ("quarterly", datetime.date(2026, 1, 15), datetime.date(2026, 4, 15)),
    ("annually", datetime.date(2026, 1, 15), datetime.date(2027, 1, 15)),
])
def test_run_date_for_one_step(tenant_a, customer_party, cadence, start, expected):
    rec = RecurringInvoice.objects.create(
        tenant=tenant_a, party=customer_party, description="x", amount=Decimal("100"),
        cadence=cadence, start_date=start)
    assert rec.next_run_date == start          # save() defaulted next_run to start
    assert rec.run_date_for(0) == start
    assert rec.run_date_for(1) == expected


def test_run_date_for_anchors_month_end(tenant_a, customer_party):
    """A month-end schedule keeps its day-of-month instead of drifting earlier (review F3)."""
    rec = RecurringInvoice.objects.create(
        tenant=tenant_a, party=customer_party, description="x", amount=Decimal("100"),
        cadence="monthly", start_date=datetime.date(2026, 1, 31))
    assert rec.run_date_for(1) == datetime.date(2026, 2, 28)
    assert rec.run_date_for(2) == datetime.date(2026, 3, 31)  # anchored back to 31, not 28
    assert rec.run_date_for(3) == datetime.date(2026, 4, 30)


def test_number_assigned_and_next_run_defaults(tenant_a, customer_party):
    rec = RecurringInvoice.objects.create(
        tenant=tenant_a, party=customer_party, description="Sub", amount=Decimal("50"),
        cadence="monthly", start_date=datetime.date(2026, 5, 1))
    assert rec.number.startswith("RINV-")
    assert rec.next_run_date == datetime.date(2026, 5, 1)


# ----------------------------------------------------------------- CRUD + generate
def _rec(tenant, party, **kw):
    return RecurringInvoice.objects.create(
        tenant=tenant, party=party, description=kw.get("description", "Monthly sub"),
        amount=kw.get("amount", Decimal("750")), cadence=kw.get("cadence", "monthly"),
        start_date=kw.get("start_date", datetime.date(2026, 1, 1)),
        status=kw.get("status", "active"))


def test_pages_render(client_a, tenant_a, customer_party):
    rec = _rec(tenant_a, customer_party)
    for name, args in [("recurringinvoice_list", []), ("recurringinvoice_create", []),
                       ("recurringinvoice_detail", [rec.pk]), ("recurringinvoice_edit", [rec.pk]),
                       ("payment_schedule", [])]:
        assert client_a.get(reverse("accounting:" + name, args=args)).status_code == 200


def test_generate_creates_invoice_and_advances(client_a, tenant_a, customer_party):
    rec = _rec(tenant_a, customer_party, amount=Decimal("750"), start_date=datetime.date(2026, 1, 1))
    before = Invoice.objects.filter(tenant=tenant_a).count()
    resp = client_a.post(reverse("accounting:recurringinvoice_generate", args=[rec.pk]))
    assert resp.status_code == 302
    rec.refresh_from_db()
    assert Invoice.objects.filter(tenant=tenant_a).count() == before + 1
    assert rec.occurrences_generated == 1
    assert rec.last_generated_at is not None
    assert rec.next_run_date == datetime.date(2026, 2, 1)  # advanced one month
    inv = Invoice.objects.filter(tenant=tenant_a).order_by("-id").first()
    assert inv.status == "draft"
    assert inv.party_id == customer_party.pk
    assert inv.total == Decimal("750.00")  # one line, qty 1 * 750, no tax
    assert inv.recurring_invoice_id == rec.pk  # authoritative FK link


def test_edit_blank_next_run_preserves_value(client_a, tenant_a, customer_party):
    """Clearing Next Run while editing keeps the current value, not a rewind to start (review F2)."""
    rec = _rec(tenant_a, customer_party, start_date=datetime.date(2026, 1, 1))
    rec.next_run_date = datetime.date(2026, 6, 1)
    rec.save(update_fields=["next_run_date"])
    resp = client_a.post(reverse("accounting:recurringinvoice_edit", args=[rec.pk]), {
        "party": customer_party.pk, "description": rec.description, "amount": "750",
        "cadence": "monthly", "start_date": "2026-01-01", "status": "active", "next_run_date": ""})
    assert resp.status_code == 302
    rec.refresh_from_db()
    assert rec.next_run_date == datetime.date(2026, 6, 1)  # preserved, not snapped to 2026-01-01


def test_generated_link_uses_fk_not_notes(client_a, tenant_a, customer_party):
    """The generated-invoices list is FK-based, so an invoice merely mentioning the schedule
    number in its (user-editable) notes is NOT listed (review F5/F6)."""
    rec = _rec(tenant_a, customer_party)
    client_a.post(reverse("accounting:recurringinvoice_generate", args=[rec.pk]))
    Invoice.objects.create(tenant=tenant_a, party=customer_party, kind="invoice",
                           issue_date=datetime.date(2026, 1, 1), status="draft",
                           notes=f"mentions schedule {rec.number} but was not generated")
    gen = client_a.get(reverse("accounting:recurringinvoice_detail", args=[rec.pk])).context["generated"]
    assert len(gen) == 1
    assert all(i.recurring_invoice_id == rec.pk for i in gen)


def test_generate_blocked_when_not_active(client_a, tenant_a, customer_party):
    rec = _rec(tenant_a, customer_party, status="paused")
    before = Invoice.objects.filter(tenant=tenant_a).count()
    client_a.post(reverse("accounting:recurringinvoice_generate", args=[rec.pk]))
    rec.refresh_from_db()
    assert Invoice.objects.filter(tenant=tenant_a).count() == before  # nothing generated
    assert rec.occurrences_generated == 0


def test_detail_lists_only_its_generated_invoices(client_a, tenant_a, customer_party):
    rec = _rec(tenant_a, customer_party)
    client_a.post(reverse("accounting:recurringinvoice_generate", args=[rec.pk]))
    resp = client_a.get(reverse("accounting:recurringinvoice_detail", args=[rec.pk]))
    gen = resp.context["generated"]
    assert len(gen) == 1
    assert f"schedule {rec.number}" in gen[0].notes


def test_recurring_idor_404(client_a, tenant_b, party_b):
    other = _rec(tenant_b, party_b)
    for name in ["recurringinvoice_detail", "recurringinvoice_edit"]:
        assert client_a.get(reverse("accounting:" + name, args=[other.pk])).status_code == 404
    assert client_a.post(reverse("accounting:recurringinvoice_generate", args=[other.pk])).status_code == 404
    assert client_a.post(reverse("accounting:recurringinvoice_delete", args=[other.pk])).status_code == 404


# ----------------------------------------------------------------- payment schedule
def _open_bill(tenant, party, total, due, term=None, bill_date=None):
    bill = Bill.objects.create(
        tenant=tenant, party=party, bill_date=bill_date or (due - datetime.timedelta(days=30)),
        due_date=due, status="approved", payment_terms=term)
    BillLine.objects.create(bill=bill, description="x", quantity=Decimal("1"), unit_price=Decimal(total))
    bill.recalc_totals()
    return bill


def test_payment_schedule_lists_open_bills(client_a, tenant_a, vendor_party):
    from django.utils import timezone
    today = timezone.localdate()
    _open_bill(tenant_a, vendor_party, "1000", today + datetime.timedelta(days=10))
    ctx = client_a.get(reverse("accounting:payment_schedule")).context
    assert ctx["totals"]["outstanding"] == Decimal("1000")
    assert ctx["totals"]["net"] == Decimal("1000")  # no discount term
    assert len(ctx["rows"]) == 1


def test_payment_schedule_applies_capturable_discount(client_a, tenant_a, vendor_party):
    from django.utils import timezone
    today = timezone.localdate()
    term = PaymentTerm.objects.create(tenant=tenant_a, name="2/10 Net 30", days_due=30,
                                      discount_pct=Decimal("2"), discount_days=10)
    # bill dated today -> discount deadline today+10 is still capturable
    _open_bill(tenant_a, vendor_party, "1000", today + datetime.timedelta(days=30),
               term=term, bill_date=today)
    row = client_a.get(reverse("accounting:payment_schedule")).context["rows"][0]
    assert row["discount"] == Decimal("20.00")          # 2% of 1000
    assert row["net"] == Decimal("980.00")
    assert row["suggested"] == today + datetime.timedelta(days=10)  # discount deadline


def test_payment_schedule_no_discount_when_window_passed(client_a, tenant_a, vendor_party):
    from django.utils import timezone
    today = timezone.localdate()
    term = PaymentTerm.objects.create(tenant=tenant_a, name="2/10 Net 30", days_due=30,
                                      discount_pct=Decimal("2"), discount_days=10)
    # bill dated 40 days ago -> discount deadline (30 days ago) has passed
    _open_bill(tenant_a, vendor_party, "1000", today - datetime.timedelta(days=10),
               term=term, bill_date=today - datetime.timedelta(days=40))
    row = client_a.get(reverse("accounting:payment_schedule")).context["rows"][0]
    assert row["discount"] == Decimal("0")
    assert row["overdue"] is True


def test_payment_schedule_renders_due_date(client_a, tenant_a, vendor_party):
    """The Due Date column must render the bill's date, not a blank cell (review F1)."""
    due = datetime.date(2026, 5, 10)
    _open_bill(tenant_a, vendor_party, "1000", due, bill_date=datetime.date(2026, 4, 10))
    resp = client_a.get(reverse("accounting:payment_schedule"))
    assert b"May 10, 2026" in resp.content  # Django "M d, Y" of the bill due date


def test_payment_schedule_excludes_other_tenant(client_a, tenant_b, party_b):
    from django.utils import timezone
    _open_bill(tenant_b, party_b, "9999", timezone.localdate() + datetime.timedelta(days=5))
    ctx = client_a.get(reverse("accounting:payment_schedule")).context
    assert ctx["totals"]["outstanding"] == Decimal("0")
    assert ctx["rows"] == []


# ----------------------------------------------------------------- navigation deep-links
def test_nav_route_name_strips_query_and_fragment():
    from apps.core.navigation import _route_name
    assert _route_name("a:b?category=crm") == ("a:b", "?category=crm")
    assert _route_name("a:b#sec") == ("a:b", "#sec")
    assert _route_name("a:b") == ("a:b", "")


def test_nav_safe_reverse_query_and_fragment():
    from apps.core.navigation import _safe_reverse
    assert _safe_reverse("accounting:integration_list?category=crm") == "/accounting/integrations/?category=crm"
    assert _safe_reverse("accounting:accounting_dashboard#cash-flow") == "/accounting/#cash-flow"
    assert _safe_reverse("accounting:nope?x=1") is None


def test_nav_is_active_ignores_suffix():
    from apps.core.navigation import _is_active
    assert _is_active("accounting:integration_list?category=crm", "accounting:integration_list")
    assert _is_active("accounting:integration_list?category=crm", "accounting:integration_detail")


def test_module2_wires_resolve():
    from apps.core.navigation import LIVE_LINKS, _safe_reverse
    # the newly-wired bullets all resolve to real hrefs
    checks = {
        ("2.2", "Allocation Rules"): "/accounting/cost-allocations/",
        ("2.5", "Treasury Forecasting"): "/accounting/reports/cash-forecast/",
        ("2.8", "Employee Master"): "/hrm/employees/",
        ("2.4", "Recurring Invoicing"): "/accounting/recurring-invoices/",
        ("2.3", "Payment Scheduling"): "/accounting/reports/payment-schedule/",
        ("2.15", "CRM"): "/accounting/integrations/?category=crm",
    }
    for (sub, label), expected in checks.items():
        assert _safe_reverse(LIVE_LINKS[sub][label]) == expected
