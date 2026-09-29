"""0.20 Admin Console & System Operations - MODELS lane.

Written against `.claude/tasks/test-contract-core-0.20.md` sections 1 and 9. Every model, field,
CHOICES value, message string and error KEY below was read out of
`apps/core/models/{JobScheduler,Maintenance,Change}.py` - nothing here is inferred, because an
invented name is a silently-blank assertion three files from now (L7/L8).

What this module protects, in order of how expensive a regression would be:

1. **Every `clean()` guard raises, and raises on the right key.** Phase 5 re-keyed three groups of
   guards onto `NON_FIELD_ERRORS` (`ChangeRequest`'s four, `MaintenanceWindow`'s last two,
   `FeatureRollout`'s last two) because their subject fields are EXCLUDED from the forms. That was
   finding X1: a `ValidationError` keyed on a field the form does not have is handed to
   `form.add_error(key, ...)`, which raises `ValueError` for an unknown key - so an ordinary
   dropdown choice became a **500** instead of a refusal. The assertions below therefore check
   `exc.value.error_dict` and, for the non-field guards, assert `NON_FIELD_ERRORS` is the *only*
   key. A guard that went back to naming `approved_by` / `ended_at` / `completed_at` fails here even
   though the guard still "works".
   Every guard is exercised through **`full_clean()`**, never through `save()`: a `save()` that
   raises `IntegrityError` is a different failure, and a `full_clean()` that never reaches `clean()`
   is no failure at all.
2. **`SCHEDULE_KIND_CHOICES is SyncSchedule.FREQUENCY_CHOICES`** - asserted with `is`, not `==`.
   Two equal lists are still two lists; only identity proves 0.20 reuses 0.13's cadence vocabulary
   rather than forking a copy that drifts the first time 0.13 adds a value. This is the single
   load-bearing assertion for the sub-module.
3. **Number minting** - four prefixes, minted on first save and never re-minted; and
   `FeatureRollout` has no `number` column at all, because a rollout is only ever addressed
   through its change.
4. **The zero rule on the derived display properties.** `JobRun.duration_display` and
   `MaintenanceWindow.duration_human` return an em dash when an end is missing and are asserted to
   be *never* `0` for an unmeasured row: "took no measurable time" and "nobody measured it" are
   different statements, and collapsing them is the null-means-zero defect.
5. **`FeatureRollout`'s `unique_together`** - enforced by the DATABASE, so the duplicate is an
   `IntegrityError`, and only the form's hand-written `clean_feature_flag` (lane 3) turns it into a
   field error. The same `(change, feature_flag)` pair under a *different* change is legal, which is
   what makes `rollout_count` provable against a real sibling.
6. **Tenancy** - every model carries `tenant` and every view filters `tenant=request.tenant`, so a
   `tenant_b` row must never be reachable from a `tenant_a` queryset.

Every reference date is derived from `timezone.now()`, never `datetime.date.today()` (L16).
"""
import pytest
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError
from django.db import IntegrityError, connection, models, transaction
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.core.models import (
    AlertRule,
    ChangeRequest,
    FeatureRollout,
    JobDefinition,
    JobRun,
    MaintenanceWindow,
    SyncSchedule,
)
from apps.core.settings_engine import LITERAL_PREFIX_MODELS

#: Every index name must be under 30 characters: MariaDB's hard limit, so a 31-character name is
#: a migration that succeeds on SQLite and fails on the database the app actually runs on.
MAX_INDEX_NAME = 30

#: The em dash the two display properties return for "not measured". Spelled as an escape on
#: purpose: a literal U+2014 is one editor encoding away from becoming a mojibake character that
#: no longer equals the model's, and the failure would look like a product bug rather than a
#: test-file bug.
EM_DASH = "\u2014"


# =================================================================================================
# helpers
# =================================================================================================
def _ac0_dt(**delta):
    """A `timezone.now()`-relative instant. Always relative (L16), never `date.today()`."""
    from datetime import timedelta

    return timezone.now() + timedelta(**delta)


def _ac0_messages(exc, key):
    return [str(m) for m in exc.error_dict[key]]


def _ac0_field_names(model):
    return {f.name for f in model._meta.get_fields()}


def _ac0_assert_keyed(exc, model, key, needle):
    """Assert a guard fired under `key` and carries `needle`.

    A FIELD-keyed guard must also name a real model field, otherwise the error is not renderable
    next to anything the operator filled in.
    """
    assert key in exc.error_dict, "expected the guard under %r, got %r" % (
        key, sorted(exc.error_dict))
    assert key in _ac0_field_names(model), (
        "%s keyed a guard on %r, which is not a field of the model" % (model.__name__, key))
    assert any(needle in m for m in _ac0_messages(exc, key)), "expected %r among %r" % (
        needle, _ac0_messages(exc, key))


def _ac0_assert_non_field(exc, needle):
    """Assert a guard fired under `NON_FIELD_ERRORS` and on NOTHING ELSE.

    The "nothing else" half is the point. X1 was a guard keyed on a field the form excludes;
    `ModelForm` routed that key through `add_error()`, which raises `ValueError` for an unknown key
    and turned the save into a 500. `__all__` is always a legal form key, so a non-field guard
    renders as a non-field error instead of crashing the request - and a regression that re-keys it
    on a real field is caught here rather than in a browser.
    """
    assert set(exc.error_dict) == {NON_FIELD_ERRORS}, (
        "the guard must be keyed on NON_FIELD_ERRORS and nothing else; got %r" % (
            sorted(exc.error_dict),))
    assert any(needle in m for m in _ac0_messages(exc, NON_FIELD_ERRORS)), "expected %r among %r" % (
        needle, _ac0_messages(exc, NON_FIELD_ERRORS))


def _ac0_tenant_scoped(model, tenant, own, other):
    """Assert `own` is reachable in `tenant` and `other` (a `tenant_b` row) is not."""
    pks = set(model.objects.filter(tenant=tenant).values_list("pk", flat=True))
    assert own.pk in pks, "%s is missing from its own tenant's queryset" % model.__name__
    assert other.pk not in pks, "%s leaked another tenant's row" % model.__name__
    # The `.get()` a detail view performs against `Model.objects.get(pk=..., tenant=...)` - with the
    # filter accidentally dropped - must fail loudly rather than render somebody else's row.
    with pytest.raises(model.DoesNotExist):
        model.objects.get(pk=other.pk, tenant=tenant)


def _ac0_clean_window(tenant, **overrides):
    """A minimal VALID `MaintenanceWindow` to break, so a guard test is not a field test."""
    fields = {"title": "Guard subject", "starts_at": _ac0_dt(hours=1),
              "ends_at": _ac0_dt(hours=2)}
    fields.update(overrides)
    return MaintenanceWindow(tenant=tenant, **fields)


def _ac0_clean_rollout(tenant, change, flag, **overrides):
    """A minimal VALID `FeatureRollout` to break - `partial` at 25% satisfies the ladder guard."""
    fields = {"change": change, "feature_flag": flag, "stage": "partial", "percentage": 25,
              "status": "planned"}
    fields.update(overrides)
    return FeatureRollout(tenant=tenant, **fields)



# =================================================================================================
# 1. number minting
# =================================================================================================
@pytest.mark.parametrize("model,prefix,extra", [
    (JobDefinition, "JOB", {"name": "Minted job", "module_slug": "core",
                             "handler_path": "apps.core.tasks.minted"}),
    (MaintenanceWindow, "MNTW", {"title": "Minted window"}),
    (ChangeRequest, "CHG", {"title": "Minted change"}),
], ids=["job", "window", "change"])
def test_ac0_number_is_minted_with_its_prefix(db, tenant_a, model, prefix, extra):
    fields = dict(extra)
    if model is MaintenanceWindow:
        fields["starts_at"] = _ac0_dt(days=1)
        fields["ends_at"] = _ac0_dt(days=1, hours=2)
    obj = model.objects.create(tenant=tenant_a, **fields)
    assert obj.number.startswith("%s-" % prefix), "%s minted %r" % (model.__name__, obj.number)
    assert len(obj.number) == len(prefix) + 6, "the suffix is zero-padded to five digits"


def test_ac0_run_number_is_minted_with_its_prefix(db, tenant_a, ac0_job):
    run = JobRun.objects.create(tenant=tenant_a, job=ac0_job, status="queued")
    assert run.number.startswith("RUN-")
    assert len(run.number) == len("RUN-") + 5


def test_ac0_first_row_in_a_tenant_is_number_one(db, tenant_a):
    """`JOB-00001` / `RUN-00001` / `MNTW-00001` / `CHG-00001` on an empty workspace - the exact
    `<PREFIX>-00001` shape the contract pins."""
    job = JobDefinition.objects.create(tenant=tenant_a, name="First", module_slug="core",
                                       handler_path="apps.core.tasks.first")
    run = JobRun.objects.create(tenant=tenant_a, job=job, status="queued")
    window = MaintenanceWindow.objects.create(
        tenant=tenant_a, title="First window", starts_at=_ac0_dt(days=1),
        ends_at=_ac0_dt(days=1, hours=1))
    change = ChangeRequest.objects.create(tenant=tenant_a, title="First change")
    assert job.number == "JOB-00001"
    assert run.number == "RUN-00001"
    assert window.number == "MNTW-00001"
    assert change.number == "CHG-00001"


def test_ac0_numbers_increment_per_tenant(db, tenant_a, tenant_b):
    """`next_number()` is `(tenant, prefix)`-scoped: a second tenant starts its own sequence."""
    first = JobDefinition.objects.create(tenant=tenant_a, name="A one", module_slug="core",
                                         handler_path="apps.core.tasks.a1")
    second = JobDefinition.objects.create(tenant=tenant_a, name="A two", module_slug="core",
                                          handler_path="apps.core.tasks.a2")
    other = JobDefinition.objects.create(tenant=tenant_b, name="B one", module_slug="core",
                                         handler_path="apps.core.tasks.b1")
    assert int(second.number.split("-")[1]) == int(first.number.split("-")[1]) + 1
    assert other.number == "JOB-00001", "each tenant numbers its own documents from one"



def test_ac0_number_is_not_re_minted_on_a_later_save(db, tenant_a):
    """`save()` mints ONCE. A second save must not burn the next number in the sequence.

    This is the `if self.number: return super().save(...)` short-circuit at the top of all four
    `save()` methods. Without it every edit of a job would hand the row a brand-new identity, and
    an operator holding `JOB-00003` would find it had become `JOB-00007`.
    """
    job = JobDefinition.objects.create(tenant=tenant_a, name="Edited", module_slug="core",
                                       handler_path="apps.core.tasks.edited")
    job.priority = 5
    job.is_muted = True
    job.save()
    job.refresh_from_db()
    assert job.number == "JOB-00001", "a re-save re-minted the job"
    assert JobDefinition.objects.filter(tenant=tenant_a).count() == 1, "a re-save created a row"

    run = JobRun.objects.create(tenant=tenant_a, job=job, status="queued")
    run.notes = "Edited after the fact."
    run.save()
    run.refresh_from_db()
    assert run.number == "RUN-00001"
    assert JobRun.objects.filter(tenant=tenant_a).count() == 1

    window = MaintenanceWindow.objects.create(
        tenant=tenant_a, title="Edited window", starts_at=_ac0_dt(days=1),
        ends_at=_ac0_dt(days=1, hours=1))
    window.purpose = "Now with a reason."
    window.save()
    window.refresh_from_db()
    assert window.number == "MNTW-00001"
    assert MaintenanceWindow.objects.filter(tenant=tenant_a).count() == 1

    change = ChangeRequest.objects.create(tenant=tenant_a, title="Edited change")
    change.summary = "Now described."
    change.save()
    change.refresh_from_db()
    assert change.number == "CHG-00001"
    assert ChangeRequest.objects.filter(tenant=tenant_a).count() == 1


def test_ac0_a_row_saved_with_a_number_already_set_is_left_alone(db, tenant_a):
    """A pre-set `number` short-circuits the mint - the other half of the same `save()` guard."""
    job = JobDefinition.objects.create(tenant=tenant_a, number="JOB-90001", name="Imported",
                                       module_slug="core", handler_path="apps.core.tasks.imported")
    assert job.number == "JOB-90001", "an imported number must survive save()"
    # ...and the next minted row does not collide with it: `next_number()` reads the NUMBER COLUMN
    # (`number__startswith`, ordered by `-number`), not the pks.
    nxt = JobDefinition.objects.create(tenant=tenant_a, name="After the import", module_slug="core",
                                       handler_path="apps.core.tasks.after")
    assert nxt.number == "JOB-90002"


def test_ac0_rollout_has_no_number_column_at_all(db, ac0_rollout):
    """A rollout is addressed only through the change that owns it, so it mints nothing.

    A fifth `ROLL-` prefix would be a number no operator ever looks up. Asserted on BOTH the
    instance and the field list, because a `number` attribute could in principle be a plain
    non-field attribute rather than a column.
    """
    assert not hasattr(ac0_rollout, "number")
    assert "number" not in _ac0_field_names(FeatureRollout)
    assert "ROLL" not in LITERAL_PREFIX_MODELS, (
        "a ROLL prefix would claim a minting model that does not exist")
    # The four that DO mint, by the `app_label.ModelName` string `prefix_usage()` matches on.
    for prefix, model in [("JOB", JobDefinition), ("RUN", JobRun), ("MNTW", MaintenanceWindow),
                          ("CHG", ChangeRequest)]:
        label = "%s.%s" % (model._meta.app_label, model.__name__)
        assert label in LITERAL_PREFIX_MODELS[prefix], (
            "%s is missing from LITERAL_PREFIX_MODELS[%r], so the numbering board would report the "
            "prefix as configured but minted by no model" % (label, prefix))



# =================================================================================================
# 2. __str__
# =================================================================================================
def test_ac0_str_carries_the_number(db, ac0_job, ac0_run, ac0_window, ac0_change):
    for obj in (ac0_job, ac0_run, ac0_window, ac0_change):
        assert obj.number in str(obj), "%s.__str__() is %r, which hides its own number" % (
            obj.__class__.__name__, str(obj))


def test_ac0_str_reads_usefully(db, ac0_job, ac0_run, ac0_window, ac0_change):
    assert str(ac0_job) == "%s %s" % (ac0_job.number, ac0_job.name)
    # A run is identified by its STATE, not by its job - many runs, one job.
    assert str(ac0_run) == "%s %s" % (ac0_run.number, ac0_run.get_status_display())
    assert str(ac0_window) == "%s %s" % (ac0_window.number, ac0_window.title)
    assert str(ac0_change) == "%s %s" % (ac0_change.number, ac0_change.title)


def test_ac0_rollout_str_carries_the_change_number_and_the_stage(db, ac0_rollout):
    """A rollout has no number of its own, so it reads through its PARENT's number.

    `"%s / %s (%d%%)"` - the change number, the stage label, and the declared percentage. An
    operator scanning a list needs all three, and the percentage is the whole claim.
    """
    text = str(ac0_rollout)
    assert ac0_rollout.change.number in text, "the parent change's number is missing from %r" % text
    assert ac0_rollout.get_stage_display() in text
    assert "%d%%" % ac0_rollout.percentage in text



# =================================================================================================
# 3. the vocabularies
# =================================================================================================
def test_ac0_schedule_kind_choices_are_reused_by_reference():
    """**`is`, not `==`.** This is the load-bearing assertion for the sub-module.

    `JobDefinition.schedule_kind` borrows 0.13's cadence vocabulary rather than declaring a second
    one (L29/L36). A pasted copy is EQUAL today and forks the first time 0.13 adds a frequency, at
    which point the register and 0.13 disagree about what "daily" means.

    Identity is only observable on the CLASS: Django normalises a *field's* own `choices` into a
    fresh list at field-definition time, so `_meta.get_field(...).choices` is never the same object.
    """
    assert JobDefinition.SCHEDULE_KIND_CHOICES is SyncSchedule.FREQUENCY_CHOICES

    # Why `==` would not do - spelled out so nobody "simplifies" the assertion above.
    copied = list(SyncSchedule.FREQUENCY_CHOICES)
    assert copied == SyncSchedule.FREQUENCY_CHOICES, "the two are equal by value..."
    assert copied is not SyncSchedule.FREQUENCY_CHOICES, "...so only `is` proves reuse"

    # And the field really is fed the same values, even though Django hands it a normalised copy.
    assert JobDefinition._meta.get_field("schedule_kind").choices == SyncSchedule.FREQUENCY_CHOICES
    assert [v for v, _l in JobDefinition.SCHEDULE_KIND_CHOICES] == [
        "manual", "hourly", "daily", "weekly"]


def test_ac0_risk_level_choices_are_deliberately_not_the_alert_severity_vocabulary():
    """The other half of the reuse rule: a vocabulary is shared BY REFERENCE when it is the SAME
    fact and kept SEPARATE when it is not. A change's assessed risk is not a firing alert's
    severity - they share three of their words and answer different questions - so these must NOT
    be one list. Asserted so nobody "unifies" the two."""
    assert ChangeRequest.RISK_LEVEL_CHOICES is not AlertRule.SEVERITY_CHOICES
    assert [v for v, _l in ChangeRequest.RISK_LEVEL_CHOICES] == ["low", "medium", "high"]
    assert [v for v, _l in AlertRule.SEVERITY_CHOICES] == ["info", "warning", "critical"]


def test_ac0_choices_are_the_documented_vocabularies():
    """Every CHOICES value, pinned. A dropped value silently removes an option from a `<select>`
    and a badge rule at a time, so the whole vocabulary is asserted rather than its length."""
    def values(choices):
        return [v for v, _label in choices]

    assert values(JobDefinition.JOB_TYPE_CHOICES) == [
        "scheduled_task", "integration_sync", "bulk_operation", "report", "cleanup", "maintenance"]
    assert values(JobRun.TRIGGER_KIND_CHOICES) == ["manual", "scheduled", "backfill", "api"]
    assert values(JobRun.STATUS_CHOICES) == [
        "queued", "running", "success", "failed", "skipped", "cancelled"]
    assert values(MaintenanceWindow.RECURRENCE_CHOICES) == ["once", "daily", "weekly", "monthly"]
    assert values(MaintenanceWindow.STATUS_CHOICES) == [
        "draft", "scheduled", "active", "ended_early", "completed", "cancelled"]
    assert values(ChangeRequest.CHANGE_TYPE_CHOICES) == ["standard", "normal", "emergency"]
    assert values(ChangeRequest.IMPACT_LEVEL_CHOICES) == ["minor", "moderate", "major"]
    assert values(ChangeRequest.STATUS_CHOICES) == [
        "draft", "submitted", "approved", "rejected", "scheduled", "in_progress", "completed",
        "rolled_back", "cancelled"]
    assert values(FeatureRollout.STAGE_CHOICES) == ["internal", "pilot", "partial", "general"]
    assert values(FeatureRollout.STATUS_CHOICES) == [
        "planned", "running", "paused", "completed", "rolled_back"]



def test_ac0_class_re_exports_are_the_module_tuples():
    """`JobRun.STATUS_CHOICES` is the SAME object as the module's `JOB_RUN_STATUS_CHOICES`, so a
    view and a test read one vocabulary rather than two that can drift."""
    from apps.core.models.Change import (  # noqa: PLC0415 - the module tuples, deliberately
        CHANGE_STATUS_CHOICES,
        ROLLOUT_STAGE_CHOICES,
    )
    from apps.core.models.JobScheduler import JOB_RUN_STATUS_CHOICES  # noqa: PLC0415
    from apps.core.models.Maintenance import WINDOW_STATUS_CHOICES  # noqa: PLC0415

    assert JobRun.STATUS_CHOICES is JOB_RUN_STATUS_CHOICES
    assert JobRun.TRIGGER_KIND_CHOICES[0][0] == "manual"
    assert MaintenanceWindow.STATUS_CHOICES is WINDOW_STATUS_CHOICES
    assert ChangeRequest.STATUS_CHOICES is CHANGE_STATUS_CHOICES
    assert FeatureRollout.STAGE_CHOICES is ROLLOUT_STAGE_CHOICES


def test_ac0_documented_defaults():
    """The defaults an operator meets on a blank form, read off the FIELD, not off a fixture."""
    assert JobDefinition._meta.get_field("priority").default == 100
    assert JobDefinition._meta.get_field("max_active_runs").default == 1
    assert JobDefinition._meta.get_field("pool_slots").default == 1
    assert JobDefinition._meta.get_field("max_consecutive_failures").default == 3
    assert JobDefinition._meta.get_field("auto_pause_after").default == 10
    assert JobDefinition._meta.get_field("is_muted").default is False
    assert JobDefinition._meta.get_field("is_active").default is True
    assert JobDefinition._meta.get_field("schedule_kind").default == "manual"
    assert JobDefinition._meta.get_field("job_type").default == "scheduled_task"
    assert JobRun._meta.get_field("status").default == "queued"
    assert JobRun._meta.get_field("trigger_kind").default == "manual"
    assert ChangeRequest._meta.get_field("status").default == "draft"
    assert ChangeRequest._meta.get_field("change_type").default == "normal"
    assert ChangeRequest._meta.get_field("risk_level").default == "medium"
    assert ChangeRequest._meta.get_field("impact_level").default == "minor"
    assert FeatureRollout._meta.get_field("stage").default == "internal"
    assert FeatureRollout._meta.get_field("percentage").default == 0
    assert FeatureRollout._meta.get_field("status").default == "planned"
    assert MaintenanceWindow._meta.get_field("status").default == "draft"
    assert MaintenanceWindow._meta.get_field("recurrence").default == "once"


def test_ac0_run_is_a_dry_run_by_default(db, ac0_run):
    """**Default `True`, deliberately.** The only writer of a `JobRun` in this repository is the
    `run_now` verb, which records a run nobody executed. A `False` on a row written by this
    codebase would be a false claim, and nothing can legitimately clear it."""
    assert JobRun._meta.get_field("is_dry_run").default is True
    assert ac0_run.is_dry_run is True


def test_ac0_job_stamps_start_null_and_recording_a_run_advances_nothing(db, ac0_job):
    """`last_run_at` / `next_run_at` are recorded INTENT. No scheduler exists - nothing advances
    them - so `None` is the honest default and must not be papered over with `timezone.now()`."""
    assert ac0_job.last_run_at is None
    assert ac0_job.next_run_at is None
    JobRun.objects.create(tenant=ac0_job.tenant, job=ac0_job, status="queued")
    ac0_job.refresh_from_db()
    assert ac0_job.last_run_at is None, "recording a run advanced last_run_at"
    assert ac0_job.next_run_at is None, "recording a run advanced next_run_at"


def test_ac0_every_index_name_is_under_mariadb_limit():
    for model in (JobDefinition, JobRun, MaintenanceWindow, ChangeRequest, FeatureRollout):
        for index in model._meta.indexes:
            assert len(index.name) <= MAX_INDEX_NAME, "%s.%s is %d chars" % (
                model.__name__, index.name, len(index.name))



# =================================================================================================
# 4. the clean() guards
#
# Every mutator below is `_ac0_guard_<name>(obj, ctx) -> (expected_error_key, expected_message)`,
# so the table IS the specification and each test body is three lines long. `ctx` carries whatever
# fixtures the guard needs. Every mutator runs at CALL time, never at import time, so every instant
# is derived from a fresh `timezone.now()` (L16).
#
# **All of these go through `full_clean()`, never `save()`.** A `save()` that raises `IntegrityError`
# is a different failure, and a `save()` that never reaches `clean()` at all would leave the lane
# blind. `full_clean()` is what the admin, an API caller and `crud_*` all reach.
# =================================================================================================
def _ac0_guard_run_success_no_finish(run, ctx):
    run.status = "success"
    return "finished_at", "A successful run must record when it finished."


def _ac0_guard_run_failed_no_message(run, ctx):
    run.status = "failed"
    run.finished_at = _ac0_dt(hours=1)
    return "error_message", "A failed run must say what went wrong."


def _ac0_guard_run_failed_no_finish(run, ctx):
    run.status = "failed"
    run.error_message = "Connection refused by the upstream host."
    return "finished_at", "A failed run must record when it finished."


def _ac0_guard_run_backwards(run, ctx):
    run.status = "skipped"  # terminal and unremarkable, so only the date guard can fire
    run.started_at = _ac0_dt(hours=2)
    run.finished_at = _ac0_dt(hours=1)
    return "finished_at", "A run cannot finish before it started."


#: `JobRun`'s four guards, all keyed on a field that IS on the form, so each surfaces as a real
#: field error rather than a non-field one. Contrast with the `*_NON_FIELD` tables below.
_AC0_JOBRUN_GUARDS = [
    ("success_without_finished_at", _ac0_guard_run_success_no_finish),
    ("failed_without_error_message", _ac0_guard_run_failed_no_message),
    ("failed_without_finished_at", _ac0_guard_run_failed_no_finish),
    ("finished_before_started", _ac0_guard_run_backwards),
]


def _ac0_guard_window_no_start(window, ctx):
    window.starts_at = None
    return "starts_at", "A maintenance window must say when it opens."


def _ac0_guard_window_no_end(window, ctx):
    window.ends_at = None
    return "ends_at", "A maintenance window must say when it closes."


def _ac0_guard_window_backwards(window, ctx):
    window.starts_at = _ac0_dt(hours=3)
    window.ends_at = _ac0_dt(hours=1)
    return "ends_at", "A window cannot close before it opens."


def _ac0_guard_window_ended_early_no_stamp(window, ctx):
    window.status = "ended_early"
    window.ended_at = None
    return NON_FIELD_ERRORS, "An ended-early window must record when it was ended."


def _ac0_guard_window_ended_after_close(window, ctx):
    window.status = "ended_early"
    window.starts_at = _ac0_dt(hours=1)
    window.ends_at = _ac0_dt(hours=2)
    window.ended_at = _ac0_dt(hours=3)
    return NON_FIELD_ERRORS, "A window cannot be ended after it was due to close."


#: The first three are keyed on a field the form HAS; the last two are deliberately keyed on
#: `NON_FIELD_ERRORS` because `ended_at` is EXCLUDED from `MaintenanceWindowForm`, and
#: `ModelForm.add_error` raises `ValueError` for a key that is not a form field (X1).
_AC0_WINDOW_FIELD_GUARDS = [
    ("no_starts_at", _ac0_guard_window_no_start),
    ("no_ends_at", _ac0_guard_window_no_end),
    ("ends_before_starts", _ac0_guard_window_backwards),
]
_AC0_WINDOW_NON_FIELD_GUARDS = [
    ("ended_early_without_ended_at", _ac0_guard_window_ended_early_no_stamp),
    ("ended_at_after_ends_at", _ac0_guard_window_ended_after_close),
]



def _ac0_guard_change_approved_no_approver(change, ctx):
    change.status = "approved"
    change.approved_by = None
    change.approved_at = _ac0_dt(days=-1)
    return NON_FIELD_ERRORS, "An approved change must name its approver."


def _ac0_guard_change_approved_no_stamp(change, ctx):
    # Starts from `ac0_change_approved`, which DOES carry an approver, so the ONLY thing missing is
    # the stamp. That is what proves the refusal is about the evidence and not about the status.
    change.approved_at = None
    return NON_FIELD_ERRORS, "An approved change must record when."


def _ac0_guard_change_rolled_back_no_reason(change, ctx):
    change.status = "rolled_back"
    change.rollback_reason = "   "  # whitespace only: `.strip()` makes this "blank"
    change.rollback_at = _ac0_dt(hours=-1)
    return NON_FIELD_ERRORS, "A rollback must say why."


def _ac0_guard_change_rolled_back_no_stamp(change, ctx):
    change.status = "rolled_back"
    change.rollback_reason = "The batch job double-posted the nightly run."
    change.rollback_at = None
    return NON_FIELD_ERRORS, "A rollback must record when."


#: ALL FOUR `ChangeRequest` guards are keyed on `NON_FIELD_ERRORS`, because `approved_by` and
#: `approved_at` are both off `ChangeRequestForm` and a keyed error would 500 the save (X1).
_AC0_CHANGE_NON_FIELD_GUARDS = [
    ("approved_without_approver", _ac0_guard_change_approved_no_approver),
    ("approved_without_approved_at", _ac0_guard_change_approved_no_stamp),
    ("rolled_back_without_reason", _ac0_guard_change_rolled_back_no_reason),
    ("rolled_back_without_rollback_at", _ac0_guard_change_rolled_back_no_stamp),
]


def _ac0_guard_rollout_internal_at_a_percentage(rollout, ctx):
    rollout.stage = "internal"
    rollout.percentage = 25
    return "percentage", "An internal-only stage reaches no users (0%)."


def _ac0_guard_rollout_general_short(rollout, ctx):
    rollout.stage = "general"
    rollout.percentage = 40
    return "percentage", "General availability is 100%."


def _ac0_guard_rollout_partial_at_zero(rollout, ctx):
    rollout.stage = "partial"
    rollout.percentage = 0
    return "percentage", "A partial stage must be between 1% and 99%."


def _ac0_guard_rollout_partial_at_hundred(rollout, ctx):
    rollout.stage = "partial"
    rollout.percentage = 100
    return "percentage", "A partial stage must be between 1% and 99%."


def _ac0_guard_rollout_completed_no_stamp(rollout, ctx):
    rollout.status = "completed"
    rollout.completed_at = None
    return NON_FIELD_ERRORS, "A completed stage must record when it finished."


def _ac0_guard_rollout_finished_before_it_started(rollout, ctx):
    rollout.started_at = _ac0_dt(hours=3)
    rollout.completed_at = _ac0_dt(hours=1)
    return NON_FIELD_ERRORS, "A stage cannot finish before it started."


#: The three ladder bookends are keyed on `percentage` (which IS on the form); the two timestamp
#: guards are keyed on `NON_FIELD_ERRORS` because `started_at` / `completed_at` are off it.
_AC0_ROLLOUT_FIELD_GUARDS = [
    ("internal_at_non_zero", _ac0_guard_rollout_internal_at_a_percentage),
    ("general_below_hundred", _ac0_guard_rollout_general_short),
    ("partial_at_zero", _ac0_guard_rollout_partial_at_zero),
    ("partial_at_hundred", _ac0_guard_rollout_partial_at_hundred),
]
_AC0_ROLLOUT_NON_FIELD_GUARDS = [
    ("completed_without_completed_at", _ac0_guard_rollout_completed_no_stamp),
    ("completed_at_before_started_at", _ac0_guard_rollout_finished_before_it_started),
]



# ---------------------------------------------------------------- JobRun
@pytest.mark.parametrize("guard_id,apply_guard", _AC0_JOBRUN_GUARDS,
                         ids=[i for i, _f in _AC0_JOBRUN_GUARDS])
def test_ac0_jobrun_guards_raise_on_their_own_field(db, tenant_a, ac0_job, guard_id, apply_guard):
    """A success nobody timed is not a success; a failure nobody explained is not a record.

    Each key names a field that IS on `JobRunForm`, so the operator sees the error beside the box
    they have to fix rather than as an unexplained refusal.
    """
    run = JobRun(tenant=tenant_a, job=ac0_job)
    key, needle = apply_guard(run, {})
    with pytest.raises(ValidationError) as exc:
        run.full_clean()
    _ac0_assert_keyed(exc.value, JobRun, key, needle)


def test_ac0_jobrun_a_complete_success_passes_clean(db, ac0_run_success):
    """The positive control: both stamps present and ordered. Without it the guard table above
    could pass by refusing EVERYTHING."""
    ac0_run_success.full_clean()
    assert ac0_run_success.status == "success"
    assert ac0_run_success.finished_at > ac0_run_success.started_at


def test_ac0_jobrun_a_queued_run_with_no_stamps_passes_clean(db, ac0_run):
    """`queued` places no rule in `clean()` - the open state must stay writable, or the run-now
    verb could never record the run it just created."""
    ac0_run.full_clean()


# ---------------------------------------------------------------- MaintenanceWindow
@pytest.mark.parametrize("guard_id,apply_guard", _AC0_WINDOW_FIELD_GUARDS,
                         ids=[i for i, _f in _AC0_WINDOW_FIELD_GUARDS])
def test_ac0_window_guards_raise_on_their_own_field(db, tenant_a, guard_id, apply_guard):
    """A window has an OPEN end and a CLOSED end. A one-ended window is a notice, and 0.17's
    `Incident` already owns notices - this is the same rule enforced on the other object."""
    window = _ac0_clean_window(tenant_a)
    key, needle = apply_guard(window, {})
    with pytest.raises(ValidationError) as exc:
        window.full_clean()
    _ac0_assert_keyed(exc.value, MaintenanceWindow, key, needle)


@pytest.mark.parametrize("guard_id,apply_guard", _AC0_WINDOW_NON_FIELD_GUARDS,
                         ids=[i for i, _f in _AC0_WINDOW_NON_FIELD_GUARDS])
def test_ac0_window_evidence_guards_are_keyed_on_non_field_errors(db, tenant_a, guard_id,
                                                                  apply_guard):
    """**The X1 shape, on `MaintenanceWindow`.** `ended_at` is EXCLUDED from
    `MaintenanceWindowForm`, so a guard keyed on `ended_at` is handed to
    `form.add_error("ended_at", ...)`, which raises `ValueError` for a key that is not a form
    field - turning an ordinary dropdown choice into a 500. These two must fire under `__all__`
    and nothing else, so they RENDER as a non-field error instead of crashing the request.
    """
    window = _ac0_clean_window(tenant_a)
    key, needle = apply_guard(window, {})
    with pytest.raises(ValidationError) as exc:
        window.full_clean()
    assert key == NON_FIELD_ERRORS
    _ac0_assert_non_field(exc.value, needle)


def test_ac0_window_a_legal_window_passes_clean(db, ac0_window, ac0_window_running,
                                                ac0_window_past):
    """Three real windows - future, running, past - all clean. The positive control that keeps the
    guard table above from passing by refusing everything."""
    for window in (ac0_window, ac0_window_running, ac0_window_past):
        window.full_clean()



# ---------------------------------------------------------------- ChangeRequest
@pytest.mark.parametrize("guard_id,apply_guard", _AC0_CHANGE_NON_FIELD_GUARDS,
                         ids=[i for i, _f in _AC0_CHANGE_NON_FIELD_GUARDS])
def test_ac0_change_guards_are_all_keyed_on_non_field_errors(db, ac0_change, ac0_change_approved,
                                                             guard_id, apply_guard):
    """**All four, and this is the load-bearing half of the X1 fix.**

    `approved_by` and `approved_at` are both off `ChangeRequestForm`, and `rollback_reason` /
    `rollback_at` likewise. Keyed on either, an ordinary dropdown choice 500s the save; keyed on
    `__all__` the guard still raises for the admin and for any API caller, but RENDERS on the form.

    The two `approved` cases use DIFFERENT base rows on purpose: one starts from the `submitted`
    fixture with the approver removed (so the refusal is the missing approver), the other from
    `ac0_change_approved`, which already carries an approver and only loses the stamp (so the
    refusal is provably about the evidence, not the status).
    """
    obj = ac0_change_approved if guard_id == "approved_without_approved_at" else ac0_change
    key, needle = apply_guard(obj, {})
    with pytest.raises(ValidationError) as exc:
        obj.full_clean()
    assert key == NON_FIELD_ERRORS
    _ac0_assert_non_field(exc.value, needle)


def test_ac0_change_submitted_and_completed_place_no_rule(db, ac0_change, ac0_change_completed,
                                                          ac0_change_approved):
    """`submitted` and `completed` put NO rule in `clean()` - neither needs an actor. That is
    exactly what makes them the right fixture states, and it is why an approved change with no
    approver can never be a fixture: `crud_edit` runs `full_clean()` on every save, so such a row
    would be unsaveable by construction and the edit page could not be exercised at all.
    """
    for change in (ac0_change, ac0_change_completed, ac0_change_approved):
        change.full_clean()
    assert ac0_change.status == "submitted"
    assert ac0_change_completed.status == "completed"
    assert ac0_change_approved.status == "approved"


def test_ac0_change_an_approved_row_with_no_approver_is_built_in_line(db, ac0_change_draft):
    """The unsaveable row, built in memory only. `status="approved"` with no approver and no stamp
    trips the FIRST of the two guards, which short-circuits - so the assertion is on the key and
    that it raised at all, not on which of two messages surfaced."""
    change = ChangeRequest(tenant=ac0_change_draft.tenant, title="Nobody approved this",
                           status="approved")
    with pytest.raises(ValidationError) as exc:
        change.full_clean()
    _ac0_assert_non_field(exc.value, "approver")


# ---------------------------------------------------------------- FeatureRollout
@pytest.mark.parametrize("guard_id,apply_guard", _AC0_ROLLOUT_FIELD_GUARDS,
                         ids=[i for i, _f in _AC0_ROLLOUT_FIELD_GUARDS])
def test_ac0_rollout_ladder_guards_raise_on_percentage(db, tenant_a, ac0_change, ac0_flag,
                                                        guard_id, apply_guard):
    """The ladder bookends are EXACT, not approximate: "general availability" at 40% is a
    contradiction, and "internal only" at 90% is worse. The stage/percentage pair is a
    DECLARATION, and a self-contradictory declaration is not a record of anything."""
    rollout = _ac0_clean_rollout(tenant_a, ac0_change, ac0_flag)
    key, needle = apply_guard(rollout, {})
    with pytest.raises(ValidationError) as exc:
        rollout.full_clean()
    _ac0_assert_keyed(exc.value, FeatureRollout, key, needle)


@pytest.mark.parametrize("guard_id,apply_guard", _AC0_ROLLOUT_NON_FIELD_GUARDS,
                         ids=[i for i, _f in _AC0_ROLLOUT_NON_FIELD_GUARDS])
def test_ac0_rollout_timestamp_guards_are_keyed_on_non_field_errors(db, tenant_a, ac0_change,
                                                                    ac0_flag, guard_id,
                                                                    apply_guard):
    """**The X1 shape, on `FeatureRollout`.** `started_at` and `completed_at` are both off
    `FeatureRolloutForm`, so keying on them would hand `add_error` an unknown key and 500 the
    save. They must fire under `__all__` and nothing else."""
    rollout = _ac0_clean_rollout(tenant_a, ac0_change, ac0_flag)
    key, needle = apply_guard(rollout, {})
    with pytest.raises(ValidationError) as exc:
        rollout.full_clean()
    assert key == NON_FIELD_ERRORS
    _ac0_assert_non_field(exc.value, needle)



@pytest.mark.parametrize("stage,percentage", [
    ("internal", 0), ("pilot", 1), ("pilot", 50), ("partial", 1), ("partial", 50),
    ("partial", 99), ("general", 100),
], ids=["internal_0", "pilot_1", "pilot_50", "partial_1", "partial_50", "partial_99",
        "general_100"])
def test_ac0_rollout_legal_ladder_positions_are_accepted(db, tenant_a, ac0_change, ac0_flag,
                                                         stage, percentage):
    """The positive control, and the reason the ladder guards can be EXACT: the two bookends are
    pinned at 0% and 100% and the middle rungs are strictly between them."""
    _ac0_clean_rollout(tenant_a, ac0_change, ac0_flag,
                       stage=stage, percentage=percentage).full_clean()


def test_ac0_rollout_a_completed_stage_with_its_stamp_passes_clean(db, tenant_a, ac0_change,
                                                                    ac0_flag):
    """`completed` IS saveable - with the evidence. The guard is about the missing stamp, not
    about the status, exactly as with the window's `ended_early`."""
    _ac0_clean_rollout(tenant_a, ac0_change, ac0_flag, status="completed",
                       started_at=_ac0_dt(hours=1), completed_at=_ac0_dt(hours=2)).full_clean()


def test_ac0_percentage_over_one_hundred_is_refused_by_the_field(db, tenant_a, ac0_change,
                                                                 ac0_flag):
    """`MaxValueValidator(100)` lives on the FIELD, not in `clean()`, so this one fires from
    `clean_fields` - a different mechanism from the ladder guards above, and worth pinning apart."""
    rollout = _ac0_clean_rollout(tenant_a, ac0_change, ac0_flag, stage="general", percentage=140)
    with pytest.raises(ValidationError) as exc:
        rollout.full_clean()
    assert "percentage" in exc.value.error_dict



# =================================================================================================
# 5. the derived properties
# =================================================================================================
@pytest.mark.parametrize("status,expected", [
    ("queued", True), ("running", True),
    ("success", False), ("failed", False), ("skipped", False), ("cancelled", False),
])
def test_ac0_run_is_open_only_while_an_outcome_is_promised(db, tenant_a, ac0_job, status,
                                                          expected):
    """`queued` and `running` are OPEN - the states that promise an outcome nobody has delivered.
    Every other status is terminal. This is what the admin board's open-runs tile counts, so the
    boundary is load-bearing in BOTH directions: a false True inflates the tile, a false False
    hides a run that never finished."""
    run = JobRun(tenant=tenant_a, job=ac0_job, status=status)
    assert run.is_open is expected, "%s should be open=%s" % (status, expected)
    assert isinstance(JobRun.is_open, property)


def test_ac0_run_is_open_on_the_fixtures(db, ac0_run, ac0_run_success):
    assert ac0_run.status == "queued"
    assert ac0_run.is_open is True
    assert ac0_run_success.status == "success"
    assert ac0_run_success.is_open is False


def test_ac0_run_duration_display_is_real_when_both_stamps_exist(db, ac0_run_success):
    """90 seconds of work renders as `90000 ms` - derived from the two stamps, not read off the
    stored `duration_ms`, so the display cannot disagree with the evidence it describes."""
    text = ac0_run_success.duration_display
    assert text == "90000 ms", "got %r" % text
    assert text != EM_DASH


@pytest.mark.parametrize("stamp", ["neither", "started_only", "finished_only"],
                         ids=["no_stamps", "started_only", "finished_only"])
def test_ac0_run_duration_display_is_an_em_dash_when_a_stamp_is_missing(db, tenant_a, ac0_job,
                                                                      stamp):
    """**Never `0`.** A run that took no measurable time and a run nobody measured are DIFFERENT
    statements, and collapsing them into the same "0ms" is the null-means-zero defect. The em dash
    says "not measured"; `0 ms` would say "it was instantaneous", which is a claim about work."""
    run = JobRun(tenant=tenant_a, job=ac0_job, status="running")
    if stamp == "started_only":
        run.started_at = _ac0_dt(minutes=-5)
    elif stamp == "finished_only":
        run.finished_at = _ac0_dt(minutes=-5)
    text = run.duration_display
    assert text == EM_DASH, "got %r" % text
    assert text not in ("0", "0ms", "0 ms", "0.0s"), (
        "an unmeasured run must never render as zero")


def test_ac0_run_zero_length_and_unmeasured_are_different_statements(db, tenant_a, ac0_job,
                                                                     ac0_run):
    """A run whose two stamps are EQUAL genuinely took no time, and that is a fact about work. An
    unmeasured run has no stamps at all, and that is a fact about EVIDENCE. They must not render
    identically - the pair is the whole point of the em dash."""
    instant = _ac0_dt(minutes=-5)
    measured_zero = JobRun(tenant=tenant_a, job=ac0_job, status="success", started_at=instant,
                           finished_at=instant)
    assert measured_zero.duration_display == "0 ms"
    assert ac0_run.duration_display == EM_DASH
    assert measured_zero.duration_display != ac0_run.duration_display



def test_ac0_window_is_future_drives_deletability(db, ac0_window, ac0_window_running,
                                                  ac0_window_past):
    """**This property IS the delete rule.** The view and the Actions column read `is_future`, not
    the module constant `FUTURE_STATUSES`: the property carries the timestamp in it, so a `draft`
    whose start has passed is history and is kept. Only a window that has not begun is deletable.
    Asserting the property rather than the tuple keeps the view and this test on one rule."""
    assert ac0_window.is_future is True
    assert ac0_window_running.is_future is False, "a running window is not deletable"
    assert ac0_window_past.is_future is False, "a window somebody ran is evidence, not a draft"
    assert isinstance(MaintenanceWindow.is_future, property)


def test_ac0_window_is_future_is_false_without_a_start(db, tenant_a):
    """A window with no `starts_at` is not in the future - it is incomplete, and `is_future`
    answers with `bool(self.starts_at)` so an unset stamp never reads as a deletable draft."""
    window = MaintenanceWindow(tenant=tenant_a, title="No start", starts_at=None,
                               ends_at=_ac0_dt(hours=1))
    assert window.is_future is False


def test_ac0_window_is_current_only_while_now_is_inside_it(db, ac0_window, ac0_window_running,
                                                          ac0_window_past):
    """`starts_at <= now < ends_at` - a half-open interval, so the instant a window closes it is no
    longer current and never overlaps the next one."""
    assert ac0_window_running.is_current is True
    assert ac0_window.is_current is False, "a window that has not opened is not current"
    assert ac0_window_past.is_current is False
    assert isinstance(MaintenanceWindow.is_current, property)


def test_ac0_window_is_current_is_false_without_an_end(db, tenant_a):
    window = MaintenanceWindow(tenant=tenant_a, title="No end", starts_at=_ac0_dt(hours=-1),
                               ends_at=None)
    assert window.is_current is False


@pytest.mark.parametrize("hours,expected", [(0, "0m"), (1, "1h"), (2, "2h"), (1.5, "1h 30m"),
                                            (0.75, "45m")],
                         ids=["zero", "1h", "2h", "1h30m", "45m"])
def test_ac0_window_duration_human_renders_the_declared_length(db, tenant_a, hours, expected):
    window = MaintenanceWindow(tenant=tenant_a, title="Measured", starts_at=_ac0_dt(hours=0),
                               ends_at=_ac0_dt(hours=hours))
    assert window.duration_human == expected


@pytest.mark.parametrize("stamp", ["no_stamps", "no_start", "no_end"],
                         ids=["no_stamps", "no_start", "no_end"])
def test_ac0_window_duration_human_is_an_em_dash_when_an_end_is_missing(db, tenant_a, stamp):
    """The same zero rule as `JobRun.duration_display`, for the same reason: a window nobody
    bounded is not a zero-length window."""
    window = MaintenanceWindow(tenant=tenant_a, title="Unmeasured", starts_at=_ac0_dt(hours=1),
                               ends_at=_ac0_dt(hours=2))
    if stamp == "no_stamps":
        window.starts_at = window.ends_at = None
    elif stamp == "no_start":
        window.starts_at = None
    else:
        window.ends_at = None
    text = window.duration_human
    assert text == EM_DASH, "got %r" % text
    assert text not in ("0", "0m", "0h"), "an unmeasured window must never render as zero"


def test_ac0_window_duration_human_on_the_fixtures(db, ac0_window, ac0_window_running,
                                                   ac0_window_past):
    """Read the length straight off the two stamps, so the property cannot drift from the data.

    The expected value is DERIVED here rather than hardcoded to "3h"/"2h"/"1h": a fixture's duration
    is a fact about the fixture, and a hardcoded literal in the test is a second place to update when
    the fixture changes - and the silent way to be wrong about both at once.
    """
    for window in (ac0_window, ac0_window_running, ac0_window_past):
        hours = int((window.ends_at - window.starts_at).total_seconds() // 3600)
        assert window.duration_human == "%dh" % hours, (
            "%s: duration_human %r does not match its own %dh span"
            % (window.number, window.duration_human, hours))



def test_ac0_change_rollout_count_is_a_property_not_an_annotation(db, ac0_change, ac0_rollout,
                                                                   ac0_rollout_alt):
    """**Must never become an `annotate()` alias** (L57 - it shipped twice). A `property` is a data
    descriptor, so `ModelIterable` cannot `setattr` an annotation of the same name onto the
    instance and the query dies with `AttributeError: can't set attribute` the first time a row is
    instantiated. The property is also prefetch-aware, so a view that passes
    `prefetch_related("rollouts")` pays for the count zero extra times - proved here by query
    count rather than by a hard budget."""
    assert isinstance(ChangeRequest.rollout_count, property)
    assert ac0_change.rollout_count == 2, "two stages hang off ac0_change, on two different flags"

    prefetched = ChangeRequest.objects.prefetch_related("rollouts").get(pk=ac0_change.pk)
    assert prefetched.rollout_count == 2
    assert "rollouts" in prefetched._prefetched_objects_cache, (
        "the prefetch cache is what makes the count free on the detail page")
    with CaptureQueriesContext(connection) as captured:
        assert prefetched.rollout_count == 2
    assert len(captured.captured_queries) == 0, "a prefetched count must not re-query"


def test_ac0_change_rollout_count_is_correct_without_a_prefetch(db, ac0_change, ac0_rollout,
                                                                ac0_rollout_alt):
    """The un-prefetched path must still be CORRECT (a real count), just not free - the two
    branches of the property have to agree or a detail page and a list would disagree."""
    plain = ChangeRequest.objects.get(pk=ac0_change.pk)
    assert plain.rollout_count == 2
    assert plain.rollout_count == ac0_change.rollout_count



# =================================================================================================
# 6. FeatureRollout's unique_together - enforced by the DATABASE
# =================================================================================================
def test_ac0_rollout_change_flag_pair_is_declared_unique():
    assert FeatureRollout._meta.unique_together == (("change", "feature_flag"),)
    assert set(FeatureRollout._meta.unique_together[0]) == {"change", "feature_flag"}


def test_ac0_rollout_a_duplicate_change_flag_pair_is_refused_by_the_database(db, ac0_rollout):
    """**This is why the pair is worth a fixture.** `unique_together` is enforced by the DATABASE
    only - there is no `clean()` guard for it - so the duplicate surfaces as an `IntegrityError`
    and, in a view, as a **500**. Only the form's hand-written `clean_feature_flag` (lane 3) turns
    it into a field error. Asserted here at the level that actually enforces it.

    The `transaction.atomic()` wrapper is not decoration: without it the `IntegrityError` leaves
    the test's transaction broken and every later query in the test errors.
    """
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            FeatureRollout.objects.create(
                tenant=ac0_rollout.tenant, change=ac0_rollout.change,
                feature_flag=ac0_rollout.feature_flag, stage="general", percentage=100)
    assert FeatureRollout.objects.filter(change=ac0_rollout.change,
                                         feature_flag=ac0_rollout.feature_flag).count() == 1, (
        "the refused duplicate must not have been written")


def test_ac0_rollout_a_duplicate_pair_is_also_flagged_by_full_clean(db, ac0_rollout):
    """`full_clean()` runs `validate_unique()`, so the same duplicate is a `ValidationError` under
    `__all__` when a caller cleans before saving - and it must be a NON-field key, because
    `ModelForm._post_clean()` would otherwise 500 on an unknown field."""
    duplicate = FeatureRollout(tenant=ac0_rollout.tenant, change=ac0_rollout.change,
                               feature_flag=ac0_rollout.feature_flag, stage="partial",
                               percentage=50)
    with pytest.raises(ValidationError) as exc:
        duplicate.full_clean()
    assert NON_FIELD_ERRORS in exc.value.error_dict


def test_ac0_rollout_a_second_flag_under_one_change_is_legal(db, ac0_rollout, ac0_rollout_alt,
                                                            ac0_change):
    """A change stages each flag ONCE, so two stages under one change need two flags. That is the
    only legal way to build a ladder, and it is what makes `rollout_count == 2` provable against a
    real sibling row rather than against a mock."""
    assert ac0_rollout.change_id == ac0_rollout_alt.change_id, "both hang off the same change"
    assert ac0_rollout.feature_flag_id != ac0_rollout_alt.feature_flag_id, "different flags"
    assert (ac0_rollout.stage, ac0_rollout.percentage) == ("partial", 25)
    assert (ac0_rollout_alt.stage, ac0_rollout_alt.percentage) == ("general", 100)
    assert FeatureRollout.objects.filter(change=ac0_change).count() == 2


def test_ac0_rollout_the_pair_is_unique_per_change_not_per_flag(db, ac0_rollout, ac0_rollout_b,
                                                                ac0_flag):
    """`ac0_rollout_b` deliberately reuses tenant_a's `ac0_flag` under a DIFFERENT change, which is
    legal: the constraint is `(change, feature_flag)`, not `feature_flag` alone."""
    assert ac0_rollout_b.feature_flag_id == ac0_flag.pk
    assert ac0_rollout_b.change_id != ac0_rollout.change_id
    assert FeatureRollout.objects.filter(feature_flag=ac0_flag).count() == 2


def test_ac0_rollout_varying_the_stage_cannot_escape_the_pair(db, ac0_rollout):
    """The negative, one level up: not even a different `stage` may escape the constraint. The
    pair is `(change, feature_flag)` and nothing else - a second stage on the same flag under the
    same change is the same pair, however it is labelled."""
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            FeatureRollout.objects.create(
                tenant=ac0_rollout.tenant, change=ac0_rollout.change,
                feature_flag=ac0_rollout.feature_flag, stage="internal", percentage=0)



# =================================================================================================
# 7. tenancy
#
# Every one of the five carries `tenant = FK("core.Tenant", CASCADE, db_index=True)` and every
# view filters `tenant=request.tenant` on all six verbs. These are the model-layer halves of that
# rule: the tenant column exists, it is indexed, and a `tenant_b` row is unreachable from a
# `tenant_a` queryset. The HTTP halves (404 on a crafted pk, 403 for a member) are lane 4.
# =================================================================================================
@pytest.mark.parametrize("model", [JobDefinition, JobRun, MaintenanceWindow, ChangeRequest,
                                   FeatureRollout])
def test_ac0_every_model_carries_an_indexed_tenant(model):
    tenant_field = model._meta.get_field("tenant")
    assert tenant_field.db_index is True, (
        "%s.tenant is not db_index, so every list query is a scan" % model.__name__)
    assert tenant_field.null is False, (
        "%s.tenant is nullable, so an orphan row is reachable by nobody" % model.__name__)
    # `on_delete` on the *remote* field is the `django.db.models.CASCADE` callable itself, not a
    # symbol, so assert identity against the function rather than reading a `.name` off it.
    assert tenant_field.remote_field.on_delete is models.CASCADE


def test_ac0_job_tenancy_is_scoped_to_the_request_tenant(db, tenant_a, tenant_b, ac0_job,
                                                         ac0_job_b):
    _ac0_tenant_scoped(JobDefinition, tenant_a, ac0_job, ac0_job_b)
    _ac0_tenant_scoped(JobDefinition, tenant_b, ac0_job_b, ac0_job)


def test_ac0_run_tenancy_is_scoped_to_the_request_tenant(db, tenant_a, tenant_b, ac0_run,
                                                         ac0_run_b):
    _ac0_tenant_scoped(JobRun, tenant_a, ac0_run, ac0_run_b)
    _ac0_tenant_scoped(JobRun, tenant_b, ac0_run_b, ac0_run)


def test_ac0_window_tenancy_is_scoped_to_the_request_tenant(db, tenant_a, tenant_b, ac0_window,
                                                            ac0_window_b):
    _ac0_tenant_scoped(MaintenanceWindow, tenant_a, ac0_window, ac0_window_b)
    _ac0_tenant_scoped(MaintenanceWindow, tenant_b, ac0_window_b, ac0_window)


def test_ac0_change_tenancy_is_scoped_to_the_request_tenant(db, tenant_a, tenant_b, ac0_change,
                                                            ac0_change_b):
    _ac0_tenant_scoped(ChangeRequest, tenant_a, ac0_change, ac0_change_b)
    _ac0_tenant_scoped(ChangeRequest, tenant_b, ac0_change_b, ac0_change)


def test_ac0_rollout_tenancy_is_scoped_to_the_request_tenant(db, tenant_a, tenant_b, ac0_rollout,
                                                             ac0_rollout_b):
    _ac0_tenant_scoped(FeatureRollout, tenant_a, ac0_rollout, ac0_rollout_b)
    _ac0_tenant_scoped(FeatureRollout, tenant_b, ac0_rollout_b, ac0_rollout)


def test_ac0_a_tenant_never_sees_another_tenants_rows(db, tenant_a, tenant_b, ac0_job, ac0_job_b,
                                                      ac0_run, ac0_run_b, ac0_window, ac0_window_b,
                                                      ac0_change, ac0_change_b, ac0_rollout,
                                                      ac0_rollout_b):
    """The whole set at once: a tenant_a register shows exactly tenant_a's rows and a tenant_b
    register exactly tenant_b's. A leak in any ONE model is a workspace boundary broken."""
    for model, own_a, own_b in [
        (JobDefinition, ac0_job, ac0_job_b),
        (JobRun, ac0_run, ac0_run_b),
        (MaintenanceWindow, ac0_window, ac0_window_b),
        (ChangeRequest, ac0_change, ac0_change_b),
        (FeatureRollout, ac0_rollout, ac0_rollout_b),
    ]:
        a_pks = set(model.objects.filter(tenant=tenant_a).values_list("pk", flat=True))
        b_pks = set(model.objects.filter(tenant=tenant_b).values_list("pk", flat=True))
        assert own_a.pk in a_pks and own_a.pk not in b_pks, model.__name__
        assert own_b.pk in b_pks and own_b.pk not in a_pks, model.__name__


def test_ac0_an_unfiltered_queryset_crosses_the_boundary(db, ac0_job, ac0_job_b):
    """The un-filtered manager crosses tenants - which is precisely why every view must filter.
    If this ever stopped being true, the views' `tenant=request.tenant` would be the only thing
    between two workspaces and this test would no longer be proving anything."""
    every_pk = set(JobDefinition.objects.values_list("pk", flat=True))
    assert ac0_job.pk in every_pk and ac0_job_b.pk in every_pk
    assert ac0_job.tenant_id != ac0_job_b.tenant_id


def test_ac0_ordering_is_a_presentation_order_not_a_tenant_filter(db, ac0_job, ac0_job_muted,
                                                                   ac0_job_b):
    """`Meta.ordering` sorts rows; it never isolates them. `ac0_job_b` is deliberately present in
    the un-filtered list, so a lane-3 view test that forgets the tenant filter cannot pass by
    accident on an empty-looking page."""
    assert JobDefinition._meta.ordering == ["name"]
    names = list(JobDefinition.objects.values_list("name", flat=True))
    assert names == sorted(names), "the declared ordering is not what Meta says it is"
    assert ac0_job_b.name in names, "ordering is not a tenant filter, by design"
    assert ac0_job_muted.is_muted is True and ac0_job.is_muted is False

