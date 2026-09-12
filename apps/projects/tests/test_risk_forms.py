"""Projects 7.5 Risk & Issue Management — FORM tests (the write boundary).

The forms lane owns the claim that the ONLY writable columns are the planning data:

* **Verb-written fields are OFF every ModelForm.** ``status``/``closed_at``/``created_by`` on the
  risk, ``status``/``completed_at``/``created_by`` on the action, the nine evidence stamps on the
  issue, and ``escalated_by``/``escalated_at``/``resolved_at``/``created_by`` on the escalation —
  a forged POST cannot set what only ``rsk_realize``/``iss_escalate``/``iss_resolve``/``rra_complete``
  may write.
* **Tenant scoping has two layers.** The narrowed ``<select>`` queryset is UX; ``_reject_foreign``
  is the boundary. Each register's foreign-FK test runs BOTH shapes (the 7.4 lane's pattern): the
  scoped form refuses with a field error, and with the queryset deliberately widened — the shape a
  crafted POST that never went near the widget takes — the backstop still refuses, and no row is
  saved either way.
* **The two companion forms keep their theme classes** (the I5 fix): ``IssueResolutionForm`` and
  ``RiskClosureForm`` are plain ``forms.Form`` objects that never run ``TenantModelForm``'s
  widget-class loop, so their textareas carry ``form-textarea`` explicitly — a regression here
  renders raw browser controls on the detail pages.
* **The escalation level is a TypedChoiceField over ``LEVEL_CHOICES``** — one vocabulary shared by
  the filter, the form and ``iss_escalate``; ``level=5`` is not a tier.

Naming (mandatory): every test is ``test_risk_*``, every module-level helper ``_risk_*``. Flat
functions, house style — no Test* classes.

Scope: forms only. Model guards/arithmetic belong to the model lane; URL/verb behaviour and
permissions to the view and security lanes.
"""
from decimal import Decimal

from apps.projects.forms import (
    IssueEscalationForm,
    IssueResolutionForm,
    ProjectIssueForm,
    ProjectRiskForm,
    RiskClosureForm,
    RiskResponseActionForm,
)
from apps.projects.models import (
    IssueEscalation,
    ProjectIssue,
    ProjectRisk,
    RiskResponseAction,
)
from apps.projects.tests.conftest import (
    _risk,
    _risk_issue,
    _risk_project,
    _risk_today,
)

D = Decimal


# ==============================================================================================
# POST-data helpers — the valid happy-path body each test then sabotages
# ==============================================================================================

def _risk_risk_data(project, **overrides):
    data = {
        "project": project.pk, "title": "Form-lane risk", "description": "Something may slip.",
        "probability": "2", "impact": "2", "cost_impact": "0.00",
        "category": "other", "risk_type": "threat", "response_strategy": "mitigate",
        "identified_date": str(_risk_today()),
    }
    data.update(overrides)
    return data


def _risk_action_data(risk, **overrides):
    data = {"risk": risk.pk, "title": "Form-lane action", "strategy": "mitigate",
            "cost": "0.00"}
    data.update(overrides)
    return data


def _risk_issue_data(project, **overrides):
    data = {
        "project": project.pk, "title": "Form-lane issue",
        "description": "Something already did.", "issue_type": "issue", "severity": "medium",
        "identified_date": str(_risk_today()),
    }
    data.update(overrides)
    return data


def _risk_escalation_data(issue, **overrides):
    data = {"issue": issue.pk, "level": "2", "reason": "Blocked beyond the team."}
    data.update(overrides)
    return data


# ==============================================================================================
# Meta.fields — the write boundary per form
# ==============================================================================================

def test_risk_form_fields_exclude_the_verb_written_columns():
    assert ProjectRiskForm._meta.model is ProjectRisk
    assert set(ProjectRiskForm._meta.fields) == {
        "project", "wbs_node", "title", "description", "cause", "effect", "category",
        "risk_type", "probability", "impact", "cost_impact", "schedule_impact_days",
        "response_strategy", "response_note", "trigger", "contingency_plan", "owner",
        "identified_by", "identified_date", "review_date", "residual_probability",
        "residual_impact", "contingency_account", "lessons_learned"}
    for forbidden in ("status", "closed_at", "created_by", "number", "tenant"):
        assert forbidden not in ProjectRiskForm._meta.fields


def test_risk_action_form_fields_exclude_the_verb_written_columns():
    assert set(RiskResponseActionForm._meta.fields) == {
        "risk", "title", "description", "strategy", "owner", "due_date", "cost",
        "trigger", "residual_probability", "residual_impact"}
    for forbidden in ("status", "completed_at", "created_by", "number", "tenant"):
        assert forbidden not in RiskResponseActionForm._meta.fields


def test_risk_issue_form_fields_exclude_the_evidence_stamps():
    assert set(ProjectIssueForm._meta.fields) == {
        "project", "wbs_node", "risk", "title", "description", "issue_type", "severity",
        "owner", "raised_by", "identified_date", "due_date", "lessons_learned"}
    for forbidden in ("status", "root_cause", "resolution_note", "resolved_by", "resolved_at",
                      "escalation_level", "escalated_to", "escalated_at", "created_by",
                      "number", "tenant"):
        assert forbidden not in ProjectIssueForm._meta.fields


def test_risk_escalation_form_fields_exclude_the_trail_stamps():
    assert set(IssueEscalationForm._meta.fields) == {
        "issue", "level", "target_role", "target_user", "reason", "outcome"}
    for forbidden in ("escalated_by", "escalated_at", "resolved_at", "created_by",
                      "number", "tenant"):
        assert forbidden not in IssueEscalationForm._meta.fields


def test_risk_escalation_level_is_a_choice_field_over_the_four_tiers():
    field = IssueEscalationForm().fields["level"]
    assert field.choices == list(IssueEscalation.LEVEL_CHOICES)
    assert field.coerce is int


# ==============================================================================================
# The create path works — a valid POST saves with tenant stamped and a number minted
# ==============================================================================================

def test_risk_form_valid_post_creates_the_row(tenant_a, risk_project_a):
    form = ProjectRiskForm(_risk_risk_data(risk_project_a), tenant=tenant_a)
    assert form.is_valid(), form.errors
    row = form.save()
    assert row.pk and row.tenant_id == tenant_a.pk
    assert row.number.startswith("RSK-")
    assert row.status == "identified"  # the verb-written default, not form-supplied


def test_risk_issue_form_valid_post_creates_the_row(tenant_a, risk_project_a):
    form = ProjectIssueForm(_risk_issue_data(risk_project_a), tenant=tenant_a)
    assert form.is_valid(), form.errors
    row = form.save()
    assert row.pk and row.number.startswith("ISS-")
    assert row.status == "open" and row.escalation_level == 0


def test_risk_action_form_valid_post_creates_the_row(tenant_a, risk_project_a):
    risk = _risk(tenant_a, risk_project_a)
    form = RiskResponseActionForm(_risk_action_data(risk), tenant=tenant_a)
    assert form.is_valid(), form.errors
    row = form.save()
    assert row.pk and row.number.startswith("RRA-")
    assert row.status == "planned"


def test_risk_escalation_form_valid_post_creates_the_row(tenant_a, risk_project_a):
    issue = _risk_issue(tenant_a, risk_project_a)
    form = IssueEscalationForm(_risk_escalation_data(issue), tenant=tenant_a)
    assert form.is_valid(), form.errors
    row = form.save()
    assert row.pk and row.number.startswith("ESC-")
    assert row.level == 2


# ==============================================================================================
# Required-field evidence — reason and resolution are not optional
# ==============================================================================================

def test_risk_escalation_reason_is_required(tenant_a, risk_project_a):
    issue = _risk_issue(tenant_a, risk_project_a)
    data = _risk_escalation_data(issue)
    data.pop("reason")
    form = IssueEscalationForm(data, tenant=tenant_a)
    assert not form.is_valid() and "reason" in form.errors


def test_risk_resolution_note_is_required_root_cause_is_not():
    form = IssueResolutionForm({"root_cause": "why", "resolution_note": ""})
    assert not form.is_valid() and "resolution_note" in form.errors
    ok = IssueResolutionForm({"resolution_note": "what was done"})
    assert ok.is_valid()
    assert IssueResolutionForm().fields["root_cause"].required is False


def test_risk_escalation_level_five_is_not_a_tier(tenant_a, risk_project_a):
    issue = _risk_issue(tenant_a, risk_project_a)
    form = IssueEscalationForm(_risk_escalation_data(issue, level="5"), tenant=tenant_a)
    assert not form.is_valid() and "level" in form.errors


# ==============================================================================================
# Widget classes — the I5 regression guard (plain forms get no widget-class loop)
# ==============================================================================================

def test_risk_resolution_form_textareas_carry_the_theme_class():
    for name in ("root_cause", "resolution_note"):
        widget = IssueResolutionForm().fields[name].widget
        assert widget.attrs.get("class") == "form-textarea", name
        assert "textarea" in widget.__class__.__name__.lower()


def test_risk_closure_form_textarea_carries_the_theme_class():
    widget = RiskClosureForm().fields["lessons_learned"].widget
    assert widget.attrs.get("class") == "form-textarea"
    assert "textarea" in widget.__class__.__name__.lower()
    assert RiskClosureForm().fields["lessons_learned"].required is False


# ==============================================================================================
# Tenant scoping, both layers — narrowed dropdown refuses; widened, the backstop still refuses
# ==============================================================================================

def test_risk_form_project_dropdown_is_tenant_scoped(tenant_a, tenant_b, risk_project_a,
                                                     risk_project_b):
    fields = ProjectRiskForm(tenant=tenant_a).fields
    assert risk_project_a in fields["project"].queryset
    assert risk_project_b not in fields["project"].queryset


def test_risk_issue_form_dropdowns_are_tenant_scoped(tenant_a, tenant_b, risk_project_a,
                                                     risk_project_b, risk_b):
    fields = ProjectIssueForm(tenant=tenant_a).fields
    assert risk_project_b not in fields["project"].queryset
    assert risk_b not in fields["risk"].queryset


def test_risk_action_form_risk_dropdown_is_tenant_scoped(tenant_a, tenant_b, risk_project_a,
                                                         risk_b):
    fields_b = RiskResponseActionForm(tenant=tenant_b).fields
    assert risk_b in fields_b["risk"].queryset
    assert _risk(tenant_a, risk_project_a) not in fields_b["risk"].queryset


def test_risk_escalation_form_issue_dropdown_is_tenant_scoped(tenant_a, tenant_b,
                                                              risk_project_a, risk_issue_b):
    fields_b = IssueEscalationForm(tenant=tenant_b).fields
    assert risk_issue_b in fields_b["issue"].queryset
    assert _risk_issue(tenant_a, risk_project_a) not in fields_b["issue"].queryset


def test_risk_form_refuses_foreign_project_scoped(tenant_a, risk_project_a, risk_project_b):
    form = ProjectRiskForm(_risk_risk_data(risk_project_b), tenant=tenant_a)
    assert not form.is_valid()
    assert "project" in form.errors
    assert not ProjectRisk.objects.exists()


def test_risk_form_refuses_foreign_project_widened(tenant_a, risk_project_a, risk_project_b):
    form = ProjectRiskForm(_risk_risk_data(risk_project_b), tenant=tenant_a)
    form.fields["project"].queryset = type(risk_project_a).objects.all()
    assert not form.is_valid()
    assert ProjectRisk.objects.count() == 0


def test_risk_action_form_refuses_foreign_risk_widened(tenant_a, risk_b):
    form = RiskResponseActionForm(_risk_action_data(risk_b), tenant=tenant_a)
    form.fields["risk"].queryset = RiskResponseAction._meta.get_field("risk").related_model \
        .objects.all()
    assert not form.is_valid()
    assert RiskResponseAction.objects.count() == 0


def test_risk_issue_form_refuses_foreign_risk_widened(tenant_a, risk_project_a, risk_b):
    form = ProjectIssueForm(_risk_issue_data(risk_project_a, risk=risk_b.pk), tenant=tenant_a)
    form.fields["risk"].queryset = ProjectRisk.objects.all()
    assert not form.is_valid()
    assert ProjectIssue.objects.count() == 0


def test_risk_escalation_form_refuses_foreign_issue_widened(tenant_a, risk_issue_b):
    form = IssueEscalationForm(_risk_escalation_data(risk_issue_b), tenant=tenant_a)
    form.fields["issue"].queryset = ProjectIssue.objects.all()
    assert not form.is_valid()
    assert IssueEscalation.objects.count() == 0
