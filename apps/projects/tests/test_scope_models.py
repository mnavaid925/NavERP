"""Projects 7.7 Scope & Requirements Management — MODEL tests (step 2 of 6).

Phase 6 runs six steps: **step 1** lands the ``scope_*`` fixture block in ``conftest.py``, **this
file is step 2** (the model lane), and steps 3–5 own the form / view / security lanes. So this
module pins the claims the four 7.7 tables would be worthless without, and nothing about HTTP.

* **``TenantNumbered``** mints ``REQ-/SCI-/SCR-/SVR-`` once, per tenant, per MODEL — the same
  per-workspace independence 7.1/7.4/7.5 proved. Two rows in one tenant advance; tenant B's
  register starts its own ``…-00001``; a second ``save()`` never re-numbers.
* **The lifecycle is verb-driven, so the predicates are DERIVED, never columns.** Every property in
  the test contract (``is_approved``/``is_verified``/``is_traced``/``is_open``/``is_locked``/
  ``badge_class``, ``is_boundary``/``is_review_overdue``, ``impact_weight``/``is_high_impact``,
  ``is_decided``/``is_accepted``) is asserted per state — the truth table, not a re-implementation.
* **The high-impact rule has three independent triggers** (``HIGH_COST`` 50000 /
  ``HIGH_SCHEDULE_DAYS`` 10 / ``quality_impact == "high"``) plus the one-unit-under boundary row
  (``scope_change_sub_threshold``: 49999.99 / 9 days / medium) — all four cases pinned separately
  so a torn threshold fails one diagnostic test, not a 40-assert monster.
* **``clean()`` is the same-project guard layer**: a ``wbs_node``/``parent``/``requirement``/``risk``
  from another project is refused at the model, not just by the scoped dropdowns. Each guard is
  asserted by the FIELD it is keyed to, and asserted NOT to fire when the FK is null.
* **Cross-module string FKs resolve** (L36): ``risk`` → 7.5's ``ProjectRisk``, ``wbs_node`` → 7.2's
  ``ProjectTask``, ``source_party`` → ``core.Party`` — plus the reverse ``related_name`` set the
  views/templates navigate.
* **The C1 fix is pinned**: ``ScopeItem.STATUS_CHOICES`` includes ``violated`` and ``is_locked``
  covers ``realized|retired|violated`` — the state exists, is creatable, and is frozen evidence.

Determinism (L16): every date basis is ``_scope_today()`` (``timezone.localdate()``) — the same
clock ``ScopeItem.is_review_overdue`` reads, so no UTC-offset flake.

Naming (mandatory): every test is ``test_scope_*``, every module-level helper ``_scope_*`` — the
``projectinitiation_``/``planning_``/``resource_``/``cost_``/``risk_`` namespaces stay untouched.
Only the conftest FACTORY functions are imported (never another lane's fixtures). Flat functions,
house style — no Test* classes.

Scope: models only. Forms, views/urls and permissions belong to the other three lanes.
"""
from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.accounts.models import User
from apps.core.models import Party, Tenant
from apps.projects.models import (
    ProjectRisk,
    ProjectTask,
    Requirement,
    ScopeChangeRequest,
    ScopeItem,
    ScopeVerification,
)
from apps.projects.tests.conftest import (
    SCOPE_PAGE_SIZE,
    _scope_change,
    _scope_fill_changes,
    _scope_fill_items,
    _scope_fill_requirements,
    _scope_item,
    _scope_month_start,
    _scope_requirement,
    _scope_today,
    _scope_verification,
)

D = Decimal

#: The theme.css badge classes ``STATUS_BANDS``/``badge_class`` may name (L33). A band value
#: outside this set is a template that renders an unstyled pill.
_THEME_BADGES = {"green", "amber", "red", "info", "muted", "slate"}

#: ``TenantNumbered`` number shape: ``REQ-`` + exactly five zero-padded digits.
_NUMBER_WIDTH = 5


def _scope_values(choices):
    """The VALUE set of a choices list — what the column actually stores."""
    return [value for value, _label in choices]


def _scope_new_tenant(name):
    """A fresh tenant with its own number sequence (L9 — a second workspace is the only way to
    prove the per-tenant counter is per-tenant)."""
    return Tenant.objects.create(name=name, slug=name.lower().replace(" ", "-"))


def _scope_user(tenant, name):
    """A plain user in ``tenant`` — used for the per-tenant ``number`` and ``__str__`` assertions
    where a root fixture actor would add nothing."""
    return User.objects.create_user(
        email=f"{name}@example.com", username=name, password="TestPass123!", tenant=tenant)


def _scope_risk(tenant, project, name="Scope-motivating risk"):
    """A 7.5 ``ProjectRisk`` via ``ProjectRisk.objects.create`` — the ``risk`` FK's target. Built
    inline rather than pulled from 7.5's fixtures: this lane imports factories, not fixtures."""
    return ProjectRisk.objects.create(
        tenant=tenant, project=project, title=name, description="The risk behind the change.",
        probability=3, impact=3, response_strategy="mitigate")


def _scope_host(tenant, name):
    """A minimal host project for a brand-new tenant — ``TenantNumbered`` needs a tenant, and the
    number sequence is per-tenant-per-model, so the project itself is immaterial."""
    from apps.projects.models import Project
    return Project.objects.create(tenant=tenant, name=name, status="active")


#: model -> the factory that mints a row on a given tenant/project (the per-tenant counter probe).
_SCOPE_BUILDERS = {
    Requirement: _scope_requirement,
    ScopeItem: _scope_item,
    ScopeChangeRequest: _scope_change,
    ScopeVerification: _scope_verification,
}


# ==============================================================================================
# Numbering — TenantNumbered across the four scope models
# ==============================================================================================

def test_scope_requirement_mints_req_number(tenant_a, scope_project_a):
    req = _scope_requirement(tenant_a, scope_project_a)
    assert req.number.startswith("REQ-"), f"contract pins REQ- prefix, got {req.number!r}"
    assert len(req.number) == 4 + _NUMBER_WIDTH
    assert req.number.split("-")[1].isdigit()


def test_scope_item_mints_sci_number(tenant_a, scope_project_a):
    item = _scope_item(tenant_a, scope_project_a)
    assert item.number.startswith("SCI-"), f"contract pins SCI- prefix, got {item.number!r}"
    assert len(item.number) == 4 + _NUMBER_WIDTH


def test_scope_change_mints_scr_number(tenant_a, scope_project_a):
    change = _scope_change(tenant_a, scope_project_a)
    assert change.number.startswith("SCR-"), f"contract pins SCR- prefix, got {change.number!r}"
    assert len(change.number) == 4 + _NUMBER_WIDTH


def test_scope_verification_mints_svr_number(tenant_a, scope_project_a):
    ver = _scope_verification(tenant_a, scope_project_a)
    assert ver.number.startswith("SVR-"), f"contract pins SVR- prefix, got {ver.number!r}"
    assert len(ver.number) == 4 + _NUMBER_WIDTH


def test_scope_number_is_zero_padded_to_five(tenant_a, scope_project_a):
    """The first row of a tenant reads ``…-00001`` — the width the register columns assume."""
    req = _scope_requirement(tenant_a, scope_project_a)
    assert req.number.split("-")[1] == "00001"


def test_scope_requirement_numbers_advance_in_one_tenant(tenant_a, scope_project_a):
    first = _scope_requirement(tenant_a, scope_project_a)
    second = _scope_requirement(tenant_a, scope_project_a)
    assert int(second.number.split("-")[1]) == int(first.number.split("-")[1]) + 1


def test_scope_item_numbers_advance_in_one_tenant(tenant_a, scope_project_a):
    first = _scope_item(tenant_a, scope_project_a)
    second = _scope_item(tenant_a, scope_project_a)
    assert int(second.number.split("-")[1]) == int(first.number.split("-")[1]) + 1


def test_scope_change_numbers_advance_in_one_tenant(tenant_a, scope_project_a):
    first = _scope_change(tenant_a, scope_project_a)
    second = _scope_change(tenant_a, scope_project_a)
    assert int(second.number.split("-")[1]) == int(first.number.split("-")[1]) + 1


def test_scope_verification_numbers_advance_in_one_tenant(tenant_a, scope_project_a):
    first = _scope_verification(tenant_a, scope_project_a)
    second = _scope_verification(tenant_a, scope_project_a)
    assert int(second.number.split("-")[1]) == int(first.number.split("-")[1]) + 1


@pytest.mark.parametrize("model", [Requirement, ScopeItem, ScopeChangeRequest, ScopeVerification])
def test_scope_number_sequence_is_per_tenant(db, model):
    """A brand-new tenant starts its own counter at ``00001`` — the per-tenant counter the
    ``unique_together`` alone would not prove."""
    first_tenant = _scope_new_tenant("Seq One")
    second_tenant = _scope_new_tenant("Seq Two")
    project = _scope_host(first_tenant, "Seq host one")
    other_project = _scope_host(second_tenant, "Seq host two")
    builder = _SCOPE_BUILDERS[model]
    builder(first_tenant, project)
    row = builder(second_tenant, other_project)
    assert row.number.split("-")[1] == "00001", (
        f"a second tenant must start its own sequence, got {row.number!r}")


def test_scope_four_models_mint_their_own_prefix(tenant_a, scope_project_a):
    assert _scope_requirement(tenant_a, scope_project_a).number.startswith("REQ-")
    assert _scope_item(tenant_a, scope_project_a).number.startswith("SCI-")
    assert _scope_change(tenant_a, scope_project_a).number.startswith("SCR-")
    assert _scope_verification(tenant_a, scope_project_a).number.startswith("SVR-")


def test_scope_save_never_renumbers(tenant_a, scope_project_a):
    req = _scope_requirement(tenant_a, scope_project_a)
    minted = req.number
    req.title = "Renamed after the mint"
    req.save()
    req.refresh_from_db()
    assert req.number == minted, "TenantNumbered mints once — a second save must not re-number"


@pytest.mark.parametrize("model", [Requirement, ScopeItem, ScopeChangeRequest, ScopeVerification])
def test_scope_unique_together_declared_on_all_four(model):
    assert model._meta.unique_together == (("tenant", "number"),), (
        f"contract pins unique_together (tenant, number) on {model.__name__}")


def test_scope_requirement_duplicate_number_rejected_by_full_clean(tenant_a, scope_project_a):
    first = _scope_requirement(tenant_a, scope_project_a)
    dup = Requirement(
        tenant=tenant_a, project=scope_project_a, title="Clashing number",
        description="Same number as its sibling.", number=first.number)
    with pytest.raises(ValidationError) as exc_info:
        dup.full_clean()
    assert exc_info.value.message_dict, "the duplicate pair must be keyed to a field"


def test_scope_item_duplicate_number_rejected_by_full_clean(tenant_a, scope_project_a):
    first = _scope_item(tenant_a, scope_project_a)
    dup = ScopeItem(tenant=tenant_a, project=scope_project_a, statement="Clashing number",
                    number=first.number)
    with pytest.raises(ValidationError):
        dup.full_clean()


def test_scope_change_duplicate_number_rejected_by_full_clean(tenant_a, scope_project_a):
    first = _scope_change(tenant_a, scope_project_a)
    dup = ScopeChangeRequest(tenant=tenant_a, project=scope_project_a, title="Clashing number",
                             description="Same number as its sibling.", number=first.number)
    with pytest.raises(ValidationError):
        dup.full_clean()


def test_scope_verification_duplicate_number_rejected_by_full_clean(tenant_a, scope_project_a):
    first = _scope_verification(tenant_a, scope_project_a)
    dup = ScopeVerification(tenant_a, scope_project_a, deliverable="Clashing number",
                            number=first.number)
    with pytest.raises(ValidationError):
        dup.full_clean()


def test_scope_requirement_duplicate_number_rejected_by_db(tenant_a, scope_project_a):
    first = _scope_requirement(tenant_a, scope_project_a)
    dup = _scope_requirement(tenant_a, scope_project_a)
    dup.number = first.number
    with transaction.atomic():
        with pytest.raises(IntegrityError):
            dup.save()


# ==============================================================================================
# Requirement — choices and the STATUS_BANDS map
# ==============================================================================================

def test_scope_requirement_type_choices_exact():
    assert _scope_values(Requirement.REQUIREMENT_TYPE_CHOICES) == [
        "functional", "non_functional", "business", "technical", "regulatory", "interface"]


def test_scope_requirement_elicitation_choices_exact():
    assert _scope_values(Requirement.ELICITATION_METHOD_CHOICES) == [
        "interview", "workshop", "survey", "user_story", "observation",
        "document_analysis", "prototype", "brainstorm"]


def test_scope_requirement_priority_choices_are_moscow():
    assert _scope_values(Requirement.PRIORITY_CHOICES) == ["must", "should", "could", "wont"]


def test_scope_requirement_status_choices_exact():
    assert _scope_values(Requirement.STATUS_CHOICES) == [
        "draft", "submitted", "approved", "rejected", "implemented", "verified", "deferred"]


def test_scope_requirement_verification_method_choices_exact():
    assert _scope_values(Requirement.VERIFICATION_METHOD_CHOICES) == [
        "inspection", "analysis", "demonstration", "test"]


def test_scope_requirement_status_bands_cover_every_status():
    bands = Requirement.STATUS_BANDS
    every_status = set(_scope_values(Requirement.STATUS_CHOICES))
    assert set(bands) == every_status, (
        f"STATUS_BANDS must have a band for every status: missing {every_status - set(bands)}")


def test_scope_requirement_status_bands_are_theme_badges():
    bad = set(Requirement.STATUS_BANDS.values()) - _THEME_BADGES
    assert not bad, f"band values outside the theme.css allow-list (L33): {bad}"


def test_scope_requirement_status_defaults_to_draft(tenant_a, scope_project_a):
    raw = Requirement(tenant=tenant_a, project=scope_project_a, title="Defaults",
                      description="Defaults.")
    assert raw.status == "draft"
    assert raw.requirement_type == "functional"
    assert raw.elicitation_method == "interview"
    assert raw.priority == "must"
    assert raw.verification_method == "test"


# ==============================================================================================
# Requirement — derived predicates, one fixture per state
# ==============================================================================================

@pytest.mark.parametrize("status,expected", [
    ("draft", False), ("submitted", False), ("approved", True), ("rejected", False),
    ("implemented", True), ("verified", True), ("deferred", False)])
def test_scope_requirement_is_approved_per_state(tenant_a, scope_project_a, status, expected):
    req = _scope_requirement(tenant_a, scope_project_a, status=status)
    assert req.is_approved is expected, f"is_approved({status}) must be {expected}"


@pytest.mark.parametrize("status,expected", [
    ("draft", False), ("submitted", False), ("approved", False), ("rejected", False),
    ("implemented", False), ("verified", True), ("deferred", False)])
def test_scope_requirement_is_verified_per_state(tenant_a, scope_project_a, status, expected):
    req = _scope_requirement(tenant_a, scope_project_a, status=status)
    assert req.is_verified is expected, f"is_verified({status}) must be {expected}"


@pytest.mark.parametrize("status,expected", [
    ("draft", True), ("submitted", True), ("approved", True), ("rejected", False),
    ("implemented", True), ("verified", False), ("deferred", False)])
def test_scope_requirement_is_open_per_state(tenant_a, scope_project_a, status, expected):
    req = _scope_requirement(tenant_a, scope_project_a, status=status)
    assert req.is_open is expected, f"is_open({status}) must be {expected}"


@pytest.mark.parametrize("status,expected", [
    ("draft", False), ("submitted", False), ("approved", False), ("rejected", False),
    ("implemented", False), ("verified", True), ("deferred", False)])
def test_scope_requirement_is_locked_per_state(tenant_a, scope_project_a, status, expected):
    req = _scope_requirement(tenant_a, scope_project_a, status=status)
    assert req.is_locked is expected, f"is_locked({status}) must be {expected}"


def test_scope_requirement_is_traced_needs_a_wbs_node(tenant_a, scope_project_a):
    untraced = _scope_requirement(tenant_a, scope_project_a)  # factory default: wbs_node=None
    assert untraced.is_traced is False, "the factory default is the coverage gap"


def test_scope_requirement_is_traced_when_wbs_node_set(tenant_a, scope_project_a, scope_wbs_a):
    traced = _scope_requirement(tenant_a, scope_project_a, wbs_node=scope_wbs_a)
    assert traced.is_traced is True


def test_scope_requirement_badge_class_reads_status_bands(tenant_a, scope_project_a):
    draft = _scope_requirement(tenant_a, scope_project_a, status="draft")
    verified = _scope_requirement(tenant_a, scope_project_a, status="verified")
    assert draft.badge_class == Requirement.STATUS_BANDS["draft"]
    assert verified.badge_class == Requirement.STATUS_BANDS["verified"]


def test_scope_requirement_lifecycle_fixtures_hold_their_states(
        scope_requirement_draft, scope_requirement_submitted, scope_requirement_approved,
        scope_requirement_implemented, scope_requirement_verified, scope_requirement_rejected):
    """The conftest lifecycle fixtures ARE the states the five verbs branch on — the model
    predicates read them the way the contract's gate table assumes."""
    assert scope_requirement_draft.is_open and not scope_requirement_draft.is_approved
    assert scope_requirement_submitted.is_open and not scope_requirement_submitted.is_approved
    assert scope_requirement_approved.is_approved and not scope_requirement_approved.is_locked
    assert scope_requirement_implemented.is_approved and \
        not scope_requirement_implemented.is_locked
    assert scope_requirement_verified.is_verified and scope_requirement_verified.is_locked
    assert not scope_requirement_rejected.is_open


# ==============================================================================================
# Requirement — clean() same-project guards
# ==============================================================================================

def test_scope_requirement_clean_rejects_foreign_wbs_node(tenant_a, scope_project_a, scope_wbs_b):
    req = Requirement(tenant=tenant_a, project=scope_project_a, title="Cross project",
                      description="Cross project.", wbs_node=scope_wbs_b)
    with pytest.raises(ValidationError) as exc_info:
        req.clean()
    assert "wbs_node" in exc_info.value.message_dict


def test_scope_requirement_clean_rejects_foreign_parent(tenant_a, scope_project_a,
                                                        scope_requirement_b):
    req = Requirement(tenant=tenant_a, project=scope_project_a, title="Cross parent",
                      description="Cross parent.", parent=scope_requirement_b)
    with pytest.raises(ValidationError) as exc_info:
        req.clean()
    assert "parent" in exc_info.value.message_dict


def test_scope_requirement_clean_allows_same_project_wbs_node(tenant_a, scope_project_a,
                                                              scope_wbs_a):
    req = Requirement(tenant=tenant_a, project=scope_project_a, title="Same project",
                      description="Same project.", wbs_node=scope_wbs_a)
    req.clean()  # no raise


def test_scope_requirement_clean_allows_same_project_parent(tenant_a, scope_project_a):
    parent = _scope_requirement(tenant_a, scope_project_a, title="The epic")
    child = Requirement(tenant=tenant_a, project=scope_project_a, title="The story",
                        description="The story.", parent=parent)
    child.clean()  # no raise


def test_scope_requirement_clean_allows_null_wbs_node_and_parent(tenant_a, scope_project_a):
    """Both FKs are nullable — an untraced, root-level requirement is legal, not a guard hit."""
    req = Requirement(tenant=tenant_a, project=scope_project_a, title="Untraced",
                      description="Untraced.", wbs_node=None, parent=None)
    req.clean()  # no raise


# ==============================================================================================
# Requirement — the FK targets behind the string FKs
# ==============================================================================================

def test_scope_requirement_wbs_node_targets_project_task():
    field = Requirement._meta.get_field("wbs_node")
    assert field.related_model is ProjectTask, "wbs_node is a string FK into 7.2's ProjectTask"


def test_scope_requirement_source_party_targets_core_party():
    field = Requirement._meta.get_field("source_party")
    assert field.related_model is Party, "source_party is a string FK into core.Party"


def test_scope_requirement_owner_reverse_accessor(tenant_a, scope_project_a):
    owner = _scope_user(tenant_a, "scope_owner_a")
    req = _scope_requirement(tenant_a, scope_project_a, owner=owner)
    assert list(owner.owned_requirements.all()) == [req]


def test_scope_requirement_requested_by_reverse_accessor(tenant_a, scope_project_a):
    requester = _scope_user(tenant_a, "scope_requester_a")
    req = _scope_requirement(tenant_a, scope_project_a, requested_by=requester)
    assert list(requester.requested_requirements.all()) == [req]


def test_scope_requirement_wbs_node_reverse_accessor(tenant_a, scope_project_a, scope_wbs_a):
    req = _scope_requirement(tenant_a, scope_project_a, wbs_node=scope_wbs_a)
    assert list(scope_wbs_a.requirements.all()) == [req]


def test_scope_requirement_source_party_reverse_accessor(tenant_a, scope_project_a,
                                                         scope_party_a):
    req = _scope_requirement(tenant_a, scope_project_a, source_party=scope_party_a)
    assert list(scope_party_a.requirements.all()) == [req]


def test_scope_requirement_project_and_children_reverse_accessors(tenant_a, scope_project_a):
    parent = _scope_requirement(tenant_a, scope_project_a, title="The epic")
    child = _scope_requirement(tenant_a, scope_project_a, title="The story", parent=parent)
    assert set(scope_project_a.requirements.all()) == {parent, child}
    assert list(parent.children.all()) == [child]


# ==============================================================================================
# ScopeItem — choices (the post-C1 status set) and BOUNDARY_TYPES
# ==============================================================================================

def test_scope_item_type_choices_exact():
    assert _scope_values(ScopeItem.ITEM_TYPE_CHOICES) == [
        "in_scope", "out_of_scope", "assumption", "constraint", "dependency"]


def test_scope_item_status_choices_include_violated():
    """C1's fix: the third closed state exists, so a violated assumption is representable."""
    values = _scope_values(ScopeItem.STATUS_CHOICES)
    assert values == ["open", "validated", "realized", "retired", "violated"], (
        f"contract pins the post-C1 status set, got {values!r}")


def test_scope_item_impact_area_choices_exact():
    assert _scope_values(ScopeItem.IMPACT_AREA_CHOICES) == [
        "schedule", "cost", "quality", "scope", "resource", "compliance"]


def test_scope_item_boundary_types_exact():
    assert ScopeItem.BOUNDARY_TYPES == {"in_scope", "out_of_scope"}


def test_scope_item_status_max_length_holds_violated():
    assert ScopeItem._meta.get_field("status").max_length >= len("violated")


# ==============================================================================================
# ScopeItem — derived predicates
# ==============================================================================================

@pytest.mark.parametrize("item_type,expected", [
    ("in_scope", True), ("out_of_scope", True), ("assumption", False),
    ("constraint", False), ("dependency", False)])
def test_scope_item_is_boundary_per_type(tenant_a, scope_project_a, item_type, expected):
    item = _scope_item(tenant_a, scope_project_a, item_type=item_type)
    assert item.is_boundary is expected, f"is_boundary({item_type}) must be {expected}"


@pytest.mark.parametrize("status,expected", [
    ("open", True), ("validated", True), ("realized", False), ("retired", False),
    ("violated", False)])
def test_scope_item_is_open_per_state(tenant_a, scope_project_a, status, expected):
    item = _scope_item(tenant_a, scope_project_a, status=status)
    assert item.is_open is expected, f"is_open({status}) must be {expected}"


@pytest.mark.parametrize("status,expected", [
    ("open", False), ("validated", False), ("realized", True), ("retired", True),
    ("violated", True)])
def test_scope_item_is_locked_per_state(tenant_a, scope_project_a, status, expected):
    item = _scope_item(tenant_a, scope_project_a, status=status)
    assert item.is_locked is expected, f"is_locked({status}) must be {expected}"


def test_scope_item_lifecycle_fixtures_hold_their_states(
        scope_item_open, scope_item_validated, scope_item_realized, scope_item_violated):
    assert scope_item_open.is_open and not scope_item_open.is_locked
    assert scope_item_validated.is_open and not scope_item_validated.is_locked
    assert not scope_item_realized.is_open and scope_item_realized.is_locked
    assert not scope_item_violated.is_open and scope_item_violated.is_locked


def test_scope_item_review_overdue_past_date_still_open(tenant_a, scope_project_a):
    item = _scope_item(tenant_a, scope_project_a, status="open",
                       review_date=_scope_today() - timedelta(days=1))
    assert item.is_review_overdue is True


def test_scope_item_review_overdue_not_past(tenant_a, scope_project_a):
    item = _scope_item(tenant_a, scope_project_a, status="open",
                       review_date=_scope_today() + timedelta(days=1))
    assert item.is_review_overdue is False


def test_scope_item_review_overdue_false_today(tenant_a, scope_project_a):
    """Today is not yet past — the predicate is strict ``<``."""
    item = _scope_item(tenant_a, scope_project_a, status="open", review_date=_scope_today())
    assert item.is_review_overdue is False


def test_scope_item_review_overdue_false_without_review_date(tenant_a, scope_project_a):
    item = _scope_item(tenant_a, scope_project_a, status="open", review_date=None)
    assert item.is_review_overdue is False


def test_scope_item_review_overdue_false_when_closed_though_overdue(tenant_a, scope_project_a):
    """A realized row with a past review date is NOT overdue — nothing left to review."""
    item = _scope_item(tenant_a, scope_project_a, status="realized",
                       review_date=_scope_today() - timedelta(days=30))
    assert item.is_review_overdue is False


def test_scope_item_review_overdue_validated_row(tenant_a, scope_project_a):
    """``validated`` is still live, so a past review date counts."""
    item = _scope_item(tenant_a, scope_project_a, status="validated",
                       review_date=_scope_today() - timedelta(days=3))
    assert item.is_review_overdue is True


def test_scope_item_owner_reverse_accessor(tenant_a, scope_project_a):
    owner = _scope_user(tenant_a, "scope_item_owner_a")
    item = _scope_item(tenant_a, scope_project_a, owner=owner)
    assert list(owner.owned_scope_items.all()) == [item]


def test_scope_item_project_reverse_accessor(tenant_a, scope_project_a):
    item = _scope_item(tenant_a, scope_project_a)
    assert list(scope_project_a.scope_items.all()) == [item]


# ==============================================================================================
# ScopeItem — clean() same-project guard
# ==============================================================================================

def test_scope_item_clean_rejects_foreign_requirement(tenant_a, scope_project_a,
                                                      scope_requirement_b):
    item = ScopeItem(tenant=tenant_a, project=scope_project_a, statement="Cross project",
                     requirement=scope_requirement_b)
    with pytest.raises(ValidationError) as exc_info:
        item.clean()
    assert "requirement" in exc_info.value.message_dict


def test_scope_item_clean_allows_same_project_requirement(tenant_a, scope_project_a):
    req = _scope_requirement(tenant_a, scope_project_a)
    item = ScopeItem(tenant=tenant_a, project=scope_project_a, statement="Same project",
                     requirement=req)
    item.clean()  # no raise


def test_scope_item_clean_allows_null_requirement(tenant_a, scope_project_a):
    item = ScopeItem(tenant=tenant_a, project=scope_project_a, statement="Unattached",
                     requirement=None)
    item.clean()  # no raise — the FK is nullable


def test_scope_item_requirement_reverse_accessor(tenant_a, scope_project_a):
    req = _scope_requirement(tenant_a, scope_project_a)
    item = _scope_item(tenant_a, scope_project_a, requirement=req)
    assert list(req.scope_items.all()) == [item]


# ==============================================================================================
# ScopeChangeRequest — choices, the threshold constants and the quality weight map
# ==============================================================================================

def test_scope_change_source_choices_exact():
    assert _scope_values(ScopeChangeRequest.SOURCE_CHOICES) == [
        "internal", "client", "regulatory", "vendor", "technical"]


def test_scope_change_priority_choices_exact():
    assert _scope_values(ScopeChangeRequest.PRIORITY_CHOICES) == [
        "low", "medium", "high", "critical"]


def test_scope_change_quality_impact_choices_exact():
    assert _scope_values(ScopeChangeRequest.QUALITY_IMPACT_CHOICES) == [
        "none", "low", "medium", "high"]


def test_scope_change_status_choices_exact():
    assert _scope_values(ScopeChangeRequest.STATUS_CHOICES) == [
        "draft", "submitted", "under_review", "approved", "rejected", "implemented"]


def test_scope_change_quality_weight_map_exact():
    assert ScopeChangeRequest.QUALITY_WEIGHT == {"none": 0, "low": 1, "medium": 2, "high": 3}


def test_scope_change_high_thresholds_exact():
    assert ScopeChangeRequest.HIGH_COST == D("50000"), "contract pins HIGH_COST 50000"
    assert ScopeChangeRequest.HIGH_SCHEDULE_DAYS == 10, "contract pins HIGH_SCHEDULE_DAYS 10"


def test_scope_change_quality_weight_per_state(tenant_a, scope_project_a):
    weights = {"none": 0, "low": 1, "medium": 2, "high": 3}
    for quality, expected in weights.items():
        change = _scope_change(tenant_a, scope_project_a, quality_impact=quality)
        assert change.impact_weight == expected, (
            f"impact_weight({quality}) must be {expected}")


def test_scope_change_defaults_are_zero_impact(tenant_a, scope_project_a):
    change = _scope_change(tenant_a, scope_project_a)
    assert change.status == "draft"
    assert change.source == "internal"
    assert change.priority == "medium"
    assert change.cost_impact == D("0"), "the factory default is inert — never in the creep totals"
    assert change.schedule_impact_days is None
    assert change.quality_impact == "none"


# ==============================================================================================
# ScopeChangeRequest — is_high_impact, one trigger per test
# ==============================================================================================

def test_scope_change_high_impact_false_for_the_zero_impact_draft(tenant_a, scope_project_a):
    change = _scope_change(tenant_a, scope_project_a)
    assert change.is_high_impact is False


def test_scope_change_high_impact_true_on_cost_threshold(tenant_a, scope_project_a):
    change = _scope_change(tenant_a, scope_project_a, cost_impact=D("50000"))
    assert change.is_high_impact is True, "cost >= HIGH_COST is a trigger"


def test_scope_change_high_impact_true_on_cost_above_threshold(tenant_a, scope_project_a):
    change = _scope_change(tenant_a, scope_project_a, cost_impact=D("60000.00"))
    assert change.is_high_impact is True


def test_scope_change_high_impact_true_on_schedule_threshold(tenant_a, scope_project_a):
    change = _scope_change(tenant_a, scope_project_a, schedule_impact_days=10)
    assert change.is_high_impact is True, "schedule >= HIGH_SCHEDULE_DAYS is a trigger"


def test_scope_change_high_impact_true_on_quality_high(tenant_a, scope_project_a):
    change = _scope_change(tenant_a, scope_project_a, quality_impact="high")
    assert change.is_high_impact is True, "quality_impact == 'high' is a trigger"


def test_scope_change_high_impact_boundary_fixture_is_false(scope_change_sub_threshold):
    """The one-unit-under row: 49999.99 / 9 days / medium crosses NONE of the three."""
    change = scope_change_sub_threshold
    assert change.cost_impact == D("49999.99")
    assert change.schedule_impact_days == 9
    assert change.is_high_impact is False


def test_scope_change_high_impact_boundary_each_unit_below(tenant_a, scope_project_a):
    cost = _scope_change(tenant_a, scope_project_a, cost_impact=D("49999.99"))
    days = _scope_change(tenant_a, scope_project_a, schedule_impact_days=9)
    quality = _scope_change(tenant_a, scope_project_a, quality_impact="medium")
    assert cost.is_high_impact is False, "49999.99 is one cent under HIGH_COST"
    assert days.is_high_impact is False, "9 is one day under HIGH_SCHEDULE_DAYS"
    assert quality.is_high_impact is False, "medium is one step under high"


def test_scope_change_high_impact_fixture_is_true(scope_change_high_impact):
    assert scope_change_high_impact.is_high_impact is True


def test_scope_change_high_impact_ignores_a_null_schedule(tenant_a, scope_project_a):
    """``schedule_impact_days=None`` must be read as 0, not as a TypeError."""
    change = _scope_change(tenant_a, scope_project_a, schedule_impact_days=None,
                           cost_impact=D("1.00"))
    assert change.is_high_impact is False


@pytest.mark.parametrize("status,expected", [
    ("draft", True), ("submitted", True), ("under_review", True), ("approved", False),
    ("rejected", False), ("implemented", False)])
def test_scope_change_is_pending_per_state(tenant_a, scope_project_a, status, expected):
    change = _scope_change(tenant_a, scope_project_a, status=status)
    assert change.is_pending is expected, f"is_pending({status}) must be {expected}"


@pytest.mark.parametrize("status,expected", [
    ("draft", False), ("submitted", False), ("under_review", False), ("approved", True),
    ("rejected", False), ("implemented", True)])
def test_scope_change_is_approved_per_state(tenant_a, scope_project_a, status, expected):
    change = _scope_change(tenant_a, scope_project_a, status=status)
    assert change.is_approved is expected, f"is_approved({status}) must be {expected}"


@pytest.mark.parametrize("status,expected", [
    ("draft", False), ("submitted", False), ("under_review", False), ("approved", False),
    ("rejected", False), ("implemented", True)])
def test_scope_change_is_locked_per_state(tenant_a, scope_project_a, status, expected):
    change = _scope_change(tenant_a, scope_project_a, status=status)
    assert change.is_locked is expected, f"is_locked({status}) must be {expected}"


def test_scope_change_lifecycle_fixtures_hold_their_states(
        scope_change_draft, scope_change_approved, scope_change_implemented):
    assert scope_change_draft.is_pending and not scope_change_draft.is_locked
    assert scope_change_approved.is_approved and not scope_change_approved.is_locked
    assert scope_change_implemented.is_approved and scope_change_implemented.is_locked


def test_scope_change_cost_impact_is_decimal_14_2():
    field = ScopeChangeRequest._meta.get_field("cost_impact")
    assert field.max_digits == 14 and field.decimal_places == 2
    assert field.get_internal_type() == "DecimalField"


def test_scope_change_cost_impact_non_negative(tenant_a, scope_project_a):
    raw = ScopeChangeRequest(tenant=tenant_a, project=scope_project_a, title="Negative cost",
                             description="Negative cost.", cost_impact=D("-0.01"))
    with pytest.raises(ValidationError) as exc_info:
        raw.full_clean()
    assert "cost_impact" in exc_info.value.message_dict


def test_scope_change_cost_impact_round_trips_as_decimal(tenant_a, scope_project_a):
    change = _scope_change(tenant_a, scope_project_a, cost_impact=D("49999.99"))
    change.refresh_from_db()
    assert change.cost_impact == D("49999.99")
    assert isinstance(change.cost_impact, Decimal), "the money column stays a Decimal, never float"


# ==============================================================================================
# ScopeChangeRequest — clean() same-project guards and the cross-module FK targets
# ==============================================================================================

def test_scope_change_clean_rejects_foreign_requirement(tenant_a, scope_project_a,
                                                        scope_requirement_b):
    change = ScopeChangeRequest(tenant=tenant_a, project=scope_project_a, title="Cross",
                                description="Cross.", requirement=scope_requirement_b)
    with pytest.raises(ValidationError) as exc_info:
        change.clean()
    assert "requirement" in exc_info.value.message_dict


def test_scope_change_clean_rejects_foreign_risk(tenant_a, scope_project_a, scope_project_b):
    foreign_risk = _scope_risk(scope_project_b.tenant, scope_project_b, name="Globex risk")
    change = ScopeChangeRequest(tenant=tenant_a, project=scope_project_a, title="Cross",
                                description="Cross.", risk=foreign_risk)
    with pytest.raises(ValidationError) as exc_info:
        change.clean()
    assert "risk" in exc_info.value.message_dict


def test_scope_change_clean_allows_same_project_requirement_and_risk(tenant_a, scope_project_a):
    req = _scope_requirement(tenant_a, scope_project_a)
    risk = _scope_risk(tenant_a, scope_project_a)
    change = ScopeChangeRequest(tenant=tenant_a, project=scope_project_a, title="Same project",
                                description="Same project.", requirement=req, risk=risk)
    change.clean()  # no raise


def test_scope_change_clean_allows_null_requirement_and_risk(tenant_a, scope_project_a):
    change = ScopeChangeRequest(tenant=tenant_a, project=scope_project_a, title="Unattached",
                                description="Unattached.", requirement=None, risk=None)
    change.clean()  # no raise — both FKs are nullable


def test_scope_change_risk_targets_project_risk():
    field = ScopeChangeRequest._meta.get_field("risk")
    assert field.related_model is ProjectRisk, "risk is a string FK into 7.5's ProjectRisk"


def test_scope_change_risk_reverse_accessor(tenant_a, scope_project_a):
    risk = _scope_risk(tenant_a, scope_project_a, name="Motivating risk")
    change = _scope_change(tenant_a, scope_project_a, risk=risk)
    assert list(risk.scope_changes.all()) == [change]


def test_scope_change_requirement_reverse_accessor(tenant_a, scope_project_a):
    req = _scope_requirement(tenant_a, scope_project_a)
    change = _scope_change(tenant_a, scope_project_a, requirement=req)
    assert list(req.change_requests.all()) == [change]


def test_scope_change_requested_by_reverse_accessor(tenant_a, scope_project_a):
    requester = _scope_user(tenant_a, "scope_change_requester_a")
    change = _scope_change(tenant_a, scope_project_a, requested_by=requester)
    assert list(requester.requested_scope_changes.all()) == [change]


def test_scope_change_decided_by_reverse_accessor(tenant_a, scope_project_a):
    decider = _scope_user(tenant_a, "scope_change_decider_a")
    change = _scope_change(tenant_a, scope_project_a, decided_by=decider)
    assert list(decider.decided_scope_changes.all()) == [change]


def test_scope_change_project_reverse_accessor(tenant_a, scope_project_a):
    change = _scope_change(tenant_a, scope_project_a)
    assert list(scope_project_a.scope_changes.all()) == [change]


# ==============================================================================================
# ScopeVerification — choices and derived predicates
# ==============================================================================================

def test_scope_verification_method_choices_exact():
    assert _scope_values(ScopeVerification.METHOD_CHOICES) == [
        "inspection", "test", "demonstration", "analysis", "review"]


def test_scope_verification_result_choices_exact():
    assert _scope_values(ScopeVerification.RESULT_CHOICES) == ["pass", "conditional", "fail"]


def test_scope_verification_acceptance_status_choices_exact():
    assert _scope_values(ScopeVerification.ACCEPTANCE_STATUS_CHOICES) == [
        "pending", "accepted", "rejected", "waived"]


def test_scope_verification_defaults_to_pending(tenant_a, scope_project_a):
    raw = ScopeVerification(tenant=tenant_a, project=scope_project_a, deliverable="Defaults")
    assert raw.acceptance_status == "pending"
    assert raw.method == "inspection"
    assert raw.result == "pass"


@pytest.mark.parametrize("status,expected", [
    ("pending", False), ("accepted", True), ("rejected", True), ("waived", True)])
def test_scope_verification_is_decided_per_state(tenant_a, scope_project_a, status, expected):
    ver = _scope_verification(tenant_a, scope_project_a, acceptance_status=status)
    assert ver.is_decided is expected, f"is_decided({status}) must be {expected}"


@pytest.mark.parametrize("status,expected", [
    ("pending", False), ("accepted", True), ("rejected", False), ("waived", True)])
def test_scope_verification_is_accepted_per_state(tenant_a, scope_project_a, status, expected):
    ver = _scope_verification(tenant_a, scope_project_a, acceptance_status=status)
    assert ver.is_accepted is expected, f"is_accepted({status}) must be {expected}"


@pytest.mark.parametrize("status,expected", [
    ("pending", False), ("accepted", True), ("rejected", True), ("waived", True)])
def test_scope_verification_is_locked_per_state(tenant_a, scope_project_a, status, expected):
    ver = _scope_verification(tenant_a, scope_project_a, acceptance_status=status)
    assert ver.is_locked is expected, f"is_locked({status}) must be {expected}"


def test_scope_verification_lifecycle_fixtures_hold_their_states(
        scope_verification_pending, scope_verification_accepted, scope_verification_rejected,
        scope_verification_waived):
    assert not scope_verification_pending.is_decided and not scope_verification_pending.is_locked
    assert scope_verification_accepted.is_accepted and scope_verification_accepted.is_locked
    assert not scope_verification_rejected.is_accepted and scope_verification_rejected.is_locked
    assert scope_verification_waived.is_accepted, "waived cleared the gate too"


# ==============================================================================================
# ScopeVerification — clean() same-project guards and the cross-module FK targets
# ==============================================================================================

def test_scope_verification_clean_rejects_foreign_wbs_node(tenant_a, scope_project_a, scope_wbs_b):
    ver = ScopeVerification(tenant=tenant_a, project=scope_project_a, deliverable="Cross",
                            wbs_node=scope_wbs_b)
    with pytest.raises(ValidationError) as exc_info:
        ver.clean()
    assert "wbs_node" in exc_info.value.message_dict


def test_scope_verification_clean_rejects_foreign_requirement(tenant_a, scope_project_a,
                                                             scope_requirement_b):
    ver = ScopeVerification(tenant=tenant_a, project=scope_project_a, deliverable="Cross",
                            requirement=scope_requirement_b)
    with pytest.raises(ValidationError) as exc_info:
        ver.clean()
    assert "requirement" in exc_info.value.message_dict


def test_scope_verification_clean_allows_same_project_fks(tenant_a, scope_project_a, scope_wbs_a):
    req = _scope_requirement(tenant_a, scope_project_a)
    ver = ScopeVerification(tenant=tenant_a, project=scope_project_a, deliverable="Same project",
                            wbs_node=scope_wbs_a, requirement=req)
    ver.clean()  # no raise


def test_scope_verification_clean_allows_null_fks(tenant_a, scope_project_a):
    ver = ScopeVerification(tenant=tenant_a, project=scope_project_a, deliverable="Unattached",
                            wbs_node=None, requirement=None)
    ver.clean()  # no raise — both FKs are nullable


def test_scope_verification_wbs_node_targets_project_task():
    field = ScopeVerification._meta.get_field("wbs_node")
    assert field.related_model is ProjectTask


def test_scope_verification_fk_reverse_accessors(tenant_a, scope_project_a, scope_wbs_a):
    req = _scope_requirement(tenant_a, scope_project_a)
    ver = _scope_verification(tenant_a, scope_project_a, wbs_node=scope_wbs_a, requirement=req)
    assert list(scope_wbs_a.scope_verifications.all()) == [ver]
    assert list(req.scope_verifications.all()) == [ver]


def test_scope_verification_inspected_by_reverse_accessor(tenant_a, scope_project_a):
    inspector = _scope_user(tenant_a, "scope_inspector_a")
    ver = _scope_verification(tenant_a, scope_project_a, inspected_by=inspector)
    assert list(inspector.inspected_scope_deliverables.all()) == [ver]


def test_scope_verification_accepted_by_reverse_accessor(tenant_a, scope_project_a):
    acceptor = _scope_user(tenant_a, "scope_acceptor_a")
    ver = _scope_verification(tenant_a, scope_project_a, accepted_by=acceptor)
    assert list(acceptor.accepted_scope_deliverables.all()) == [ver]


def test_scope_verification_project_reverse_accessor(tenant_a, scope_project_a):
    ver = _scope_verification(tenant_a, scope_project_a)
    assert list(scope_project_a.scope_verifications.all()) == [ver]


# ==============================================================================================
# Meta — ordering, index names and __str__
# ==============================================================================================

@pytest.mark.parametrize("model", [Requirement, ScopeItem, ScopeChangeRequest, ScopeVerification])
def test_scope_ordering_is_newest_first(model):
    assert model._meta.ordering == ["-created_at", "-id"], (
        f"contract pins newest-first ordering on {model.__name__}")


@pytest.mark.parametrize("model", [Requirement, ScopeItem, ScopeChangeRequest, ScopeVerification])
def test_scope_index_names_match_the_contract(model):
    prefixes = {"REQ": "req_tnt_", "SCI": "sci_tnt_", "SCR": "scr_tnt_", "SVR": "svr_tnt_"}
    expected_prefix = prefixes[model.NUMBER_PREFIX]
    names = [index.name for index in model._meta.indexes]
    assert names, f"{model.__name__} declares no indexes"
    assert all(name.startswith(expected_prefix) for name in names), (
        f"{model.__name__} index names must start {expected_prefix!r}, got {names!r}")


def test_scope_requirement_index_count_matches_the_contract():
    assert len(Requirement._meta.indexes) == 5
    assert {i.name for i in Requirement._meta.indexes} == {
        "req_tnt_project_idx", "req_tnt_status_idx", "req_tnt_type_idx",
        "req_tnt_priority_idx", "req_tnt_created_idx"}


def test_scope_item_index_count_matches_the_contract():
    assert {i.name for i in ScopeItem._meta.indexes} == {
        "sci_tnt_project_idx", "sci_tnt_type_idx", "sci_tnt_status_idx", "sci_tnt_impact_idx"}


def test_scope_change_index_count_matches_the_contract():
    assert {i.name for i in ScopeChangeRequest._meta.indexes} == {
        "scr_tnt_project_idx", "scr_tnt_status_idx", "scr_tnt_priority_idx",
        "scr_tnt_source_idx"}


def test_scope_verification_index_count_matches_the_contract():
    assert {i.name for i in ScopeVerification._meta.indexes} == {
        "svr_tnt_project_idx", "svr_tnt_status_idx", "svr_tnt_result_idx"}


def test_scope_requirement_str(tenant_a, scope_project_a):
    req = _scope_requirement(tenant_a, scope_project_a, title="Zero-touch matching")
    assert str(req) == f"{req.number} — Zero-touch matching"


def test_scope_item_str(tenant_a, scope_project_a):
    item = _scope_item(tenant_a, scope_project_a, statement="No downtime at peak")
    assert str(item) == f"{item.number} — No downtime at peak"


def test_scope_change_str(tenant_a, scope_project_a):
    change = _scope_change(tenant_a, scope_project_a, title="Move the batch window")
    assert str(change) == f"{change.number} — Move the batch window"


def test_scope_verification_str(tenant_a, scope_project_a):
    ver = _scope_verification(tenant_a, scope_project_a, deliverable="Onboarding runbook")
    assert str(ver) == f"{ver.number} — Onboarding runbook"


# ==============================================================================================
# The factory fills stay inert (they must not move the pinned matrix figures)
# ==============================================================================================

def test_scope_fill_requirements_are_untraced_drafts(tenant_a, scope_project_a):
    rows = _scope_fill_requirements(tenant_a, scope_project_a, 3)
    assert len(rows) == 3
    assert all(row.wbs_node_id is None for row in rows), "fills must never enter the coverage numerator"
    assert all(row.status == "draft" for row in rows)
    assert len({row.title for row in rows}) == 3, "distinct titles — never collide with matrix rows"


def test_scope_fill_items_are_open_and_never_overdue(tenant_a, scope_project_a):
    rows = _scope_fill_items(tenant_a, scope_project_a, 3)
    assert all(row.status == "open" and row.review_date is None for row in rows)
    assert all(row.is_review_overdue is False for row in rows)


def test_scope_fill_changes_are_zero_impact_drafts(tenant_a, scope_project_a):
    rows = _scope_fill_changes(tenant_a, scope_project_a, 3)
    assert all(row.status == "draft" for row in rows)
    assert all(row.cost_impact == D("0") and not row.is_high_impact for row in rows)


def test_scope_page_size_constant_pins_the_default_per_page():
    """``crud_list``'s default ``per_page`` — the 7.7 register pagination contract."""
    assert SCOPE_PAGE_SIZE == 15


def test_scope_month_start_anchors_are_distinct_months():
    """The creep fixtures' bucket anchor: this month, last month, two months back are three
    different ``(year, month)`` keys as long as ``months_back`` differs."""
    keys = {(_scope_month_start(n).year, _scope_month_start(n).month) for n in (0, 1, 2)}
    assert len(keys) == 3
    assert _scope_month_start(0).day == 1
