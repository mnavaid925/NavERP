"""core — 0.20 forms: the job register, the maintenance window, the change register and its rollouts.

**Five forms, all `Meta`-only except the one that cannot be.** `ModelForm._post_clean()` calls
`instance.full_clean()`, so every `clean()` in `models/JobScheduler.py`, `models/Maintenance.py`
and `models/Change.py` already holds on every form, on the admin and on the seeder. A
`clean_<field>` copy could never fire on its own, so one rule lives in one place.

**The one exception is `FeatureRolloutForm`, and it is forced.** The repo-wide trap the 0.16 form
docstring describes applies here: a `unique_together` is never validated by a `ModelForm`, because
`Model._get_unique_checks()` only sees fields that are in `Meta.fields`, and the database raises
`IntegrityError` as a 500 on save. `FeatureRollout` declares
`unique_together = (("change", "feature_flag"),)`, so the user-facing failure needs a form-level
duplicate guard. It copies the `clean_<field>` shape from `apps/core/forms/Localization.py`
(`StatutoryRuleForm`).

**Every evidence stamp and every actor field is excluded, on purpose.**
`JobDefinition.last_run_at` / `next_run_at`, `JobRun.triggered_at` / `triggered_by`,
`MaintenanceWindow.ended_at`, and `ChangeRequest.requestor` / `approved_by` / `requested_at` /
`approved_at` / `implemented_at` / `rollback_at` / `rollback_reason` / `post_review` are all written
by a POST-only verb or by the system, never by a form (L22). If `approved_by` were editable a user
could attribute an approval to somebody else — and the approval is precisely the act an audit
exists to attribute.
"""
from django.core.exceptions import ValidationError

from apps.core.forms._common import *  # noqa: F401,F403
from apps.core.models import (
    ChangeRequest,
    FeatureRollout,
    JobDefinition,
    JobRun,
    MaintenanceWindow,
)


class JobDefinitionForm(TenantModelForm):
    """A declared job. Note what is absent: `last_run_at` and `next_run_at`.

    Those two are recorded intent that no scheduler advances, so letting a form set them would let
    the register assert a cadence it has never observed. `handler_path` stays editable because the
    point of the register is to record the declared target; the model's `help_text` says plainly
    that nothing imports it.
    """

    class Meta:
        model = JobDefinition
        fields = ["name", "module_slug", "job_type", "description", "schedule_kind",
                  "cron_expression", "interval_minutes", "handler_path", "sync_schedule",
                  "environment", "is_active", "priority", "timeout_seconds", "max_active_runs",
                  "pool_name", "pool_slots", "max_consecutive_failures", "auto_pause_after",
                  "is_muted", "notes"]


class JobRunForm(TenantModelForm):
    """A run record. `triggered_at` and `triggered_by` are excluded — see the module docstring.

    There is deliberately NO create route and no Add button for a `JobRun`: the only legitimate
    writer is the `run_now` verb. This form exists so an operator can correct a recorded outcome,
    and the `status` field it does expose is governed by `JobRun.clean()` — a `success` with no
    `finished_at`, or a `failed` with no `error_message`, is refused here as well as in the model.
    """

    class Meta:
        model = JobRun
        fields = ["job", "trigger_kind", "status", "is_dry_run", "started_at", "finished_at",
                  "exit_code", "records_processed", "duration_ms", "error_message", "notes"]


class MaintenanceWindowForm(TenantModelForm):
    """A maintenance window. `ended_at` is excluded — only the `end_now` verb writes it.

    `status` IS editable, and that combination is deliberate: `MaintenanceWindow.clean()` refuses
    `ended_early` without an `ended_at`, so a user who types that status gets a refusal explaining
    that a window may only be ended by the verb which records the ending, never by typing a status.
    The two recorded-scope booleans stay editable because stating the intent is the operator's job;
    each carries a `help_text` saying that nothing enforces it.
    """

    class Meta:
        model = MaintenanceWindow
        fields = ["title", "purpose", "starts_at", "ends_at", "recurrence", "timezone_label",
                  "status", "affected_services", "suppressed_alert_rules",
                  "suppressed_notification_rules", "incident", "environment", "change_request",
                  "suppresses_jobs", "blocks_admin_writes", "notes"]


class ChangeRequestForm(TenantModelForm):
    """A change record. Every actor field and every evidence stamp is excluded.

    `requestor` and `approved_by` come from the acting user at the verb that performs the
    transition; `requested_at` / `approved_at` / `implemented_at` / `rollback_at` are the L22
    evidence stamps; `rollback_reason` is only meaningful alongside a rollback verb, which refuses
    without it. `post_review` is excluded for the same reason a verification stamp is: it is
    written after the fact, never as part of authoring the change.
    """

    class Meta:
        model = ChangeRequest
        fields = ["title", "summary", "change_type", "risk_level", "impact_level", "status",
                  "environment", "requested_at", "downtime_required", "notes"]


class FeatureRolloutForm(TenantModelForm):
    """One rollout stage. `started_at` and `completed_at` are excluded.

    Both are written by the verb that moves the stage, never typed. The duplicate guard below is
    the one hand-written rule in this file, and it exists because `unique_together` is enforced
    only by the database: without it a user who stages the same flag twice under one change gets a
    500 rather than a field error.
    """

    class Meta:
        model = FeatureRollout
        fields = ["change", "feature_flag", "stage", "percentage", "cohort_label",
                  "scheduled_at", "status", "notes"]

    def clean_feature_flag(self):
        """Refuse a second stage for the same flag under the same change.

        Scoped to the instance being edited, so re-saving an existing rollout with its own flag is
        not mistaken for a duplicate. The database raises `IntegrityError` on this pair regardless;
        this turns that 500 into a message attached to the field that caused it.
        """
        flag = self.cleaned_data.get("feature_flag")
        if not flag:
            return flag
        change = self.cleaned_data.get("change")
        if not change:
            return flag
        clash = FeatureRollout.objects.filter(change=change, feature_flag=flag)
        if self.instance.pk:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise ValidationError(
                "This flag is already staged under this change request. A change stages each flag "
                "once; edit the existing stage instead.")
        return flag

