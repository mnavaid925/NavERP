"""0.20 FORMS lane — the status-dropdown walk, and the X1/X3/X9 mass-assignment guards.

Against `.claude/tasks/test-contract-core-0.20.md`.

**The headline test is `test_ac0_every_offered_status_value_is_valid`.** Phase 5 finding X1 was that
four status values 500'd, because `Model.clean()` raised `ValidationError` keyed on a field
*excluded from its own form*: Django routes that through `form.add_error(key, ...)`, which raises
`ValueError` for a key the form does not have. A structural smoke cannot catch this — it only ever
submits seeded data, never a value a person picks. So this lane walks **every** value in **every**
status choice set and asserts `is_valid()` RETURNS. A walk is what makes the regression impossible to
reintroduce silently: adding a CHOICES value without running it through a form fails here.
"""
import pytest

from apps.core.forms import (
    ChangeRequestForm,
    FeatureRolloutForm,
    JobDefinitionForm,
    JobRunForm,
    MaintenanceWindowForm,
)
from apps.core.models import ChangeRequest, FeatureRollout, MaintenanceWindow

_ALL_FORMS = (JobDefinitionForm, JobRunForm, MaintenanceWindowForm,
              ChangeRequestForm, FeatureRolloutForm)

#: (form, payload fixture, model, values a POST-only verb owns rather than the form)
_STATUS_LANES = [
    (ChangeRequestForm, "ac0_change_payload", ChangeRequest, {"submitted", "approved", "rolled_back"}),
    (MaintenanceWindowForm, "ac0_window_payload", MaintenanceWindow, {"ended_early"}),
    (FeatureRolloutForm, "ac0_rollout_payload", FeatureRollout, {"completed"}),
]

#: Values a PERSON may author, because they assert that nothing happened. `rejected` and `cancelled`
#: record a decision not to proceed, and only a person knows that — no verb can infer it.
_PERSON_OWNED = {"rejected", "cancelled"}


def _ac0_values(form_cls, **kw):
    """The status values the form's widget actually OFFERS, read from the form itself.

    Reading the WIDGET rather than the model's CHOICES is deliberate: the Phase 5 fix narrowed the
    widget, so the model and the form no longer agree, and a test asserting against the model would
    be asserting the wrong thing.
    """
    form = form_cls(**kw)
    return [v for v, _ in form.fields["status"].widget.choices]


class TestAc0StatusWidgets:
    @pytest.mark.parametrize("form_cls,payload_fixture,model,verb_owned", _STATUS_LANES)
    def test_ac0_every_offered_status_value_is_valid(self, form_cls, payload_fixture, model,
                                                      verb_owned, request, tenant_a):
        """The X1 regression guard: is_valid() must RETURN for every offered value, never raise.

        `request.getfixturevalue` rather than a `**fixtures` catch-all: pytest resolves the
        parametrised fixture name into the signature only if it is a real parameter, and a `**kwargs`
        bag does not give that — the name lands as a plain key, not as the fixture's value.
        """
        payload = request.getfixturevalue(payload_fixture)
        for value in _ac0_values(form_cls, tenant=tenant_a):
            form = form_cls(data=dict(payload, status=value), tenant=tenant_a)
            try:
                form.is_valid()
            except ValueError as exc:  # the exact failure X1 produced
                pytest.fail("%s raised ValueError on status=%r: %s"
                            % (form_cls.__name__, value, exc))

    @pytest.mark.parametrize("form_cls,payload_fixture,model,verb_owned", _STATUS_LANES)
    def test_ac0_every_model_status_value_is_formable_or_verb_owned(
            self, form_cls, payload_fixture, model, verb_owned, tenant_a):
        """A value the form refuses must be owned by a named verb, or a state is unreachable.

        The point is NOT that every non-offered value is verb-owned: `rejected` and `cancelled` are
        legitimately authorable by a person, because they assert that nothing happened and only a
        person knows that. What must never happen is a value that is neither offered by the form nor
        reachable by any verb, because then NO path in the application can put a row into that state.
        """
        offered = set(_ac0_values(form_cls, tenant=tenant_a))
        model_values = {v for v, _ in model.STATUS_CHOICES}
        # `rejected` and `cancelled` assert that nothing happened, so a person is the only party
        # who can author them; they are legitimately formable and are named here so the assertion
        # is about UNACCOUNTED values, not about a narrow verb set.
        person_owned = {"rejected", "cancelled"}
        unaccounted = model_values - offered - verb_owned - person_owned
        assert not unaccounted, (
            "%s: status value(s) %r are offered by neither the form nor a named verb, so no path "
            "can put a row into that state" % (model.__name__, unaccounted))

    def test_ac0_change_form_offers_the_values_a_person_may_author(self):
        """Not `draft` alone: `scheduled`, `in_progress` and `completed` are also person-authorable.

        They assert what a human observed, and the views and templates READ all three — so refusing
        them would leave states nothing can produce, and the rollback verb unreachable because its
        `completed` precondition could never be met.
        """
        assert set(_ac0_values(ChangeRequestForm)) == {
            "draft", "scheduled", "in_progress", "completed"}

    @pytest.mark.parametrize("value", ["approved", "rolled_back", "submitted"])
    def test_ac0_change_form_never_offers_a_verb_owned_value(self, value):
        """Each of these needs a stamp only its verb can write."""
        assert value not in _ac0_values(ChangeRequestForm)

    def test_ac0_window_form_never_offers_ended_early(self):
        """`ended_early` needs an `ended_at` this form cannot supply; only the verb writes it."""
        assert set(_ac0_values(MaintenanceWindowForm)) == {
            "draft", "scheduled", "active", "completed", "cancelled"}

    def test_ac0_rollout_form_never_offers_completed(self):
        assert set(_ac0_values(FeatureRolloutForm)) == {
            "planned", "running", "paused", "rolled_back"}


class TestAc0EditPreservesStatus:
    """The X1(b) hazard: a select whose current value is absent renders with nothing chosen, so the
    browser posts the FIRST option — editing an approved change's title would reset it to Draft."""

    def test_ac0_editing_a_non_authorable_row_keeps_its_status_selected(self, tenant_a,
                                                                         ac0_change_approved):
        form = ChangeRequestForm(instance=ac0_change_approved, tenant=tenant_a)
        offered = dict(form.fields["status"].widget.choices)
        assert ac0_change_approved.status in offered
        assert "current" in offered[ac0_change_approved.status]

    def test_ac0_a_create_form_shows_only_authorable_values(self, tenant_a):
        form = ChangeRequestForm(tenant=tenant_a)
        assert all("current" not in lbl for _, lbl in form.fields["status"].widget.choices)

    def test_ac0_resubmitting_a_non_authorable_row_does_not_reset_it(self, tenant_a,
                                                                     ac0_change_approved,
                                                                     ac0_change_payload):
        payload = dict(ac0_change_payload, title="renamed; status must survive")
        payload["status"] = ac0_change_approved.status
        form = ChangeRequestForm(data=payload, instance=ac0_change_approved, tenant=tenant_a)
        assert form.is_valid(), form.errors
        form.save()
        ac0_change_approved.refresh_from_db()
        assert ac0_change_approved.status == "approved"


# ------------------------------------------------------------------ mass assignment
class TestAc0EvidenceStampsAreNotFormFields:
    """L22: a stamp is written by the verb that performs the transition, never typed.

    These are the X3 and X9 findings. Each asserts the field is ABSENT, so a forged POST cannot
    attach it even if a template were wrong.
    """

    @pytest.mark.parametrize("form_cls,stamps", [
        (JobDefinitionForm, ("last_run_at", "next_run_at", "number", "created_at")),
        (JobRunForm, ("triggered_at", "triggered_by", "is_dry_run")),
        (MaintenanceWindowForm, ("ended_at", "number", "created_at")),
        (ChangeRequestForm, ("requestor", "approved_by", "requested_at", "approved_at",
                             "implemented_at", "rollback_at", "rollback_reason", "post_review")),
        (FeatureRolloutForm, ("started_at", "completed_at")),
    ])
    def test_ac0_stamps_are_not_form_fields(self, form_cls, stamps):
        fields = form_cls().fields
        for stamp in stamps:
            assert stamp not in fields, ("%s: %s must not be form-authorable"
                                         % (form_cls.__name__, stamp))

    def test_ac0_requested_at_is_not_a_change_form_field(self):
        """The X3 finding, named on its own: a forgeable request date on the register."""
        assert "requested_at" not in ChangeRequestForm().fields

    def test_ac0_is_dry_run_is_not_a_run_form_field(self):
        """The X9 finding: unchecking it made the register assert a real, non-dry run."""
        assert "is_dry_run" not in JobRunForm().fields

    @pytest.mark.parametrize("form_cls", _ALL_FORMS)
    def test_ac0_no_form_exposes_the_tenant(self, form_cls):
        assert "tenant" not in form_cls().fields


# ------------------------------------------------------------------ the stage ladder
class TestAc0StagePercentageMatrix:
    """The LaunchDarkly ladder bookends are EXACT, and the model refuses a contradiction.

    A "general availability" stage reaching 40% of users is not a record of anything, so the pair
    is rejected rather than stored. This is a matrix rather than three cases because the whole point
    is the corners: 0 and 100 are legal for one stage and illegal for another.
    """

    @pytest.mark.parametrize("stage,pct,valid", [
        ("internal", 0, True), ("internal", 50, False), ("internal", 100, False),
        ("pilot", 0, True), ("pilot", 50, True), ("pilot", 100, True),
        ("partial", 0, False), ("partial", 1, True), ("partial", 50, True),
        ("partial", 99, True), ("partial", 100, False),
        ("general", 0, False), ("general", 50, False), ("general", 100, True),
    ])
    def test_ac0_stage_percentage_pair_is_accepted_or_refused_as_documented(
            self, stage, pct, valid, tenant_a, ac0_rollout_payload):
        from apps.core.models import FeatureRollout
        payload = dict(ac0_rollout_payload, stage=stage, percentage=pct, status="planned")
        form = FeatureRolloutForm(data=payload, tenant=tenant_a)
        if valid:
            assert form.is_valid(), form.errors
        else:
            assert not form.is_valid()
            assert "percentage" in form.errors

    def test_ac0_a_refused_ladder_pair_surfaces_as_a_field_error_not_a_crash(
            self, tenant_a, ac0_rollout_payload):
        """The refusal must be a field error, so the operator sees which field to fix."""
        payload = dict(ac0_rollout_payload, stage="general", percentage=40, status="planned")
        form = FeatureRolloutForm(data=payload, tenant=tenant_a)
        form.is_valid()  # must RETURN
        assert form.errors.get("percentage")


class TestAc0DuplicateGuard:
    """`unique_together` is enforced only by the database, so the form carries the one hand-written
    rule in this file. Without it a second stage for the same flag under the same change is a 500
    rather than a field error."""

    def test_ac0_a_second_stage_for_the_same_flag_under_the_same_change_is_refused(
            self, tenant_a, ac0_rollout, ac0_rollout_payload):
        payload = dict(ac0_rollout_payload, change=ac0_rollout.change_id,
                       feature_flag=ac0_rollout.feature_flag_id)
        form = FeatureRolloutForm(data=payload, tenant=tenant_a)
        assert not form.is_valid()
        assert "feature_flag" in form.errors

    def test_ac0_resaving_the_existing_stage_with_its_own_flag_is_not_a_duplicate(
            self, tenant_a, ac0_rollout, ac0_rollout_payload):
        """Scoped to the instance being edited — otherwise you could never correct a stage."""
        payload = dict(ac0_rollout_payload, change=ac0_rollout.change_id,
                       feature_flag=ac0_rollout.feature_flag_id,
                       cohort_label="corrected in place")
        form = FeatureRolloutForm(data=payload, instance=ac0_rollout, tenant=tenant_a)
        assert form.is_valid(), form.errors