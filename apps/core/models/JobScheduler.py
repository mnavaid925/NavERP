"""core — 0.20 bullet 2: the job-definition register and its run history.

**No scheduler exists in this repository, and this file does not create one.** `requirements.txt`
carries no Celery, no RQ, no APScheduler, no django-q and no redis, and `core.SyncSchedule` — which
this model EXTENDS rather than re-declares — still documents itself as "a recorded sync
intention. **Nothing runs it**". So a `JobDefinition` is a DECLARATION: a name, a cadence, a
declared handler path, a pool and a failure policy that an operator has written down. `last_run_at`
and `next_run_at` are recorded intent and **nothing advances them**; no row in this file imports,
calls or resolves `handler_path`. The only writer of a `JobRun` is the POST-only
`jobdefinition_run_now` verb, which records a dry run and says so in its success message.

**Why this file does not redeclare a schedule table (L29/L36).** 0.13's `SyncSchedule` already owns
"what is exchanged and how often" for integrations. A second schedule vocabulary here would be two
parallel schemas for one fact, so `schedule_kind` takes `SyncSchedule.FREQUENCY_CHOICES` **by
reference** (the `core.Monitoring` reuse-by-reference pattern) and `sync_schedule` is an FK onto
0.13's own row. A cron string stays recordable in free text (`cron_expression`) without minting a
second cadence vocabulary to drift.

`JOB-` / `RUN-` are minted with a hardcoded literal in `save()` rather than a `NUMBER_PREFIX`
class attribute, so `core.settings_engine.LITERAL_PREFIX_MODELS` is what makes them discoverable to
the reconciliation board — the same arrangement the four 0.19 licensing models use.
"""
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction

from apps.core.models._base import *  # noqa: F401,F403
from apps.core.models.Integration import SyncSchedule
from apps.core.utils import next_number


#: 0.13's cadence vocabulary, re-exposed BY REFERENCE. Assign the object; never paste a copy. A
#: copied list is two vocabularies that drift, and the numbering/board surfaces would then disagree
#: about what "daily" means. This is the `AlertRule.SEVERITY_CHOICES` reuse in
#: `apps/core/models/Security.py`, restated: the field below reads THIS attribute so a test can
#: assert identity (`is`, not `==`) on the class — Django normalizes a field's own `choices` into a
#: fresh list, so identity is only observable here.
SCHEDULE_KIND_CHOICES = SyncSchedule.FREQUENCY_CHOICES

#: The kinds of background work a tenant declares. `integration_sync` is the one 0.13's
#: `SyncSchedule` drives; the rest are workspace chores a platform admin schedules by hand.
JOB_TYPE_CHOICES = [
    ("scheduled_task", "Scheduled task"),
    ("integration_sync", "Integration sync"),
    ("bulk_operation", "Bulk operation"),
    ("report", "Report"),
    ("cleanup", "Cleanup"),
    ("maintenance", "Maintenance"),
]

#: How a run came to exist. `manual` is the ONLY one anything in this repo can produce — the
#: `run_now` verb writes exactly that. The other three are the vocabulary a real dispatcher would
#: use, kept here so the register does not have to be re-modelled the day one arrives.
TRIGGER_KIND_CHOICES = [
    ("manual", "Manual"),
    ("scheduled", "Scheduled"),
    ("backfill", "Backfill"),
    ("api", "API"),
]

#: The run lifecycle. `queued` and `running` are OPEN; the rest are terminal. Nothing in this repo
#: moves a run out of `queued` on its own.
JOB_RUN_STATUS_CHOICES = [
    ("queued", "Queued"),
    ("running", "Running"),
    ("success", "Success"),
    ("failed", "Failed"),
    ("skipped", "Skipped"),
    ("cancelled", "Cancelled"),
]

class JobDefinition(models.Model):
    """One declared background job — its cadence, its declared handler, and its failure policy.

    Every operational field here is a POLICY somebody wrote down. `priority`, `pool_slots`,
    `max_consecutive_failures` and `auto_pause_after` are not enforced by anything; they are
    recorded so the intent is reviewable. `is_muted` is how a maintenance window silences a job
    (the Datadog downtime-scope idea) — it is a flag on a schedule, not an interceptor.
    """

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="job_definitions", db_index=True)
    #: Re-exposed on the class so a view and a test read the same object, the SecurityThreat /
    #: UsageQuota pattern. `is`, not `==`, is the assertion that matters: two equal lists are
    #: still two lists, and only identity proves this one reuses 0.13's vocabulary rather than a
    #: copy of it that can drift.
    SCHEDULE_KIND_CHOICES = SCHEDULE_KIND_CHOICES
    JOB_TYPE_CHOICES = JOB_TYPE_CHOICES
    #: JOB-##### — minted in save() with a hardcoded literal; see
    #: `core.settings_engine.LITERAL_PREFIX_MODELS`, without which `core:numbering_board` would
    #: report this prefix as configured but minted by no model.
    number = models.CharField(max_length=20, editable=False)
    name = models.CharField(max_length=150)
    #: Which module owns the work, e.g. "crm" or "accounting". Free text on purpose: it is a label
    #: for grouping, not a foreign key, because the alternative would refuse to name a job for a
    #: module this workspace has not installed.
    module_slug = models.CharField(max_length=60)
    job_type = models.CharField(max_length=20, choices=JOB_TYPE_CHOICES, default="scheduled_task")
    description = models.TextField(blank=True)
    #: Reused BY REFERENCE from 0.13 rather than pasted - see `SCHEDULE_KIND_CHOICES` above.
    schedule_kind = models.CharField(max_length=10, choices=SCHEDULE_KIND_CHOICES, default="manual")
    #: Free text so an operator can record a real cron string without this project adopting a cron
    #: parser it does not have. Nothing validates or evaluates it.
    cron_expression = models.CharField(max_length=60, blank=True)
    interval_minutes = models.IntegerField(null=True, blank=True)
    #: The DECLARED target, e.g. "apps.core.tasks.send_expiry_notices". `help_text` says plainly
    #: that nothing imports it — a reader must not believe the string is wired to anything.
    handler_path = models.CharField(
        max_length=200,
        help_text=("Declared target, e.g. apps.core.tasks.send_expiry_notices. RECORDED ONLY - "
                   "nothing in this repository imports or calls it."))
    #: 0.13's own schedule row, when this job carries one of its syncs. Referenced, not copied.
    sync_schedule = models.ForeignKey("core.SyncSchedule", on_delete=models.SET_NULL, null=True,
                                      blank=True, related_name="job_definitions")
    environment = models.ForeignKey("core.EnvironmentInstance", on_delete=models.SET_NULL, null=True,
                                    blank=True, related_name="environment_job_definitions")
    is_active = models.BooleanField(default=True)
    #: Lower runs first. A RECORDED order: no dispatcher sorts by it.
    priority = models.SmallIntegerField(default=100)
    timeout_seconds = models.IntegerField(null=True, blank=True)
    max_active_runs = models.SmallIntegerField(default=1)
    #: Airflow pools as a declaration. No worker pool exists to reserve a slot in.
    pool_name = models.CharField(
        max_length=60, blank=True,
        help_text="Recorded pool name. No worker pool exists; nothing reserves a slot.")
    pool_slots = models.SmallIntegerField(default=1)
    #: A recorded failure policy. Nothing counts failures and nothing pauses a job.
    max_consecutive_failures = models.SmallIntegerField(default=3)
    auto_pause_after = models.SmallIntegerField(default=10)
    #: Recorded intent. No scheduler advances either stamp — the only writer of a run is the
    #: POST-only `jobdefinition_run_now` verb, and it does not touch these.
    last_run_at = models.DateTimeField(null=True, blank=True)
    next_run_at = models.DateTimeField(null=True, blank=True)
    #: How a maintenance window silences a job. A flag on the schedule, not an interceptor.
    is_muted = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="jobdef_tenant_active_idx"),
            models.Index(fields=["tenant", "module_slug"], name="jobdef_tenant_module_idx"),
        ]

    def save(self, *args, **kwargs):
        if self.number:
            return super().save(*args, **kwargs)
        for _ in range(5):  # retry the rare concurrent-collision
            self.number = next_number(JobDefinition, self.tenant, "JOB")
            try:
                with transaction.atomic():
                    return super().save(*args, **kwargs)
            except IntegrityError:
                self.number = ""
        return super().save(*args, **kwargs)

    def __str__(self):
        return "%s %s" % (self.number, self.name)


class JobRun(models.Model):
    """One recorded execution attempt of a `JobDefinition` (the Airflow `DagRun` shape).

    **A row here is a record that a run was ASKED for, not evidence that work happened.** The only
    writer in this repository is the `jobdefinition_run_now` verb, which sets `is_dry_run=True`
    because there is no dispatcher to execute the handler. That is why `is_dry_run` **defaults to
    True** — a `False` on a row written by this codebase would be a false claim, and nothing can
    legitimately clear it.
    """

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="job_runs", db_index=True)
    #: RUN-##### — literal mint; see `core.settings_engine.LITERAL_PREFIX_MODELS`.
    number = models.CharField(max_length=20, editable=False)
    job = models.ForeignKey(JobDefinition, on_delete=models.CASCADE, related_name="runs")
    triggered_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    trigger_kind = models.CharField(max_length=10, choices=TRIGGER_KIND_CHOICES, default="manual")
    status = models.CharField(max_length=10, choices=JOB_RUN_STATUS_CHOICES, default="queued")
    #: True unless a real dispatcher clears it, because no such dispatcher exists.
    is_dry_run = models.BooleanField(default=True)
    triggered_by = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, null=True,
                                     blank=True, related_name="+")
    exit_code = models.IntegerField(null=True, blank=True)
    records_processed = models.IntegerField(null=True, blank=True)
    duration_ms = models.IntegerField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    #: Re-exposed on the class so a view and a template read the same object rather than
    #: importing the module-level tuples separately (the `UsageQuota` pattern).
    STATUS_CHOICES = JOB_RUN_STATUS_CHOICES
    TRIGGER_KIND_CHOICES = TRIGGER_KIND_CHOICES

    class Meta:
        ordering = ["-triggered_at", "-id"]
        indexes = [
            models.Index(fields=["tenant", "status"], name="jobrun_tenant_status_idx"),
            models.Index(fields=["job", "-triggered_at"], name="jobrun_job_time_idx"),
        ]

    def save(self, *args, **kwargs):
        if self.number:
            return super().save(*args, **kwargs)
        for _ in range(5):
            self.number = next_number(JobRun, self.tenant, "RUN")
            try:
                with transaction.atomic():
                    return super().save(*args, **kwargs)
            except IntegrityError:
                self.number = ""
        return super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        # A success nobody timed is not a success — the terminal stamps are what make a run
        # readable later, and a bare "success" row is exactly the zero-evidence row L52 warns
        # against. Same rule for a failure: no message, no failure worth recording.
        if self.status == "success" and self.finished_at is None:
            raise ValidationError({"finished_at": "A successful run must record when it finished."})
        if self.status == "failed":
            if not (self.error_message or "").strip():
                raise ValidationError({"error_message": "A failed run must say what went wrong."})
            if self.finished_at is None:
                raise ValidationError({"finished_at": "A failed run must record when it finished."})
        if self.started_at and self.finished_at and self.finished_at < self.started_at:
            raise ValidationError({"finished_at": "A run cannot finish before it started."})

    @property
    def is_open(self):
        """Queued or running — the states that promise an outcome nobody has delivered."""
        return self.status in ("queued", "running")

    @property
    def duration_display(self):
        """Elapsed time, or an em dash when either stamp is missing.

        **Never `0`**: a run that took no measurable time and a run nobody measured are different
        statements, and collapsing them to the same "0ms" is the null-means-zero defect.
        """
        if not self.started_at or not self.finished_at:
            return "—"
        return "%d ms" % max(0, int((self.finished_at - self.started_at).total_seconds() * 1000))

    def __str__(self):
        return "%s %s" % (self.number, self.get_status_display())


