"""Projects 7.6 Quality Management — FORM tests.

The six forms are 7.6's entire write boundary: every byte that reaches a ``QualityPlan``,
``QualityReview``, ``DeliverableInspection`` or ``QualityDefect`` through the UI passes through
one of the four ModelForms, and the two gated decisions (``qci_accept`` / ``qdf_resolve``) pass
through the two plain ``forms.Form`` bodies. This lane owns the claims no other lane can see:

**1. What is NOT a field.** Each ``Meta.fields`` whitelist is a security control (order pinned —
an order-sensitive assert). ``status`` is verb-driven on all four models (approve/supersede ·
report/close · record/accept/reject · resolve/close), the ``*_by``/``*_at`` stamps are decision
evidence, ``project_issue`` is the POST-only ``qdf_raise_issue`` bridge, ``root_cause``/
``resolution_note`` are ``qdf_resolve``'s evidence and ``acceptance_note``/``usage_decision``/
``accepted_by*`` are ``qci_accept``'s — a field a gated verb writes must not also be POST-settable
through the ungated edit form. ``number`` and ``tenant`` are the system's. Absence is asserted
directly on ``form.fields``.

**2. ``TenantUniqueMixin`` FIRST, on every ModelForm.** The mixin stamps ``instance.tenant``
before ``full_clean()`` runs on CREATE, so a valid same-workspace POST is never falsely refused
and the saved row carries the workspace. The stamp is asserted on ``form.instance`` right after
``is_valid()`` and again on the ``save(commit=False)`` instance.

**3. The crafted-POST backstop, with its exact wording.** ``TenantModelForm`` narrows every
tenant-scoped ``ModelChoiceField``, so a foreign pk normally dies as "Select a valid choice" —
that proves the WIDGET was scoped. Widening the queryset first (the shape a crafted POST that
never went near the widget takes) is how ``_reject_foreign`` in each form's ``clean()`` is
reached; its message — "That record belongs to another workspace." — keys on the right field.
``owner``/``reviewer``/``inspector``/``improvement_owner`` are User FKs and ARE on the lists;
``accepted_by_party`` is a ``core.Party`` FK and is NOT — the Party is scoped by queryset
(``_acceptor_parties``) instead, so a tenant-less form offers NO parties and a foreign pk dies
as an invalid choice, never as "another workspace".

**4. The model's same-project guards are reachable from a form POST.** A same-tenant node from a
DIFFERENT project passes the narrowed dropdown and ``_reject_foreign`` (same workspace) — the
model ``clean()`` same-project refusal is what must answer, surfaced as a field error.

Plus the required/optional split (``acceptance_criteria`` and ``QualityDefect.description``
required, ``description``/``scope``-class text optional, ``resolution_note`` required while
``root_cause`` is optional), the acceptance decision's EXACT two-choice vocabulary (no
``reject`` — that is ``qci_reject``'s), the theme widget classes on the plain forms, and round
trips proving the verb-written stamps keep the system's values.

Determinism (L16): every date basis is ``_quality_today()`` (``timezone.localdate()``) — never
``datetime.date.today()``.

Naming (mandatory): every test is ``test_quality_*``, every module-level helper ``_quality_*`` /
``_QUALITY_*``. Flat functions, house style — no Test* classes.

Scope: forms only. Models, views/urls and permissions belong to the other three lanes.
"""
from datetime import timedelta

from apps.projects.forms import (
    DefectResolutionForm,
    DeliverableInspectionForm,
    InspectionAcceptanceForm,
    QualityDefectForm,
    QualityPlanForm,
    QualityReviewForm,
)
from apps.projects.models import (
    DeliverableInspection,
    QualityDefect,
    QualityPlan,
    QualityReview,
)
from apps.projects.tests.conftest import (
    _quality_project,
    _quality_today,
    _quality_wbs_node,
)

# The four whitelists — contract §3 verbatim, order-sensitive.
_QUALITY_PLAN_FIELDS = [
    "project", "wbs_node", "source_risk", "title", "description", "acceptance_criteria",
    "verification_method", "standard_reference", "regulatory_requirement", "owner",
    "planned_review_date",
]
_QUALITY_REVIEW_FIELDS = [
    "project", "wbs_node", "quality_plan", "title", "scope", "review_type", "checklist",
    "findings", "reviewer", "review_date", "maturity_score", "improvement_action",
    "improvement_owner", "improvement_due_date", "improvement_status",
]
_QUALITY_INSPECTION_FIELDS = [
    "project", "wbs_node", "quality_plan", "milestone", "title", "description",
    "inspection_type", "planned_date", "inspected_date", "inspector", "result", "findings",
]
_QUALITY_DEFECT_FIELDS = [
    "project", "wbs_node", "quality_plan", "inspection", "title", "description",
    "defect_category", "severity", "disposition", "owner", "identified_date", "due_date",
    "lessons_learned",
]

# The verb-written stamps + system columns that must never render as fields (L20/L22).
_FORBIDDEN_PLAN = ["status", "approved_by", "approved_at", "created_by", "number", "tenant"]
_FORBIDDEN_REVIEW = ["status", "closed_at", "created_by", "number", "tenant"]
_FORBIDDEN_INSPECTION = ["status", "usage_decision", "accepted_by", "accepted_by_party",
                         "accepted_at", "acceptance_note", "created_by", "number", "tenant"]
_FORBIDDEN_DEFECT = ["status", "project_issue", "root_cause", "resolution_note",
                     "resolved_by", "resolved_at", "created_by", "number", "tenant"]

_REJECT_FOREIGN_MSG = "That record belongs to another workspace."


def _quality_plan_data(project, **over):
    """A valid ``QualityPlanForm`` POST for ``project``."""
    data = {
        "project": project.pk,
        "wbs_node": "",
        "source_risk": "",
        "title": "Form-built plan",
        "description": "What this plan verifies and how.",
        "acceptance_criteria": "Zero critical defects on the acceptance inspection.",
        "verification_method": "inspection",
        "standard_reference": "ISO 9001:2015 cl. 8.5",
        "regulatory_requirement": "",
        "owner": "",
        "planned_review_date": "",
    }
    data.update(over)
    return data


def _quality_review_data(project, **over):
    """A valid ``QualityReviewForm`` POST for ``project``."""
    data = {
        "project": project.pk,
        "wbs_node": "",
        "quality_plan": "",
        "title": "Form-built review",
        "scope": "The delivery process for the current stage.",
        "review_type": "methodology_review",
        "checklist": "",
        "findings": "",
        "reviewer": "",
        "review_date": _quality_today().isoformat(),
        "maturity_score": "",
        "improvement_action": "",
        "improvement_owner": "",
        "improvement_due_date": "",
        "improvement_status": "n_a",
    }
    data.update(over)
    return data


def _quality_inspection_data(project, **over):
    """A valid ``DeliverableInspectionForm`` POST for ``project``."""
    data = {
        "project": project.pk,
        "wbs_node": "",
        "quality_plan": "",
        "milestone": "",
        "title": "Form-built inspection",
        "description": "The protocol the inspection follows.",
        "inspection_type": "review",
        "planned_date": "",
        "inspected_date": "",
        "inspector": "",
        "result": "pending",
        "findings": "",
    }
    data.update(over)
    return data


def _quality_defect_data(project, **over):
    """A valid ``QualityDefectForm`` POST for ``project``."""
    data = {
        "project": project.pk,
        "wbs_node": "",
        "quality_plan": "",
        "inspection": "",
        "title": "Form-built defect",
        "description": "The output does not meet the acceptance criterion.",
        "defect_category": "other",
        "severity": "minor",
        "disposition": "open",
        "owner": "",
        "identified_date": _quality_today().isoformat(),
        "due_date": "",
        "lessons_learned": "",
    }
    data.update(over)
    return data


def _quality_widen(form, *names):
    """Drop the tenant narrowing off named ``ModelChoiceField``s, in place.

    A narrowed ``<select>`` refuses a foreign pk as "Select a valid choice" — a real control, but
    it only proves the widget was scoped. Widening first simulates a crafted POST that never went
    near the widget, so what answers is the second layer: ``_reject_foreign`` in the form's
    ``clean()``, with its own wording.
    """
    for name in names:
        field = form.fields[name]
        field.queryset = field.queryset.model._default_manager.all()
    return form


# ==============================================================================================
# Field inventories — the whitelists are the write boundary (order-sensitive)
# ==============================================================================================

def test_quality_plan_form_fields_exact(tenant_a):
    form = QualityPlanForm(tenant=tenant_a)
    assert QualityPlanForm.Meta.fields == _QUALITY_PLAN_FIELDS
    assert list(form.fields) == _QUALITY_PLAN_FIELDS
    for name in _FORBIDDEN_PLAN:
        assert name not in form.fields, name


def test_quality_review_form_fields_exact(tenant_a):
    form = QualityReviewForm(tenant=tenant_a)
    assert QualityReviewForm.Meta.fields == _QUALITY_REVIEW_FIELDS
    assert list(form.fields) == _QUALITY_REVIEW_FIELDS
    for name in _FORBIDDEN_REVIEW:
        assert name not in form.fields, name


def test_quality_inspection_form_fields_exact(tenant_a):
    form = DeliverableInspectionForm(tenant=tenant_a)
    assert DeliverableInspectionForm.Meta.fields == _QUALITY_INSPECTION_FIELDS
    assert list(form.fields) == _QUALITY_INSPECTION_FIELDS
    for name in _FORBIDDEN_INSPECTION:
        assert name not in form.fields, name


def test_quality_defect_form_fields_exact(tenant_a):
    form = QualityDefectForm(tenant=tenant_a)
    assert QualityDefectForm.Meta.fields == _QUALITY_DEFECT_FIELDS
    assert list(form.fields) == _QUALITY_DEFECT_FIELDS
    for name in _FORBIDDEN_DEFECT:
        assert name not in form.fields, name


# ==============================================================================================
# Required / optional — missing prerequisites are field errors, never silent rows
# ==============================================================================================

def test_quality_plan_form_required_and_optional_fields(tenant_a, quality_project_a):
    """``acceptance_criteria`` is the plan's REQUIRED column; ``title`` is required; the
    ``description`` text is optional and its absence must not error."""
    form = QualityPlanForm({}, tenant=tenant_a)
    assert not form.is_valid()
    assert form.fields["acceptance_criteria"].required
    assert form.fields["title"].required
    assert not form.fields["description"].required
    for name in ("project", "title", "acceptance_criteria"):
        assert name in form.errors, name
    assert "description" not in form.errors


def test_quality_defect_form_description_required(tenant_a, quality_project_a):
    """A defect without a description is not recordable — the column has no ``blank=True``."""
    assert QualityDefectForm(tenant=tenant_a).fields["description"].required
    form = QualityDefectForm(_quality_defect_data(quality_project_a, description=""),
                             tenant=tenant_a)
    assert not form.is_valid()
    assert "description" in form.errors
    assert "title" not in form.errors and "identified_date" not in form.errors


# ==============================================================================================
# Happy paths — each form saves a complete row, TenantUniqueMixin stamps CREATE, stamps untouched
# ==============================================================================================

def test_quality_plan_form_round_trip(tenant_a, quality_project_a, admin_user):
    form = QualityPlanForm(
        _quality_plan_data(quality_project_a, owner=admin_user.pk,
                           planned_review_date=(_quality_today() + timedelta(days=14)).isoformat()),
        tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.tenant == tenant_a          # TenantUniqueMixin stamped CREATE
    assert obj.number.startswith("QPL-")   # TenantNumbered minted it, never the POST
    assert obj.status == "draft"           # verb-driven state cannot be POSTed in
    assert obj.approved_by is None and obj.approved_at is None and obj.created_by is None
    assert obj.owner == admin_user
    assert obj.planned_review_date == _quality_today() + timedelta(days=14)


def test_quality_review_form_round_trip(tenant_a, quality_project_a, quality_plan_draft,
                                        admin_user):
    """The improvement block IS form data (planning input, not a verb stamp), and the same-project
    ``quality_plan`` link passes the model's guard on the way through."""
    form = QualityReviewForm(
        _quality_review_data(quality_project_a, quality_plan=quality_plan_draft.pk,
                             reviewer=admin_user.pk,
                             improvement_action="Automate the regression pack.",
                             improvement_owner=admin_user.pk,
                             improvement_status="planned"),
        tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.tenant == tenant_a
    assert obj.number.startswith("QRV-")
    assert obj.status == "planned"         # the report/close verbs own the lifecycle
    assert obj.closed_at is None and obj.created_by is None
    assert obj.quality_plan == quality_plan_draft
    assert obj.reviewer == admin_user
    assert obj.improvement_owner == admin_user
    assert obj.improvement_status == "planned"
    assert obj.maturity_score is None      # empty string → NULL, not 0


def test_quality_inspection_form_create_stamps_tenant_before_model_clean(
        tenant_a, quality_project_a, quality_wbs_node_a, quality_milestone_a, admin_user):
    """``TenantUniqueMixin`` is mixed in FIRST: on CREATE the instance's tenant is stamped before
    ``full_clean()`` runs, so a valid same-workspace POST is never falsely refused as cross-tenant
    and the row lands in the right workspace."""
    form = DeliverableInspectionForm(
        _quality_inspection_data(quality_project_a, wbs_node=quality_wbs_node_a.pk,
                                 milestone=quality_milestone_a.pk, inspector=admin_user.pk,
                                 result="pass"),
        tenant=tenant_a)
    assert form.is_valid(), form.errors    # no false cross-tenant refusal on CREATE
    assert form.instance.tenant_id == tenant_a.pk   # stamped BEFORE the model clean ran
    obj = form.save(commit=False)
    assert obj.tenant_id == tenant_a.pk
    obj.save()
    assert obj.number.startswith("QCI-")
    assert obj.status == "planned"             # the record/accept/reject verbs own the lifecycle
    assert obj.usage_decision == "pending"     # the decision is qci_accept's / qci_reject's
    assert obj.result == "pass"                # execution entry data IS on the form
    assert obj.wbs_node == quality_wbs_node_a
    assert obj.milestone == quality_milestone_a
    assert obj.inspector == admin_user


def test_quality_defect_form_round_trip(tenant_a, quality_project_a):
    form = QualityDefectForm(_quality_defect_data(quality_project_a), tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.tenant == tenant_a
    assert obj.number.startswith("QDF-")
    assert obj.status == "open" and obj.disposition == "open"
    assert obj.root_cause == "" and obj.resolution_note == ""
    assert obj.resolved_by is None and obj.resolved_at is None
    assert obj.project_issue is None       # the bridge is qdf_raise_issue's, never the form's


# ==============================================================================================
# Smuggled excluded fields (L20/L22) — bound and saved, the system's values must win
# ==============================================================================================

def test_quality_plan_form_smuggled_excluded_fields_change_nothing(
        tenant_a, quality_project_a, admin_user):
    data = _quality_plan_data(quality_project_a)
    data.update({
        "status": "active", "approved_by": admin_user.pk, "approved_at": "1999-01-01",
        "created_by": admin_user.pk, "number": "QPL-99999", "tenant": "x",
    })
    form = QualityPlanForm(data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.status == "draft"
    assert obj.approved_by is None and obj.approved_at is None
    assert obj.created_by is None
    assert obj.number.startswith("QPL-") and obj.number != "QPL-99999"
    assert obj.tenant_id == tenant_a.pk


def test_quality_review_form_smuggled_excluded_fields_change_nothing(
        tenant_a, quality_project_a, admin_user):
    data = _quality_review_data(quality_project_a)
    data.update({"status": "closed", "closed_at": "1999-01-01", "created_by": admin_user.pk,
                 "number": "QRV-99999", "tenant": "x"})
    form = QualityReviewForm(data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.status == "planned"
    assert obj.closed_at is None and obj.created_by is None
    assert obj.number.startswith("QRV-") and obj.number != "QRV-99999"


def test_quality_inspection_form_smuggled_excluded_fields_change_nothing(
        tenant_a, quality_project_a, admin_user):
    """The whole acceptance evidence trail — decision, acceptor, party, moment, note — is
    ``qci_accept``'s; a POST cannot forge any of it through the entry form."""
    data = _quality_inspection_data(quality_project_a)
    data.update({
        "status": "passed", "usage_decision": "accept", "accepted_by": admin_user.pk,
        "accepted_by_party": "x", "accepted_at": "1999-01-01",
        "acceptance_note": "smuggled conditions", "created_by": admin_user.pk,
        "number": "QCI-99999", "tenant": "x",
    })
    form = DeliverableInspectionForm(data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.status == "planned"
    assert obj.usage_decision == "pending"
    assert obj.accepted_by is None and obj.accepted_by_party is None and obj.accepted_at is None
    assert obj.acceptance_note == ""
    assert obj.created_by is None
    assert obj.number.startswith("QCI-") and obj.number != "QCI-99999"


def test_quality_defect_form_smuggled_excluded_fields_change_nothing(
        tenant_a, quality_project_a, admin_user):
    """The resolution evidence and the issue bridge are the verbs' — a POST cannot resolve a
    defect or bridge it to the issue register through the entry form."""
    data = _quality_defect_data(quality_project_a)
    data.update({
        "status": "resolved", "root_cause": "smuggled cause",
        "resolution_note": "smuggled note", "resolved_by": admin_user.pk,
        "resolved_at": "1999-01-01", "project_issue": "x",
        "number": "QDF-99999", "tenant": "x",
    })
    form = QualityDefectForm(data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.status == "open"
    assert obj.root_cause == "" and obj.resolution_note == ""
    assert obj.resolved_by is None and obj.resolved_at is None
    assert obj.project_issue is None
    assert obj.number.startswith("QDF-") and obj.number != "QDF-99999"


# ==============================================================================================
# _reject_foreign — the crafted-POST backstop, its own wording, on every tenant-scoped FK
# ==============================================================================================

def test_quality_plan_form_rejects_foreign_records(
        tenant_a, quality_project_a, quality_project_b, quality_wbs_node_b, admin_b):
    cases = [
        ("project", quality_project_b),
        ("wbs_node", quality_wbs_node_b),
        ("owner", admin_b),
    ]
    for name, foreign in cases:
        data = _quality_plan_data(quality_project_a)
        data[name] = foreign.pk
        form = _quality_widen(QualityPlanForm(data, tenant=tenant_a), name)
        assert not form.is_valid(), name
        assert any(_REJECT_FOREIGN_MSG in msg for msg in form.errors[name]), (name, form.errors)
        assert not QualityPlan.objects.exists(), name


def test_quality_review_form_rejects_foreign_records(
        tenant_a, quality_project_a, quality_project_b, quality_wbs_node_b, quality_plan_b,
        admin_b):
    cases = [
        ("project", quality_project_b),
        ("wbs_node", quality_wbs_node_b),
        ("quality_plan", quality_plan_b),
        ("reviewer", admin_b),
        ("improvement_owner", admin_b),
    ]
    for name, foreign in cases:
        data = _quality_review_data(quality_project_a)
        data[name] = foreign.pk
        form = _quality_widen(QualityReviewForm(data, tenant=tenant_a), name)
        assert not form.is_valid(), name
        assert any(_REJECT_FOREIGN_MSG in msg for msg in form.errors[name]), (name, form.errors)
        assert not QualityReview.objects.exists(), name


def test_quality_inspection_form_rejects_foreign_records(
        tenant_a, quality_project_a, quality_project_b, quality_wbs_node_b, quality_plan_b,
        quality_milestone_b, admin_b):
    cases = [
        ("project", quality_project_b),
        ("wbs_node", quality_wbs_node_b),
        ("quality_plan", quality_plan_b),
        ("milestone", quality_milestone_b),
        ("inspector", admin_b),
    ]
    for name, foreign in cases:
        data = _quality_inspection_data(quality_project_a)
        data[name] = foreign.pk
        form = _quality_widen(DeliverableInspectionForm(data, tenant=tenant_a), name)
        assert not form.is_valid(), name
        assert any(_REJECT_FOREIGN_MSG in msg for msg in form.errors[name]), (name, form.errors)
        assert not DeliverableInspection.objects.exists(), name


def test_quality_defect_form_rejects_foreign_records(
        tenant_a, quality_project_a, quality_project_b, quality_wbs_node_b, quality_plan_b,
        quality_inspection_b, admin_b):
    cases = [
        ("project", quality_project_b),
        ("wbs_node", quality_wbs_node_b),
        ("quality_plan", quality_plan_b),
        ("inspection", quality_inspection_b),
        ("owner", admin_b),
    ]
    for name, foreign in cases:
        data = _quality_defect_data(quality_project_a)
        data[name] = foreign.pk
        form = _quality_widen(QualityDefectForm(data, tenant=tenant_a), name)
        assert not form.is_valid(), name
        assert any(_REJECT_FOREIGN_MSG in msg for msg in form.errors[name]), (name, form.errors)
        assert not QualityDefect.objects.exists(), name


# ==============================================================================================
# Model clean() passthrough — the same-project guards are reachable from a same-tenant POST
# ==============================================================================================

def test_quality_inspection_form_cross_project_wbs_node_refused_by_model_clean(
        tenant_a, quality_project_a):
    """A node from ANOTHER tenant-A project passes the narrowed dropdown and ``_reject_foreign``
    (same workspace) — the model's own same-project guard must answer, as a ``wbs_node`` field
    error."""
    other_node = _quality_wbs_node(tenant_a, _quality_project(tenant_a))
    form = DeliverableInspectionForm(
        _quality_inspection_data(quality_project_a, wbs_node=other_node.pk), tenant=tenant_a)
    assert not form.is_valid()
    assert "wbs_node" in form.errors
    assert any("same project" in msg for msg in form.errors["wbs_node"])
    assert not DeliverableInspection.objects.exists()


def test_quality_review_form_cross_project_wbs_node_refused_by_model_clean(
        tenant_a, quality_project_a):
    other_node = _quality_wbs_node(tenant_a, _quality_project(tenant_a))
    form = QualityReviewForm(
        _quality_review_data(quality_project_a, wbs_node=other_node.pk), tenant=tenant_a)
    assert not form.is_valid()
    assert "wbs_node" in form.errors
    assert any("same project" in msg for msg in form.errors["wbs_node"])
    assert not QualityReview.objects.exists()


def test_quality_defect_form_cross_project_wbs_node_refused_by_model_clean(
        tenant_a, quality_project_a):
    other_node = _quality_wbs_node(tenant_a, _quality_project(tenant_a))
    form = QualityDefectForm(
        _quality_defect_data(quality_project_a, wbs_node=other_node.pk), tenant=tenant_a)
    assert not form.is_valid()
    assert "wbs_node" in form.errors
    assert any("same project" in msg for msg in form.errors["wbs_node"])
    assert not QualityDefect.objects.exists()


def test_quality_plan_form_cross_project_wbs_node_refused_by_model_clean(
        tenant_a, quality_project_a):
    other_node = _quality_wbs_node(tenant_a, _quality_project(tenant_a))
    form = QualityPlanForm(
        _quality_plan_data(quality_project_a, wbs_node=other_node.pk), tenant=tenant_a)
    assert not form.is_valid()
    assert "wbs_node" in form.errors
    assert any("same project" in msg for msg in form.errors["wbs_node"])
    assert not QualityPlan.objects.exists()


# ==============================================================================================
# InspectionAcceptanceForm — qci_accept's plain body: the two decisions, the scoped Party
# ==============================================================================================

def test_quality_acceptance_form_usage_decision_choices_exact(tenant_a):
    """The decision vocabulary is EXACTLY accept / accept_with_deviation — a rejection is
    ``qci_reject``'s, so it cannot be forged from the accept endpoint."""
    field = InspectionAcceptanceForm(tenant=tenant_a).fields["usage_decision"]
    assert field.required
    assert list(field.choices) == [("accept", "Accept"),
                                   ("accept_with_deviation", "Accept with Deviation")]

    empty = InspectionAcceptanceForm({}, tenant=tenant_a)
    assert not empty.is_valid()
    assert "usage_decision" in empty.errors

    reject = InspectionAcceptanceForm({"usage_decision": "reject"}, tenant=tenant_a)
    assert not reject.is_valid()
    assert "usage_decision" in reject.errors


def test_quality_acceptance_form_party_queryset_scoped_by_tenant(
        tenant_a, quality_client_party_a, quality_client_party_b):
    """The Party IS the tenant boundary here: a tenant-less form offers NO parties at all, a
    tenant form offers only its own workspace's — the foreign pk is never even a choice."""
    unscoped = InspectionAcceptanceForm(tenant=None)
    assert not unscoped.fields["accepted_by_party"].queryset.exists()

    scoped = InspectionAcceptanceForm(tenant=tenant_a).fields["accepted_by_party"].queryset
    pks = set(scoped.values_list("pk", flat=True))
    assert quality_client_party_a.pk in pks
    assert quality_client_party_b.pk not in pks
    assert set(scoped.values_list("tenant_id", flat=True)) == {tenant_a.pk}


def test_quality_acceptance_form_happy_path_and_refuses_foreign_party(
        tenant_a, quality_client_party_a, quality_client_party_b):
    """Both decisions validate with the party and note; a foreign party pk dies as an invalid
    choice — never as ``_reject_foreign``'s wording (a Party has no tenant on the mixin's terms,
    so the queryset IS the boundary and the verb re-checks it behind the form)."""
    minimal = InspectionAcceptanceForm({"usage_decision": "accept"}, tenant=tenant_a)
    assert minimal.is_valid(), minimal.errors
    assert minimal.cleaned_data["accepted_by_party"] is None
    assert minimal.cleaned_data["acceptance_note"] == ""

    form = InspectionAcceptanceForm(
        {"usage_decision": "accept_with_deviation",
         "accepted_by_party": quality_client_party_a.pk,
         "acceptance_note": "Accepted with the punch list attached."},
        tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["usage_decision"] == "accept_with_deviation"
    assert form.cleaned_data["accepted_by_party"] == quality_client_party_a
    assert form.cleaned_data["acceptance_note"] == "Accepted with the punch list attached."

    foreign = InspectionAcceptanceForm(
        {"usage_decision": "accept", "accepted_by_party": quality_client_party_b.pk},
        tenant=tenant_a)
    assert not foreign.is_valid()
    assert "accepted_by_party" in foreign.errors
    assert not any(_REJECT_FOREIGN_MSG in msg for msg in foreign.errors["accepted_by_party"])


def test_quality_acceptance_form_is_not_a_model_form():
    """The accept verb writes ``cleaned_data`` into the row itself (stamping accepted_by/at and
    status ``passed``) — the body must not be a ModelForm that could save over the row."""
    assert not hasattr(InspectionAcceptanceForm(), "save")


# ==============================================================================================
# DefectResolutionForm — qdf_resolve's plain body: the note is required, the cause is optional
# ==============================================================================================

def test_quality_resolution_form_note_required_root_cause_optional():
    """A resolution without a recorded action is not a resolution: ``resolution_note`` is
    REQUIRED, ``root_cause`` may stay blank."""
    empty = DefectResolutionForm({})
    assert not empty.is_valid()
    assert "resolution_note" in empty.errors
    assert "root_cause" not in empty.errors

    form = DefectResolutionForm({"resolution_note": "Housing replaced and re-measured."})
    assert form.is_valid(), form.errors
    assert form.cleaned_data["resolution_note"] == "Housing replaced and re-measured."
    assert form.cleaned_data["root_cause"] == ""


def test_quality_resolution_form_is_not_a_model_form():
    """The resolve verb writes ``cleaned_data`` into the row itself (stamping resolved_by/at and
    status ``resolved``) — the body must not be a ModelForm that could save over the row."""
    assert not hasattr(DefectResolutionForm(), "save")


# ==============================================================================================
# Widget classes — the theme styling reaches the plain bodies and the ModelForms alike
# ==============================================================================================

def test_quality_forms_carry_theme_widget_classes(tenant_a):
    """The plain verb bodies carry their classes by hand (no ``TenantModelForm`` behind them);
    the ModelForms get the same theme classes from ``TenantModelForm``'s pass."""
    accept = InspectionAcceptanceForm(tenant=tenant_a)
    assert accept.fields["usage_decision"].widget.attrs.get("class") == "form-select"
    assert accept.fields["accepted_by_party"].widget.attrs.get("class") == "form-select"
    assert accept.fields["acceptance_note"].widget.attrs.get("class") == "form-textarea"

    resolve = DefectResolutionForm()
    assert resolve.fields["root_cause"].widget.attrs.get("class") == "form-textarea"
    assert resolve.fields["resolution_note"].widget.attrs.get("class") == "form-textarea"

    plan = QualityPlanForm(tenant=tenant_a)
    assert plan.fields["project"].widget.attrs.get("class") == "form-select"
    assert plan.fields["title"].widget.attrs.get("class") == "form-input"
    assert plan.fields["acceptance_criteria"].widget.attrs.get("class") == "form-textarea"
