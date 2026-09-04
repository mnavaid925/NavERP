"""Procurement 6.15 Budget & Cost Management - isolation & hardening tests.

The defensive half of the 6.15 suite. Every test here asks the same question from a different
angle: *can a caller reach another workspace's budget mapping or frozen forecast - or coerce a
computed page into leaking one - and does a hand-edited query string or crafted POST ever reach
a 500 instead of a clean page or a field error?*

Laid out in six sections:

1. **Cross-tenant IDOR** - every pk-scoped 6.15 route aimed at another workspace's pk returns
   **404** (detail/edit/delete on mappings, detail/delete on forecasts), the delete attempt
   leaves the foreign row byte-identical, and the owning workspace still reaches its own row.
2. **Register isolation** - ``budgetmapping_list`` and ``costforecast_list`` never contain the
   other workspace's rows.
3. **Computed-page isolation** - the availability checker, the commitment register, the variance
   report and its CSV export resolve a FOREIGN budget pk through tenant-scoped querysets, so it
   selects NOTHING: an empty state (checker) or an unscoped-but-still-tenant-A page, never a
   leaked figure and never a 500.
4. **Crafted POSTs** - another workspace's pk in every tenant-scoped FK on both create forms
   lands as a FIELD error and saves nothing; a valid POST does save (L44); and a forecast's three
   amount columns are stamped server-side from ``compute_forecast_amounts`` - the POSTed copies
   are ignored, and ``created_by`` comes from ``request.user``.
5. **The authz ladder** - anonymous redirects to ``/login/`` on all 13 routes; CSRF is enforced
   on the two mutating POSTs; a GET on a ``@require_POST`` delete verb is 405 and mutates nothing.
6. **Hostile input** - junk FK / enum / decimal GET params on all five list-and-computed pages
   return **200 never 500** (L11), each paired with the POSITIVE filter path proving the guard
   did not simply break the feature (L44).

All dates derive from ``timezone.localdate()`` (never ``date.today()``) so nothing here flakes
in the hours after local midnight (L16). Domain rows are built inside this file via the local
``_budgetcost_*`` helpers.
"""
import datetime
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.accounting.models import Budget, BudgetLine, FiscalPeriod, GLAccount, Project
from apps.core.models import OrgUnit, Party
from apps.procurement.models import BudgetMapping, CostForecast, compute_forecast_amounts
from apps.scm.models import (
    PurchaseOrder,
    PurchaseOrderLine,
    PurchaseRequisition,
    PurchaseRequisitionLine,
)

pytestmark = pytest.mark.django_db


# ------------------------------------------------------------------ helpers (module-private)
def _budgetcost_gl(tenant, code="6000", name="Office Supplies"):
    return GLAccount.objects.create(tenant=tenant, code=code, name=name,
                                    account_type="expense")


def _budgetcost_org(tenant, name="Operations"):
    return OrgUnit.objects.create(tenant=tenant, name=name)


def _budgetcost_project(tenant, name="Nav rollout"):
    return Project.objects.create(tenant=tenant, name=name)


def _budgetcost_period(tenant, name="FY26-Q1"):
    return FiscalPeriod.objects.create(
        tenant=tenant, name=name, period_type="quarter",
        start_date=timezone.localdate() - datetime.timedelta(days=30),
        end_date=timezone.localdate() + datetime.timedelta(days=60))


def _budgetcost_budget(tenant, name="Ops budget", fiscal_period=None):
    return Budget.objects.create(tenant=tenant, name=name, fiscal_period=fiscal_period)


def _budgetcost_line(budget, gl, amount="10000.00", org_unit=None):
    return BudgetLine.objects.create(tenant=budget.tenant, budget=budget, gl_account=gl,
                                     org_unit=org_unit, amount=Decimal(amount))


def _budgetcost_party(tenant, name="Northwind"):
    return Party.objects.create(tenant=tenant, name=name, kind="organization")


def _budgetcost_mapping(tenant, budget, **overrides):
    fields = dict(tenant=tenant, budget=budget, notes="Workspace mapping.")
    fields.update(overrides)
    return BudgetMapping.objects.create(**fields)


def _budgetcost_forecast(tenant, name="Q3 ops spend projection", **overrides):
    fields = dict(tenant=tenant, name=name, method="blended", horizon_months=3,
                  as_of=timezone.localdate(), assumptions="Frozen by the test suite.")
    fields.update(overrides)
    return CostForecast.objects.create(**fields)


def _budgetcost_pr(tenant, requester, status="approved", budget=None, org_unit=None,
                   title="Office supplies"):
    return PurchaseRequisition.objects.create(
        tenant=tenant, title=title, requester=requester, status=status, budget=budget,
        org_unit=org_unit, required_by=timezone.localdate() + datetime.timedelta(days=10),
        justification="Raised by the security suite.")


def _budgetcost_pr_line(pr, gl=None, qty="4", price="25.00"):
    line = PurchaseRequisitionLine.objects.create(
        requisition=pr, item_description="A4 printer paper", quantity=Decimal(qty),
        estimated_unit_price=Decimal(price), gl_account=gl)
    return line


def _budgetcost_po(tenant, vendor, requisition=None, status="approved"):
    return PurchaseOrder.objects.create(tenant=tenant, vendor=vendor, requisition=requisition,
                                        status=status, order_date=timezone.localdate())


def _budgetcost_po_line(po, gl=None, qty="3", price="50.00"):
    return PurchaseOrderLine.objects.create(
        purchase_order=po, item_description="Desk chairs", quantity=Decimal(qty),
        unit_price=Decimal(price), gl_account=gl)


def _budgetcost_mapping_payload(**overrides):
    """A complete, valid ``BudgetMappingForm`` POST body - every FK blank unless supplied."""
    payload = {"budget": "", "org_unit": "", "project": "", "default_gl_account": "",
               "priority": "100", "is_active": "on", "notes": "Crafted mapping."}
    payload.update(overrides)
    return payload


def _budgetcost_forecast_payload(**overrides):
    """A complete, valid ``CostForecastForm`` POST body (amounts are NOT fields - they are
    stamped server-side; the freeze test below rides forged copies along anyway)."""
    payload = {"name": "Crafted forecast", "budget": "", "method": "open_pos",
               "horizon_months": "3", "as_of": timezone.localdate().isoformat(),
               "currency": "", "assumptions": "Crafted assumptions."}
    payload.update(overrides)
    return payload


def _budgetcost_row_urls(resp):
    """The commitment register's row urls - pk-bearing, so per-tenant number collisions
    (both workspaces' first PO is PO-00001) cannot falsify an isolation assertion."""
    return {row["url"] for row in resp.context["rows"]}


# ==================================================================== 1. cross-tenant IDOR
def test_budgetcost_foreign_mapping_pk_404_on_detail_edit_delete(
        client_a, client_b, tenant_a, tenant_b):
    """Logged in as tenant A, tenant B's mapping pk is a 404 on detail, edit AND delete - the
    delete attempt included - and the foreign row survives the attempt byte-identical."""
    budget_a = _budgetcost_budget(tenant_a, "Acme ops budget")
    budget_b = _budgetcost_budget(tenant_b, "Globex ops budget")
    mapping_a = _budgetcost_mapping(tenant_a, budget_a)
    mapping_b = _budgetcost_mapping(tenant_b, budget_b,
                                    org_unit=_budgetcost_org(tenant_b, "Globex Facilities"))

    assert client_a.get(
        reverse("procurement:budgetmapping_detail", args=[mapping_b.pk])).status_code == 404
    assert client_a.get(
        reverse("procurement:budgetmapping_edit", args=[mapping_b.pk])).status_code == 404
    assert client_a.post(
        reverse("procurement:budgetmapping_delete", args=[mapping_b.pk])).status_code == 404

    # B's row survived the delete attempt, still owned by B.
    assert BudgetMapping.objects.filter(pk=mapping_b.pk, tenant=tenant_b).exists()

    # L44 pair: the guard narrows ONLY across the boundary - B still reaches its own row,
    # and A reaches its own.
    assert client_b.get(
        reverse("procurement:budgetmapping_detail", args=[mapping_b.pk])).status_code == 200
    assert client_a.get(
        reverse("procurement:budgetmapping_detail", args=[mapping_a.pk])).status_code == 200


def test_budgetcost_foreign_forecast_pk_404_on_detail_delete(client_a, client_b, tenant_a,
                                                             tenant_b):
    """Tenant B's frozen forecast is a 404 on A's detail and delete routes, and survives the
    delete attempt - a forecast is frozen, and no stranger unfreezes it."""
    forecast_a = _budgetcost_forecast(tenant_a, name="Acme Q3 projection")
    forecast_b = _budgetcost_forecast(tenant_b, name="Globex-only forecast")

    assert client_a.get(
        reverse("procurement:costforecast_detail", args=[forecast_b.pk])).status_code == 404
    assert client_a.post(
        reverse("procurement:costforecast_delete", args=[forecast_b.pk])).status_code == 404

    assert CostForecast.objects.filter(pk=forecast_b.pk, tenant=tenant_b).exists()

    # L44 pair: each workspace still reads its own forecast.
    assert client_b.get(
        reverse("procurement:costforecast_detail", args=[forecast_b.pk])).status_code == 200
    assert client_a.get(
        reverse("procurement:costforecast_detail", args=[forecast_a.pk])).status_code == 200


# ==================================================================== 2. register isolation
def test_budgetcost_mapping_list_never_contains_foreign_rows(client_a, client_b, tenant_a,
                                                             tenant_b):
    """A's mapping register renders A's rows only - B's mapping (and its budget's name) never
    reaches the page, by content and by the exact object_list."""
    budget_a = _budgetcost_budget(tenant_a, "Acme ops budget")
    budget_b = _budgetcost_budget(tenant_b, "Globex ops budget")
    mapping_a = _budgetcost_mapping(tenant_a, budget_a,
                                    org_unit=_budgetcost_org(tenant_a, "Acme Facilities"))
    mapping_b = _budgetcost_mapping(tenant_b, budget_b)

    resp = client_a.get(reverse("procurement:budgetmapping_list"))
    assert resp.status_code == 200
    assert [row.pk for row in resp.context["object_list"]] == [mapping_a.pk]
    content = resp.content.decode()
    assert budget_a.name in content
    assert budget_b.name not in content

    # L44 pair: B's own register shows B's row.
    resp_b = client_b.get(reverse("procurement:budgetmapping_list"))
    assert [row.pk for row in resp_b.context["object_list"]] == [mapping_b.pk]


def test_budgetcost_forecast_list_never_contains_foreign_rows(client_a, client_b, tenant_a,
                                                              tenant_b):
    """A's forecast register renders A's frozen projections only - never B's name or row."""
    forecast_a = _budgetcost_forecast(tenant_a, name="Acme Q3 projection")
    forecast_b = _budgetcost_forecast(tenant_b, name="Globex-only forecast")

    resp = client_a.get(reverse("procurement:costforecast_list"))
    assert resp.status_code == 200
    assert [row.pk for row in resp.context["object_list"]] == [forecast_a.pk]
    content = resp.content.decode()
    assert forecast_a.name in content
    assert forecast_b.name not in content

    # L44 pair: B's own register shows B's forecast.
    resp_b = client_b.get(reverse("procurement:costforecast_list"))
    assert [row.pk for row in resp_b.context["object_list"]] == [forecast_b.pk]


# ==================================================================== 3. computed-page isolation
def test_budgetcost_availability_foreign_budget_selects_nothing(
        client_a, admin_user, tenant_a, tenant_b):
    """The checker resolves the budget THROUGH the tenant-scoped queryset: B's budget pk
    selects nothing - empty-state page, no figures, 200 not 500 - while A's own pk renders
    exact figures (the L44 pair)."""
    gl_a = _budgetcost_gl(tenant_a)
    org_a = _budgetcost_org(tenant_a)
    budget_a = _budgetcost_budget(tenant_a, "Acme ops budget")
    budget_b = _budgetcost_budget(tenant_b, "Globex ops budget")
    _budgetcost_line(budget_a, gl_a)  # no org unit -> company-wide line

    # Commitment spine for the positive path: an open PO behind an approved requisition,
    # an approved-but-unconverted requisition, and a pending one (the pipeline).
    vendor = _budgetcost_party(tenant_a)
    pr_approved = _budgetcost_pr(tenant_a, admin_user, status="approved", budget=budget_a,
                                 org_unit=org_a)
    _budgetcost_pr_line(pr_approved, gl=gl_a, qty="4", price="25.00")
    pr_approved.recalc_totals()
    pr_pending = _budgetcost_pr(tenant_a, admin_user, status="pending_approval",
                                budget=budget_a, title="Lab consumables")
    _budgetcost_pr_line(pr_pending, gl=gl_a, qty="2", price="20.00")
    pr_pending.recalc_totals()
    po = _budgetcost_po(tenant_a, vendor, requisition=pr_approved)
    _budgetcost_po_line(po, gl=gl_a, qty="3", price="50.00")

    url = reverse("procurement:budget_availability")

    # Foreign budget pk -> nothing selected, no figures, nothing of B's on the page.
    resp = client_a.get(url, {"budget": str(budget_b.pk)})
    assert resp.status_code == 200
    assert resp.context["selected_budget"] is None
    assert resp.context["figures"] is None
    assert budget_b.name not in resp.content.decode()

    # A foreign org-unit pk narrows nothing either - the figures are the unscoped ones.
    org_b = _budgetcost_org(tenant_b, "Globex Facilities")
    resp = client_a.get(url, {"budget": str(budget_a.pk), "org_unit": str(org_b.pk)})
    assert resp.status_code == 200
    assert resp.context["selected_org_unit"] is None
    assert resp.context["figures"]["remaining"] == Decimal("9710.00")

    # L44 pair: A's own budget pk renders exact like-for-like figures.
    resp = client_a.get(url, {"budget": str(budget_a.pk), "amount": "250.00"})
    assert resp.status_code == 200
    figures = resp.context["figures"]
    assert figures is not None
    assert figures["budgeted"] == Decimal("10000.00")
    assert figures["po_committed"] == Decimal("150.00")
    assert figures["pr_committed"] == Decimal("100.00")
    assert figures["requested"] == Decimal("40.00")
    assert figures["check_amount"] == Decimal("250.00")
    assert figures["remaining"] == Decimal("9460.00")
    assert figures["over_budget"] is False


def test_budgetcost_availability_junk_params_return_200(client_a, tenant_a, tenant_b):
    """L11: junk pks, NaN, negative and non-finite amounts all skip their filter instead of
    500ing - and the positive path proves the checker still computes (L44)."""
    gl_a = _budgetcost_gl(tenant_a)
    budget_a = _budgetcost_budget(tenant_a, "Acme ops budget")
    _budgetcost_line(budget_a, gl_a)
    _budgetcost_budget(tenant_b, "Globex ops budget")
    url = reverse("procurement:budget_availability")

    resp = client_a.get(url, {"budget": "abc", "amount": "NaN", "org_unit": "xyz"})
    assert resp.status_code == 200
    assert resp.context["figures"] is None  # junk budget selects nothing -> empty state

    for bad_amount in ("-5", "Infinity"):
        resp = client_a.get(url, {"budget": str(budget_a.pk), "amount": bad_amount})
        assert resp.status_code == 200, bad_amount
        # Junk amount is SKIPPED: figures are computed with zero spend, input echoes empty.
        assert resp.context["check_amount"] == "", bad_amount
        assert resp.context["figures"]["remaining"] == Decimal("10000.00"), bad_amount

    # L44 pair: a clean amount is honoured to the cent.
    resp = client_a.get(url, {"budget": str(budget_a.pk), "amount": "250.00"})
    assert resp.status_code == 200
    assert resp.context["check_amount"] == "250.00"
    assert resp.context["figures"]["remaining"] == Decimal("9750.00")


def test_budgetcost_register_foreign_budget_leaks_nothing(client_a, admin_user, tenant_a,
                                                          tenant_b):
    """A foreign budget pk on the commitment register selects nothing (no budget narrowing),
    and the page is tenant-A's commitments only - B's purchase order never appears."""
    budget_a = _budgetcost_budget(tenant_a, "Acme ops budget")
    budget_b = _budgetcost_budget(tenant_b, "Globex ops budget")

    vendor_a = _budgetcost_party(tenant_a)
    pr_a = _budgetcost_pr(tenant_a, admin_user, status="approved", budget=budget_a)
    _budgetcost_pr_line(pr_a, qty="4", price="25.00")
    pr_a.recalc_totals()
    po_a = _budgetcost_po(tenant_a, vendor_a, requisition=pr_a)
    _budgetcost_po_line(po_a, qty="3", price="50.00")
    po_free = _budgetcost_po(tenant_a, vendor_a)  # no requisition -> no budget link
    _budgetcost_po_line(po_free, qty="1", price="80.00")

    po_b = _budgetcost_po(tenant_b, _budgetcost_party(tenant_b, "Globex Freight"))
    _budgetcost_po_line(po_b, qty="6", price="80.00")

    po_url = lambda po: reverse("scm:purchaseorder_detail", args=[po.pk])  # noqa: E731
    pr_url = reverse("procurement:req_detail", args=[pr_a.pk])
    url = reverse("procurement:commitment_register")

    resp = client_a.get(url, {"budget": str(budget_b.pk)})
    assert resp.status_code == 200
    assert resp.context["selected_budget"] is None  # the foreign pk selected nothing
    row_urls = _budgetcost_row_urls(resp)
    assert row_urls == {po_url(po_a), po_url(po_free), pr_url}
    assert po_url(po_b) not in row_urls
    assert budget_b.name not in resp.content.decode()

    # L44 pair: A's own budget pk narrows to the commitments linked to it (the budget-less
    # PO drops out).
    resp = client_a.get(url, {"budget": str(budget_a.pk)})
    assert resp.status_code == 200
    assert resp.context["selected_budget"].pk == budget_a.pk
    assert _budgetcost_row_urls(resp) == {po_url(po_a), pr_url}


def test_budgetcost_register_junk_params_return_200(client_a, admin_user, tenant_a):
    """L11: ``?source=junk&budget=999999`` narrows nothing and returns 200 - and the valid
    source enum still filters (L44)."""
    budget_a = _budgetcost_budget(tenant_a, "Acme ops budget")
    vendor = _budgetcost_party(tenant_a)
    pr_a = _budgetcost_pr(tenant_a, admin_user, status="approved", budget=budget_a)
    _budgetcost_pr_line(pr_a)
    pr_a.recalc_totals()
    po_a = _budgetcost_po(tenant_a, vendor, requisition=pr_a)
    _budgetcost_po_line(po_a)

    url = reverse("procurement:commitment_register")
    resp = client_a.get(url, {"source": "junk", "budget": "999999"})
    assert resp.status_code == 200
    assert resp.context["selected_budget"] is None
    assert _budgetcost_row_urls(resp) == {
        reverse("scm:purchaseorder_detail", args=[po_a.pk]),
        reverse("procurement:req_detail", args=[pr_a.pk]),
    }

    # L44 pair: the frozen source values still filter.
    resp = client_a.get(url, {"source": "po"})
    assert resp.status_code == 200
    assert {row["source"] for row in resp.context["rows"]} == {"po"}
    resp = client_a.get(url, {"source": "pr"})
    assert resp.status_code == 200
    assert {row["source"] for row in resp.context["rows"]} == {"pr"}


def test_budgetcost_variance_foreign_budget_leaks_nothing(client_a, tenant_a, tenant_b):
    """On the variance page AND its CSV export, B's budget pk selects nothing: the page stays
    the unscoped tenant-A report, and no B figure (budget name, GL code) appears anywhere."""
    gl_a = _budgetcost_gl(tenant_a, code="6000")
    budget_a = _budgetcost_budget(tenant_a, "Acme ops budget")
    _budgetcost_line(budget_a, gl_a)
    budget_b = _budgetcost_budget(tenant_b, "Globex ops budget")
    _budgetcost_gl(tenant_b, code="9100", name="Globex Suspense")

    resp = client_a.get(reverse("procurement:budget_variance"),
                        {"budget": str(budget_b.pk)})
    assert resp.status_code == 200
    assert resp.context["selected_budget"] is None
    content = resp.content.decode()
    assert "6000" in content          # tenant A's own row renders
    assert "9100" not in content      # B's GL code never does
    assert budget_b.name not in content

    # The CSV export shares the exact same context builder - same isolation.
    resp = client_a.get(reverse("procurement:budget_variance_export"),
                        {"budget": str(budget_b.pk)})
    assert resp.status_code == 200
    assert resp["Content-Type"] == "text/csv"
    csv_body = resp.content.decode()
    assert "9100" not in csv_body
    assert budget_b.name not in csv_body
    # Nothing selected -> no budget number in the filename.
    assert resp["Content-Disposition"] == 'attachment; filename="budget-variance.csv"'

    # L44 pair: A's own budget pk scopes the report and the filename.
    resp = client_a.get(reverse("procurement:budget_variance"),
                        {"budget": str(budget_a.pk)})
    assert resp.status_code == 200
    assert resp.context["selected_budget"].pk == budget_a.pk
    rows = resp.context["rows"]
    assert rows and rows[0]["gl_code"] == "6000"
    assert resp.context["totals"]["budgeted"] == Decimal("10000.00")

    resp = client_a.get(reverse("procurement:budget_variance_export"),
                        {"budget": str(budget_a.pk)})
    assert budget_a.number in resp["Content-Disposition"]
    assert "6000" in resp.content.decode()


def test_budgetcost_variance_junk_params_return_200(client_a, tenant_a):
    """L11: ``?budget=abc&fiscal_period=xyz`` parses to nothing and returns the unscoped 200
    page - and a valid fiscal-period pk still scopes (L44)."""
    gl_a = _budgetcost_gl(tenant_a)
    period_a = _budgetcost_period(tenant_a)
    budget_a = _budgetcost_budget(tenant_a, "Acme ops budget", fiscal_period=period_a)
    _budgetcost_line(budget_a, gl_a)
    url = reverse("procurement:budget_variance")

    resp = client_a.get(url, {"budget": "abc", "fiscal_period": "xyz"})
    assert resp.status_code == 200
    assert resp.context["selected_budget"] is None
    assert resp.context["selected_period"] is None
    assert resp.context["rows"]  # the unscoped tenant-A report still renders

    # L44 pair: a valid fiscal period selects and scopes.
    resp = client_a.get(url, {"fiscal_period": str(period_a.pk)})
    assert resp.status_code == 200
    assert resp.context["selected_period"].pk == period_a.pk
    assert resp.context["totals"]["budgeted"] == Decimal("10000.00")


# ==================================================================== 4. crafted POSTs
def test_budgetcost_mapping_create_rejects_foreign_pks(
        client_a, tenant_a, tenant_b):
    """A narrowed <select> is UX, not a boundary: a hand-crafted POST naming tenant B's
    budget, org unit, project or GL account lands as a FIELD error and saves nothing - each
    scope posted on its own with every OTHER field a valid tenant-A value, then all four at
    once; the L44 pair saves with A's own pks."""
    budget_a = _budgetcost_budget(tenant_a, "Acme ops budget")
    org_a = _budgetcost_org(tenant_a)
    project_a = _budgetcost_project(tenant_a)
    gl_a = _budgetcost_gl(tenant_a)
    budget_b = _budgetcost_budget(tenant_b, "Globex ops budget")
    org_b = _budgetcost_org(tenant_b, "Globex Facilities")
    project_b = _budgetcost_project(tenant_b, "Globex rollout")
    gl_b = _budgetcost_gl(tenant_b, code="6100", name="Globex Supplies")

    before = BudgetMapping.objects.count()
    url = reverse("procurement:budgetmapping_create")
    own = {"budget": str(budget_a.pk), "org_unit": str(org_a.pk),
           "project": str(project_a.pk), "default_gl_account": str(gl_a.pk)}

    crafted = (("budget", budget_b.pk), ("org_unit", org_b.pk),
               ("project", project_b.pk), ("default_gl_account", gl_b.pk))
    for field, value in crafted:
        payload = _budgetcost_mapping_payload(**own)
        payload[field] = str(value)
        resp = client_a.post(url, payload)
        assert resp.status_code == 200, field
        assert field in resp.context["form"].errors, field
    assert BudgetMapping.objects.count() == before

    # All four foreign pks in ONE POST - every field errors, still nothing saved.
    resp = client_a.post(url, _budgetcost_mapping_payload(
        budget=str(budget_b.pk), org_unit=str(org_b.pk), project=str(project_b.pk),
        default_gl_account=str(gl_b.pk)))
    assert resp.status_code == 200
    for field, _value in crafted:
        assert field in resp.context["form"].errors, field
    assert BudgetMapping.objects.count() == before

    # L44 pair: the same POST with tenant A's own pks saves, stamped with the request tenant.
    resp = client_a.post(url, _budgetcost_mapping_payload(**own))
    assert resp.status_code == 302
    mapping = BudgetMapping.objects.get(tenant=tenant_a)
    assert mapping.budget_id == budget_a.pk
    assert mapping.org_unit_id == org_a.pk
    assert mapping.project_id == project_a.pk
    assert mapping.default_gl_account_id == gl_a.pk


def test_budgetcost_forecast_create_rejects_foreign_budget(client_a, tenant_a, tenant_b):
    """A crafted POST naming B's budget on the forecast form is a field error on ``budget``
    and freezes nothing in either workspace; a valid budget freezes one for A (L44)."""
    budget_a = _budgetcost_budget(tenant_a, "Acme ops budget")
    budget_b = _budgetcost_budget(tenant_b, "Globex ops budget")
    url = reverse("procurement:costforecast_create")

    resp = client_a.post(url, _budgetcost_forecast_payload(budget=str(budget_b.pk)))
    assert resp.status_code == 200
    assert "budget" in resp.context["form"].errors
    assert CostForecast.objects.filter(tenant=tenant_a).count() == 0
    assert CostForecast.objects.filter(tenant=tenant_b).count() == 0

    # L44 pair: A's own budget freezes a forecast for A.
    resp = client_a.post(url, _budgetcost_forecast_payload(budget=str(budget_a.pk)))
    assert resp.status_code == 302
    forecast = CostForecast.objects.get(tenant=tenant_a)
    assert forecast.budget_id == budget_a.pk
    assert CostForecast.objects.filter(tenant=tenant_b).count() == 0


def test_budgetcost_forecast_create_stamps_server_side_amounts(
        client_a, admin_user, tenant_a):
    """The freeze is honest: the three amount columns come from ``compute_forecast_amounts``
    on the server, NEVER from the POST. A crafted body riding forged committed / historical /
    forecast amounts saves the COMPUTED figures, the request user as author, and a system
    FCST number."""
    gl_a = _budgetcost_gl(tenant_a)
    budget_a = _budgetcost_budget(tenant_a, "Acme ops budget")
    _budgetcost_line(budget_a, gl_a)
    po = _budgetcost_po(tenant_a, _budgetcost_party(tenant_a))
    _budgetcost_po_line(po, gl=gl_a, qty="10", price="25.00")  # open commitment of 250.00

    as_of = timezone.localdate()
    expected = compute_forecast_amounts(tenant_a, budget_a, "open_pos", 3, as_of)
    assert expected["committed"] == Decimal("250.00")  # setup sanity

    forged = {"committed_amount": "999999.99", "historical_amount": "888888.88",
              "forecast_amount": "777777.77"}
    resp = client_a.post(reverse("procurement:costforecast_create"),
                         _budgetcost_forecast_payload(name="Q3 freeze",
                                                      budget=str(budget_a.pk), **forged))
    assert resp.status_code == 302

    forecast = CostForecast.objects.get(tenant=tenant_a)
    assert forecast.committed_amount == expected["committed"]
    assert forecast.historical_amount == expected["historical"]
    assert forecast.forecast_amount == expected["forecast"]
    # ...and NOT the forged values riding in the POST.
    assert forecast.committed_amount != Decimal("999999.99")
    assert forecast.historical_amount != Decimal("888888.88")
    assert forecast.forecast_amount != Decimal("777777.77")
    assert forecast.created_by_id == admin_user.pk
    assert forecast.tenant_id == tenant_a.pk
    assert forecast.number.startswith("FCST")
    assert resp["Location"] == reverse("procurement:costforecast_detail", args=[forecast.pk])


# ==================================================================== 5. the authz ladder
def test_budgetcost_anonymous_redirected_on_all_thirteen_urls(tenant_a):
    """Anonymous (a bare, never-logged-in Client) is bounced to the login page on every one of
    the 13 6.15 URLs - GET pages, pk pages and the two POST-only delete verbs alike - and
    nothing moves while it is bounced."""
    budget_a = _budgetcost_budget(tenant_a, "Acme ops budget")
    mapping_a = _budgetcost_mapping(tenant_a, budget_a)
    forecast_a = _budgetcost_forecast(tenant_a)
    anon = Client()
    login_prefix = reverse("accounts:login")
    assert login_prefix == "/login/"

    for name in ("procurement:budgetmapping_list", "procurement:budgetmapping_create",
                 "procurement:budget_availability", "procurement:commitment_register",
                 "procurement:budget_variance", "procurement:budget_variance_export",
                 "procurement:costforecast_list", "procurement:costforecast_create"):
        resp = anon.get(reverse(name))
        assert resp.status_code == 302, name
        assert resp["Location"].startswith(login_prefix), name

    for name in ("procurement:budgetmapping_detail", "procurement:budgetmapping_edit"):
        resp = anon.get(reverse(name, args=[mapping_a.pk]))
        assert resp.status_code == 302, name
        assert resp["Location"].startswith(login_prefix), name
    resp = anon.get(reverse("procurement:costforecast_detail", args=[forecast_a.pk]))
    assert resp.status_code == 302
    assert resp["Location"].startswith(login_prefix)

    for name, pk in (("procurement:budgetmapping_delete", mapping_a.pk),
                     ("procurement:costforecast_delete", forecast_a.pk)):
        resp = anon.post(reverse(name, args=[pk]))
        assert resp.status_code == 302, name
        assert resp["Location"].startswith(login_prefix), name

    # Nothing was deleted by the bounced delete attempts.
    assert BudgetMapping.objects.filter(pk=mapping_a.pk).exists()
    assert CostForecast.objects.filter(pk=forecast_a.pk).exists()


def test_budgetcost_csrf_enforced_on_delete_and_create_posts(admin_user, tenant_a):
    """A logged-in session is not enough: the mapping-delete POST and the forecast-create POST
    both 403 without a CSRF token, and nothing is deleted or frozen; the L44 pair shows the
    same enforcing client still READS, and a tokened client still writes."""
    budget_a = _budgetcost_budget(tenant_a, "Acme ops budget")
    mapping_a = _budgetcost_mapping(tenant_a, budget_a)

    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(admin_user)

    resp = csrf_client.post(reverse("procurement:budgetmapping_delete", args=[mapping_a.pk]))
    assert resp.status_code == 403
    assert BudgetMapping.objects.filter(pk=mapping_a.pk).exists()

    resp = csrf_client.post(reverse("procurement:costforecast_create"),
                            _budgetcost_forecast_payload(budget=str(budget_a.pk)))
    assert resp.status_code == 403
    assert CostForecast.objects.filter(tenant=tenant_a).count() == 0

    # L44 pair: only UNSAFE methods are gated - the same client reads happily...
    assert csrf_client.get(reverse("procurement:costforecast_list")).status_code == 200

    # ...and with a token (the default test client disables CSRF) both writes succeed.
    plain = Client()
    plain.force_login(admin_user)
    assert plain.post(
        reverse("procurement:budgetmapping_delete", args=[mapping_a.pk])).status_code == 302
    assert not BudgetMapping.objects.filter(pk=mapping_a.pk).exists()
    assert plain.post(reverse("procurement:costforecast_create"),
                      _budgetcost_forecast_payload(budget=str(budget_a.pk))).status_code == 302
    assert CostForecast.objects.filter(tenant=tenant_a).count() == 1


def test_budgetcost_get_on_delete_verbs_is_405_and_never_mutates(client_a, tenant_a):
    """``@require_POST`` fires first: a GET on either delete URL is 405 and leaves its row
    untouched."""
    budget_a = _budgetcost_budget(tenant_a, "Acme ops budget")
    mapping_a = _budgetcost_mapping(tenant_a, budget_a)
    forecast_a = _budgetcost_forecast(tenant_a)

    resp = client_a.get(reverse("procurement:budgetmapping_delete", args=[mapping_a.pk]))
    assert resp.status_code == 405
    resp = client_a.get(reverse("procurement:costforecast_delete", args=[forecast_a.pk]))
    assert resp.status_code == 405

    assert BudgetMapping.objects.filter(pk=mapping_a.pk).exists()
    assert CostForecast.objects.filter(pk=forecast_a.pk).exists()

    # L44 pair: the POST the decorator demands does delete.
    assert client_a.post(
        reverse("procurement:budgetmapping_delete", args=[mapping_a.pk])).status_code == 302
    assert not BudgetMapping.objects.filter(pk=mapping_a.pk).exists()


# ==================================================================== 6. hostile input (lists)
def test_budgetcost_mapping_list_junk_filters_return_200(client_a, tenant_a):
    """L11: ``?budget=abc&is_active=junk`` skips both filters and renders the full register -
    and the valid budget pk / boolean values still filter (L44)."""
    budget_a = _budgetcost_budget(tenant_a, "Acme ops budget")
    active = _budgetcost_mapping(tenant_a, budget_a,
                                 org_unit=_budgetcost_org(tenant_a, "Acme Facilities"),
                                 is_active=True)
    inactive = _budgetcost_mapping(tenant_a, budget_a,
                                   project=_budgetcost_project(tenant_a), is_active=False)
    url = reverse("procurement:budgetmapping_list")

    resp = client_a.get(url, {"budget": "abc", "is_active": "junk"})
    assert resp.status_code == 200
    assert sorted(row.pk for row in resp.context["object_list"]) == sorted(
        [active.pk, inactive.pk])

    # L44 pairs: a valid FK pk and the literal True/False booleans each narrow.
    resp = client_a.get(url, {"budget": str(budget_a.pk), "is_active": "True"})
    assert resp.status_code == 200
    assert [row.pk for row in resp.context["object_list"]] == [active.pk]
    resp = client_a.get(url, {"is_active": "False"})
    assert resp.status_code == 200
    assert [row.pk for row in resp.context["object_list"]] == [inactive.pk]


def test_budgetcost_forecast_list_junk_filters_return_200(client_a, tenant_a):
    """L11: ``?method=junk&budget=abc`` skips both filters (junk enum ignored, junk pk never
    parsed) and shows the whole register - and the valid method / budget values still filter
    (L44)."""
    budget_a = _budgetcost_budget(tenant_a, "Acme ops budget")
    scoped = _budgetcost_forecast(tenant_a, name="Scoped open-PO view", method="open_pos",
                                  budget=budget_a)
    wide = _budgetcost_forecast(tenant_a, name="Workspace run rate", method="run_rate",
                                budget=None)
    url = reverse("procurement:costforecast_list")

    resp = client_a.get(url, {"method": "junk", "budget": "abc"})
    assert resp.status_code == 200
    assert sorted(row.pk for row in resp.context["object_list"]) == sorted(
        [scoped.pk, wide.pk])

    # L44 pairs: the enum and the FK each narrow when valid.
    resp = client_a.get(url, {"method": "open_pos"})
    assert resp.status_code == 200
    assert [row.pk for row in resp.context["object_list"]] == [scoped.pk]
    resp = client_a.get(url, {"budget": str(budget_a.pk)})
    assert resp.status_code == 200
    assert [row.pk for row in resp.context["object_list"]] == [scoped.pk]
