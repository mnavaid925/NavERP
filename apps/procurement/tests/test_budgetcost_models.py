"""Procurement 6.15 - Budget & Cost Management MODEL tests.

The invariants this lane owns:

* ``BudgetMapping`` as a CONFIGURATION MASTER - ``TenantOwned``, no ``number`` and deliberately
  NO ``unique_together``: two same-shaped rows at different priorities are a legitimate override
  and :meth:`BudgetMapping.resolve` (not a database constraint) decides which one wins;
* ``resolve()`` specificity - a project row beats an org-unit row beats the workspace default,
  specificity beats priority, and inside each tier the LOWEST priority wins with ties broken on
  the mapping's id; inactive rows never match; instances and raw pks are both accepted;
* the commitment vocabulary - ``OPEN_COMMITMENT_PO_STATUSES`` / ``COMMITTED_PR_STATUSES`` /
  ``REQUESTED_PR_STATUSES`` are this sub-module's SINGLE definition of "what counts as
  committed / requested spend" (``converted`` is deliberately NOT a committed requisition:
  counting both the requisition and the order it became would double-count one commitment), and
  the three line-window helpers are their SQL mirrors;
* ``CostForecast`` - per-tenant ``FCST-`` auto-numbering, ``unique_together ('tenant',
  'number')``, the three method choices, the frozen ``editable=False`` amount columns and the
  cross-tenant backstop on its budget FK;
* and ``compute_forecast_amounts`` - PURE arithmetic: committed from the open-PO vocabulary,
  historical from 6.13's recognised invoices over the half-open window
  ``[as_of - 30 x horizon days, as_of)``, forecast per method (open_pos / run_rate / blended),
  both populations scoped to the GL accounts a budget's lines fund, and honest zeros for every
  guard case.

Determinism (L16): every date basis here is ``timezone.localdate()`` - the same basis the model
code uses. ``datetime.date.today()`` never appears, or the window-boundary assertions flake for
the hours after local midnight.
"""
import datetime
import itertools
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.utils import timezone

from apps.procurement.models import (
    COMMITTED_PR_STATUSES,
    OPEN_COMMITMENT_PO_STATUSES,
    REQUESTED_PR_STATUSES,
    BudgetMapping,
    CostForecast,
    committed_pr_lines,
    compute_forecast_amounts,
    open_po_commitment_lines,
    requested_pr_lines,
)
from apps.procurement.models.BudgetCostManagement.CostForecasts import (
    METHOD_CHOICES as _BUDGETCOST_MODULE_METHOD_CHOICES,
)
from apps.procurement.models.SpendAnalyticsReporting.SpendClassificationRules import (
    RECOGNISED_INVOICE_STATUSES,
)

pytestmark = pytest.mark.django_db


# -- local helpers ------------------------------------------------------------------------------
# Named _budgetcost_* so a sibling lane appending near this file cannot shadow them, and so a
# failure names its own lane. Domain rows are minted HERE (the pinned contract's minimal create
# kwargs) - the concurrently-owned conftest is never leaned on.

#: The middot CostForecast.__str__ and the accounting masters fold into their labels.
_BUDGETCOST_DOT = "·"

#: Every compute_forecast_amounts guard case returns exactly this shape.
_BUDGETCOST_ZEROS = {"committed": Decimal("0.00"), "historical": Decimal("0.00"),
                     "forecast": Decimal("0.00")}

#: SupplierInvoice numbers only need to be locally distinct - a counter keeps it boring.
_BUDGETCOST_INVOICE_SEQ = itertools.count(1)


def _budgetcost_today():
    """The SAME date basis the models use (L16) - never ``datetime.date.today()``."""
    return timezone.localdate()


def _budgetcost_field(model, name):
    return model._meta.get_field(name)


def _budgetcost_gl(tenant, code="6000", name="Office Supplies"):
    from apps.accounting.models import GLAccount
    return GLAccount.objects.create(tenant=tenant, code=code, name=name, account_type="expense")


def _budgetcost_org(tenant, name="Operations"):
    from apps.core.models import OrgUnit
    return OrgUnit.objects.create(tenant=tenant, name=name)


def _budgetcost_project(tenant, name="Nav rollout"):
    from apps.accounting.models import Project
    return Project.objects.create(tenant=tenant, name=name)


def _budgetcost_budget(tenant, name="Ops budget"):
    from apps.accounting.models import Budget
    return Budget.objects.create(tenant=tenant, name=name)


def _budgetcost_budget_line(tenant, budget, gl_account, amount=Decimal("10000.00")):
    from apps.accounting.models import BudgetLine
    return BudgetLine.objects.create(tenant=tenant, budget=budget, gl_account=gl_account,
                                     amount=amount)


def _budgetcost_party(tenant, name="Northwind"):
    from apps.core.models import Party
    return Party.objects.create(tenant=tenant, name=name, kind="organization")


def _budgetcost_po(tenant, vendor, status="approved", **overrides):
    from apps.scm.models import PurchaseOrder
    fields = dict(tenant=tenant, vendor=vendor, status=status, order_date=_budgetcost_today(),
                  requisition=None)
    fields.update(overrides)
    return PurchaseOrder.objects.create(**fields)


def _budgetcost_po_line(po, quantity=Decimal("4"), unit_price=Decimal("60.00"), gl_account=None):
    """``line_total`` is DERIVED in save() - never pass it."""
    from apps.scm.models import PurchaseOrderLine
    return PurchaseOrderLine.objects.create(purchase_order=po, item_description="Toner",
                                            quantity=quantity, unit_price=unit_price,
                                            gl_account=gl_account)


def _budgetcost_pr(tenant, status="approved", **overrides):
    from apps.scm.models import PurchaseRequisition
    fields = dict(tenant=tenant, title="Laptops", status=status, requester=None, org_unit=None,
                  budget=None)
    fields.update(overrides)
    return PurchaseRequisition.objects.create(**fields)


def _budgetcost_pr_line(pr, quantity=Decimal("4"), unit_price=Decimal("22.50"), gl_account=None):
    """``line_total`` is DERIVED in save() - never pass it."""
    from apps.scm.models import PurchaseRequisitionLine
    return PurchaseRequisitionLine.objects.create(requisition=pr, item_description="A4",
                                                  quantity=quantity,
                                                  estimated_unit_price=unit_price,
                                                  gl_account=gl_account)


def _budgetcost_invoice(tenant, vendor, invoice_date, status="approved"):
    from apps.procurement.models import SupplierInvoice
    return SupplierInvoice.objects.create(
        tenant=tenant, vendor=vendor, invoice_number=f"SUP-{next(_BUDGETCOST_INVOICE_SEQ)}",
        invoice_date=invoice_date, status=status)


def _budgetcost_invoice_line(invoice, quantity=Decimal("10"), unit_price=Decimal("25.00"),
                             gl_account=None):
    """``line_total`` is DERIVED in save() - never pass it."""
    from apps.procurement.models import SupplierInvoiceLine
    return SupplierInvoiceLine.objects.create(invoice=invoice, description="Service",
                                              quantity=quantity, unit_price=unit_price,
                                              gl_account=gl_account)


def _budgetcost_mapping(tenant, budget, **overrides):
    fields = dict(tenant=tenant, budget=budget)
    fields.update(overrides)
    return BudgetMapping.objects.create(**fields)


def _budgetcost_forecast(tenant, **overrides):
    fields = dict(tenant=tenant, name="Q3 ops spend projection")
    fields.update(overrides)
    return CostForecast.objects.create(**fields)


def _budgetcost_scene(tenant):
    """One workspace scene for the compute tests.

    A budget funding ONLY GL 6000; an open PO carrying lines on GL 6000 (240.00), GL 6100
    (100.00) and uncoded (75.00); a CLOSED PO line (90.00) that is no longer a commitment;
    a recognised invoice on GL 6000 (250.00) and GL 6100 (90.00); and a DRAFT invoice line
    (100.00) that is not spend yet. Returns the handles the tests narrow with.
    """
    today = _budgetcost_today()
    gl_office = _budgetcost_gl(tenant, code="6000", name="Office Supplies")
    gl_travel = _budgetcost_gl(tenant, code="6100", name="Travel")
    budget = _budgetcost_budget(tenant)
    _budgetcost_budget_line(tenant, budget, gl_office)
    vendor = _budgetcost_party(tenant)

    open_po = _budgetcost_po(tenant, vendor, status="approved")
    _budgetcost_po_line(open_po, Decimal("4"), Decimal("60.00"), gl_office)   # 240.00 in scope
    _budgetcost_po_line(open_po, Decimal("2"), Decimal("50.00"), gl_travel)   # 100.00 off scope
    _budgetcost_po_line(open_po, Decimal("1"), Decimal("75.00"))               # 75.00 uncoded
    closed_po = _budgetcost_po(tenant, vendor, status="closed")
    _budgetcost_po_line(closed_po, Decimal("9"), Decimal("10.00"), gl_office)  # 90.00, never

    invoice = _budgetcost_invoice(tenant, vendor, today - datetime.timedelta(days=10))
    _budgetcost_invoice_line(invoice, Decimal("10"), Decimal("25.00"), gl_office)  # 250.00
    _budgetcost_invoice_line(invoice, Decimal("1"), Decimal("90.00"), gl_travel)    # 90.00 off
    draft = _budgetcost_invoice(tenant, vendor, today - datetime.timedelta(days=9),
                                status="draft")
    _budgetcost_invoice_line(draft, Decimal("5"), Decimal("20.00"), gl_office)  # 100.00, never
    return {"budget": budget, "gl_office": gl_office, "gl_travel": gl_travel}


# =================================================================================================
# BudgetMapping - shape, defaults, ordering
# =================================================================================================

def test_budgetcost_mapping_defaults_are_the_documented_ones(tenant_a):
    budget = _budgetcost_budget(tenant_a)
    mapping = _budgetcost_mapping(tenant_a, budget)
    mapping.refresh_from_db()
    assert mapping.priority == 100
    assert mapping.is_active is True
    assert mapping.notes == ""
    assert mapping.org_unit_id is None
    assert mapping.project_id is None
    assert mapping.default_gl_account_id is None
    assert mapping.created_at is not None and mapping.updated_at is not None


def test_budgetcost_mapping_field_defaults_on_the_meta():
    assert _budgetcost_field(BudgetMapping, "priority").default == 100
    assert _budgetcost_field(BudgetMapping, "is_active").default is True


def test_budgetcost_mapping_is_a_configuration_master_not_a_document():
    """TenantOwned, not TenantNumbered - no number, no status, no unique_together."""
    names = {f.name for f in BudgetMapping._meta.get_fields()}
    assert "number" not in names
    assert "status" not in names
    assert {"tenant", "created_at", "updated_at"} <= names
    assert BudgetMapping._meta.unique_together == ()
    assert BudgetMapping._meta.ordering == ["priority", "id"]


def test_budgetcost_mapping_two_same_shaped_rows_coexist(tenant_a):
    """Two same-shaped rows at different priorities are a legal override, not a mistake."""
    budget = _budgetcost_budget(tenant_a)
    first = _budgetcost_mapping(tenant_a, budget, priority=10)
    second = _budgetcost_mapping(tenant_a, budget, priority=50)
    assert list(BudgetMapping.objects.filter(tenant=tenant_a)) == [first, second]


def test_budgetcost_mapping_ordering_is_priority_then_id(tenant_a):
    budget = _budgetcost_budget(tenant_a)
    low = _budgetcost_mapping(tenant_a, budget, priority=50)
    first_high = _budgetcost_mapping(tenant_a, budget, priority=10)
    second_high = _budgetcost_mapping(tenant_a, budget, priority=10)
    ordered = list(BudgetMapping.objects.filter(tenant=tenant_a))
    assert ordered == [first_high, second_high, low]


def test_budgetcost_mapping_budget_is_protected(tenant_a):
    """PROTECT: deleting a budget a mapping still points at must fail loudly."""
    budget = _budgetcost_budget(tenant_a)
    _budgetcost_mapping(tenant_a, budget)
    with pytest.raises(ProtectedError):
        budget.delete()


# =================================================================================================
# BudgetMapping - __str__ and display properties
# =================================================================================================

def test_budgetcost_mapping_str_folds_budget_and_dimension(tenant_a):
    budget = _budgetcost_budget(tenant_a)
    org = _budgetcost_org(tenant_a)
    mapping = _budgetcost_mapping(tenant_a, budget, org_unit=org)
    assert str(mapping) == f"{budget} -> {org}"


def test_budgetcost_mapping_str_falls_back_to_the_dimension_label_unsaved(tenant_a):
    """An unsaved instance (a ModelForm rendering its own errors) must never 500 on __str__."""
    assert str(BudgetMapping(tenant=tenant_a)) == "Workspace default"


def test_budgetcost_mapping_dimension_label_prefers_project(tenant_a):
    budget = _budgetcost_budget(tenant_a)
    org = _budgetcost_org(tenant_a)
    project = _budgetcost_project(tenant_a)
    both = _budgetcost_mapping(tenant_a, budget, org_unit=org, project=project)
    org_only = _budgetcost_mapping(tenant_a, budget, org_unit=org)
    neither = _budgetcost_mapping(tenant_a, budget)
    assert both.dimension_label == str(project)
    assert org_only.dimension_label == str(org)
    assert neither.dimension_label == "Workspace default"


def test_budgetcost_mapping_status_css_and_label_follow_is_active(tenant_a):
    budget = _budgetcost_budget(tenant_a)
    mapping = _budgetcost_mapping(tenant_a, budget)
    assert (mapping.status_css, mapping.status_label) == ("badge-green", "Active")
    mapping.is_active = False
    assert (mapping.status_css, mapping.status_label) == ("badge-muted", "Inactive")


# =================================================================================================
# BudgetMapping - the commitment vocabulary (single source for the whole sub-module)
# =================================================================================================

def test_budgetcost_open_commitment_po_statuses_are_the_five_documented():
    assert OPEN_COMMITMENT_PO_STATUSES == (
        "approved", "sent", "acknowledged", "partially_received", "received")
    assert "received" in OPEN_COMMITMENT_PO_STATUSES
    # The encumbrance is released once the order is closed - and draft / pending_approval /
    # cancelled never were commitments.
    for excluded in ("closed", "cancelled", "draft", "pending_approval"):
        assert excluded not in OPEN_COMMITMENT_PO_STATUSES


def test_budgetcost_committed_pr_statuses_exclude_converted():
    """NOT ``converted`` - a converted requisition has become its PO; counting both would
    double-count one commitment."""
    assert COMMITTED_PR_STATUSES == ("approved",)
    assert "converted" not in COMMITTED_PR_STATUSES


def test_budgetcost_requested_pr_statuses_are_the_pipeline_column():
    assert REQUESTED_PR_STATUSES == ("pending_approval",)


def test_budgetcost_vocabulary_is_reexposed_on_the_model():
    """Views/templates/tests reach the vocabulary through the model."""
    assert BudgetMapping.OPEN_COMMITMENT_PO_STATUSES == OPEN_COMMITMENT_PO_STATUSES
    assert BudgetMapping.COMMITTED_PR_STATUSES == COMMITTED_PR_STATUSES
    assert BudgetMapping.REQUESTED_PR_STATUSES == REQUESTED_PR_STATUSES


# =================================================================================================
# BudgetMapping - resolve()
# =================================================================================================

def test_budgetcost_resolve_project_tier_beats_org_and_default_even_at_worse_priority(tenant_a):
    budget = _budgetcost_budget(tenant_a)
    org = _budgetcost_org(tenant_a)
    project = _budgetcost_project(tenant_a)
    project_row = _budgetcost_mapping(tenant_a, budget, project=project, priority=90)
    _budgetcost_mapping(tenant_a, budget, org_unit=org, priority=1)
    _budgetcost_mapping(tenant_a, budget, priority=1)
    assert BudgetMapping.resolve(tenant_a, org_unit=org, project=project) == project_row


def test_budgetcost_resolve_org_tier_beats_workspace_default_even_at_worse_priority(tenant_a):
    budget = _budgetcost_budget(tenant_a)
    org = _budgetcost_org(tenant_a)
    org_row = _budgetcost_mapping(tenant_a, budget, org_unit=org, priority=90)
    default_row = _budgetcost_mapping(tenant_a, budget, priority=1)
    assert BudgetMapping.resolve(tenant_a, org_unit=org) == org_row
    assert BudgetMapping.resolve(tenant_a) == default_row


def test_budgetcost_resolve_within_a_tier_lowest_priority_wins(tenant_a):
    budget = _budgetcost_budget(tenant_a)
    project = _budgetcost_project(tenant_a)
    _budgetcost_mapping(tenant_a, budget, project=project, priority=20)
    winner = _budgetcost_mapping(tenant_a, budget, project=project, priority=5)
    assert BudgetMapping.resolve(tenant_a, project=project) == winner


def test_budgetcost_resolve_breaks_a_priority_tie_on_id(tenant_a):
    budget = _budgetcost_budget(tenant_a)
    project = _budgetcost_project(tenant_a)
    org = _budgetcost_org(tenant_a)
    first_project = _budgetcost_mapping(tenant_a, budget, project=project, priority=10)
    _budgetcost_mapping(tenant_a, budget, project=project, priority=10)
    first_org = _budgetcost_mapping(tenant_a, budget, org_unit=org, priority=40)
    _budgetcost_mapping(tenant_a, budget, org_unit=org, priority=40)
    assert BudgetMapping.resolve(tenant_a, project=project) == first_project
    assert BudgetMapping.resolve(tenant_a, org_unit=org) == first_org


def test_budgetcost_resolve_skips_inactive_rows(tenant_a):
    budget = _budgetcost_budget(tenant_a)
    project = _budgetcost_project(tenant_a)
    org = _budgetcost_org(tenant_a)
    _budgetcost_mapping(tenant_a, budget, project=project, priority=1, is_active=False)
    org_row = _budgetcost_mapping(tenant_a, budget, org_unit=org, priority=50)
    assert BudgetMapping.resolve(tenant_a, org_unit=org, project=project) == org_row


def test_budgetcost_resolve_is_none_when_only_inactive_rows_exist(tenant_a):
    budget = _budgetcost_budget(tenant_a)
    _budgetcost_mapping(tenant_a, budget, is_active=False)
    assert BudgetMapping.resolve(tenant_a) is None


def test_budgetcost_resolve_accepts_instances_and_pks(tenant_a):
    budget = _budgetcost_budget(tenant_a)
    org = _budgetcost_org(tenant_a)
    project = _budgetcost_project(tenant_a)
    row = _budgetcost_mapping(tenant_a, budget, project=project, org_unit=org)
    by_instance = BudgetMapping.resolve(tenant_a, org_unit=org, project=project)
    by_pk = BudgetMapping.resolve(tenant_a, org_unit=org.pk, project=project.pk)
    assert by_instance == row == by_pk


def test_budgetcost_resolve_is_none_without_a_tenant():
    assert BudgetMapping.resolve(None, org_unit=1, project=1) is None
    assert BudgetMapping.resolve(None) is None


def test_budgetcost_resolve_is_none_when_nothing_matches(tenant_a):
    budget = _budgetcost_budget(tenant_a)
    org = _budgetcost_org(tenant_a)
    other_org = _budgetcost_org(tenant_a, name="Research")
    _budgetcost_mapping(tenant_a, budget, org_unit=org)
    assert BudgetMapping.resolve(tenant_a, org_unit=other_org) is None
    # Dimensioned rows are never a workspace default.
    assert BudgetMapping.resolve(tenant_a) is None


def test_budgetcost_resolve_ignores_other_workspaces_mappings(tenant_a, tenant_b):
    foreign_budget = _budgetcost_budget(tenant_b, name="Globex budget")
    _budgetcost_mapping(tenant_b, foreign_budget)
    assert BudgetMapping.resolve(tenant_a) is None


def test_budgetcost_resolve_org_tier_never_matches_a_row_carrying_a_project(tenant_a):
    """A row with org AND project is a project mapping - the org tier requires project NULL."""
    budget = _budgetcost_budget(tenant_a)
    org = _budgetcost_org(tenant_a)
    project = _budgetcost_project(tenant_a)
    _budgetcost_mapping(tenant_a, budget, org_unit=org, project=project, priority=1)
    assert BudgetMapping.resolve(tenant_a, org_unit=org) is None
    default_row = _budgetcost_mapping(tenant_a, budget, priority=99)
    assert BudgetMapping.resolve(tenant_a, org_unit=org) == default_row


def test_budgetcost_resolve_falls_back_to_org_for_an_unmatched_project(tenant_a):
    budget = _budgetcost_budget(tenant_a)
    org = _budgetcost_org(tenant_a)
    unknown_project = _budgetcost_project(tenant_a, name="Unmapped rollout")
    org_row = _budgetcost_mapping(tenant_a, budget, org_unit=org)
    assert BudgetMapping.resolve(tenant_a, org_unit=org, project=unknown_project) == org_row


# =================================================================================================
# BudgetMapping - clean()
# =================================================================================================

@pytest.mark.parametrize("field", ["budget", "org_unit", "project", "default_gl_account"])
def test_budgetcost_mapping_clean_rejects_a_cross_tenant_fk(field, tenant_a, tenant_b):
    own_budget = _budgetcost_budget(tenant_a)
    foreign = {
        "budget": _budgetcost_budget(tenant_b, name="Globex budget"),
        "org_unit": _budgetcost_org(tenant_b, name="Globex Operations"),
        "project": _budgetcost_project(tenant_b, name="Globex rollout"),
        "default_gl_account": _budgetcost_gl(tenant_b, code="5000", name="Globex Expense"),
    }[field]
    mapping = BudgetMapping(tenant=tenant_a, budget=own_budget)
    setattr(mapping, field, foreign)
    with pytest.raises(ValidationError) as exc:
        mapping.clean()
    assert exc.value.message_dict[field] == ["That record belongs to another workspace."]


def test_budgetcost_mapping_clean_accepts_its_own_workspace_rows(tenant_a):
    budget = _budgetcost_budget(tenant_a)
    mapping = BudgetMapping(tenant=tenant_a, budget=budget,
                            org_unit=_budgetcost_org(tenant_a),
                            project=_budgetcost_project(tenant_a),
                            default_gl_account=_budgetcost_gl(tenant_a))
    mapping.full_clean()  # must not raise


# =================================================================================================
# CostForecast - numbering, defaults, __str__
# =================================================================================================

def test_budgetcost_forecast_auto_number_is_fcst_five_wide(tenant_a):
    assert CostForecast.NUMBER_PREFIX == "FCST"
    assert _budgetcost_forecast(tenant_a).number == "FCST-00001"


def test_budgetcost_forecast_numbers_run_in_sequence(tenant_a):
    first = _budgetcost_forecast(tenant_a)
    second = _budgetcost_forecast(tenant_a, name="Q4 ops spend projection")
    assert [first.number, second.number] == ["FCST-00001", "FCST-00002"]


def test_budgetcost_forecast_numbers_are_independent_across_tenants(tenant_a, tenant_b):
    a_first = _budgetcost_forecast(tenant_a)
    _budgetcost_forecast(tenant_a, name="Second acme projection")
    b_first = _budgetcost_forecast(tenant_b, name="Globex projection")
    assert a_first.number == b_first.number == "FCST-00001"
    assert a_first.tenant_id != b_first.tenant_id


def test_budgetcost_forecast_unique_together_and_meta():
    assert CostForecast._meta.unique_together == (("tenant", "number"),)
    assert CostForecast._meta.ordering == ["-as_of", "-id"]


def test_budgetcost_forecast_number_is_unique_within_a_tenant(tenant_a):
    first = _budgetcost_forecast(tenant_a)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            CostForecast.objects.create(tenant=tenant_a, name="Twin", number=first.number)


def test_budgetcost_forecast_defaults_are_the_documented_ones(tenant_a):
    forecast = _budgetcost_forecast(tenant_a)
    forecast.refresh_from_db()
    assert forecast.method == "blended"
    assert forecast.horizon_months == 3
    assert forecast.as_of == _budgetcost_today()
    assert forecast.committed_amount == Decimal("0")
    assert forecast.historical_amount == Decimal("0")
    assert forecast.forecast_amount == Decimal("0")
    assert forecast.budget_id is None
    assert forecast.currency_id is None
    assert forecast.assumptions == ""
    assert forecast.created_by_id is None


def test_budgetcost_forecast_field_defaults_on_the_meta():
    assert _budgetcost_field(CostForecast, "method").default == "blended"
    assert _budgetcost_field(CostForecast, "horizon_months").default == 3
    assert _budgetcost_field(CostForecast, "as_of").default is timezone.localdate


def test_budgetcost_forecast_ordering_is_newest_as_of_first(tenant_a):
    today = _budgetcost_today()
    older = _budgetcost_forecast(tenant_a, as_of=today - datetime.timedelta(days=1))
    same_day_first = _budgetcost_forecast(tenant_a, name="Same day, first")
    same_day_second = _budgetcost_forecast(tenant_a, name="Same day, second")
    ordered = list(CostForecast.objects.filter(tenant=tenant_a))
    assert ordered == [same_day_second, same_day_first, older]


def test_budgetcost_forecast_amount_fields_and_created_by_are_not_editable():
    """Stamped ONLY by compute_forecast_amounts at create time - never hand-editable."""
    for name in ("committed_amount", "historical_amount", "forecast_amount", "created_by",
                 "number"):
        assert _budgetcost_field(CostForecast, name).editable is False, name


def test_budgetcost_forecast_str_folds_number_and_name(tenant_a):
    forecast = _budgetcost_forecast(tenant_a)
    assert str(forecast) == f"{forecast.number} {_BUDGETCOST_DOT} {forecast.name}"


def test_budgetcost_forecast_str_survives_an_unsaved_row():
    assert str(CostForecast(name="Half-built projection")) == f"FCST {_BUDGETCOST_DOT} Half-built projection"


# =================================================================================================
# CostForecast - vocabulary and clean()
# =================================================================================================

def test_budgetcost_forecast_method_choices_are_the_three_documented():
    assert CostForecast.METHOD_CHOICES == [
        ("open_pos", "Open POs"),
        ("run_rate", "Run rate (historical)"),
        ("blended", "Blended"),
    ]
    assert CostForecast.METHOD_CHOICES == _BUDGETCOST_MODULE_METHOD_CHOICES


@pytest.mark.parametrize("method", [key for key, _label in CostForecast.METHOD_CHOICES])
def test_budgetcost_forecast_every_method_value_validates(method, tenant_a):
    CostForecast(tenant=tenant_a, name="M", method=method).full_clean()  # must not raise


def test_budgetcost_forecast_clean_rejects_an_unknown_method(tenant_a):
    forecast = CostForecast(tenant=tenant_a, name="Junk", method="crystal_ball")
    with pytest.raises(ValidationError) as exc:
        forecast.full_clean()
    assert "method" in exc.value.message_dict


def test_budgetcost_forecast_method_css_map_and_fallback():
    assert CostForecast.METHOD_CSS == {"open_pos": "badge-info", "run_rate": "badge-slate",
                                       "blended": "badge-muted"}
    assert CostForecast(method="open_pos").method_css == "badge-info"
    assert CostForecast(method="run_rate").method_css == "badge-slate"
    assert CostForecast(method="blended").method_css == "badge-muted"
    # Anything outside the map falls back to a real theme badge, never an unstyled one.
    assert CostForecast(method="telepathy").method_css == "badge-slate"


@pytest.mark.parametrize("horizon,valid", [(0, False), (25, False), (1, True), (24, True)])
def test_budgetcost_forecast_horizon_bounds(horizon, valid, tenant_a):
    forecast = CostForecast(tenant=tenant_a, name="H", horizon_months=horizon)
    if valid:
        forecast.full_clean()
    else:
        with pytest.raises(ValidationError) as exc:
            forecast.full_clean()
        assert "horizon_months" in exc.value.message_dict


def test_budgetcost_forecast_clean_rejects_a_cross_tenant_budget(tenant_a, tenant_b):
    forecast = CostForecast(tenant=tenant_a, name="Crafted",
                            budget=_budgetcost_budget(tenant_b, name="Globex budget"))
    with pytest.raises(ValidationError) as exc:
        forecast.clean()
    assert exc.value.message_dict["budget"] == ["That record belongs to another workspace."]


def test_budgetcost_forecast_clean_accepts_its_own_workspace_budget(tenant_a):
    CostForecast(tenant=tenant_a, name="Scoped", budget=_budgetcost_budget(tenant_a)).clean()


# =================================================================================================
# compute_forecast_amounts - arithmetic for all three methods
# =================================================================================================

def test_budgetcost_compute_open_pos_forecast_is_the_commitment(tenant_a):
    scene = _budgetcost_scene(tenant_a)
    result = compute_forecast_amounts(tenant_a, scene["budget"], "open_pos", 2,
                                      _budgetcost_today())
    assert result["committed"] == Decimal("240.00")
    assert result["historical"] == Decimal("250.00")
    assert result["forecast"] == Decimal("240.00")


def test_budgetcost_compute_run_rate_forecast_is_the_historical_window(tenant_a):
    scene = _budgetcost_scene(tenant_a)
    result = compute_forecast_amounts(tenant_a, scene["budget"], "run_rate", 2,
                                      _budgetcost_today())
    assert result["forecast"] == result["historical"] == Decimal("250.00")


def test_budgetcost_compute_blended_forecast_is_the_mean(tenant_a):
    scene = _budgetcost_scene(tenant_a)
    result = compute_forecast_amounts(tenant_a, scene["budget"], "blended", 2,
                                      _budgetcost_today())
    assert result["forecast"] == Decimal("245.00")  # (240.00 + 250.00) / 2


def test_budgetcost_compute_amounts_are_quantized_to_two_places(tenant_a):
    scene = _budgetcost_scene(tenant_a)
    for method in ("open_pos", "run_rate", "blended"):
        result = compute_forecast_amounts(tenant_a, scene["budget"], method, 2,
                                          _budgetcost_today())
        for key in ("committed", "historical", "forecast"):
            assert result[key].as_tuple().exponent == -2, (method, key)


def test_budgetcost_compute_budget_scoping_excludes_unfunded_gl_and_non_open_documents(tenant_a):
    """The budget funds ONLY GL 6000: GL 6100 and uncoded lines stay out, and a closed PO is no
    longer a commitment while a draft invoice is not spend yet."""
    scene = _budgetcost_scene(tenant_a)
    result = compute_forecast_amounts(tenant_a, scene["budget"], "blended", 2,
                                      _budgetcost_today())
    assert result["committed"] == Decimal("240.00")   # not 240 + 100 + 75 + 90
    assert result["historical"] == Decimal("250.00")  # not 250 + 90 + 100


def test_budgetcost_compute_without_a_budget_forecasts_the_whole_workspace(tenant_a):
    """A None budget scopes nothing - every open PO line and recognised invoice line counts."""
    _budgetcost_scene(tenant_a)
    result = compute_forecast_amounts(tenant_a, None, "blended", 2, _budgetcost_today())
    assert result["committed"] == Decimal("415.00")   # 240 + 100 + 75
    assert result["historical"] == Decimal("340.00")  # 250 + 90
    assert result["forecast"] == Decimal("377.50")


# =================================================================================================
# compute_forecast_amounts - guard cases return honest zeros
# =================================================================================================

def test_budgetcost_compute_is_zero_without_a_tenant(tenant_a):
    scene = _budgetcost_scene(tenant_a)
    assert compute_forecast_amounts(None, scene["budget"], "blended", 3,
                                    _budgetcost_today()) == _BUDGETCOST_ZEROS


def test_budgetcost_compute_is_zero_for_an_unknown_method(tenant_a):
    scene = _budgetcost_scene(tenant_a)
    assert compute_forecast_amounts(tenant_a, scene["budget"], "crystal_ball", 3,
                                    _budgetcost_today()) == _BUDGETCOST_ZEROS


@pytest.mark.parametrize("horizon", [0, -3, None])
def test_budgetcost_compute_is_zero_for_a_non_positive_horizon(horizon, tenant_a):
    scene = _budgetcost_scene(tenant_a)
    assert compute_forecast_amounts(tenant_a, scene["budget"], "blended", horizon,
                                    _budgetcost_today()) == _BUDGETCOST_ZEROS


def test_budgetcost_compute_is_zero_without_an_as_of(tenant_a):
    scene = _budgetcost_scene(tenant_a)
    assert compute_forecast_amounts(tenant_a, scene["budget"], "blended", 3,
                                    None) == _BUDGETCOST_ZEROS


def test_budgetcost_compute_is_zero_for_a_budget_with_no_gl_scoped_lines(tenant_a):
    """A budget with NO lines funds nothing - zeros, never the whole workspace."""
    scene = _budgetcost_scene(tenant_a)
    empty_budget = _budgetcost_budget(tenant_a, name="Empty budget")
    assert compute_forecast_amounts(tenant_a, empty_budget, "blended", 3,
                                    _budgetcost_today()) == _BUDGETCOST_ZEROS


def test_budgetcost_compute_is_zero_on_an_empty_workspace(tenant_a):
    result = compute_forecast_amounts(tenant_a, None, "blended", 3, _budgetcost_today())
    assert result == _BUDGETCOST_ZEROS


# =================================================================================================
# compute_forecast_amounts - the half-open historical window
# =================================================================================================

def test_budgetcost_compute_window_is_half_open(tenant_a):
    """``[as_of - 30 x horizon days, as_of)`` - start INCLUSIVE, end EXCLUSIVE."""
    today = _budgetcost_today()
    vendor = _budgetcost_party(tenant_a)
    at_start = _budgetcost_invoice(tenant_a, vendor, today - datetime.timedelta(days=30))
    _budgetcost_invoice_line(at_start, Decimal("1"), Decimal("10.00"))
    before_start = _budgetcost_invoice(tenant_a, vendor, today - datetime.timedelta(days=31))
    _budgetcost_invoice_line(before_start, Decimal("1"), Decimal("20.00"))
    at_as_of = _budgetcost_invoice(tenant_a, vendor, today)
    _budgetcost_invoice_line(at_as_of, Decimal("1"), Decimal("30.00"))

    result = compute_forecast_amounts(tenant_a, None, "run_rate", 1, today)
    assert result["historical"] == Decimal("10.00")  # only the at-start invoice counts


def test_budgetcost_compute_window_scales_with_the_horizon(tenant_a):
    today = _budgetcost_today()
    vendor = _budgetcost_party(tenant_a)
    deep = _budgetcost_invoice(tenant_a, vendor, today - datetime.timedelta(days=45))
    _budgetcost_invoice_line(deep, Decimal("1"), Decimal("77.00"))

    one_month = compute_forecast_amounts(tenant_a, None, "run_rate", 1, today)
    two_months = compute_forecast_amounts(tenant_a, None, "run_rate", 2, today)
    assert one_month["historical"] == Decimal("0.00")   # day 45 lies outside 30 days
    assert two_months["historical"] == Decimal("77.00")  # but inside 60


def test_budgetcost_compute_window_counts_only_recognised_invoice_statuses(tenant_a):
    """RECOGNISED_INVOICE_STATUSES is ('approved', 'scheduled', 'paid') - nothing else is spend."""
    today = _budgetcost_today()
    vendor = _budgetcost_party(tenant_a)
    for status, amount in (("approved", "12.00"), ("scheduled", "8.00"), ("paid", "5.00"),
                           ("draft", "50.00"), ("parked", "60.00")):
        invoice = _budgetcost_invoice(tenant_a, vendor, today - datetime.timedelta(days=5),
                                      status=status)
        _budgetcost_invoice_line(invoice, Decimal("1"), Decimal(amount))
    result = compute_forecast_amounts(tenant_a, None, "run_rate", 1, today)
    assert result["historical"] == Decimal("25.00")


def test_budgetcost_recognised_invoice_statuses_constant():
    assert RECOGNISED_INVOICE_STATUSES == ("approved", "scheduled", "paid")


# =================================================================================================
# The three line-window helpers (the SQL mirrors of the vocabulary)
# =================================================================================================

@pytest.mark.parametrize("status", OPEN_COMMITMENT_PO_STATUSES)
def test_budgetcost_open_po_lines_include_every_open_status(status, tenant_a):
    vendor = _budgetcost_party(tenant_a)
    line = _budgetcost_po_line(_budgetcost_po(tenant_a, vendor, status=status))
    assert line in open_po_commitment_lines(tenant_a)


@pytest.mark.parametrize("status", ["draft", "pending_approval", "cancelled", "closed"])
def test_budgetcost_open_po_lines_exclude_non_commitment_statuses(status, tenant_a):
    vendor = _budgetcost_party(tenant_a)
    _budgetcost_po_line(_budgetcost_po(tenant_a, vendor, status=status))
    assert open_po_commitment_lines(tenant_a).count() == 0


def test_budgetcost_open_po_lines_stay_inside_their_workspace(tenant_a, tenant_b):
    vendor_a = _budgetcost_party(tenant_a)
    vendor_b = _budgetcost_party(tenant_b, name="Globex Supplies")
    own = _budgetcost_po_line(_budgetcost_po(tenant_a, vendor_a))
    _budgetcost_po_line(_budgetcost_po(tenant_b, vendor_b))
    assert list(open_po_commitment_lines(tenant_a)) == [own]


def test_budgetcost_committed_pr_lines_only_approved_requisitions(tenant_a, tenant_b):
    own = _budgetcost_pr_line(_budgetcost_pr(tenant_a, status="approved"))
    _budgetcost_pr_line(_budgetcost_pr(tenant_a, status="converted"))
    _budgetcost_pr_line(_budgetcost_pr(tenant_a, status="pending_approval"))
    _budgetcost_pr_line(_budgetcost_pr(tenant_a, status="draft"))
    _budgetcost_pr_line(_budgetcost_pr(tenant_b, status="approved"))
    assert list(committed_pr_lines(tenant_a)) == [own]


def test_budgetcost_requested_pr_lines_only_pending_approval(tenant_a, tenant_b):
    own = _budgetcost_pr_line(_budgetcost_pr(tenant_a, status="pending_approval"))
    _budgetcost_pr_line(_budgetcost_pr(tenant_a, status="approved"))
    _budgetcost_pr_line(_budgetcost_pr(tenant_a, status="draft"))
    _budgetcost_pr_line(_budgetcost_pr(tenant_b, status="pending_approval"))
    assert list(requested_pr_lines(tenant_a)) == [own]


@pytest.mark.parametrize("helper", [open_po_commitment_lines, committed_pr_lines,
                                    requested_pr_lines])
def test_budgetcost_line_helpers_are_empty_without_a_tenant(helper):
    """tenant None -> .none(), never an unscoped sweep of the table."""
    assert helper(None).count() == 0
    assert helper(None).exists() is False
