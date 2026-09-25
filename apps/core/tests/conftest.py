"""Core app test fixtures."""
import pytest
from django.test import Client


@pytest.fixture
def party_a(db, tenant_a):
    from apps.core.models import Party
    return Party.objects.create(tenant=tenant_a, name="Acme Party", kind="organization")


@pytest.fixture
def party_b(db, tenant_b):
    from apps.core.models import Party
    return Party.objects.create(tenant=tenant_b, name="Globex Party", kind="organization")


# ------------------------------------------------------------------ 0.15 Localization
# APPEND-ONLY (L43): the two fixtures above are never rewritten; everything below is added.

@pytest.fixture
def localization_languages(db):
    """3 GLOBAL languages — two of them RTL.

    Global, so there is no `tenant` argument and no tenant scoping. Count assertions on this table must be
    scoped by `code`/`name` rather than by `.count()`, because the table is shared with anything else that
    creates a language.
    """
    from apps.core.models import Language
    return [
        Language.objects.create(code="en", name="English", native_name="English", is_default=True),
        Language.objects.create(code="ar", name="Arabic", native_name="العربية", is_rtl=True),
        Language.objects.create(code="he", name="Hebrew", native_name="עברית", is_rtl=True),
    ]


@pytest.fixture
def localization_zones(db):
    """3 GLOBAL zones covering both DST postures and a non-hour offset."""
    from apps.core.models import TimeZone
    return [
        TimeZone.objects.create(name="UTC", label="UTC", utc_offset_minutes=0),
        TimeZone.objects.create(name="Asia/Kolkata", label="Kolkata (IST)",
                                utc_offset_minutes=330),
        TimeZone.objects.create(name="Europe/London", label="London (GMT/BST)",
                                utc_offset_minutes=0, observes_dst=True),
    ]


@pytest.fixture
def localization_profile(db, tenant_a, localization_languages, localization_zones):
    """The tenant_a singleton profile."""
    from apps.core.models import LocaleProfile
    return LocaleProfile.objects.create(
        tenant=tenant_a,
        language=localization_languages[0],
        time_zone=localization_zones[0],
        first_day_of_week=1,
    )


@pytest.fixture
def localization_rules(db, tenant_a, tenant_b):
    """2 rules for tenant_a, 1 for tenant_b — the isolation test needs a real foreign row."""
    import datetime

    from apps.core.models import StatutoryRule
    today = datetime.date(2026, 1, 1)
    return {
        "a": [
            StatutoryRule.objects.create(
                tenant=tenant_a, name="EU VAT e-invoicing", jurisdiction="European Union",
                e_invoicing_required=True, e_invoicing_scheme="peppol",
                statutory_report="EC Sales List", effective_from=today),
            StatutoryRule.objects.create(
                tenant=tenant_a, name="US sales tax filing", jurisdiction="United States",
                effective_from=today),
        ],
        "b": StatutoryRule.objects.create(
            tenant=tenant_b, name="Globex Filing", jurisdiction="Globex Land",
            effective_from=today),
    }


@pytest.fixture
def localization_statutory_payload():
    """Valid POST fields for a StatutoryRule — a helper, not a DB fixture."""
    return {
        "name": "New Compliance Rule",
        "jurisdiction": "Test Jurisdiction",
        "tax_code": "",
        "e_invoicing_scheme": "none",
        "statutory_report": "",
        "effective_from": "2026-01-01",
        "effective_to": "",
        "is_active": "on",
        "notes": "",
    }


# ==================================================================== 0.16 Backup & Recovery
# APPEND-ONLY (L43): nothing above is rewritten; this whole section is added.
#
# Contract: `.claude/tasks/test-contract-core-0.16.md` — the fixtures below are pinned there before
# these tests exist. Several states exist BECAUSE of a Phase-5 Critical and the fix id is named in the
# docstring, so a future reader can trace the fixture to the finding that produced it instead of
# assuming it is arbitrary.

def _bkp_job(tenant, **overrides):
    """A `BackupJob`. Defaults to `success` with NO integrity check — the untested claim.

    `integrity_verified_at=None` is the default deliberately: the verified state is the reassuring one
    and a helper that defaulted to it would make every test assert the happy path. Ask for
    `integrity_verified_at=timezone.now()` when the test is about the green tick.
    """
    from django.utils import timezone

    from apps.core.models import BackupJob

    now = timezone.now()
    fields = dict(name="Nightly full backup", scope_label="nav_erp schema", backup_type="full",
                  frequency="daily", retention_days=30, target_location="s3://acme-backups/nav_erp",
                  storage_tier="standard", encryption_scheme="aes256", status="success",
                  failure_reason="n_a", started_at=now - timezone.timedelta(hours=8),
                  finished_at=now - timezone.timedelta(hours=8) + timezone.timedelta(minutes=24),
                  integrity_verified_at=None, evidence="OPS-1041")
    fields.update(overrides)
    obj = BackupJob(tenant=tenant, **fields)
    obj.full_clean()
    obj.save()
    return obj


def _bkp_archive(tenant, _validate=True, **overrides):
    """A `DataArchive`. `location` is required (no `blank=True`), so it is always passed explicitly.

    `_validate=False` is for the deliberately-invalid states — an archive with `location=""` is a
    STORABLE row that the FORM refuses (`blank=False`), which is exactly why the board counts it and
    why the seeder plants one. `full_clean()` would refuse to build the state the tests must assert on,
    so those fixtures opt out and the form lane covers the refusal separately.
    """
    from apps.core.models import DataArchive

    fields = dict(name="2024 activity archive", location="glacier://acme-archive/2024/activity.parquet",
                  storage_tier="glacier", format="parquet", status="active",
                  content_description="Archived activity rows.")
    fields.update(overrides)
    obj = DataArchive(tenant=tenant, **fields)
    if _validate:
        obj.full_clean()
    obj.save()
    return obj


def _bkp_hold(tenant, **overrides):
    """A `LegalHold`. Defaults to a properly active hold — the state that SUSPENDS a schedule (C2)."""
    from django.utils import timezone

    from apps.core.models.LegalHold import LegalHold

    fields = dict(name="Hold — Acme v. Initech", custodian="Finance team",
                  matter_reference="ACME-2026-114", issuing_authority="Superior Court",
                  scope="All finance correspondence.", model_label="", retention_policy=None,
                  issued_at=timezone.now() - timezone.timedelta(days=30), status="active",
                  released_at=None, release_reason="", authority_reference="",
                  notes="Preservation order received.")
    fields.update(overrides)
    obj = LegalHold(tenant=tenant, **fields)
    obj.full_clean()
    obj.save()
    return obj


def _bkp_env(tenant, _validate=True, **overrides):
    """An `EnvironmentInstance`.

    `_validate=False` is for the PAST-EXPIRY state: the model refuses `expires_at` earlier than
    `created_at`, and `created_at` is `auto_now_add`, so an environment that is already past its
    reaping date cannot be built through `full_clean()` at all. That state is reachable in production
    (an un-reaped sandbox) and the board counts it, so the fixture builds it directly.
    """
    from django.utils import timezone

    from apps.core.models import EnvironmentInstance

    fields = dict(name="Sandbox — UAT", kind="sandbox", copy_scope="none", status="active",
                  copy_includes_pii=False, masking_required=False, is_active=True,
                  expires_at=timezone.now() + timezone.timedelta(days=30))
    fields.update(overrides)
    obj = EnvironmentInstance(tenant=tenant, **fields)
    if _validate:
        obj.full_clean()
    obj.save()
    return obj


def _bkp_drill(tenant, **overrides):
    """A `RecoveryDrill` carrying MEASURED actuals — the point of the posture's targets."""
    from django.utils import timezone

    from apps.core.models import RecoveryDrill

    fields = dict(name="Q3 isolated failover", kind="test_failover", outcome="passed",
                  performed_at=timezone.now() - timezone.timedelta(days=7),
                  measured_rpo_minutes=45, measured_rto_minutes=180,
                  participants="Ops team", findings="Failover completed within target.",
                  follow_up_actions="", evidence="DR-2026-Q3")
    fields.update(overrides)
    obj = RecoveryDrill(tenant=tenant, **fields)
    obj.full_clean()
    obj.save()
    return obj


def _bkp_restore(tenant, **overrides):
    """A `RestoreRecord`.

    NOTE: `RestoreRecord` has **no `name` field** and only `tenant` is required — passing `name=`
    raises `TypeError`. Its `is_verified` is a stored FIELD (a claim), unlike `BackupJob.is_verified`
    which is a property.
    """
    from django.utils import timezone

    from apps.core.models import RestoreRecord

    fields = dict(scope="full_instance", status="succeeded", target_time=timezone.now() - timezone.timedelta(days=1),
                  reason="Quarterly drill.", is_verified=True, evidence="DR-2026-Q3")
    fields.update(overrides)
    obj = RestoreRecord(tenant=tenant, **fields)
    obj.full_clean()
    obj.save()
    return obj


def _bkp_key(tenant, **overrides):
    """A `tenants.EncryptionKey`. All four of tenant/name/prefix/key_hash are required.

    Stores a prefix and a hash only — never plaintext. C7's leak was measured on this field's
    queryset, because `EncryptionKey.__str__` renders the prefix.
    """
    from apps.tenants.models import EncryptionKey

    fields = dict(name="Primary", prefix="acmekey", key_hash="sha256:" + "0" * 64, status="active")
    fields.update(overrides)
    obj = EncryptionKey(tenant=tenant, **fields)
    obj.full_clean()
    obj.save()
    return obj


# ---- Tenant A subjects -------------------------------------------------------------

@pytest.fixture
def bkp_verified_job_a(db, tenant_a):
    """The ONLY state that earns a green ✓ — success AND an integrity check."""
    from django.utils import timezone
    return _bkp_job(tenant_a, name="Nightly full backup",
                    integrity_verified_at=timezone.now() - timezone.timedelta(hours=7),
                    integrity_method="restore_test")


@pytest.fixture
def bkp_unverified_job_a(db, tenant_a):
    """Success with NO check — the untested claim the board exists to name."""
    return _bkp_job(tenant_a, name="Nightly full backup (unchecked)")


@pytest.fixture
def bkp_partial_job_a(db, tenant_a):
    """`warning`/partial. More dangerous than a failed backup, because people trust it."""
    return _bkp_job(tenant_a, name="Hourly transaction log", backup_type="log", frequency="hourly",
                    status="warning", failure_reason="partial_scope_skipped",
                    notes="Two tables were locked and skipped.")


@pytest.fixture
def bkp_failed_job_a(db, tenant_a):
    """`failed` with `integrity_check_failed`. I6: verify must REFUSE this."""
    return _bkp_job(tenant_a, name="Weekly offsite copy", backup_type="full", frequency="weekly",
                    status="failed", failure_reason="integrity_check_failed")


@pytest.fixture
def bkp_queued_job_a(db, tenant_a):
    """C5: the IN-FLIGHT row. `started_at=None`, which is what MariaDB sorted to the bottom."""
    return _bkp_job(tenant_a, name="Queued nightly full backup", status="queued",
                    started_at=None, finished_at=None, integrity_verified_at=None, evidence="")


@pytest.fixture
def bkp_cancelled_job_a(db, tenant_a):
    """C5's boundary: `cancelled` has no `started_at` but is SETTLED, so it is NOT in flight and its
    absent integrity check IS a finding. A naive `not is_verified` would sweep it in."""
    return _bkp_job(tenant_a, name="Cancelled nightly backup", status="cancelled",
                    failure_reason="cancelled_by_operator", started_at=None, finished_at=None)


@pytest.fixture
def bkp_running_job_a(db, tenant_a):
    """The other in-flight status."""
    from django.utils import timezone
    return _bkp_job(tenant_a, name="Running full backup", status="running",
                    started_at=timezone.now() - timezone.timedelta(minutes=10), finished_at=None)


@pytest.fixture
def bkp_archive_ok_a(db, tenant_a):
    """A restorable archive — the control for I1."""
    return _bkp_archive(tenant_a, name="2024 activity archive")


@pytest.fixture
def bkp_archive_lost_a(db, tenant_a):
    """I1: locationless AND lost — the bait the seeder also plants. `is_restorable` is False, so a
    `succeeded` restore naming it must be refused.

    `_validate=False`: an empty `location` is refused by the FORM (`blank=False`) but is a perfectly
    storable row, and it is the row the board exists to surface. Building it through `full_clean()`
    would be impossible, which is why the seeder uses `objects.create()` too.
    """
    return _bkp_archive(tenant_a, _validate=False, name="Legacy CRM export (media lost)",
                        location="", status="lost")


@pytest.fixture
def bkp_hold_active_a(db, tenant_a):
    """C2: an active hold. A board that reports "due for disposal" over this scope is committing the
    spoliation the model exists to prevent."""
    return _bkp_hold(tenant_a, name="Hold — Acme v. Initech", status="active", released_at=None)


@pytest.fixture
def bkp_hold_released_a(db, tenant_a):
    """C3: the LEGITIMATELY closed state — status and release event agree."""
    from django.utils import timezone
    issued = timezone.now() - timezone.timedelta(days=40)
    return _bkp_hold(tenant_a, name="Released hold", status="released", issued_at=issued,
                     released_at=issued + timezone.timedelta(hours=1),
                     release_reason="Matter settled.")


@pytest.fixture
def bkp_hold_expired_a(db, tenant_a):
    """C3's third branch: expired/superseded suspend NOTHING, and the page must say so rather than
    claim the schedule resumed."""
    return _bkp_hold(tenant_a, name="Superseded hold", status="superseded", released_at=None)


@pytest.fixture
def bkp_env_a(db, tenant_a):
    """A sandbox PAST its reaping date.

    `_validate=False` because the model refuses `expires_at < created_at` and `created_at` is
    `auto_now_add` — so this state cannot be built through `full_clean()` at all, yet it is exactly
    the un-reaped sandbox the board's `expired_environments` list exists to name.
    """
    from django.utils import timezone
    return _bkp_env(tenant_a, _validate=False, name="Sandbox — UAT",
                    expires_at=timezone.now() - timezone.timedelta(days=1))


@pytest.fixture
def bkp_env_production_a(db, tenant_a):
    """The environment a cycle test points back at."""
    from django.utils import timezone
    return _bkp_env(tenant_a, name="Production", kind="production", copy_scope="none",
                    expires_at=timezone.now() + timezone.timedelta(days=365))


@pytest.fixture
def bkp_env_sandbox_a(db, tenant_a):
    """A VALID sandbox — future expiry, so `full_clean()` works.

    The cycle tests need this rather than `bkp_env_a`: the past-expiry fixture can only be built with
    `_validate=False`, so calling `full_clean()` on it later fails on `expires_at` and the test would
    report a cycle failure that is really a fixture artefact. A test that asserts a rule must be able to
    run the rule.
    """
    from django.utils import timezone
    return _bkp_env(tenant_a, name="Sandbox — cycle source", kind="sandbox", copy_scope="none",
                    expires_at=timezone.now() + timezone.timedelta(days=60))


@pytest.fixture
def bkp_env_cycle_a(db, tenant_a):
    """I8: a reachable A→B→A cycle.

    Created with `objects.create()` rather than `full_clean()` **on purpose** — the cycle is the STATE
    under test, and the model rule that refuses it must be exercised separately by a test that calls
    `full_clean()`. A fixture that could not create the state could not test what a page does when it
    already exists.
    """
    from apps.core.models import EnvironmentInstance
    first = EnvironmentInstance.objects.create(tenant=tenant_a, name="Cycle A", kind="sandbox",
                                               copy_scope="none", status="active", is_active=True)
    second = EnvironmentInstance.objects.create(tenant=tenant_a, name="Cycle B", kind="sandbox",
                                                copy_scope="none", status="active", is_active=True,
                                                source_environment=first)
    EnvironmentInstance.objects.filter(pk=first.pk).update(source_environment=second)
    first.refresh_from_db()
    return {"a": first, "b": second}


@pytest.fixture
def bkp_posture_both_a(db, tenant_a):
    """Both targets set — the state that EARNS the green "Set"."""
    from apps.core.models import RecoveryPosture
    return RecoveryPosture.objects.create(tenant=tenant_a, rpo_target_minutes=60,
                                          rto_target_minutes=240, backup_retention_days=30)


@pytest.fixture
def bkp_posture_partial_b(db, tenant_b):
    """M6: only the RPO. A green "Set" here would be an unearned reassurance.

    **On tenant_b, not tenant_a** — `RecoveryPosture.tenant` is a `OneToOneField`, so a tenant can
    hold exactly one posture and `bkp_posture_both_a` already occupies tenant_a's slot. A fixture pair
    that both claimed tenant_a would raise `UNIQUE constraint failed` and the test would fail for a
    reason that has nothing to do with what it asserts.
    """
    from apps.core.models import RecoveryPosture
    return RecoveryPosture.objects.create(tenant=tenant_b, rpo_target_minutes=60,
                                          rto_target_minutes=None)


@pytest.fixture
def bkp_drill_a(db, tenant_a, bkp_posture_both_a):
    """A drill whose measured actuals are judged against the posture's targets."""
    return _bkp_drill(tenant_a)


@pytest.fixture
def bkp_key_a(db, tenant_a):
    """C7: the field whose queryset leaked. `prefix` is what a leaked dropdown renders."""
    return _bkp_key(tenant_a, name="Acme primary", prefix="acmekey")


# ---- Tenant B: the 404 / isolation subjects ----------------------------------------

@pytest.fixture
def bkp_job_b(db, tenant_b):
    """Tenant B's verified backup — the row A must never see or name."""
    from django.utils import timezone
    return _bkp_job(tenant_b, name="ZZB globex nightly",
                    integrity_verified_at=timezone.now() - timezone.timedelta(hours=6))


@pytest.fixture
def bkp_archive_b(db, tenant_b):
    return _bkp_archive(tenant_b, name="ZZB globex archive")


@pytest.fixture
def bkp_hold_b(db, tenant_b):
    return _bkp_hold(tenant_b, name="ZZB globex hold", status="active", released_at=None)


@pytest.fixture
def bkp_env_b(db, tenant_b):
    return _bkp_env(tenant_b, name="ZZB globex production", kind="production")


@pytest.fixture
def bkp_drill_b(db, tenant_b):
    return _bkp_drill(tenant_b, name="ZZB globex drill")


@pytest.fixture
def bkp_key_b(db, tenant_b):
    """The prefix that must NEVER appear in tenant A's `encryption_key` dropdown (C7)."""
    return _bkp_key(tenant_b, name="Globex primary", prefix="zglobexkey")


# ---- Payload helpers (not DB fixtures) ---------------------------------------------

@pytest.fixture
def bkp_job_payload():
    """Valid `BackupJobForm` POST fields. `tenant` is absent on purpose — it is never a form field."""
    from django.utils import timezone
    now = timezone.now()
    return {
        "name": "New nightly backup",
        "scope_label": "nav_erp schema",
        "backup_type": "full",
        "frequency": "daily",
        "retention_days": "30",
        "target_location": "s3://acme-backups/nav_erp",
        "storage_tier": "standard",
        "encryption_key": "",
        "encryption_scheme": "aes256",
        "size_bytes": "1845000000",
        "checksum": "sha256:abc",
        "integrity_method": "checksum",
        "integrity_verified_at": "",
        "status": "success",
        "failure_reason": "n_a",
        "attempt_count": "1",
        "is_immutable": "on",
        "retain_until": "",
        "started_at": now.strftime("%Y-%m-%dT%H:%M"),
        "finished_at": (now + timezone.timedelta(minutes=20)).strftime("%Y-%m-%dT%H:%M"),
        "performed_by": "",
        "evidence": "OPS-9999",
        "notes": "",
    }


@pytest.fixture
def bkp_restore_payload():
    """Valid `RestoreRecordForm` POST fields."""
    from django.utils import timezone
    return {
        "backup": "",
        "archive": "",
        "scope": "full_instance",
        "target_time": (timezone.now() - timezone.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
        "target_environment": "",
        "status": "succeeded",
        "requested_by": "",
        "reason": "Quarterly drill.",
        "started_at": "",
        "finished_at": "",
        "outcome": "",
        "is_verified": "on",
        "evidence": "DR-9999",
    }


@pytest.fixture
def bkp_hold_payload():
    """Valid `LegalHoldForm` POST fields — an ACTIVE hold, i.e. the coherent state."""
    from django.utils import timezone
    return {
        "name": "New preservation order",
        "custodian": "Legal team",
        "subject_party": "",
        "matter_reference": "ACME-2026-999",
        "issuing_authority": "Superior Court",
        "scope": "All correspondence for the matter.",
        "retention_policy": "",
        "model_label": "",
        "issued_at": (timezone.now() - timezone.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
        "status": "active",
        "released_at": "",
        "release_reason": "",
        "authority_reference": "",
        "notes": "",
    }
