"""core — 0.16 forms (backup, recovery & data lifecycle).

**Seven forms, all `Meta`-only.** Like 0.15, none of them re-states a model rule: `ModelForm._post_clean`
calls `instance.full_clean()`, so every `clean()` in `models/Backup.py` and `models/LegalHold.py` is
already enforced on every form, and a `clean_<field>` copy could never fire on its own. One rule, one
place — and the seeder and the admin get it too.

**No `unique_together` guard is needed here, and that is deliberate, not an oversight.** The repo-wide
trap is that a `unique_together` containing `tenant` is never validated by a `ModelForm` (`tenant` is
never in `Meta.fields`, so `Model._get_unique_checks()` drops the whole tuple and MySQL raises an
`IntegrityError` 500 on create *and* edit). **No 0.16 model declares a `unique_together`** — verified by
grep over `models/Backup.py` and `models/LegalHold.py`. If one is ever added, copy the `clean_name` shape
from `apps/core/forms/Localization.py` (`StatutoryRuleForm`).

**Actor fields are excluded on purpose.** `performed_by`, `requested_by`, `issued_by` and `released_by`
are never form fields: the actor is the request user. If `released_by` were editable, a user could
attribute the release of a legal hold to somebody else — and the release of a hold is precisely the act
an audit exists to attribute. `BackupJob.integrity_verified_at` is excluded for the same reason: it is
written only by the POST-only `backup_job_verify` action, so the register cannot be edited into claiming
a verification that never happened.
"""
from apps.core.forms._common import *  # noqa: F401,F403
from apps.core.models import (
    BackupJob,
    DataArchive,
    EnvironmentInstance,
    RecoveryDrill,
    RecoveryPosture,
    RestoreRecord,
)
from apps.core.models.LegalHold import LegalHold


class BackupJobForm(TenantModelForm):
    """A recorded backup. Note what is absent: the integrity verification stamp."""

    class Meta:
        model = BackupJob
        fields = ["name", "scope_label", "backup_type", "frequency", "retention_days",
                  "target_location", "storage_tier", "encryption_scheme", "encryption_key",
                  "size_bytes", "checksum", "integrity_method", "status", "failure_reason",
                  "attempt_count", "is_immutable", "retain_until", "started_at", "finished_at",
                  "evidence", "notes"]


class RestoreRecordForm(TenantModelForm):
    """A restore operation. `target_time` is validated against the source's window in the model."""

    class Meta:
        model = RestoreRecord
        fields = ["backup", "archive", "scope", "target_time", "target_environment", "status",
                  "reason", "started_at", "finished_at", "outcome", "is_verified", "evidence"]


class DataArchiveForm(TenantModelForm):
    """A catalogue entry. `location` is required — without it a restore is impossible."""

    class Meta:
        model = DataArchive
        fields = ["name", "policy", "disposal", "model_label", "content_description", "location",
                  "storage_tier", "format", "record_count", "size_bytes", "encryption_key",
                  "checksum", "immutable", "archived_at", "restored_at", "expires_at", "status",
                  "notes"]


class LegalHoldForm(TenantModelForm):
    """A preservation order.

    `issued_by` and `released_by` are absent by design (see the module docstring). The anti-spoliation
    rule that refuses a release while a sibling hold covers the same scope lives in the model's `clean()`
    so that it cannot be bypassed by any caller.
    """

    class Meta:
        model = LegalHold
        fields = ["name", "custodian", "subject_party", "matter_reference", "issuing_authority",
                  "scope", "retention_policy", "model_label", "status", "released_at",
                  "release_reason", "authority_reference", "notes"]


class EnvironmentInstanceForm(TenantModelForm):
    """A provisioned environment — bullets 2 and 5 of the catalog, one model."""

    class Meta:
        model = EnvironmentInstance
        fields = ["name", "kind", "tier", "source_environment", "copy_scope", "subset_rule",
                  "copy_includes_pii", "masking_required", "status", "refreshed_at",
                  "refresh_source", "refresh_interval_days", "expires_at", "storage_limit_mb",
                  "is_active", "notes"]
        # Django's default label for these two is `Copy includes pii` / `Storage limit mb` (I11) — a
        # mid-level form that reads like a database dump. `Meta.labels` is the minimal fix: no field
        # redeclaration, no model `verbose_name` (which would need a migration for a cosmetic change).
        labels = {"copy_includes_pii": "Copy includes PII",
                  "storage_limit_mb": "Storage limit (MB)"}


class RecoveryPostureForm(TenantModelForm):
    """The workspace's DR targets. A singleton — edited, never created or deleted."""

    class Meta:
        model = RecoveryPosture
        fields = ["rpo_target_minutes", "rto_target_minutes", "replication_mode", "primary_region",
                  "dr_region", "backup_retention_days", "dr_plan_reference", "last_reviewed_at"]


class RecoveryDrillForm(TenantModelForm):
    """A rehearsal, carrying MEASURED actuals. Never writes back to the posture's targets."""

    class Meta:
        model = RecoveryDrill
        fields = ["name", "kind", "scheduled_for", "performed_at", "outcome",
                  "measured_rpo_minutes", "measured_rto_minutes", "participants", "findings",
                  "follow_up_actions", "evidence", "notes"]
        # `Measured rpo minutes` -> `Measured RPO (minutes)` (I11): RPO/RTO are initialisms, not words,
        # so Django's `capitalize()`-style label is wrong rather than merely ugly.
        labels = {"measured_rpo_minutes": "Measured RPO (minutes)",
                  "measured_rto_minutes": "Measured RTO (minutes)"}
