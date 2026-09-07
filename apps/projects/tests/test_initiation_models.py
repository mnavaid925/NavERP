"""Projects 7.1 Project Initiation & Charter - MODEL tests.

The model lane owns the claims the four tables would be worthless without - the numbering, the
constraints, the derived economics and the one verb that lives on a model rather than in a view:

* **``TenantNumbered``** mints ``PRQ-/PRJ-/PST-/PKO-00001`` once, per tenant, per MODEL. Two
  workspaces both read ``PRQ-00001`` and neither collides; a second ``save()`` never re-numbers.
  ``accounting.Project`` and ``crm.CrmProject`` also mint ``PRJ-`` numbers, so this lane proves
  ``projects.Project``'s sequence is independent of both rather than "globally unique".
* **The constraints are the data model.** ``(tenant, number)`` on all four; ``(tenant, project)``
  on ``ProjectKickoff`` - one kickoff per project; ``(tenant, project, party, raci_scope)`` on
  ``ProjectStakeholder`` - the same sponsor may be ``a`` for "charter approval" and ``c`` for
  "vendor selection", but never the same scope twice.
* **The economics are DERIVED, never columns.** ``roi_pct`` / ``risk_adjusted_benefit`` /
  ``risk_adjusted_roi_pct`` are properties over ``RISK_DISCOUNT``; a zero cost reads ``None``
  rather than raising ``ZeroDivisionError`` or fabricating an infinity, and every figure goes
  through ``q2()``'s 2dp quantize + clamp. All arithmetic is ``Decimal`` - a float assertion here
  would pass for the wrong reason.
* **``convert_to_project()``** is a field-by-field mapping plus a row-level compare-and-swap
  inside ``transaction.atomic()``. The second caller - including a caller holding a STALE
  in-memory copy, which is the shape a double-submit actually takes - gets ``None`` and mints no
  second project.
* **``attendee_count`` is a property**, so the registers annotate ``attendee_total`` instead:
  annotating over the property raises ``AttributeError``. Both names must agree in value, and
  this lane pins that they do.
* **``get_engagement_strategy_display()`` is HAND-WRITTEN** - Django generates ``get_FOO_display``
  for fields with choices, and ``engagement_strategy`` is a property, so without the method the
  grid renders an empty cell at HTTP 200 (the L7/L8 failure mode).

Determinism (L16): ``USE_TZ`` is True, so every date basis here is ``timezone.localdate()`` via
``_projectinitiation_today()`` - the same basis ``Project.is_overdue`` compares against.
``datetime.date.today()`` never appears, or the overdue-boundary assertions flake for the hours
either side of local midnight.

Naming (mandatory): every test is ``test_projectinitiation_*`` and every module-level helper
``_projectinitiation_*``, so 7.2's lane appending into this package cannot shadow either.

Scope: models only. Forms, views, urls and permissions belong to the other three lanes.
"""
import datetime
from decimal import Decimal

import pytest
from django.core.exceptions import NON_FIELD_ERRORS, FieldDoesNotExist, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Count, Q

from apps.projects.models import (
    MAX_Q2,
    ZERO,
    Project,
    ProjectKickoff,
    ProjectRequest,
    ProjectStakeholder,
    TenantNumbered,
    TenantOwned,
    next_number,
    q2,
)
from apps.projects.tests.conftest import (
    _projectinitiation_fill_kickoffs,
    _projectinitiation_fill_requests,
    _projectinitiation_fill_stakeholders,
    _projectinitiation_kickoff,
    _projectinitiation_project,
    _projectinitiation_request,
    _projectinitiation_stakeholder,
    _projectinitiation_today,
)

pytestmark = pytest.mark.django_db


# ==================================================================================================
# Local helpers - _projectinitiation_* for the same reason the tests are (Python binds the LAST
# module-level definition, so an unprefixed helper here would silently rebind a sibling lane's).
# Everything that builds a 7.1 row comes from the shared conftest factories; these only read.
# ==================================================================================================

#: U+2014. Written as an escape so this file stays pure ASCII - the model's ``__str__`` separator
#: is a real em dash and a mangled literal would make the comparison pass or fail for the wrong
#: reason on a differently-encoded checkout.
_PROJECTINITIATION_DASH = "\u2014"

#: The four 7.1 models, with the prefix each one mints.
_PROJECTINITIATION_MODELS = (
    (ProjectRequest, "PRQ"),
    (Project, "PRJ"),
    (ProjectStakeholder, "PST"),
    (ProjectKickoff, "PKO"),
)


def _projectinitiation_values(choices):
    """The value strings of a CHOICES list, in declaration order."""
    return [value for value, _label in choices]


def _projectinitiation_field_names(model):
    return {f.name for f in model._meta.fields}


def _projectinitiation_non_editable(model):
    """The columns no ModelForm can offer - the model-layer half of the L20/L22 contract."""
    return {f.name for f in model._meta.fields if not f.editable}


def _projectinitiation_index_names(model):
    return {index.name for index in model._meta.indexes}


def _projectinitiation_annotated_kickoffs(tenant):
    """The EXACT annotation ``pko_list`` / ``prj_detail`` run - under the other name.

    ``attendee_total``, not ``attendee_count``: the property is a data descriptor with no setter,
    so the model iterator cannot assign an annotation onto it. Reproduced here so the model lane
    can prove the two names agree without importing a view.
    """
    return (
        ProjectKickoff.objects.filter(tenant=tenant)
        .annotate(attendee_total=Count(
            "project__stakeholders",
            filter=Q(project__stakeholders__attending_kickoff=True)))
        .order_by("-created_at", "-id")
    )


def _projectinitiation_stakeholder_shell(project, **overrides):
    """An UNSAVED stakeholder - ``clean()`` is what is under test, and ``save()`` never calls it."""
    fields = dict(tenant=project.tenant, project=project, raci_scope="charter approval")
    fields.update(overrides)
    return ProjectStakeholder(**fields)


# ==================================================================================================
# The package import surface
# ==================================================================================================

def test_projectinitiation_models_package_reexports_the_shared_toolkit():
    """``from apps.projects.models import q2`` must keep working - the peer apps' tests, the
    seeder and the views all import through the package root, and a missing re-export is an
    ImportError at runtime, never at edit time."""
    assert MAX_Q2 == Decimal("9999999999.99")
    assert ZERO == Decimal("0")
    assert callable(q2) and callable(next_number)
    assert issubclass(TenantNumbered, TenantOwned)
    assert TenantOwned._meta.abstract and TenantNumbered._meta.abstract


def test_projectinitiation_every_model_inherits_the_numbered_base():
    for model, prefix in _PROJECTINITIATION_MODELS:
        assert issubclass(model, TenantNumbered), model.__name__
        assert model.NUMBER_PREFIX == prefix


# ==================================================================================================
# q2 - the 2dp quantize + clamp every derived figure passes through
# ==================================================================================================

def test_projectinitiation_q2_quantizes_to_two_places():
    assert str(q2(Decimal("1"))) == "1.00"
    assert q2(Decimal("112.4999")) == Decimal("112.50")
    assert q2(Decimal("0.005")) == Decimal("0.00")   # banker's rounding, the Decimal default


def test_projectinitiation_q2_treats_a_missing_value_as_zero():
    assert q2(None) == Decimal("0.00")
    assert q2(ZERO) == Decimal("0.00")


def test_projectinitiation_q2_clamps_to_the_shared_ceiling():
    """The documented clamp: a derived figure is displayed, never stored, so it is bounded rather
    than allowed to grow into a value no money column could hold."""
    assert q2(Decimal("99999999999999")) == MAX_Q2
    assert q2(Decimal("-99999999999999")) == -MAX_Q2


# ==================================================================================================
# TenantNumbered - the per-tenant, per-model sequences
# ==================================================================================================

def test_projectinitiation_request_mints_prq_00001(tenant_a):
    assert _projectinitiation_request(tenant_a).number == "PRQ-00001"


def test_projectinitiation_project_mints_prj_00001(tenant_a):
    assert _projectinitiation_project(tenant_a).number == "PRJ-00001"


def test_projectinitiation_stakeholder_mints_pst_00001(tenant_a):
    project = _projectinitiation_project(tenant_a)
    assert _projectinitiation_stakeholder(project).number == "PST-00001"


def test_projectinitiation_kickoff_mints_pko_00001(tenant_a):
    project = _projectinitiation_project(tenant_a)
    assert _projectinitiation_kickoff(project).number == "PKO-00001"


def test_projectinitiation_each_model_keeps_its_own_sequence(tenant_a):
    """Four prefixes, four independent counters - creating a project must not push the next
    request to PRQ-00002."""
    request = _projectinitiation_request(tenant_a)
    project = _projectinitiation_project(tenant_a)
    stakeholder = _projectinitiation_stakeholder(project)
    kickoff = _projectinitiation_kickoff(project)
    assert [request.number, project.number, stakeholder.number, kickoff.number] == [
        "PRQ-00001", "PRJ-00001", "PST-00001", "PKO-00001"]


def test_projectinitiation_numbers_run_in_sequence(tenant_a):
    rows = _projectinitiation_fill_requests(tenant_a, 3)
    assert [row.number for row in rows] == ["PRQ-00001", "PRQ-00002", "PRQ-00003"]


def test_projectinitiation_stakeholder_numbers_run_in_sequence(tenant_a):
    project = _projectinitiation_project(tenant_a)
    rows = _projectinitiation_fill_stakeholders(project, 3)
    assert [row.number for row in rows] == ["PST-00001", "PST-00002", "PST-00003"]


def test_projectinitiation_kickoff_numbers_run_in_sequence(tenant_a):
    rows = _projectinitiation_fill_kickoffs(tenant_a, 3)
    assert [row.number for row in rows] == ["PKO-00001", "PKO-00002", "PKO-00003"]


def test_projectinitiation_request_numbers_do_not_collide_across_tenants(tenant_a, tenant_b):
    a = _projectinitiation_request(tenant_a)
    b = _projectinitiation_request(tenant_b)
    assert a.number == b.number == "PRQ-00001"
    assert a.tenant_id != b.tenant_id


def test_projectinitiation_project_numbers_do_not_collide_across_tenants(tenant_a, tenant_b):
    a = _projectinitiation_project(tenant_a)
    b = _projectinitiation_project(tenant_b)
    assert a.number == b.number == "PRJ-00001"
    assert a.tenant_id != b.tenant_id


def test_projectinitiation_a_tenants_sequence_ignores_the_other_tenants_rows(tenant_a, tenant_b):
    _projectinitiation_fill_requests(tenant_b, 4)
    assert _projectinitiation_request(tenant_a).number == "PRQ-00001"


def test_projectinitiation_project_numbering_is_independent_of_the_other_two_prj_models(tenant_a):
    """``accounting.Project`` and ``crm.CrmProject`` are pre-spine stand-ins that also mint
    ``PRJ-``. ``next_number`` scopes to ONE model's table, so all three read ``PRJ-00001`` in one
    workspace - a number is unique per (model, tenant), never globally."""
    from apps.accounting.models import Project as AccountingProject
    from apps.crm.models import CrmProject

    costing = AccountingProject.objects.create(tenant=tenant_a, name="Costing lens")
    delivery = CrmProject.objects.create(tenant=tenant_a, name="Delivery lens")
    ours = _projectinitiation_project(tenant_a)

    assert costing.number == delivery.number == ours.number == "PRJ-00001"
    assert isinstance(ours, Project)
    assert Project.objects.filter(tenant=tenant_a).count() == 1


def test_projectinitiation_a_second_save_does_not_renumber(tenant_a):
    request = _projectinitiation_request(tenant_a)
    minted = request.number
    request.title = "Renamed after the fact"
    request.save()
    request.refresh_from_db()
    assert request.number == minted == "PRQ-00001"


def test_projectinitiation_a_second_save_does_not_renumber_the_other_three(tenant_a):
    project = _projectinitiation_project(tenant_a)
    stakeholder = _projectinitiation_stakeholder(project)
    kickoff = _projectinitiation_kickoff(project)
    minted = [project.number, stakeholder.number, kickoff.number]
    for row in (project, stakeholder, kickoff):
        row.save()
        row.refresh_from_db()
    assert [project.number, stakeholder.number, kickoff.number] == minted


def test_projectinitiation_number_is_never_operator_writable():
    for model, _prefix in _PROJECTINITIATION_MODELS:
        field = model._meta.get_field("number")
        assert field.editable is False, model.__name__
        assert field.max_length == 20, model.__name__


def test_projectinitiation_a_row_without_a_tenant_is_refused_and_never_numbered(db):
    """``TenantNumbered.save()`` only mints when ``tenant_id`` is set, so a tenant-less row does
    not burn a number on its way to the NOT NULL failure."""
    orphan = ProjectRequest(title="Orphan", description="No workspace.")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            orphan.save()
    assert orphan.number == ""


# ==================================================================================================
# unique_together - the shapes, and that the database really enforces them
# ==================================================================================================

def test_projectinitiation_unique_together_shapes_are_the_pinned_ones():
    assert ProjectRequest._meta.unique_together == (("tenant", "number"),)
    assert Project._meta.unique_together == (("tenant", "number"),)
    assert ProjectStakeholder._meta.unique_together == (
        ("tenant", "number"), ("tenant", "project", "party", "raci_scope"))
    assert ProjectKickoff._meta.unique_together == (
        ("tenant", "number"), ("tenant", "project"))


def test_projectinitiation_a_request_number_is_unique_inside_one_tenant(tenant_a):
    first = _projectinitiation_request(tenant_a)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _projectinitiation_request(tenant_a, number=first.number)


def test_projectinitiation_a_project_number_is_unique_inside_one_tenant(tenant_a):
    first = _projectinitiation_project(tenant_a)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _projectinitiation_project(tenant_a, number=first.number, code="DUP-01")


def test_projectinitiation_a_stakeholder_number_is_unique_inside_one_tenant(tenant_a):
    project = _projectinitiation_project(tenant_a)
    first = _projectinitiation_stakeholder(project)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _projectinitiation_stakeholder(project, number=first.number, raci_scope="second scope")


def test_projectinitiation_a_kickoff_number_is_unique_inside_one_tenant(tenant_a):
    first = _projectinitiation_kickoff(_projectinitiation_project(tenant_a))
    second_project = _projectinitiation_project(tenant_a, name="Other host", code="OTH-01")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _projectinitiation_kickoff(second_project, number=first.number)


def test_projectinitiation_the_same_number_is_free_in_another_tenant(tenant_a, tenant_b):
    a = _projectinitiation_request(tenant_a)
    b = _projectinitiation_request(tenant_b, number=a.number)
    assert a.number == b.number
    assert ProjectRequest.objects.filter(number=a.number).count() == 2


def test_projectinitiation_a_project_holds_at_most_one_kickoff(projectinitiation_kickoff_planned):
    """``(tenant, project)`` - a plain FK plus the constraint, deliberately not a OneToOneField."""
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _projectinitiation_kickoff(projectinitiation_kickoff_planned.project)


def test_projectinitiation_a_party_holds_one_raci_scope_per_project(
        projectinitiation_stakeholder_a, projectinitiation_project_draft,
        projectinitiation_party_a):
    assert projectinitiation_stakeholder_a.raci_scope == "charter approval"
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _projectinitiation_stakeholder(
                projectinitiation_project_draft, party=projectinitiation_party_a,
                raci_scope="charter approval")


def test_projectinitiation_a_refused_row_never_lands_with_an_empty_number(
        projectinitiation_stakeholder_a, projectinitiation_project_draft,
        projectinitiation_party_a):
    """``TenantNumbered.save()`` reads EVERY IntegrityError as a number collision and re-mints up
    to five times, so a row refused by the RACI constraint runs the whole retry loop. What must
    hold either way: the duplicate does not land, and nothing is left carrying an empty number
    (the register keys off it and an empty one would render a nameless row)."""
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            _projectinitiation_stakeholder(
                projectinitiation_project_draft, party=projectinitiation_party_a,
                raci_scope="charter approval")
    assert not ProjectStakeholder.objects.filter(number="").exists()
    assert ProjectStakeholder.objects.filter(project=projectinitiation_project_draft).count() == 1


def test_projectinitiation_the_same_party_may_hold_a_second_scope(
        projectinitiation_stakeholder_a, projectinitiation_project_draft,
        projectinitiation_party_a):
    """The constraint binds on the SCOPE, not on the person: one sponsor is ``a`` for charter
    approval and ``c`` for vendor selection, and that is the point of the register."""
    second = _projectinitiation_stakeholder(
        projectinitiation_project_draft, party=projectinitiation_party_a,
        raci_scope="vendor selection", raci_role="c")
    assert second.pk
    assert ProjectStakeholder.objects.filter(
        project=projectinitiation_project_draft, party=projectinitiation_party_a).count() == 2


def test_projectinitiation_the_same_party_and_scope_is_free_on_another_project(
        projectinitiation_stakeholder_a, tenant_a, projectinitiation_party_a):
    other = _projectinitiation_project(tenant_a, name="Second project", code="SEC-01")
    twin = _projectinitiation_stakeholder(
        other, party=projectinitiation_party_a, raci_scope="charter approval")
    assert twin.pk
    assert twin.project_id != projectinitiation_stakeholder_a.project_id


def test_projectinitiation_index_names_are_the_as_built_set():
    """Migration 0002 added ``(tenant, -created_at)`` to all four and REMOVED the redundant
    ``pst_tnt_project_idx`` / ``pko_tnt_project_idx`` (leftmost prefixes of the unique_together
    indexes). Re-adding either is write cost with no read benefit."""
    assert _projectinitiation_index_names(ProjectRequest) == {
        "prq_tnt_status_idx", "prq_tnt_type_idx", "prq_tnt_ou_idx", "prq_tnt_created_idx"}
    assert _projectinitiation_index_names(Project) == {
        "prj_tnt_status_idx", "prj_tnt_charter_idx", "prj_tnt_client_idx", "prj_tnt_ou_idx",
        "prj_tnt_created_idx"}
    assert _projectinitiation_index_names(ProjectStakeholder) == {
        "pst_tnt_type_idx", "pst_tnt_created_idx"}
    assert _projectinitiation_index_names(ProjectKickoff) == {
        "pko_tnt_status_idx", "pko_tnt_created_idx"}


# ==================================================================================================
# The tenant spine - every model is scoped, and none of them owns a reverse accessor
# ==================================================================================================

def test_projectinitiation_every_model_carries_a_cascading_tenant_fk():
    for model, _prefix in _PROJECTINITIATION_MODELS:
        field = model._meta.get_field("tenant")
        assert field.related_model._meta.label == "core.Tenant", model.__name__
        assert field.null is False, model.__name__
        assert field.remote_field.on_delete.__name__ == "CASCADE", model.__name__
        # related_name="+" - the views always filter by request.tenant, so no reverse accessor is
        # created and the abstract base never clashes across its many subclasses.
        assert field.remote_field.related_name == "+", model.__name__


def test_projectinitiation_the_tenant_has_no_reverse_accessor_for_these_models(tenant_a):
    _projectinitiation_request(tenant_a)
    for accessor in ("projectrequest_set", "project_set", "projectstakeholder_set",
                     "projectkickoff_set"):
        assert not hasattr(tenant_a, accessor), accessor


def test_projectinitiation_deleting_a_tenant_takes_its_rows_and_leaves_the_others(
        tenant_a, tenant_b):
    mine = _projectinitiation_request(tenant_a)
    theirs = _projectinitiation_request(tenant_b)
    tenant_b.delete()
    assert ProjectRequest.objects.filter(pk=mine.pk).exists()
    assert not ProjectRequest.objects.filter(pk=theirs.pk).exists()


def test_projectinitiation_every_model_orders_newest_first():
    for model, _prefix in _PROJECTINITIATION_MODELS:
        assert model._meta.ordering == ["-created_at", "-id"], model.__name__


def test_projectinitiation_the_register_reads_newest_first(tenant_a):
    oldest, middle, newest = _projectinitiation_fill_requests(tenant_a, 3)
    assert list(ProjectRequest.objects.filter(tenant=tenant_a)) == [newest, middle, oldest]


def test_projectinitiation_a_created_at_tie_is_broken_by_id(tenant_a):
    """Seeded rows land inside the same clock tick often enough that the tie-break is load
    bearing: without ``-id`` the register's order is whatever the database felt like."""
    first, second = _projectinitiation_fill_requests(tenant_a, 2)
    stamp = first.created_at
    ProjectRequest.objects.filter(pk__in=[first.pk, second.pk]).update(created_at=stamp)
    assert list(ProjectRequest.objects.filter(tenant=tenant_a)) == [second, first]


# ==================================================================================================
# ProjectRequest - vocabulary, defaults, __str__
# ==================================================================================================

def test_projectinitiation_request_type_choices_are_the_five_documented():
    assert _projectinitiation_values(ProjectRequest.REQUEST_TYPE_CHOICES) == [
        "new_project", "enhancement", "change_request", "defect", "idea"]


def test_projectinitiation_request_source_choices_are_the_five_documented():
    assert _projectinitiation_values(ProjectRequest.SOURCE_CHOICES) == [
        "portal", "internal", "idea", "opportunity", "email"]


def test_projectinitiation_request_priority_and_risk_share_one_scale():
    assert _projectinitiation_values(ProjectRequest.PRIORITY_CHOICES) == [
        "low", "medium", "high", "critical"]
    assert _projectinitiation_values(ProjectRequest.RISK_RATING_CHOICES) == [
        "low", "medium", "high", "critical"]


def test_projectinitiation_request_feasibility_choices_are_the_four_documented():
    assert _projectinitiation_values(ProjectRequest.FEASIBILITY_CHOICES) == [
        "not_assessed", "feasible", "feasible_with_constraints", "not_feasible"]


def test_projectinitiation_feasibility_column_holds_its_longest_choice():
    """``feasible_with_constraints`` is 25 characters; a max_length of 24 was a fields.E009."""
    field = ProjectRequest._meta.get_field("feasibility")
    assert field.max_length == 32
    assert max(len(value) for value in
               _projectinitiation_values(ProjectRequest.FEASIBILITY_CHOICES)) <= field.max_length


def test_projectinitiation_request_status_choices_are_the_nine_documented():
    assert _projectinitiation_values(ProjectRequest.STATUS_CHOICES) == [
        "draft", "submitted", "screening", "assessment", "needs_information",
        "approved", "rejected", "deferred", "converted"]


def test_projectinitiation_request_decision_choices_are_the_four_documented():
    assert _projectinitiation_values(ProjectRequest.DECISION_CHOICES) == [
        "go", "no_go", "hold", "deferred"]


def test_projectinitiation_decision_statuses_are_the_three_under_review():
    """The gate the approve / reject verbs read. A never-submitted draft is NOT in it - the
    absent-prerequisite case must be refused, not fall through to approval (L35)."""
    assert ProjectRequest.DECISION_STATUSES == ("submitted", "screening", "assessment")
    valid = set(_projectinitiation_values(ProjectRequest.STATUS_CHOICES))
    assert set(ProjectRequest.DECISION_STATUSES) <= valid
    assert set(ProjectRequest.DECISION_STATUSES).isdisjoint(
        {"draft", "needs_information", "approved", "rejected", "deferred", "converted"})


def test_projectinitiation_risk_discount_carries_a_factor_for_every_rating():
    assert ProjectRequest.RISK_DISCOUNT == {
        "low": Decimal("1.00"),
        "medium": Decimal("0.85"),
        "high": Decimal("0.70"),
        "critical": Decimal("0.50"),
    }
    assert set(ProjectRequest.RISK_DISCOUNT) == set(
        _projectinitiation_values(ProjectRequest.RISK_RATING_CHOICES))


def test_projectinitiation_request_defaults_are_the_documented_ones(tenant_a):
    obj = ProjectRequest(tenant=tenant_a, title="Bare minimum",
                         description="Only the two required columns.")
    obj.save()
    obj.refresh_from_db()
    assert obj.number == "PRQ-00001"
    assert obj.request_type == "new_project"
    assert obj.source == "internal"
    assert obj.priority == "medium"
    assert obj.strategic_alignment == 0
    assert obj.estimated_cost == Decimal("0.00")
    assert obj.estimated_benefit == Decimal("0.00")
    assert obj.risk_rating == "low"
    assert obj.feasibility == "not_assessed"
    assert obj.status == "draft"
    assert obj.decision == ""


def test_projectinitiation_request_optional_columns_start_empty(tenant_a):
    obj = ProjectRequest(tenant=tenant_a, title="Bare minimum", description="Nothing else set.")
    obj.save()
    obj.refresh_from_db()
    assert obj.feasibility_notes == obj.alternatives_considered == obj.required_resources == ""
    assert obj.decision_notes == obj.rejection_reason == obj.information_requested == ""
    assert obj.target_start_date is None and obj.target_end_date is None
    assert obj.submitted_at is None and obj.decided_at is None
    assert obj.decided_by_id is None and obj.created_by_id is None
    assert obj.converted_project_id is None
    assert obj.currency_id is None and obj.requester_party_id is None and obj.org_unit_id is None
    assert obj.assigned_reviewer_id is None and obj.assigned_approver_id is None
    assert obj.created_at is not None and obj.updated_at is not None


def test_projectinitiation_request_str_is_number_then_title(projectinitiation_request_draft):
    obj = projectinitiation_request_draft
    assert str(obj) == f"{obj.number} {_PROJECTINITIATION_DASH} {obj.title}"


def test_projectinitiation_request_display_labels_read_back(projectinitiation_request_draft):
    obj = projectinitiation_request_draft
    assert obj.get_status_display() == "Draft"
    assert obj.get_priority_display() == "High"
    assert obj.get_request_type_display() == "New Project"
    assert obj.get_feasibility_display() == "Feasible"


def test_projectinitiation_request_spine_fks_are_set_null_never_cascade(
        projectinitiation_request_draft, projectinitiation_org_unit_a,
        projectinitiation_party_a):
    """Retiring an org unit or a party must not delete the intake history that referenced it -
    the request row IS the audit trail of what was asked for and what was decided."""
    projectinitiation_org_unit_a.delete()
    projectinitiation_party_a.delete()
    projectinitiation_request_draft.refresh_from_db()
    assert projectinitiation_request_draft.pk
    assert projectinitiation_request_draft.org_unit_id is None
    assert projectinitiation_request_draft.requester_party_id is None


def test_projectinitiation_request_decision_stamps_are_not_operator_writable():
    """The model half of the L20/L22 contract: who decided and when are stamped by a gated verb.
    ``status`` / ``decision`` / the reason columns stay editable at the model layer and are held
    out of the form by ``Meta.exclude`` instead - that is the form lane's assertion."""
    non_editable = _projectinitiation_non_editable(ProjectRequest)
    assert {"number", "decided_by", "decided_at", "submitted_at", "created_by",
            "created_at", "updated_at"} <= non_editable
    assert not non_editable & {"title", "estimated_cost", "status", "decision"}


# ==================================================================================================
# ProjectRequest - the derived economics (Decimal only, never float)
# ==================================================================================================

def test_projectinitiation_economics_are_properties_never_columns():
    for name in ("roi_pct", "risk_adjusted_benefit", "risk_adjusted_roi_pct"):
        with pytest.raises(FieldDoesNotExist):
            ProjectRequest._meta.get_field(name)
        assert isinstance(getattr(ProjectRequest, name), property), name


def test_projectinitiation_roi_pct_is_the_stated_return(projectinitiation_request_draft):
    obj = projectinitiation_request_draft
    assert obj.estimated_cost == Decimal("120000.00")
    assert obj.estimated_benefit == Decimal("300000.00")
    assert obj.roi_pct == Decimal("150.00")
    assert str(obj.roi_pct) == "150.00"


def test_projectinitiation_risk_adjusted_benefit_discounts_by_the_rating(
        projectinitiation_request_draft):
    obj = projectinitiation_request_draft
    assert obj.risk_rating == "medium"
    assert obj.risk_adjusted_benefit == Decimal("255000.00")
    assert str(obj.risk_adjusted_benefit) == "255000.00"


def test_projectinitiation_risk_adjusted_roi_uses_the_discounted_benefit(
        projectinitiation_request_draft):
    obj = projectinitiation_request_draft
    assert obj.risk_adjusted_roi_pct == Decimal("112.50")


@pytest.mark.parametrize("rating,expected", [
    ("low", Decimal("300000.00")),
    ("medium", Decimal("255000.00")),
    ("high", Decimal("210000.00")),
    ("critical", Decimal("150000.00")),
])
def test_projectinitiation_every_risk_rating_discounts_by_its_own_factor(tenant_a, rating,
                                                                        expected):
    obj = _projectinitiation_request(tenant_a, risk_rating=rating,
                                     estimated_benefit=Decimal("300000.00"))
    assert obj.risk_adjusted_benefit == expected


def test_projectinitiation_an_unmapped_risk_rating_falls_back_to_no_discount():
    """``RISK_DISCOUNT.get(..., 1.00)`` - a rating the dict has never heard of degrades to the
    undiscounted benefit instead of raising KeyError while rendering a register row."""
    obj = ProjectRequest(estimated_benefit=Decimal("1000.00"), risk_rating="")
    assert obj.risk_adjusted_benefit == Decimal("1000.00")


def test_projectinitiation_a_zero_cost_reads_none_not_a_division_error(tenant_a):
    obj = _projectinitiation_request(tenant_a, estimated_cost=Decimal("0.00"),
                                     estimated_benefit=Decimal("50000.00"))
    assert obj.roi_pct is None
    assert obj.risk_adjusted_roi_pct is None
    # The benefit side still computes - only the ratio is undefined.
    assert obj.risk_adjusted_benefit == Decimal("42500.00")


def test_projectinitiation_a_brand_new_request_has_no_roi(tenant_a):
    obj = ProjectRequest(tenant=tenant_a, title="Unpriced", description="No case yet.")
    obj.save()
    assert obj.estimated_cost == Decimal("0")
    assert obj.roi_pct is None
    assert obj.risk_adjusted_roi_pct is None


def test_projectinitiation_a_negative_return_reads_negative(projectinitiation_request_rejected):
    obj = projectinitiation_request_rejected
    assert obj.estimated_cost == Decimal("320000.00")
    assert obj.estimated_benefit == Decimal("140000.00")
    assert obj.roi_pct == Decimal("-56.25")


def test_projectinitiation_a_risk_adjusted_return_rounds_to_two_places(
        projectinitiation_request_rejected):
    """(140000 * 0.70 - 320000) / 320000 * 100 = -69.375, quantized to 2dp."""
    obj = projectinitiation_request_rejected
    assert obj.risk_adjusted_benefit == Decimal("98000.00")
    assert obj.risk_adjusted_roi_pct == Decimal("-69.38")


def test_projectinitiation_roi_clamps_instead_of_overflowing(tenant_a):
    obj = _projectinitiation_request(tenant_a, estimated_cost=Decimal("0.01"),
                                     estimated_benefit=Decimal("9999999999.99"),
                                     risk_rating="low")
    assert obj.roi_pct == MAX_Q2
    assert obj.risk_adjusted_roi_pct == MAX_Q2


def test_projectinitiation_a_benefit_above_the_shared_ceiling_clamps(tenant_a):
    """``q2``'s ceiling is the app-wide MAX_Q2, which is narrower than the 14,2 column - a
    benefit above it displays clamped rather than as a figure no peer app would print."""
    obj = _projectinitiation_request(tenant_a, estimated_benefit=Decimal("999999999999.99"),
                                     risk_rating="low")
    assert obj.risk_adjusted_benefit == MAX_Q2


def test_projectinitiation_the_economics_follow_the_current_values_without_a_save(
        projectinitiation_request_draft):
    """Derived, not stored: edit the inputs in memory and the figures move; refresh and they come
    back. Nothing about them is persisted, so nothing about them can go stale."""
    obj = projectinitiation_request_draft
    assert obj.roi_pct == Decimal("150.00")
    obj.estimated_benefit = Decimal("120000.00")
    assert obj.roi_pct == Decimal("0.00")
    obj.refresh_from_db()
    assert obj.roi_pct == Decimal("150.00")


def test_projectinitiation_the_economics_are_decimal_not_float(projectinitiation_request_draft):
    obj = projectinitiation_request_draft
    assert isinstance(obj.roi_pct, Decimal)
    assert isinstance(obj.risk_adjusted_benefit, Decimal)
    assert isinstance(obj.risk_adjusted_roi_pct, Decimal)


# ==================================================================================================
# ProjectRequest - the numeric guards (migration 0002 + Django's own field validation)
# ==================================================================================================

def test_projectinitiation_a_well_formed_request_passes_full_clean(
        projectinitiation_request_draft):
    """The control for every raise below: the fixture row itself is clean, so a ValidationError in
    the next tests is about the value under test and not about incidental required fields."""
    assert projectinitiation_request_draft.full_clean() is None


def test_projectinitiation_a_negative_cost_is_refused(projectinitiation_request_draft):
    obj = projectinitiation_request_draft
    obj.estimated_cost = Decimal("-5.00")
    with pytest.raises(ValidationError) as excinfo:
        obj.full_clean()
    assert "estimated_cost" in excinfo.value.error_dict
    assert "greater than or equal to 0" in str(excinfo.value.messages)


def test_projectinitiation_a_negative_benefit_is_refused(projectinitiation_request_draft):
    obj = projectinitiation_request_draft
    obj.estimated_benefit = Decimal("-0.01")
    with pytest.raises(ValidationError) as excinfo:
        obj.full_clean()
    assert "estimated_benefit" in excinfo.value.error_dict


def test_projectinitiation_the_min_value_validator_is_on_both_money_columns():
    for name in ("estimated_cost", "estimated_benefit"):
        field = ProjectRequest._meta.get_field(name)
        assert field.max_digits == 14 and field.decimal_places == 2
        limits = [getattr(v, "limit_value", None) for v in field.validators]
        assert ZERO in limits, name


def test_projectinitiation_an_over_wide_cost_is_a_friendly_error_not_a_driver_failure(
        projectinitiation_request_draft):
    obj = projectinitiation_request_draft
    obj.estimated_cost = Decimal("999999999999999.99")
    with pytest.raises(ValidationError) as excinfo:
        obj.full_clean()
    assert "estimated_cost" in excinfo.value.error_dict
    assert "14 digits" in str(excinfo.value.messages)


@pytest.mark.parametrize("junk", ["NaN", "Infinity", "-Infinity"])
def test_projectinitiation_a_non_finite_cost_is_refused(projectinitiation_request_draft, junk):
    """L35: garbage in must be an error, never a stored value the ROI column then ranks on."""
    obj = projectinitiation_request_draft
    obj.estimated_cost = Decimal(junk)
    with pytest.raises(ValidationError):
        obj.full_clean()


def test_projectinitiation_a_non_finite_cost_cannot_be_saved(projectinitiation_request_draft):
    """Not just ``full_clean()``: the field refuses a non-finite value on the way to the database
    too, so no code path can persist one. The ``atomic()`` wrapper is only there to scope the
    rollback - a failed statement poisons the surrounding test transaction otherwise."""
    obj = projectinitiation_request_draft
    obj.estimated_cost = Decimal("NaN")
    with pytest.raises(ValidationError):
        with transaction.atomic():
            obj.save()
    obj.refresh_from_db()
    assert obj.estimated_cost == Decimal("120000.00")


def test_projectinitiation_strategic_alignment_tops_out_at_five(projectinitiation_request_draft):
    obj = projectinitiation_request_draft
    obj.strategic_alignment = 9
    with pytest.raises(ValidationError) as excinfo:
        obj.full_clean()
    assert "strategic_alignment" in excinfo.value.error_dict
    assert "less than or equal to 5" in str(excinfo.value.messages)


def test_projectinitiation_strategic_alignment_accepts_the_whole_zero_to_five_scale(
        projectinitiation_request_draft):
    obj = projectinitiation_request_draft
    for score in range(0, 6):
        obj.strategic_alignment = score
        assert obj.full_clean() is None


# ==================================================================================================
# ProjectRequest.convert_to_project() - the mapping and the compare-and-swap
# ==================================================================================================

def test_projectinitiation_convert_maps_the_text_columns(projectinitiation_request_approved,
                                                         admin_user):
    request = projectinitiation_request_approved
    project = request.convert_to_project(user=admin_user)
    assert project is not None
    assert project.tenant_id == request.tenant_id
    assert project.name == request.title
    assert project.description == request.description
    assert project.number.startswith("PRJ-")


def test_projectinitiation_convert_maps_the_fks_and_the_dates(projectinitiation_request_approved,
                                                              admin_user):
    request = projectinitiation_request_approved
    project = request.convert_to_project(user=admin_user)
    assert project.org_unit_id == request.org_unit_id
    assert project.client_id == request.requester_party_id
    assert project.executive_sponsor_id == request.assigned_approver_id
    assert project.start_date == request.target_start_date
    assert project.end_date == request.target_end_date
    assert project.created_by_id == admin_user.pk
    # Everything the request has no opinion on stays unset - convert fabricates nothing.
    assert project.project_manager_id is None
    assert project.charter_document_id is None
    assert project.code == ""


def test_projectinitiation_convert_links_both_directions_and_marks_the_request(
        projectinitiation_request_approved, admin_user):
    request = projectinitiation_request_approved
    project = request.convert_to_project(user=admin_user)
    request.refresh_from_db()
    project.refresh_from_db()
    assert request.status == "converted"
    assert request.converted_project_id == project.pk
    assert project.request_id == request.pk
    assert list(request.projects.all()) == [project]
    assert list(project.source_requests.all()) == [request]


def test_projectinitiation_the_converted_project_starts_at_charter_draft(
        projectinitiation_request_approved, admin_user):
    """A go decision on the REQUEST is not an approved charter - the new project starts at the
    beginning of its own workflow, with no approval stamp to inherit."""
    project = projectinitiation_request_approved.convert_to_project(user=admin_user)
    assert project.status == "draft"
    assert project.charter_status == "draft"
    assert project.charter_approved_by_id is None
    assert project.charter_approved_at is None


def test_projectinitiation_convert_writes_only_its_own_three_columns(
        projectinitiation_request_approved, admin_user):
    """``save(update_fields=[...])`` - an unrelated in-memory edit must not ride along into the
    database on the back of a convert."""
    request = projectinitiation_request_approved
    original_title = request.title
    request.title = "Edited in memory, never saved"
    request.convert_to_project(user=admin_user)
    request.refresh_from_db()
    assert request.title == original_title
    assert request.status == "converted"


def test_projectinitiation_convert_without_a_user_leaves_created_by_empty(
        projectinitiation_request_approved):
    project = projectinitiation_request_approved.convert_to_project()
    assert project is not None
    assert project.created_by_id is None


def test_projectinitiation_convert_carries_a_sparse_request_without_inventing_data(tenant_a,
                                                                                  admin_user):
    request = _projectinitiation_request(
        tenant_a, status="approved", org_unit=None, requester_party=None,
        assigned_approver=None, target_start_date=None, target_end_date=None)
    project = request.convert_to_project(user=admin_user)
    assert project.org_unit_id is None
    assert project.client_id is None
    assert project.executive_sponsor_id is None
    assert project.start_date is None and project.end_date is None


def test_projectinitiation_convert_is_idempotent(projectinitiation_request_converted, admin_user):
    """The fixture already ran the real convert. A second call must answer falsy and mint
    nothing - one demand, one project."""
    request = projectinitiation_request_converted
    before = Project.objects.filter(tenant=request.tenant).count()
    assert request.convert_to_project(user=admin_user) is None
    assert Project.objects.filter(tenant=request.tenant).count() == before == 1


def test_projectinitiation_a_stale_copy_loses_the_compare_and_swap(
        projectinitiation_request_approved, admin_user):
    """The shape a double-submit actually takes: two requests each hold their OWN in-memory row,
    so the loser's ``converted_project_id`` fast path is None and the guard has to be the
    row-level compare-and-swap inside ``transaction.atomic()``."""
    fresh = projectinitiation_request_approved
    stale = ProjectRequest.objects.get(pk=fresh.pk)
    assert stale.converted_project_id is None

    winner = fresh.convert_to_project(user=admin_user)
    loser = stale.convert_to_project(user=admin_user)

    assert winner is not None
    assert loser is None
    assert Project.objects.filter(tenant=fresh.tenant).count() == 1
    fresh.refresh_from_db()
    assert fresh.converted_project_id == winner.pk


def test_projectinitiation_convert_re_arms_once_the_back_pointer_is_cleared(
        projectinitiation_request_converted, admin_user):
    """The guard is the LINK, not a one-shot flag: clear ``converted_project`` and the same
    request converts again, taking the next number alongside the first project."""
    request = projectinitiation_request_converted
    first = request.converted_project
    request.converted_project = None
    request.status = "approved"
    request.save(update_fields=["converted_project", "status", "updated_at"])

    second = request.convert_to_project(user=admin_user)
    assert second is not None
    assert second.pk != first.pk
    assert second.number == "PRJ-00002"
    assert Project.objects.filter(tenant=request.tenant).count() == 2


def test_projectinitiation_convert_runs_again_after_the_project_is_deleted(
        projectinitiation_request_converted, admin_user):
    """The model side of the project-delete reopen: SET_NULL clears the back-pointer, the view
    walks the status back to ``approved``, and the request is convertible again.

    The new project's number is minted fresh by ``apps.core.utils.next_number`` (existence-guarded
    max+1, app-wide), so this asserts a NEW ROW rather than a particular number.
    """
    request = projectinitiation_request_converted
    first_pk = request.converted_project_id
    request.converted_project.delete()
    request.refresh_from_db()
    assert request.converted_project_id is None

    request.status = "approved"
    request.save(update_fields=["status", "updated_at"])
    second = request.convert_to_project(user=admin_user)
    assert second is not None
    assert second.pk != first_pk
    assert second.number.startswith("PRJ-")
    assert Project.objects.filter(tenant=request.tenant).count() == 1


def test_projectinitiation_convert_does_not_gate_on_status(tenant_a, admin_user):
    """Deliberate: ``convert_to_project()`` is the MECHANISM and the "only an approved request"
    gate lives in ``prq_convert`` (the view lane asserts the refusal). Pinned here so nobody
    reads the model as the gate - and so a future model-level guard has to be a decision, not an
    accident."""
    draft = _projectinitiation_request(tenant_a, status="draft")
    project = draft.convert_to_project(user=admin_user)
    assert project is not None
    draft.refresh_from_db()
    assert draft.status == "converted"


def test_projectinitiation_converted_project_is_set_null_on_a_deleted_project(
        projectinitiation_request_converted):
    """Deleting the project must leave the request standing - the row carries the intake history
    and the decision that was taken on it."""
    request = projectinitiation_request_converted
    request.converted_project.delete()
    request.refresh_from_db()
    assert request.converted_project_id is None
    assert request.status == "converted"   # the view is what walks it back to `approved`


def test_projectinitiation_a_deleted_request_leaves_its_project_standing(
        projectinitiation_request_converted):
    request = projectinitiation_request_converted
    project = request.converted_project
    request.delete()
    project.refresh_from_db()
    assert project.request_id is None


# ==================================================================================================
# Project - vocabulary, defaults, __str__, is_overdue
# ==================================================================================================

def test_projectinitiation_project_methodology_choices_are_the_three_documented():
    assert _projectinitiation_values(Project.METHODOLOGY_CHOICES) == [
        "waterfall", "agile", "hybrid"]


def test_projectinitiation_project_charter_status_choices_keep_the_reserved_rejected():
    """No 7.1 verb SETS ``rejected``, but ``prj_submit_charter`` accepts it as a source so a
    rejected charter can be resubmitted. Dropping it would cost a migration and come straight
    back."""
    assert _projectinitiation_values(Project.CHARTER_STATUS_CHOICES) == [
        "draft", "submitted", "approved", "rejected"]


def test_projectinitiation_project_status_choices_are_the_seven_documented():
    assert _projectinitiation_values(Project.STATUS_CHOICES) == [
        "draft", "chartered", "kickoff", "active", "on_hold", "completed", "cancelled"]


def test_projectinitiation_project_defaults_are_the_documented_ones(tenant_a):
    obj = Project(tenant=tenant_a, name="Bare minimum")
    obj.save()
    obj.refresh_from_db()
    assert obj.number == "PRJ-00001"
    assert obj.methodology == "hybrid"
    assert obj.charter_status == "draft"
    assert obj.status == "draft"
    assert obj.code == "" and obj.description == ""
    assert obj.in_scope == obj.out_of_scope == obj.objectives == ""
    assert obj.success_criteria == obj.assumptions == obj.constraints == obj.risk_summary == ""
    assert obj.request_id is None and obj.charter_document_id is None
    assert obj.executive_sponsor_id is None and obj.project_manager_id is None
    assert obj.org_unit_id is None and obj.client_id is None
    assert obj.start_date is None and obj.end_date is None
    assert obj.charter_approved_by_id is None and obj.charter_approved_at is None
    assert obj.created_by_id is None
    assert obj.is_overdue is False


def test_projectinitiation_project_str_is_number_then_name(projectinitiation_project_draft):
    obj = projectinitiation_project_draft
    assert str(obj) == f"{obj.number} {_PROJECTINITIATION_DASH} {obj.name}"


def test_projectinitiation_project_charter_stamps_are_not_operator_writable():
    non_editable = _projectinitiation_non_editable(Project)
    assert {"number", "charter_approved_by", "charter_approved_at", "created_by",
            "created_at", "updated_at"} <= non_editable
    assert not non_editable & {"name", "charter_status", "status", "charter_document"}


def test_projectinitiation_is_overdue_is_derived_never_a_column():
    with pytest.raises(FieldDoesNotExist):
        Project._meta.get_field("is_overdue")
    assert isinstance(Project.is_overdue, property)


def test_projectinitiation_a_past_end_date_reads_overdue(projectinitiation_project_overdue):
    obj = projectinitiation_project_overdue
    assert obj.end_date < _projectinitiation_today()
    assert obj.is_overdue is True


def test_projectinitiation_a_future_end_date_is_not_overdue(projectinitiation_project_draft):
    assert projectinitiation_project_draft.is_overdue is False


def test_projectinitiation_a_project_without_an_end_date_is_never_overdue(tenant_a):
    obj = _projectinitiation_project(tenant_a, end_date=None, status="active")
    assert obj.is_overdue is False


def test_projectinitiation_overdue_starts_the_day_after_the_end_date(tenant_a):
    """The boundary, on ``timezone.localdate()`` - the same basis the property compares against
    (L16). ``datetime.date.today()`` would flake either side of local midnight."""
    today = _projectinitiation_today()
    on_time = _projectinitiation_project(tenant_a, name="Due today", code="DUE-01",
                                         end_date=today, status="active")
    late = _projectinitiation_project(tenant_a, name="Due yesterday", code="DUE-02",
                                      end_date=today - datetime.timedelta(days=1), status="active")
    assert on_time.is_overdue is False
    assert late.is_overdue is True


def test_projectinitiation_a_closed_project_is_never_overdue(tenant_a):
    """An "Overdue" badge on a finished project is how people stop trusting the badge."""
    yesterday = _projectinitiation_today() - datetime.timedelta(days=1)
    for status in ("completed", "cancelled"):
        obj = _projectinitiation_project(tenant_a, name=f"Closed {status}", code=f"CL-{status}",
                                         end_date=yesterday, status=status)
        assert obj.is_overdue is False, status


def test_projectinitiation_is_overdue_suppression_matches_the_view_terminal_set(tenant_a):
    """Drift guard: ``is_overdue`` hard-codes ("completed", "cancelled") and the charter verbs
    read ``TERMINAL_STATUSES``. If one grows a state the other must too, or a project can be
    terminal for the verbs and still wear an Overdue badge."""
    from apps.projects.views.ProjectInitiation.Projects import TERMINAL_STATUSES

    assert TERMINAL_STATUSES == ("completed", "cancelled")
    yesterday = _projectinitiation_today() - datetime.timedelta(days=1)
    for status in _projectinitiation_values(Project.STATUS_CHOICES):
        shell = Project(tenant=tenant_a, name=f"Late {status}", end_date=yesterday, status=status)
        assert shell.is_overdue is (status not in TERMINAL_STATUSES), status


def test_projectinitiation_project_reverse_names_are_the_pinned_ones(
        projectinitiation_project_draft, projectinitiation_stakeholder_a,
        projectinitiation_kickoff_planned):
    project = projectinitiation_project_draft
    assert list(project.stakeholders.all()) == [projectinitiation_stakeholder_a]
    assert list(project.kickoffs.all()) == [projectinitiation_kickoff_planned]


def test_projectinitiation_deleting_a_project_cascades_to_its_children(
        projectinitiation_project_draft, projectinitiation_stakeholder_a,
        projectinitiation_kickoff_planned):
    stakeholder_pk = projectinitiation_stakeholder_a.pk
    kickoff_pk = projectinitiation_kickoff_planned.pk
    projectinitiation_project_draft.delete()
    assert not ProjectStakeholder.objects.filter(pk=stakeholder_pk).exists()
    assert not ProjectKickoff.objects.filter(pk=kickoff_pk).exists()


# ==================================================================================================
# ProjectStakeholder - vocabulary, defaults, __str__
# ==================================================================================================

def test_projectinitiation_stakeholder_type_choices_are_the_seven_documented():
    assert _projectinitiation_values(ProjectStakeholder.STAKEHOLDER_TYPE_CHOICES) == [
        "sponsor", "approver", "resource_provider", "subject_matter_expert", "affected",
        "team_member", "other"]


def test_projectinitiation_raci_roles_are_the_four_single_letters():
    assert _projectinitiation_values(ProjectStakeholder.RACI_ROLE_CHOICES) == ["r", "a", "c", "i"]
    assert ProjectStakeholder._meta.get_field("raci_role").max_length == 1


def test_projectinitiation_influence_and_interest_share_one_scale():
    assert _projectinitiation_values(ProjectStakeholder.INFLUENCE_CHOICES) == [
        "high", "medium", "low"]
    assert _projectinitiation_values(ProjectStakeholder.INTEREST_CHOICES) == [
        "high", "medium", "low"]


def test_projectinitiation_comms_choices_are_the_documented_sets():
    assert _projectinitiation_values(ProjectStakeholder.COMMS_PREFERENCE_CHOICES) == [
        "email", "meeting", "written_report", "portal", "none"]
    assert _projectinitiation_values(ProjectStakeholder.COMMS_FREQUENCY_CHOICES) == [
        "daily", "weekly", "monthly", "at_milestone", "ad_hoc"]


def test_projectinitiation_stakeholder_defaults_are_the_documented_ones(
        tenant_a, projectinitiation_party_a):
    project = _projectinitiation_project(tenant_a)
    obj = ProjectStakeholder(tenant=tenant_a, project=project, party=projectinitiation_party_a)
    obj.save()
    obj.refresh_from_db()
    assert obj.number == "PST-00001"
    assert obj.stakeholder_type == "other"
    assert obj.raci_role == "i"
    assert obj.raci_scope == ""
    assert obj.influence == "medium" and obj.interest == "medium"
    assert obj.comms_preference == "email" and obj.comms_frequency == "weekly"
    assert obj.attending_kickoff is False
    assert obj.notes == "" and obj.created_by_id is None
    assert obj.user_id is None


def test_projectinitiation_stakeholder_str_names_the_party_and_the_raci_letter(
        projectinitiation_stakeholder_a, projectinitiation_party_a):
    obj = projectinitiation_stakeholder_a
    assert str(obj) == (f"{obj.number} {_PROJECTINITIATION_DASH} {projectinitiation_party_a.name} "
                        f"(A (Accountable))")


def test_projectinitiation_stakeholder_str_falls_through_to_the_user(
        projectinitiation_stakeholder_user_only, member_user):
    obj = projectinitiation_stakeholder_user_only
    assert obj.party_id is None
    assert str(obj) == (f"{obj.number} {_PROJECTINITIATION_DASH} {member_user.email} "
                        f"(R (Responsible))")


def test_projectinitiation_stakeholder_str_survives_a_row_that_names_nobody():
    """``__str__`` is called from the admin, from log lines and from a kickoff's own string - it
    must not raise on a half-built row."""
    shell = ProjectStakeholder(number="PST-09999", raci_role="i")
    assert str(shell) == (f"PST-09999 {_PROJECTINITIATION_DASH} {_PROJECTINITIATION_DASH} "
                          f"(I (Informed))")


def test_projectinitiation_stakeholder_created_by_is_not_operator_writable():
    non_editable = _projectinitiation_non_editable(ProjectStakeholder)
    assert {"number", "created_by", "created_at", "updated_at"} <= non_editable
    assert not non_editable & {"project", "party", "user", "raci_role", "attending_kickoff"}


def test_projectinitiation_stakeholder_party_and_user_are_set_null(
        projectinitiation_stakeholder_a, projectinitiation_party_a):
    """Losing the party master must not silently delete the RACI history."""
    projectinitiation_party_a.delete()
    projectinitiation_stakeholder_a.refresh_from_db()
    assert projectinitiation_stakeholder_a.party_id is None
    assert projectinitiation_stakeholder_a.pk


def test_projectinitiation_stakeholder_user_fk_is_set_null(
        projectinitiation_stakeholder_user_only, member_user):
    member_user.delete()
    projectinitiation_stakeholder_user_only.refresh_from_db()
    assert projectinitiation_stakeholder_user_only.user_id is None


# ==================================================================================================
# ProjectStakeholder - the influence x interest grid
# ==================================================================================================

def test_projectinitiation_engagement_strategy_is_derived_never_a_column():
    with pytest.raises(FieldDoesNotExist):
        ProjectStakeholder._meta.get_field("engagement_strategy")
    assert "engagement_strategy" not in _projectinitiation_field_names(ProjectStakeholder)
    assert isinstance(ProjectStakeholder.engagement_strategy, property)


def test_projectinitiation_engagement_strategy_choices_are_a_label_set_only():
    assert _projectinitiation_values(ProjectStakeholder.ENGAGEMENT_STRATEGY_CHOICES) == [
        "manage_closely", "keep_satisfied", "keep_informed", "monitor"]


@pytest.mark.parametrize("influence,interest,expected", [
    ("high", "high", "manage_closely"),
    ("high", "medium", "keep_satisfied"),
    ("high", "low", "keep_satisfied"),
    ("medium", "high", "keep_informed"),
    ("low", "high", "keep_informed"),
    ("medium", "medium", "monitor"),
    ("medium", "low", "monitor"),
    ("low", "medium", "monitor"),
    ("low", "low", "monitor"),
])
def test_projectinitiation_the_engagement_grid_covers_every_combination(influence, interest,
                                                                       expected):
    """``medium`` maps to the LOW side of BOTH axes - documented on the property, and the reason
    a three-point scale with no neutral middle is not ambiguous here."""
    shell = ProjectStakeholder(influence=influence, interest=interest)
    assert shell.engagement_strategy == expected


def test_projectinitiation_the_high_high_quadrant_is_managed_closely(
        projectinitiation_stakeholder_a):
    obj = projectinitiation_stakeholder_a
    assert (obj.influence, obj.interest) == ("high", "high")
    assert obj.engagement_strategy == "manage_closely"
    assert obj.get_engagement_strategy_display() == "Manage Closely"


def test_projectinitiation_the_low_quadrant_is_monitored(projectinitiation_stakeholder_monitor):
    obj = projectinitiation_stakeholder_monitor
    assert (obj.influence, obj.interest) == ("medium", "low")
    assert obj.engagement_strategy == "monitor"
    assert obj.get_engagement_strategy_display() == "Monitor"


@pytest.mark.parametrize("influence,interest,label", [
    ("high", "high", "Manage Closely"),
    ("high", "low", "Keep Satisfied"),
    ("low", "high", "Keep Informed"),
    ("low", "low", "Monitor"),
])
def test_projectinitiation_every_quadrant_has_a_label(influence, interest, label):
    shell = ProjectStakeholder(influence=influence, interest=interest)
    assert shell.get_engagement_strategy_display() == label


def test_projectinitiation_the_engagement_label_getter_is_hand_written():
    """Django only generates ``get_FOO_display`` for real FIELDS with choices. Without the
    hand-written method the grid column renders empty at HTTP 200 - the L7/L8 failure mode on a
    column that looks like it worked."""
    assert "get_engagement_strategy_display" in ProjectStakeholder.__dict__
    assert callable(ProjectStakeholder.__dict__["get_engagement_strategy_display"])


def test_projectinitiation_the_engagement_label_tracks_a_live_edit(
        projectinitiation_stakeholder_a):
    obj = projectinitiation_stakeholder_a
    obj.interest = "low"
    assert obj.engagement_strategy == "keep_satisfied"
    assert obj.get_engagement_strategy_display() == "Keep Satisfied"
    obj.refresh_from_db()
    assert obj.engagement_strategy == "manage_closely"


# ==================================================================================================
# ProjectStakeholder.clean() - the rules save() does not enforce
# ==================================================================================================

def test_projectinitiation_a_stakeholder_must_name_a_party_or_a_user(
        projectinitiation_project_draft):
    shell = _projectinitiation_stakeholder_shell(projectinitiation_project_draft)
    with pytest.raises(ValidationError) as excinfo:
        shell.full_clean()
    assert NON_FIELD_ERRORS in excinfo.value.error_dict
    assert "identifies nobody" in str(excinfo.value.messages)


def test_projectinitiation_a_party_alone_satisfies_the_identity_rule(
        projectinitiation_project_draft, projectinitiation_person_a):
    shell = _projectinitiation_stakeholder_shell(
        projectinitiation_project_draft, party=projectinitiation_person_a)
    assert shell.full_clean() is None


def test_projectinitiation_a_user_alone_satisfies_the_identity_rule(
        projectinitiation_project_draft, member_user):
    shell = _projectinitiation_stakeholder_shell(
        projectinitiation_project_draft, user=member_user)
    assert shell.full_clean() is None


def test_projectinitiation_clean_refuses_a_duplicate_party_and_scope(
        projectinitiation_stakeholder_a, projectinitiation_project_draft,
        projectinitiation_party_a):
    """The friendly half of the ``(tenant, project, party, raci_scope)`` constraint: clean()
    answers before the database raises an IntegrityError 500."""
    shell = _projectinitiation_stakeholder_shell(
        projectinitiation_project_draft, party=projectinitiation_party_a,
        raci_scope="charter approval")
    with pytest.raises(ValidationError) as excinfo:
        shell.full_clean()
    assert NON_FIELD_ERRORS in excinfo.value.error_dict
    assert "double-count" in str(excinfo.value.messages)


def test_projectinitiation_clean_allows_the_same_party_on_a_second_scope(
        projectinitiation_stakeholder_a, projectinitiation_project_draft,
        projectinitiation_party_a):
    shell = _projectinitiation_stakeholder_shell(
        projectinitiation_project_draft, party=projectinitiation_party_a,
        raci_scope="vendor selection", raci_role="c")
    assert shell.full_clean() is None


def test_projectinitiation_clean_does_not_flag_a_row_against_itself(
        projectinitiation_stakeholder_a):
    """``exclude(pk=self.pk)`` - editing a saved row in place must not report it as its own
    duplicate, or no stakeholder could ever be edited."""
    obj = projectinitiation_stakeholder_a
    obj.notes = "Re-confirmed at the steering group."
    assert obj.full_clean() is None
    obj.save()
    obj.refresh_from_db()
    assert obj.notes == "Re-confirmed at the steering group."


def test_projectinitiation_clean_scopes_the_duplicate_check_to_one_project(
        projectinitiation_stakeholder_a, tenant_a, projectinitiation_party_a):
    other = _projectinitiation_project(tenant_a, name="Unrelated project", code="UNR-01")
    shell = _projectinitiation_stakeholder_shell(
        other, party=projectinitiation_party_a, raci_scope="charter approval")
    assert shell.full_clean() is None


def test_projectinitiation_clean_scopes_the_duplicate_check_to_one_tenant(
        projectinitiation_stakeholder_b, projectinitiation_project_b,
        projectinitiation_party_b, tenant_b):
    """Tenant B's own duplicate is still refused inside tenant B - the scoping narrows the check,
    it does not disable it."""
    shell = _projectinitiation_stakeholder_shell(
        projectinitiation_project_b, party=projectinitiation_party_b,
        raci_scope=projectinitiation_stakeholder_b.raci_scope)
    with pytest.raises(ValidationError):
        shell.full_clean()


def test_projectinitiation_save_does_not_run_clean(projectinitiation_project_draft):
    """Django's contract, pinned because the register depends on it: ``save()`` never calls
    ``clean()``, which is why the identity rule has to be enforced by the form (and why the
    conftest factory mints a party when the caller names nobody)."""
    shell = _projectinitiation_stakeholder_shell(projectinitiation_project_draft)
    shell.save()
    assert shell.pk is not None
    assert shell.party_id is None and shell.user_id is None


# ==================================================================================================
# ProjectKickoff - vocabulary, defaults, __str__
# ==================================================================================================

def test_projectinitiation_kickoff_agenda_template_choices_are_the_four_documented():
    assert _projectinitiation_values(ProjectKickoff.AGENDA_TEMPLATE_CHOICES) == [
        "standard", "agile", "client_facing", "custom"]


def test_projectinitiation_kickoff_status_choices_are_the_four_documented():
    assert _projectinitiation_values(ProjectKickoff.STATUS_CHOICES) == [
        "planned", "scheduled", "held", "completed"]


def test_projectinitiation_kickoff_defaults_are_the_documented_ones(tenant_a):
    project = _projectinitiation_project(tenant_a)
    obj = ProjectKickoff(tenant=tenant_a, project=project)
    obj.save()
    obj.refresh_from_db()
    assert obj.number == "PKO-00001"
    assert obj.agenda_template == "standard"
    assert obj.status == "planned"
    assert obj.meeting_date is None
    assert obj.location_or_link == "" and obj.agenda == ""
    assert obj.attendee_summary == "" and obj.onboarding_notes == "" and obj.notes == ""
    assert obj.baseline_acknowledged_at is None and obj.baseline_acknowledged_by_id is None
    assert obj.completed_at is None and obj.created_by_id is None
    assert obj.attendee_count == 0


def test_projectinitiation_kickoff_str_chains_through_the_project(
        projectinitiation_kickoff_planned):
    """The chained ``__str__`` is exactly why the register select_relates the project - a list
    that renders this without it is an N+1."""
    obj = projectinitiation_kickoff_planned
    project = obj.project
    assert str(obj) == (f"{obj.number} {_PROJECTINITIATION_DASH} {project.number} "
                        f"{_PROJECTINITIATION_DASH} {project.name} (Planned)")


def test_projectinitiation_kickoff_str_reads_the_current_status(
        projectinitiation_kickoff_completed):
    assert str(projectinitiation_kickoff_completed).endswith("(Completed)")


def test_projectinitiation_kickoff_ceremony_stamps_are_not_operator_writable():
    non_editable = _projectinitiation_non_editable(ProjectKickoff)
    assert {"number", "baseline_acknowledged_at", "baseline_acknowledged_by", "completed_at",
            "created_by", "created_at", "updated_at"} <= non_editable
    assert not non_editable & {"project", "meeting_date", "agenda", "status"}


def test_projectinitiation_kickoff_project_fk_cascades(tenant_a):
    project = _projectinitiation_project(tenant_a)
    kickoff = _projectinitiation_kickoff(project)
    field = ProjectKickoff._meta.get_field("project")
    assert field.remote_field.related_name == "kickoffs"
    assert field.remote_field.on_delete.__name__ == "CASCADE"
    project.delete()
    assert not ProjectKickoff.objects.filter(pk=kickoff.pk).exists()


def test_projectinitiation_stakeholder_project_fk_cascades():
    field = ProjectStakeholder._meta.get_field("project")
    assert field.remote_field.related_name == "stakeholders"
    assert field.remote_field.on_delete.__name__ == "CASCADE"
    assert field.null is False


# ==================================================================================================
# ProjectKickoff.attendee_count - the property, and the annotation that has to agree with it
# ==================================================================================================

def test_projectinitiation_attendee_count_is_derived_never_a_column():
    with pytest.raises(FieldDoesNotExist):
        ProjectKickoff._meta.get_field("attendee_count")
    assert isinstance(ProjectKickoff.attendee_count, property)


def test_projectinitiation_attendee_count_counts_only_the_attending(
        projectinitiation_kickoff_with_attendees):
    obj = projectinitiation_kickoff_with_attendees
    assert obj.project.stakeholders.count() == 3
    assert obj.attendee_count == 2


def test_projectinitiation_attendee_count_agrees_with_the_annotation(
        projectinitiation_kickoff_with_attendees, tenant_a):
    """The registers annotate ``attendee_total`` because ``attendee_count`` is a data descriptor.
    Two names, one number - if they ever disagree the list and the detail page disagree."""
    row = _projectinitiation_annotated_kickoffs(tenant_a).get(
        pk=projectinitiation_kickoff_with_attendees.pk)
    assert row.attendee_total == projectinitiation_kickoff_with_attendees.attendee_count == 2


def test_projectinitiation_annotating_over_the_property_raises(
        projectinitiation_kickoff_with_attendees, tenant_a):
    """The reason the annotation is called ``attendee_total``: a property with no setter cannot
    take an annotated value, and the failure is at row-materialisation time, not at query build
    time - i.e. in production, not in a check."""
    qs = ProjectKickoff.objects.filter(tenant=tenant_a).annotate(
        attendee_count=Count("project__stakeholders"))
    with pytest.raises(AttributeError):
        list(qs)


def test_projectinitiation_attendee_count_follows_a_live_change(
        projectinitiation_kickoff_with_attendees):
    obj = projectinitiation_kickoff_with_attendees
    obj.project.stakeholders.update(attending_kickoff=True)
    assert obj.attendee_count == 3
    obj.project.stakeholders.update(attending_kickoff=False)
    assert obj.attendee_count == 0


def test_projectinitiation_attendee_count_is_zero_without_a_project():
    assert ProjectKickoff().attendee_count == 0


def test_projectinitiation_attendee_count_ignores_another_projects_stakeholders(
        projectinitiation_kickoff_with_attendees, tenant_a):
    other = _projectinitiation_project(tenant_a, name="Noise project", code="NOI-01")
    _projectinitiation_fill_stakeholders(other, 2, attending_kickoff=True)
    assert projectinitiation_kickoff_with_attendees.attendee_count == 2


def test_projectinitiation_the_annotation_costs_one_query_for_the_whole_page(
        tenant_a, django_assert_num_queries):
    """One aggregate for every row - the property would be a COUNT per row, which is what the
    annotation exists to avoid."""
    kickoffs = _projectinitiation_fill_kickoffs(tenant_a, 3)
    for kickoff in kickoffs:
        _projectinitiation_stakeholder(kickoff.project, attending_kickoff=True)
    with django_assert_num_queries(1):
        rows = list(_projectinitiation_annotated_kickoffs(tenant_a))
    assert [row.attendee_total for row in rows] == [1, 1, 1]


def test_projectinitiation_an_aggregate_drops_meta_ordering(tenant_a):
    """Django ignores ``Meta.ordering`` in a GROUP BY query, which is why the annotated registers
    re-state ``.order_by("-created_at", "-id")``. Without it the newest-first contract silently
    becomes whatever the database returns."""
    _projectinitiation_fill_kickoffs(tenant_a, 2)
    unordered = ProjectKickoff.objects.filter(tenant=tenant_a).annotate(
        attendee_total=Count("project__stakeholders"))
    assert "ORDER BY" not in str(unordered.query)
    assert "ORDER BY" in str(_projectinitiation_annotated_kickoffs(tenant_a).query)


def test_projectinitiation_the_annotated_page_still_reads_newest_first(tenant_a):
    oldest, newest = _projectinitiation_fill_kickoffs(tenant_a, 2)
    rows = list(_projectinitiation_annotated_kickoffs(tenant_a))
    assert [row.pk for row in rows] == [newest.pk, oldest.pk]
