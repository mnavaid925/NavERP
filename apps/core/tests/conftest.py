"""Core app test fixtures."""
import pytest


@pytest.fixture
def party_a(db, tenant_a):
    from apps.core.models import Party
    return Party.objects.create(tenant=tenant_a, name="Acme Party", kind="organization")


@pytest.fixture
def party_b(db, tenant_b):
    from apps.core.models import Party
    return Party.objects.create(tenant=tenant_b, name="Globex Party", kind="organization")


# ==================================================================== 0.21 Compliance
# APPEND-ONLY (L43): the fixtures above are never rewritten; everything below is added.
#
# **PREFIX RULE (the house convention):** everything here is `cml021_`-prefixed and every test
# function that uses it is `test_compliance_*`. The rule exists for one reason — the next sub-module
# appending nearby must not be able to shadow a name and silently take a fixture with it.
#
# The prefix is `cml021_` and not a bare `cml_` because a short prefix is one a later author is
# likely to reuse a name inside, and the 0.19 precedent in `apps/tenants/tests/conftest.py` is
# already the `lic019_` shape for exactly that reason.


# ------------------------------------------------------------------ the entities
@pytest.fixture
def cml021_framework(db, tenant_a):
    """One registered control framework, NOT adopted — the honest seeded starting state."""
    from apps.core.models import ControlFramework

    return ControlFramework.objects.create(
        tenant=tenant_a, code="SOC2", name="SOC 2 Trust Services Criteria",
        framework_type="attestation", version="2017", authority="AICPA",
        description="Security (CC) category.", is_active=True,
    )


@pytest.fixture
def cml021_framework_b(db, tenant_b):
    """A framework in the OTHER tenant — the IDOR target. It must never be reachable from tenant_a."""
    from apps.core.models import ControlFramework

    return ControlFramework.objects.create(
        tenant=tenant_b, code="SOC2B", name="Globex SOC 2", framework_type="attestation",
    )


@pytest.fixture
def cml021_control(db, tenant_a):
    """An in-progress control. Deliberately NOT `effective`: that status needs a review date, and a
    test that wanted one would have to earn it — the same rule the model enforces."""
    from apps.core.models import ComplianceControl

    return ComplianceControl.objects.create(
        tenant=tenant_a, code="CC6.1", title="Logical access security",
        category="access_control", status="in_progress", frequency="quarterly",
    )


@pytest.fixture
def cml021_control_b(db, tenant_b):
    from apps.core.models import ComplianceControl

    return ComplianceControl.objects.create(
        tenant=tenant_b, code="CC6.1B", title="Globex logical access", status="not_started",
    )


@pytest.fixture
def cml021_mapping(db, tenant_a, cml021_framework, cml021_control):
    from apps.core.models import ControlFrameworkMapping

    return ControlFrameworkMapping.objects.create(
        tenant=tenant_a, framework=cml021_framework, control=cml021_control,
        clause_reference="CC6.1", coverage="partial",
    )


@pytest.fixture
def cml021_policy(db, tenant_a, admin_user):
    """A PUBLISHED policy with an effective date — the only status the acknowledge action accepts."""
    import datetime

    from django.utils import timezone

    from apps.core.models import CorporatePolicy

    return CorporatePolicy.objects.create(
        tenant=tenant_a, code="SEC-001", title="Information Security Policy",
        policy_type="security", version="1.0", status="published", owner=admin_user,
        effective_on=timezone.localdate() - datetime.timedelta(days=30),
        requires_acknowledgement=True, body="The umbrella policy.",
    )


@pytest.fixture
def cml021_policy_draft(db, tenant_a):
    """A DRAFT — the target the acknowledge refusal must reject."""
    from apps.core.models import CorporatePolicy

    return CorporatePolicy.objects.create(
        tenant=tenant_a, code="AUP-002", title="Acceptable Use Policy",
        policy_type="acceptable_use", version="0.1", status="draft",
    )


@pytest.fixture
def cml021_policy_b(db, tenant_b):
    from apps.core.models import CorporatePolicy

    return CorporatePolicy.objects.create(
        tenant=tenant_b, code="SEC-B", title="Globex security policy", status="published",
        effective_on="2026-01-01",
    )


@pytest.fixture
def cml021_risk(db, tenant_a, admin_user):
    """`likely`(4) x `severe`(5) = 20, which lands in the CRITICAL band.

    **C1: `clean()` is called explicitly**, exactly as `seed_core` now does. `objects.create()`
    does NOT run `full_clean()`, and `inherent_score` is written in `clean()` alone — so a fixture
    (or a seeder, which is what C1 actually was) that creates the row without it lands on the
    field default of `0`, and the fixture silently stops being the critical-band risk its own
    docstring claims. A fixture that lies about the value under test is worse than no fixture,
    because the assertion still passes.
    """
    from apps.core.models import RiskRegister

    risk = RiskRegister(
        tenant=tenant_a, code="RSK-01", title="Single region of operation",
        risk_statement="If the primary region is unavailable, then services are unavailable.",
        category="operational", likelihood="likely", impact="severe",
        treatment="mitigate", treatment_plan="Run a second environment.", status="treating",
        owner=admin_user,
    )
    risk.clean()
    risk.save()
    return risk


@pytest.fixture
def cml021_risk_b(db, tenant_b):
    """Tenant B's risk, for the IDOR lane. Scored the same way C1's `cml021_risk` is."""
    from apps.core.models import RiskRegister

    risk = RiskRegister(
        tenant=tenant_b, code="RSK-B", title="Globex risk",
        risk_statement="If X, then Y.", status="identified",
    )
    risk.clean()
    risk.save()
    return risk


@pytest.fixture
def cml021_ack(db, tenant_a, cml021_policy, admin_user):
    """One acknowledgement by the tenant admin, carrying the version SNAPSHOT."""
    from apps.core.models import PolicyAcknowledgement

    return PolicyAcknowledgement.objects.create(
        tenant=tenant_a, policy=cml021_policy, user=admin_user,
        policy_version=cml021_policy.version,
    )

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
    """Valid `LegalHoldForm` POST fields — an ACTIVE hold, i.e. the coherent state.

    **No `issued_at`** — it is deliberately not a form field (a preservation order is issued when it is
    recorded, not when somebody types a date), so posting one is silently ignored and the model default
    supplies "now". Passing it here would imply it works. `tenant` is absent for the usual reason: it is
    never a form field.
    """
    return {
        "name": "New preservation order",
        "custodian": "Legal team",
        "subject_party": "",
        "matter_reference": "ACME-2026-999",
        "issuing_authority": "Superior Court",
        "scope": "All correspondence for the matter.",
        "retention_policy": "",
        "model_label": "",
        "status": "active",
        "released_at": "",
        "release_reason": "",
        "authority_reference": "",
        "notes": "",
        "authority_reference": "",
        "notes": "",
    }


# ------------------------------------------------------------------ 0.17 Monitoring
# APPEND-ONLY (L43): nothing above this point is rewritten; this whole section is added.
#
# Names are prefixed `mon_` rather than `monitoring_` so they cannot collide with the 0.15
# `localization_*` or the 0.16 `bkp_*` blocks above, nor with whatever the next sub-module appends.
# The test contract is `.claude/tasks/test-contract-core-0.17.md`.

@pytest.fixture
def _mon_svc(db, tenant_a):
    """A `ServiceComponent` factory for tenant A. Several tests need a second component."""
    from apps.core.models import ServiceComponent

    def _make(**kwargs):
        n = ServiceComponent.objects.filter(tenant=tenant_a).count()
        defaults = {"tenant": tenant_a, "name": f"Component {n}", "code": f"mon-{n}",
                    "kind": "web_service", "current_status": "operational"}
        defaults.update(kwargs)
        return ServiceComponent.objects.create(**defaults)

    return _make


@pytest.fixture
def mon_service_ok_a(db, tenant_a):
    """An operational component that HAS been given a status by hand."""
    from apps.core.models import ServiceComponent
    from django.utils import timezone
    return ServiceComponent.objects.create(
        tenant=tenant_a, name="Web front end", code="web", kind="web_service",
        current_status="operational", last_status_at=timezone.now())


@pytest.fixture
def mon_service_unreported_a(db, tenant_a):
    """A component nobody has ever set a status on. `last_status_at` is NULL, not epoch."""
    from apps.core.models import ServiceComponent
    return ServiceComponent.objects.create(
        tenant=tenant_a, name="Unreported thing", code="unreported", kind="api",
        current_status="unknown", last_status_at=None)


@pytest.fixture
def mon_service_retired_a(db, tenant_a):
    """A retired component - registered, but excluded from the roll-up."""
    from apps.core.models import ServiceComponent
    return ServiceComponent.objects.create(
        tenant=tenant_a, name="Retired thing", code="retired", kind="database",
        current_status="degraded", is_active=False)


@pytest.fixture
def mon_rule_two_tier_a(db, tenant_a, mon_service_ok_a):
    """A correctly ordered `gte` rule: warning 800 < critical 1500."""
    from decimal import Decimal
    from apps.core.models import AlertRule
    return AlertRule.objects.create(
        tenant=tenant_a, name="Latency budget", service=mon_service_ok_a,
        metric_key="latency_p95_ms", comparator="gte",
        warning_threshold=Decimal("800"), critical_threshold=Decimal("1500"),
        must_persist_seconds=300, frequency="hourly", severity="warning",
        category="performance", no_data_action="ignore")


@pytest.fixture
def mon_rule_floor_a(db, tenant_a, mon_service_ok_a):
    """An `lt` rule - a FLOOR, so the capacity board must subtract the other way round."""
    from decimal import Decimal
    from apps.core.models import AlertRule
    return AlertRule.objects.create(
        tenant=tenant_a, name="Uptime floor", service=mon_service_ok_a,
        metric_key="uptime_pct", comparator="lt",
        warning_threshold=None, critical_threshold=Decimal("99.5"),
        frequency="daily", severity="critical", category="availability",
        no_data_action="fire")


@pytest.fixture
def mon_rule_inactive_a(db, tenant_a, mon_service_ok_a):
    """A parked rule, for the `?active=` filter and the capacity board's inactive row."""
    from decimal import Decimal
    from apps.core.models import AlertRule
    return AlertRule.objects.create(
        tenant=tenant_a, name="Parked rule", service=mon_service_ok_a,
        metric_key="cpu_pct", comparator="gte", warning_threshold=Decimal("90"),
        frequency="weekly", severity="info", category="capacity",
        no_data_action="ignore", is_active=False)


@pytest.fixture
def _mon_event(db):
    """Build an `AlertEvent` for a tenant. `service` is optional so the orphan case is expressible."""
    from apps.core.models import AlertEvent
    from django.utils import timezone

    def _make(tenant, *, rule=None, service=None, state="firing", **kwargs):
        defaults = {
            "tenant": tenant, "rule": rule, "service": service,
            "service_label": service.name if service else "",
            "state": state, "severity_at_fire": "warning",
            "message": "A firing somebody reported",
            "fired_at": timezone.now(), "occurrence_count": 1,
        }
        defaults.update(kwargs)
        return AlertEvent.objects.create(**defaults)

    return _make


@pytest.fixture
def mon_event_firing_a(db, tenant_a, _mon_event, mon_rule_two_tier_a, mon_service_ok_a):
    return _mon_event(tenant_a, rule=mon_rule_two_tier_a, service=mon_service_ok_a)


@pytest.fixture
def mon_event_ack_a(db, tenant_a, _mon_event, mon_rule_two_tier_a, mon_service_ok_a):
    """Acknowledged is part of the OPEN set, so a board counting only `firing` under-counts."""
    return _mon_event(tenant_a, rule=mon_rule_two_tier_a, service=mon_service_ok_a, state="acknowledged")


@pytest.fixture
def mon_event_resolved_a(db, tenant_a, _mon_event, mon_rule_two_tier_a, mon_service_ok_a):
    return _mon_event(tenant_a, rule=mon_rule_two_tier_a, service=mon_service_ok_a, state="resolved")


@pytest.fixture
def mon_event_no_data_a(db, tenant_a, _mon_event, mon_rule_two_tier_a, mon_service_ok_a):
    """The state the badge ladder dropped into the grey 'unrecognised' branch."""
    return _mon_event(tenant_a, rule=mon_rule_two_tier_a, service=mon_service_ok_a, state="no_data")


@pytest.fixture
def mon_event_unmeasured_a(db, tenant_a, _mon_event, mon_rule_two_tier_a, mon_service_ok_a):
    """A firing with no reading attached - the register's own honesty score."""
    return _mon_event(tenant_a, rule=mon_rule_two_tier_a, service=mon_service_ok_a, observed_value=None)


@pytest.fixture
def mon_event_orphan_a(db, tenant_a, _mon_event, mon_service_ok_a):
    """A firing whose rule was retired. `rule_id` is NULL and it must still be listed."""
    return _mon_event(tenant_a, rule=None, service=mon_service_ok_a)


@pytest.fixture
def mon_event_b(db, tenant_b, _mon_event):
    """A tenant-B firing, for the cross-tenant lane."""
    return _mon_event(tenant_b, message="Globex firing")


@pytest.fixture
def mon_incident_open_a(db, tenant_a, mon_service_ok_a):
    from apps.core.models import Incident
    from django.utils import timezone
    inc = Incident.objects.create(
        tenant=tenant_a, service=mon_service_ok_a, title="Checkout down",
        incident_type="incident", status="investigating", impact="major",
        public_note="We are looking into it.", started_at=timezone.now())
    inc.affected_services.add(mon_service_ok_a)
    return inc


@pytest.fixture
def mon_incident_resolved_a(db, tenant_a, mon_service_ok_a):
    from apps.core.models import Incident
    from django.utils import timezone
    return Incident.objects.create(
        tenant=tenant_a, service=mon_service_ok_a, title="Old blip",
        incident_type="incident", status="resolved", impact="minor", started_at=timezone.now())


@pytest.fixture
def mon_incident_maintenance_a(db, tenant_a, mon_service_ok_a):
    from apps.core.models import Incident
    from django.utils import timezone
    return Incident.objects.create(
        tenant=tenant_a, service=mon_service_ok_a, title="Planned window",
        incident_type="scheduled_maintenance", status="scheduled", impact="none",
        scheduled_for=timezone.now() + timezone.timedelta(days=1),
        scheduled_until=timezone.now() + timezone.timedelta(days=1, hours=2))


@pytest.fixture
def mon_incident_b(db, tenant_b):
    from apps.core.models import Incident
    from django.utils import timezone
    return Incident.objects.create(
        tenant=tenant_b, title="Globex outage", incident_type="incident",
        status="investigating", impact="critical", started_at=timezone.now())


@pytest.fixture
def mon_component_payload():
    """Valid `ServiceComponentForm` POST fields.

    **No `last_status_at`** - it is deliberately not a form field (L22), so posting one is silently
    ignored; including it here would imply it works. `tenant` is absent for the usual reason: a form
    must never be able to set it.
    """
    return {
        "name": "Payments API", "code": "payments", "kind": "api",
        "description": "The customer-facing payments endpoint.", "owner_role": "",
        "is_public": "on", "is_critical": "on", "display_order": "1",
        "current_status": "operational", "notes": "", "is_active": "on",
    }


@pytest.fixture
def mon_rule_payload():
    """Valid `AlertRuleForm` POST fields - a ONE-tier rule, which `clean()` accepts.

    `critical_threshold` is blank so this does not depend on the tier-order rule; the tier-order tests
    build their own payloads.
    """
    return {
        "name": "Disk usage ceiling", "module_slug": "core", "metric_key": "disk_usage_pct",
        "comparator": "gte", "warning_threshold": "85", "critical_threshold": "",
        "must_persist_seconds": "600", "frequency": "hourly", "severity": "warning",
        "category": "capacity", "no_data_action": "ignore", "service": "",
        "notification_rule": "", "notes": "", "is_active": "on",
    }


# ================= 0.18 Threat Protection fixtures (appended 2026-09-27) =================
# APPEND-ONLY, per the L43 discipline. Everything above this line belongs to 0.9-0.17 and is
# never rewritten.
#
# `sec_*` prefix, NOT `security_*`: `apps/core/tests/test_security.py` already exists and is a
# PRE-EXISTING generic CSRF/IDOR file from the 0.9 era, unrelated to this sub-module. A
# `security_` prefix would read as belonging to it.
#
# The seeder creates ZERO SecurityThreat / SecurityIncident / IpAccessRule rows (the L52 ruling),
# so every fixture here creates exactly what it needs, explicitly.


@pytest.fixture
def sec_rule_a(db, tenant_a):
    """A tenant-A allow/deny rule. `reason` is required by the model's clean()."""
    from apps.core.models import IpAccessRule
    return IpAccessRule.objects.create(
        tenant=tenant_a, cidr="203.0.113.0/24", direction="deny", action="block",
        scope="workspace", reason="Scanning activity seen from this block",
        source="manual", is_active=True)


@pytest.fixture
def sec_rule_b(db, tenant_b):
    """A tenant-B rule, for the cross-tenant lane."""
    from apps.core.models import IpAccessRule
    return IpAccessRule.objects.create(
        tenant=tenant_b, cidr="198.51.100.7", direction="allow", reason="Corp egress",
        source="manual")


@pytest.fixture
def sec_threat_new_a(db, tenant_a, sec_rule_a):
    """An OPEN tenant-A finding in its initial `new` state, ready for the triage action."""
    from apps.core.models import SecurityThreat
    return SecurityThreat.objects.create(
        tenant=tenant_a, title="Brute force against the admin account",
        threat_type="brute_force", status="new", severity="warning",
        source_ip="203.0.113.7", occurrence_count=1, mitigated_by=sec_rule_a,
        summary="Several hundred failures from one address.")


@pytest.fixture
def sec_threat_b(db, tenant_b):
    """A tenant-B finding, for the cross-tenant lane."""
    from apps.core.models import SecurityThreat
    return SecurityThreat.objects.create(
        tenant=tenant_b, title="Globex-only finding", threat_type="phishing", status="new")


@pytest.fixture
def sec_finding_a(db, tenant_a):
    """An OPEN tenant-A advisory WITH a fix, so `fixed` is a legal transition."""
    from apps.core.models import VulnerabilityFinding
    from django.utils import timezone
    return VulnerabilityFinding.objects.create(
        tenant=tenant_a, title="Example dependency advisory", advisory_id="EXAMPLE-TEST-1",
        finding_source="dependency", package_name="example", installed_version="1.0.0",
        severity="high", cvss_score="7.5", fix_available="yes", fixed_in_version="1.0.1",
        status="open", first_seen_at=timezone.now())


@pytest.fixture
def sec_finding_no_fix_a(db, tenant_a):
    """An advisory with NO fix — the fixture that makes the `fixed` refusal provable."""
    from apps.core.models import VulnerabilityFinding
    from django.utils import timezone
    return VulnerabilityFinding.objects.create(
        tenant=tenant_a, title="No fix published", advisory_id="EXAMPLE-TEST-2",
        finding_source="application", severity="low", fix_available="no", status="open",
        first_seen_at=timezone.now())


@pytest.fixture
def sec_incident_open_a(db, tenant_a):
    """An OPEN tenant-A incident with notifiability UNDECIDED — the state the 72h clock exists
    to pressure, and the one `close` must refuse."""
    from apps.core.models import SecurityIncident
    from django.utils import timezone
    return SecurityIncident.objects.create(
        tenant=tenant_a, title="Possible unauthorised export", incident_class="data_breach",
        status="triaged", severity="critical", is_notifiable=None,
        subject_exemption="none", discovered_at=timezone.now())


@pytest.fixture
def sec_incident_b(db, tenant_b):
    """A tenant-B incident, for the cross-tenant lane."""
    from apps.core.models import SecurityIncident
    from django.utils import timezone
    return SecurityIncident.objects.create(
        tenant=tenant_b, title="Globex-only incident", status="triage", is_notifiable=True,
        subject_exemption="none", discovered_at=timezone.now())


@pytest.fixture
def sec_threat_payload():
    """A minimal VALID create payload for `SecurityThreatForm`."""
    from django.utils import timezone
    return {
        "title": "Suspicious API activity", "threat_type": "suspicious_api_activity",
        "severity": "warning", "status": "new", "occurrence_count": 1,
        "detected_at": timezone.now().strftime("%Y-%m-%dT%H:%M"),
        "mitre_technique": "", "mitre_tactic": "", "rule_reference": "", "waf_action": "",
        "defense_mode": "", "source_ip": "", "summary": "", "detail": "", "evidence": "",
        "notes": "",
    }


@pytest.fixture
def sec_incident_payload():
    """A minimal VALID create payload for `SecurityIncidentForm`."""
    from django.utils import timezone
    return {
        "title": "Credential stuffing wave", "incident_class": "security_incident",
        "status": "detected", "severity": "warning", "is_notifiable": "unknown",
        "subject_exemption": "none", "discovered_at": timezone.now().strftime("%Y-%m-%dT%H:%M"),
        "notifiable_reason": "", "authority_reference": "", "dpo_contact": "",
        "likely_consequences": "", "measures_taken": "", "measures_proposed": "",
        "forensic_log": "", "root_cause": "", "lessons_learned": "", "evidence": "", "notes": "",
    }

# ===================== 0.20 Admin Console & System Operations fixtures (appended) =====================
# APPEND-ONLY, per the L43 discipline. Everything above this line belongs to 0.9-0.18 and 0.21 and
# is never rewritten.
#
# **PREFIX RULE (house convention):** everything here is `ac0_`-prefixed, and every test function
# that uses it is `test_adminconsole_*`. The reason is collision, not taste: sub-module 0.21 is
# appending its own `cml021_` block to THIS SAME FILE right now, and an unprefixed name here would
# either collide outright or, worse, silently take a fixture with it. The prefix is `ac0_` and not
# a bare `admin_` for the same reason 0.18 used `sec_` rather than `security_`: a short prefix is
# one a later author is likely to reuse a name inside.
#
# The contract these fixtures are written against is
# `.claude/tasks/test-contract-core-0.20.md`. Every name below was read out of the code.


# ------------------------------------------------------------------ the actor
@pytest.fixture
def ac0_actor(db, tenant_a):
    """A SECOND tenant admin in tenant_a, deliberately NOT the root conftest's `admin_user`.

    `change_request_approve` stamps `approved_by = request.user` and never reads a form, so "a
    change cannot be approved in somebody else's name" is only a PROVABLE claim when the
    requester and the approver are different rows. Requested by `admin_user`, approved by
    `ac0_actor`: the stamp must name the actor.

    The root `admin_user` is reused as-is for everything that only needs "a tenant admin"; this
    exists solely so the attribution lane has two names to tell apart.
    """
    from apps.accounts.models import User

    return User.objects.create_user(
        email="ops-lead@acme.com",
        username="ops_lead_acme",
        password="TestPass123!",
        tenant=tenant_a,
        is_tenant_admin=True,
    )


@pytest.fixture
def ac0_actor_client(db, ac0_actor):
    """A client logged in as `ac0_actor` - the mirror of the root conftest's `client_a`."""
    from django.test import Client

    c = Client()
    c.force_login(ac0_actor)
    return c


# ------------------------------------------------------------------ the referenced spine rows
@pytest.fixture
def ac0_env(db, tenant_a):
    """One 0.16 `EnvironmentInstance` - the environment `JobDefinition`, `MaintenanceWindow` and
    `ChangeRequest` all point AT rather than re-declaring (L29/L36)."""
    from apps.core.models import EnvironmentInstance

    return EnvironmentInstance.objects.create(
        tenant=tenant_a, name="Staging - ops rehearsal", kind="staging", tier="",
        copy_scope="metadata_only", status="active", is_active=True,
    )


@pytest.fixture
def ac0_flag(db, tenant_a):
    """0.10's per-tenant toggle - the flag a `FeatureRollout` stages. Unique on `(tenant, key)`."""
    from apps.core.models import FeatureFlag

    return FeatureFlag.objects.create(
        tenant=tenant_a, key="ops.reconciliation_job", label="Invoice reconciliation job",
        is_enabled=False,
    )


@pytest.fixture
def ac0_flag_alt(db, tenant_a):
    """A SECOND flag, so two stages can hang off ONE change.

    `FeatureRollout.unique_together` is `(("change", "feature_flag"),)`: a change stages each flag
    once, so two rollouts under one change need two flags. This is the second one, and it is what
    makes `rollout_count == 2` and the duplicate-flag guard observable against a real sibling.
    """
    from apps.core.models import FeatureFlag

    return FeatureFlag.objects.create(
        tenant=tenant_a, key="ops.bulk_backfill", label="Bulk document-number backfill",
        is_enabled=False,
    )


@pytest.fixture
def ac0_service(db, tenant_a):
    """A `ServiceComponent` for a window's `affected_services`.

    Attached to `ac0_window`, deliberately: the window detail prefetches three M2M sets, and a page
    whose sets are all empty cannot tell a working prefetch from a missing one.
    """
    from django.utils import timezone

    from apps.core.models import ServiceComponent

    return ServiceComponent.objects.create(
        tenant=tenant_a, name="Payments API", code="ac0-payments", kind="api",
        current_status="operational", last_status_at=timezone.now(),
    )


# ------------------------------------------------------------------ bullet 2: jobs and runs
@pytest.fixture
def ac0_job(db, tenant_a, ac0_env):
    """A DECLARED job: a cadence, a handler path, a failure policy.

    `last_run_at` is NULL on purpose, because "a job nobody has ever run" is the state the
    `admin_board` never-run tile and the `needs_attention` strip both count. Nothing advances
    either stamp - no scheduler exists.
    """
    from apps.core.models import JobDefinition

    return JobDefinition.objects.create(
        tenant=tenant_a, name="Invoice reconciliation sweep", module_slug="accounting",
        job_type="scheduled_task", schedule_kind="daily", cron_expression="0 2 * * *",
        handler_path="apps.core.tasks.reconcile_invoices", environment=ac0_env,
        description="Re-derive invoice totals from their lines.",
        is_active=True, priority=100, max_active_runs=1, pool_name="default", pool_slots=2,
        max_consecutive_failures=3, auto_pause_after=10, is_muted=False,
        last_run_at=None, next_run_at=None,
    )


@pytest.fixture
def ac0_job_muted(db, tenant_a):
    """A job silenced by hand. `is_muted` is a flag on a schedule, not an interceptor - nothing
    anywhere consults it, and the seeder mutes one row so the field is exercised by data."""
    from apps.core.models import JobDefinition

    return JobDefinition.objects.create(
        tenant=tenant_a, name="Archive retention sweep", module_slug="core", job_type="cleanup",
        schedule_kind="weekly", cron_expression="0 3 * * 0",
        handler_path="apps.core.tasks.sweep_archives", is_muted=True,
    )


@pytest.fixture
def ac0_job_b(db, tenant_b):
    """A job in the OTHER tenant - the cross-tenant IDOR target. Never reachable from tenant_a."""
    from apps.core.models import JobDefinition

    return JobDefinition.objects.create(
        tenant=tenant_b, name="Globex-only job", module_slug="globex", job_type="bulk_operation",
        handler_path="apps.globex.tasks.nightly",
    )


@pytest.fixture
def ac0_run(db, tenant_a, ac0_job, ac0_actor):
    """An OPEN run: `queued`, dry, no start or finish stamp - so `is_open` is True and
    `duration_display` is the em dash. `is_dry_run` is left at the model default rather than
    passed, so a test asserting the default is asserting the MODEL's."""
    from apps.core.models import JobRun

    return JobRun.objects.create(
        tenant=tenant_a, job=ac0_job, trigger_kind="manual", status="queued",
        triggered_by=ac0_actor,
        notes="Recorded by an operator pressing Run now. No scheduler exists, so nothing executed.",
    )


@pytest.fixture
def ac0_run_success(db, tenant_a, ac0_job):
    """A run with BOTH stamps, so `duration_display` has something real to render.

    `JobRun.clean()` refuses a `success` with no `finished_at` and refuses a `finished_at` earlier
    than `started_at`; this row satisfies both, which is the point - it is a run a form could
    legitimately have saved. `is_open` is False: success is terminal.
    """
    from datetime import timedelta

    from django.utils import timezone

    from apps.core.models import JobRun

    started = timezone.now() - timedelta(minutes=5)
    return JobRun.objects.create(
        tenant=tenant_a, job=ac0_job, trigger_kind="scheduled", status="success",
        started_at=started, finished_at=started + timedelta(seconds=90), exit_code=0,
        records_processed=42, duration_ms=90000,
    )


@pytest.fixture
def ac0_run_b(db, tenant_b, ac0_job_b):
    """A run in the OTHER tenant - the cross-tenant IDOR target."""
    from apps.core.models import JobRun

    return JobRun.objects.create(tenant=tenant_b, job=ac0_job_b, status="queued")


# ------------------------------------------------------------------ bullet 3a: maintenance windows
@pytest.fixture
def ac0_window(db, tenant_a, ac0_env, ac0_change_draft, ac0_service):
    """A FUTURE window - `is_future` is True, so this is the ONE state `maintenancewindow_delete`
    will actually delete. A window somebody ran is evidence an incident review may need, so every
    other shape refuses.

    Carries `ac0_change_draft` and one `ac0_service`, so the detail page's linked-change block and
    its prefetched `affected_services` set both have something to read.
    """
    from datetime import timedelta

    from django.utils import timezone

    from apps.core.models import MaintenanceWindow

    now = timezone.now()
    window = MaintenanceWindow.objects.create(
        tenant=tenant_a, title="Ledger schema migration", purpose="Deploy migration 0019.",
        starts_at=now + timedelta(days=2), ends_at=now + timedelta(days=2, hours=3),
        recurrence="once", timezone_label="UTC", status="scheduled", environment=ac0_env,
        change_request=ac0_change_draft, suppresses_jobs=True, blocks_admin_writes=False,
    )
    window.affected_services.set([ac0_service])
    return window


@pytest.fixture
def ac0_window_running(db, tenant_a):
    """A window AS IT RUNS: opened an hour ago, closes in an hour. `is_current` is True and
    `is_future` is False, so it is NOT deletable - and it is the legal `end_now` target."""
    from datetime import timedelta

    from django.utils import timezone

    from apps.core.models import MaintenanceWindow

    now = timezone.now()
    return MaintenanceWindow.objects.create(
        tenant=tenant_a, title="Rolling node restart", purpose="Restart the batch node.",
        starts_at=now - timedelta(hours=1), ends_at=now + timedelta(hours=1), status="active",
        recurrence="once",
    )


@pytest.fixture
def ac0_window_past(db, tenant_a):
    """A window that ran its course - history. Neither future nor current, so the delete guard
    refuses it, and `end_now` refuses it too because it is already `completed`."""
    from datetime import timedelta

    from django.utils import timezone

    from apps.core.models import MaintenanceWindow

    now = timezone.now()
    return MaintenanceWindow.objects.create(
        tenant=tenant_a, title="Certificate rotation", purpose="Rotate the TLS certificate.",
        # `timedelta(days=3, hours=1)` is 3 days MINUS 1 hour, not plus - the keyword args share one
        # sign - so it would put `ends_at` an hour BEFORE `starts_at` and `clean()` would (rightly)
        # refuse the row. Build it from `now` and offset positively.
        starts_at=now - timedelta(days=3, hours=2),
        ends_at=now - timedelta(days=3),
        status="completed", recurrence="once",
    )


@pytest.fixture
def ac0_window_b(db, tenant_b):
    """A window in the OTHER tenant - the cross-tenant IDOR target. Future, so it is deletable in
    its own tenant; the point is that tenant_a cannot reach it at all."""
    from datetime import timedelta

    from django.utils import timezone

    from apps.core.models import MaintenanceWindow

    now = timezone.now()
    return MaintenanceWindow.objects.create(
        tenant=tenant_b, title="Globex-only window", purpose="Globex maintenance.",
        starts_at=now + timedelta(days=1), ends_at=now + timedelta(days=1, hours=2),
        status="scheduled",
    )


# ------------------------------------------------------------------ bullet 3b: changes and rollouts
@pytest.fixture
def ac0_change_draft(db, tenant_a, ac0_env):
    """A DRAFT change - the only status `ChangeRequestForm` offers, and the state
    `change_request_submit` acts from. No actor, no stamp, nothing to be inconsistent with."""
    from apps.core.models import ChangeRequest

    return ChangeRequest.objects.create(
        tenant=tenant_a, title="Enable multi-currency on invoices",
        summary="Turn on the second currency on the invoice form.",
        change_type="standard", risk_level="low", impact_level="minor", status="draft",
        environment=ac0_env, downtime_required=False,
    )


@pytest.fixture
def ac0_change(db, tenant_a, ac0_env, admin_user):
    """A `submitted` change - the state the Approve action is offered from, and EDITABLE.

    **Why `submitted` and not `approved`.** `ChangeRequest.clean()` refuses an `approved` row with
    no `approved_by` and no `approved_at`, and `crud_edit` runs `full_clean()` on EVERY save - so an
    approved row with no approver can never be saved again through the form, and every POST fails.
    A fixture in that state could not exercise the edit page at all, which is exactly why the
    seeder moved its demo row back to `submitted` in the same fix. `submitted` places no rule in
    `clean()` and needs no actor, so this row saves cleanly.

    `requested_at` and `requestor` are set because the submit verb is the only writer of both and
    they are off the form - a test that wants to prove the form never touches them needs a row
    that already carries them.
    """
    from datetime import timedelta

    from django.utils import timezone

    from apps.core.models import ChangeRequest

    return ChangeRequest.objects.create(
        tenant=tenant_a, title="Retire the legacy export endpoint",
        summary="Turn off the v1 export and move callers to v2.",
        change_type="normal", risk_level="medium", impact_level="moderate", status="submitted",
        environment=ac0_env, requestor=admin_user,
        requested_at=timezone.now() - timedelta(days=5), downtime_required=False,
    )


@pytest.fixture
def ac0_change_approved(db, tenant_a, ac0_env, ac0_actor):
    """An `approved` change that DOES carry its evidence - the counter-example that proves the
    refusal is about the missing stamp and not about the status.

    `approved_by` and `approved_at` are both set, so `full_clean()` passes and this row IS
    editable through the form. Pair it with `ac0_change` to show the two differ only by their
    evidence. An approved change with NO approver is deliberately not a fixture: it is unsaveable
    by construction, so a test that wants it must build the row in-line.
    """
    from datetime import timedelta

    from django.utils import timezone

    from apps.core.models import ChangeRequest

    return ChangeRequest.objects.create(
        tenant=tenant_a, title="Add the reconciliation job to the scheduler register",
        summary="Declare the job; nothing executes it.",
        change_type="standard", risk_level="low", impact_level="minor", status="approved",
        environment=ac0_env, approved_by=ac0_actor,
        approved_at=timezone.now() - timedelta(days=2), downtime_required=False,
    )


@pytest.fixture
def ac0_change_completed(db, tenant_a, ac0_env, ac0_actor):
    """A COMPLETED change - the only state `change_request_rollback` accepts.

    Carries an approver and an implementation stamp, so `clean()` passes and the row stays
    editable; the rollback verb then has a legal starting point to move away from.
    """
    from datetime import timedelta

    from django.utils import timezone

    from apps.core.models import ChangeRequest

    return ChangeRequest.objects.create(
        tenant=tenant_a, title="Move the nightly backup to the new host",
        summary="Repoint the backup job at the replacement host.",
        change_type="normal", risk_level="medium", impact_level="major", status="completed",
        environment=ac0_env, approved_by=ac0_actor,
        approved_at=timezone.now() - timedelta(days=10),
        implemented_at=timezone.now() - timedelta(days=8), downtime_required=True,
    )


@pytest.fixture
def ac0_change_b(db, tenant_b):
    """A change in the OTHER tenant - the cross-tenant IDOR target."""
    from apps.core.models import ChangeRequest

    return ChangeRequest.objects.create(
        tenant=tenant_b, title="Globex-only change", change_type="emergency", risk_level="high",
        impact_level="major", status="draft",
    )


@pytest.fixture
def ac0_rollout(db, tenant_a, ac0_change, ac0_flag):
    """One declared stage: `partial` at 25% on `ac0_flag` under `ac0_change`.

    The `(change, feature_flag)` pair is UNIQUE - that is the whole point of this fixture. The
    pair is enforced by the database only, so a duplicate is an `IntegrityError` and a 500, and
    `FeatureRolloutForm.clean_feature_flag` is the one hand-written rule that turns it into a field
    error instead. `ac0_rollout_alt` is the sibling the guard has to refuse.
    """
    from apps.core.models import FeatureRollout

    return FeatureRollout.objects.create(
        tenant=tenant_a, change=ac0_change, feature_flag=ac0_flag, stage="partial",
        percentage=25, cohort_label="Finance team", status="planned",
    )


@pytest.fixture
def ac0_rollout_alt(db, tenant_a, ac0_change, ac0_flag_alt):
    """A SECOND stage under the SAME change - on a DIFFERENT flag, which is the only legal way to do
    it. Two rollouts on one change is the ladder the model is shaped for, and it is what makes
    `rollout_count == 2` observable on a prefetched page.

    `general` at exactly 100% is the other exact bookend; a test wanting a contradiction builds it
    in-line rather than as a fixture.
    """
    from apps.core.models import FeatureRollout

    return FeatureRollout.objects.create(
        tenant=tenant_a, change=ac0_change, feature_flag=ac0_flag_alt, stage="general",
        percentage=100, cohort_label="Everyone", status="planned",
    )


@pytest.fixture
def ac0_rollout_b(db, tenant_b, ac0_change_b, ac0_flag):
    """A rollout in the OTHER tenant - the cross-tenant IDOR target. It reuses `ac0_flag` on
    purpose: the pair is unique per CHANGE, and this change is a different row, so the fixture is
    legal and still exercises the tenant boundary."""
    from apps.core.models import FeatureRollout

    return FeatureRollout.objects.create(
        tenant=tenant_b, change=ac0_change_b, feature_flag=ac0_flag, stage="pilot",
        percentage=5, status="planned",
    )


# ------------------------------------------------------------------ minimal valid form payloads
# Datetimes are in the `%Y-%m-%dT%H:%M` format `TenantModelForm` declares in `input_formats` - the
# same shape its `datetime-local` widget posts. M2M fields are LISTS of pks; a checkbox is "on"
# when set and ABSENT when not. Every payload carries the WHOLE form, because a partial dict
# silently exercises the "field absent" path rather than the "field supplied" one.


def _ac0_stamp(days=0, hours=0):
    """A `%Y-%m-%dT%H:%M` string offset from now - the format the form widgets post."""
    from datetime import timedelta

    from django.utils import timezone

    return (timezone.now() + timedelta(days=days, hours=hours)).strftime("%Y-%m-%dT%H:%M")


@pytest.fixture
def ac0_job_payload(ac0_env):
    """A minimal VALID create payload for `JobDefinitionForm`.

    `handler_path` is supplied because it is REQUIRED on the model and deliberately still on the
    form - recording the declared target is the point of the register. `last_run_at` and
    `next_run_at` are absent on purpose: they are off the form, and a payload that tried to set
    them would be testing a field that does not exist. `is_muted` is absent so it posts False.
    """
    return {
        "name": "Nightly stock count sync", "module_slug": "scm", "job_type": "integration_sync",
        "description": "Declared against an integration sync.", "schedule_kind": "hourly",
        "cron_expression": "", "interval_minutes": 60,
        "handler_path": "apps.core.tasks.sync_stock_counts", "sync_schedule": "",
        "environment": str(ac0_env.pk), "is_active": "on", "priority": 100,
        "timeout_seconds": 900, "max_active_runs": 1, "pool_name": "default", "pool_slots": 2,
        "max_consecutive_failures": 3, "auto_pause_after": 10, "notes": "",
    }


@pytest.fixture
def ac0_run_payload(ac0_job):
    """A minimal VALID `JobRunForm` payload that RECORDS AN OUTCOME.

    `status="success"` needs `finished_at` (`JobRun.clean()` refuses it otherwise) and
    `started_at` must not be later. `triggered_at`, `triggered_by` and `is_dry_run` are absent:
    all three are off the form, and a dry run edited into asserting a real one is precisely what
    dropping `is_dry_run` prevents.
    """
    return {
        "job": str(ac0_job.pk), "trigger_kind": "manual", "status": "success",
        "started_at": _ac0_stamp(hours=-1), "finished_at": _ac0_stamp(),
        "exit_code": 0, "records_processed": 12, "duration_ms": 90000, "error_message": "",
        "notes": "",
    }


@pytest.fixture
def ac0_window_payload(ac0_env, ac0_service, ac0_change_draft):
    """A minimal VALID `MaintenanceWindowForm` payload - both ends present, because the model
    refuses a one-ended window.

    `ended_at` is absent (off the form, verb-written only) and `status` is `scheduled`, one of the
    five values the widget actually offers. `suppresses_jobs` is posted "on" and
    `blocks_admin_writes` is absent, so the two recorded-scope booleans are exercised in both
    states - stating the intent is the operator's job; nothing enforces either.
    """
    return {
        "title": "Read replica failover rehearsal", "purpose": "Prove the replica fails over.",
        "starts_at": _ac0_stamp(days=1), "ends_at": _ac0_stamp(days=1, hours=2),
        "recurrence": "once", "timezone_label": "UTC", "status": "scheduled",
        "affected_services": [str(ac0_service.pk)], "suppressed_alert_rules": [],
        "suppressed_notification_rules": [], "incident": "", "environment": str(ac0_env.pk),
        "change_request": str(ac0_change_draft.pk), "suppresses_jobs": "on",
        "blocks_admin_writes": "", "notes": "",
    }


@pytest.fixture
def ac0_change_payload(ac0_env):
    """A minimal VALID `ChangeRequestForm` payload.

    `status` is `draft` - the ONLY value the widget offers, and the only one a person may author.
    Every actor field and every evidence stamp is absent, which is the L22 property under test:
    `requestor`, `approved_by`, `requested_at`, `approved_at`, `implemented_at`, `rollback_at`,
    `rollback_reason` and `post_review` are all written by a verb or after the fact, never typed.
    """
    return {
        "title": "Raise the invoice approval threshold",
        "summary": "Only above 10k needs a sign-off.",
        "change_type": "standard", "risk_level": "medium", "impact_level": "minor",
        "status": "draft", "environment": str(ac0_env.pk), "downtime_required": "", "notes": "",
    }


@pytest.fixture
def ac0_rollout_payload(ac0_change, ac0_flag):
    """A minimal VALID `FeatureRolloutForm` payload.

    `stage="partial"` with `percentage=25` satisfies the ladder guard (a partial stage must be
    between 1% and 99%), and `status="planned"` is one of the four the widget offers - `completed`
    is dropped because it needs `completed_at`, which is off the form. `scheduled_at` is supplied
    because it IS authorable; `started_at` and `completed_at` are not.
    """
    return {
        "change": str(ac0_change.pk), "feature_flag": str(ac0_flag.pk), "stage": "partial",
        "percentage": 25, "cohort_label": "Finance team", "scheduled_at": _ac0_stamp(days=1),
        "status": "planned", "notes": "",
    }
