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
def test_advance_per_cadence(tenant_a, customer_party, cadence, start, expected):
    rec = RecurringInvoice.objects.create(
        tenant=tenant_a, party=customer_party, description="x", amount=Decimal("100"),
        cadence=cadence, start_date=start)
    assert rec.next_run_date == start  # save() defaulted next_run to start
    rec.advance()
    assert rec.next_run_date == expected


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
    assert f"schedule {rec.number}" in inv.notes


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
