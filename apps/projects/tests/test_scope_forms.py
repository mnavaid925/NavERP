"""Projects 7.7 Scope & Requirements Management — FORM tests (phase 6, step 3 of 6).

The nine forms in ``apps/projects/forms/ScopeRequirements/`` are 7.7's entire write boundary:
four ``TenantUniqueMixin`` + ``TenantModelForm`` register forms, plus the five plain
``forms.Form`` companions the verb-driven gates bind (a rejection needs a written reason, a
verification/outcome/CCB-decision/acceptance note is captured by the audited verb that also
stamps the evidence columns).

This lane owns the claims no other lane can see:

**1. What is NOT a field.** Each ``Meta.fields`` whitelist is a security control. ``status``
and ``acceptance_status`` are verb-driven (submit/approve/reject/implement/verify; accept/
reject/waive), the ``*_by``/``*_at`` stamps and ``rejection_reason``/``decision_note``/
``verification_note``/``outcome``/``closed_at`` are evidence a GATED verb writes, ``number``
and ``tenant`` are the system's. A field a gated verb writes must not also be POST-settable
through the ungated edit form. Absence is asserted twice over (L20/L22): the name is missing
from ``form.fields``, AND a payload carrying every excluded name binds and proves the row
keeps the system's values, not the smuggled ones. Exposing ``status`` would let a member mint
their own approval evidence — that is the highest-value assertion in this module.

**2. The MRO of the four ModelForms.** Every one carries ``TenantUniqueMixin`` FIRST, then
``TenantModelForm``: the mixin stamps ``instance.tenant`` before ``full_clean()`` so a model
``clean()`` comparing a chosen FK's project does not false-positive as cross-tenant on create.

**3. Tenant scoping.** ``TenantModelForm`` narrows every ``ModelChoiceField`` whose target
carries a ``tenant`` column, so a crafted cross-tenant POST errors on that FIELD (per the
review's lane-5 finding the narrowed queryset refuses first; the test asserts "this field has
an error", never Django's or ``_reject_foreign``'s wording). For each tenant-scoped FK the
same-field tenant-A pk is asserted ACCEPTED, so the proof is about the tenant, not the field.

**4. The same-project ``clean()`` guards** reach the form: a cross-project (same tenant!)
``wbs_node``/``parent``/``requirement``/``risk`` is refused with the error keyed to that field.

Plus required-vs-optional fields (every optional FK is ``null=True, blank=True``), the five
plain forms' required/optional contract, choice-field allow-lists (L11), the ``cost_impact`` /
``schedule_impact_days`` hardening, and the create-time defaults the contract pins.

Determinism (L16): every date basis is ``_scope_today()`` — never ``datetime.date.today()``.

Naming (mandatory): every test is ``test_scope_*``, every module-level helper ``_scope_*`` /
``_SCOPE_*``. Scope: forms only. Models, views and permissions belong to the other three lanes.

Step 3 of 6 for sub-module 7.7 (models → **forms** → views → security → …).
"""
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.projects.forms import (
    ChangeRejectionForm,
    RequirementForm,
    RequirementRejectionForm,
    RequirementVerificationForm,
    ScopeChangeForm,
    ScopeItemForm,
    ScopeItemOutcomeForm,
    ScopeVerificationForm,
    VerificationDecisionForm,
)
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin
from apps.projects.models import (
    ProjectRisk,
    Requirement,
    ScopeChangeRequest,
    ScopeItem,
    ScopeVerification,
)
from apps.projects.tests.conftest import (
    _risk,
    _scope_change,
    _scope_item,
    _scope_requirement,
    _scope_today,
    _scope_verification,
)

D = Decimal

# -- the pinned field sets (contract §3) -----------------------------------------------------------

_SCOPE_REQUIREMENT_FIELDS = [
    "project", "parent", "wbs_node", "title", "description", "requirement_type",
    "elicitation_method", "elicitation_note", "source_party", "priority", "acceptance_criteria",
    "version", "verification_method", "owner", "requested_by",
]
_SCOPE_REQUIREMENT_FORBIDDEN = [
    "tenant", "number", "status", "rejection_reason", "approved_by", "approved_at",
    "verified_by", "verified_at", "verification_note", "created_by",
]

_SCOPE_ITEM_FIELDS = [
    "project", "requirement", "item_type", "statement", "description", "impact_area", "owner",
    "identified_date", "review_date",
]
_SCOPE_ITEM_FORBIDDEN = ["tenant", "number", "status", "outcome", "closed_at", "created_by"]

_SCOPE_CHANGE_FIELDS = [
    "project", "requirement", "risk", "title", "description", "justification", "source",
    "priority", "schedule_impact_days", "cost_impact", "quality_impact", "quality_note",
    "requested_by",
]
_SCOPE_CHANGE_FORBIDDEN = [
    "tenant", "number", "status", "decision_note", "decided_by", "decided_at", "implemented_at",
    "created_by",
]

_SCOPE_VERIFICATION_FIELDS = [
    "project", "wbs_node", "requirement", "deliverable", "method", "result", "inspected_by",
    "inspection_date", "findings",
]
_SCOPE_VERIFICATION_FORBIDDEN = [
    "tenant", "number", "acceptance_status", "decision_note", "accepted_by", "accepted_at",
    "created_by",
]

#: Every FK the four forms expose that is re-checked against the workspace (contract §3).
_SCOPE_TENANT_SCOPED_FKS = [
    "project", "parent", "wbs_node", "source_party", "owner", "requested_by", "requirement",
    "risk", "inspected_by",
]


# ==================================================================================================
# Payload builders — one valid POST body per ModelForm, kept readable by the tests below
# ==================================================================================================

def _scope_requirement_payload(project, **over):
    data = {
        "project": project.pk if project is not None else "",
        "parent": "",
        "wbs_node": "",
        "title": "Form-built requirement",
        "description": "The capability the solution must provide.",
        "requirement_type": "functional",
        "elicitation_method": "interview",
        "elicitation_note": "",
        "source_party": "",
        "priority": "must",
        "acceptance_criteria": "",
        "version": "1.0",
        "verification_method": "test",
        "owner": "",
        "requested_by": "",
    }
    data.update(over)
    return data


def _scope_item_payload(project, **over):
    data = {
        "project": project.pk if project is not None else "",
        "requirement": "",
        "item_type": "assumption",
        "statement": "Form-built scope item",
        "description": "",
        "impact_area": "scope",
        "owner": "",
        "identified_date": _scope_today().isoformat(),
        "review_date": "",
    }
    data.update(over)
    return data


def _scope_change_payload(project, **over):
    data = {
        "project": project.pk if project is not None else "",
        "requirement": "",
        "risk": "",
        "title": "Form-built change",
        "description": "The scope change the board is asked to weigh.",
        "justification": "",
        "source": "internal",
        "priority": "medium",
        "schedule_impact_days": "",
        "cost_impact": "0.00",
        "quality_impact": "none",
        "quality_note": "",
        "requested_by": "",
    }
    data.update(over)
    return data


def _scope_verification_payload(project, **over):
    data = {
        "project": project.pk if project is not None else "",
        "wbs_node": "",
        "requirement": "",
        "deliverable": "Form-built deliverable",
        "method": "inspection",
        "result": "pass",
        "inspected_by": "",
        "inspection_date": _scope_today().isoformat(),
        "findings": "",
    }
    data.update(over)
    return data


def _scope_smuggle(data, names, values):
    """Overlay every forbidden field name with a plausible attacker value on a valid payload.

    ``values`` is the name -> value map drawn (per form) from the contract's crafted set:
    ``status="verified"``, ``approved_by=<pk>``, ``acceptance_status="accepted"``,
    ``decision_note="x"``, ``number="REQ-99999"``, ``tenant=<other pk>``, ``created_by=<pk>``.
    """
    for name in names:
        data[name] = values[name]
    return data


# ==================================================================================================
# The MRO — TenantUniqueMixin FIRST on every ModelForm whose model clean() reads a chosen FK
# ==================================================================================================

@pytest.mark.parametrize("form_class", [
    RequirementForm, ScopeItemForm, ScopeChangeForm, ScopeVerificationForm,
])
def test_scope_model_forms_mix_tenant_unique_first(form_class):
    mro = form_class.__mro__
    assert TenantUniqueMixin in mro
    assert TenantModelForm in mro
    # The mixin must come BEFORE the model form so its __init__/validate_unique wrap ours.
    assert mro.index(TenantUniqueMixin) < mro.index(TenantModelForm)


# ==================================================================================================
# 1. Field inventories — the whitelists are the write boundary
# ==================================================================================================

def test_scope_requirement_form_fields_exact(tenant_a):
    form = RequirementForm(tenant=tenant_a)
    assert set(form.fields) == set(_SCOPE_REQUIREMENT_FIELDS)


def test_scope_requirement_form_forbidden_names_absent(tenant_a):
    form = RequirementForm(tenant=tenant_a)
    for name in _SCOPE_REQUIREMENT_FORBIDDEN:
        assert name not in form.fields, name


def test_scope_item_form_fields_exact(tenant_a):
    form = ScopeItemForm(tenant=tenant_a)
    assert set(form.fields) == set(_SCOPE_ITEM_FIELDS)


def test_scope_item_form_forbidden_names_absent(tenant_a):
    form = ScopeItemForm(tenant=tenant_a)
    for name in _SCOPE_ITEM_FORBIDDEN:
        assert name not in form.fields, name


def test_scope_change_form_fields_exact(tenant_a):
    form = ScopeChangeForm(tenant=tenant_a)
    assert set(form.fields) == set(_SCOPE_CHANGE_FIELDS)


def test_scope_change_form_forbidden_names_absent(tenant_a):
    form = ScopeChangeForm(tenant=tenant_a)
    for name in _SCOPE_CHANGE_FORBIDDEN:
        assert name not in form.fields, name


def test_scope_verification_form_fields_exact(tenant_a):
    form = ScopeVerificationForm(tenant=tenant_a)
    assert set(form.fields) == set(_SCOPE_VERIFICATION_FIELDS)


def test_scope_verification_form_forbidden_names_absent(tenant_a):
    form = ScopeVerificationForm(tenant=tenant_a)
    for name in _SCOPE_VERIFICATION_FORBIDDEN:
        assert name not in form.fields, name


# ==================================================================================================
# 2. Mass-assignment lockdown — every excluded name smuggled on top of a VALID payload is ignored
# ==================================================================================================

def test_scope_requirement_form_smuggled_excluded_fields_change_nothing(
        tenant_a, scope_project_a, admin_user):
    data = _scope_smuggle(
        _scope_requirement_payload(scope_project_a), _SCOPE_REQUIREMENT_FORBIDDEN,
        {
            "tenant": tenant_a.pk, "number": "REQ-99999", "status": "verified",
            "rejection_reason": "smuggled", "approved_by": admin_user.pk,
            "approved_at": "1999-01-01T00:00", "verified_by": admin_user.pk,
            "verified_at": "1999-01-01T00:00", "verification_note": "smuggled",
            "created_by": admin_user.pk,
        })
    form = RequirementForm(data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    for name in _SCOPE_REQUIREMENT_FORBIDDEN:
        assert name not in form.cleaned_data, name
    obj = form.save()
    assert obj.status == "draft"                  # a plain edit cannot self-approve
    assert obj.approved_by is None and obj.approved_at is None
    assert obj.verified_by is None and obj.verified_at is None
    assert obj.rejection_reason == "" and obj.verification_note == ""
    assert obj.created_by is None
    assert obj.number != "REQ-99999"              # the system mints REQ-####
    assert obj.tenant == tenant_a                 # TenantUniqueMixin stamped the real tenant


def test_scope_item_form_smuggled_excluded_fields_change_nothing(tenant_a, scope_project_a):
    data = _scope_smuggle(
        _scope_item_payload(scope_project_a), _SCOPE_ITEM_FORBIDDEN,
        {
            "tenant": tenant_a.pk, "number": "SCI-99999", "status": "realized",
            "outcome": "smuggled outcome", "closed_at": "1999-01-01T00:00", "created_by": "x",
        })
    form = ScopeItemForm(data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    for name in _SCOPE_ITEM_FORBIDDEN:
        assert name not in form.cleaned_data, name
    obj = form.save()
    assert obj.status == "open"                   # realize/retire are the verbs' business
    assert obj.outcome == "" and obj.closed_at is None
    assert obj.created_by is None
    assert obj.number != "SCI-99999"
    assert obj.tenant == tenant_a


def test_scope_change_form_smuggled_excluded_fields_change_nothing(
        tenant_a, scope_project_a, admin_user):
    data = _scope_smuggle(
        _scope_change_payload(scope_project_a), _SCOPE_CHANGE_FORBIDDEN,
        {
            "tenant": tenant_a.pk, "number": "SCR-99999", "status": "approved",
            "decision_note": "smuggled decision", "decided_by": admin_user.pk,
            "decided_at": "1999-01-01T00:00", "implemented_at": "1999-01-01T00:00",
            "created_by": admin_user.pk,
        })
    form = ScopeChangeForm(data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    for name in _SCOPE_CHANGE_FORBIDDEN:
        assert name not in form.cleaned_data, name
    obj = form.save()
    assert obj.status == "draft"                  # the CCB decision is admin-verb-only
    assert obj.decision_note == "" and obj.decided_by is None and obj.decided_at is None
    assert obj.implemented_at is None
    assert obj.created_by is None
    assert obj.number != "SCR-99999"
    assert obj.tenant == tenant_a


def test_scope_verification_form_smuggled_excluded_fields_change_nothing(
        tenant_a, scope_project_a, admin_user):
    data = _scope_smuggle(
        _scope_verification_payload(scope_project_a), _SCOPE_VERIFICATION_FORBIDDEN,
        {
            "tenant": tenant_a.pk, "number": "SVR-99999", "acceptance_status": "accepted",
            "decision_note": "smuggled decision", "accepted_by": admin_user.pk,
            "accepted_at": "1999-01-01T00:00", "created_by": admin_user.pk,
        })
    form = ScopeVerificationForm(data, tenant=tenant_a)
    assert form.is_valid(), form.errors
    for name in _SCOPE_VERIFICATION_FORBIDDEN:
        assert name not in form.cleaned_data, name
    obj = form.save()
    assert obj.acceptance_status == "pending"     # only the acceptance verbs may decide
    assert obj.decision_note == "" and obj.accepted_by is None and obj.accepted_at is None
    assert obj.created_by is None
    assert obj.number != "SVR-99999"
    assert obj.tenant == tenant_a


# ==================================================================================================
# 3. Cross-tenant FK injection — the foreign pk errors on its FIELD, the home pk is ACCEPTED
# ==================================================================================================

def test_scope_requirement_form_refuses_foreign_project(tenant_a, tenant_b, scope_project_b):
    form = RequirementForm(_scope_requirement_payload(scope_project_b), tenant=tenant_a)
    assert not form.is_valid()
    assert "project" in form.errors


def test_scope_requirement_form_accepts_home_project(tenant_a, scope_project_a):
    form = RequirementForm(_scope_requirement_payload(scope_project_a), tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_scope_requirement_form_refuses_foreign_parent(tenant_a, scope_project_a,
                                                       scope_requirement_b):
    form = RequirementForm(
        _scope_requirement_payload(scope_project_a, parent=scope_requirement_b.pk),
        tenant=tenant_a)
    assert not form.is_valid()
    assert "parent" in form.errors


def test_scope_requirement_form_accepts_home_parent(tenant_a, scope_project_a,
                                                    scope_requirement_draft):
    form = RequirementForm(
        _scope_requirement_payload(scope_project_a, parent=scope_requirement_draft.pk),
        tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_scope_requirement_form_refuses_foreign_wbs_node(tenant_a, scope_project_a, scope_wbs_b):
    form = RequirementForm(
        _scope_requirement_payload(scope_project_a, wbs_node=scope_wbs_b.pk), tenant=tenant_a)
    assert not form.is_valid()
    assert "wbs_node" in form.errors


def test_scope_requirement_form_accepts_home_wbs_node(tenant_a, scope_project_a, scope_wbs_a):
    form = RequirementForm(
        _scope_requirement_payload(scope_project_a, wbs_node=scope_wbs_a.pk), tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_scope_requirement_form_refuses_foreign_source_party(tenant_a, scope_project_a,
                                                             scope_party_b):
    form = RequirementForm(
        _scope_requirement_payload(scope_project_a, source_party=scope_party_b.pk),
        tenant=tenant_a)
    assert not form.is_valid()
    assert "source_party" in form.errors


def test_scope_requirement_form_accepts_home_source_party(tenant_a, scope_project_a,
                                                          scope_party_a):
    form = RequirementForm(
        _scope_requirement_payload(scope_project_a, source_party=scope_party_a.pk),
        tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_scope_requirement_form_refuses_foreign_owner(tenant_a, scope_project_a, admin_b):
    form = RequirementForm(
        _scope_requirement_payload(scope_project_a, owner=admin_b.pk), tenant=tenant_a)
    assert not form.is_valid()
    assert "owner" in form.errors


def test_scope_requirement_form_accepts_home_owner(tenant_a, scope_project_a, admin_user):
    form = RequirementForm(
        _scope_requirement_payload(scope_project_a, owner=admin_user.pk), tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_scope_requirement_form_refuses_foreign_requested_by(tenant_a, scope_project_a, admin_b):
    form = RequirementForm(
        _scope_requirement_payload(scope_project_a, requested_by=admin_b.pk), tenant=tenant_a)
    assert not form.is_valid()
    assert "requested_by" in form.errors


def test_scope_requirement_form_accepts_home_requested_by(tenant_a, scope_project_a, admin_user):
    form = RequirementForm(
        _scope_requirement_payload(scope_project_a, requested_by=admin_user.pk), tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_scope_item_form_refuses_foreign_project(tenant_a, scope_project_b):
    form = ScopeItemForm(_scope_item_payload(scope_project_b), tenant=tenant_a)
    assert not form.is_valid()
    assert "project" in form.errors


def test_scope_item_form_accepts_home_project(tenant_a, scope_project_a):
    form = ScopeItemForm(_scope_item_payload(scope_project_a), tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_scope_item_form_refuses_foreign_requirement(tenant_a, scope_project_a,
                                                     scope_requirement_b):
    form = ScopeItemForm(
        _scope_item_payload(scope_project_a, requirement=scope_requirement_b.pk), tenant=tenant_a)
    assert not form.is_valid()
    assert "requirement" in form.errors


def test_scope_item_form_accepts_home_requirement(tenant_a, scope_project_a,
                                                  scope_requirement_draft):
    form = ScopeItemForm(
        _scope_item_payload(scope_project_a, requirement=scope_requirement_draft.pk),
        tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_scope_item_form_refuses_foreign_owner(tenant_a, scope_project_a, admin_b):
    form = ScopeItemForm(
        _scope_item_payload(scope_project_a, owner=admin_b.pk), tenant=tenant_a)
    assert not form.is_valid()
    assert "owner" in form.errors


def test_scope_item_form_accepts_home_owner(tenant_a, scope_project_a, admin_user):
    form = ScopeItemForm(
        _scope_item_payload(scope_project_a, owner=admin_user.pk), tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_scope_change_form_refuses_foreign_project(tenant_a, scope_project_b):
    form = ScopeChangeForm(_scope_change_payload(scope_project_b), tenant=tenant_a)
    assert not form.is_valid()
    assert "project" in form.errors


def test_scope_change_form_accepts_home_project(tenant_a, scope_project_a):
    form = ScopeChangeForm(_scope_change_payload(scope_project_a), tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_scope_change_form_refuses_foreign_requirement(tenant_a, scope_project_a,
                                                       scope_requirement_b):
    form = ScopeChangeForm(
        _scope_change_payload(scope_project_a, requirement=scope_requirement_b.pk),
        tenant=tenant_a)
    assert not form.is_valid()
    assert "requirement" in form.errors


def test_scope_change_form_accepts_home_requirement(tenant_a, scope_project_a,
                                                    scope_requirement_draft):
    form = ScopeChangeForm(
        _scope_change_payload(scope_project_a, requirement=scope_requirement_draft.pk),
        tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_scope_change_form_refuses_foreign_risk(tenant_a, scope_project_a, risk_b):
    """``risk`` is 7.5's ``ProjectRisk`` — a tenant-B pk is refused on the field."""
    form = ScopeChangeForm(
        _scope_change_payload(scope_project_a, risk=risk_b.pk), tenant=tenant_a)
    assert not form.is_valid()
    assert "risk" in form.errors


def test_scope_change_form_accepts_home_risk(tenant_a, scope_project_a):
    """A risk on the SAME project as the change request is the valid pairing."""
    home = _risk(tenant_a, scope_project_a, title="Home scope risk")
    form = ScopeChangeForm(
        _scope_change_payload(scope_project_a, risk=home.pk), tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_scope_change_form_refuses_foreign_requested_by(tenant_a, scope_project_a, admin_b):
    form = ScopeChangeForm(
        _scope_change_payload(scope_project_a, requested_by=admin_b.pk), tenant=tenant_a)
    assert not form.is_valid()
    assert "requested_by" in form.errors


def test_scope_change_form_accepts_home_requested_by(tenant_a, scope_project_a, admin_user):
    form = ScopeChangeForm(
        _scope_change_payload(scope_project_a, requested_by=admin_user.pk), tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_scope_verification_form_refuses_foreign_project(tenant_a, scope_project_b):
    form = ScopeVerificationForm(_scope_verification_payload(scope_project_b), tenant=tenant_a)
    assert not form.is_valid()
    assert "project" in form.errors


def test_scope_verification_form_accepts_home_project(tenant_a, scope_project_a):
    form = ScopeVerificationForm(_scope_verification_payload(scope_project_a), tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_scope_verification_form_refuses_foreign_wbs_node(tenant_a, scope_project_a, scope_wbs_b):
    form = ScopeVerificationForm(
        _scope_verification_payload(scope_project_a, wbs_node=scope_wbs_b.pk), tenant=tenant_a)
    assert not form.is_valid()
    assert "wbs_node" in form.errors


def test_scope_verification_form_accepts_home_wbs_node(tenant_a, scope_project_a, scope_wbs_a):
    form = ScopeVerificationForm(
        _scope_verification_payload(scope_project_a, wbs_node=scope_wbs_a.pk), tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_scope_verification_form_refuses_foreign_requirement(tenant_a, scope_project_a,
                                                             scope_requirement_b):
    form = ScopeVerificationForm(
        _scope_verification_payload(scope_project_a, requirement=scope_requirement_b.pk),
        tenant=tenant_a)
    assert not form.is_valid()
    assert "requirement" in form.errors


def test_scope_verification_form_accepts_home_requirement(tenant_a, scope_project_a,
                                                          scope_requirement_draft):
    form = ScopeVerificationForm(
        _scope_verification_payload(scope_project_a, requirement=scope_requirement_draft.pk),
        tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_scope_verification_form_refuses_foreign_inspected_by(tenant_a, scope_project_a, admin_b):
    form = ScopeVerificationForm(
        _scope_verification_payload(scope_project_a, inspected_by=admin_b.pk), tenant=tenant_a)
    assert not form.is_valid()
    assert "inspected_by" in form.errors


def test_scope_verification_form_accepts_home_inspected_by(tenant_a, scope_project_a,
                                                           admin_user):
    form = ScopeVerificationForm(
        _scope_verification_payload(scope_project_a, inspected_by=admin_user.pk),
        tenant=tenant_a)
    assert form.is_valid(), form.errors


# ==================================================================================================
# 4. Same-project clean() guards — a cross-PROJECT (same tenant) FK errors on that field
# ==================================================================================================

def test_scope_requirement_form_cross_project_wbs_node_refused(tenant_a, scope_wbs_b,
                                                               scope_matrix_project_a):
    """``scope_wbs_b`` is tenant B's. Widen the queryset so the model clean() branch — not the
    dropdown — is what refuses: same-field error, no row."""
    form = RequirementForm(
        _scope_requirement_payload(scope_matrix_project_a, wbs_node=scope_wbs_b.pk),
        tenant=tenant_a)
    form.fields["wbs_node"].queryset = form.fields["wbs_node"].queryset.model.objects.all()
    assert not form.is_valid()
    assert "wbs_node" in form.errors
    assert not Requirement.objects.exists()


def test_scope_requirement_form_cross_project_parent_refused(tenant_a, scope_project_a,
                                                             scope_requirement_b):
    form = RequirementForm(
        _scope_requirement_payload(scope_project_a, parent=scope_requirement_b.pk),
        tenant=tenant_a)
    form.fields["parent"].queryset = Requirement.objects.all()
    assert not form.is_valid()
    assert "parent" in form.errors


def test_scope_item_form_cross_project_requirement_refused(tenant_a, scope_project_a,
                                                           scope_requirement_b):
    form = ScopeItemForm(
        _scope_item_payload(scope_project_a, requirement=scope_requirement_b.pk), tenant=tenant_a)
    form.fields["requirement"].queryset = Requirement.objects.all()
    assert not form.is_valid()
    assert "requirement" in form.errors
    assert not ScopeItem.objects.exists()


def test_scope_change_form_cross_project_requirement_refused(tenant_a, scope_project_a,
                                                             scope_requirement_b):
    form = ScopeChangeForm(
        _scope_change_payload(scope_project_a, requirement=scope_requirement_b.pk),
        tenant=tenant_a)
    form.fields["requirement"].queryset = Requirement.objects.all()
    assert not form.is_valid()
    assert "requirement" in form.errors
    assert not ScopeChangeRequest.objects.exists()


def test_scope_change_form_cross_project_risk_refused(tenant_a, scope_project_a, risk_b):
    """``risk_b`` is a tenant-B risk; widened, the model clean() same-project branch refuses it."""
    form = ScopeChangeForm(
        _scope_change_payload(scope_project_a, risk=risk_b.pk), tenant=tenant_a)
    form.fields["risk"].queryset = ProjectRisk.objects.all()
    assert not form.is_valid()
    assert "risk" in form.errors


def test_scope_change_form_cross_project_risk_same_tenant_refused(
        tenant_a, scope_project_a, scope_project_b):
    """A risk on ANOTHER tenant-A project must be refused by the model clean() guard too."""
    other = _risk(tenant_a, scope_project_b, title="Cross-project risk")
    form = ScopeChangeForm(
        _scope_change_payload(scope_project_a, risk=other.pk), tenant=tenant_a)
    form.fields["risk"].queryset = ProjectRisk.objects.filter(tenant=tenant_a)
    assert not form.is_valid()
    assert "risk" in form.errors


def test_scope_verification_form_cross_project_wbs_node_refused(
        tenant_a, scope_project_a, scope_wbs_b):
    form = ScopeVerificationForm(
        _scope_verification_payload(scope_project_a, wbs_node=scope_wbs_b.pk), tenant=tenant_a)
    form.fields["wbs_node"].queryset = form.fields["wbs_node"].queryset.model.objects.all()
    assert not form.is_valid()
    assert "wbs_node" in form.errors
    assert not ScopeVerification.objects.exists()


def test_scope_verification_form_cross_project_requirement_refused(
        tenant_a, scope_project_a, scope_requirement_b):
    form = ScopeVerificationForm(
        _scope_verification_payload(scope_project_a, requirement=scope_requirement_b.pk),
        tenant=tenant_a)
    form.fields["requirement"].queryset = Requirement.objects.all()
    assert not form.is_valid()
    assert "requirement" in form.errors


# ==================================================================================================
# 5. Required vs optional — every optional FK is (null=True, blank=True); a minimal form validates
# ==================================================================================================

def test_scope_requirement_form_minimal_validates(tenant_a, scope_project_a):
    """Only the three genuinely required fields carry values; every optional FK is blank."""
    form = RequirementForm(
        {"project": scope_project_a.pk, "title": "Minimal", "description": "Just enough.",
         "requirement_type": "functional", "elicitation_method": "interview", "priority": "must",
         "version": "1.0", "verification_method": "test"},
        tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_scope_requirement_form_optional_fks_accept_blank(tenant_a, scope_project_a):
    form = RequirementForm(
        _scope_requirement_payload(scope_project_a, parent="", wbs_node="", source_party="",
                                   owner="", requested_by=""),
        tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_scope_requirement_form_required_fields_error_when_blank(tenant_a):
    form = RequirementForm(
        _scope_requirement_payload(None, title="", description=""), tenant=tenant_a)
    assert not form.is_valid()
    for name in ("project", "title", "description"):
        assert name in form.errors, name


def test_scope_item_form_minimal_validates(tenant_a, scope_project_a):
    form = ScopeItemForm(
        {"project": scope_project_a.pk, "statement": "Minimal boundary", "item_type": "assumption",
         "impact_area": "scope", "identified_date": _scope_today().isoformat()},
        tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_scope_item_form_optional_fks_accept_blank(tenant_a, scope_project_a):
    form = ScopeItemForm(
        _scope_item_payload(scope_project_a, requirement="", owner=""), tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_scope_item_form_required_fields_error_when_blank(tenant_a):
    form = ScopeItemForm(
        _scope_item_payload(None, statement="", item_type="", impact_area=""), tenant=tenant_a)
    assert not form.is_valid()
    for name in ("project", "statement", "item_type", "impact_area"):
        assert name in form.errors, name


def test_scope_change_form_minimal_validates(tenant_a, scope_project_a):
    form = ScopeChangeForm(
        {"project": scope_project_a.pk, "title": "Minimal", "description": "Just enough.",
         "source": "internal", "priority": "medium", "cost_impact": "0.00",
         "quality_impact": "none"},
        tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_scope_change_form_optional_fks_accept_blank(tenant_a, scope_project_a):
    form = ScopeChangeForm(
        _scope_change_payload(scope_project_a, requirement="", risk="", requested_by=""),
        tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_scope_change_form_required_fields_error_when_blank(tenant_a):
    form = ScopeChangeForm(
        _scope_change_payload(None, title="", description=""), tenant=tenant_a)
    assert not form.is_valid()
    for name in ("project", "title", "description"):
        assert name in form.errors, name


def test_scope_verification_form_minimal_validates(tenant_a, scope_project_a):
    form = ScopeVerificationForm(
        {"project": scope_project_a.pk, "deliverable": "Minimal deliverable",
         "method": "inspection", "result": "pass",
         "inspection_date": _scope_today().isoformat()},
        tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_scope_verification_form_optional_fks_accept_blank(tenant_a, scope_project_a):
    form = ScopeVerificationForm(
        _scope_verification_payload(scope_project_a, wbs_node="", requirement="",
                                    inspected_by=""),
        tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_scope_verification_form_required_fields_error_when_blank(tenant_a):
    form = ScopeVerificationForm(
        _scope_verification_payload(None, deliverable="", method="", result=""),
        tenant=tenant_a)
    assert not form.is_valid()
    for name in ("project", "deliverable", "method", "result"):
        assert name in form.errors, name


# ==================================================================================================
# 6. The five plain forms — required vs optional text
# ==================================================================================================

def test_scope_requirement_rejection_form_requires_reason():
    form = RequirementRejectionForm({})
    assert not form.is_valid()
    assert "reason" in form.errors


def test_scope_requirement_rejection_form_accepts_reason():
    form = RequirementRejectionForm({"reason": "Not funded this quarter."})
    assert form.is_valid()
    assert form.cleaned_data["reason"] == "Not funded this quarter."


def test_scope_requirement_verification_form_note_is_optional():
    form = RequirementVerificationForm({})
    assert form.is_valid(), form.errors


def test_scope_item_outcome_form_requires_outcome():
    form = ScopeItemOutcomeForm({})
    assert not form.is_valid()
    assert "outcome" in form.errors


def test_scope_item_outcome_form_accepts_outcome():
    form = ScopeItemOutcomeForm({"outcome": "The assumption held."})
    assert form.is_valid()
    assert form.cleaned_data["outcome"] == "The assumption held."


def test_scope_change_rejection_form_requires_decision_note():
    form = ChangeRejectionForm({})
    assert not form.is_valid()
    assert "decision_note" in form.errors


def test_scope_change_rejection_form_accepts_decision_note():
    form = ChangeRejectionForm({"decision_note": "Out of the agreed scope."})
    assert form.is_valid()
    assert form.cleaned_data["decision_note"] == "Out of the agreed scope."


def test_scope_verification_decision_form_note_is_optional():
    form = VerificationDecisionForm({})
    assert form.is_valid(), form.errors


@pytest.mark.parametrize("form_class", [
    RequirementRejectionForm, RequirementVerificationForm, ScopeItemOutcomeForm,
    ChangeRejectionForm, VerificationDecisionForm,
])
def test_scope_plain_forms_are_not_model_forms(form_class):
    """Each companion writes form.cleaned_data itself — it must not be a ModelForm with save()."""
    assert not hasattr(form_class(), "save")


# ==================================================================================================
# 7. Choice-field validation — an out-of-vocabulary value is refused (L11 allow-list)
# ==================================================================================================

@pytest.mark.parametrize("field,bad", [
    ("requirement_type", "not_a_type"),
    ("priority", "someday"),
    ("elicitation_method", "telepathy"),
    ("verification_method", "vibes"),
])
def test_scope_requirement_form_rejects_out_of_vocabulary_choice(
        tenant_a, scope_project_a, field, bad):
    form = RequirementForm(
        _scope_requirement_payload(scope_project_a, **{field: bad}), tenant=tenant_a)
    assert not form.is_valid()
    assert field in form.errors


@pytest.mark.parametrize("field,bad", [
    ("item_type", "maybe_scope"),
    ("impact_area", "vibes"),
])
def test_scope_item_form_rejects_out_of_vocabulary_choice(tenant_a, scope_project_a, field, bad):
    form = ScopeItemForm(
        _scope_item_payload(scope_project_a, **{field: bad}), tenant=tenant_a)
    assert not form.is_valid()
    assert field in form.errors


@pytest.mark.parametrize("field,bad", [
    ("source", "astrology"),
    ("priority", "whenever"),
    ("quality_impact", "catastrophic"),
])
def test_scope_change_form_rejects_out_of_vocabulary_choice(tenant_a, scope_project_a, field, bad):
    form = ScopeChangeForm(
        _scope_change_payload(scope_project_a, **{field: bad}), tenant=tenant_a)
    assert not form.is_valid()
    assert field in form.errors


@pytest.mark.parametrize("field,bad", [
    ("method", "guesswork"),
    ("result", "maybe"),
])
def test_scope_verification_form_rejects_out_of_vocabulary_choice(
        tenant_a, scope_project_a, field, bad):
    form = ScopeVerificationForm(
        _scope_verification_payload(scope_project_a, **{field: bad}), tenant=tenant_a)
    assert not form.is_valid()
    assert field in form.errors


# ==================================================================================================
# 8. cost_impact / schedule_impact_days hardening — never a 500, a 2-dp Decimal when valid
# ==================================================================================================

def test_scope_change_form_refuses_negative_cost_impact(tenant_a, scope_project_a):
    form = ScopeChangeForm(
        _scope_change_payload(scope_project_a, cost_impact="-1.00"), tenant=tenant_a)
    assert not form.is_valid()
    assert "cost_impact" in form.errors


def test_scope_change_form_refuses_negative_schedule_impact_days(tenant_a, scope_project_a):
    form = ScopeChangeForm(
        _scope_change_payload(scope_project_a, schedule_impact_days="-3"), tenant=tenant_a)
    assert not form.is_valid()
    assert "schedule_impact_days" in form.errors


def test_scope_change_form_accepts_two_dp_cost_impact_as_decimal(tenant_a, scope_project_a):
    form = ScopeChangeForm(
        _scope_change_payload(scope_project_a, cost_impact="49999.99"), tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["cost_impact"] == D("49999.99")
    assert isinstance(form.cleaned_data["cost_impact"], Decimal)


def test_scope_change_form_accepts_positive_schedule_impact_days(tenant_a, scope_project_a):
    form = ScopeChangeForm(
        _scope_change_payload(scope_project_a, schedule_impact_days="12"), tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["schedule_impact_days"] == 12


# ==================================================================================================
# 9. Create-time defaults — version, identified_date and inspection_date on an unbound form
# ==================================================================================================

def test_scope_requirement_form_version_defaults_to_one_point_zero(tenant_a):
    form = RequirementForm(tenant=tenant_a)
    assert form["version"].value() == "1.0"


def test_scope_item_form_identified_date_defaults_to_today(tenant_a):
    form = ScopeItemForm(tenant=tenant_a)
    assert str(form["identified_date"].value()) == _scope_today().isoformat()


def test_scope_verification_form_inspection_date_defaults_to_today(tenant_a):
    form = ScopeVerificationForm(tenant=tenant_a)
    assert str(form["inspection_date"].value()) == _scope_today().isoformat()


# ==================================================================================================
# Model clean() happy path — the same-project pairing the forms build by default validates
# ==================================================================================================

def test_scope_item_form_bounds_to_an_existing_instance(tenant_a, scope_project_a):
    """An edit round-trip over a factory row must validate and keep the system's status."""
    item = _scope_item(tenant_a, scope_project_a, statement="Boundary to edit")
    form = ScopeItemForm(
        _scope_item_payload(scope_project_a, statement="Boundary edited"), instance=item,
        tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.statement == "Boundary edited"
    assert obj.status == "open"                   # still verb-driven, never form-driven
    assert obj.tenant == tenant_a


def test_scope_verification_form_bounds_to_an_existing_instance(tenant_a, scope_project_a):
    ver = _scope_verification(tenant_a, scope_project_a, deliverable="Boundary inspection")
    form = ScopeVerificationForm(
        _scope_verification_payload(scope_project_a, deliverable="Boundary re-inspected"),
        instance=ver, tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.deliverable == "Boundary re-inspected"
    assert obj.acceptance_status == "pending"     # an edit cannot self-accept
