"""Tests for the 2.1 cash-flow forecast (accounting:cash_forecast) and the navigation
``name#fragment`` deep-link support added for the 2.1 dashboard widgets."""
import datetime
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.accounting.models import Bill, BillLine, Invoice, InvoiceLine

pytestmark = pytest.mark.django_db


# ----------------------------------------------------------------- helpers
def _open_invoice(tenant, party, usd, total, due, status="sent"):
    inv = Invoice.objects.create(
        tenant=tenant, party=party, issue_date=due - datetime.timedelta(days=30),
        due_date=due, status=status, currency=usd)
    InvoiceLine.objects.create(invoice=inv, description="x", quantity=Decimal("1"),
                               unit_price=Decimal(total))
    inv.recalc_totals()
    return inv


def _open_bill(tenant, party, usd, total, due, status="approved"):
    bill = Bill.objects.create(
        tenant=tenant, party=party, bill_date=due - datetime.timedelta(days=30),
        due_date=due, status=status, currency=usd)
    BillLine.objects.create(bill=bill, description="x", quantity=Decimal("1"),
                            unit_price=Decimal(total))
    bill.recalc_totals()
    return bill


def _ctx(client):
    resp = client.get(reverse("accounting:cash_forecast"))
    assert resp.status_code == 200
    return resp.context


# ----------------------------------------------------------------- view basics
def test_forecast_renders_200(client_a):
    assert client_a.get(reverse("accounting:cash_forecast")).status_code == 200


def test_forecast_login_required(client):
    resp = client.get(reverse("accounting:cash_forecast"))
    assert resp.status_code in (302, 301)
    assert "/login" in resp.url


def test_weeks_param_clamped_and_defaulted(client_a):
    assert _ctx_weeks(client_a, None) == 13          # default
    assert _ctx_weeks(client_a, "8") == 8
    assert _ctx_weeks(client_a, "1000") == 52         # upper clamp
    assert _ctx_weeks(client_a, "1") == 4             # lower clamp
    assert _ctx_weeks(client_a, "bogus") == 13        # bad input -> default, no 500
    # row count tracks the horizon
    resp = client_a.get(reverse("accounting:cash_forecast"), {"weeks": "8"})
    assert len(resp.context["rows"]) == 8


def _ctx_weeks(client, weeks):
    params = {} if weeks is None else {"weeks": weeks}
    resp = client.get(reverse("accounting:cash_forecast"), params)
    assert resp.status_code == 200
    return resp.context["weeks"]


def test_no_tenant_is_empty_not_error(rf, admin_user):
    """A user with no tenant gets a 200 with a flat/empty projection (by design)."""
    from apps.accounting.views import cash_forecast
    req = rf.get(reverse("accounting:cash_forecast"))
    req.user = admin_user
    req.tenant = None
    resp = cash_forecast(req)
    assert resp.status_code == 200
    assert b"no tenant" in resp.content  # the empty-state notice rendered


# ----------------------------------------------------------------- projection math
def test_opening_equals_cash_position(client_a, bank_account):
    from apps.accounting.views import _cash_position
    ctx = _ctx(client_a)
    assert ctx["stats"]["opening"] == _cash_position(bank_account.tenant)
    assert ctx["stats"]["opening"] == Decimal("1000.00")  # the bank_account fixture opening


def test_open_ar_becomes_inflow_open_ap_becomes_outflow(client_a, tenant_a, customer_party,
                                                        vendor_party, usd, bank_account):
    from django.utils import timezone
    today = timezone.localdate()
    _open_invoice(tenant_a, customer_party, usd, "500", today + datetime.timedelta(weeks=2))
    _open_bill(tenant_a, vendor_party, usd, "200", today + datetime.timedelta(weeks=3))
    ctx = _ctx(client_a)
    s = ctx["stats"]
    assert s["inflow"] == Decimal("500")
    assert s["outflow"] == Decimal("200")
    assert s["projected"] == Decimal("1000") + Decimal("500") - Decimal("200")  # 1300
    # lowest projected balance never drops below the opening here (inflow precedes outflow)
    assert s["low_balance"] == Decimal("1000")


def test_overdue_rolls_into_first_week(client_a, tenant_a, customer_party, usd, bank_account):
    from django.utils import timezone
    today = timezone.localdate()
    _open_invoice(tenant_a, customer_party, usd, "300", today - datetime.timedelta(days=20))
    ctx = _ctx(client_a)
    assert ctx["rows"][0]["inflow"] == Decimal("300")   # week 0 catches the overdue invoice
    assert ctx["stats"]["inflow"] == Decimal("300")


def test_beyond_horizon_reported_separately(client_a, tenant_a, customer_party, usd, bank_account):
    from django.utils import timezone
    today = timezone.localdate()
    _open_invoice(tenant_a, customer_party, usd, "777", today + datetime.timedelta(weeks=40))
    ctx = _ctx(client_a)  # default horizon 13 weeks
    assert ctx["stats"]["beyond_inflow"] == Decimal("777")
    assert ctx["stats"]["inflow"] == Decimal("0")        # not double-counted in the buckets


def test_draft_invoice_excluded(client_a, tenant_a, customer_party, usd, bank_account):
    from django.utils import timezone
    today = timezone.localdate()
    _open_invoice(tenant_a, customer_party, usd, "999", today + datetime.timedelta(weeks=1),
                  status="draft")  # draft is NOT an OPEN status
    ctx = _ctx(client_a)
    assert ctx["stats"]["inflow"] == Decimal("0")


def test_low_balance_flags_negative(client_a, tenant_a, vendor_party, usd, bank_account):
    from django.utils import timezone
    today = timezone.localdate()
    # A big bill beyond the opening cash drives the projection negative.
    _open_bill(tenant_a, vendor_party, usd, "5000", today + datetime.timedelta(weeks=1))
    ctx = _ctx(client_a)
    assert ctx["stats"]["projected"] == Decimal("1000") - Decimal("5000")  # -4000
    assert ctx["stats"]["low_balance"] < 0


# ----------------------------------------------------------------- multi-tenant isolation
def test_other_tenant_docs_excluded(client_a, tenant_b, party_b, usd, bank_account):
    """tenant_b's open invoice must not appear in tenant_a's forecast."""
    from django.utils import timezone
    today = timezone.localdate()
    _open_invoice(tenant_b, party_b, usd, "12345", today + datetime.timedelta(weeks=2))
    ctx = _ctx(client_a)
    assert ctx["stats"]["inflow"] == Decimal("0")
    assert ctx["stats"]["beyond_inflow"] == Decimal("0")


# ----------------------------------------------------------------- navigation fragment support
def test_safe_reverse_handles_fragment():
    from apps.core.navigation import _safe_reverse
    assert _safe_reverse("accounting:accounting_dashboard#cash-flow") == "/accounting/#cash-flow"
    assert _safe_reverse("accounting:accounting_dashboard") == "/accounting/"
    assert _safe_reverse("accounting:does_not_exist") is None
    assert _safe_reverse("") is None


def test_is_active_matches_route_ignoring_fragment():
    from apps.core.navigation import _is_active
    assert _is_active("accounting:accounting_dashboard#cash-flow", "accounting:accounting_dashboard")
    assert _is_active("accounting:accounting_dashboard#alert-center", "accounting:accounting_dashboard")
    # a different route does not match
    assert not _is_active("accounting:cash_forecast#x", "accounting:accounting_dashboard")
    # CRUD-subroute matching still works on the plain name
    assert _is_active("accounting:invoice_list", "accounting:invoice_detail")


def test_2_1_widgets_resolve_to_distinct_urls():
    from apps.core.navigation import LIVE_LINKS, _safe_reverse
    urls = {label: _safe_reverse(v) for label, v in LIVE_LINKS["2.1"].items()}
    # the four dashboard widgets now point at distinct anchors, not one identical URL
    widget_urls = [urls["Executive Summary"], urls["Cash Flow Widget"],
                   urls["Alert Center"], urls["Quick Actions"]]
    assert len(set(widget_urls)) == 4
    # Forecasting is now Live (resolves) rather than a roadmap placeholder
    assert urls["Forecasting"] == "/accounting/reports/cash-forecast/"
