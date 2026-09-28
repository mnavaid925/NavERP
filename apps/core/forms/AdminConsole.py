"""core — 0.20 forms: the job register, the maintenance window, the change register and its rollouts.

**Validation lives in one place: the model.** `ModelForm._post_clean()` calls
`instance.full_clean()`, so every `clean()` in `models/JobScheduler.py`, `models/Maintenance.py`
and `models/Change.py` already holds on every form, on the admin and on the seeder. A
`clean_<field>` copy could never fire on its own, so one rule lives in one place.

**The forms narrow the CHOICES a person may author; they never re-implement a guard.** Three
`__init__` methods restrict a `status` widget to the values a human can legitimately set from a
form — `ChangeRequestForm` offers `draft` only, `MaintenanceWindowForm` drops `ended_early`,
`FeatureRolloutForm` drops `completed` — because each of those statuses needs an evidence stamp
that is deliberately NOT on the form. This is a *usability* narrowing, not the safety property:
the model's `clean()` still fires for the Django admin and for any API caller, and on the form it
renders as a non-field error. Every guard that keys an excluded stamp is keyed on
`NON_FIELD_ERRORS`, because `add_error()` raises `ValueError` for a key that is not a form field
and that turned an ordinary dropdown choice into a 500.

**One hand-written rule remains: `FeatureRolloutForm.clean_feature_flag`, and it is forced.** The
repo-wide trap the 0.16 form docstring describes applies here: a `unique_together` is never
validated by a `ModelForm`, because `Model._get_unique_checks()` only sees fields that are in
`Meta.fields`, and the database raises `IntegrityError` as a 500 on save. `FeatureRollout` declares
`unique_together = (("change", "feature_flag"),)`, so the user-facing failure needs a form-level
duplicate guard. It copies the `clean_<field>` shape from `apps/core/forms/Localization.py`
(`StatutoryRuleForm`).

**Every evidence stamp and every actor field is excluded, on purpose.**
`JobDefinition.last_run_at` / `next_run_at`, `JobRun.triggered_at` / `triggered_by` /
`is_dry_run`, `MaintenanceWindow.ended_at`, and `ChangeRequest.requestor` / `approved_by` /
`requested_at` / `approved_at` / `implemented_at` / `rollback_at` / `rollback_reason` /
`post_review` are all written by a POST-only verb or by the system, never by a form (L22). If
`approved_by` were editable a user could attribute an approval to somebody else — and the approval
is precisely the act an audit exists to attribute. `requested_at` was on `ChangeRequestForm` until
this pass: a hand-made POST could forge the request date on the register, and permanently so on a
row that stayed a draft, because the submit verb only overwrites it on the legitimate path.
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


def _narrow_status(form, status_choices, authorable):
    """Restrict a `status` widget to the values a person may AUTHOR, without clobbering a row.

    `authorable` is the subset of `status_choices` a form may set. Two rules make this safe:

    1. **Never offer a value the model would refuse** for want of an evidence stamp the form does
       not carry. Those are the values that used to 500.
    2. **Never silently change an existing row's status.** On EDIT the instance already holds a
       status that may sit outside `authorable` — a submitted change, a window a verb ended early.
       A `<select>` whose current value is not among its options renders with NOTHING selected,
       so the browser posts the first option, and that first option is a legal value: editing an
       approved change's title would quietly reset it to Draft. So the instance's own current
       status is added back to the choices on edit, marked as current. It is selectable (the row
       genuinely is in that state, and hiding it would misrepresent the record) but it is never
       *offered* as something new to move into, because it is already there.

    An UNSAVED instance (a create form) has no status worth preserving, so only `authorable` is
    shown there.
    """
    choices = [(v, l) for v, l in status_choices if v in authorable]
    current = getattr(form.instance, "status", None)
    if current and not form.instance.pk:
        # Unsaved instance: nothing to preserve.
        current = None
    if current and current not in authorable:
        label = dict(status_choices).get(current, current)
        choices.append((current, "%s (current)" % label))
    form.fields["status"].widget.choices = choices


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
    """A run record. `triggered_at`, `triggered_by` and `is_dry_run` are excluded.

    The first two are stamped by the action that requested the run, so the register cannot be
    edited into claiming a different requester or time. `is_dry_run` is dropped for the same
    reason it defaults to `True` in the model: nothing in this repository can legitimately clear
    it, so a checkbox that could would let an operator edit a dry run into asserting a real one.

    There is deliberately NO create route and no Add button for a `JobRun`: the only legitimate
    writer is the `run_now` verb. This form exists so an operator can correct a recorded outcome,
    and the `status` field it does expose is governed by `JobRun.clean()` — a `success` with no
    `finished_at`, or a `failed` with no `error_message`, is refused here as well as in the model.
    """

    class Meta:
        model = JobRun
        fields = ["job", "trigger_kind", "status", "started_at", "finished_at",
                  "exit_code", "records_processed", "duration_ms", "error_message", "notes"]


class MaintenanceWindowForm(TenantModelForm):
    """A maintenance window. `ended_at` is excluded — only the `end_now` verb writes it.

    `status` IS editable, and that combination is deliberate: the `status` widget below offers
    only the values a person may AUTHOR, so `ended_early` is never on the dropdown. Ending a
    window early is the POST-only verb's job, because only the verb can write the `ended_at`
    evidence stamp — `MaintenanceWindow.clean()` refuses `ended_early` without it, and that
    refusal renders as a non-field error rather than a 500.
    The two recorded-scope booleans stay editable because stating the intent is the operator's
    job; each carries a `help_text` saying that nothing enforces it.
    """

    class Meta:
        model = MaintenanceWindow
        fields = ["title", "purpose", "starts_at", "ends_at", "recurrence", "timezone_label",
                  "status", "affected_services", "suppressed_alert_rules",
                  "suppressed_notification_rules", "incident", "environment", "change_request",
                  "suppresses_jobs", "blocks_admin_writes", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # `ended_early` needs `ended_at`, which is not on this form, so it is not authorable here.
        # The model guard stays for the admin and for the verb's own callers.
        _narrow_status(
            self, MaintenanceWindow.STATUS_CHOICES,
            authorable={"draft", "scheduled", "active", "completed", "cancelled"})


class ChangeRequestForm(TenantModelForm):
    """A change record. Every actor field and every evidence stamp is excluded.

    `requestor` and `approved_by` come from the acting user at the verb that performs the
    transition; `requested_at` / `approved_at` / `implemented_at` / `rollback_at` are the L22
    evidence stamps; `rollback_reason` is only meaningful alongside a rollback verb, which refuses
    without it. `post_review` is excluded for the same reason a verification stamp is: it is
    written after the fact, never as part of authoring the change.

    **`status` offers `draft` ONLY** (see `__init__`). Every other lifecycle value needs a stamp
    this form cannot supply — `approved` needs an approver, `rolled_back` needs a reason and a
    time — and `submitted` is the submit verb's transition. Those transitions are POST-only verbs
    that stamp the evidence themselves; a status dropdown that offered them was a dropdown that
    promised a state the form could not make true.
    """

    class Meta:
        model = ChangeRequest
        fields = ["title", "summary", "change_type", "risk_level", "impact_level", "status",
                  "environment", "downtime_required", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Authorable values only. `ChangeRequest.clean()` still refuses an unstamped approval or
        # rollback for the admin and for any API caller; those refusals render as non-field errors.
        _narrow_status(self, ChangeRequest.STATUS_CHOICES, authorable={"draft"})


class FeatureRolloutForm(TenantModelForm):
    """One rollout stage. `started_at` and `completed_at` are excluded.

    Both are written by the verb that moves the stage, never typed. `status` therefore offers
    every value EXCEPT `completed`: completing a stage is a transition that records when it
    finished, and only the mover may record that. `FeatureRollout.clean()` still refuses an
    unstamped completion for the admin and for any API caller.

    The duplicate guard below is the one hand-written rule in this file, and it exists because
    `unique_together` is enforced only by the database: without it a user who stages the same flag
    twice under one change gets a 500 rather than a field error.
    """

    class Meta:
        model = FeatureRollout
        fields = ["change", "feature_flag", "stage", "percentage", "cohort_label",
                  "scheduled_at", "status", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # `completed` needs `completed_at`, which is not on this form.
        _narrow_status(
            self, FeatureRollout.STATUS_CHOICES,
            authorable={"planned", "running", "paused", "rolled_back"})

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

