"""Projects 7.1 Project Initiation & Charter - FORM tests.

The five forms are 7.1's entire write boundary: every byte that reaches a ``ProjectRequest``,
``Project``, ``ProjectStakeholder`` or ``ProjectKickoff`` through the UI passes through one of
them. This lane owns the three claims no other lane can see.

**1. What is NOT a field.** Each ``Meta.exclude`` list is a security control, not a tidiness
preference. ``status`` / ``decision`` / ``charter_status`` are verb-driven, the ``*_by`` / ``*_at``
stamps are evidence of who decided what and when, ``number`` and ``tenant`` are the system's, and
- added by fix **I3** during the review pass - ``rejection_reason``, ``information_requested`` and
``decision_notes`` are written ONLY by the ``@tenant_admin_required`` verbs. A field a gated verb
writes must not also be POST-settable through the ungated edit form, or any member can rewrite or
blank the admin's stated rationale while leaving the "Rejected" badge intact. Absence is asserted
twice over (L20/L22): the name is missing from ``form.fields``, **and** a payload carrying every
excluded name is bound and the saved row proved to hold the system's values, not the smuggled ones.

**2. Tenant scoping of every FK dropdown, on both layers.** ``TenantModelForm`` narrows a
``ModelChoiceField`` whose target model carries a ``tenant`` column, which is why a crafted
cross-tenant POST answers with Django's ``"Select a valid choice."`` and NOT with
``_reject_foreign``'s ``"That record belongs to another workspace."`` (contract 2.6). Both layers
are exercised: the narrowing on its own, and then - with the queryset deliberately widened, the
shape a POST that never went near the widget actually takes - the ``clean()`` backstop behind it.
Never the wording, always "this field has an error".

The one FK that must stay UNSCOPED is ``currency``: ``accounting.Currency`` is a GLOBAL table with
no ``tenant`` column (**L29**), so narrowing it would empty the dropdown and handing it to
``_reject_foreign`` would raise ``AttributeError`` on ``currency.tenant_id``.

**3. The ``tenant=None`` form.** ``TenantModelForm`` scopes only ``if tenant is not None``, so a
form built without one offers every workspace's users, parties, org units and documents.
``ProjectStakeholderForm`` and ``ProjectKickoffForm`` alone fail closed, explicitly ``.none()``-ing
their ``project`` field. That asymmetry is the form half of security fix **I1**; the view half
hoisted a ``request.tenant is None`` guard to the first line of all four create views. This lane
pins the current behaviour of every field so a regression on either half is visible here.

Plus the numeric hardening the ``0002`` migration added (a negative ``estimated_cost`` is a field
error, and so are ``NaN`` / ``Infinity`` / garbage / 15 digits / three decimal places - never a
500), the party-or-user rule surfacing as a non-field error, ``ProjectKickoffForm``'s
one-kickoff-per-project dropdown that still round-trips on edit, and a clean round-trip proving a
re-submitted unchanged form changes nothing.

Determinism (L16): ``USE_TZ`` is True and ``TIME_ZONE`` is UTC; every date basis is
``timezone.localdate()`` through ``_projectinitiation_today()``, never ``datetime.date.today()``.
No network, no filesystem.

Naming (mandatory): every test is ``test_projectinitiation_*`` and every module-level helper
``_projectinitiation_*`` / ``_PROJECTINITIATION_*``, so 7.2 appending into this package cannot
shadow either.

Scope: forms only. Views, urls, permissions and templates belong to the other two lanes.
"""
import datetime
from decimal import Decimal

import pytest
from django import forms as django_forms
from django.core.exceptions import NON_FIELD_ERRORS
from django.utils import timezone

from apps.core.forms import TenantModelForm
from apps.projects.forms import (
    ProjectForm,
    ProjectKickoffForm,
    ProjectRequestDecisionForm,
    ProjectRequestForm,
    ProjectStakeholderForm,
    TenantUniqueMixin,
)
from apps.projects.forms._common import _reject_foreign
from apps.projects.models import Project, ProjectKickoff, ProjectRequest, ProjectStakeholder
from apps.projects.tests.conftest import (
    _projectinitiation_kickoff,
    _projectinitiation_project,
    _projectinitiation_stakeholder,
    _projectinitiation_today,
)

pytestmark = pytest.mark.django_db


# ==================================================================================================
# Module-level helpers - all _projectinitiation_* / _PROJECTINITIATION_* for the same reason the
# tests are: Python binds the LAST module-level definition, so an unprefixed helper here would
# silently rebind a sibling lane's (L47). Record factories come from conftest, which OWNS them.
# ==================================================================================================

#: The four ModelForms with the model each one writes. ``ProjectRequestDecisionForm`` is a plain
#: ``forms.Form`` with no model and is asserted on its own, at the bottom.
_PROJECTINITIATION_MODEL_FORMS = (
    (ProjectRequestForm, ProjectRequest),
    (ProjectForm, Project),
    (ProjectStakeholderForm, ProjectStakeholder),
    (ProjectKickoffForm, ProjectKickoff),
)

#: ``ProjectRequestForm.Meta.exclude``, verbatim and in order. The last three were added by fix
#: **I3**; a regression that drops them re-opens the mass-assignment hole the review pass closed.
_PROJECTINITIATION_REQUEST_EXCLUDE = [
    "tenant", "number",
    "status", "decision",
    "decided_by", "decided_at", "submitted_at",
    "converted_project",
    "created_by",
    "rejection_reason", "information_requested", "decision_notes",
]

_PROJECTINITIATION_PROJECT_EXCLUDE = [
    "tenant", "number", "request", "charter_status",
    "charter_approved_by", "charter_approved_at", "status", "created_by",
]

_PROJECTINITIATION_STAKEHOLDER_EXCLUDE = ["tenant", "number", "created_by"]

_PROJECTINITIATION_KICKOFF_EXCLUDE = [
    "tenant", "number", "status",
    "baseline_acknowledged_at", "baseline_acknowledged_by", "completed_at", "created_by",
]

#: The 22 fields ``ProjectRequestForm`` offers, in declaration order.
_PROJECTINITIATION_REQUEST_FIELDS = [
    "title", "description", "request_type", "requested_by", "requester_party", "org_unit",
    "source", "source_opportunity", "assigned_reviewer", "assigned_approver", "priority",
    "strategic_alignment", "estimated_cost", "estimated_benefit", "currency", "risk_rating",
    "feasibility", "feasibility_notes", "alternatives_considered", "required_resources",
    "target_start_date", "target_end_date",
]

#: The 18 fields ``ProjectForm`` offers.
_PROJECTINITIATION_PROJECT_FIELDS = [
    "name", "code", "description", "methodology", "in_scope", "out_of_scope", "objectives",
    "success_criteria", "assumptions", "constraints", "risk_summary", "executive_sponsor",
    "project_manager", "org_unit", "client", "start_date", "end_date", "charter_document",
]

#: The 12 fields ``ProjectStakeholderForm`` offers (``project`` is declared on the form itself).
_PROJECTINITIATION_STAKEHOLDER_FIELDS = [
    "project", "party", "user", "stakeholder_type", "raci_role", "raci_scope", "influence",
    "interest", "comms_preference", "comms_frequency", "attending_kickoff", "notes",
]

#: The 8 fields ``ProjectKickoffForm`` offers.
_PROJECTINITIATION_KICKOFF_FIELDS = [
    "project", "meeting_date", "location_or_link", "agenda_template", "agenda",
    "attendee_summary", "onboarding_notes", "notes",
]

#: Every column the four models keep for themselves, pooled. Not one of these may appear on ANY of
#: the four forms: a workflow state, an evidence stamp or an auto-number a POST can set is a
#: control the form quietly removed. ``project`` is deliberately absent - it is the user's own
#: choice on two of the models, and a legitimate field there.
_PROJECTINITIATION_SYSTEM_COLUMNS = {
    "tenant", "number", "created_at", "updated_at", "created_by",
    # ProjectRequest
    "status", "decision", "decided_by", "decided_at", "decision_notes", "rejection_reason",
    "information_requested", "submitted_at", "converted_project",
    # Project
    "request", "charter_status", "charter_approved_by", "charter_approved_at",
    # ProjectKickoff
    "baseline_acknowledged_at", "baseline_acknowledged_by", "completed_at",
}

#: The 10 fields ``ProjectRequestForm`` requires. The last five are required not because anyone
#: marked them so but because they carry a MODEL DEFAULT without ``blank=True`` - which is the trap
#: in every hand-written create POST, and the reason this set is pinned rather than eyeballed.
_PROJECTINITIATION_REQUEST_REQUIRED = {
    "title", "description", "request_type", "source", "priority", "strategic_alignment",
    "estimated_cost", "estimated_benefit", "risk_rating", "feasibility",
}

_PROJECTINITIATION_PROJECT_REQUIRED = {"name", "methodology"}

_PROJECTINITIATION_STAKEHOLDER_REQUIRED = {
    "project", "stakeholder_type", "raci_role", "influence", "interest", "comms_preference",
    "comms_frequency",
}

_PROJECTINITIATION_KICKOFF_REQUIRED = {"project", "agenda_template"}


def _projectinitiation_request_payload(**overrides):
    """The MINIMUM valid ``ProjectRequestForm`` POST - exactly the 10 required fields.

    Everything else on the form is optional, so a negative test can add one bad value to this and
    know the only reason the form failed is the value it changed.
    """
    payload = {
        "title": "Replace the depot scheduling spreadsheet",
        "description": "The depot still schedules 40 vans from one shared workbook.",
        "request_type": "new_project",
        "source": "internal",
        "priority": "medium",
        "strategic_alignment": "4",
        "estimated_cost": "120000.00",
        "estimated_benefit": "300000.00",
        "risk_rating": "medium",
        "feasibility": "feasible",
    }
    payload.update(overrides)
    return payload


def _projectinitiation_project_payload(**overrides):
    """The MINIMUM valid ``ProjectForm`` POST - name and methodology, nothing else."""
    payload = {"name": "Depot scheduling replacement", "methodology": "hybrid"}
    payload.update(overrides)
    return payload


def _projectinitiation_stakeholder_payload(project, **overrides):
    """The minimum valid ``ProjectStakeholderForm`` POST for ``project``.

    ``party`` is NOT included: the party-or-user rule is one of the things under test, so the
    caller adds whichever identity the case needs.
    """
    payload = {
        "project": str(project.pk),
        "stakeholder_type": "sponsor",
        "raci_role": "a",
        "raci_scope": "charter approval",
        "influence": "high",
        "interest": "high",
        "comms_preference": "email",
        "comms_frequency": "weekly",
    }
    payload.update(overrides)
    return payload


def _projectinitiation_kickoff_payload(project, **overrides):
    """The minimum valid ``ProjectKickoffForm`` POST for ``project``."""
    payload = {"project": str(project.pk), "agenda_template": "standard"}
    payload.update(overrides)
    return payload


def _projectinitiation_widen(form, *names):
    """Drop the tenant narrowing off named ``ModelChoiceField``s, in place.

    A narrowed ``<select>`` refuses a foreign pk as "Select a valid choice", which is a real
    control - but it proves the WIDGET was scoped, not that the boundary holds. Widening first is
    how a crafted POST that never went near the widget is simulated, so what answers is the second
    layer: ``_reject_foreign`` in each form's ``clean()``.
    """
    for name in names:
        field = form.fields[name]
        field.queryset = field.queryset.model._default_manager.all()
    return form


def _projectinitiation_pks(form, name):
    """The pks a ``ModelChoiceField`` dropdown currently offers."""
    return set(form.fields[name].queryset.values_list("pk", flat=True))


def _projectinitiation_choice_fields(form):
    """Every ``ModelChoiceField`` on ``form``, by name."""
    return {name: field for name, field in form.fields.items()
            if isinstance(field, django_forms.ModelChoiceField)}


def _projectinitiation_roundtrip_payload(form):
    """The POST a browser would send back for an UNCHANGED bound form.

    Each value goes out through the same widget that rendered it - ``BoundField.value()`` applies
    ``prepare_value`` (pk for an FK, current-timezone for a datetime) and the widget's ``format``
    is the one ``TenantModelForm`` installed, so the string that comes back out is one the field's
    ``input_formats`` accepts. That is what makes ``changed_data == []`` a real claim rather than
    an artefact of hand-typing the values.
    """
    data = {}
    for name, field in form.fields.items():
        value = form[name].value()
        if value is None or value == "":
            data[name] = ""
        elif isinstance(value, bool):
            data[name] = "on" if value else ""
        elif isinstance(value, (datetime.datetime, datetime.date)):
            data[name] = field.widget.format_value(value)
        else:
            data[name] = str(value)
    return data


def _projectinitiation_minute(days=7):
    """An aware datetime with zero seconds - the precision a ``datetime-local`` input carries.

    Derived from ``timezone.now()`` (L16). Truncating here rather than asserting around it keeps
    the kickoff round-trip an assertion about the FORM instead of about widget precision.
    """
    return (timezone.now() + datetime.timedelta(days=days)).replace(second=0, microsecond=0)


# ==================================================================================================
# 1. The import surface and the class shape
# ==================================================================================================

def test_projectinitiation_forms_package_reexports_all_five_forms():
    """Views, the CRUD helpers and these tests all import through the package root; a form added
    without its re-export line is an ImportError at runtime, never at edit time."""
    for form_class in (ProjectRequestForm, ProjectForm, ProjectStakeholderForm,
                       ProjectKickoffForm, ProjectRequestDecisionForm):
        assert isinstance(form_class, type)


def test_projectinitiation_forms_package_reexports_the_shared_toolkit():
    """``TenantModelForm`` / ``TenantUniqueMixin`` come out of the package root too - the peer
    apps' suites depend on exactly this line."""
    assert issubclass(TenantModelForm, django_forms.ModelForm)
    assert isinstance(TenantUniqueMixin, type)
    assert callable(_reject_foreign)


def test_projectinitiation_every_model_form_writes_the_model_it_claims():
    for form_class, model in _PROJECTINITIATION_MODEL_FORMS:
        assert form_class.Meta.model is model, form_class.__name__


def test_projectinitiation_every_model_form_mixes_the_tenant_unique_mixin_in_first():
    """Mixin BEFORE ``TenantModelForm``: ``TenantUniqueMixin.__init__`` stamps
    ``instance.tenant`` so a model ``clean()`` comparing a chosen FK's tenant reads a real value.
    Reversed, every create would validate against ``tenant_id = None``."""
    for form_class, _model in _PROJECTINITIATION_MODEL_FORMS:
        mro = form_class.__mro__
        assert mro.index(TenantUniqueMixin) < mro.index(TenantModelForm), form_class.__name__


def test_projectinitiation_decision_form_is_a_plain_form_not_a_model_form():
    """It writes nothing by itself - the verb does. A ModelForm here would hand ``prq_reject`` a
    ``save()`` it must never call."""
    assert issubclass(ProjectRequestDecisionForm, django_forms.Form)
    assert not issubclass(ProjectRequestDecisionForm, django_forms.ModelForm)


def test_projectinitiation_the_constructor_takes_tenant_as_a_keyword(tenant_a):
    """``Form(data=None, *, tenant=...)`` - every view builds them this way."""
    for form_class, _model in _PROJECTINITIATION_MODEL_FORMS:
        form = form_class(tenant=tenant_a)
        assert form.tenant is tenant_a, form_class.__name__


# ==================================================================================================
# 2. Meta.exclude IS the security boundary - the lists, the absences, and the smuggled POST
# ==================================================================================================

def test_projectinitiation_request_form_exclude_list_is_the_pinned_twelve():
    """Verbatim, including the three fix-I3 names. Anything dropped from this list becomes
    POST-settable through the ungated edit form."""
    assert ProjectRequestForm.Meta.exclude == _PROJECTINITIATION_REQUEST_EXCLUDE


def test_projectinitiation_request_form_excludes_the_three_decision_evidence_fields():
    """The I3 regression guard, stated on its own so a failure names the actual hole: these three
    are written ONLY by ``prq_reject`` / ``prq_return_for_information``, both
    ``@tenant_admin_required``."""
    for name in ("rejection_reason", "information_requested", "decision_notes"):
        assert name in ProjectRequestForm.Meta.exclude, name


def test_projectinitiation_project_form_exclude_list_is_the_pinned_eight():
    assert ProjectForm.Meta.exclude == _PROJECTINITIATION_PROJECT_EXCLUDE


def test_projectinitiation_stakeholder_form_exclude_list_is_the_pinned_three():
    assert ProjectStakeholderForm.Meta.exclude == _PROJECTINITIATION_STAKEHOLDER_EXCLUDE


def test_projectinitiation_kickoff_form_exclude_list_is_the_pinned_seven():
    assert ProjectKickoffForm.Meta.exclude == _PROJECTINITIATION_KICKOFF_EXCLUDE


def test_projectinitiation_every_excluded_name_is_a_real_model_field():
    """A typo in ``exclude`` is a SILENT no-op - Django neither raises nor warns, and the field it
    was meant to remove ships in the form. This is the only thing that catches it.

    Concrete + m2m only, never ``get_fields()``: a reverse accessor is not something ``exclude``
    can remove, so matching one would let a typo pass.
    """
    for form_class, model in _PROJECTINITIATION_MODEL_FORMS:
        real = {f.name for f in model._meta.fields} | {f.name for f in model._meta.many_to_many}
        for name in form_class.Meta.exclude:
            assert name in real, f"{form_class.__name__}.Meta.exclude has no field {name!r}"


def test_projectinitiation_request_form_offers_exactly_the_twenty_two_fields(tenant_a):
    form = ProjectRequestForm(tenant=tenant_a)
    assert list(form.fields) == _PROJECTINITIATION_REQUEST_FIELDS
    assert len(form.fields) == 22


def test_projectinitiation_project_form_offers_exactly_the_eighteen_fields(tenant_a):
    form = ProjectForm(tenant=tenant_a)
    assert list(form.fields) == _PROJECTINITIATION_PROJECT_FIELDS
    assert len(form.fields) == 18


def test_projectinitiation_stakeholder_form_offers_exactly_the_twelve_fields(tenant_a):
    form = ProjectStakeholderForm(tenant=tenant_a)
    assert list(form.fields) == _PROJECTINITIATION_STAKEHOLDER_FIELDS
    assert len(form.fields) == 12


def test_projectinitiation_kickoff_form_offers_exactly_the_eight_fields(tenant_a):
    form = ProjectKickoffForm(tenant=tenant_a)
    assert list(form.fields) == _PROJECTINITIATION_KICKOFF_FIELDS
    assert len(form.fields) == 8


def test_projectinitiation_no_form_offers_any_pooled_system_column(tenant_a):
    """The single sweep: not one workflow state, evidence stamp, auto-number or tenant key is a
    field on any of the four."""
    for form_class, _model in _PROJECTINITIATION_MODEL_FORMS:
        leaked = _PROJECTINITIATION_SYSTEM_COLUMNS & set(form_class(tenant=tenant_a).fields)
        assert leaked == set(), f"{form_class.__name__} exposes {sorted(leaked)}"


def test_projectinitiation_no_form_offers_a_non_editable_column(tenant_a):
    """``editable=False`` on the model is the second half of the same control: ``number``,
    ``decided_by``/``decided_at``, ``submitted_at``, ``charter_approved_by``/``_at``,
    ``baseline_acknowledged_*``, ``completed_at`` and ``created_by`` cannot reach a ModelForm at
    all - so this holds even if a name were dropped from an ``exclude`` list."""
    for form_class, model in _PROJECTINITIATION_MODEL_FORMS:
        frozen = {f.name for f in model._meta.fields if not f.editable}
        assert frozen & set(form_class(tenant=tenant_a).fields) == set(), form_class.__name__


def test_projectinitiation_field_sets_are_exactly_editable_minus_exclude(tenant_a):
    """The arithmetic behind every list above, so a NEW model field is caught: a column added
    without a decision about it lands on the form by default.

    ``formfield() is not None`` is Django's own rule in ``fields_for_model`` - it is what drops
    the ``AutoField`` primary key, which is ``editable`` but has no form representation.
    """
    for form_class, model in _PROJECTINITIATION_MODEL_FORMS:
        offerable = {f.name for f in model._meta.fields
                     if f.editable and f.formfield() is not None}
        expected = offerable - set(form_class.Meta.exclude)
        assert set(form_class(tenant=tenant_a).fields) == expected, form_class.__name__


def test_projectinitiation_edit_mode_offers_the_same_fields_as_create(
        tenant_a, projectinitiation_request_draft, projectinitiation_project_draft,
        projectinitiation_stakeholder_a, projectinitiation_kickoff_planned):
    """An edit form that grew a field is the same hole as a create form that did."""
    pairs = (
        (ProjectRequestForm, projectinitiation_request_draft),
        (ProjectForm, projectinitiation_project_draft),
        (ProjectStakeholderForm, projectinitiation_stakeholder_a),
        (ProjectKickoffForm, projectinitiation_kickoff_planned),
    )
    for form_class, instance in pairs:
        create = set(form_class(tenant=tenant_a).fields)
        edit = set(form_class(instance=instance, tenant=tenant_a).fields)
        assert create == edit, form_class.__name__


def test_projectinitiation_request_form_ignores_every_smuggled_excluded_value(
        tenant_a, tenant_b, admin_b, projectinitiation_project_b):
    """L20/L22, the whole list at once: a POST naming all twelve excluded fields still saves a
    ``draft`` in tenant A with a freshly minted number and no decision evidence."""
    smuggled = _projectinitiation_request_payload(
        tenant=str(tenant_b.pk),
        number="PRQ-99999",
        status="approved",
        decision="go",
        decided_by=str(admin_b.pk),
        decided_at="2020-01-01T00:00",
        submitted_at="2020-01-01T00:00",
        converted_project=str(projectinitiation_project_b.pk),
        created_by=str(admin_b.pk),
        rejection_reason="smuggled rejection",
        information_requested="smuggled question",
        decision_notes="smuggled notes",
    )
    form = ProjectRequestForm(smuggled, tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    obj.refresh_from_db()

    assert obj.tenant_id == tenant_a.pk
    assert obj.number == "PRQ-00001"
    assert obj.status == "draft"
    assert obj.decision == ""
    assert obj.decided_by_id is None and obj.decided_at is None
    assert obj.submitted_at is None
    assert obj.converted_project_id is None
    assert obj.created_by_id is None
    assert obj.rejection_reason == ""
    assert obj.information_requested == ""
    assert obj.decision_notes == ""


def test_projectinitiation_edit_cannot_blank_a_stated_rejection_reason(
        tenant_a, projectinitiation_request_rejected):
    """The sharpest form of I3: the admin's stated rationale survives an edit POST that tries to
    erase it, and the badge and the reason stay consistent."""
    original = projectinitiation_request_rejected.rejection_reason
    assert original

    form = ProjectRequestForm(
        _projectinitiation_request_payload(rejection_reason="", decision_notes="",
                                           status="draft", decision=""),
        instance=projectinitiation_request_rejected, tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    obj.refresh_from_db()

    assert obj.rejection_reason == original
    assert obj.status == "rejected"
    assert obj.decision == "no_go"
    assert obj.decided_at is not None


def test_projectinitiation_edit_cannot_rewrite_the_information_requested(
        tenant_a, projectinitiation_request_needs_information):
    original = projectinitiation_request_needs_information.information_requested
    form = ProjectRequestForm(
        _projectinitiation_request_payload(information_requested="Nothing, actually"),
        instance=projectinitiation_request_needs_information, tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    obj.refresh_from_db()
    assert obj.information_requested == original
    assert obj.status == "needs_information"


def test_projectinitiation_project_form_ignores_every_smuggled_excluded_value(
        tenant_a, tenant_b, admin_b, projectinitiation_request_draft):
    """``charter_status`` is the one that matters most: a POST that could set it walks straight
    past ``prj_approve_charter``'s ``@tenant_admin_required``."""
    smuggled = _projectinitiation_project_payload(
        tenant=str(tenant_b.pk),
        number="PRJ-99999",
        request=str(projectinitiation_request_draft.pk),
        charter_status="approved",
        charter_approved_by=str(admin_b.pk),
        charter_approved_at="2020-01-01T00:00",
        status="active",
        created_by=str(admin_b.pk),
    )
    form = ProjectForm(smuggled, tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    obj.refresh_from_db()

    assert obj.tenant_id == tenant_a.pk
    assert obj.number == "PRJ-00001"
    assert obj.request_id is None
    assert obj.charter_status == "draft"
    assert obj.charter_approved_by_id is None and obj.charter_approved_at is None
    assert obj.status == "draft"
    assert obj.created_by_id is None


def test_projectinitiation_edit_cannot_walk_a_charter_to_approved(
        tenant_a, projectinitiation_project_draft):
    form = ProjectForm(_projectinitiation_project_payload(charter_status="approved",
                                                          status="completed"),
                       instance=projectinitiation_project_draft, tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    obj.refresh_from_db()
    assert obj.charter_status == "draft"
    assert obj.status == "draft"


def test_projectinitiation_stakeholder_form_ignores_every_smuggled_excluded_value(
        tenant_a, tenant_b, admin_b, projectinitiation_project_draft,
        projectinitiation_party_a):
    smuggled = _projectinitiation_stakeholder_payload(
        projectinitiation_project_draft,
        party=str(projectinitiation_party_a.pk),
        tenant=str(tenant_b.pk),
        number="PST-99999",
        created_by=str(admin_b.pk),
    )
    form = ProjectStakeholderForm(smuggled, tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    obj.refresh_from_db()
    assert obj.tenant_id == tenant_a.pk
    assert obj.number == "PST-00001"
    assert obj.created_by_id is None


def test_projectinitiation_kickoff_form_ignores_every_smuggled_excluded_value(
        tenant_a, tenant_b, admin_b, projectinitiation_project_draft):
    """``status`` and the two acknowledgement stamps are the ceremony's evidence: a POST that
    could set them fakes a kickoff that never happened."""
    smuggled = _projectinitiation_kickoff_payload(
        projectinitiation_project_draft,
        tenant=str(tenant_b.pk),
        number="PKO-99999",
        status="completed",
        baseline_acknowledged_at="2020-01-01T00:00",
        baseline_acknowledged_by=str(admin_b.pk),
        completed_at="2020-01-01T00:00",
        created_by=str(admin_b.pk),
    )
    form = ProjectKickoffForm(smuggled, tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    obj.refresh_from_db()
    assert obj.tenant_id == tenant_a.pk
    assert obj.number == "PKO-00001"
    assert obj.status == "planned"
    assert obj.baseline_acknowledged_at is None and obj.baseline_acknowledged_by_id is None
    assert obj.completed_at is None
    assert obj.created_by_id is None


def test_projectinitiation_kickoff_edit_cannot_stamp_the_baseline(
        tenant_a, admin_user, projectinitiation_kickoff_planned):
    form = ProjectKickoffForm(
        _projectinitiation_kickoff_payload(
            projectinitiation_kickoff_planned.project,
            status="held", baseline_acknowledged_by=str(admin_user.pk),
            baseline_acknowledged_at="2020-01-01T00:00"),
        instance=projectinitiation_kickoff_planned, tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    obj.refresh_from_db()
    assert obj.status == "planned"
    assert obj.baseline_acknowledged_at is None


# ==================================================================================================
# 3. Required vs optional
# ==================================================================================================

def test_projectinitiation_request_form_requires_the_pinned_ten(tenant_a):
    form = ProjectRequestForm(tenant=tenant_a)
    required = {name for name, field in form.fields.items() if field.required}
    assert required == _PROJECTINITIATION_REQUEST_REQUIRED


def test_projectinitiation_request_form_reports_all_ten_missing_at_once(tenant_a):
    """One round trip tells the user everything that is wrong, rather than ten."""
    form = ProjectRequestForm({}, tenant=tenant_a)
    assert not form.is_valid()
    assert set(form.errors) == _PROJECTINITIATION_REQUEST_REQUIRED


def test_projectinitiation_the_five_defaulted_fields_are_still_required(tenant_a):
    """``priority`` / ``strategic_alignment`` / ``estimated_cost`` / ``estimated_benefit`` /
    ``risk_rating`` / ``feasibility`` all carry a model default, and a default is NOT
    ``blank=True`` - omitting them from a POST is an error, not a fallback to the default."""
    for name in ("priority", "strategic_alignment", "estimated_cost", "estimated_benefit",
                 "risk_rating", "feasibility"):
        payload = _projectinitiation_request_payload()
        payload.pop(name)
        form = ProjectRequestForm(payload, tenant=tenant_a)
        assert not form.is_valid(), name
        assert name in form.errors, name


def test_projectinitiation_request_form_optional_fields_accept_nothing(tenant_a):
    """The other 12 are genuinely optional - a minimum POST saves."""
    form = ProjectRequestForm(_projectinitiation_request_payload(), tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.requested_by_id is None
    assert obj.requester_party_id is None
    assert obj.org_unit_id is None
    assert obj.source_opportunity_id is None
    assert obj.currency_id is None
    assert obj.target_start_date is None and obj.target_end_date is None
    assert obj.feasibility_notes == ""


def test_projectinitiation_project_form_requires_only_name_and_methodology(tenant_a):
    form = ProjectForm(tenant=tenant_a)
    required = {name for name, field in form.fields.items() if field.required}
    assert required == _PROJECTINITIATION_PROJECT_REQUIRED


def test_projectinitiation_project_form_reports_both_missing_required_fields(tenant_a):
    form = ProjectForm({}, tenant=tenant_a)
    assert not form.is_valid()
    assert set(form.errors) == _PROJECTINITIATION_PROJECT_REQUIRED


def test_projectinitiation_project_form_saves_on_the_minimum(tenant_a):
    form = ProjectForm(_projectinitiation_project_payload(), tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.code == "" and obj.client_id is None and obj.start_date is None


def test_projectinitiation_stakeholder_form_requires_the_pinned_seven(tenant_a):
    form = ProjectStakeholderForm(tenant=tenant_a)
    required = {name for name, field in form.fields.items() if field.required}
    assert required == _PROJECTINITIATION_STAKEHOLDER_REQUIRED


def test_projectinitiation_stakeholder_form_reports_its_missing_required_fields(tenant_a):
    form = ProjectStakeholderForm({}, tenant=tenant_a)
    assert not form.is_valid()
    assert _PROJECTINITIATION_STAKEHOLDER_REQUIRED <= set(form.errors)


def test_projectinitiation_stakeholder_raci_scope_and_notes_are_optional(
        tenant_a, projectinitiation_project_draft, projectinitiation_party_a):
    form = ProjectStakeholderForm(
        _projectinitiation_stakeholder_payload(
            projectinitiation_project_draft, party=str(projectinitiation_party_a.pk),
            raci_scope="", notes=""),
        tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.raci_scope == "" and obj.notes == ""


def test_projectinitiation_kickoff_form_requires_only_project_and_agenda_template(tenant_a):
    form = ProjectKickoffForm(tenant=tenant_a)
    required = {name for name, field in form.fields.items() if field.required}
    assert required == _PROJECTINITIATION_KICKOFF_REQUIRED


def test_projectinitiation_kickoff_form_reports_both_missing_required_fields(tenant_a):
    form = ProjectKickoffForm({}, tenant=tenant_a)
    assert not form.is_valid()
    assert set(form.errors) == _PROJECTINITIATION_KICKOFF_REQUIRED


def test_projectinitiation_kickoff_meeting_date_is_optional(
        tenant_a, projectinitiation_project_draft):
    """A kickoff can be planned before a date exists - ``pko_schedule`` is what insists on one."""
    form = ProjectKickoffForm(
        _projectinitiation_kickoff_payload(projectinitiation_project_draft, meeting_date=""),
        tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.save().meeting_date is None


def test_projectinitiation_minimum_payloads_really_are_valid(
        tenant_a, projectinitiation_project_draft, projectinitiation_party_a):
    """Every negative test below only means something if the baseline it perturbs saves."""
    assert ProjectRequestForm(_projectinitiation_request_payload(), tenant=tenant_a).is_valid()
    assert ProjectForm(_projectinitiation_project_payload(), tenant=tenant_a).is_valid()
    assert ProjectStakeholderForm(
        _projectinitiation_stakeholder_payload(projectinitiation_project_draft,
                                               party=str(projectinitiation_party_a.pk)),
        tenant=tenant_a).is_valid()
    assert ProjectKickoffForm(
        _projectinitiation_kickoff_payload(projectinitiation_project_draft),
        tenant=tenant_a).is_valid()


# ==================================================================================================
# 4. Widgets, choices and date handling
# ==================================================================================================

def test_projectinitiation_date_fields_take_an_iso_date_and_the_html_date_widget(tenant_a):
    """``TenantModelForm`` rewrites every ``DateField`` to ``<input type="date">`` with ONE input
    format. A dd/mm/yyyy POST is a field error, not a silently mis-parsed date.

    The type lives on ``widget.input_type``, not in ``widget.attrs``: ``forms.Input.__init__``
    POPS ``"type"`` out of the attrs dict it is handed and keeps it as the attribute.
    """
    for form_class, names in ((ProjectRequestForm, ("target_start_date", "target_end_date")),
                              (ProjectForm, ("start_date", "end_date"))):
        form = form_class(tenant=tenant_a)
        for name in names:
            field = form.fields[name]
            assert isinstance(field.widget, django_forms.DateInput), name
            assert field.widget.input_type == "date", name
            assert field.widget.attrs["class"] == "form-input", name
            assert field.input_formats == ["%Y-%m-%d"], name


def test_projectinitiation_request_form_accepts_an_iso_target_date(tenant_a):
    today = _projectinitiation_today()
    start = today + datetime.timedelta(days=30)
    form = ProjectRequestForm(
        _projectinitiation_request_payload(target_start_date=start.isoformat()), tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.save().target_start_date == start


def test_projectinitiation_request_form_rejects_a_non_iso_target_date(tenant_a):
    form = ProjectRequestForm(
        _projectinitiation_request_payload(target_start_date="31/12/2026"), tenant=tenant_a)
    assert not form.is_valid()
    assert "target_start_date" in form.errors


def test_projectinitiation_request_form_rejects_a_garbage_target_date(tenant_a):
    form = ProjectRequestForm(
        _projectinitiation_request_payload(target_end_date="not-a-date"), tenant=tenant_a)
    assert not form.is_valid()
    assert "target_end_date" in form.errors


def test_projectinitiation_kickoff_meeting_date_uses_the_datetime_local_widget(tenant_a):
    field = ProjectKickoffForm(tenant=tenant_a).fields["meeting_date"]
    assert isinstance(field.widget, django_forms.DateTimeInput)
    assert field.widget.input_type == "datetime-local"
    assert field.widget.attrs["class"] == "form-input"
    assert field.input_formats == ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]


def test_projectinitiation_kickoff_accepts_a_datetime_local_string(
        tenant_a, projectinitiation_project_draft):
    when = _projectinitiation_minute()
    form = ProjectKickoffForm(
        _projectinitiation_kickoff_payload(projectinitiation_project_draft,
                                           meeting_date=when.strftime("%Y-%m-%dT%H:%M")),
        tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.save().meeting_date == when


def test_projectinitiation_kickoff_rejects_a_garbage_meeting_date(
        tenant_a, projectinitiation_project_draft):
    form = ProjectKickoffForm(
        _projectinitiation_kickoff_payload(projectinitiation_project_draft,
                                           meeting_date="yesterday-ish"),
        tenant=tenant_a)
    assert not form.is_valid()
    assert "meeting_date" in form.errors


def test_projectinitiation_every_choice_field_offers_exactly_the_model_choices(tenant_a):
    """The dropdown a user sees IS the model's CHOICES (plus the blank option a required-with-
    default field renders), so a value the model would refuse is never offered."""
    cases = (
        (ProjectRequestForm, ProjectRequest, ("request_type", "source", "priority",
                                              "risk_rating", "feasibility")),
        (ProjectForm, Project, ("methodology",)),
        (ProjectStakeholderForm, ProjectStakeholder, ("stakeholder_type", "raci_role",
                                                      "influence", "interest",
                                                      "comms_preference", "comms_frequency")),
        (ProjectKickoffForm, ProjectKickoff, ("agenda_template",)),
    )
    for form_class, model, names in cases:
        form = form_class(tenant=tenant_a)
        for name in names:
            offered = [value for value, _label in form.fields[name].choices if value != ""]
            expected = [value for value, _label in model._meta.get_field(name).choices]
            assert offered == expected, f"{form_class.__name__}.{name}"


def test_projectinitiation_request_form_rejects_a_value_outside_the_choices(tenant_a):
    for name, bad in (("request_type", "not_a_type"), ("source", "carrier_pigeon"),
                      ("priority", "urgent"), ("risk_rating", "extreme"),
                      ("feasibility", "maybe")):
        form = ProjectRequestForm(_projectinitiation_request_payload(**{name: bad}),
                                  tenant=tenant_a)
        assert not form.is_valid(), name
        assert name in form.errors, name


def test_projectinitiation_request_form_accepts_the_long_feasibility_value(tenant_a):
    """``feasible_with_constraints`` is 25 characters; the column was widened to 32 for it, and
    the form must carry the same width."""
    form = ProjectRequestForm(
        _projectinitiation_request_payload(feasibility="feasible_with_constraints"),
        tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.save().feasibility == "feasible_with_constraints"


def test_projectinitiation_char_fields_enforce_their_max_length(tenant_a,
                                                                projectinitiation_project_draft):
    """The dev database is not in strict SQL mode, so a missing form-level ``max_length`` would
    TRUNCATE rather than raise. The form is the only real control."""
    cases = (
        (ProjectRequestForm, _projectinitiation_request_payload(title="T" * 201), "title"),
        (ProjectForm, _projectinitiation_project_payload(name="N" * 256), "name"),
        (ProjectForm, _projectinitiation_project_payload(code="C" * 31), "code"),
        (ProjectStakeholderForm,
         _projectinitiation_stakeholder_payload(projectinitiation_project_draft,
                                                raci_scope="S" * 121), "raci_scope"),
        (ProjectKickoffForm,
         _projectinitiation_kickoff_payload(projectinitiation_project_draft,
                                            location_or_link="L" * 256), "location_or_link"),
    )
    for form_class, payload, name in cases:
        form = form_class(payload, tenant=tenant_a)
        assert not form.is_valid(), f"{form_class.__name__}.{name}"
        assert name in form.errors, f"{form_class.__name__}.{name}"


def test_projectinitiation_attending_kickoff_defaults_to_false_when_unchecked(
        tenant_a, projectinitiation_project_draft, projectinitiation_party_a):
    """An unchecked checkbox sends nothing at all - the attendee list must not opt people in."""
    form = ProjectStakeholderForm(
        _projectinitiation_stakeholder_payload(projectinitiation_project_draft,
                                               party=str(projectinitiation_party_a.pk)),
        tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.save().attending_kickoff is False


def test_projectinitiation_attending_kickoff_is_true_when_checked(
        tenant_a, projectinitiation_project_draft, projectinitiation_party_a):
    form = ProjectStakeholderForm(
        _projectinitiation_stakeholder_payload(projectinitiation_project_draft,
                                               party=str(projectinitiation_party_a.pk),
                                               attending_kickoff="on"),
        tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.save().attending_kickoff is True


# ==================================================================================================
# 5. Tenant scoping of every ModelChoiceField queryset
# ==================================================================================================

def test_projectinitiation_request_form_scopes_its_five_tenant_owned_dropdowns(
        tenant_a, admin_user, projectinitiation_party_a, projectinitiation_org_unit_a,
        projectinitiation_opportunity_a, projectinitiation_party_b,
        projectinitiation_org_unit_b, projectinitiation_opportunity_b, admin_b):
    form = ProjectRequestForm(tenant=tenant_a)
    expected = {
        "requested_by": (admin_user, admin_b),
        "assigned_reviewer": (admin_user, admin_b),
        "assigned_approver": (admin_user, admin_b),
        "requester_party": (projectinitiation_party_a, projectinitiation_party_b),
        "org_unit": (projectinitiation_org_unit_a, projectinitiation_org_unit_b),
        "source_opportunity": (projectinitiation_opportunity_a, projectinitiation_opportunity_b),
    }
    for name, (mine, theirs) in expected.items():
        pks = _projectinitiation_pks(form, name)
        assert mine.pk in pks, name
        assert theirs.pk not in pks, name


def test_projectinitiation_project_form_scopes_its_five_tenant_owned_dropdowns(
        tenant_a, admin_user, member_user, admin_b, projectinitiation_party_a,
        projectinitiation_party_b, projectinitiation_org_unit_a, projectinitiation_org_unit_b,
        projectinitiation_document_a, projectinitiation_document_b):
    form = ProjectForm(tenant=tenant_a)
    expected = {
        "executive_sponsor": (admin_user, admin_b),
        "project_manager": (member_user, admin_b),
        "org_unit": (projectinitiation_org_unit_a, projectinitiation_org_unit_b),
        "client": (projectinitiation_party_a, projectinitiation_party_b),
        "charter_document": (projectinitiation_document_a, projectinitiation_document_b),
    }
    for name, (mine, theirs) in expected.items():
        pks = _projectinitiation_pks(form, name)
        assert mine.pk in pks, name
        assert theirs.pk not in pks, name


def test_projectinitiation_stakeholder_form_scopes_project_party_and_user(
        tenant_a, admin_user, admin_b, projectinitiation_project_draft,
        projectinitiation_project_b, projectinitiation_party_a, projectinitiation_party_b):
    form = ProjectStakeholderForm(tenant=tenant_a)
    expected = {
        "project": (projectinitiation_project_draft, projectinitiation_project_b),
        "party": (projectinitiation_party_a, projectinitiation_party_b),
        "user": (admin_user, admin_b),
    }
    for name, (mine, theirs) in expected.items():
        pks = _projectinitiation_pks(form, name)
        assert mine.pk in pks, name
        assert theirs.pk not in pks, name


def test_projectinitiation_kickoff_form_scopes_its_project_dropdown(
        tenant_a, projectinitiation_project_draft, projectinitiation_project_b):
    form = ProjectKickoffForm(tenant=tenant_a)
    pks = _projectinitiation_pks(form, "project")
    assert projectinitiation_project_draft.pk in pks
    assert projectinitiation_project_b.pk not in pks


def test_projectinitiation_no_dropdown_ever_shows_another_workspaces_row(
        tenant_a, tenant_b, admin_b, projectinitiation_party_b, projectinitiation_org_unit_b,
        projectinitiation_opportunity_b, projectinitiation_document_b,
        projectinitiation_project_b, projectinitiation_stakeholder_b):
    """The sweep: with tenant B fully populated and tenant A holding nothing but its admin, no
    dropdown on any of the four forms may contain a tenant B pk."""
    foreign = {
        "user": {admin_b.pk},
        "party": {projectinitiation_party_b.pk},
        "orgunit": {projectinitiation_org_unit_b.pk},
        "opportunity": {projectinitiation_opportunity_b.pk},
        "document": {projectinitiation_document_b.pk},
        "project": {projectinitiation_project_b.pk},
    }
    for form_class, _model in _PROJECTINITIATION_MODEL_FORMS:
        form = form_class(tenant=tenant_a)
        for name, field in _projectinitiation_choice_fields(form).items():
            model_name = field.queryset.model.__name__.lower()
            if model_name in foreign:
                assert _projectinitiation_pks(form, name) & foreign[model_name] == set(), (
                    f"{form_class.__name__}.{name} leaks tenant B")


def test_projectinitiation_scoping_survives_edit_mode(
        tenant_a, projectinitiation_request_draft, projectinitiation_org_unit_b,
        projectinitiation_party_b):
    """Editing an existing row must not widen the dropdowns back out."""
    form = ProjectRequestForm(instance=projectinitiation_request_draft, tenant=tenant_a)
    assert projectinitiation_org_unit_b.pk not in _projectinitiation_pks(form, "org_unit")
    assert projectinitiation_party_b.pk not in _projectinitiation_pks(form, "requester_party")


# ==================================================================================================
# 6. The tenant=None form - the form half of security fix I1
# ==================================================================================================

def test_projectinitiation_a_tenantless_form_stamps_no_tenant_on_its_instance(tenant_a):
    """``TenantUniqueMixin`` only stamps ``if self.tenant is not None``. Without a tenant the row
    would reach the NOT NULL constraint - which is why the create views guard on their FIRST
    line, before the form is ever built."""
    for form_class, _model in _PROJECTINITIATION_MODEL_FORMS:
        assert form_class(tenant=None).instance.tenant_id is None, form_class.__name__
        assert form_class(tenant=tenant_a).instance.tenant_id == tenant_a.pk, form_class.__name__


def test_projectinitiation_stakeholder_form_fails_closed_on_project_without_a_tenant(
        projectinitiation_project_draft, projectinitiation_project_b):
    """The explicit ``.none()`` branch: an unscoped ``project`` dropdown would list EVERY
    workspace's projects."""
    form = ProjectStakeholderForm(tenant=None)
    assert form.fields["project"].queryset.count() == 0


def test_projectinitiation_kickoff_form_fails_closed_on_project_without_a_tenant(
        projectinitiation_project_draft, projectinitiation_project_b):
    form = ProjectKickoffForm(tenant=None)
    assert form.fields["project"].queryset.count() == 0


def test_projectinitiation_kickoff_form_fails_closed_even_on_edit_without_a_tenant(
        tenant_a, projectinitiation_kickoff_planned):
    """The edit branch re-adds the instance's own project by filtering the SAME empty queryset,
    so it stays empty - the row cannot be round-tripped by a tenant-less caller."""
    form = ProjectKickoffForm(instance=projectinitiation_kickoff_planned, tenant=None)
    assert form.fields["project"].queryset.count() == 0


def test_projectinitiation_a_tenantless_stakeholder_post_cannot_name_a_project(
        projectinitiation_project_draft):
    form = ProjectStakeholderForm(
        _projectinitiation_stakeholder_payload(projectinitiation_project_draft), tenant=None)
    assert not form.is_valid()
    assert "project" in form.errors


def test_projectinitiation_a_tenantless_kickoff_post_cannot_name_a_project(
        projectinitiation_project_draft):
    form = ProjectKickoffForm(
        _projectinitiation_kickoff_payload(projectinitiation_project_draft), tenant=None)
    assert not form.is_valid()
    assert "project" in form.errors


def test_projectinitiation_a_tenantless_form_rejects_the_fks_reject_foreign_rechecks(
        projectinitiation_org_unit_a, projectinitiation_opportunity_a,
        projectinitiation_party_a, projectinitiation_document_a):
    """``_reject_foreign`` compares against ``tenant_id = None``, so every row it re-checks is
    "foreign" to a tenant-less form. Fail-closed on ``org_unit`` / ``source_opportunity`` /
    ``client`` / ``charter_document``."""
    request_form = ProjectRequestForm(
        _projectinitiation_request_payload(
            org_unit=str(projectinitiation_org_unit_a.pk),
            source_opportunity=str(projectinitiation_opportunity_a.pk)),
        tenant=None)
    assert not request_form.is_valid()
    assert "org_unit" in request_form.errors
    assert "source_opportunity" in request_form.errors

    project_form = ProjectForm(
        _projectinitiation_project_payload(
            client=str(projectinitiation_party_a.pk),
            charter_document=str(projectinitiation_document_a.pk),
            org_unit=str(projectinitiation_org_unit_a.pk)),
        tenant=None)
    assert not project_form.is_valid()
    for name in ("client", "charter_document", "org_unit"):
        assert name in project_form.errors, name


def test_projectinitiation_a_tenantless_form_does_not_narrow_the_user_dropdowns(
        tenant_a, tenant_b, admin_user, admin_b):
    """CURRENT, DOCUMENTED behaviour, pinned so a regression is visible either way.
    ``TenantModelForm`` scopes only ``if tenant is not None``, so a tenant-less
    ``ProjectRequestForm`` / ``ProjectForm`` offers BOTH workspaces' users - which is precisely
    why fix I1 hoisted the ``request.tenant is None`` guard to the first line of every create
    view rather than relying on the form."""
    for form_class, names in (
            (ProjectRequestForm, ("requested_by", "assigned_reviewer", "assigned_approver")),
            (ProjectForm, ("executive_sponsor", "project_manager")),
            (ProjectStakeholderForm, ("user",))):
        form = form_class(tenant=None)
        for name in names:
            pks = _projectinitiation_pks(form, name)
            assert {admin_user.pk, admin_b.pk} <= pks, f"{form_class.__name__}.{name}"


def test_projectinitiation_a_tenantless_form_does_not_narrow_the_party_dropdowns(
        projectinitiation_party_a, projectinitiation_party_b):
    """Same documented gap, on ``core.Party``. Pinned, not asserted as desirable."""
    form = ProjectStakeholderForm(tenant=None)
    pks = _projectinitiation_pks(form, "party")
    assert {projectinitiation_party_a.pk, projectinitiation_party_b.pk} <= pks


def test_projectinitiation_a_tenantless_form_still_offers_the_same_field_list(tenant_a):
    """Whatever the querysets do, the field LIST is unchanged - the exclusions are not
    tenant-dependent."""
    for form_class, _model in _PROJECTINITIATION_MODEL_FORMS:
        assert set(form_class(tenant=None).fields) == set(form_class(tenant=tenant_a).fields), (
            form_class.__name__)


# ==================================================================================================
# 7. Cross-tenant FK rejection - the narrowed queryset, then the clean() backstop behind it
# ==================================================================================================

def test_projectinitiation_request_form_rejects_every_cross_tenant_fk(
        tenant_a, admin_b, projectinitiation_party_b, projectinitiation_org_unit_b,
        projectinitiation_opportunity_b):
    """A crafted POST carrying tenant B pks in an otherwise valid tenant A form. The queryset
    narrowing answers FIRST (contract 2.6), so the assertion is "this field has an error" and
    never the wording."""
    form = ProjectRequestForm(
        _projectinitiation_request_payload(
            requested_by=str(admin_b.pk),
            assigned_reviewer=str(admin_b.pk),
            assigned_approver=str(admin_b.pk),
            requester_party=str(projectinitiation_party_b.pk),
            org_unit=str(projectinitiation_org_unit_b.pk),
            source_opportunity=str(projectinitiation_opportunity_b.pk)),
        tenant=tenant_a)
    assert not form.is_valid()
    for name in ("requested_by", "assigned_reviewer", "assigned_approver", "requester_party",
                 "org_unit", "source_opportunity"):
        assert name in form.errors, name


def test_projectinitiation_request_form_rejects_one_cross_tenant_fk_on_its_own(
        tenant_a, projectinitiation_org_unit_b):
    """One bad pk among nine good values still fails - a partial rejection that saved the row
    minus the foreign FK would be worse than either outcome."""
    form = ProjectRequestForm(
        _projectinitiation_request_payload(org_unit=str(projectinitiation_org_unit_b.pk)),
        tenant=tenant_a)
    assert not form.is_valid()
    assert "org_unit" in form.errors
    assert ProjectRequest.objects.count() == 0


def test_projectinitiation_project_form_rejects_every_cross_tenant_fk(
        tenant_a, admin_b, projectinitiation_party_b, projectinitiation_org_unit_b,
        projectinitiation_document_b):
    form = ProjectForm(
        _projectinitiation_project_payload(
            executive_sponsor=str(admin_b.pk),
            project_manager=str(admin_b.pk),
            org_unit=str(projectinitiation_org_unit_b.pk),
            client=str(projectinitiation_party_b.pk),
            charter_document=str(projectinitiation_document_b.pk)),
        tenant=tenant_a)
    assert not form.is_valid()
    for name in ("executive_sponsor", "project_manager", "org_unit", "client",
                 "charter_document"):
        assert name in form.errors, name


def test_projectinitiation_stakeholder_form_rejects_a_cross_tenant_project(
        tenant_a, projectinitiation_project_b, projectinitiation_party_a):
    form = ProjectStakeholderForm(
        _projectinitiation_stakeholder_payload(projectinitiation_project_b,
                                               party=str(projectinitiation_party_a.pk)),
        tenant=tenant_a)
    assert not form.is_valid()
    assert "project" in form.errors
    assert ProjectStakeholder.objects.count() == 0


def test_projectinitiation_stakeholder_form_rejects_a_cross_tenant_party(
        tenant_a, projectinitiation_project_draft, projectinitiation_party_b):
    form = ProjectStakeholderForm(
        _projectinitiation_stakeholder_payload(projectinitiation_project_draft,
                                               party=str(projectinitiation_party_b.pk)),
        tenant=tenant_a)
    assert not form.is_valid()
    assert "party" in form.errors


def test_projectinitiation_stakeholder_form_rejects_a_cross_tenant_user(
        tenant_a, projectinitiation_project_draft, admin_b):
    form = ProjectStakeholderForm(
        _projectinitiation_stakeholder_payload(projectinitiation_project_draft,
                                               user=str(admin_b.pk)),
        tenant=tenant_a)
    assert not form.is_valid()
    assert "user" in form.errors


def test_projectinitiation_kickoff_form_rejects_a_cross_tenant_project(
        tenant_a, projectinitiation_project_b):
    form = ProjectKickoffForm(
        _projectinitiation_kickoff_payload(projectinitiation_project_b), tenant=tenant_a)
    assert not form.is_valid()
    assert "project" in form.errors
    assert ProjectKickoff.objects.count() == 0


def test_projectinitiation_a_nonexistent_pk_is_a_field_error_not_a_crash(
        tenant_a, projectinitiation_project_draft):
    """The other crafted-POST shape: a pk that belongs to nobody at all."""
    assert not ProjectRequestForm(
        _projectinitiation_request_payload(org_unit="999999"), tenant=tenant_a).is_valid()
    assert not ProjectForm(
        _projectinitiation_project_payload(client="999999"), tenant=tenant_a).is_valid()
    assert not ProjectStakeholderForm(
        _projectinitiation_stakeholder_payload(projectinitiation_project_draft,
                                               party="999999"), tenant=tenant_a).is_valid()
    assert not ProjectKickoffForm(
        {"project": "999999", "agenda_template": "standard"}, tenant=tenant_a).is_valid()


def test_projectinitiation_a_junk_fk_value_is_a_field_error_not_a_crash(
        tenant_a, projectinitiation_project_draft):
    """L11's form-layer twin: ``?category=abc`` on a list, ``org_unit=abc`` in a POST."""
    for value in ("abc", "NaN", "1e400", "-1", "0"):
        form = ProjectRequestForm(
            _projectinitiation_request_payload(org_unit=value), tenant=tenant_a)
        assert not form.is_valid(), value
        assert "org_unit" in form.errors, value


def test_projectinitiation_reject_foreign_backstops_a_widened_request_queryset(
        tenant_a, projectinitiation_org_unit_b, projectinitiation_opportunity_b):
    """The SECOND layer, reached by widening the queryset first - the shape a POST that never
    went near the widget actually takes. Here ``_reject_foreign``'s own message is what answers,
    so this is where the wording is asserted."""
    form = ProjectRequestForm(
        _projectinitiation_request_payload(
            org_unit=str(projectinitiation_org_unit_b.pk),
            source_opportunity=str(projectinitiation_opportunity_b.pk)),
        tenant=tenant_a)
    _projectinitiation_widen(form, "org_unit", "source_opportunity")
    assert not form.is_valid()
    assert form.errors["org_unit"] == ["That record belongs to another workspace."]
    assert form.errors["source_opportunity"] == ["That record belongs to another workspace."]


def test_projectinitiation_reject_foreign_backstops_a_widened_project_queryset(
        tenant_a, projectinitiation_org_unit_b, projectinitiation_party_b,
        projectinitiation_document_b):
    form = ProjectForm(
        _projectinitiation_project_payload(
            org_unit=str(projectinitiation_org_unit_b.pk),
            client=str(projectinitiation_party_b.pk),
            charter_document=str(projectinitiation_document_b.pk)),
        tenant=tenant_a)
    _projectinitiation_widen(form, "org_unit", "client", "charter_document")
    assert not form.is_valid()
    for name in ("org_unit", "client", "charter_document"):
        assert form.errors[name] == ["That record belongs to another workspace."], name


def test_projectinitiation_reject_foreign_backstops_a_widened_stakeholder_queryset(
        tenant_a, projectinitiation_project_b, projectinitiation_party_b):
    form = ProjectStakeholderForm(
        _projectinitiation_stakeholder_payload(projectinitiation_project_b,
                                               party=str(projectinitiation_party_b.pk)),
        tenant=tenant_a)
    _projectinitiation_widen(form, "project", "party")
    assert not form.is_valid()
    assert "project" in form.errors
    assert "party" in form.errors
    assert ProjectStakeholder.objects.count() == 0


def test_projectinitiation_reject_foreign_backstops_a_widened_kickoff_queryset(
        tenant_a, projectinitiation_project_b):
    form = ProjectKickoffForm(
        _projectinitiation_kickoff_payload(projectinitiation_project_b), tenant=tenant_a)
    _projectinitiation_widen(form, "project")
    assert not form.is_valid()
    assert form.errors["project"] == ["That record belongs to another workspace."]


def test_projectinitiation_reject_foreign_leaves_a_valid_own_tenant_row_alone(
        tenant_a, projectinitiation_org_unit_a, projectinitiation_opportunity_a):
    """The backstop must not fire on the happy path - a rule that rejects everything is not a
    rule."""
    form = ProjectRequestForm(
        _projectinitiation_request_payload(
            org_unit=str(projectinitiation_org_unit_a.pk),
            source_opportunity=str(projectinitiation_opportunity_a.pk)),
        tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.org_unit_id == projectinitiation_org_unit_a.pk
    assert obj.source_opportunity_id == projectinitiation_opportunity_a.pk


# ==================================================================================================
# 8. accounting.Currency - the ONE deliberately GLOBAL FK (L29)
# ==================================================================================================

def test_projectinitiation_currency_target_model_has_no_tenant_column(tenant_a):
    """The premise of the whole exemption, asserted rather than assumed: if ``Currency`` ever
    grew a ``tenant`` column, ``TenantModelForm`` would silently start narrowing it and every
    workspace's dropdown would empty."""
    field = ProjectRequestForm(tenant=tenant_a).fields["currency"]
    assert "tenant" not in {f.name for f in field.queryset.model._meta.fields}


def test_projectinitiation_currency_dropdown_is_not_narrowed(
        tenant_a, tenant_b, projectinitiation_currency):
    """The same global row is offered to both workspaces."""
    for tenant in (tenant_a, tenant_b, None):
        form = ProjectRequestForm(tenant=tenant)
        assert projectinitiation_currency.pk in _projectinitiation_pks(form, "currency")


def test_projectinitiation_currency_is_accepted_on_a_valid_request(
        tenant_a, projectinitiation_currency):
    form = ProjectRequestForm(
        _projectinitiation_request_payload(currency=str(projectinitiation_currency.pk)),
        tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.save().currency_id == projectinitiation_currency.pk


def test_projectinitiation_currency_is_never_handed_to_reject_foreign(
        projectinitiation_currency, projectinitiation_org_unit_a):
    """Behavioural proof that ``currency`` is NOT in ``clean()``'s recheck list.

    ``_reject_foreign`` compares ``getattr(chosen, "tenant_id", None)`` against the form's tenant,
    so on a ``tenant=None`` form it rejects every row it is handed. In one and the same POST the
    tenant-scoped ``org_unit`` is refused and the GLOBAL ``currency`` is accepted - which can only
    happen if ``currency`` was never passed to it (L29). A regression that added the name would
    make every currency unselectable in every workspace.
    """
    form = ProjectRequestForm(
        _projectinitiation_request_payload(
            currency=str(projectinitiation_currency.pk),
            org_unit=str(projectinitiation_org_unit_a.pk)),
        tenant=None)
    assert not form.is_valid()
    assert "org_unit" in form.errors
    assert "currency" not in form.errors
    assert form.cleaned_data["currency"] == projectinitiation_currency


# ==================================================================================================
# 9. ProjectKickoffForm - one kickoff per project, and the edit round-trip
# ==================================================================================================

def test_projectinitiation_kickoff_dropdown_offers_only_projects_without_a_kickoff(tenant_a):
    free = _projectinitiation_project(tenant_a, name="Free host", code="FH-01")
    taken = _projectinitiation_project(tenant_a, name="Taken host", code="TH-01")
    _projectinitiation_kickoff(taken)

    pks = _projectinitiation_pks(ProjectKickoffForm(tenant=tenant_a), "project")
    assert free.pk in pks
    assert taken.pk not in pks


def test_projectinitiation_kickoff_create_refuses_a_project_that_already_has_one(tenant_a):
    """``unique_together = ("tenant", "project")`` enforced at the FORM, so the user gets a field
    error instead of an IntegrityError 500."""
    taken = _projectinitiation_project(tenant_a, name="Taken host", code="TH-01")
    _projectinitiation_kickoff(taken)

    form = ProjectKickoffForm(_projectinitiation_kickoff_payload(taken), tenant=tenant_a)
    assert not form.is_valid()
    assert "project" in form.errors
    assert ProjectKickoff.objects.filter(project=taken).count() == 1


def test_projectinitiation_kickoff_edit_still_offers_its_own_project(tenant_a):
    """Without the ``qs.filter(pk=instance.project_id) |`` branch the edit form could not
    round-trip: its own project would be "taken" by itself."""
    free = _projectinitiation_project(tenant_a, name="Free host", code="FH-01")
    host = _projectinitiation_project(tenant_a, name="Edit host", code="EH-01")
    kickoff = _projectinitiation_kickoff(host)

    pks = _projectinitiation_pks(ProjectKickoffForm(instance=kickoff, tenant=tenant_a), "project")
    assert host.pk in pks
    assert free.pk in pks


def test_projectinitiation_kickoff_edit_does_not_offer_another_rows_project(tenant_a):
    """Its OWN project, not every taken one - moving this kickoff onto a project that already has
    one would break the constraint."""
    mine = _projectinitiation_project(tenant_a, name="Mine", code="MI-01")
    theirs = _projectinitiation_project(tenant_a, name="Theirs", code="TR-01")
    kickoff = _projectinitiation_kickoff(mine)
    _projectinitiation_kickoff(theirs)

    pks = _projectinitiation_pks(ProjectKickoffForm(instance=kickoff, tenant=tenant_a), "project")
    assert mine.pk in pks
    assert theirs.pk not in pks


def test_projectinitiation_kickoff_edit_saves_unchanged(tenant_a,
                                                        projectinitiation_kickoff_planned):
    form = ProjectKickoffForm(
        _projectinitiation_kickoff_payload(projectinitiation_kickoff_planned.project,
                                           agenda="Rewritten agenda"),
        instance=projectinitiation_kickoff_planned, tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.pk == projectinitiation_kickoff_planned.pk
    assert obj.agenda == "Rewritten agenda"
    assert obj.project_id == projectinitiation_kickoff_planned.project_id


def test_projectinitiation_kickoff_dropdown_ignores_another_tenants_taken_projects(
        tenant_a, tenant_b):
    """The "taken" exclusion is computed inside the tenant's own queryset, so tenant B's kickoffs
    can neither hide nor reveal a tenant A project."""
    mine = _projectinitiation_project(tenant_a, name="Mine", code="MI-01")
    theirs = _projectinitiation_project(tenant_b, name="Theirs", code="TR-01")
    _projectinitiation_kickoff(theirs)

    pks = _projectinitiation_pks(ProjectKickoffForm(tenant=tenant_a), "project")
    assert pks == {mine.pk}


# ==================================================================================================
# 10. ProjectStakeholderForm - party-or-user, and the duplicate rule
# ==================================================================================================

def test_projectinitiation_stakeholder_form_rejects_neither_party_nor_user(
        tenant_a, projectinitiation_project_draft):
    """The model's ``clean()`` surfacing through the form as a NON-FIELD error - there is no one
    field to blame, and a row identifying nobody is worse than no row."""
    form = ProjectStakeholderForm(
        _projectinitiation_stakeholder_payload(projectinitiation_project_draft), tenant=tenant_a)
    assert not form.is_valid()
    assert NON_FIELD_ERRORS in form.errors
    assert form.non_field_errors()
    assert ProjectStakeholder.objects.count() == 0


def test_projectinitiation_stakeholder_form_accepts_a_party_alone(
        tenant_a, projectinitiation_project_draft, projectinitiation_party_a):
    form = ProjectStakeholderForm(
        _projectinitiation_stakeholder_payload(projectinitiation_project_draft,
                                               party=str(projectinitiation_party_a.pk)),
        tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.party_id == projectinitiation_party_a.pk and obj.user_id is None


def test_projectinitiation_stakeholder_form_accepts_a_user_alone(
        tenant_a, projectinitiation_project_draft, member_user):
    form = ProjectStakeholderForm(
        _projectinitiation_stakeholder_payload(projectinitiation_project_draft,
                                               user=str(member_user.pk)),
        tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.user_id == member_user.pk and obj.party_id is None


def test_projectinitiation_stakeholder_form_accepts_both_a_party_and_a_user(
        tenant_a, projectinitiation_project_draft, projectinitiation_party_a, member_user):
    """"At least one", not "exactly one" - a named person who also has a login is one row."""
    form = ProjectStakeholderForm(
        _projectinitiation_stakeholder_payload(projectinitiation_project_draft,
                                               party=str(projectinitiation_party_a.pk),
                                               user=str(member_user.pk)),
        tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.party_id and obj.user_id


def test_projectinitiation_stakeholder_form_rejects_a_duplicate_raci_assignment(
        tenant_a, projectinitiation_project_draft, projectinitiation_party_a):
    """Same project, same party, same scope twice would double-count them in the grid. A
    non-field error, because the clash is the combination."""
    _projectinitiation_stakeholder(projectinitiation_project_draft,
                                   party=projectinitiation_party_a,
                                   raci_scope="charter approval")
    form = ProjectStakeholderForm(
        _projectinitiation_stakeholder_payload(projectinitiation_project_draft,
                                               party=str(projectinitiation_party_a.pk),
                                               raci_scope="charter approval"),
        tenant=tenant_a)
    assert not form.is_valid()
    assert NON_FIELD_ERRORS in form.errors
    assert ProjectStakeholder.objects.filter(project=projectinitiation_project_draft).count() == 1


def test_projectinitiation_stakeholder_form_allows_the_same_party_on_a_different_scope(
        tenant_a, projectinitiation_project_draft, projectinitiation_party_a):
    """A RACI is a relationship to a piece of WORK: the same sponsor may be ``a`` for charter
    approval and ``c`` for vendor selection."""
    _projectinitiation_stakeholder(projectinitiation_project_draft,
                                   party=projectinitiation_party_a,
                                   raci_scope="charter approval")
    form = ProjectStakeholderForm(
        _projectinitiation_stakeholder_payload(projectinitiation_project_draft,
                                               party=str(projectinitiation_party_a.pk),
                                               raci_role="c", raci_scope="vendor selection"),
        tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_projectinitiation_stakeholder_form_allows_the_same_party_on_a_different_project(
        tenant_a, projectinitiation_project_draft, projectinitiation_party_a):
    other = _projectinitiation_project(tenant_a, name="Second project", code="SP-01")
    _projectinitiation_stakeholder(projectinitiation_project_draft,
                                   party=projectinitiation_party_a,
                                   raci_scope="charter approval")
    form = ProjectStakeholderForm(
        _projectinitiation_stakeholder_payload(other,
                                               party=str(projectinitiation_party_a.pk),
                                               raci_scope="charter approval"),
        tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_projectinitiation_stakeholder_edit_does_not_trip_its_own_duplicate_check(
        tenant_a, projectinitiation_stakeholder_a, projectinitiation_party_a):
    """``clean()`` excludes ``self.pk`` - otherwise no stakeholder row could ever be edited."""
    form = ProjectStakeholderForm(
        _projectinitiation_stakeholder_payload(projectinitiation_stakeholder_a.project,
                                               party=str(projectinitiation_party_a.pk),
                                               raci_scope="charter approval",
                                               notes="Updated note"),
        instance=projectinitiation_stakeholder_a, tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.save().notes == "Updated note"


def test_projectinitiation_stakeholder_duplicate_check_does_not_cross_tenants(
        tenant_a, tenant_b, projectinitiation_party_a):
    """The constraint is per workspace: tenant B holding an identical-looking row must not block
    tenant A's create."""
    mine = _projectinitiation_project(tenant_a, name="Shared name", code="SN-01")
    theirs = _projectinitiation_project(tenant_b, name="Shared name", code="SN-01")
    _projectinitiation_stakeholder(theirs, raci_scope="charter approval")

    form = ProjectStakeholderForm(
        _projectinitiation_stakeholder_payload(mine,
                                               party=str(projectinitiation_party_a.pk),
                                               raci_scope="charter approval"),
        tenant=tenant_a)
    assert form.is_valid(), form.errors


def test_projectinitiation_stakeholder_form_stamps_the_tenant_before_the_model_clean_runs(
        tenant_a, projectinitiation_project_draft, projectinitiation_party_a):
    """``TenantUniqueMixin`` first in the MRO, proved by behaviour: the model's ``clean()``
    filters on ``self.tenant_id``, so an unstamped instance would look for duplicates in
    ``tenant_id=None`` and the ``(tenant, number)`` unique check would compare against nothing."""
    form = ProjectStakeholderForm(
        _projectinitiation_stakeholder_payload(projectinitiation_project_draft,
                                               party=str(projectinitiation_party_a.pk)),
        tenant=tenant_a)
    assert form.instance.tenant_id == tenant_a.pk
    assert form.is_valid(), form.errors
    assert form.save().tenant_id == tenant_a.pk


# ==================================================================================================
# 11. Numeric hardening - every bad number is a FIELD error, never a 500 (the 0002 validators)
# ==================================================================================================

@pytest.mark.parametrize("name", ["estimated_cost", "estimated_benefit"])
def test_projectinitiation_a_negative_estimate_is_rejected(tenant_a, name):
    """Migration ``0002`` added ``MinValueValidator(0)`` precisely because a negative cost reaches
    ``roi_pct``, where ``q2()`` clamps it to a fabricated -9999999999.99% that the
    ready-to-convert queue then ranks on."""
    form = ProjectRequestForm(_projectinitiation_request_payload(**{name: "-5"}), tenant=tenant_a)
    assert not form.is_valid()
    assert name in form.errors
    assert "greater than or equal to 0" in " ".join(form.errors[name])


@pytest.mark.parametrize("name", ["estimated_cost", "estimated_benefit"])
@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-Infinity", "abc", "1,000", "", "   "])
def test_projectinitiation_a_non_numeric_estimate_is_a_field_error(tenant_a, name, bad):
    """``NaN`` and ``Infinity`` are the ones that used to 500 here: a Decimal accepts both and
    every downstream comparison then behaves nonsensically."""
    form = ProjectRequestForm(_projectinitiation_request_payload(**{name: bad}), tenant=tenant_a)
    assert not form.is_valid()
    assert name in form.errors
    assert ProjectRequest.objects.count() == 0


@pytest.mark.parametrize("name", ["estimated_cost", "estimated_benefit"])
@pytest.mark.parametrize("bad", ["999999999999999.99", "1e400", "99999999999999999999"])
def test_projectinitiation_an_over_max_digits_estimate_is_a_field_error(tenant_a, name, bad):
    """``max_digits=14``. Over it is a friendly message, not a database error."""
    form = ProjectRequestForm(_projectinitiation_request_payload(**{name: bad}), tenant=tenant_a)
    assert not form.is_valid()
    assert name in form.errors


@pytest.mark.parametrize("name", ["estimated_cost", "estimated_benefit"])
def test_projectinitiation_a_third_decimal_place_is_a_field_error(tenant_a, name):
    """``decimal_places=2``. Silently rounding money is how a business case stops reconciling."""
    form = ProjectRequestForm(_projectinitiation_request_payload(**{name: "1.005"}),
                              tenant=tenant_a)
    assert not form.is_valid()
    assert name in form.errors


@pytest.mark.parametrize("name", ["estimated_cost", "estimated_benefit"])
def test_projectinitiation_the_boundary_estimates_are_accepted(tenant_a, name):
    """Zero and the largest 14-digit value both save - the guard bounds the field, it does not
    narrow it."""
    for good in ("0", "0.00", "999999999999.99"):
        form = ProjectRequestForm(_projectinitiation_request_payload(**{name: good}),
                                  tenant=tenant_a)
        assert form.is_valid(), (name, good, form.errors)
        assert getattr(form.save(), name) == Decimal(good)


def test_projectinitiation_a_zero_cost_saves_and_reads_a_none_roi(tenant_a):
    """The form's half of the divide-by-zero contract: the row saves, and the DERIVED figure is
    ``None`` rather than an exception or a fabricated infinity."""
    form = ProjectRequestForm(
        _projectinitiation_request_payload(estimated_cost="0", estimated_benefit="500.00"),
        tenant=tenant_a)
    assert form.is_valid(), form.errors
    obj = form.save()
    assert obj.estimated_cost == Decimal("0.00")
    assert obj.roi_pct is None
    assert obj.risk_adjusted_roi_pct is None


def test_projectinitiation_strategic_alignment_above_five_is_rejected(tenant_a):
    """``MaxValueValidator(5)`` - a 9 out of 5 makes the whole scoring column meaningless."""
    form = ProjectRequestForm(_projectinitiation_request_payload(strategic_alignment="9"),
                              tenant=tenant_a)
    assert not form.is_valid()
    assert "strategic_alignment" in form.errors
    assert "less than or equal to 5" in " ".join(form.errors["strategic_alignment"])


def test_projectinitiation_strategic_alignment_below_zero_is_rejected(tenant_a):
    """``PositiveSmallIntegerField`` floors the widget at 0 and the field validates it."""
    form = ProjectRequestForm(_projectinitiation_request_payload(strategic_alignment="-1"),
                              tenant=tenant_a)
    assert not form.is_valid()
    assert "strategic_alignment" in form.errors


@pytest.mark.parametrize("bad", ["abc", "NaN", "Infinity", "2.5", "999999999999999999999"])
def test_projectinitiation_a_junk_strategic_alignment_is_a_field_error(tenant_a, bad):
    form = ProjectRequestForm(_projectinitiation_request_payload(strategic_alignment=bad),
                              tenant=tenant_a)
    assert not form.is_valid(), bad
    assert "strategic_alignment" in form.errors, bad


@pytest.mark.parametrize("good", ["0", "3", "5"])
def test_projectinitiation_the_strategic_alignment_boundaries_are_accepted(tenant_a, good):
    """0 means "not scored", not "no alignment" - both ends of the scale must save."""
    form = ProjectRequestForm(_projectinitiation_request_payload(strategic_alignment=good),
                              tenant=tenant_a)
    assert form.is_valid(), form.errors
    assert form.save().strategic_alignment == int(good)


def test_projectinitiation_no_bad_number_ever_saves_a_row(tenant_a):
    """The point of every case above, stated once: a rejected form writes nothing."""
    for payload in (_projectinitiation_request_payload(estimated_cost="NaN"),
                    _projectinitiation_request_payload(estimated_benefit="-1"),
                    _projectinitiation_request_payload(strategic_alignment="99")):
        assert not ProjectRequestForm(payload, tenant=tenant_a).is_valid()
    assert ProjectRequest.objects.count() == 0


# ==================================================================================================
# 12. ProjectRequestDecisionForm - the reason both gated verbs insist on
# ==================================================================================================

def test_projectinitiation_decision_form_has_exactly_one_field():
    form = ProjectRequestDecisionForm()
    assert list(form.fields) == ["reason"]


def test_projectinitiation_decision_form_reason_is_required():
    """A rejection with no stated reason is the single most common way an intake process loses
    the trust of the people feeding it - and ``prq_reject`` refuses without it."""
    field = ProjectRequestDecisionForm().fields["reason"]
    assert field.required is True
    assert field.label == "Reason"


def test_projectinitiation_decision_form_renders_a_textarea():
    widget = ProjectRequestDecisionForm().fields["reason"].widget
    assert isinstance(widget, django_forms.Textarea)
    assert widget.attrs["class"] == "form-textarea"
    assert widget.attrs["rows"] == 3


def test_projectinitiation_decision_form_rejects_an_empty_reason():
    for data in ({}, {"reason": ""}, {"reason": "   "}):
        form = ProjectRequestDecisionForm(data)
        assert not form.is_valid(), data
        assert "reason" in form.errors, data


def test_projectinitiation_decision_form_accepts_a_stated_reason():
    form = ProjectRequestDecisionForm({"reason": "Negative ROI; three mature vendors exist."})
    assert form.is_valid(), form.errors
    assert form.cleaned_data["reason"] == "Negative ROI; three mature vendors exist."


def test_projectinitiation_decision_form_takes_no_tenant_and_writes_nothing():
    """It is a plain ``forms.Form``: no ``instance``, no ``save()``, no tenant scoping to get
    wrong. The verb reads ``cleaned_data["reason"]`` and stamps the row itself."""
    form = ProjectRequestDecisionForm({"reason": "x"})
    assert not hasattr(form, "instance")
    assert not hasattr(form, "save")


# ==================================================================================================
# 13. Round-trip - an unchanged edit form re-submitted changes nothing
# ==================================================================================================

def test_projectinitiation_request_form_round_trips_unchanged(
        tenant_a, projectinitiation_request_draft):
    """Build from the instance, send exactly what the widgets rendered, and assert Django itself
    saw NO change. ``changed_data == []`` is a stronger claim than field-by-field equality: it
    also proves the widget formats and the input formats agree."""
    bound = ProjectRequestForm(instance=projectinitiation_request_draft, tenant=tenant_a)
    again = ProjectRequestForm(_projectinitiation_roundtrip_payload(bound),
                               instance=projectinitiation_request_draft, tenant=tenant_a)
    assert again.is_valid(), again.errors
    assert again.changed_data == []


def test_projectinitiation_project_form_round_trips_unchanged(
        tenant_a, projectinitiation_project_draft):
    bound = ProjectForm(instance=projectinitiation_project_draft, tenant=tenant_a)
    again = ProjectForm(_projectinitiation_roundtrip_payload(bound),
                        instance=projectinitiation_project_draft, tenant=tenant_a)
    assert again.is_valid(), again.errors
    assert again.changed_data == []


def test_projectinitiation_stakeholder_form_round_trips_unchanged(
        tenant_a, projectinitiation_stakeholder_a):
    bound = ProjectStakeholderForm(instance=projectinitiation_stakeholder_a, tenant=tenant_a)
    again = ProjectStakeholderForm(_projectinitiation_roundtrip_payload(bound),
                                   instance=projectinitiation_stakeholder_a, tenant=tenant_a)
    assert again.is_valid(), again.errors
    assert again.changed_data == []


def test_projectinitiation_kickoff_form_round_trips_unchanged(tenant_a):
    """``meeting_date`` is truncated to the minute up front, because a ``datetime-local`` input
    carries no seconds - so any difference the assertion finds is the FORM's, not the widget's."""
    project = _projectinitiation_project(tenant_a, name="Round-trip host", code="RT-01")
    kickoff = _projectinitiation_kickoff(project, meeting_date=_projectinitiation_minute())

    bound = ProjectKickoffForm(instance=kickoff, tenant=tenant_a)
    again = ProjectKickoffForm(_projectinitiation_roundtrip_payload(bound), instance=kickoff,
                               tenant=tenant_a)
    assert again.is_valid(), again.errors
    assert again.changed_data == []


def test_projectinitiation_a_round_tripped_request_keeps_every_value(
        tenant_a, projectinitiation_request_draft):
    """The saved row, field by field - ``changed_data`` proves the form saw no change, this
    proves the database agrees."""
    before = {name: getattr(projectinitiation_request_draft, name)
              for name in _PROJECTINITIATION_REQUEST_FIELDS}
    bound = ProjectRequestForm(instance=projectinitiation_request_draft, tenant=tenant_a)
    again = ProjectRequestForm(_projectinitiation_roundtrip_payload(bound),
                               instance=projectinitiation_request_draft, tenant=tenant_a)
    assert again.is_valid(), again.errors
    saved = again.save()
    saved.refresh_from_db()
    for name, value in before.items():
        assert getattr(saved, name) == value, name


def test_projectinitiation_a_round_tripped_request_keeps_its_number_and_workflow_state(
        tenant_a, projectinitiation_request_approved):
    """The excluded columns survive an edit of a DECIDED row: the number, the status, the
    decision and both stamps are untouched by a form that cannot name them."""
    before = (projectinitiation_request_approved.number,
              projectinitiation_request_approved.status,
              projectinitiation_request_approved.decision,
              projectinitiation_request_approved.decided_by_id,
              projectinitiation_request_approved.decided_at,
              projectinitiation_request_approved.submitted_at)

    bound = ProjectRequestForm(instance=projectinitiation_request_approved, tenant=tenant_a)
    again = ProjectRequestForm(_projectinitiation_roundtrip_payload(bound),
                               instance=projectinitiation_request_approved, tenant=tenant_a)
    assert again.is_valid(), again.errors
    saved = again.save()
    saved.refresh_from_db()
    assert (saved.number, saved.status, saved.decision, saved.decided_by_id, saved.decided_at,
            saved.submitted_at) == before


def test_projectinitiation_a_round_tripped_project_keeps_its_charter_evidence(
        tenant_a, projectinitiation_project_charter_approved):
    before = (projectinitiation_project_charter_approved.number,
              projectinitiation_project_charter_approved.charter_status,
              projectinitiation_project_charter_approved.charter_approved_by_id,
              projectinitiation_project_charter_approved.charter_approved_at,
              projectinitiation_project_charter_approved.status)

    bound = ProjectForm(instance=projectinitiation_project_charter_approved, tenant=tenant_a)
    again = ProjectForm(_projectinitiation_roundtrip_payload(bound),
                        instance=projectinitiation_project_charter_approved, tenant=tenant_a)
    assert again.is_valid(), again.errors
    saved = again.save()
    saved.refresh_from_db()
    assert (saved.number, saved.charter_status, saved.charter_approved_by_id,
            saved.charter_approved_at, saved.status) == before


def test_projectinitiation_a_round_trip_does_not_move_the_row_between_tenants(
        tenant_a, projectinitiation_stakeholder_a):
    bound = ProjectStakeholderForm(instance=projectinitiation_stakeholder_a, tenant=tenant_a)
    again = ProjectStakeholderForm(_projectinitiation_roundtrip_payload(bound),
                                   instance=projectinitiation_stakeholder_a, tenant=tenant_a)
    assert again.is_valid(), again.errors
    saved = again.save()
    saved.refresh_from_db()
    assert saved.tenant_id == tenant_a.pk
    assert saved.number == projectinitiation_stakeholder_a.number
