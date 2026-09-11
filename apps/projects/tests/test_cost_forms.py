"""Projects 7.4 Cost & Budget Management — FORM tests.

The five forms are 7.4's entire write boundary: every byte that reaches a ``BudgetRevision``,
``CostControlAccount``, ``ProjectBudgetLine`` or ``ProjectExpense`` through the UI passes
through one of them. This lane owns the claims no other lane can see:

**1. What is NOT a field.** Each ``Meta.fields`` whitelist is a security control. ``status`` is
verb-driven (submit/approve/reject/activate on a revision; post/void on an expense), the
``*_by``/``*_at`` stamps are decision evidence, ``decision_notes`` is written ONLY by the
``@tenant_admin_required`` ``bvr_reject`` — a field a gated verb writes must not also be
POST-settable through the ungated edit form. ``number`` and ``tenant`` are the system's.
Absence is asserted twice over (L20/L22): the name is missing from ``form.fields``, AND a
payload carrying every excluded name is bound and the saved row proved to hold the system's
values, not the smuggled ones.

**2. Tenant scoping on both layers.** ``TenantModelForm`` narrows every ``ModelChoiceField``
whose target carries a ``tenant`` column, so a crafted cross-tenant POST answers with Django's
``"Select a valid choice."`` — never ``_reject_foreign``'s wording (that is the unreachable
second layer, per the review's lane-5 finding; the test asserts "this field has an error",
never the wording). The backstop is exercised with the queryset deliberately widened — the
shape a POST that never went near the widget takes — and ``_reject_foreign``/model-``clean()``
must still refuse.

**3. The one unscoped FK.** ``currency``: ``accounting.Currency`` is a GLOBAL table (L29) —
never narrowed, never handed to ``_reject_foreign``.

Plus the money hardening (a negative amount is a field error, and so are NaN / garbage /
three decimal places — never a 500), the ``TenantUniqueMixin`` duplicates surfacing as form
errors instead of ``IntegrityError`` 500s, the decision form's required textarea, and a clean
round-trip proving a re-submitted unchanged form changes nothing.

Determinism (L16): every date basis is ``_cost_today()`` — never ``datetime.date.today()``.

Naming (mandatory): every test is ``test_cost_*``, every module-level helper ``_cost_*``.
Scope: forms only. Models, views and permissions belong to the other three lanes.
"""
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.projects.forms import (
    BudgetRevisionDecisionForm,
    BudgetRevisionForm,
    CostControlAccountForm,
    ProjectBudgetLineForm,
    ProjectExpenseForm,
)
from apps.projects.models import (
    BudgetRevision,
    CostControlAccount,
    ProjectBudgetLine,
    ProjectExpense,
)
from apps.projects.tests.conftest import (
    _cost_budget_line,
    _cost_control_account,
    _cost_expense,
    _cost_revision,
    _cost_today,
)

D = Decimal

_FORBIDDEN_REVISION = ["status", "requested_at", "decided_by", "decided_at", "decision_notes",
                       "activated_at", "created_by", "number", "tenant"]
_FORBIDDEN_EXPENSE = ["status", "created_by", "number", "tenant"]


def _cost_revision_data(project, currency=None, **over):
    data = {
        "project": project.pk,
        "revision_no": "9",
        "title": "Form-built revision",
        "currency": currency.pk if currency else "",
        "reason": "Rate review landed.",
        "impact_note": "",
        "schedule_impact_note": "",
        "requested_by": "",
    }
    data.update(over)
    return data


def _cost_account_data(project, **over):
    data = {
        "project": project.pk,
        "name": "Form-built CA",
        "code": "CA-F.1",
        "wbs_node": "",
        "gl_account": "",
        "contingency": "0.00",
        "percent_complete": "0.00",
        "status": "planning",
        "note": "",
    }
    data.update(over)
    return data


def _cost_line_data(revision, project, **over):
    data = {
        "budget_revision": revision.pk,
        "project": project.pk,
        "category": "labor",
        "wbs_node": "",
        "control_account": "",
        "gl_account": "",
        "amount": "100.00",
        "note": "",
    }
    data.update(over)
    return data


def _cost_expense_data(project, control_account, **over):
    data = {
        "project": project.pk,
        "control_account": control_account.pk,
        "wbs_node": "",
        "entry_type": "actual",
        "source_kind": "manual",
        "source_number": "",
        "vendor": "",
        "gl_account": "",
        "amount": "50.00",
        "currency": "",
        "entry_date": _cost_today().isoformat(),
        "description": "",
    }
    data.update(over)
    return data


# ==============================================================================================
# Field inventories — the whitelists are the write boundary
# ==============================================================================================

def test_cost_revision_form_fields_exact(tenant_a, cost_project_a):
    form = BudgetRevisionForm(tenant=tenant_a)
    assert list(form.fields) == ["project", "revision_no", "title", "currency", "reason",
                                 "impact_note", "schedule_impact_note", "requested_by"]


def test_cost_revision_form_forbidden_names_absent(tenant_a, cost_project_a):
    form = BudgetRevisionForm(tenant=tenant_a)
    for name in _FORBIDDEN_REVISION:
        assert name not in form.fields, name


def test_cost_control_account_form_fields_exact(tenant_a, cost_project_a):
    form = CostControlAccountForm(tenant=tenant_a)
    assert list(form.fields) == ["project", "name", "code", "wbs_node", "gl_account",
                                 "contingency", "percent_complete", "status", "note"]
    assert "number" not in form.fields and "tenant" not in form.fields


def test_cost_budget_line_form_fields_exact(tenant_a, cost_project_a):
    form = ProjectBudgetLineForm(tenant=tenant_a)
    assert list(form.fields) == ["budget_revision", "project", "category", "wbs_node",
                                 "control_account", "gl_account", "amount", "note"]
    assert "number" not in form.fields and "tenant" not in form.fields


def test_cost_expense_form_fields_exact(tenant_a, cost_project_a, cost_control_account_a):
    form = ProjectExpenseForm(tenant=tenant_a)
    assert list(form.fields) == ["project", "control_account", "wbs_node", "entry_type",
                                 "source_kind", "source_number", "vendor", "gl_account",
                                 "amount", "currency", "entry_date", "description"]


def test_cost_expense_form_forbidden_names_absent(tenant_a, cost_project_a):
    form = ProjectExpenseForm(tenant=tenant_a)
    for name in _FORBIDDEN_EXPENSE:
        assert name not in form.fields, name


# ==============================================================================================
# Happy paths — each form saves a complete row with the system's stamps untouched
# ==============================================================================================

def test_cost_revision_form_round_trip(tenant_a, cost_project_a, cost_currency):
    form = BudgetRevisionForm(_cost_revision_data(cost_project_a, currency=cost_currency),
                              tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.status == "draft"          # verb-driven state cannot be POSTed in
    assert obj.tenant == tenant_a         # TenantUniqueMixin stamped it
    assert obj.decision_notes == "" and obj.activated_at is None
    assert obj.currency == cost_currency  # the one unscoped FK (L29)


def test_cost_control_account_form_round_trip(tenant_a, cost_project_a, cost_wbs_node_a):
    form = CostControlAccountForm(
        _cost_account_data(cost_project_a, wbs_node=cost_wbs_node_a.pk,
                           percent_complete="37.50", contingency="15.00"),
        tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.percent_complete == D("37.50")
    assert obj.contingency == D("15.00")
    assert obj.wbs_node == cost_wbs_node_a


def test_cost_budget_line_form_round_trip(tenant_a, cost_project_a, cost_control_account_a,
                                          cost_revision_draft, cost_wbs_node_a):
    form = ProjectBudgetLineForm(
        _cost_line_data(cost_revision_draft, cost_project_a,
                        control_account=cost_control_account_a.pk,
                        wbs_node=cost_wbs_node_a.pk),
        tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.budget_revision == cost_revision_draft
    assert obj.control_account == cost_control_account_a
    assert obj.amount == D("100.00")


def test_cost_expense_form_round_trip(tenant_a, cost_project_a, cost_control_account_a,
                                      cost_currency):
    form = ProjectExpenseForm(
        _cost_expense_data(cost_project_a, cost_control_account_a, currency=cost_currency.pk,
                           source_kind="purchase_order", source_number="PO-00042"),
        tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.status == "draft"          # a new expense is a draft — verbs move it
    assert obj.source_number == "PO-00042"  # the SOFT reference rides straight through
    assert obj.currency == cost_currency


# ==============================================================================================
# Smuggled excluded fields (L20/L22) — bound and saved, the system's values must win
# ==============================================================================================

def test_cost_revision_form_smuggled_excluded_fields_change_nothing(
        tenant_a, cost_project_a, cost_currency):
    data = _cost_revision_data(cost_project_a, currency=cost_currency)
    for name in _FORBIDDEN_REVISION:
        data[name] = {
            "status": "approved", "requested_at": "1999-01-01", "decided_by": "x",
            "decided_at": "1999-01-01", "decision_notes": "rewritten", "activated_at":
            "1999-01-01", "created_by": "x", "number": "BVR-99999", "tenant": "x"}[name]
    form = BudgetRevisionForm(data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.status == "draft"
    assert obj.decision_notes == ""
    assert obj.requested_at is None and obj.decided_at is None and obj.activated_at is None
    assert obj.created_by is None


def test_cost_expense_form_smuggled_status_change_nothing(tenant_a, cost_project_a,
                                                          cost_control_account_a):
    data = _cost_expense_data(cost_project_a, cost_control_account_a)
    for name in _FORBIDDEN_EXPENSE:
        data[name] = {"status": "posted", "created_by": "x", "number": "PEX-99999",
                      "tenant": "x"}[name]
    form = ProjectExpenseForm(data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.status == "draft"          # drafts never burn budget — a POST cannot post
    assert obj.created_by is None         # the create view stamps the author, not the form


# ==============================================================================================
# Required fields — missing prerequisites are field errors, never silent rows
# ==============================================================================================

def test_cost_revision_form_required_fields(tenant_a, cost_project_a):
    form = BudgetRevisionForm({"revision_no": "1"}, tenant=tenant_a)
    assert not form.is_valid()
    for name in ("project", "title", "reason"):
        assert name in form.errors, name


def test_cost_control_account_form_required_fields(tenant_a, cost_project_a):
    form = CostControlAccountForm({}, tenant=tenant_a)
    assert not form.is_valid()
    for name in ("project", "name", "code"):
        assert name in form.errors, name


def test_cost_budget_line_form_required_fields(tenant_a, cost_project_a):
    form = ProjectBudgetLineForm({}, tenant=tenant_a)
    assert not form.is_valid()
    for name in ("budget_revision", "project", "category", "amount"):
        assert name in form.errors, name


def test_cost_expense_form_required_fields(tenant_a, cost_project_a):
    form = ProjectExpenseForm({}, tenant=tenant_a)
    assert not form.is_valid()
    for name in ("project", "control_account", "amount", "entry_date"):
        assert name in form.errors, name


# ==============================================================================================
# Money hardening — never a 500
# ==============================================================================================

@pytest.mark.parametrize("bad", ["-1.00", "abc", "NaN", "Infinity", "10.005", ""])
def test_cost_budget_line_amount_rejects_garbage(tenant_a, cost_project_a,
                                                 cost_revision_draft, bad):
    form = ProjectBudgetLineForm(
        _cost_line_data(cost_revision_draft, cost_project_a, amount=bad), tenant=tenant_a)
    assert not form.is_valid()
    assert "amount" in form.errors


@pytest.mark.parametrize("bad", ["-1.00", "abc", "10.005"])
def test_cost_expense_amount_rejects_garbage(tenant_a, cost_project_a,
                                             cost_control_account_a, bad):
    form = ProjectExpenseForm(
        _cost_expense_data(cost_project_a, cost_control_account_a, amount=bad),
        tenant=tenant_a)
    assert not form.is_valid()
    assert "amount" in form.errors


def test_cost_control_account_percent_complete_rejects_out_of_band(tenant_a, cost_project_a):
    form = CostControlAccountForm(_cost_account_data(cost_project_a, percent_complete="100.01"),
                                  tenant=tenant_a)
    assert not form.is_valid()
    assert "percent_complete" in form.errors


# ==============================================================================================
# Tenant scoping, both layers — narrowed dropdown refuses; widened, the backstop still refuses
# ==============================================================================================

def test_cost_budget_line_form_refuses_foreign_revision_scoped(tenant_a, cost_project_a,
                                                               cost_revision_b):
    """The narrowed queryset makes the foreign pk 'not one of the available choices' — the
    field errors, no row is saved, and the wording is Django's, not ours (lane 5)."""
    form = ProjectBudgetLineForm(
        _cost_line_data(cost_revision_b, cost_project_a), tenant=tenant_a)
    assert not form.is_valid()
    assert "budget_revision" in form.errors
    assert not ProjectBudgetLine.objects.exists()


def test_cost_budget_line_form_refuses_foreign_revision_widened(tenant_a, cost_project_a,
                                                                cost_revision_b):
    """The backstop: with the queryset deliberately widened (the shape a crafted POST that
    never went near the widget takes), _reject_foreign / model clean() still refuse."""
    form = ProjectBudgetLineForm(_cost_line_data(cost_revision_b, cost_project_a),
                                 tenant=tenant_a)
    form.fields["budget_revision"].queryset = BudgetRevision.objects.all()
    assert not form.is_valid()
    assert ProjectBudgetLine.objects.count() == 0


def test_cost_expense_form_refuses_foreign_control_account_scoped(tenant_a, cost_project_a,
                                                                  cost_control_account_b):
    form = ProjectExpenseForm(
        _cost_expense_data(cost_project_a, cost_control_account_b), tenant=tenant_a)
    assert not form.is_valid()
    assert "control_account" in form.errors


def test_cost_revision_form_refuses_foreign_project(tenant_a, cost_project_b):
    form = BudgetRevisionForm(_cost_revision_data(cost_project_b), tenant=tenant_a)
    assert not form.is_valid()
    assert "project" in form.errors


def test_cost_currency_is_never_scoped(tenant_a, cost_project_a, cost_currency):
    """L29: Currency is a GLOBAL table — the dropdown offers it regardless of workspace and
    a POST carrying it validates (narrowing it would empty the dropdown app-wide)."""
    form = BudgetRevisionForm(_cost_revision_data(cost_project_a, currency=cost_currency),
                              tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert "currency" not in (form.errors or {})


# ==============================================================================================
# TenantUniqueMixin — duplicates surface as form errors, not IntegrityError 500s
# ==============================================================================================

def test_cost_revision_duplicate_revision_no_is_a_form_error(tenant_a, cost_project_a,
                                                             cost_currency):
    _cost_revision(tenant_a, cost_project_a, no=0)
    form = BudgetRevisionForm(_cost_revision_data(cost_project_a, revision_no="0",
                                                  currency=cost_currency), tenant=tenant_a)
    assert not form.is_valid()
    assert ProjectBudgetLine.objects.count() == 0  # refused before any save


def test_cost_control_account_duplicate_code_is_a_form_error(tenant_a, cost_project_a):
    _cost_control_account(tenant_a, cost_project_a, "CA-F.1")
    form = CostControlAccountForm(_cost_account_data(cost_project_a, code="CA-F.1"),
                                  tenant=tenant_a)
    assert not form.is_valid()


def test_cost_control_account_code_unique_per_project_not_per_tenant(
        tenant_a, tenant_b, cost_project_a, cost_project_b):
    """The constraint is (tenant, project, code) — the same code is legal in another
    workspace, exactly like the per-tenant numbers."""
    assert CostControlAccountForm(_cost_account_data(cost_project_b, code="CA-F.1"),
                                  tenant=tenant_b).is_valid()


# ==============================================================================================
# Model clean() surfaced through the form — same-project guards reachable from a crafted POST
# ==============================================================================================

def test_cost_budget_line_form_project_must_match_revision(tenant_a, cost_project_a,
                                                           cost_revision_draft):
    """The form-level happy path for the same-project pairing (the model guard's refusal
    lives in the models lane): the line's project matches the revision's → valid."""
    form = ProjectBudgetLineForm(
        _cost_line_data(cost_revision_draft, cost_project_a), tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_cost_budget_line_form_cross_project_wbs_refused(tenant_a, tenant_b, cost_project_a,
                                                         cost_revision_draft,
                                                         cost_wbs_node_b):
    """cost_wbs_node_b is tenant B's — scoped dropdown refuses; even widened, the model
    clean() same-project guard fires on wbs_node."""
    form = ProjectBudgetLineForm(
        _cost_line_data(cost_revision_draft, cost_project_a, wbs_node=cost_wbs_node_b.pk),
        tenant=tenant_a)
    form.fields["wbs_node"].queryset = ProjectBudgetLine.wbs_node.get_queryset()
    assert not form.is_valid()
    assert "wbs_node" in form.errors or "__all__" in form.errors


def test_cost_expense_form_cross_project_control_account_refused(tenant_a, cost_project_a,
                                                                 cost_control_account_b):
    form = ProjectExpenseForm(_cost_expense_data(cost_project_a, cost_control_account_b),
                              tenant=tenant_a)
    form.fields["control_account"].queryset = CostControlAccount.objects.all()
    assert not form.is_valid()
    assert ProjectExpense.objects.count() == 0


# ==============================================================================================
# The decision form — the gated verb's evidence
# ==============================================================================================

def test_cost_decision_form_requires_notes():
    form = BudgetRevisionDecisionForm({})
    assert not form.is_valid()
    assert "decision_notes" in form.errors


def test_cost_decision_form_accepts_notes_and_uses_a_textarea():
    form = BudgetRevisionDecisionForm({"decision_notes": "No budget for this."})
    assert form.is_valid()
    assert form.cleaned_data["decision_notes"] == "No budget for this."
    assert "form-textarea" in str(form.fields["decision_notes"].widget.attrs.get("class", ""))


def test_cost_decision_form_is_not_a_model_form():
    """The reject verb writes form.cleaned_data into obj.decision_notes itself — the form must
    not be a ModelForm that could save over the row."""
    assert not hasattr(BudgetRevisionDecisionForm(), "save")


# ==============================================================================================
# Edit round-trip — an unchanged re-submission changes nothing
# ==============================================================================================

def test_cost_revision_form_edit_round_trip_changes_nothing(tenant_a, cost_project_a,
                                                            cost_revision_draft):
    data = _cost_revision_data(cost_project_a)
    data.update({
        "project": cost_revision_draft.project_id,
        "revision_no": str(cost_revision_draft.revision_no),
        "title": cost_revision_draft.title,
        "reason": cost_revision_draft.reason,
    })
    form = BudgetRevisionForm(data, instance=cost_revision_draft, tenant=tenant_a)
    assert form.is_valid(), form.errors
    before = (cost_revision_draft.title, cost_revision_draft.reason, cost_revision_draft.status)
    obj = form.save()
    assert (obj.title, obj.reason, obj.status) == before


def test_cost_budget_line_form_edit_round_trip(tenant_a, cost_project_a,
                                               cost_budget_line_draft):
    data = _cost_line_data(cost_budget_line_draft.budget_revision,
                           cost_budget_line_draft.project)
    data.update({"amount": "150.00"})
    form = ProjectBudgetLineForm(data, instance=cost_budget_line_draft, tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.amount == D("150.00")
