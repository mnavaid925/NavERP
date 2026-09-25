"""0.16 model-lane tests — Backup, Recovery & Data Lifecycle.

Contract: `.claude/tasks/test-contract-core-0.16.md` §4. Every assertion target below is pinned there
before this file existed.

The theme of this lane: **the states a naive register omits.** An in-flight backup, a cancelled one, a
partial one people would trust, a hold that is released rather than expired, a cycle between two
environments, and a FK pointing into the wrong workspace. Each of those is a state where the *obvious*
implementation is wrong, and several of them were shipped wrong and fixed in Phase 5 — the fix id is
named on the test so a regression can be traced to its finding.
"""
import datetime

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.core.models import (
    BackupJob,
    DataArchive,
    EnvironmentInstance,
    LegalHold,
    RecoveryDrill,
    RecoveryPosture,
    RestoreRecord,
)
from apps.core.tests.conftest import (
    _bkp_archive,
    _bkp_env,
    _bkp_hold,
    _bkp_job,
    _bkp_key,
)


# ============================================================ BackupJob derived state (C5)

class TestBackupJobIsInFlight:
    """C5's root cause: the board could not tell in-flight work from settled work."""

    def test_queued_is_in_flight(self, bkp_queued_job_a):
        assert bkp_queued_job_a.is_in_flight is True

    def test_running_is_in_flight(self, bkp_running_job_a):
        assert bkp_running_job_a.is_in_flight is True

    def test_success_is_not_in_flight(self, bkp_verified_job_a):
        assert bkp_verified_job_a.is_in_flight is False

    def test_partial_is_not_in_flight(self, bkp_partial_job_a):
        assert bkp_partial_job_a.is_in_flight is False

    def test_failed_is_not_in_flight(self, bkp_failed_job_a):
        assert bkp_failed_job_a.is_in_flight is False

    def test_cancelled_is_NOT_in_flight_even_though_it_has_no_started_at(self, bkp_cancelled_job_a):
        """THE BOUNDARY THAT MATTERS.

        A cancelled backup has `started_at=None`, exactly like a queued one, so an implementation that
        keyed off "has no start time" would sweep it into the in-flight group. It is SETTLED: it has a
        result, and its absent integrity check is a finding rather than "not yet a question".
        """
        assert bkp_cancelled_job_a.started_at is None
        assert bkp_cancelled_job_a.is_in_flight is False

    def test_is_in_flight_is_not_the_negation_of_is_verified(self, bkp_queued_job_a, bkp_failed_job_a):
        """Both rows are UNVERIFIED; they must differ on `is_in_flight`.

        This is the conflation C5 fixed. If `is_in_flight` were implemented as `not is_verified`, both
        would be True and the queued backup would be named as an untested claim.
        """
        assert bkp_queued_job_a.is_verified is False
        assert bkp_failed_job_a.is_verified is False
        assert bkp_queued_job_a.is_in_flight is True
        assert bkp_failed_job_a.is_in_flight is False

    def test_in_flight_statuses_vocabulary(self):
        assert BackupJob.IN_FLIGHT_STATUSES == ("queued", "running")
        # And every member is a real status, so the tuple cannot drift out of the choices.
        valid = {value for value, _label in BackupJob.STATUS_CHOICES}
        assert set(BackupJob.IN_FLIGHT_STATUSES) <= valid


class TestBackupJobDerived:
    def test_is_verified_is_a_property_not_a_field(self):
        """`BackupJob.is_verified` is derived; `RestoreRecord.is_verified` is a stored claim.

        Asserted so a future test cannot treat the two the same way.
        """
        assert isinstance(BackupJob.is_verified, property)
        assert not any(f.name == "is_verified" for f in BackupJob._meta.fields)

    def test_is_partial_is_warning(self, bkp_partial_job_a, bkp_verified_job_a):
        assert bkp_partial_job_a.is_partial is True
        assert bkp_verified_job_a.is_partial is False

    def test_duration_is_None_when_either_stamp_is_missing(self, bkp_queued_job_a, bkp_verified_job_a):
        """A missing stamp is `None`, never a zero-length duration."""
        assert bkp_queued_job_a.duration is None
        assert bkp_verified_job_a.duration is not None

    def test_size_display_is_dash_for_null(self, tenant_a):
        """NULL bytes means "not reported", which is NOT the same as 0 bytes."""
        assert _bkp_job(tenant_a, name="No size reported", size_bytes=None).size_display == "—"
        assert _bkp_job(tenant_a, name="Zero bytes", size_bytes=0).size_display == "0 B"


# ============================================================ LegalHold rules (C3, I7)

class TestLegalHoldStatusCoherence:
    """C3: two fields that must agree are one field's worth of information."""

    def test_active_with_a_release_date_is_refused(self, tenant_a):
        hold = LegalHold(tenant=tenant_a, name="Incoherent",
                         issued_at=timezone.now() - datetime.timedelta(days=10),
                         status="active", released_at=timezone.now() - datetime.timedelta(days=1))
        with pytest.raises(ValidationError) as exc:
            hold.full_clean()
        assert "status" in exc.value.message_dict

    def test_released_without_a_release_date_is_refused(self, tenant_a):
        hold = LegalHold(tenant=tenant_a, name="Released but undated",
                         issued_at=timezone.now() - datetime.timedelta(days=10),
                         status="released", released_at=None)
        with pytest.raises(ValidationError) as exc:
            hold.full_clean()
        assert "released_at" in exc.value.message_dict

    @pytest.mark.parametrize("status,released", [
        ("active", None),
        ("released", "issued_plus_1h"),
        ("expired", None),
        ("superseded", None),
    ])
    def test_the_four_legitimate_states_all_pass(self, tenant_a, status, released):
        """THE CONTROL. A rule that refused everything would pass the two tests above.

        `expired` and `superseded` are the states C3's template previously described as "the schedule
        has resumed", which is only true of `released`.
        """
        issued = timezone.now() - datetime.timedelta(days=10)
        hold = LegalHold(tenant=tenant_a, name="Legit %s" % status, issued_at=issued,
                         status=status,
                         released_at=(issued + datetime.timedelta(hours=1)
                                      if released == "issued_plus_1h" else None))
        hold.full_clean()          # must NOT raise

    def test_rule_1_still_fires_for_a_genuinely_backdated_release(self, tenant_a):
        hold = LegalHold(tenant=tenant_a, name="Backdated", issued_at=timezone.now(),
                         status="released",
                         released_at=timezone.now() - datetime.timedelta(days=5))
        with pytest.raises(ValidationError) as exc:
            hold.full_clean()
        assert "released_at" in exc.value.message_dict


class TestLegalHoldSameMinuteRelease:
    """I7: the release widget is minute-precision, so a strict comparison refused a same-minute release."""

    def test_released_in_the_same_minute_as_issue_is_accepted(self, tenant_a):
        """`issued_at` carries seconds; the form can only express minutes. Truncating to the minute the
        UI can express is the fix — without it, the most common real correction is impossible."""
        issued = timezone.now().replace(second=3, microsecond=523112)
        released = issued.replace(second=0, microsecond=0)
        hold = LegalHold(tenant=tenant_a, name="Same minute", issued_at=issued,
                         status="released", released_at=released)
        hold.full_clean()          # must NOT raise

    def test_a_release_one_minute_earlier_is_still_refused(self, tenant_a):
        """The fix must not have widened the rule into accepting a real backdating."""
        issued = timezone.now().replace(second=0, microsecond=0)
        hold = LegalHold(tenant=tenant_a, name="One minute early", issued_at=issued,
                         status="released", released_at=issued - datetime.timedelta(minutes=1))
        with pytest.raises(ValidationError) as exc:
            hold.full_clean()
        assert "released_at" in exc.value.message_dict


class TestLegalHoldAntiSpoliation:
    """Rule 2 — Exterro's "no mistaken release". The reason the rule is at the model edge."""

    def test_releasing_while_a_sibling_hold_covers_the_same_policy_is_refused(self, tenant_a):
        policy = _policy(tenant_a)
        blocker = _bkp_hold(tenant_a, name="Blocker", status="active", retention_policy=policy)
        target = LegalHold(tenant=tenant_a, name="To release",
                           issued_at=timezone.now() - datetime.timedelta(days=5),
                           retention_policy=policy, status="released", released_at=timezone.now())
        with pytest.raises(ValidationError) as exc:
            target.full_clean()
        assert "status" in exc.value.message_dict
        # The message must NAME the blocking hold — a refusal that does not say which hold is in the way
        # leaves the operator unable to act.
        assert blocker.name in str(exc.value)

    def test_a_sibling_on_a_different_scope_does_not_block(self, tenant_a):
        """The control: a rule that refused any sibling would make every second hold unreleasable."""
        mine = _policy(tenant_a, model_label="core.BackupJob")
        theirs = _policy(tenant_a, model_label="core.DataArchive")
        _bkp_hold(tenant_a, name="Unrelated", status="active", retention_policy=theirs)
        target = LegalHold(tenant=tenant_a, name="Mine", issued_at=timezone.now() - datetime.timedelta(days=5),
                           retention_policy=mine, status="released", released_at=timezone.now())
        target.full_clean()        # must NOT raise

    def test_releasing_itself_is_not_blocked_by_itself(self, tenant_a, bkp_hold_active_a):
        """`exclude(pk=self.pk)` — otherwise no hold could ever be released."""
        bkp_hold_active_a.status = "released"
        bkp_hold_active_a.released_at = timezone.now()
        bkp_hold_active_a.full_clean()     # must NOT raise


class TestLegalHoldDerived:
    def test_is_active_requires_both(self, bkp_hold_active_a, bkp_hold_released_a):
        assert bkp_hold_active_a.is_active is True
        assert bkp_hold_released_a.is_active is False

    def test_scope_label_falls_back(self, tenant_a):
        assert LegalHold(tenant=tenant_a, name="x").scope_label == "workspace-wide"
        assert LegalHold(tenant=tenant_a, name="x", model_label="core.Party").scope_label == "core.Party"
        policy = _policy(tenant_a, name="Finance records")
        assert LegalHold(tenant=tenant_a, name="x", retention_policy=policy).scope_label == "Finance records"

    def test_suspends_policy_matches_by_policy_or_model_label(self, tenant_a):
        policy = _policy(tenant_a, model_label="core.BackupJob")
        by_policy = _bkp_hold(tenant_a, name="By policy", retention_policy=policy)
        by_label = _bkp_hold(tenant_a, name="By label", model_label="core.BackupJob")
        unrelated = _bkp_hold(tenant_a, name="Unrelated", model_label="core.Party")
        assert by_policy.suspends_policy(policy) is True
        assert by_label.suspends_policy(policy) is True
        assert unrelated.suspends_policy(policy) is False

    def test_a_released_hold_suspends_nothing(self, tenant_a, bkp_hold_released_a):
        """The whole point of `suspends_policy` gating on `is_active` — C2."""
        policy = _policy(tenant_a, model_label="core.BackupJob")
        assert bkp_hold_released_a.suspends_policy(policy) is False

    def test_active_for_tenant_excludes_released_rows(self, tenant_a, bkp_hold_active_a, bkp_hold_released_a):
        names = [h.name for h in LegalHold.active_for_tenant(tenant_a)]
        assert bkp_hold_active_a.name in names
        assert bkp_hold_released_a.name not in names


def _policy(tenant, **overrides):
    from apps.core.models import RetentionPolicy
    fields = dict(name="Finance records", model_label="", retention_months=24, action="archive")
    fields.update(overrides)
    return RetentionPolicy.objects.create(tenant=tenant, **fields)


# ============================================================ RestoreRecord (I1)

class TestRestoreRecordIsRestorable:
    """I1: a register that accepts "archive retrieval → succeeded" against an archive its own page
    calls unrestorable is the mirror image of 0.8's fake-destruction dishonesty."""

    def test_a_succeeded_restore_from_an_unrestorable_archive_is_refused(self, tenant_a, bkp_archive_lost_a):
        record = RestoreRecord(tenant=tenant_a, archive=bkp_archive_lost_a, scope="archive_retrieval",
                               status="succeeded", target_time=timezone.now())
        with pytest.raises(ValidationError) as exc:
            record.full_clean()
        assert "archive" in exc.value.message_dict

    def test_the_same_restore_from_a_restorable_archive_is_accepted(self, tenant_a, bkp_archive_ok_a):
        """THE CONTROL — a rule that refused every archive would pass the test above."""
        record = RestoreRecord(tenant=tenant_a, archive=bkp_archive_ok_a, scope="archive_retrieval",
                               status="succeeded", target_time=timezone.now())
        record.full_clean()        # must NOT raise

    def test_the_guard_does_not_fire_when_no_archive_is_named(self, tenant_a, bkp_verified_job_a):
        """A restore need not come from an archive — most come from a backup."""
        record = RestoreRecord(tenant=tenant_a, backup=bkp_verified_job_a, scope="full_instance",
                               status="succeeded", target_time=timezone.now())
        record.full_clean()        # must NOT raise


class TestDataArchiveIsRestorable:
    """`is_restorable` is False when the archive has no location OR is lost/destroyed.

    The locationless states are built with `_validate=False` because the FORM refuses an empty
    `location` (`blank=False`) while the DATABASE accepts it — and it is the database state the board
    counts. Asserting on it requires building it the way the seeder does.
    """

    def test_locationless_is_unrestorable(self, tenant_a):
        assert _bkp_archive(tenant_a, _validate=False, location="", status="active").is_restorable is False

    def test_lost_is_unrestorable(self, tenant_a):
        assert _bkp_archive(tenant_a, status="lost").is_restorable is False

    def test_destroyed_is_unrestorable(self, tenant_a):
        assert _bkp_archive(tenant_a, status="destroyed").is_restorable is False

    def test_active_with_a_location_is_restorable(self, tenant_a):
        assert _bkp_archive(tenant_a, status="active").is_restorable is True

    def test_a_row_that_is_BOTH_locationless_and_lost_is_one_boolean(self, tenant_a):
        """A row satisfying both disjuncts is still ONE row. This is the shape that made a count
        computed by subtraction double-count — the orchestrator's own C4 probe made exactly that
        mistake and reported a defect the view did not have — so the shape is pinned here."""
        archive = _bkp_archive(tenant_a, _validate=False, location="", status="lost")
        assert archive.is_restorable is False
        # And the two disjuncts both match it, which is why a naive `total - complement` double-counts.
        assert DataArchive.objects.filter(pk=archive.pk).filter(location="").exists()
        assert DataArchive.objects.filter(pk=archive.pk).filter(status__in=["lost", "destroyed"]).exists()


# ============================================================ EnvironmentInstance (I8)

class TestEnvironmentInstanceCycle:
    """I8: the FK is self-referential and nothing checked transitivity, so A→B→A was storable.

    A future template that walks `while env.source_environment:` — the obvious way to render
    "derived from → → production" — would loop forever on the first cycle an operator creates by
    accident.
    """

    def test_a_self_edge_is_refused(self, tenant_a, bkp_env_a):
        bkp_env_a.source_environment = bkp_env_a
        with pytest.raises(ValidationError):
            bkp_env_a.full_clean()

    def test_a_two_node_cycle_is_refused(self, tenant_a, bkp_env_sandbox_a, bkp_env_production_a):
        """The cycle the review proved reachable through the shipped edit form."""
        bkp_env_sandbox_a.source_environment = bkp_env_production_a
        bkp_env_sandbox_a.full_clean()               # A -> production is fine
        bkp_env_sandbox_a.save()

        bkp_env_production_a.source_environment = bkp_env_sandbox_a
        with pytest.raises(ValidationError) as exc:
            bkp_env_production_a.full_clean()
        assert "source_environment" in exc.value.message_dict

    def test_a_refresh_source_cycle_is_also_refused(self, tenant_a, bkp_env_sandbox_a, bkp_env_production_a):
        """The finding names both FK fields; a fix for one is half a fix."""
        bkp_env_sandbox_a.refresh_source = bkp_env_production_a
        bkp_env_sandbox_a.full_clean()
        bkp_env_sandbox_a.save()

        bkp_env_production_a.refresh_source = bkp_env_sandbox_a
        with pytest.raises(ValidationError) as exc:
            bkp_env_production_a.full_clean()
        assert "refresh_source" in exc.value.message_dict

    def test_a_legitimate_three_long_chain_is_accepted(self, tenant_a):
        """THE CONTROL — a cycle check that refused any depth would pass the tests above and break the
        feature it protects (NetSuite's refresh chain is the model's own stated use case)."""
        production = _bkp_env(tenant_a, name="Production", kind="production")
        staging = _bkp_env(tenant_a, name="Staging", kind="staging", source_environment=production)
        sandbox = _bkp_env(tenant_a, name="Sandbox", kind="sandbox", source_environment=staging)
        sandbox.full_clean()          # must NOT raise
        assert sandbox.source_environment.source_environment == production

    def test_the_cycle_state_is_reachable_so_the_guard_matters(self, bkp_env_cycle_a):
        """The fixture builds the cycle with `objects.create()` — i.e. the state exists in the database
        and pages must survive it. This is why the rule belongs in `clean()` and the pages still need
        to be robust."""
        assert bkp_env_cycle_a["a"].source_environment_id == bkp_env_cycle_a["b"].pk
        assert bkp_env_cycle_a["b"].source_environment_id == bkp_env_cycle_a["a"].pk


# ============================================================ TenantConsistentMixin (I2)

class TestTenantConsistentMixin:
    """I2: the admin uses a plain `ModelForm` with no narrowing, so the rule must live at the model
    edge. Without it a workspace's sandbox can be recorded as a clone of another tenant's production
    environment.
    """

    def test_backupjob_refuses_a_foreign_encryption_key(self, tenant_a, bkp_key_b):
        job = BackupJob(tenant=tenant_a, name="Cross-tenant key", encryption_key=bkp_key_b)
        with pytest.raises(ValidationError) as exc:
            job.full_clean()
        assert "encryption_key" in exc.value.message_dict

    def test_backupjob_accepts_a_same_tenant_key(self, tenant_a, bkp_key_a):
        job = BackupJob(tenant=tenant_a, name="Own key", encryption_key=bkp_key_a)
        job.full_clean()           # must NOT raise

    def test_legalhold_refuses_a_foreign_retention_policy(self, tenant_a, tenant_b):
        foreign = _policy(tenant_b)
        hold = LegalHold(tenant=tenant_a, name="Cross-tenant policy",
                         issued_at=timezone.now(), retention_policy=foreign)
        with pytest.raises(ValidationError) as exc:
            hold.full_clean()
        assert "retention_policy" in exc.value.message_dict

    def test_dataarchive_refuses_a_foreign_policy(self, tenant_a, tenant_b):
        foreign = _policy(tenant_b)
        archive = DataArchive(tenant=tenant_a, name="Cross-tenant", location="s3://x",
                              policy=foreign)
        with pytest.raises(ValidationError) as exc:
            archive.full_clean()
        assert "policy" in exc.value.message_dict

    def test_environment_refuses_a_foreign_source(self, tenant_a, bkp_env_b):
        env = EnvironmentInstance(tenant=tenant_a, name="Clone of another tenant's prod",
                                  kind="sandbox", source_environment=bkp_env_b)
        with pytest.raises(ValidationError) as exc:
            env.full_clean()
        assert "source_environment" in exc.value.message_dict

    def test_restorerecord_refuses_a_foreign_archive(self, tenant_a, bkp_archive_b):
        record = RestoreRecord(tenant=tenant_a, archive=bkp_archive_b, scope="archive_retrieval",
                               status="planned", target_time=timezone.now())
        with pytest.raises(ValidationError) as exc:
            record.full_clean()
        assert "archive" in exc.value.message_dict

    def test_restorerecord_refuses_a_foreign_target_environment(self, tenant_a, bkp_env_b):
        record = RestoreRecord(tenant=tenant_a, target_environment=bkp_env_b, scope="full_instance",
                               status="planned", target_time=timezone.now())
        with pytest.raises(ValidationError) as exc:
            record.full_clean()
        assert "target_environment" in exc.value.message_dict

    def test_a_tenant_less_row_is_not_checked(self, tenant_a, bkp_key_b):
        """A tenant-less actor (the superuser, by design) has nothing to be consistent with. Asserted
        so the rule cannot start refusing rows it has no basis to judge."""
        job = BackupJob(tenant=None, name="Tenant-less", encryption_key=bkp_key_b)
        job.clean()                # must NOT raise — `tenant_id is None` short-circuits

    def test_the_mixin_is_on_every_0_16_model(self):
        """A model that forgets the mixin silently loses the guard, and nothing else would notice."""
        from apps.core.models.Backup import TenantConsistentMixin
        for model in (BackupJob, DataArchive, RestoreRecord, EnvironmentInstance, RecoveryPosture,
                      RecoveryDrill, LegalHold):
            assert issubclass(model, TenantConsistentMixin), model.__name__


# ============================================================ RecoveryPosture / Drill

class TestRecoveryPostureAndDrill:
    """`RecoveryPosture.tenant` is a `OneToOneField`, so a tenant holds exactly ONE posture.

    The property tests below therefore build UNSAVED instances — they assert a derivation, not a
    stored row, so a database is not needed and the singleton constraint cannot make two fixtures
    collide. The saved fixtures are used only where a page needs the row.
    """

    def test_has_targets_is_true_for_either_target(self):
        assert RecoveryPosture(rpo_target_minutes=60, rto_target_minutes=240).has_targets is True
        assert RecoveryPosture(rpo_target_minutes=60, rto_target_minutes=None).has_targets is True
        assert RecoveryPosture(rpo_target_minutes=None, rto_target_minutes=240).has_targets is True

    def test_has_targets_is_false_when_neither_is_set(self):
        assert RecoveryPosture(rpo_target_minutes=None, rto_target_minutes=None).has_targets is False

    def test_targets_partial_names_the_half_filled_case(self):
        """M6: `has_targets` is an `or`, so a workspace with only an RPO earned the same green "Set"
        badge as one carrying both. `targets_partial` is what lets the page tell them apart — without
        it, "Set" is an unearned reassurance."""
        assert RecoveryPosture(rpo_target_minutes=60, rto_target_minutes=240).targets_partial is False
        assert RecoveryPosture(rpo_target_minutes=60, rto_target_minutes=None).targets_partial is True
        assert RecoveryPosture(rpo_target_minutes=None, rto_target_minutes=240).targets_partial is True
        assert RecoveryPosture(rpo_target_minutes=None, rto_target_minutes=None).targets_partial is False

    def test_the_singleton_is_one_per_tenant(self, tenant_a, bkp_posture_both_a):
        """The constraint that shaped the fixtures — asserted so the reason is on the record."""
        from django.db import IntegrityError, transaction
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                RecoveryPosture.objects.create(tenant=tenant_a, rpo_target_minutes=1)

    def test_a_drill_carries_measured_actuals(self, bkp_drill_a):
        """Measured, not target — the structural reason `RecoveryPosture` is a separate model: a missed
        objective cannot rewrite itself into a met one."""
        assert bkp_drill_a.measured_rpo_minutes == 45
        assert bkp_drill_a.measured_rto_minutes == 180
        assert bkp_drill_a.outcome == "passed"

    def test_a_half_set_posture_is_still_storable(self, bkp_posture_partial_b):
        """M6's premise: the half-filled state is REACHABLE, so the badge has to handle it rather than
        the model preventing it."""
        assert bkp_posture_partial_b.has_targets is True
        assert bkp_posture_partial_b.targets_partial is True
