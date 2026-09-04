"""Procurement 6.15 Budget & Cost Management - view / CRUD integration flows.

Everything here drives the real URLconf and the real templates: the BudgetMapping register
(list + search + each filter + pagination + create / edit / delete), the advisory Budget
Availability checker (figures arithmetic), the read-only Commitment Register, the Budget
Variance report (+ CSV export) and the frozen CostForecast register (list / detail / create /
delete).

Lane discipline followed here:

* a context key is never asserted "present" alone - it is asserted POPULATED (L41);
* every reference date derives from ``timezone.localdate()``, never ``date.today()`` (L16);
* the page-2 cases build enough rows to actually cross the 15-row ``crud_list`` page size for
  BOTH the budget-mapping register and the cost-forecast register - a page-2 guard is invisible
  at fixture size (L9);
* the money figures on the availability checker, the commitment register and the variance report
  are hand-computed Decimals, not "is it a number";
* the BudgetMapping register list is wrapped in ``django_assert_max_num_queries`` to catch an
  N+1 on the chained FK columns it renders.

Every test is ``test_budgetcost_*`` and every module-level helper / fixture ``_budgetcost_*``
so the three sibling lanes (models / forms / security) cannot shadow them.
"""
import csv
import datetime
import io
from decimal import Decimal

import pytest

from django.contrib.messages import get_messages
from django.urls import reverse
from django.utils import timezone

from apps.accounting.models import Budget, BudgetLine, FiscalPeriod, GLAccount, Project
from apps.core.models import OrgUnit, Party, PartyRole
from apps.procurement.models import (
    BudgetMapping,
    CostForecast,
    SupplierInvoice,
    SupplierInvoiceLine,
    compute_forecast_amounts,
)
from apps.procurement.views.BudgetCostManagement.BudgetChecks import ADVISORY_NOTE, CURRENCY_NOTE
from apps.procurement.views.BudgetCostManagement.CommitmentRegister import (
    SOURCE_CHOICES, VENDOR_FILTER_NOTE)
from apps.procurement.views.BudgetCostManagement.CostForecasts import FORECAST_NOTE
from apps.procurement.views.BudgetCostManagement.VarianceReport import (
    PERIOD_INVOICE_NOTE, REMAINING_NOTE, SCOPED_INVOICE_NOTE, UNASSIGNED_LABEL)
from apps.scm.models import (
    PurchaseOrder, PurchaseOrderLine, PurchaseRequisition, PurchaseRequisitionLine)

pytestmark = pytest.mark.django_db


# ================================================================== helpers

def _budgetcost_today():
    """The single date basis for every window here - never ``date.today()`` (L16)."""
    return timezone.localdate()


def _budgetcost_templates(response):
    return [t.name for t in response.templates if t.name]


def _budgetcost_messages(response):
    """Works on a 302 too - the storage hangs off the request, not the context."""
    return [str(m) for m in get_messages(response.wsgi_request)]


def _budgetcost_pks(response):
    return [obj.pk for obj in response.context["object_list"]]


# -- accounting / core masters ---------------------------------------------------------------

def _budgetcost_gl(tenant, code="6000", name="Office Supplies"):
    return GLAccount.objects.create(tenant=tenant, code=code, name=name,
                                    account_type="expense")


def _budgetcost_org(tenant, name="Operations"):
    return OrgUnit.objects.create(tenant=tenant, name=name)


def _budgetcost_project(tenant, name="Nav rollout"):
    return Project.objects.create(tenant=tenant, name=name)


def _budgetcost_budget(tenant, name="Ops budget", fiscal_period=None):
    return Budget.objects.create(tenant=tenant, name=name, fiscal_period=fiscal_period)


def _budgetcost_budget_line(budget, gl, amount, org_unit=None):
    return BudgetLine.objects.create(tenant=budget.tenant, budget=budget, gl_account=gl,
                                     amount=Decimal(amount), org_unit=org_unit)


def _budgetcost_period(tenant, name="FY25 Q1"):
    return FiscalPeriod.objects.create(
        tenant=tenant, name=name, start_date=_budgetcost_today(),
        end_date=_budgetcost_today() + datetime.timedelta(days=89))


def _budgetcost_party(tenant, name="Northwind", role="supplier"):
    """A counterparty WITH its PartyRole - the commitment register's vendor dropdown narrows on
    ``roles__role__in=("supplier", "vendor")``, so a bare Party would be invisible to it."""
    party = Party.objects.create(tenant=tenant, name=name, kind="organization")
    PartyRole.objects.create(tenant=tenant, party=party, role=role, status="active")
    return party


# -- scm document spine ----------------------------------------------------------------------

def _budgetcost_pr(tenant, status="approved", budget=None, org_unit=None, requester=None,
                   title="Laptops"):
    return PurchaseRequisition.objects.create(
        tenant=tenant, title=title, status=status, requester=requester,
        org_unit=org_unit, budget=budget)


def _budgetcost_pr_line(pr, gl=None, qty="1", price="10.00"):
    return PurchaseRequisitionLine.objects.create(
        requisition=pr, item_description="A4", quantity=Decimal(qty),
        estimated_unit_price=Decimal(price), gl_account=gl)


def _budgetcost_po(tenant, vendor, requisition=None, status="approved"):
    return PurchaseOrder.objects.create(
        tenant=tenant, vendor=vendor, status=status, requisition=requisition,
        order_date=_budgetcost_today())


def _budgetcost_po_line(po, gl=None, qty="1", price="10.00"):
    return PurchaseOrderLine.objects.create(
        purchase_order=po, item_description="Toner", quantity=Decimal(qty),
        unit_price=Decimal(price), gl_account=gl)


# -- 6.13 recognised invoices ----------------------------------------------------------------

def _budgetcost_invoice(tenant, vendor, purchase_order=None, status="approved"):
    return SupplierInvoice.objects.create(
        tenant=tenant, vendor=vendor, invoice_number="SUP-1",
        invoice_date=_budgetcost_today(), status=status, invoice_type="standard",
        purchase_order=purchase_order)


def _budgetcost_invoice_line(invoice, gl=None, qty="1", price="10.00"):
    return SupplierInvoiceLine.objects.create(
        invoice=invoice, description="Service", quantity=Decimal(qty),
        unit_price=Decimal(price), gl_account=gl)


# -- the two 6.15 entities -------------------------------------------------------------------

def _budgetcost_mapping(tenant, budget, org_unit=None, project=None, **overrides):
    fields = dict(tenant=tenant, budget=budget, org_unit=org_unit, project=project,
                  is_active=True, priority=100, notes="")
    fields.update(overrides)
    return BudgetMapping.objects.create(**fields)


def _budgetcost_forecast(tenant, **overrides):
    """A frozen projection row built directly (amounts are writable via ``.create`` even though
    they are ``editable=False`` on forms) - the list / detail / delete lanes need stored rows."""
    fields = dict(tenant=tenant, name="Q3 ops projection", method="blended",
                  horizon_months=3, as_of=_budgetcost_today(),
                  committed_amount=Decimal("100.00"),
                  historical_amount=Decimal("50.00"),
                  forecast_amount=Decimal("75.00"))
    fields.update(overrides)
    return CostForecast.objects.create(**fields)


def _budgetcost_mapping_body(budget, **overrides):
    """A complete, valid ``BudgetMappingForm`` POST body."""
    body = {"budget": str(budget.pk), "org_unit": "", "project": "",
            "default_gl_account": "", "priority": "100", "is_active": "on",
            "notes": "created by the view test"}
    body.update(overrides)
    return body


def _budgetcost_forecast_body(**overrides):
    """A complete, valid ``CostForecastForm`` POST body (the amounts are NOT fields - they are
    stamped by the view via ``compute_forecast_amounts``)."""
    body = {"name": "Q3 ops spend projection", "budget": "", "method": "open_pos",
            "horizon_months": "3", "as_of": _budgetcost_today().isoformat(),
            "currency": "", "assumptions": "Open purchase orders stand as the projection."}
    body.update(overrides)
    return body


# ================================================================== bulk fixtures (page 2, L9)

@pytest.fixture
def _budgetcost_bulk_mappings(db, tenant_a):
    """18 mappings - enough to cross the 15-row register page size and force a page 2."""
    budget = _budgetcost_budget(tenant_a, "Bulk budget")
    return [_budgetcost_mapping(tenant_a, budget, notes=f"Bulk mapping {i:02d}",
                                priority=100 + i) for i in range(18)]


@pytest.fixture
def _budgetcost_bulk_forecasts(db, tenant_a):
    """18 frozen projections - enough to cross the 15-row register page size and force a page 2."""
    return [_budgetcost_forecast(tenant_a, name=f"Bulk forecast {i:02d}") for i in range(18)]


# =================================================================================================
# BudgetMapping register (list / search / filters / pagination)
# =================================================================================================

def test_budgetcost_budgetmapping_list_renders_contract_context(client_a, tenant_a):
    gl = _budgetcost_gl(tenant_a)
    org = _budgetcost_org(tenant_a)
    project = _budgetcost_project(tenant_a)
    budget = _budgetcost_budget(tenant_a)
    active = _budgetcost_mapping(tenant_a, budget, org_unit=org, project=project,
                                 default_gl_account=gl, notes="governs ops")
    inactive = _budgetcost_mapping(tenant_a, budget, is_active=False, notes="retired one")

    resp = client_a.get(reverse("procurement:budgetmapping_list"))

    assert resp.status_code == 200
    assert "procurement/budgetcost/budgetmapping/list.html" in _budgetcost_templates(resp)
    ctx = resp.context
    assert set(_budgetcost_pks(resp)) == {active.pk, inactive.pk}
    assert ctx["q"] == ""
    # POPULATED stat strip, not just a present key (L41).
    assert ctx["stats"] == {"total": 2, "active": 1, "inactive": 1}
    assert [b.pk for b in ctx["budgets"]] == [budget.pk]
    assert [o.pk for o in ctx["org_units"]] == [org.pk]
    assert [p.pk for p in ctx["projects"]] == [project.pk]
    assert ctx["page_obj"] is not None
    assert ctx["page_obj"].paginator.count == 2


def test_budgetcost_budgetmapping_list_search_narrows_rows_but_not_stats(client_a, tenant_a):
    budget = _budgetcost_budget(tenant_a)
    hit = _budgetcost_mapping(tenant_a, budget, notes="alpha warehouse")
    _budgetcost_mapping(tenant_a, budget, notes="beta depot")

    resp = client_a.get(reverse("procurement:budgetmapping_list"), {"q": "warehouse"})

    assert resp.status_code == 200
    assert _budgetcost_pks(resp) == [hit.pk]
    assert resp.context["q"] == "warehouse"
    # The stat strip describes the WORKSPACE, so a search must not move it.
    assert resp.context["stats"]["total"] == 2


def test_budgetcost_budgetmapping_list_filters_each_narrow(client_a, tenant_a):
    budget_x = _budgetcost_budget(tenant_a, "Budget X")
    budget_y = _budgetcost_budget(tenant_a, "Budget Y")
    org = _budgetcost_org(tenant_a)
    project = _budgetcost_project(tenant_a)
    mapping_x = _budgetcost_mapping(tenant_a, budget_x)
    mapping_y = _budgetcost_mapping(tenant_a, budget_y, org_unit=org, project=project,
                                    is_active=False)

    url = reverse("procurement:budgetmapping_list")
    assert _budgetcost_pks(client_a.get(url, {"budget": str(budget_x.pk)})) == [mapping_x.pk]
    assert _budgetcost_pks(client_a.get(url, {"org_unit": str(org.pk)})) == [mapping_y.pk]
    assert _budgetcost_pks(client_a.get(url, {"project": str(project.pk)})) == [mapping_y.pk]
    assert _budgetcost_pks(client_a.get(url, {"is_active": "True"})) == [mapping_x.pk]
    assert _budgetcost_pks(client_a.get(url, {"is_active": "False"})) == [mapping_y.pk]


def test_budgetcost_budgetmapping_list_page_two(client_a, _budgetcost_bulk_mappings):
    url = reverse("procurement:budgetmapping_list")

    page_one = client_a.get(url)
    assert len(_budgetcost_pks(page_one)) == 15
    assert page_one.context["page_obj"].paginator.num_pages == 2

    page_two = client_a.get(url, {"page": "2"})
    assert page_two.status_code == 200
    assert len(_budgetcost_pks(page_two)) == 3
    assert set(_budgetcost_pks(page_one)).isdisjoint(_budgetcost_pks(page_two))

    past_end = client_a.get(url, {"page": "999"})
    assert past_end.status_code == 200
    assert past_end.context["page_obj"].number == 2


def test_budgetcost_budgetmapping_list_query_budget(client_a, _budgetcost_bulk_mappings,
                                                    django_assert_max_num_queries):
    """15 rows whose columns walk budget / org_unit / project / default_gl_account - guard the
    register against a per-row FK query. Bound observed then widened once for headroom."""
    with django_assert_max_num_queries(14):
        resp = client_a.get(reverse("procurement:budgetmapping_list"))
    assert resp.status_code == 200
    assert len(_budgetcost_pks(resp)) == 15


# =================================================================================================
# BudgetMapping create / edit / delete
# =================================================================================================

def test_budgetcost_budgetmapping_create_get_renders_form(client_a, tenant_a):
    _budgetcost_budget(tenant_a)
    resp = client_a.get(reverse("procurement:budgetmapping_create"))

    assert resp.status_code == 200
    assert "procurement/budgetcost/budgetmapping/form.html" in _budgetcost_templates(resp)
    assert resp.context["is_edit"] is False
    assert resp.context["form"] is not None


def test_budgetcost_budgetmapping_create_post_saves_with_request_tenant(client_a, tenant_a):
    budget = _budgetcost_budget(tenant_a)

    resp = client_a.post(reverse("procurement:budgetmapping_create"),
                         _budgetcost_mapping_body(budget))

    assert resp.status_code == 302
    assert resp["Location"] == reverse("procurement:budgetmapping_list")
    obj = BudgetMapping.objects.get(tenant=tenant_a)
    assert obj.budget_id == budget.pk
    assert obj.is_active is True
    assert obj.priority == 100
    assert obj.notes == "created by the view test"


def test_budgetcost_budgetmapping_edit_post_saves(client_a, tenant_a):
    budget = _budgetcost_budget(tenant_a)
    mapping = _budgetcost_mapping(tenant_a, budget, notes="before")

    resp = client_a.post(reverse("procurement:budgetmapping_edit", args=[mapping.pk]),
                         _budgetcost_mapping_body(budget, notes="after", priority="5"))

    assert resp.status_code == 302
    assert resp["Location"] == reverse("procurement:budgetmapping_list")
    mapping.refresh_from_db()
    assert mapping.notes == "after"
    assert mapping.priority == 5


def test_budgetcost_budgetmapping_delete_is_post_only(client_a, tenant_a):
    budget = _budgetcost_budget(tenant_a)
    mapping = _budgetcost_mapping(tenant_a, budget)
    url = reverse("procurement:budgetmapping_delete", args=[mapping.pk])

    getter = client_a.get(url)
    assert getter.status_code == 405
    assert BudgetMapping.objects.filter(pk=mapping.pk).exists()

    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp["Location"] == reverse("procurement:budgetmapping_list")
    assert not BudgetMapping.objects.filter(pk=mapping.pk).exists()


# =================================================================================================
# Budget Availability checker
# =================================================================================================

def test_budgetcost_availability_renders_contract_context(client_a, tenant_a):
    gl = _budgetcost_gl(tenant_a)
    org = _budgetcost_org(tenant_a)
    budget = _budgetcost_budget(tenant_a)

    resp = client_a.get(reverse("procurement:budget_availability"))

    assert resp.status_code == 200
    assert "procurement/budgetcost/availability.html" in _budgetcost_templates(resp)
    ctx = resp.context
    assert [b.pk for b in ctx["budgets"]] == [budget.pk]
    assert [o.pk for o in ctx["org_units"]] == [org.pk]
    assert [g.pk for g in ctx["gl_accounts"]] == [gl.pk]
    assert ctx["selected_budget"] is None
    assert ctx["figures"] is None
    assert ctx["check_amount"] == ""
    assert ctx["advisory_note"] == ADVISORY_NOTE
    assert ctx["currency_note"] == CURRENCY_NOTE


def test_budgetcost_availability_figures_are_hand_computed(client_a, tenant_a):
    gl = _budgetcost_gl(tenant_a, code="6000")
    org = _budgetcost_org(tenant_a, "Operations")
    budget = _budgetcost_budget(tenant_a, "Ops budget")
    # A company-wide line (org_unit=None) so it is counted under ANY department filter.
    _budgetcost_budget_line(budget, gl, "10000.00", org_unit=None)

    vendor = _budgetcost_party(tenant_a)

    # Open PO commitment - the requisition behind the order carries the budget + department.
    po_pr = _budgetcost_pr(tenant_a, status="converted", budget=budget, org_unit=org)
    po = _budgetcost_po(tenant_a, vendor, requisition=po_pr)
    _budgetcost_po_line(po, gl=gl, qty="4", price="60.00")          # 240.00 committed

    # Approved-but-not-converted requisition -> pr_committed.
    pr_approved = _budgetcost_pr(tenant_a, status="approved", budget=budget, org_unit=org)
    _budgetcost_pr_line(pr_approved, gl=gl, qty="2", price="10.00")  # 20.00

    # Pending-approval requisition -> requested pipeline.
    pr_pending = _budgetcost_pr(tenant_a, status="pending_approval", budget=budget, org_unit=org)
    _budgetcost_pr_line(pr_pending, gl=gl, qty="1", price="5.00")    # 5.00

    resp = client_a.get(reverse("procurement:budget_availability"),
                        {"budget": str(budget.pk), "org_unit": str(org.pk),
                         "gl_account": str(gl.pk), "amount": "100"})

    assert resp.status_code == 200
    ctx = resp.context
    assert ctx["selected_budget"].pk == budget.pk
    assert ctx["check_amount"] == "100"
    figures = ctx["figures"]
    assert figures is not None
    assert figures["budgeted"] == Decimal("10000.00")
    assert figures["po_committed"] == Decimal("240.00")
    assert figures["pr_committed"] == Decimal("20.00")
    assert figures["committed"] == Decimal("260.00")
    assert figures["requested"] == Decimal("5.00")
    assert figures["check_amount"] == Decimal("100.00")
    # remaining = budgeted - po - pr - requested - check_amount.
    assert figures["remaining"] == Decimal("9635.00")
    assert figures["over_budget"] is False


def test_budgetcost_availability_over_budget_flag(client_a, tenant_a):
    gl = _budgetcost_gl(tenant_a)
    budget = _budgetcost_budget(tenant_a)
    _budgetcost_budget_line(budget, gl, "100.00", org_unit=None)

    resp = client_a.get(reverse("procurement:budget_availability"),
                        {"budget": str(budget.pk), "amount": "250"})

    figures = resp.context["figures"]
    assert figures["remaining"] == Decimal("-150.00")
    assert figures["over_budget"] is True


def test_budgetcost_availability_junk_params_render_200_with_no_figures(client_a, tenant_a):
    _budgetcost_budget(tenant_a)

    resp = client_a.get(reverse("procurement:budget_availability"),
                        {"budget": "abc", "org_unit": "²", "amount": "not-a-number"})

    assert resp.status_code == 200
    assert resp.context["figures"] is None
    assert resp.context["selected_budget"] is None
    assert resp.context["check_amount"] == ""


# =================================================================================================
# Commitment Register
# =================================================================================================

def test_budgetcost_commitment_register_rows_and_totals(client_a, tenant_a, admin_user):
    gl = _budgetcost_gl(tenant_a)
    budget = _budgetcost_budget(tenant_a)
    vendor = _budgetcost_party(tenant_a, "Northwind")

    # One PO commitment (requisition links the budget) + one approved-not-converted requisition.
    po_pr = _budgetcost_pr(tenant_a, status="converted", budget=budget)
    po = _budgetcost_po(tenant_a, vendor, requisition=po_pr)
    _budgetcost_po_line(po, gl=gl, qty="4", price="60.00")          # 240.00

    pr = _budgetcost_pr(tenant_a, status="approved", budget=budget, requester=admin_user,
                        title="Standing order")
    _budgetcost_pr_line(pr, gl=gl, qty="2", price="10.00")          # 20.00
    pr.recalc_totals()

    resp = client_a.get(reverse("procurement:commitment_register"))

    assert resp.status_code == 200
    assert "procurement/budgetcost/commitment_register.html" in _budgetcost_templates(resp)
    ctx = resp.context
    assert ctx["totals"] == {"count": 2,
                             "po_committed": Decimal("240.00"),
                             "pr_committed": Decimal("20.00"),
                             "committed": Decimal("260.00")}
    rows = ctx["rows"]
    assert len(rows) == 2
    po_row = next(r for r in rows if r["source"] == "po")
    pr_row = next(r for r in rows if r["source"] == "pr")
    assert po_row["number"] == po.number
    assert po_row["party"] == vendor.name
    assert po_row["amount"] == Decimal("240.00")
    assert po_row["url"] == reverse("scm:purchaseorder_detail", args=[po.pk])
    assert po_row["budget"].pk == budget.pk
    assert pr_row["number"] == pr.number
    assert pr_row["amount"] == Decimal("20.00")
    assert pr_row["url"] == reverse("procurement:req_detail", args=[pr.pk])
    assert ctx["row_cap"] == 500
    assert ctx["truncated"] is False
    assert ctx["source_choices"] == SOURCE_CHOICES
    assert [b.pk for b in ctx["budgets"]] == [budget.pk]
    assert [v.pk for v in ctx["vendors"]] == [vendor.pk]
    assert ctx["selected_vendor"] is None
    assert ctx["vendor_filter_note"] == ""


def test_budgetcost_commitment_register_source_filter_hides_po_rows(client_a, tenant_a):
    gl = _budgetcost_gl(tenant_a)
    budget = _budgetcost_budget(tenant_a)
    vendor = _budgetcost_party(tenant_a)

    po_pr = _budgetcost_pr(tenant_a, status="converted", budget=budget)
    po = _budgetcost_po(tenant_a, vendor, requisition=po_pr)
    _budgetcost_po_line(po, gl=gl, qty="4", price="60.00")

    pr = _budgetcost_pr(tenant_a, status="approved", budget=budget)
    _budgetcost_pr_line(pr, gl=gl, qty="2", price="10.00")
    pr.recalc_totals()

    pr_only = client_a.get(reverse("procurement:commitment_register"), {"source": "pr"})
    assert [r["source"] for r in pr_only.context["rows"]] == ["pr"]
    assert pr_only.context["totals"]["count"] == 1
    assert pr_only.context["totals"]["po_committed"] == Decimal("0.00")

    po_only = client_a.get(reverse("procurement:commitment_register"), {"source": "po"})
    assert [r["source"] for r in po_only.context["rows"]] == ["po"]
    assert po_only.context["totals"]["count"] == 1


def test_budgetcost_commitment_register_vendor_filter_hides_pr_rows_and_sets_note(
        client_a, tenant_a):
    gl = _budgetcost_gl(tenant_a)
    budget = _budgetcost_budget(tenant_a)
    vendor = _budgetcost_party(tenant_a)

    po_pr = _budgetcost_pr(tenant_a, status="converted", budget=budget)
    po = _budgetcost_po(tenant_a, vendor, requisition=po_pr)
    _budgetcost_po_line(po, gl=gl, qty="4", price="60.00")

    pr = _budgetcost_pr(tenant_a, status="approved", budget=budget)
    _budgetcost_pr_line(pr, gl=gl, qty="2", price="10.00")
    pr.recalc_totals()

    resp = client_a.get(reverse("procurement:commitment_register"), {"vendor": str(vendor.pk)})

    assert resp.status_code == 200
    # A requisition has no supplier: with a vendor filter set its rows are hidden and noted.
    assert all(r["source"] == "po" for r in resp.context["rows"])
    assert resp.context["selected_vendor"].pk == vendor.pk
    assert resp.context["vendor_filter_note"] == VENDOR_FILTER_NOTE


# =================================================================================================
# Budget Variance report (+ CSV export)
# =================================================================================================

def test_budgetcost_variance_scoped_rows_and_totals(client_a, tenant_a):
    gl = _budgetcost_gl(tenant_a, code="6100", name="IT Equipment")
    budget = _budgetcost_budget(tenant_a, "Ops budget")
    _budgetcost_budget_line(budget, gl, "5000.00", org_unit=None)

    vendor = _budgetcost_party(tenant_a)
    po_pr = _budgetcost_pr(tenant_a, status="converted", budget=budget)
    po = _budgetcost_po(tenant_a, vendor, requisition=po_pr)
    _budgetcost_po_line(po, gl=gl, qty="4", price="60.00")          # committed 240.00

    inv = _budgetcost_invoice(tenant_a, vendor, purchase_order=po, status="approved")
    _budgetcost_invoice_line(inv, gl=gl, qty="2", price="50.00")    # invoiced 100.00 (PO-backed)

    resp = client_a.get(reverse("procurement:budget_variance"), {"budget": str(budget.pk)})

    assert resp.status_code == 200
    assert "procurement/budgetcost/variance_report.html" in _budgetcost_templates(resp)
    ctx = resp.context
    assert ctx["selected_budget"].pk == budget.pk
    assert ctx["remaining_note"] == REMAINING_NOTE
    assert ctx["scoped_invoice_note"] == SCOPED_INVOICE_NOTE
    rows = ctx["rows"]
    assert len(rows) == 1
    row = rows[0]
    assert row["gl_code"] == "6100"
    assert row["gl_name"] == "IT Equipment"
    assert row["org_unit_name"] == UNASSIGNED_LABEL
    assert row["budgeted"] == Decimal("5000.00")
    assert row["committed"] == Decimal("240.00")
    assert row["invoiced"] == Decimal("100.00")
    assert row["standalone_invoiced"] == Decimal("0.00")
    # remaining = budgeted - committed - standalone_invoiced (PO-backed invoice NOT deducted).
    assert row["remaining"] == Decimal("4760.00")
    assert row["variance_pct"] == Decimal("95.2")
    assert row["over_budget"] is False
    assert ctx["totals"] == {"budgeted": Decimal("5000.00"), "committed": Decimal("240.00"),
                             "invoiced": Decimal("100.00"), "remaining": Decimal("4760.00")}


def test_budgetcost_variance_unbudgeted_row_has_no_pct(client_a, tenant_a):
    gl = _budgetcost_gl(tenant_a, code="6200", name="Unbudgeted")
    vendor = _budgetcost_party(tenant_a)
    pr = _budgetcost_pr(tenant_a, status="converted")                # no budget attached
    po = _budgetcost_po(tenant_a, vendor, requisition=pr)
    _budgetcost_po_line(po, gl=gl, qty="3", price="40.00")           # committed 120.00

    resp = client_a.get(reverse("procurement:budget_variance"))      # all-budgets view

    rows = resp.context["rows"]
    assert len(rows) == 1
    row = rows[0]
    assert row["budgeted"] == Decimal("0.00")
    assert row["committed"] == Decimal("120.00")
    assert row["remaining"] == Decimal("-120.00")
    # No budget base to divide by -> None, never zero.
    assert row["variance_pct"] is None
    assert row["over_budget"] is True


def test_budgetcost_variance_scoped_invoice_note_switches(client_a, tenant_a):
    budget = _budgetcost_budget(tenant_a)
    period = _budgetcost_period(tenant_a)

    neither = client_a.get(reverse("procurement:budget_variance"))
    assert neither.context["scoped_invoice_note"] == ""

    scoped = client_a.get(reverse("procurement:budget_variance"), {"budget": str(budget.pk)})
    assert scoped.context["scoped_invoice_note"] == SCOPED_INVOICE_NOTE

    by_period = client_a.get(reverse("procurement:budget_variance"),
                             {"fiscal_period": str(period.pk)})
    assert by_period.context["scoped_invoice_note"] == PERIOD_INVOICE_NOTE
    assert by_period.context["selected_period"].pk == period.pk


def test_budgetcost_variance_export_csv_and_total_row(client_a, tenant_a):
    gl = _budgetcost_gl(tenant_a, code="6300", name="Travel")
    budget = _budgetcost_budget(tenant_a)
    _budgetcost_budget_line(budget, gl, "1000.00", org_unit=None)

    vendor = _budgetcost_party(tenant_a)
    po_pr = _budgetcost_pr(tenant_a, status="converted", budget=budget)
    po = _budgetcost_po(tenant_a, vendor, requisition=po_pr)
    _budgetcost_po_line(po, gl=gl, qty="1", price="100.00")          # committed 100.00

    resp = client_a.get(reverse("procurement:budget_variance_export"),
                        {"budget": str(budget.pk)})

    assert resp.status_code == 200
    assert resp["Content-Type"] == "text/csv"
    assert "attachment" in resp["Content-Disposition"]
    assert f"budget-variance-{budget.number}.csv" in resp["Content-Disposition"]

    lines = [row for row in csv.reader(io.StringIO(resp.content.decode())) if row]
    assert lines[0] == ["GL Code", "GL Account", "Department", "Budgeted", "Committed",
                        "Invoiced", "Remaining", "Variance %"]
    # Header + ONE data row + the TOTAL footer.
    assert len(lines) == 3
    data = lines[1]
    assert data[0] == "6300"
    assert data[2] == UNASSIGNED_LABEL
    assert data[3] == "1000.00"
    assert data[4] == "100.00"
    assert data[6] == "900.00"
    total = lines[-1]
    assert total[0] == "TOTAL"
    assert total[3] == "1000.00"
    assert total[4] == "100.00"
    assert total[6] == "900.00"


# =================================================================================================
# CostForecast register / detail / create / delete
# =================================================================================================

def test_budgetcost_costforecast_list_renders_contract_context(client_a, tenant_a):
    budget = _budgetcost_budget(tenant_a)
    scoped = _budgetcost_forecast(tenant_a, budget=budget, method="open_pos")
    wide = _budgetcost_forecast(tenant_a, method="run_rate")

    resp = client_a.get(reverse("procurement:costforecast_list"))

    assert resp.status_code == 200
    assert "procurement/budgetcost/costforecast/list.html" in _budgetcost_templates(resp)
    ctx = resp.context
    assert set(_budgetcost_pks(resp)) == {scoped.pk, wide.pk}
    # POPULATED stats (L41): one budget-scoped, one workspace-wide.
    assert ctx["stats"] == {"total": 2, "budget_scoped": 1, "workspace_wide": 1}
    assert ctx["method_choices"] == CostForecast.METHOD_CHOICES
    assert ctx["forecast_note"] == FORECAST_NOTE
    assert [b.pk for b in ctx["budgets"]] == [budget.pk]
    assert ctx["page_obj"] is not None


def test_budgetcost_costforecast_list_search_and_filters(client_a, tenant_a):
    budget = _budgetcost_budget(tenant_a)
    scoped = _budgetcost_forecast(tenant_a, name="warehouse runway", method="open_pos",
                                  budget=budget)
    wide = _budgetcost_forecast(tenant_a, name="depot runway", method="run_rate")

    url = reverse("procurement:costforecast_list")
    assert _budgetcost_pks(client_a.get(url, {"q": "warehouse"})) == [scoped.pk]
    assert _budgetcost_pks(client_a.get(url, {"method": "run_rate"})) == [wide.pk]
    assert _budgetcost_pks(client_a.get(url, {"budget": str(budget.pk)})) == [scoped.pk]


def test_budgetcost_costforecast_list_page_two(client_a, _budgetcost_bulk_forecasts):
    url = reverse("procurement:costforecast_list")

    page_one = client_a.get(url)
    assert len(_budgetcost_pks(page_one)) == 15
    assert page_one.context["page_obj"].paginator.num_pages == 2

    page_two = client_a.get(url, {"page": "2"})
    assert page_two.status_code == 200
    assert len(_budgetcost_pks(page_two)) == 3
    assert set(_budgetcost_pks(page_one)).isdisjoint(_budgetcost_pks(page_two))


def test_budgetcost_costforecast_detail_renders_note(client_a, tenant_a):
    forecast = _budgetcost_forecast(tenant_a)

    resp = client_a.get(reverse("procurement:costforecast_detail", args=[forecast.pk]))

    assert resp.status_code == 200
    assert "procurement/budgetcost/costforecast/detail.html" in _budgetcost_templates(resp)
    assert resp.context["obj"].pk == forecast.pk
    assert resp.context["forecast_note"] == FORECAST_NOTE


def test_budgetcost_costforecast_create_get_renders_form_contract(client_a, tenant_a):
    resp = client_a.get(reverse("procurement:costforecast_create"))

    assert resp.status_code == 200
    assert "procurement/budgetcost/costforecast/form.html" in _budgetcost_templates(resp)
    ctx = resp.context
    assert ctx["title"] == "New cost forecast"
    assert ctx["submit_label"] == "Freeze forecast"
    assert ctx["cancel_url"] == reverse("procurement:costforecast_list")
    assert ctx["forecast_note"] == FORECAST_NOTE
    fields = ctx["form"].fields
    for name in ("name", "budget", "method", "horizon_months", "as_of"):
        assert name in fields
    # The frozen amount columns and the authorship stamp are never form fields.
    assert "committed_amount" not in fields
    assert "historical_amount" not in fields
    assert "forecast_amount" not in fields
    assert "created_by" not in fields


def test_budgetcost_costforecast_create_post_freezes_amounts(client_a, tenant_a, admin_user):
    # One open PO (240.00) and NO recognised invoices -> open_pos forecast == commitment.
    vendor = _budgetcost_party(tenant_a)
    pr = _budgetcost_pr(tenant_a, status="converted")
    po = _budgetcost_po(tenant_a, vendor, requisition=pr)
    _budgetcost_po_line(po, qty="4", price="60.00")

    expected = compute_forecast_amounts(tenant_a, None, "open_pos", 3, _budgetcost_today())
    assert expected == {"committed": Decimal("240.00"), "historical": Decimal("0.00"),
                        "forecast": Decimal("240.00")}

    resp = client_a.post(reverse("procurement:costforecast_create"), _budgetcost_forecast_body())

    assert resp.status_code == 302
    obj = CostForecast.objects.get(tenant=tenant_a)
    assert resp["Location"] == reverse("procurement:costforecast_detail", args=[obj.pk])
    assert obj.number == "FCST-00001"
    assert obj.created_by_id == admin_user.pk
    assert obj.method == "open_pos"
    # The amounts are stamped by compute_forecast_amounts, never typed.
    assert obj.committed_amount == Decimal("240.00")
    assert obj.historical_amount == Decimal("0.00")
    assert obj.forecast_amount == Decimal("240.00")
    assert any("frozen" in message for message in _budgetcost_messages(resp))


def test_budgetcost_costforecast_delete_is_post_only(client_a, tenant_a):
    forecast = _budgetcost_forecast(tenant_a)
    url = reverse("procurement:costforecast_delete", args=[forecast.pk])

    getter = client_a.get(url)
    assert getter.status_code == 405
    assert CostForecast.objects.filter(pk=forecast.pk).exists()

    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp["Location"] == reverse("procurement:costforecast_list")
    assert not CostForecast.objects.filter(pk=forecast.pk).exists()
