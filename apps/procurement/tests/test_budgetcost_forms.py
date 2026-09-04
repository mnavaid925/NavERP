"""Procurement 6.15 Budget & Cost Management — form tests.

This lane owns the two forms of the sub-module (``BudgetMappingForm`` and
``CostForecastForm``) and asserts five things over and over:

1. **Nothing system-owned reaches a form field** (L20/L22 — the lessons that shipped bugs
   elsewhere): ``tenant`` / ``id`` / the timestamps stay OFF the mapping form; ``tenant``,
   the ``FCST-`` number, the three COMPUTED amount columns, the ``created_by`` authorship
   stamp, ``id`` and the timestamps stay OFF the forecast form — asserted as explicit name
   lists AND generically (every ``editable=False`` column of each model against its form).
   The forecast's EXEMPTION is asserted too: there is no edit form for a frozen projection.
2. **Every tenant-carrying FK ``<select>`` is tenant-scoped** — a field built for tenant A
   never contains a tenant B row, and a tenant-less form (the superuser has ``tenant=None``
   by design) offers nothing at all. ``currency`` is the deliberate counter-example: a
   GLOBAL table with no tenant column, narrowed only to active rows.
3. **The narrowed ``<select>`` is UX, not the boundary.** Cross-tenant pks are asserted
   twice: against the narrowed queryset (layer 1, "Select a valid choice") and with the
   queryset deliberately widened to simulate a hand-edited POST (layer 2, the explicit
   ``_reject_foreign`` message on the field).
4. **Required fields and junk input** — the missing-required map per form, off-vocabulary
   ``method``, malformed dates and the horizon bounds the MODEL validators (1..24) surface
   as form errors on ``horizon_months``.
5. **The happy path saves the way the views do** — ``save(commit=False)`` + the tenant
   stamp (plus, for the forecast, the computed amounts and the author stamp).

Dates derive from ``timezone.localdate()`` — never ``date.today()`` — so exact-date
assertions stay stable in the hours after local midnight (L16).
"""
import datetime
from decimal import Decimal

import pytest
from django import forms
from django.utils import timezone

from apps.accounting.models import Currency
from apps.procurement.forms import BudgetMappingForm, CostForecastForm
from apps.procurement.models.BudgetCostManagement.BudgetMappings import BudgetMapping
from apps.procurement.models.BudgetCostManagement.CostForecasts import (
    METHOD_CHOICES, CostForecast, compute_forecast_amounts)

pytestmark = pytest.mark.django_db


# -- local helpers (module-level names are _budgetcost_* so no sibling lane can shadow) --------

_BUDGETCOST_FOREIGN = "That record belongs to another workspace."


def _budgetcost_day(offset=0):
    """A date derived from the SAME basis the models use (L16)."""
    return timezone.localdate() + datetime.timedelta(days=offset)


def _budgetcost_iso(offset=0):
    return _budgetcost_day(offset).strftime("%Y-%m-%d")


def _budgetcost_budget(tenant, name="Ops budget"):
    from apps.accounting.models import Budget
    return Budget.objects.create(tenant=tenant, name=name)


def _budgetcost_org_unit(tenant, name="Operations"):
    from apps.core.models import OrgUnit
    return OrgUnit.objects.create(tenant=tenant, name=name)


def _budgetcost_project(tenant, name="Nav rollout"):
    from apps.accounting.models import Project
    return Project.objects.create(tenant=tenant, name=name)


def _budgetcost_gl(tenant, code="6000", name="Office Supplies", **overrides):
    from apps.accounting.models import GLAccount
    fields = dict(tenant=tenant, code=code, name=name, account_type="expense")
    fields.update(overrides)
    return GLAccount.objects.create(**fields)


def _budgetcost_currency(code="USD", name="US Dollar", **overrides):
    fields = dict(code=code, name=name)
    fields.update(overrides)
    return Currency.objects.create(**fields)


def _budgetcost_widen(form, name, queryset):
    """Simulate a crafted POST: drop the narrowing so layer 2 (the explicit ``_reject_foreign``
    re-check) is what has to refuse the foreign pk."""
    form.fields[name].queryset = queryset
    return form


def _budgetcost_mapping_post(budget=None, org_unit=None, project=None, default_gl_account=None,
                             **overrides):
    """The minimum a budgetMapping POST carries: a budget, a numeric priority, the active flag."""
    data = {"budget": "", "org_unit": "", "project": "", "default_gl_account": "",
            "priority": "100", "is_active": "on", "notes": ""}
    for name, obj in (("budget", budget), ("org_unit", org_unit), ("project", project),
                      ("default_gl_account", default_gl_account)):
        if obj is not None:
            data[name] = str(obj.pk)
    data.update(overrides)
    return data


def _budgetcost_forecast_post(name="Q3 ops spend projection", **overrides):
    """The INPUTS of a forecast. The three amounts and the author stamp are never part of it."""
    data = {"name": name, "budget": "", "method": "blended", "horizon_months": "3",
            "as_of": _budgetcost_iso(), "currency": "", "assumptions": ""}
    data.update(overrides)
    return data


# ===============================================================================================
# 1. Meta.fields contract — the mass-assignment guard (L20/L22)
# ===============================================================================================

def test_budgetcost_mapping_form_meta_fields_match_contract_exactly():
    assert BudgetMappingForm.Meta.fields == [
        "budget", "org_unit", "project", "default_gl_account", "priority", "is_active", "notes",
    ]


def test_budgetcost_mapping_form_never_exposes_tenant_id_or_timestamps(tenant_a):
    banned = {"tenant", "id", "created_at", "updated_at"}
    assert not banned & set(BudgetMappingForm.Meta.fields)
    form = BudgetMappingForm(tenant=tenant_a)
    for name in ("tenant", "id", "created_at", "updated_at"):
        assert name not in form.fields
    assert set(form.fields) == set(BudgetMappingForm.Meta.fields)


def test_budgetcost_forecast_form_meta_fields_match_contract_exactly():
    assert CostForecastForm.Meta.fields == [
        "name", "budget", "method", "horizon_months", "as_of", "currency", "assumptions",
    ]


def test_budgetcost_forecast_form_never_exposes_amounts_number_or_stamps(tenant_a):
    """The three amounts are COMPUTED at create, ``number`` is minted by ``TenantNumbered.save()``
    and ``created_by`` is the authorship stamp — none of them is a field a POST can touch."""
    banned = {"tenant", "number", "committed_amount", "historical_amount", "forecast_amount",
              "created_by", "id", "created_at", "updated_at"}
    assert not banned & set(CostForecastForm.Meta.fields)
    form = CostForecastForm(tenant=tenant_a)
    for name in banned:
        assert name not in form.fields
    assert set(form.fields) == set(CostForecastForm.Meta.fields)


@pytest.mark.parametrize("model,form_class", [
    (BudgetMapping, BudgetMappingForm),
    (CostForecast, CostForecastForm),
])
def test_budgetcost_no_editable_false_column_is_ever_a_form_field(tenant_a, model, form_class):
    """The generic form of the assertion above: every system-owned column (``editable=False``,
    which covers ``number``, the computed amounts and every ``auto_now*`` stamp) is absent from
    the form that binds this model."""
    system_owned = {f.name for f in model._meta.fields if not f.editable}
    assert system_owned, "expected at least one system-owned column on this model"
    assert not system_owned & set(form_class(tenant=tenant_a).fields)


def test_budgetcost_costforecast_has_no_edit_form(tenant_a):
    """A forecast is a FROZEN projection — a wrong one is deleted and re-frozen, never amended.
    The only form bound to CostForecast anywhere in the package is the create form."""
    import apps.procurement.forms as procurement_forms
    from apps.procurement.forms.BudgetCostManagement import CostForecasts as forecast_forms

    assert not hasattr(procurement_forms, "CostForecastEditForm")
    bound = [obj for obj in vars(forecast_forms).values()
             if isinstance(obj, type) and issubclass(obj, forms.ModelForm)
             and getattr(getattr(obj, "Meta", None), "model", None) is CostForecast]
    assert bound == [CostForecastForm]


# ===============================================================================================
# 2. BudgetMappingForm — required fields and invalid input
# ===============================================================================================

def test_budgetcost_mapping_form_requires_budget_and_priority(tenant_a):
    form = BudgetMappingForm({}, tenant=tenant_a)
    assert not form.is_valid()
    assert "budget" in form.errors
    assert "priority" in form.errors
    # The three narrowing dropdowns are optional, labelled "- any -".
    for name in ("org_unit", "project", "default_gl_account"):
        assert name not in form.errors
        assert form.fields[name].required is False
        assert form.fields[name].empty_label == "- any -"


@pytest.mark.parametrize("junk", ["not-a-number", "-5"])
def test_budgetcost_mapping_form_rejects_junk_priority(tenant_a, junk):
    budget = _budgetcost_budget(tenant_a)
    form = BudgetMappingForm(_budgetcost_mapping_post(budget=budget, priority=junk),
                             tenant=tenant_a)
    assert not form.is_valid()
    assert "priority" in form.errors
    assert BudgetMapping.objects.count() == 0


# ===============================================================================================
# 3. BudgetMappingForm — tenant-scoped dropdowns
# ===============================================================================================

def test_budgetcost_mapping_form_dropdowns_are_scoped_to_the_workspace(tenant_a, tenant_b):
    budget_a = _budgetcost_budget(tenant_a)
    budget_b = _budgetcost_budget(tenant_b, "Globex budget")
    org_a = _budgetcost_org_unit(tenant_a)
    org_b = _budgetcost_org_unit(tenant_b, "Globex Operations")
    project_a = _budgetcost_project(tenant_a)
    project_b = _budgetcost_project(tenant_b, "Globex rollout")
    gl_a = _budgetcost_gl(tenant_a)
    gl_b = _budgetcost_gl(tenant_b, name="Globex Expense")

    form = BudgetMappingForm(tenant=tenant_a)
    assert list(form.fields["budget"].queryset) == [budget_a]
    assert list(form.fields["org_unit"].queryset) == [org_a]
    assert list(form.fields["project"].queryset) == [project_a]
    assert list(form.fields["default_gl_account"].queryset) == [gl_a]
    for name, foreign in (("budget", budget_b), ("org_unit", org_b), ("project", project_b),
                          ("default_gl_account", gl_b)):
        assert foreign not in form.fields[name].queryset, f"{name} leaked a tenant-B row"


def test_budgetcost_mapping_form_dropdowns_follow_the_contract_ordering(tenant_a):
    first = _budgetcost_budget(tenant_a, "First budget")
    second = _budgetcost_budget(tenant_a, "Second budget")
    zeta = _budgetcost_org_unit(tenant_a, "Zeta team")
    alpha = _budgetcost_org_unit(tenant_a, "Alpha team")
    proj_z = _budgetcost_project(tenant_a, "Zebra rollout")
    proj_a = _budgetcost_project(tenant_a, "Alpha rollout")
    gl_high = _budgetcost_gl(tenant_a, code="6100", name="Travel")
    gl_low = _budgetcost_gl(tenant_a, code="6000", name="Office Supplies")

    form = BudgetMappingForm(tenant=tenant_a)
    assert list(form.fields["budget"].queryset) == [second, first]          # order_by("-id")
    assert list(form.fields["org_unit"].queryset) == [alpha, zeta]          # order_by("name")
    assert list(form.fields["project"].queryset) == [proj_a, proj_z]        # order_by("name")
    assert list(form.fields["default_gl_account"].queryset) == [gl_low, gl_high]  # by code


def test_budgetcost_mapping_form_gl_dropdown_hides_retired_accounts(tenant_a):
    active = _budgetcost_gl(tenant_a, code="6000")
    retired = _budgetcost_gl(tenant_a, code="6999", name="Retired expense", is_active=False)
    field = BudgetMappingForm(tenant=tenant_a).fields["default_gl_account"]
    assert active in field.queryset
    assert retired not in field.queryset


def test_budgetcost_mapping_form_with_no_tenant_offers_nothing(tenant_a, tenant_b):
    """The superuser has ``tenant=None`` by design; a tenant-less form must not be able to see
    OR post another workspace's rows."""
    _budgetcost_budget(tenant_a)
    _budgetcost_budget(tenant_b, "Globex budget")
    _budgetcost_org_unit(tenant_a)
    _budgetcost_org_unit(tenant_b, "Globex Operations")
    _budgetcost_project(tenant_a)
    _budgetcost_project(tenant_b, "Globex rollout")
    _budgetcost_gl(tenant_a)
    _budgetcost_gl(tenant_b, name="Globex Expense")

    form = BudgetMappingForm(tenant=None)
    for name in ("budget", "org_unit", "project", "default_gl_account"):
        assert list(form.fields[name].queryset) == [], f"{name} offered rows with no tenant"


# ===============================================================================================
# 4. BudgetMappingForm — the crafted-POST re-check (_reject_foreign)
# ===============================================================================================

def test_budgetcost_mapping_form_narrowed_select_refuses_a_foreign_budget(tenant_a, tenant_b):
    """Layer 1: the narrowed <select> never offers the row, so its pk is an invalid choice."""
    foreign = _budgetcost_budget(tenant_b, "Globex budget")
    form = BudgetMappingForm(_budgetcost_mapping_post(budget=foreign), tenant=tenant_a)
    assert not form.is_valid()
    assert "Select a valid choice" in " ".join(form.errors["budget"])
    assert BudgetMapping.objects.count() == 0


@pytest.mark.parametrize("field_name", ["budget", "org_unit", "project", "default_gl_account"])
def test_budgetcost_mapping_form_rejects_a_crafted_foreign_pk(tenant_a, tenant_b, field_name):
    """Layer 2: a narrowed <select> is UX; the hand-edited POST never goes near it. Widen the
    queryset and the explicit ``_reject_foreign`` re-check is what has to refuse the row."""
    mine_budget = _budgetcost_budget(tenant_a)
    foreign = {
        "budget": _budgetcost_budget(tenant_b, "Globex budget"),
        "org_unit": _budgetcost_org_unit(tenant_b, "Globex Operations"),
        "project": _budgetcost_project(tenant_b, "Globex rollout"),
        "default_gl_account": _budgetcost_gl(tenant_b, name="Globex Expense"),
    }[field_name]
    payload = _budgetcost_mapping_post(budget=mine_budget)
    payload[field_name] = str(foreign.pk)
    form = BudgetMappingForm(payload, tenant=tenant_a)
    _budgetcost_widen(form, field_name, type(foreign).objects.all())
    assert not form.is_valid()
    assert _BUDGETCOST_FOREIGN in form.errors[field_name]
    assert BudgetMapping.objects.count() == 0


def test_budgetcost_mapping_form_valid_post_saves_with_the_view_tenant_stamp(tenant_a):
    """Happy path, exactly the way ``crud_create`` does it: ``save(commit=False)`` + the
    tenant stamp, then the single ``save()``."""
    budget = _budgetcost_budget(tenant_a)
    org = _budgetcost_org_unit(tenant_a)
    project = _budgetcost_project(tenant_a)
    gl = _budgetcost_gl(tenant_a)
    data = _budgetcost_mapping_post(budget=budget, org_unit=org, project=project,
                                    default_gl_account=gl, priority="50",
                                    notes="Department override")
    form = BudgetMappingForm(data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save(commit=False)
    obj.tenant = tenant_a
    obj.save()
    assert obj.pk is not None
    assert obj.tenant_id == tenant_a.pk
    assert obj.budget_id == budget.pk
    assert obj.org_unit_id == org.pk
    assert obj.project_id == project.pk
    assert obj.default_gl_account_id == gl.pk
    assert obj.priority == 50
    assert obj.is_active is True
    assert BudgetMapping.objects.filter(tenant=tenant_a).count() == 1


# ===============================================================================================
# 5. CostForecastForm — required fields and invalid input
# ===============================================================================================

def test_budgetcost_forecast_form_requires_name_method_horizon_and_as_of(tenant_a):
    form = CostForecastForm({}, tenant=tenant_a)
    assert not form.is_valid()
    for name in ("name", "method", "horizon_months", "as_of"):
        assert name in form.errors, f"expected {name} to be required"
    # The optional axes: blank budget = whole workspace, currency = display label only.
    for name in ("budget", "currency", "assumptions"):
        assert name not in form.errors


def test_budgetcost_forecast_form_rejects_an_unknown_method(tenant_a):
    form = CostForecastForm(_budgetcost_forecast_post(method="astrology"), tenant=tenant_a)
    assert not form.is_valid()
    assert "method" in form.errors
    assert CostForecast.objects.count() == 0


def test_budgetcost_forecast_form_method_choices_come_from_the_model_vocabulary(tenant_a):
    field = CostForecastForm(tenant=tenant_a).fields["method"]
    assert [value for value, _label in field.choices] == [
        value for value, _label in METHOD_CHOICES]
    assert field.required is True


@pytest.mark.parametrize("value", ["0", "25"])
def test_budgetcost_forecast_form_rejects_a_horizon_outside_1_24(tenant_a, value):
    """The MODEL validators (MinValueValidator(1) / MaxValueValidator(24)) surface as a form
    error on ``horizon_months`` — the form declares nothing of its own here."""
    form = CostForecastForm(_budgetcost_forecast_post(horizon_months=value), tenant=tenant_a)
    assert not form.is_valid()
    assert "horizon_months" in form.errors
    assert CostForecast.objects.count() == 0


@pytest.mark.parametrize("value", ["1", "24"])
def test_budgetcost_forecast_form_accepts_horizons_on_the_boundary(tenant_a, value):
    form = CostForecastForm(_budgetcost_forecast_post(horizon_months=value), tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_budgetcost_forecast_form_rejects_a_malformed_as_of(tenant_a):
    form = CostForecastForm(_budgetcost_forecast_post(as_of="not-a-date"), tenant=tenant_a)
    assert not form.is_valid()
    assert "as_of" in form.errors
    assert CostForecast.objects.count() == 0


# ===============================================================================================
# 6. CostForecastForm — tenant-scoped dropdowns (and the deliberate global currency)
# ===============================================================================================

def test_budgetcost_forecast_form_budget_dropdown_is_scoped_and_labelled(tenant_a, tenant_b):
    mine = _budgetcost_budget(tenant_a)
    theirs = _budgetcost_budget(tenant_b, "Globex budget")
    form = CostForecastForm(tenant=tenant_a)
    assert list(form.fields["budget"].queryset) == [mine]
    assert theirs not in form.fields["budget"].queryset
    assert form.fields["budget"].required is False
    assert form.fields["budget"].empty_label == "- whole workspace -"


def test_budgetcost_forecast_form_currency_is_global_not_tenant_scoped(tenant_a, tenant_b):
    """The deliberate counter-example: ``Currency`` carries NO tenant column, so both forms
    offer the same active rows to every workspace — the narrowing is active-only + ordering,
    not a tenancy boundary."""
    usd = _budgetcost_currency("USD", "US Dollar")
    eur = _budgetcost_currency("EUR", "Euro")
    retired = _budgetcost_currency("GBP", "Pound sterling", is_active=False)
    assert "tenant" not in {f.name for f in Currency._meta.fields}

    for tenant in (tenant_a, tenant_b):
        field = CostForecastForm(tenant=tenant).fields["currency"]
        assert list(field.queryset) == [eur, usd]          # active only, order_by("code")
        assert retired not in field.queryset
        assert field.empty_label == "- not labelled -"
        assert field.required is False


def test_budgetcost_forecast_form_with_no_tenant_offers_no_budgets(tenant_a, tenant_b):
    """``tenant=None`` empties the one tenant-scoped FK. (``currency`` stays global by design —
    it has no tenant column to scope — and the view refuses tenant-less creates outright.)"""
    _budgetcost_budget(tenant_a)
    _budgetcost_budget(tenant_b, "Globex budget")
    form = CostForecastForm(tenant=None)
    assert list(form.fields["budget"].queryset) == []


# ===============================================================================================
# 7. CostForecastForm — the crafted-POST re-check and the frozen happy path
# ===============================================================================================

def test_budgetcost_forecast_form_narrowed_select_refuses_a_foreign_budget(tenant_a, tenant_b):
    foreign = _budgetcost_budget(tenant_b, "Globex budget")
    form = CostForecastForm(_budgetcost_forecast_post(budget=str(foreign.pk)), tenant=tenant_a)
    assert not form.is_valid()
    assert "Select a valid choice" in " ".join(form.errors["budget"])
    assert CostForecast.objects.count() == 0


def test_budgetcost_forecast_form_rejects_a_crafted_foreign_budget_pk(tenant_a, tenant_b):
    """Layer 2: widen the budget queryset to simulate the hand-edited POST — the explicit
    ``_reject_foreign`` re-check is what has to refuse the row, on the field."""
    foreign = _budgetcost_budget(tenant_b, "Globex budget")
    form = CostForecastForm(_budgetcost_forecast_post(budget=str(foreign.pk)), tenant=tenant_a)
    _budgetcost_widen(form, "budget", type(foreign).objects.all())
    assert not form.is_valid()
    assert _BUDGETCOST_FOREIGN in form.errors["budget"]
    assert CostForecast.objects.count() == 0


def test_budgetcost_forecast_form_valid_post_freezes_with_the_view_stamp(tenant_a, admin_user):
    """Happy path, exactly the way ``costforecast_create`` does it: ``save(commit=False)``,
    the tenant stamp, the computed amounts and the authorship stamp, then the single save."""
    form = CostForecastForm(
        _budgetcost_forecast_post(name="Q3 ops spend projection", method="run_rate",
                                  horizon_months="6"),
        tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save(commit=False)
    obj.tenant = tenant_a
    amounts = compute_forecast_amounts(tenant_a, obj.budget, obj.method, obj.horizon_months,
                                       obj.as_of)
    obj.committed_amount = amounts["committed"]
    obj.historical_amount = amounts["historical"]
    obj.forecast_amount = amounts["forecast"]
    obj.created_by = admin_user
    obj.save()
    assert obj.number.startswith("FCST-")
    assert obj.tenant_id == tenant_a.pk
    assert obj.budget_id is None                      # blank = whole workspace
    assert obj.method == "run_rate"
    assert obj.horizon_months == 6
    assert obj.as_of == _budgetcost_day()
    assert obj.created_by_id == admin_user.pk
    # An empty workspace commits nothing and has invoiced nothing -> frozen zeros.
    assert obj.committed_amount == Decimal("0")
    assert obj.historical_amount == Decimal("0")
    assert obj.forecast_amount == Decimal("0")


def test_budgetcost_forecast_form_ignores_posted_system_fields(tenant_a):
    """A crafted POST carrying the computed amounts, the number or the authorship stamp is
    dropped on the floor — none of those is a field this form binds."""
    data = _budgetcost_forecast_post(number="FCST-99999", committed_amount="999.00",
                                     historical_amount="888.00", forecast_amount="777.00",
                                     created_by="1", tenant=str(tenant_a.pk))
    form = CostForecastForm(data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.number.startswith("FCST-") and obj.number != "FCST-99999"
    assert obj.committed_amount == Decimal("0")
    assert obj.historical_amount == Decimal("0")
    assert obj.forecast_amount == Decimal("0")
    assert obj.created_by_id is None
    assert obj.tenant_id == tenant_a.pk
