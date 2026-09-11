"""Projects 7.3 Resource Management - FORM tests.

The three resource forms are 7.3's write boundary for pool rows, bookings and day-entries:
every byte that reaches a ``ResourceProfile``, ``ResourceAllocation`` or
``ResourceTimeEntry`` through the UI passes through one of them. This lane owns the claims
no other lane can see.

**1. What is NOT a field.** ``ResourceProfileForm`` deliberately KEEPS ``status`` (active /
inactive is a lens toggle on the pool register, not governance state), while
``ResourceAllocationForm`` omits ``booking_status`` + ``substitute_of`` (verb-driven - only
assign / substitute / commit / complete / cancel write them) and ``requested_by``
(provenance, stamped by ``ral_create``), and ``ResourceTimeEntryForm`` omits ``status`` and
every approval stamp plus ``decision_note`` - the form can never rewind or forge an approval
because it cannot touch the stamps at all. ``tenant`` and ``number`` are the system's on all
three. Each absence is asserted twice over (L20/L22): the name is missing from
``form.fields``, and a payload carrying the excluded names is bound and the saved row proved
to hold the system's values, not the smuggled ones.

**2. Tenant scoping on both layers.** ``TenantModelForm`` narrows every ``ModelChoiceField``
whose target carries a ``tenant`` column (employee / party / org_unit on the pool form;
project / project_request / project_task / resource on the booking form; resource / project /
project_task on the time-entry form), so a crafted cross-tenant POST answers with Django's
``"Select a valid choice."`` - the field HAS an error, never asserting wording. Widening the
queryset first (the shape a POST that never went near the widget actually takes) reaches the
``_reject_foreign`` backstop behind each form's ``clean()``, where the pinned wording
``"That record belongs to another workspace."`` does answer.

**3. The model ``clean()`` guards, surfaced through the form.** ``save()`` never runs
``clean()``, so the FORM's ``_post_clean`` is where these bite, and this lane is the proof
they render: the pool row's exactly-one-of-employee/party (non-field) and its one-row-per-
employee pool check (keyed ``employee``); the booking's attach-to-project-or-request
(non-field), its ``end_date >= start_date`` window (keyed ``end_date``) and the
one-magnitude-matching-the-unit rule (keyed the magnitude field - each of the three units,
both the missing-own and the second-magnitude branch). ``ResourceTimeEntry`` has NO model
clean: ``hours > 0`` is a validator, and its floor (0.01) plus the NaN / Infinity / garbage
hardening are pinned at form level.

Also pinned: the fixer-era ``select_related("employee__party", "party")`` on the resource
dropdown of the booking and time-entry forms (``ResourceProfile.name`` walks employee ->
party - I7), and the two Meta.help_texts that teach the one-magnitude rule.

Required fields: as everywhere in this app, a field carrying a model default WITHOUT
``blank=True`` is mechanically required on its ModelForm (the 7.1 trap) - the as-built
required sets (5 / 3 / 3) are pinned, and the identity fields on the pool form are optional
at field level even though the exactly-one-of rule means a bare POST still fails.

Determinism (L16): ``USE_TZ`` is True and ``TIME_ZONE`` is UTC; every date basis is
``timezone.localdate()`` through ``_resource_today()``, never ``datetime.date.today()``. No
network, no filesystem. Tests use the conftest FACTORIES (and the 7.1/7.2 factory functions
for foreign-tenant project/request/task rows), never the seeder, and never ``bulk_create``
(numbering lives in ``save()``).

Naming (mandatory): every test is ``test_resource_*`` and every module-level helper
``_resource_*`` / ``_RESOURCE_*``, so no other lane in this package can shadow either.

Scope: forms only. Models, views, urls and permissions belong to the other three lanes.
"""
import datetime
from decimal import Decimal

import pytest
from django import forms as django_forms
from django.core.exceptions import NON_FIELD_ERRORS

from apps.core.forms import TenantModelForm
from apps.projects.forms import (
    ResourceAllocationForm,
    ResourceProfileForm,
    ResourceTimeEntryForm,
    TenantUniqueMixin,
)
from apps.projects.forms._common import _reject_foreign
from apps.projects.models import ResourceAllocation, ResourceProfile, ResourceTimeEntry
from apps.projects.tests.conftest import (
    _planning_task,
    _projectinitiation_request,
    _resource_today,
)

pytestmark = pytest.mark.django_db


# ==================================================================================================
# Module-level helpers - all _resource_* / _RESOURCE_* for the same reason the tests are: Python
# binds the LAST module-level definition, so an unprefixed helper here would silently rebind a
# sibling lane's (L47). Record factories come from conftest, which OWNS them.
# ==================================================================================================

#: ``ResourceProfileForm.Meta.fields``, verbatim and in order - the exact 12. ``status`` stays
#: ON the form (the pool register's lens toggle); ``tenant`` / ``number`` and the stamps do not.
_RESOURCE_PROFILE_FIELDS = [
    "employee", "party", "resource_type", "default_role", "org_unit",
    "skill_summary", "weekly_capacity_hours", "utilization_target_pct",
    "available_from", "available_to", "status", "notes",
]

#: ``ResourceAllocationForm.Meta.fields``, verbatim and in order - the exact 13.
#: ``booking_status`` / ``substitute_of`` are verb-driven, ``requested_by`` is provenance.
_RESOURCE_ALLOCATION_FIELDS = [
    "project", "project_request", "project_task", "resource", "role_name",
    "skill_requirements", "allocation_unit", "hours_per_week", "pct_capacity",
    "total_hours", "start_date", "end_date", "notes",
]

#: ``ResourceTimeEntryForm.Meta.fields``, verbatim and in order - the exact 7. ``status``, the
#: approval stamps and ``decision_note`` are the verbs' alone.
_RESOURCE_TIME_ENTRY_FIELDS = [
    "resource", "project", "project_task", "entry_date", "hours", "task_description", "notes",
]

#: The AS-BUILT required sets. Beyond the obviously required columns, every field carrying a
#: model default without ``blank=True`` (``resource_type``, ``weekly_capacity_hours``,
#: ``utilization_target_pct``, ``status``, ``allocation_unit``) is mechanically required - the
#: 7.1 trap, pinned the same way. ``employee`` / ``party`` are OPTIONAL at field level; the
#: exactly-one-of rule is model ``clean()`` and surfaces as a NON-FIELD error.
_RESOURCE_PROFILE_REQUIRED = {
    "resource_type", "default_role", "weekly_capacity_hours", "utilization_target_pct", "status",
}

_RESOURCE_ALLOCATION_REQUIRED = {"role_name", "allocation_unit", "start_date"}

_RESOURCE_TIME_ENTRY_REQUIRED = {"resource", "entry_date", "hours"}

#: (unit value, its own magnitude field, its display label) - the three allocation units.
_RESOURCE_UNITS = (
    ("hours_per_week", "hours_per_week", "Hours per Week"),
    ("pct_capacity", "pct_capacity", "% of Capacity"),
    ("total_hours", "total_hours", "Total Hours"),
)

_RESOURCE_UNIT_VALUES = {"hours_per_week": "16.00", "pct_capacity": "50", "total_hours": "40.00"}


def _resource_profile_payload(**overrides):
    """A ``ResourceProfileForm`` POST with every required field filled - and NO identity.

    ``employee`` / ``party`` are deliberately blank so the exactly-one-of tests can add
    whichever identity (or none) the case needs; a bare payload fails on that guard alone.
    """
    payload = {
        "employee": "",
        "party": "",
        "resource_type": "internal",
        "default_role": "Data engineer",
        "org_unit": "",
        "skill_summary": "Python, Django",
        "weekly_capacity_hours": "40.00",
        "utilization_target_pct": "80",
        "available_from": "",
        "available_to": "",
        "status": "active",
        "notes": "",
    }
    payload.update(overrides)
    return payload


def _resource_allocation_payload(**overrides):
    """A ``ResourceAllocationForm`` POST: hours_per_week magnitude, a live window, NO anchor.

    The default payload attaches to nothing on purpose (the attach guard is one of the things
    under test); the caller passes ``project=`` / ``project_request=`` to make it valid.
    """
    today = _resource_today()
    payload = {
        "project": "",
        "project_request": "",
        "project_task": "",
        "resource": "",
        "role_name": "Backend developer",
        "skill_requirements": "",
        "allocation_unit": "hours_per_week",
        "hours_per_week": "16.00",
        "pct_capacity": "",
        "total_hours": "",
        "start_date": str(today),
        "end_date": str(today + datetime.timedelta(days=30)),
        "notes": "",
    }
    payload.update(overrides)
    return payload


def _resource_time_entry_payload(**overrides):
    """A ``ResourceTimeEntryForm`` POST - 6.00h today, nothing attached but the resource."""
    payload = {
        "resource": "",
        "project": "",
        "project_task": "",
        "entry_date": str(_resource_today()),
        "hours": "6.00",
        "task_description": "",
        "notes": "",
    }
    payload.update(overrides)
    return payload


def _resource_widen(form, *names):
    """Drop the tenant narrowing off named ``ModelChoiceField``s, in place.

    A narrowed ``<select>`` refuses a foreign pk as "Select a valid choice", which is a real
    control - but it proves the WIDGET was scoped, not that the boundary holds. Widening first
    is how a crafted POST that never went near the widget is simulated, so what answers is the
    second layer: ``_reject_foreign`` in each form's ``clean()``.
    """
    for name in names:
        field = form.fields[name]
        field.queryset = field.queryset.model._default_manager.all()
    return form


def _resource_pks(form, name):
    """The pks a ``ModelChoiceField`` dropdown currently offers."""
    return set(form.fields[name].queryset.values_list("pk", flat=True))


def _resource_foreign_employee(tenant):
    """An ``hrm.EmployeeProfile`` in the GIVEN tenant on its own person Party.

    conftest ships only a tenant A employee (``resource_employee_a``); the foreign-``employee``
    cases need a second workspace's one, and ``EmployeeProfile.party`` is a OneToOne so it
    cannot share a party with anyone.
    """
    from apps.core.models import Party
    from apps.hrm.models import EmployeeProfile
    party = Party.objects.create(tenant=tenant, kind="person", name="Globex employee")
    obj = EmployeeProfile(tenant=tenant, party=party)
    obj.save()
    return obj


# ==================================================================================================
# 1. The import surface and the class shape
# ==================================================================================================

def test_resource_forms_package_reexports_all_three_forms():
    """Views and the CRUD helpers import through the package root; a form added without its
    re-export line is an ImportError at runtime, never at edit time."""
    for form_class in (ResourceProfileForm, ResourceAllocationForm, ResourceTimeEntryForm):
        assert isinstance(form_class, type)


def test_resource_forms_package_reexports_the_shared_toolkit():
    """``TenantModelForm`` / ``TenantUniqueMixin`` / ``_reject_foreign`` are the shared toolkit."""
    assert issubclass(TenantModelForm, django_forms.ModelForm)
    assert isinstance(TenantUniqueMixin, type)
    assert callable(_reject_foreign)


def test_resource_forms_every_form_writes_the_model_it_claims():
    assert ResourceProfileForm.Meta.model is ResourceProfile
    assert ResourceAllocationForm.Meta.model is ResourceAllocation
    assert ResourceTimeEntryForm.Meta.model is ResourceTimeEntry


def test_resource_forms_mix_the_tenant_unique_mixin_in_first():
    """Mixin BEFORE ``TenantModelForm``: ``TenantUniqueMixin.__init__`` stamps
    ``instance.tenant`` so the model ``clean()`` guards (pool check, attach comparison) read a
    real tenant before ``full_clean()`` runs."""
    for form_class in (ResourceProfileForm, ResourceAllocationForm, ResourceTimeEntryForm):
        mro = form_class.__mro__
        assert mro.index(TenantUniqueMixin) < mro.index(TenantModelForm), form_class.__name__


def test_resource_forms_the_constructor_takes_tenant_as_a_keyword(resource_tenant):
    """``Form(data=None, *, tenant=...)`` - every view builds them this way."""
    for form_class in (ResourceProfileForm, ResourceAllocationForm, ResourceTimeEntryForm):
        form = form_class(tenant=resource_tenant)
        assert form.tenant is resource_tenant, form_class.__name__


def test_resource_forms_edit_mode_offers_the_same_fields_as_create(
        resource_tenant, resource_profile_internal, resource_allocation_named_soft,
        resource_entry_draft):
    """An edit form that grew a field is the same hole as a create form that did."""
    pairs = (
        (ResourceProfileForm, resource_profile_internal),
        (ResourceAllocationForm, resource_allocation_named_soft),
        (ResourceTimeEntryForm, resource_entry_draft),
    )
    for form_class, instance in pairs:
        create = list(form_class(tenant=resource_tenant).fields)
        edit = list(form_class(instance=instance, tenant=resource_tenant).fields)
        assert create == edit, form_class.__name__


# ==================================================================================================
# 2. ResourceProfileForm - the field list, required set, choices and the status lens
# ==================================================================================================

def test_resource_profile_form_offers_exactly_the_twelve_fields(resource_tenant):
    """``Meta.fields`` is the exact 12-list in order (so ``tenant`` / ``number`` are offered to
    nobody), and ``status`` IS among them - active/inactive is a lens toggle, not governance."""
    form = ResourceProfileForm(tenant=resource_tenant)
    assert ResourceProfileForm.Meta.fields == _RESOURCE_PROFILE_FIELDS
    assert list(form.fields) == _RESOURCE_PROFILE_FIELDS
    assert len(form.fields) == 12
    for absent in ("tenant", "number", "created_at", "updated_at"):
        assert absent not in form.fields, absent


def test_resource_profile_form_requires_the_pinned_five(resource_tenant):
    """Five required: the three defaulted-without-blank columns plus ``default_role`` and
    ``status``. ``employee`` / ``party`` are optional at FIELD level - the exactly-one-of rule
    is model ``clean()`` and answers as a NON-FIELD error, even on a bare POST."""
    form = ResourceProfileForm(tenant=resource_tenant)
    required = {name for name, field in form.fields.items() if field.required}
    assert required == _RESOURCE_PROFILE_REQUIRED

    empty = ResourceProfileForm({}, tenant=resource_tenant)
    assert not empty.is_valid()
    assert _RESOURCE_PROFILE_REQUIRED <= set(empty.errors)
    assert NON_FIELD_ERRORS in empty.errors


def test_resource_profile_form_offers_the_model_choices(resource_tenant):
    """The dropdowns a user sees ARE the model's CHOICES (plus the blank option), so a value
    the model would refuse is never offered."""
    form = ResourceProfileForm(tenant=resource_tenant)
    for name in ("resource_type", "status"):
        offered = [value for value, _label in form.fields[name].choices if value != ""]
        expected = [value for value, _label in ResourceProfile._meta.get_field(name).choices]
        assert offered == expected, name


def test_resource_profile_form_scopes_identity_and_team_dropdowns(
        resource_tenant, resource_tenant_b, resource_employee_a, resource_party_a,
        resource_org_unit_a, resource_party_b, resource_org_unit_b):
    """All three ``ModelChoiceField``s (employee, party, org_unit) are narrowed to the form's
    tenant - a foreign workspace's row is never offered."""
    foreign_employee = _resource_foreign_employee(resource_tenant_b)
    form = ResourceProfileForm(tenant=resource_tenant)
    expected = {
        "employee": (resource_employee_a, foreign_employee),
        "party": (resource_party_a, resource_party_b),
        "org_unit": (resource_org_unit_a, resource_org_unit_b),
    }
    for name, (mine, theirs) in expected.items():
        pks = _resource_pks(form, name)
        assert mine.pk in pks, name
        assert theirs.pk not in pks, name


def test_resource_profile_form_rejects_every_cross_tenant_fk(
        resource_tenant, resource_tenant_b, resource_party_b, resource_org_unit_b):
    """A crafted POST carrying tenant B pks in an otherwise valid tenant A form. The queryset
    narrowing answers FIRST, so the assertion is "this field has an error" - never the wording."""
    foreign_employee = _resource_foreign_employee(resource_tenant_b)
    form = ResourceProfileForm(
        _resource_profile_payload(
            employee=str(foreign_employee.pk),
            party=str(resource_party_b.pk),
            org_unit=str(resource_org_unit_b.pk)),
        tenant=resource_tenant)
    assert not form.is_valid()
    for name in ("employee", "party", "org_unit"):
        assert name in form.errors, name
    assert ResourceProfile.objects.count() == 0


def test_resource_profile_form_reject_foreign_backstops_a_widened_queryset(
        resource_tenant, resource_tenant_b, resource_party_b, resource_org_unit_b):
    """The SECOND layer, reached by widening the querysets first - the shape a POST that never
    went near the widget actually takes. Here ``_reject_foreign``'s own wording is what answers."""
    foreign_employee = _resource_foreign_employee(resource_tenant_b)
    form = ResourceProfileForm(
        _resource_profile_payload(
            employee=str(foreign_employee.pk),
            party=str(resource_party_b.pk),
            org_unit=str(resource_org_unit_b.pk)),
        tenant=resource_tenant)
    _resource_widen(form, "employee", "party", "org_unit")
    assert not form.is_valid()
    for name in ("employee", "party", "org_unit"):
        assert form.errors[name] == ["That record belongs to another workspace."], name


def test_resource_profile_form_refuses_both_identities(
        resource_tenant, resource_employee_a, resource_party_a):
    """The model's exactly-one-of guard surfacing through the form as a NON-FIELD error - a row
    with both identities double-counts one person's capacity."""
    form = ResourceProfileForm(
        _resource_profile_payload(
            employee=str(resource_employee_a.pk), party=str(resource_party_a.pk)),
        tenant=resource_tenant)
    assert not form.is_valid()
    assert form.non_field_errors() == [
        "Choose an employee or an external party — exactly one of the two."]
    assert ResourceProfile.objects.count() == 0


def test_resource_profile_form_refuses_neither_identity(resource_tenant):
    """And a row identifying nobody is bad in the other direction - same non-field answer."""
    form = ResourceProfileForm(_resource_profile_payload(), tenant=resource_tenant)
    assert not form.is_valid()
    assert form.non_field_errors() == [
        "Choose an employee or an external party — exactly one of the two."]
    assert ResourceProfile.objects.count() == 0


def test_resource_profile_form_refuses_a_second_pool_row_for_one_employee(
        resource_tenant, resource_profile_internal, resource_employee_a):
    """The one-row-per-employee pool check is deliberately a clean() guard, not a constraint -
    the form is where the tenant sees it, keyed on ``employee``."""
    form = ResourceProfileForm(
        _resource_profile_payload(employee=str(resource_employee_a.pk)),
        tenant=resource_tenant)
    assert not form.is_valid()
    assert form.errors["employee"] == [
        "This employee is already in this tenant's resource pool."]
    assert ResourceProfile.objects.count() == 1


def test_resource_profile_edit_does_not_trip_its_own_pool_check(
        resource_tenant, resource_profile_internal, resource_employee_a):
    """``clean()`` excludes ``self.pk`` - otherwise no pool row could ever be edited."""
    form = ResourceProfileForm(
        _resource_profile_payload(
            employee=str(resource_employee_a.pk),
            org_unit="",
            default_role="Senior data engineer",
            notes="Updated skills"),
        instance=resource_profile_internal, tenant=resource_tenant)
    assert form.is_valid(), form.errors
    obj = form.save()
    obj.refresh_from_db()
    assert obj.pk == resource_profile_internal.pk
    assert obj.default_role == "Senior data engineer"
    assert ResourceProfile.objects.count() == 1


def test_resource_profile_form_saves_the_contractor_shape(resource_tenant, resource_party_a):
    """The happy path: a valid POST saves a tenant-stamped, numbered, party-keyed row holding
    every cleaned value."""
    today = _resource_today()
    form = ResourceProfileForm(
        _resource_profile_payload(
            resource_type="contractor",
            party=str(resource_party_a.pk),
            skill_summary="Playwright, pytest",
            available_from=str(today - datetime.timedelta(days=1)),
            available_to=str(today + datetime.timedelta(days=60))),
        tenant=resource_tenant)
    assert form.is_valid(), form.errors
    obj = form.save()
    obj.refresh_from_db()

    assert obj.tenant_id == resource_tenant.pk
    assert obj.number.startswith("RSP-")
    assert obj.party_id == resource_party_a.pk
    assert obj.employee_id is None
    assert obj.resource_type == "contractor"
    assert obj.default_role == "Data engineer"
    assert obj.skill_summary == "Playwright, pytest"
    assert obj.weekly_capacity_hours == Decimal("40.00")
    assert obj.utilization_target_pct == 80
    assert obj.available_from == today - datetime.timedelta(days=1)
    assert obj.available_to == today + datetime.timedelta(days=60)
    assert obj.status == "active"


def test_resource_profile_status_is_a_lens_toggle_not_governance(
        resource_tenant, resource_party_a, resource_profile_contractor):
    """``status`` is deliberately ON the form - unlike the booking status on
    ``ResourceAllocation``, no verb owns it: a create POST can open the row inactive and an
    edit POST can flip it back."""
    form = ResourceProfileForm(
        _resource_profile_payload(party=str(resource_party_a.pk), status="inactive"),
        tenant=resource_tenant)
    assert form.is_valid(), form.errors
    assert form.save().status == "inactive"

    edit = ResourceProfileForm(
        _resource_profile_payload(party=str(resource_profile_contractor.party_id),
                                  status="active"),
        instance=resource_profile_contractor, tenant=resource_tenant)
    assert edit.is_valid(), edit.errors
    saved = edit.save()
    saved.refresh_from_db()
    assert saved.status == "active"


# ==================================================================================================
# 3. ResourceProfileForm - numeric hardening (validators surface as FIELD errors, never a 500)
# ==================================================================================================

@pytest.mark.parametrize("bad,message", [
    ("123456", "Ensure that there are no more than 4 digits before the decimal point."),
    ("1234567", "Ensure that there are no more than 6 digits in total."),
    ("-1", "Ensure this value is greater than or equal to 0."),
])
def test_resource_profile_a_bad_weekly_capacity_is_a_field_error(resource_tenant, bad, message):
    """``weekly_capacity_hours`` is DecimalField(6, 2) floored at 0: over-max whole digits, over
    max total digits and negatives are friendly field errors (the form field carries Django's
    ``DecimalValidator``; the MinValue surfaces through the model clean_fields pass)."""
    form = ResourceProfileForm(
        _resource_profile_payload(weekly_capacity_hours=bad), tenant=resource_tenant)
    assert not form.is_valid()
    assert form.errors["weekly_capacity_hours"] == [message]
    assert ResourceProfile.objects.count() == 0


@pytest.mark.parametrize("bad,message", [
    ("0", "Ensure this value is greater than or equal to 1."),
    ("101", "Ensure this value is less than or equal to 100."),
])
def test_resource_profile_utilization_target_is_bounded(resource_tenant, bad, message):
    form = ResourceProfileForm(
        _resource_profile_payload(utilization_target_pct=bad), tenant=resource_tenant)
    assert not form.is_valid()
    assert form.errors["utilization_target_pct"] == [message]


def test_resource_profile_numeric_boundaries_are_accepted(resource_tenant, resource_party_a):
    """The floor of every scale is a valid row, not an off-by-one - 0h capacity at 1% target."""
    form = ResourceProfileForm(
        _resource_profile_payload(
            party=str(resource_party_a.pk),
            weekly_capacity_hours="0",
            utilization_target_pct="1"),
        tenant=resource_tenant)
    assert form.is_valid(), form.errors
    obj = form.save()
    obj.refresh_from_db()
    assert obj.weekly_capacity_hours == Decimal("0.00")
    assert obj.utilization_target_pct == 1


# ==================================================================================================
# 4. ResourceAllocationForm - the field list, required set, scoping and the I7 join
# ==================================================================================================

def test_resource_allocation_form_offers_exactly_the_thirteen_fields(resource_tenant):
    """``Meta.fields`` is the exact 13-list in order. ``booking_status`` / ``substitute_of`` /
    ``requested_by`` are the verbs' and provenance's - a POST that could name them would walk
    past every gate the verbs sit behind."""
    form = ResourceAllocationForm(tenant=resource_tenant)
    assert ResourceAllocationForm.Meta.fields == _RESOURCE_ALLOCATION_FIELDS
    assert list(form.fields) == _RESOURCE_ALLOCATION_FIELDS
    assert len(form.fields) == 13
    for absent in ("tenant", "number", "booking_status", "substitute_of", "requested_by",
                   "created_at", "updated_at"):
        assert absent not in form.fields, absent


def test_resource_allocation_form_requires_the_pinned_three(resource_tenant):
    """Three required fields; ``allocation_unit`` is required despite its model default (no
    ``blank=True`` - the 7.1 trap). A bare POST also trips the attach guard as a non-field
    error, because the model's clean runs even on an empty POST."""
    form = ResourceAllocationForm(tenant=resource_tenant)
    required = {name for name, field in form.fields.items() if field.required}
    assert required == _RESOURCE_ALLOCATION_REQUIRED

    empty = ResourceAllocationForm({}, tenant=resource_tenant)
    assert not empty.is_valid()
    assert _RESOURCE_ALLOCATION_REQUIRED <= set(empty.errors)
    assert NON_FIELD_ERRORS in empty.errors


def test_resource_allocation_form_scopes_its_four_dropdowns(
        resource_tenant, resource_tenant_b, resource_project, resource_request,
        resource_project_b, resource_profile_internal, resource_profile_b):
    """Every tenant-stamped FK dropdown (project, project_request, project_task, resource) is
    narrowed to the form's tenant."""
    own_task = _planning_task(resource_tenant, resource_project)
    foreign_request = _projectinitiation_request(resource_tenant_b)
    foreign_task = _planning_task(resource_tenant_b, resource_project_b)
    form = ResourceAllocationForm(tenant=resource_tenant)
    expected = {
        "project": (resource_project, resource_project_b),
        "project_request": (resource_request, foreign_request),
        "project_task": (own_task, foreign_task),
        "resource": (resource_profile_internal, resource_profile_b),
    }
    for name, (mine, theirs) in expected.items():
        pks = _resource_pks(form, name)
        assert mine.pk in pks, name
        assert theirs.pk not in pks, name


def test_resource_allocation_form_rejects_every_cross_tenant_fk(
        resource_tenant, resource_tenant_b, resource_project_b, resource_profile_b):
    """A crafted POST carrying tenant B pks: the narrowing answers first - the field HAS an
    error, and the row is never saved."""
    foreign_request = _projectinitiation_request(resource_tenant_b)
    foreign_task = _planning_task(resource_tenant_b, resource_project_b)
    form = ResourceAllocationForm(
        _resource_allocation_payload(
            project=str(resource_project_b.pk),
            project_request=str(foreign_request.pk),
            project_task=str(foreign_task.pk),
            resource=str(resource_profile_b.pk)),
        tenant=resource_tenant)
    assert not form.is_valid()
    for name in ("project", "project_request", "project_task", "resource"):
        assert name in form.errors, name
    assert ResourceAllocation.objects.count() == 0


def test_resource_allocation_form_reject_foreign_backstops_a_widened_queryset(
        resource_tenant, resource_tenant_b, resource_project_b, resource_profile_b):
    """The SECOND layer, reached by widening the querysets first: ``_reject_foreign``'s own
    wording answers for each of the four re-checked FKs."""
    foreign_request = _projectinitiation_request(resource_tenant_b)
    foreign_task = _planning_task(resource_tenant_b, resource_project_b)
    form = ResourceAllocationForm(
        _resource_allocation_payload(
            project=str(resource_project_b.pk),
            project_request=str(foreign_request.pk),
            project_task=str(foreign_task.pk),
            resource=str(resource_profile_b.pk)),
        tenant=resource_tenant)
    _resource_widen(form, "project", "project_request", "project_task", "resource")
    assert not form.is_valid()
    for name in ("project", "project_request", "project_task", "resource"):
        assert form.errors[name] == ["That record belongs to another workspace."], name


def test_resource_allocation_form_select_relateds_the_resource_name_walk(resource_tenant,
                                                                         resource_profile_internal):
    """The fixer-era I7 join: the resource dropdown's queryset carries
    ``select_related("employee__party", "party")`` so ``ResourceProfile.name`` - which walks
    employee -> party - does not pay two queries per pool row in the option labels. The
    tenant narrowing survives the re-assignment."""
    form = ResourceAllocationForm(tenant=resource_tenant)
    related = form.fields["resource"].queryset.query.select_related
    assert related, "the resource dropdown lost its select_related"
    assert related.get("employee", {}).get("party") == {} and "party" in related, related
    assert resource_profile_internal.pk in _resource_pks(form, "resource")


# ==================================================================================================
# 5. ResourceAllocationForm - the model clean() guards through the form
# ==================================================================================================

def test_resource_allocation_form_surfaces_the_attach_guard(resource_tenant):
    """A booking attached to neither a project nor a request is unreportable - the model's
    clean() answers as a NON-FIELD error through the form."""
    form = ResourceAllocationForm(_resource_allocation_payload(), tenant=resource_tenant)
    assert not form.is_valid()
    assert form.non_field_errors() == [
        "Attach the allocation to a project or a project request."]
    assert ResourceAllocation.objects.count() == 0


def test_resource_allocation_form_accepts_a_request_as_the_anchor(resource_tenant,
                                                                  resource_request):
    """Exactly-one-of, not at-least-one-of-nothing: a request-linked placeholder is a valid
    booking (the pipeline-demand shape), and the form saves it verb-driven-state first."""
    form = ResourceAllocationForm(
        _resource_allocation_payload(project_request=str(resource_request.pk)),
        tenant=resource_tenant)
    assert form.is_valid(), form.errors
    obj = form.save()
    obj.refresh_from_db()
    assert obj.project_request_id == resource_request.pk
    assert obj.project_id is None
    assert obj.booking_status == "requested"


def test_resource_allocation_form_refuses_an_end_before_start(resource_tenant, resource_project):
    form = ResourceAllocationForm(
        _resource_allocation_payload(
            project=str(resource_project.pk),
            start_date=str(_resource_today() + datetime.timedelta(days=10)),
            end_date=str(_resource_today() + datetime.timedelta(days=9))),
        tenant=resource_tenant)
    assert not form.is_valid()
    assert form.errors["end_date"] == ["End date cannot precede start date."]
    assert ResourceAllocation.objects.count() == 0


def test_resource_allocation_form_window_edges_are_accepted(resource_tenant, resource_project):
    """Same-day windows save, and an empty end date saves as NULL = ongoing."""
    today = _resource_today()
    same = ResourceAllocationForm(
        _resource_allocation_payload(
            project=str(resource_project.pk), start_date=str(today), end_date=str(today)),
        tenant=resource_tenant)
    assert same.is_valid(), same.errors
    assert same.save().end_date == today

    ongoing = ResourceAllocationForm(
        _resource_allocation_payload(
            project=str(resource_project.pk), start_date=str(today), end_date=""),
        tenant=resource_tenant)
    assert ongoing.is_valid(), ongoing.errors
    assert ongoing.save().end_date is None


@pytest.mark.parametrize("unit,magnitude_field,label", _RESOURCE_UNITS)
def test_resource_allocation_form_requires_the_units_own_magnitude(
        resource_tenant, resource_project, unit, magnitude_field, label):
    """Each of the three units: leaving the unit's OWN magnitude blank is a field error keyed
    on that magnitude - "Required when the allocation unit is <label>."""
    payload = _resource_allocation_payload(
        project=str(resource_project.pk), allocation_unit=unit,
        hours_per_week="", pct_capacity="", total_hours="")
    form = ResourceAllocationForm(payload, tenant=resource_tenant)
    assert not form.is_valid()
    assert form.errors[magnitude_field] == [
        f"Required when the allocation unit is {label}."]
    assert ResourceAllocation.objects.count() == 0


@pytest.mark.parametrize("unit,other_field,other_value,label", [
    ("hours_per_week", "pct_capacity", "50", "Hours per Week"),
    ("pct_capacity", "total_hours", "40.00", "% of Capacity"),
    ("total_hours", "hours_per_week", "16.00", "Total Hours"),
])
def test_resource_allocation_form_refuses_a_second_magnitude(
        resource_tenant, resource_project, unit, other_field, other_value, label):
    """Each of the three units: a SECOND magnitude beside the unit's own is refused, keyed on
    the field that must have stayed blank - "Leave blank — the allocation unit is <label>."""
    magnitudes = {"hours_per_week": "", "pct_capacity": "", "total_hours": ""}
    magnitudes["hours_per_week" if unit == "hours_per_week"
               else "pct_capacity" if unit == "pct_capacity" else "total_hours"] = \
        _RESOURCE_UNIT_VALUES[unit]
    magnitudes[other_field] = other_value
    form = ResourceAllocationForm(
        _resource_allocation_payload(
            project=str(resource_project.pk), allocation_unit=unit, **magnitudes),
        tenant=resource_tenant)
    assert not form.is_valid()
    assert form.errors[other_field] == [f"Leave blank — the allocation unit is {label}."]
    assert ResourceAllocation.objects.count() == 0


@pytest.mark.parametrize("unit,magnitude_field,saved_value", [
    ("hours_per_week", "hours_per_week", Decimal("16.00")),
    ("pct_capacity", "pct_capacity", 50),
    ("total_hours", "total_hours", Decimal("40.00")),
])
def test_resource_allocation_form_saves_each_units_own_magnitude(
        resource_tenant, resource_project, resource_profile_internal, unit, magnitude_field,
        saved_value):
    """The happy magnitude per unit: the unit's own number sticks, the other two stay NULL,
    the tenant and the verb-driven status are the system's."""
    magnitudes = {"hours_per_week": "", "pct_capacity": "", "total_hours": ""}
    magnitudes[magnitude_field] = _RESOURCE_UNIT_VALUES[unit]
    form = ResourceAllocationForm(
        _resource_allocation_payload(
            project=str(resource_project.pk),
            resource=str(resource_profile_internal.pk),
            allocation_unit=unit, **magnitudes),
        tenant=resource_tenant)
    assert form.is_valid(), form.errors
    obj = form.save()
    obj.refresh_from_db()

    assert obj.tenant_id == resource_tenant.pk
    assert obj.number.startswith("RAL-")
    assert obj.allocation_unit == unit
    assert getattr(obj, magnitude_field) == saved_value
    for other_field, _own, _label in _RESOURCE_UNITS:
        if other_field != magnitude_field:
            assert getattr(obj, other_field) is None
    assert obj.booking_status == "requested"


def test_resource_allocation_form_ignores_every_smuggled_excluded_value(
        resource_tenant, resource_tenant_b, resource_admin, resource_project):
    """L20/L22: a create POST naming the excluded columns still saves a ``requested`` tenant A
    row with a freshly minted number, no substitute chain and no provenance stamp."""
    smuggled = _resource_allocation_payload(
        project=str(resource_project.pk),
        tenant=str(resource_tenant_b.pk),
        number="RAL-99999",
        booking_status="firm",
        substitute_of="999999",
        requested_by=str(resource_admin.pk),
    )
    form = ResourceAllocationForm(smuggled, tenant=resource_tenant)
    assert form.is_valid(), form.errors
    obj = form.save()
    obj.refresh_from_db()

    assert obj.tenant_id == resource_tenant.pk
    assert obj.number.startswith("RAL-") and obj.number != "RAL-99999"
    assert obj.booking_status == "requested"
    assert obj.substitute_of_id is None
    assert obj.requested_by_id is None


def test_resource_allocation_edit_cannot_move_the_booking_status(
        resource_tenant, resource_admin, resource_allocation_named_soft,
        resource_allocation_successor):
    """The edit half of the same control: a soft booking stays soft when the edit POST carries
    ``booking_status=cancelled`` (or a substitute chain, or provenance) - only the verbs move
    it, and the successor pointer stays unwritten."""
    obj = resource_allocation_named_soft
    payload = _resource_allocation_payload(
        project=str(obj.project_id),
        resource=str(obj.resource_id),
        role_name=obj.role_name,
        skill_requirements=obj.skill_requirements,
        hours_per_week="16.00",
        start_date=str(obj.start_date),
        end_date=str(obj.end_date),
        booking_status="cancelled",
        substitute_of=str(resource_allocation_successor.pk),
        requested_by="999999",
    )
    form = ResourceAllocationForm(payload, instance=obj, tenant=resource_tenant)
    assert form.is_valid(), form.errors
    saved = form.save()
    saved.refresh_from_db()

    assert saved.booking_status == "soft"
    assert saved.substitute_of_id is None
    assert saved.requested_by_id == resource_admin.pk


def test_resource_allocation_form_help_text_pins_the_one_magnitude_rule(resource_tenant):
    """The pinned Meta.help_texts entry that teaches the one-magnitude rule in the UI."""
    form = ResourceAllocationForm(tenant=resource_tenant)
    assert form.fields["allocation_unit"].help_text == (
        "Set only the magnitude matching the allocation unit — the others stay blank.")


# ==================================================================================================
# 6. ResourceTimeEntryForm - fields, scoping, the I7 join and the hours validator
# ==================================================================================================

def test_resource_time_entry_form_offers_exactly_the_seven_fields(resource_tenant):
    """``Meta.fields`` is the exact 7-list in order. ``status`` and every approval stamp plus
    ``decision_note`` are the verbs' alone - the form cannot rewind or forge an approval."""
    form = ResourceTimeEntryForm(tenant=resource_tenant)
    assert ResourceTimeEntryForm.Meta.fields == _RESOURCE_TIME_ENTRY_FIELDS
    assert list(form.fields) == _RESOURCE_TIME_ENTRY_FIELDS
    assert len(form.fields) == 7
    for absent in ("tenant", "number", "status", "submitted_at", "approved_at",
                   "approved_by", "decision_note"):
        assert absent not in form.fields, absent


def test_resource_time_entry_form_requires_the_pinned_three(resource_tenant):
    """Exactly three required fields and NOTHING else on an empty POST - the model has no
    clean() beyond the validators, so no non-field error can appear."""
    form = ResourceTimeEntryForm(tenant=resource_tenant)
    required = {name for name, field in form.fields.items() if field.required}
    assert required == _RESOURCE_TIME_ENTRY_REQUIRED

    empty = ResourceTimeEntryForm({}, tenant=resource_tenant)
    assert not empty.is_valid()
    assert set(empty.errors) == _RESOURCE_TIME_ENTRY_REQUIRED


def test_resource_time_entry_form_scopes_its_three_dropdowns(
        resource_tenant, resource_tenant_b, resource_project, resource_project_b,
        resource_profile_internal, resource_profile_b):
    own_task = _planning_task(resource_tenant, resource_project)
    foreign_task = _planning_task(resource_tenant_b, resource_project_b)
    form = ResourceTimeEntryForm(tenant=resource_tenant)
    expected = {
        "resource": (resource_profile_internal, resource_profile_b),
        "project": (resource_project, resource_project_b),
        "project_task": (own_task, foreign_task),
    }
    for name, (mine, theirs) in expected.items():
        pks = _resource_pks(form, name)
        assert mine.pk in pks, name
        assert theirs.pk not in pks, name


def test_resource_time_entry_form_rejects_every_cross_tenant_fk(
        resource_tenant, resource_tenant_b, resource_project_b, resource_profile_b):
    """A crafted POST carrying tenant B pks: the narrowing answers first - the field HAS an
    error, and the row is never saved."""
    foreign_task = _planning_task(resource_tenant_b, resource_project_b)
    form = ResourceTimeEntryForm(
        _resource_time_entry_payload(
            resource=str(resource_profile_b.pk),
            project=str(resource_project_b.pk),
            project_task=str(foreign_task.pk)),
        tenant=resource_tenant)
    assert not form.is_valid()
    for name in ("resource", "project", "project_task"):
        assert name in form.errors, name
    assert ResourceTimeEntry.objects.count() == 0


def test_resource_time_entry_form_reject_foreign_backstops_a_widened_queryset(
        resource_tenant, resource_tenant_b, resource_project_b, resource_profile_b):
    """The SECOND layer, reached by widening the querysets first: ``_reject_foreign``'s own
    wording answers for each of the three re-checked FKs."""
    foreign_task = _planning_task(resource_tenant_b, resource_project_b)
    form = ResourceTimeEntryForm(
        _resource_time_entry_payload(
            resource=str(resource_profile_b.pk),
            project=str(resource_project_b.pk),
            project_task=str(foreign_task.pk)),
        tenant=resource_tenant)
    _resource_widen(form, "resource", "project", "project_task")
    assert not form.is_valid()
    for name in ("resource", "project", "project_task"):
        assert form.errors[name] == ["That record belongs to another workspace."], name


def test_resource_time_entry_form_select_relateds_the_resource_name_walk(
        resource_tenant, resource_profile_internal):
    """The fixer-era I7 join on the second form that renders the resource dropdown - same
    ``select_related("employee__party", "party")``, same tenant-narrowed queryset."""
    form = ResourceTimeEntryForm(tenant=resource_tenant)
    related = form.fields["resource"].queryset.query.select_related
    assert related, "the resource dropdown lost its select_related"
    assert related.get("employee", {}).get("party") == {} and "party" in related, related
    assert resource_profile_internal.pk in _resource_pks(form, "resource")


@pytest.mark.parametrize("bad", ["0", "-1"])
def test_resource_time_entry_hours_below_the_floor_is_a_field_error(
        resource_tenant, resource_profile_internal, bad):
    """0.01 is the smallest loggable unit - the MinValueValidator answers through the form as
    a field error, and nothing saves."""
    form = ResourceTimeEntryForm(
        _resource_time_entry_payload(
            resource=str(resource_profile_internal.pk), hours=bad),
        tenant=resource_tenant)
    assert not form.is_valid()
    assert form.errors["hours"] == ["Ensure this value is greater than or equal to 0.01."]
    assert ResourceTimeEntry.objects.count() == 0


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-Infinity", "abc"])
def test_resource_time_entry_a_non_numeric_hours_is_a_field_error(
        resource_tenant, resource_profile_internal, bad):
    """``NaN`` and ``Infinity`` are the ones that used to 500 elsewhere: the DecimalField
    answers "Enter a number." before anything downstream can choke on them."""
    form = ResourceTimeEntryForm(
        _resource_time_entry_payload(
            resource=str(resource_profile_internal.pk), hours=bad),
        tenant=resource_tenant)
    assert not form.is_valid()
    assert form.errors["hours"] == ["Enter a number."]
    assert ResourceTimeEntry.objects.count() == 0


def test_resource_time_entry_the_smallest_loggable_unit_is_accepted(
        resource_tenant, resource_profile_internal):
    """The floor itself saves - the guard bounds the field, it does not narrow it."""
    form = ResourceTimeEntryForm(
        _resource_time_entry_payload(
            resource=str(resource_profile_internal.pk), hours="0.01"),
        tenant=resource_tenant)
    assert form.is_valid(), form.errors
    assert form.save().hours == Decimal("0.01")


def test_resource_time_entry_form_saves_the_draft_shape(
        resource_tenant, resource_profile_internal, resource_project):
    """The happy path: a valid POST saves a tenant-stamped, numbered, DRAFT day-row holding
    every cleaned value."""
    today = _resource_today()
    form = ResourceTimeEntryForm(
        _resource_time_entry_payload(
            resource=str(resource_profile_internal.pk),
            project=str(resource_project.pk),
            task_description="Pipelines"),
        tenant=resource_tenant)
    assert form.is_valid(), form.errors
    obj = form.save()
    obj.refresh_from_db()

    assert obj.tenant_id == resource_tenant.pk
    assert obj.number.startswith("RTE-")
    assert obj.resource_id == resource_profile_internal.pk
    assert obj.project_id == resource_project.pk
    assert obj.project_task_id is None
    assert obj.entry_date == today
    assert obj.hours == Decimal("6.00")
    assert obj.task_description == "Pipelines"
    assert obj.status == "draft"


def test_resource_time_entry_form_ignores_the_approval_stamps(
        resource_tenant, resource_admin, resource_profile_internal, resource_project):
    """L20/L22 on the time-entry form: a create POST carrying the whole approval state still
    saves a stamp-less draft with a freshly minted number."""
    smuggled = _resource_time_entry_payload(
        resource=str(resource_profile_internal.pk),
        project=str(resource_project.pk),
        tenant="999999",
        number="RTE-99999",
        status="approved",
        submitted_at="2020-01-01T00:00",
        approved_at="2020-01-01T00:00",
        approved_by=str(resource_admin.pk),
        decision_note="forged approval",
    )
    form = ResourceTimeEntryForm(smuggled, tenant=resource_tenant)
    assert form.is_valid(), form.errors
    obj = form.save()
    obj.refresh_from_db()

    assert obj.tenant_id == resource_tenant.pk
    assert obj.number.startswith("RTE-") and obj.number != "RTE-99999"
    assert obj.status == "draft"
    assert obj.submitted_at is None and obj.approved_at is None
    assert obj.approved_by_id is None
    assert obj.decision_note == ""


def test_resource_time_entry_edit_cannot_forge_an_approval(
        resource_tenant, resource_admin, resource_entry_draft):
    """The edit half: an EDIT POST of a draft carrying ``status=approved`` and a full stamp set
    changes nothing - approved_by/approved_at stay empty and the row stays a draft."""
    obj = resource_entry_draft
    payload = _resource_time_entry_payload(
        resource=str(obj.resource_id),
        project=str(obj.project_id or ""),
        entry_date=str(obj.entry_date),
        hours="6.00",
        task_description=obj.task_description,
        status="approved",
        approved_by=str(resource_admin.pk),
        approved_at="2020-01-01T00:00",
        decision_note="forged approval",
    )
    form = ResourceTimeEntryForm(payload, instance=obj, tenant=resource_tenant)
    assert form.is_valid(), form.errors
    saved = form.save()
    saved.refresh_from_db()

    assert saved.status == "draft"
    assert saved.approved_by_id is None and saved.approved_at is None
    assert saved.decision_note == ""


def test_resource_time_entry_form_help_text_pins_positive_hours(resource_tenant):
    """The pinned Meta.help_texts entry that teaches the positive-only rule in the UI."""
    form = ResourceTimeEntryForm(tenant=resource_tenant)
    assert form.fields["hours"].help_text == "Hours logged this day — positive only."
