"""Projects 7.3 Resource Management - MODEL tests.

The model lane owns the claims the three registers would be worthless without - the numbering,
the pool/booking guards, the live-window truth table and the demand arithmetic:

* **``TenantNumbered``** mints ``RSP-/RAL-/RTE-00001`` once, per tenant, per MODEL. Two
  workspaces both read ``RSP-00001`` and neither collides; a second ``save()`` never re-numbers.
  ``crm.ResourceAllocation`` [RA-] is the 1.8 stand-in that also books people - this lane proves
  ``projects.ResourceAllocation``'s sequence is independent of it rather than "globally unique".
* **The pool guards are clean(), not constraints.** Exactly one of employee/party, and one pool
  row per employee per tenant - deliberately a ``clean()`` guard (MariaDB cannot enforce the
  conditional unique), so ``save()`` never runs it and every refusal here goes through
  ``full_clean()`` - the shape the forms see.
* **``is_live`` is the register's lens contract**: soft/firm AND the window covers
  ``timezone.localdate()`` - a soft PLACEHOLDER with a current window is live, which is
  load-bearing for the allocation register's "Live" badge and the ``?is_live=`` lens.
* **``planned_hours()`` is the demand arithmetic everything downstream sums.** Cancelled AND
  released rows count ZERO (a released row's successor already carries the demand - counting
  both would double it), completed rows do NOT short-circuit here (the board QUERIES exclude
  them, the method does not), a % of a placeholder's capacity is unknowable and counts ZERO, a
  null end clamps to the window end, and every figure goes through ``q2()``'s 2dp quantize. All
  arithmetic is ``Decimal`` - a float assertion here would pass for the wrong reason.
* **``week_key`` is the regroup key**: ``"{resource_id}:{iso_year}-W{iso_week:02d}"`` off
  ``entry_date.isocalendar()`` - one key = one person-week, ISO weeks (a Sunday can close the
  previous ISO year), and two people in the same week never share a group.
* **The approval stamps are model-layer non-editable**: ``submitted_at`` / ``approved_by`` /
  ``approved_at`` are written exactly once by the verbs. The approved/rejected edit+delete LOCK
  lives at the VIEW layer (``rte_edit``/``rte_delete`` refuse before crud) - deliberately no
  model test pins it; the verbs lane does.

Determinism (L16): ``USE_TZ`` is True, so every date basis here is ``timezone.localdate()`` via
``_resource_today()`` - the same basis ``is_live`` and ``planned_hours``' windows use.
``datetime.date.today()`` never appears, or the live-window assertions flake for the hours either
side of local midnight.

Naming (mandatory): every test is ``test_resource_*`` and every module-level helper
``_resource_*`` / ``_RESOURCE_*``, so no later lane of this package can shadow either.

Scope: models only. Forms, views, urls and permissions belong to the other three lanes.
"""
import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import NON_FIELD_ERRORS, FieldDoesNotExist, ValidationError
from django.db import IntegrityError, transaction

from apps.projects.models import (
    ZERO,
    ResourceAllocation,
    ResourceProfile,
    ResourceTimeEntry,
    TenantNumbered,
    TenantOwned,
    q2,
)
from apps.projects.tests.conftest import (
    _resource_allocation,
    _resource_entry,
    _resource_profile,
    _resource_today,
)

pytestmark = pytest.mark.django_db


# ==================================================================================================
# Local helpers - _resource_* for the same reason the tests are (Python binds the LAST module-level
# definition, so an unprefixed helper here would silently rebind a sibling lane's). Everything that
# builds a 7.3 row comes from the shared conftest factories; these only read or build UNSAVED
# shells for the clean()/property tests - save() never runs clean(), so the shell IS the shape.
# ==================================================================================================

#: U+00B7. Written as an escape so this file stays pure ASCII - the three models' ``__str__``
#: separator is a real middle dot and a mangled literal would make the comparison pass or fail
#: for the wrong reason on a differently-encoded checkout.
_RESOURCE_MIDDOT = "\u00b7"

#: The three 7.3 models, with the prefix each one mints.
_RESOURCE_MODELS = (
    (ResourceProfile, "RSP"),
    (ResourceAllocation, "RAL"),
    (ResourceTimeEntry, "RTE"),
)

#: The one magnitude value each allocation unit drives, keyed by field name - the clean() tests
#: build shells with any two of the three set.
_RESOURCE_MAGNITUDES = {
    "hours_per_week": Decimal("16.00"),
    "pct_capacity": 50,
    "total_hours": Decimal("40.00"),
}


def _resource_values(choices):
    """The (value, label) tuples of a CHOICES list, in declaration order - asserted verbatim."""
    return [(value, label) for value, label in choices]


def _resource_index_names(model):
    return {index.name for index in model._meta.indexes}


def _resource_non_editable(model):
    """The columns no ModelForm can offer - the model-layer half of the L20/L22 contract."""
    return {f.name for f in model._meta.fields if not f.editable}


def _resource_employee(tenant, name):
    """A saved ``hrm.EmployeeProfile`` on its own person Party (the OneToOne forbids sharing) -
    the same shape the conftest's ``resource_employee_a`` fixture builds, for the pool tests that
    need fresh identities."""
    from apps.core.models import Party
    from apps.hrm.models import EmployeeProfile
    party = Party.objects.create(tenant=tenant, kind="person", name=name)
    obj = EmployeeProfile(tenant=tenant, party=party)
    obj.save()
    return obj


def _resource_window(offsets):
    """``(win_start, win_end)`` from ``(start_offset, end_offset)`` days relative to today (L16)."""
    today = _resource_today()
    return (today + datetime.timedelta(days=offsets[0]),
            today + datetime.timedelta(days=offsets[1]))


def _resource_live_shell(start_offset, end_offset, status="soft",
                         hours_per_week=Decimal("16.00")):
    """An UNSAVED booking on a window relative to today. ``is_live`` / ``planned_hours`` read the
    instance only, so the shell never touches the database; ``end_offset=None`` is ongoing.
    Carries the 16h/wk default magnitude the shells' ``planned_hours`` math assumes - a
    hours_per_week booking without a magnitude would TypeError inside the proration."""
    start, end = _resource_window((start_offset, end_offset or 0))
    return ResourceAllocation(
        booking_status=status,
        allocation_unit="hours_per_week",
        hours_per_week=hours_per_week,
        start_date=start,
        end_date=end if end_offset is not None else None,
    )


def _resource_allocation_shell(tenant, **overrides):
    """An UNSAVED allocation in the factory's clean default shape (16h/wk over a live window,
    nothing attached, no second magnitude). ``clean()`` is what is under test and ``save()``
    never calls it - pass ``project=`` / ``project_request=`` for the happy paths."""
    start, end = _resource_window((-7, 35))
    fields = dict(
        tenant=tenant,
        role_name="Backend developer",
        allocation_unit="hours_per_week",
        hours_per_week=Decimal("16.00"),
        start_date=start,
        end_date=end,
        booking_status="soft",
    )
    fields.update(overrides)
    return ResourceAllocation(**fields)


# ==================================================================================================
# The package import surface
# ==================================================================================================

def test_resource_models_package_reexports_the_shared_toolkit():
    """``from apps.projects.models import ZERO`` must keep working - the views, the seeder and the
    peer lanes all import through the package root, and a missing re-export is an ImportError at
    runtime, never at edit time."""
    assert ZERO == Decimal("0")
    assert callable(q2)
    assert issubclass(TenantNumbered, TenantOwned)
    assert TenantOwned._meta.abstract and TenantNumbered._meta.abstract


def test_resource_models_every_model_inherits_the_numbered_base():
    for model, prefix in _RESOURCE_MODELS:
        assert issubclass(model, TenantNumbered), model.__name__
        assert model.NUMBER_PREFIX == prefix, model.__name__
        # The number is minted in save() and never operator-writable - the same base contract
        # every numbered app shares.
        field = model._meta.get_field("number")
        assert field.editable is False, model.__name__
        assert field.max_length == 20, model.__name__


# ==================================================================================================
# TenantNumbered - the per-tenant, per-model sequences
# ==================================================================================================

def test_resource_models_numbers_run_in_sequence(resource_tenant):
    """Three prefixes, three independent counters - creating a booking must not push the next
    pool row to RSP-00002."""
    profiles = [_resource_profile(resource_tenant) for _ in range(3)]
    allocation = _resource_allocation(resource_tenant)
    entry = _resource_entry(resource_tenant, profiles[0])
    assert [row.number for row in profiles] == ["RSP-00001", "RSP-00002", "RSP-00003"]
    assert allocation.number == "RAL-00001"
    assert entry.number == "RTE-00001"


def test_resource_models_numbers_do_not_collide_across_tenants(resource_tenant, resource_tenant_b):
    a = _resource_profile(resource_tenant)
    b = _resource_profile(resource_tenant_b)
    assert a.number == b.number == "RSP-00001"
    assert a.tenant_id != b.tenant_id


def test_resource_models_a_second_save_does_not_renumber(resource_tenant):
    profile = _resource_profile(resource_tenant)
    allocation = _resource_allocation(resource_tenant)
    entry = _resource_entry(resource_tenant, profile)
    minted = (profile.number, allocation.number, entry.number)
    profile.default_role = "Renamed after the fact"
    for row in (profile, allocation, entry):
        row.save()
        row.refresh_from_db()
    assert (profile.number, allocation.number, entry.number) == minted


def test_resource_models_a_number_is_unique_inside_one_tenant_and_free_in_another(
        resource_tenant, resource_tenant_b):
    first = _resource_profile(resource_tenant)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _resource_profile(resource_tenant, number=first.number)
    twin = _resource_profile(resource_tenant_b, number=first.number)
    assert twin.number == first.number
    assert ResourceProfile.objects.filter(number=first.number).count() == 2


def test_resource_allocation_numbering_is_independent_of_the_crm_stand_in(resource_tenant):
    """``crm.ResourceAllocation`` [RA-] is the 1.8 pre-spine stand-in that also books people.
    ``next_number`` scopes to ONE model's table, so both read their own 00001 in one workspace -
    a number is unique per (model, tenant), never globally."""
    from apps.crm.models import CrmProject
    from apps.crm.models import ResourceAllocation as CrmResourceAllocation
    crm_project = CrmProject.objects.create(tenant=resource_tenant, name="Delivery lens")
    crm_booking = CrmResourceAllocation.objects.create(
        tenant=resource_tenant, project=crm_project, start_date=_resource_today())
    ours = _resource_allocation(resource_tenant)
    assert CrmResourceAllocation.NUMBER_PREFIX == "RA"
    assert crm_booking.number == "RA-00001"
    assert ours.number == "RAL-00001"
    assert isinstance(ours, ResourceAllocation)


# ==================================================================================================
# Meta shapes - unique_together, indexes, ordering
# ==================================================================================================

def test_resource_models_unique_together_shapes_are_the_pinned_ones():
    for model, _prefix in _RESOURCE_MODELS:
        assert model._meta.unique_together == (("tenant", "number"),), model.__name__


def test_resource_models_index_names_are_the_as_built_sets():
    """The exact index names the migration ships - a rename is a pointless migration and a
    stray name here means the register's filters lost their covering index."""
    assert _resource_index_names(ResourceProfile) == {
        "rsp_tnt_rtype_idx", "rsp_tnt_status_idx", "rsp_tnt_employee_idx", "rsp_tnt_party_idx"}
    assert _resource_index_names(ResourceAllocation) == {
        "ral_tnt_resource_idx", "ral_tnt_project_idx", "ral_tnt_request_idx",
        "ral_tnt_status_idx", "ral_tnt_start_idx"}
    assert _resource_index_names(ResourceTimeEntry) == {
        "rte_tnt_res_date_idx", "rte_tnt_prj_date_idx", "rte_tnt_status_idx"}


def test_resource_models_meta_orderings_are_the_pinned_strings():
    assert ResourceProfile._meta.ordering == ["employee__party__name", "party__name", "id"]
    assert ResourceAllocation._meta.ordering == ["-start_date", "-id"]
    assert ResourceTimeEntry._meta.ordering == ["resource_id", "-entry_date", "-id"]


# ==================================================================================================
# ResourceProfile - vocabulary, defaults, name, __str__
# ==================================================================================================

def test_resource_profile_resource_type_choices_are_the_four_documented():
    assert _resource_values(ResourceProfile.RESOURCE_TYPE_CHOICES) == [
        ("internal", "Internal"), ("contractor", "Contractor"),
        ("freelancer", "Freelancer"), ("consultant", "Consultant")]
    field = ResourceProfile._meta.get_field("resource_type")
    assert field.max_length == 12
    assert max(len(value) for value, _label in ResourceProfile.RESOURCE_TYPE_CHOICES) \
        <= field.max_length


def test_resource_profile_status_choices_are_the_two_documented():
    assert _resource_values(ResourceProfile.STATUS_CHOICES) == [
        ("active", "Active"), ("inactive", "Inactive")]
    field = ResourceProfile._meta.get_field("status")
    assert field.max_length == 8
    assert max(len(value) for value, _label in ResourceProfile.STATUS_CHOICES) <= field.max_length


def test_resource_profile_defaults_are_the_documented_ones(resource_tenant):
    obj = ResourceProfile(tenant=resource_tenant, default_role="Bare minimum")
    obj.save()
    obj.refresh_from_db()
    assert obj.number == "RSP-00001"
    assert obj.employee_id is None and obj.party_id is None and obj.org_unit_id is None
    assert obj.resource_type == "internal"
    assert obj.weekly_capacity_hours == Decimal("40.00")
    assert obj.utilization_target_pct == 80
    assert obj.available_from is None and obj.available_to is None
    assert obj.status == "active"
    assert obj.skill_summary == "" and obj.notes == ""


def test_resource_profile_str_is_number_middot_name(resource_profile_contractor):
    obj = resource_profile_contractor
    assert str(obj) == f"{obj.number} {_RESOURCE_MIDDOT} {obj.name}"


def test_resource_profile_name_prefers_the_employee_party(resource_profile_internal):
    """``name`` is a property, never a column - a column would go stale the day the person's
    party is renamed."""
    with pytest.raises(FieldDoesNotExist):
        ResourceProfile._meta.get_field("name")
    assert isinstance(ResourceProfile.name, property)
    obj = resource_profile_internal
    assert obj.employee_id and obj.party_id is None
    assert obj.name == obj.employee.party.name


def test_resource_profile_name_falls_back_to_the_external_party(resource_profile_contractor):
    obj = resource_profile_contractor
    assert obj.employee_id is None and obj.party_id
    assert obj.name == obj.party.name


def test_resource_profile_name_falls_back_to_the_number():
    """A row that names nobody (which clean() refuses and save() tolerates) still renders - the
    admin changelist and the audit log call ``str()`` on half-built rows too."""
    shell = ResourceProfile(number="RSP-09999")
    assert shell.employee_id is None and shell.party_id is None
    assert shell.name == "RSP-09999"


def test_resource_profile_orders_same_kind_rows_alphabetically(resource_tenant):
    """The people-list ordering: party-keyed rows by the party's name, employee-keyed rows by the
    employee's party name. Cross-kind position (the NULL-employee rows first on SQLite/MariaDB)
    is a database artifact and is deliberately NOT pinned."""
    from apps.core.models import Party
    zulu = _resource_profile(resource_tenant, party=Party.objects.create(
        tenant=resource_tenant, kind="person", name="Zed Ortega"))
    alpha = _resource_profile(resource_tenant, party=Party.objects.create(
        tenant=resource_tenant, kind="person", name="Ada Quinn"))
    party_rows = ResourceProfile.objects.filter(tenant=resource_tenant, party__isnull=False)
    assert list(party_rows) == [alpha, zulu]

    nia = _resource_employee(resource_tenant, "Nia Fields")
    ben = _resource_employee(resource_tenant, "Ben Okafor")
    nia_row = _resource_profile(resource_tenant, employee=nia)
    ben_row = _resource_profile(resource_tenant, employee=ben)
    employee_rows = ResourceProfile.objects.filter(tenant=resource_tenant, employee__isnull=False)
    assert list(employee_rows) == [ben_row, nia_row]


def test_resource_profile_scale_validators_hold(resource_profile_internal):
    """utilization_target_pct is 1..100; weekly_capacity_hours floors at 0 - zero capacity is
    legal (a person on leave), a negative one is a typo."""
    obj = resource_profile_internal
    obj.utilization_target_pct = 0
    with pytest.raises(ValidationError) as excinfo:
        obj.full_clean()
    assert "utilization_target_pct" in excinfo.value.error_dict
    obj.utilization_target_pct = 101
    with pytest.raises(ValidationError) as excinfo:
        obj.full_clean()
    assert "utilization_target_pct" in excinfo.value.error_dict
    obj.utilization_target_pct = 80
    obj.weekly_capacity_hours = Decimal("-1.00")
    with pytest.raises(ValidationError) as excinfo:
        obj.full_clean()
    assert "weekly_capacity_hours" in excinfo.value.error_dict
    obj.weekly_capacity_hours = Decimal("0.00")
    assert obj.full_clean() is None


# ==================================================================================================
# ResourceProfile.clean() - the rules save() does not enforce
# ==================================================================================================

def test_resource_profile_clean_refuses_both_identities(resource_tenant, resource_employee_a,
                                                        resource_party_a):
    """A row with both double-counts one person's capacity - exactly the shape the register
    would sum twice on the capacity board."""
    shell = ResourceProfile(tenant=resource_tenant, employee=resource_employee_a,
                            party=resource_party_a, default_role="Doubled up")
    with pytest.raises(ValidationError) as excinfo:
        shell.full_clean()
    assert NON_FIELD_ERRORS in excinfo.value.error_dict
    assert "exactly one of the two" in str(excinfo.value.messages)


def test_resource_profile_clean_refuses_neither_identity(resource_tenant):
    """A row with neither has no identity at all - it could never render as a person."""
    shell = ResourceProfile(tenant=resource_tenant, default_role="Ghost")
    with pytest.raises(ValidationError) as excinfo:
        shell.full_clean()
    assert NON_FIELD_ERRORS in excinfo.value.error_dict
    assert "exactly one of the two" in str(excinfo.value.messages)


def test_resource_profile_clean_accepts_exactly_one_identity(resource_profile_internal,
                                                             resource_profile_contractor):
    """The control for every refusal above: the employee-keyed and the party-keyed fixture rows
    are both clean, so a ValidationError in the neighbours is about the shape under test."""
    assert resource_profile_internal.full_clean() is None
    assert resource_profile_contractor.full_clean() is None


def test_resource_profile_clean_refuses_a_second_pool_row_for_one_employee(
        resource_tenant, resource_employee_a, resource_profile_internal):
    """The friendly half of the one-row-per-employee rule: clean() answers before the database
    could raise - which it never would, the conditional unique deliberately does not exist
    (MariaDB can't enforce one)."""
    shell = ResourceProfile(tenant=resource_tenant, employee=resource_employee_a,
                            default_role="Second pool row")
    with pytest.raises(ValidationError) as excinfo:
        shell.full_clean()
    assert "employee" in excinfo.value.error_dict
    assert "already in this tenant's resource pool" in str(excinfo.value.messages)


def test_resource_profile_clean_excludes_itself_when_editing(resource_profile_internal):
    """``exclude(pk=self.pk)`` - editing a saved row in place must not report it as its own
    duplicate, or nobody could ever edit a pool row."""
    obj = resource_profile_internal
    obj.default_role = "Data engineer II"
    assert obj.full_clean() is None
    obj.save()
    obj.refresh_from_db()
    assert obj.default_role == "Data engineer II"


def test_resource_profile_clean_scopes_the_pool_check_to_one_tenant(resource_tenant_b):
    """Tenant B's own duplicate is still refused inside tenant B - the scoping narrows the check,
    it does not disable it."""
    employee = _resource_employee(resource_tenant_b, "Globex staffer")
    _resource_profile(resource_tenant_b, employee=employee)
    shell = ResourceProfile(tenant=resource_tenant_b, employee=employee,
                            default_role="Duplicate in B")
    with pytest.raises(ValidationError):
        shell.full_clean()


def test_resource_profile_save_does_not_run_clean(resource_tenant):
    """Django's contract, pinned because the conftest factory depends on it: ``save()`` never
    calls ``clean()``, which is why the form has to run the identity rule."""
    shell = ResourceProfile(tenant=resource_tenant, default_role="Names nobody")
    shell.save()
    assert shell.pk is not None
    assert shell.employee_id is None and shell.party_id is None


def test_resource_profile_identity_and_team_fks_are_set_null(resource_profile_internal,
                                                             resource_profile_contractor,
                                                             resource_employee_a,
                                                             resource_party_a,
                                                             resource_org_unit_a):
    """Losing the person master or the org unit must not delete the pool row - the row IS the
    booking denominator and its booking history."""
    resource_employee_a.delete()
    resource_org_unit_a.delete()
    resource_party_a.delete()
    resource_profile_internal.refresh_from_db()
    resource_profile_contractor.refresh_from_db()
    assert resource_profile_internal.pk
    assert resource_profile_internal.employee_id is None
    assert resource_profile_internal.org_unit_id is None
    assert resource_profile_contractor.pk
    assert resource_profile_contractor.party_id is None


# ==================================================================================================
# ResourceAllocation - vocabulary, defaults, __str__, column pins
# ==================================================================================================

def test_resource_allocation_unit_choices_are_the_three_documented():
    assert _resource_values(ResourceAllocation.ALLOCATION_UNIT_CHOICES) == [
        ("hours_per_week", "Hours per Week"), ("pct_capacity", "% of Capacity"),
        ("total_hours", "Total Hours")]
    field = ResourceAllocation._meta.get_field("allocation_unit")
    assert field.max_length == 14   # "hours_per_week" is 14 chars - one less was a fields.E009
    assert max(len(value) for value, _label in ResourceAllocation.ALLOCATION_UNIT_CHOICES) \
        <= field.max_length


def test_resource_allocation_booking_status_choices_are_the_six_documented():
    assert _resource_values(ResourceAllocation.BOOKING_STATUS_CHOICES) == [
        ("requested", "Requested"), ("soft", "Soft Booked"), ("firm", "Firm Booked"),
        ("completed", "Completed"), ("cancelled", "Cancelled"), ("released", "Released")]
    field = ResourceAllocation._meta.get_field("booking_status")
    assert field.max_length == 12
    assert max(len(value) for value, _label in ResourceAllocation.BOOKING_STATUS_CHOICES) \
        <= field.max_length


def test_resource_allocation_defaults_are_the_documented_ones(resource_tenant):
    obj = ResourceAllocation(tenant=resource_tenant, role_name="Bare minimum",
                             start_date=_resource_today())
    obj.save()
    obj.refresh_from_db()
    assert obj.number == "RAL-00001"
    assert obj.allocation_unit == "hours_per_week"
    assert obj.hours_per_week is None and obj.pct_capacity is None and obj.total_hours is None
    assert obj.booking_status == "requested"
    assert obj.end_date is None
    assert obj.project_id is None and obj.project_request_id is None and obj.project_task_id is None
    assert obj.resource_id is None and obj.substitute_of_id is None and obj.requested_by_id is None
    assert obj.skill_requirements == "" and obj.notes == ""


def test_resource_allocation_str_is_number_middot_role(resource_allocation_named_firm):
    obj = resource_allocation_named_firm
    assert str(obj) == f"{obj.number} {_RESOURCE_MIDDOT} {obj.role_name}"


def test_resource_allocation_provenance_and_chain_columns_are_pinned():
    """``requested_by`` is provenance (stamped by ral_create, never a form field);
    ``substitute_of`` is the verb-built chain; ``booking_status`` stays editable at the MODEL
    layer - the verbs write it with a plain ``save()`` - and is held out of the form instead
    (the form lane's assertion)."""
    requested_by = ResourceAllocation._meta.get_field("requested_by")
    assert requested_by.editable is False
    assert requested_by.remote_field.related_name == "requested_allocations"
    substitute_of = ResourceAllocation._meta.get_field("substitute_of")
    assert substitute_of.remote_field.related_name == "substituted_by"
    assert substitute_of.remote_field.on_delete.__name__ == "SET_NULL"
    assert ResourceAllocation._meta.get_field("booking_status").editable is True
    pct = ResourceAllocation._meta.get_field("pct_capacity")
    limits = [getattr(validator, "limit_value", None) for validator in pct.validators]
    assert 1 in limits and 100 in limits


# ==================================================================================================
# ResourceAllocation.is_live - the truth table the register lens and the boards read
# ==================================================================================================

@pytest.mark.parametrize("status,live", [
    ("requested", False), ("soft", True), ("firm", True),
    ("completed", False), ("cancelled", False), ("released", False),
])
def test_resource_allocation_is_live_requires_a_soft_or_firm_status(status, live):
    assert _resource_live_shell(-1, 1, status=status).is_live is live


def test_resource_allocation_is_live_tracks_the_window_edges():
    """Every edge inclusive: the booking is live ON its start day and ON its last day, dead the
    day after - and a null end (ongoing) never expires."""
    assert _resource_live_shell(-1, 1).is_live is True       # covers today
    assert _resource_live_shell(1, 9).is_live is False       # has not started
    assert _resource_live_shell(-9, -1).is_live is False     # ended yesterday
    assert _resource_live_shell(-9, 0).is_live is True       # ends today - still live
    assert _resource_live_shell(-9, None).is_live is True    # ongoing


def test_resource_allocation_a_soft_placeholder_can_be_live(resource_allocation_placeholder_soft):
    """Load-bearing for the register lens: a placeholder is a state of the booking (NULL
    resource), not a person - a soft one whose window covers today is LIVE."""
    obj = resource_allocation_placeholder_soft
    assert obj.resource_id is None
    assert obj.booking_status == "soft"
    assert obj.is_live is True


# ==================================================================================================
# ResourceAllocation.planned_hours() - the demand arithmetic (Decimal only, q2-quantized)
# ==================================================================================================

@pytest.mark.parametrize("booking_window,query_window,expected", [
    ((-7, 35), (-7, -1), Decimal("16.00")),   # a full 7-day window inside the booking: all 16h
    ((-3, 3), (0, 9), Decimal("9.14")),       # a 4-day overlap slice: 16 * 4/7, quantized
])
def test_resource_planned_hours_hours_per_week_prorates_by_days(booking_window, query_window,
                                                                expected):
    booking = _resource_live_shell(*booking_window)
    booking.hours_per_week = Decimal("16.00")
    win_start, win_end = _resource_window(query_window)
    ov_start = max(booking.start_date, win_start)
    ov_end = min(booking.end_date, win_end)
    days = (ov_end - ov_start).days + 1
    result = booking.planned_hours(win_start, win_end)
    assert result == q2(booking.hours_per_week * days / 7)   # the contract's formula...
    assert result == expected                                # ...and the pinned figure agree
    assert isinstance(result, Decimal) and result == result.quantize(Decimal("0.01"))


def test_resource_planned_hours_cancelled_and_released_count_zero(
        resource_allocation_cancelled, resource_allocation_released):
    """A window match is NOT enough: both verb states short-circuit to ZERO before any overlap
    math - the released row's successor already carries the demand."""
    win_start, win_end = _resource_window((0, 6))
    for booking in (resource_allocation_cancelled, resource_allocation_released):
        assert booking.start_date <= win_start and win_end <= booking.end_date
        assert booking.is_live is False
        assert booking.planned_hours(win_start, win_end) == ZERO


def test_resource_planned_hours_completed_does_not_short_circuit(resource_allocation_completed):
    """``completed`` rows still count in the METHOD - it is the board queries that exclude them.
    Pinning the seam so nobody "fixes" one side and silently double-discounts the other."""
    booking = resource_allocation_completed
    win_start, win_end = _resource_window((-60, -54))   # a 7-day window inside the past booking
    assert booking.booking_status == "completed"
    assert booking.start_date <= win_start and win_end <= booking.end_date
    assert booking.planned_hours(win_start, win_end) == q2(booking.hours_per_week * 7 / 7)
    assert booking.planned_hours(win_start, win_end) == Decimal("16.00")


def test_resource_planned_hours_a_disjoint_window_is_zero():
    booking = _resource_live_shell(10, 40)
    win_start, win_end = _resource_window((0, 5))
    assert booking.start_date > win_end
    assert booking.planned_hours(win_start, win_end) == ZERO


@pytest.mark.parametrize("query_window,expected", [
    ((0, 6), Decimal("16.00")),   # a full 7-day window of an ongoing 16h/wk booking
    ((0, 2), Decimal("6.86")),    # a 3-day slice: 16 * 3/7 = 6.857..., quantized
])
def test_resource_planned_hours_a_null_end_clamps_to_the_window_end(query_window, expected):
    booking = _resource_live_shell(-9, None)
    assert booking.end_date is None
    win_start, win_end = _resource_window(query_window)
    days = (win_end - win_start).days + 1
    assert booking.planned_hours(win_start, win_end) == q2(booking.hours_per_week * days / 7)
    assert booking.planned_hours(win_start, win_end) == expected


def test_resource_planned_hours_pct_capacity_prorates_the_named_resource(
        resource_allocation_soft_pct):
    """50% of the 24h part-timer over a full week = 12.00h - computed from the pulled rows, never
    hardcoded (the fixture's window and the resource's capacity are both read back)."""
    booking = resource_allocation_soft_pct
    assert booking.allocation_unit == "pct_capacity" and booking.pct_capacity == 50
    win_start, win_end = _resource_window((-7, -1))   # a full 7-day window inside the booking
    days = (win_end - win_start).days + 1
    expected = q2(Decimal(booking.pct_capacity) / 100
                  * booking.resource.weekly_capacity_hours * days / 7)
    assert expected == Decimal("12.00")
    assert booking.planned_hours(win_start, win_end) == expected


def test_resource_planned_hours_pct_capacity_of_a_placeholder_is_zero():
    """A % of an unknown person is unknowable - a pct placeholder counts ZERO and is flagged on
    the demand board by presence, never by hours."""
    booking = _resource_live_shell(-7, 35)
    booking.allocation_unit = "pct_capacity"
    booking.pct_capacity = 50
    win_start, win_end = _resource_window((-7, -1))
    assert booking.resource_id is None
    assert booking.planned_hours(win_start, win_end) == ZERO


@pytest.mark.parametrize("query_window,expected", [
    ((-10, 4), Decimal("40.00")),    # the whole 15-day own window inside the query window
    ((-10, -4), Decimal("18.67")),   # a 7-day sample: 40 * 7/15 = 18.666..., quantized
])
def test_resource_planned_hours_total_hours_spread_over_the_own_window(query_window, expected):
    booking = _resource_live_shell(-10, 4)
    booking.allocation_unit = "total_hours"
    booking.total_hours = Decimal("40.00")
    window_days = (booking.end_date - booking.start_date).days + 1
    assert window_days == 15
    win_start, win_end = _resource_window(query_window)
    ov_start = max(booking.start_date, win_start)
    ov_end = min(booking.end_date, win_end)
    days = (ov_end - ov_start).days + 1
    assert booking.planned_hours(win_start, win_end) \
        == q2(booking.total_hours * days / window_days)
    assert booking.planned_hours(win_start, win_end) == expected


def test_resource_planned_hours_an_inverted_own_window_reads_zero():
    """Dirty data the clean() guard refuses but save() would accept (end before start) must read
    ZERO - never a negative figure and never a crash on a register row."""
    win_start, win_end = _resource_window((-1, 5))
    total = _resource_live_shell(2, 0)
    total.allocation_unit = "total_hours"
    total.total_hours = Decimal("40.00")
    assert total.end_date < total.start_date
    assert total.planned_hours(win_start, win_end) == ZERO
    weekly = _resource_live_shell(2, 0)
    weekly.hours_per_week = Decimal("16.00")
    assert weekly.planned_hours(win_start, win_end) == ZERO


def test_resource_the_substitution_chain_counts_the_demand_once(resource_allocation_released,
                                                                resource_allocation_successor):
    """The cross-model claim: a released original + its firm successor sum to the successor's own
    hours - the released half is ZERO, so the chain never double-counts."""
    released, successor = resource_allocation_released, resource_allocation_successor
    assert successor.substitute_of_id == released.pk
    assert list(released.substituted_by.all()) == [successor]
    win_start, win_end = _resource_window((0, 6))
    assert released.planned_hours(win_start, win_end) == ZERO
    successor_planned = successor.planned_hours(win_start, win_end)
    assert successor_planned == q2(successor.hours_per_week * 7 / 7) == Decimal("10.00")
    assert released.planned_hours(win_start, win_end) + successor_planned == successor_planned
    assert released.is_live is False and successor.is_live is True


# ==================================================================================================
# ResourceAllocation.clean() - the rules save() does not enforce
# ==================================================================================================

def test_resource_allocation_clean_requires_a_project_or_request(resource_tenant):
    """Both null is unreportable - a booking that hangs off nothing cannot appear on any project
    or pipeline lens."""
    shell = _resource_allocation_shell(resource_tenant)
    with pytest.raises(ValidationError) as excinfo:
        shell.full_clean()
    assert NON_FIELD_ERRORS in excinfo.value.error_dict
    assert "Attach the allocation to a project or a project request." \
        in str(excinfo.value.messages)


def test_resource_allocation_clean_accepts_a_project_and_a_request_anchor(
        resource_tenant, resource_project, resource_request):
    """Either anchor alone satisfies the attach rule - the request-linked booking is the
    pipeline-demand shape with no project yet."""
    on_project = _resource_allocation_shell(resource_tenant, project=resource_project)
    assert on_project.full_clean() is None
    on_request = _resource_allocation_shell(
        resource_tenant, project=None, project_request=resource_request)
    assert on_request.full_clean() is None


def test_resource_allocation_clean_refuses_an_end_before_start(resource_tenant, resource_project):
    today = _resource_today()
    shell = _resource_allocation_shell(
        resource_tenant, project=resource_project, start_date=today,
        end_date=today - datetime.timedelta(days=1))
    with pytest.raises(ValidationError) as excinfo:
        shell.full_clean()
    assert "end_date" in excinfo.value.error_dict
    assert "End date cannot precede start date." in str(excinfo.value.messages)
    shell.end_date = today   # the inclusive edge: a single-day booking is fine
    assert shell.full_clean() is None


@pytest.mark.parametrize("unit,field,label", [
    ("hours_per_week", "hours_per_week", "Hours per Week"),
    ("pct_capacity", "pct_capacity", "% of Capacity"),
    ("total_hours", "total_hours", "Total Hours"),
])
def test_resource_allocation_clean_requires_the_units_own_magnitude(resource_tenant,
                                                                    resource_project,
                                                                    unit, field, label):
    magnitudes = {"hours_per_week": None, "pct_capacity": None, "total_hours": None}
    shell = _resource_allocation_shell(resource_tenant, project=resource_project,
                                       allocation_unit=unit, **magnitudes)
    with pytest.raises(ValidationError) as excinfo:
        shell.full_clean()
    assert field in excinfo.value.error_dict
    assert f"Required when the allocation unit is {label}." in str(excinfo.value.messages)


@pytest.mark.parametrize("unit,own,extra", [
    ("hours_per_week", "hours_per_week", "pct_capacity"),
    ("hours_per_week", "hours_per_week", "total_hours"),
    ("pct_capacity", "pct_capacity", "hours_per_week"),
    ("total_hours", "total_hours", "hours_per_week"),
])
def test_resource_allocation_clean_refuses_a_foreign_magnitude(resource_tenant, resource_project,
                                                               unit, own, extra):
    """The unit says which number drives every capacity computation - a second one would be
    ambiguous, so either OTHER field set is refused, keyed to that other field."""
    magnitudes = {"hours_per_week": None, "pct_capacity": None, "total_hours": None}
    magnitudes[own] = _RESOURCE_MAGNITUDES[own]
    magnitudes[extra] = _RESOURCE_MAGNITUDES[extra]
    shell = _resource_allocation_shell(resource_tenant, project=resource_project,
                                       allocation_unit=unit, **magnitudes)
    with pytest.raises(ValidationError) as excinfo:
        shell.full_clean()
    assert extra in excinfo.value.error_dict
    assert "Leave blank" in str(excinfo.value.messages)


def test_resource_allocation_save_does_not_run_clean(resource_tenant):
    """Django's contract, pinned because the conftest factory depends on it: ``save()`` never
    calls ``clean()``, so an unattached row lands - the form (and only the form) runs the guards."""
    shell = _resource_allocation_shell(resource_tenant)
    shell.save()
    assert shell.pk is not None
    assert shell.project_id is None and shell.project_request_id is None


# ==================================================================================================
# ResourceTimeEntry - vocabulary, defaults, __str__
# ==================================================================================================

def test_resource_time_entry_status_choices_are_the_four_documented():
    assert _resource_values(ResourceTimeEntry.STATUS_CHOICES) == [
        ("draft", "Draft"), ("submitted", "Submitted"),
        ("approved", "Approved"), ("rejected", "Rejected")]
    field = ResourceTimeEntry._meta.get_field("status")
    assert field.max_length == 12
    assert max(len(value) for value, _label in ResourceTimeEntry.STATUS_CHOICES) <= field.max_length


@pytest.mark.parametrize("hours,valid", [
    (Decimal("0.01"), True),   # the smallest loggable unit
    (Decimal("6.00"), True),
    (Decimal("0"), False),
    (Decimal("-0.01"), False),
    (Decimal("-8"), False),
])
def test_resource_time_entry_hours_validator_floors_at_zero_point_zero_one(resource_entry_draft,
                                                                           hours, valid):
    field = ResourceTimeEntry._meta.get_field("hours")
    assert field.max_digits == 5 and field.decimal_places == 2
    obj = resource_entry_draft
    obj.hours = hours
    if valid:
        assert obj.full_clean() is None
    else:
        with pytest.raises(ValidationError) as excinfo:
            obj.full_clean()
        assert "hours" in excinfo.value.error_dict
        assert "greater than or equal to 0.01" in str(excinfo.value.messages)


def test_resource_time_entry_defaults_are_the_documented_ones(resource_tenant,
                                                              resource_profile_internal):
    obj = ResourceTimeEntry(tenant=resource_tenant, resource=resource_profile_internal,
                            entry_date=_resource_today(), hours=Decimal("6.00"))
    obj.save()
    obj.refresh_from_db()
    assert obj.number == "RTE-00001"
    assert obj.project_id is None and obj.project_task_id is None
    assert obj.status == "draft"
    assert obj.submitted_at is None and obj.approved_by_id is None and obj.approved_at is None
    assert obj.task_description == "" and obj.decision_note == "" and obj.notes == ""


def test_resource_time_entry_str_has_no_fk_dereference(resource_entry_draft):
    """``{number} · {hours}h on {date}`` - no resource/project hop, because the admin changelist
    calls ``str()`` once per row and a deref there is an N+1 (or worse, a crash on a row whose
    project is gone). Asserted on a project-less row for exactly that reason."""
    obj = resource_entry_draft
    obj.project = None  # instance-only mutation - str() must not deref it, so nothing is saved
    assert obj.project_id is None
    assert str(obj) == f"{obj.number} {_RESOURCE_MIDDOT} {obj.hours}h on {obj.entry_date:%Y-%m-%d}"


# ==================================================================================================
# ResourceTimeEntry.week_key - the person-week regroup key
# ==================================================================================================

def test_resource_time_entry_week_key_is_the_person_week(resource_tenant,
                                                         resource_profile_internal):
    entry = _resource_entry(resource_tenant, resource_profile_internal,
                            entry_date=datetime.date(2026, 1, 1))
    assert isinstance(entry.iso_year, int) and isinstance(entry.iso_week, int)
    assert (entry.iso_year, entry.iso_week) == (2026, 1)
    assert entry.week_key == f"{resource_profile_internal.pk}:2026-W01"


def test_resource_time_entry_week_key_follows_iso_weeks_across_the_year_boundary(
        resource_tenant, resource_profile_internal):
    """ISO weeks, not calendar weeks: Sunday 2027-01-03 still closes 2026-W53, and the NEXT day
    is already 2027-W01 - a regroup on calendar week/month would split the person-week."""
    sunday = _resource_entry(resource_tenant, resource_profile_internal,
                             entry_date=datetime.date(2027, 1, 3))
    monday = _resource_entry(resource_tenant, resource_profile_internal,
                             entry_date=datetime.date(2027, 1, 4))
    assert (sunday.iso_year, sunday.iso_week) == (2026, 53)
    assert (monday.iso_year, monday.iso_week) == (2027, 1)
    assert sunday.week_key == f"{resource_profile_internal.pk}:2026-W53"
    assert monday.week_key == f"{resource_profile_internal.pk}:2027-W01"


def test_resource_time_entry_two_people_never_share_a_week_key(resource_tenant,
                                                               resource_profile_internal,
                                                               resource_profile_contractor):
    """The key prefixes ``resource_id`` (the id, not the object) so the template's
    ``{% regroup by week_key %}`` never merges two people's weeks."""
    mine = _resource_entry(resource_tenant, resource_profile_internal,
                           entry_date=datetime.date(2026, 1, 1))
    theirs = _resource_entry(resource_tenant, resource_profile_contractor,
                             entry_date=datetime.date(2026, 1, 1))
    assert mine.week_key != theirs.week_key
    assert mine.week_key.split(":", 1)[1] == theirs.week_key.split(":", 1)[1] == "2026-W01"


def test_resource_time_entry_week_properties_are_derived_never_columns():
    for name in ("iso_year", "iso_week", "week_key"):
        with pytest.raises(FieldDoesNotExist):
            ResourceTimeEntry._meta.get_field(name)
        assert isinstance(getattr(ResourceTimeEntry, name), property), name


# ==================================================================================================
# ResourceTimeEntry - FK behavior, stamps, ordering
# ==================================================================================================

def test_resource_time_entry_dies_with_its_person_but_not_with_its_project(
        resource_entry_draft, resource_project):
    """The resource FK CASCADEs (an entry dies with its person, mirroring hrm.Timesheet.employee);
    the project FK is SET_NULL (non-project time is loggable, and logged time outlives its
    project)."""
    resource_field = ResourceTimeEntry._meta.get_field("resource")
    assert resource_field.remote_field.on_delete.__name__ == "CASCADE"
    project_field = ResourceTimeEntry._meta.get_field("project")
    assert project_field.remote_field.on_delete.__name__ == "SET_NULL"
    entry_pk = resource_entry_draft.pk
    resource_project.delete()
    resource_entry_draft.refresh_from_db()
    assert resource_entry_draft.pk == entry_pk
    assert resource_entry_draft.project_id is None
    resource_entry_draft.resource.delete()
    assert not ResourceTimeEntry.objects.filter(pk=entry_pk).exists()


def test_resource_time_entry_decision_stamps_are_not_operator_writable():
    """The model half of the L20/L22 contract: who decided and when are stamped exactly once by
    the verbs. ``status`` / ``decision_note`` / ``hours`` stay editable at the model layer - the
    verbs write them with a plain ``save()`` - and are held out of the form instead (the form
    lane's assertion)."""
    non_editable = _resource_non_editable(ResourceTimeEntry)
    assert {"number", "submitted_at", "approved_by", "approved_at",
            "created_at", "updated_at"} <= non_editable
    assert not non_editable & {"status", "decision_note", "hours", "entry_date"}


def test_resource_time_entry_orders_person_week_blocks_contiguously(resource_tenant):
    """``[resource_id, -entry_date, -id]`` keeps one person's week contiguous so the template's
    ``{% regroup object_list by week_key %}`` yields one block per person-week - two people
    logging the same day must not interleave."""
    r_a = _resource_profile(resource_tenant)
    r_b = _resource_profile(resource_tenant)
    a_thu = _resource_entry(resource_tenant, r_a, entry_date=datetime.date(2026, 1, 1))
    b_thu = _resource_entry(resource_tenant, r_b, entry_date=datetime.date(2026, 1, 1))
    a_fri = _resource_entry(resource_tenant, r_a, entry_date=datetime.date(2026, 1, 2))
    a_thu_later = _resource_entry(resource_tenant, r_a, entry_date=datetime.date(2026, 1, 1))
    rows = list(ResourceTimeEntry.objects.filter(tenant=resource_tenant))
    assert rows == [a_fri, a_thu_later, a_thu, b_thu]
    assert [row.resource_id for row in rows] == [r_a.pk, r_a.pk, r_a.pk, r_b.pk]
    # One key = one person-week: person A's three rows share exactly one regroup key.
    assert len({row.week_key for row in rows[:3]}) == 1
