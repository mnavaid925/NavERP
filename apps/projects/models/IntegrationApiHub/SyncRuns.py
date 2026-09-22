"""Projects 7.18 — ProjectSyncRun model [SYR-], APPEND-ONLY.

What each sync batch actually did — the register a PMO argues about ("last night's Jira push",
"chase SYR-00042"). Numbered for that reason, mirroring ``inventory.StockSyncRun``'s explicit ruling.
Append-only: list + detail + ``syr_retry`` only; there is no form and no create/edit/delete url.

``status="simulated"`` is MANDATORY honesty: nothing in this build leaves the process, so no run is
ever a real transfer. The ONLY writer is :meth:`record` (the run verb, the retry verb and the seeder
all go through it); the seeder must NEVER bare-``.create()`` a run. Retry semantics (docstring lives
here): ``syr_retry`` sets ``status="pending"``, ``attempt_no += 1``, stamps ``next_retry_at`` from
``SYNC_BACKOFF_SECONDS[min(attempt_no, 7)]``, and **performs no HTTP request**.
"""
from apps.projects.models._base import *


#: Svix's 8 retry slots, adopted verbatim as scm 4.19's ``DELIVERY_BACKOFF_SECONDS`` and
#: inventory 5.19's ``SYNC_BACKOFF_SECONDS``.
SYNC_BACKOFF_SECONDS = (0, 5, 300, 1800, 7200, 18000, 36000, 36000)


class ProjectSyncRun(TenantNumbered):
    """One append-only record of a sync batch (always simulated in this build)."""

    NUMBER_PREFIX = "SYR"

    RUN_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("running", "Running"),
        ("success", "Success"),
        ("partial", "Partial"),
        ("failed", "Failed"),
        ("skipped", "Skipped"),
        ("simulated", "Simulated"),
    ]
    DIRECTION_CHOICES = [
        ("inbound", "Inbound"),
        ("outbound", "Outbound"),
        ("bidirectional", "Bidirectional"),
    ]
    TRIGGER_SOURCE_CHOICES = [
        ("manual", "Manual"),
        ("schedule", "Schedule"),
        ("event", "Event"),
    ]

    job = models.ForeignKey(
        "projects.ProjectSyncJob",
        on_delete=models.CASCADE,
        related_name="runs",
    )
    direction = models.CharField(max_length=14, choices=DIRECTION_CHOICES, default="bidirectional")
    status = models.CharField(max_length=10, choices=RUN_STATUS_CHOICES, default="pending")
    trigger_source = models.CharField(max_length=10, choices=TRIGGER_SOURCE_CHOICES, default="manual")
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        editable=False,
        related_name="+",
    )
    records_read = models.PositiveIntegerField(default=0)
    records_created = models.PositiveIntegerField(default=0)
    records_updated = models.PositiveIntegerField(default=0)
    records_skipped = models.PositiveIntegerField(default=0)
    records_failed = models.PositiveIntegerField(default=0)
    error_code = models.CharField(max_length=50, blank=True)
    error_message = models.TextField(blank=True)
    payload_excerpt = models.TextField(blank=True, help_text="Truncated; may contain partner PII.")
    attempt_no = models.PositiveSmallIntegerField(default=1)
    next_retry_at = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(default=timezone.now, editable=False)
    finished_at = models.DateTimeField(null=True, blank=True, editable=False)
    duration_ms = models.PositiveIntegerField(default=0, editable=False)

    class Meta:
        ordering = ["-started_at", "-id"]
        unique_together = [("tenant", "number")]
        indexes = [
            models.Index(fields=["tenant", "job", "status"], name="syr_tnt_job_stat_idx"),
            models.Index(fields=["tenant", "status", "started_at"], name="syr_tnt_stat_strt_idx"),
            models.Index(fields=["tenant", "job", "started_at"], name="syr_tnt_job_strt_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.get_status_display()} @ {self.started_at:%Y-%m-%d %H:%M}"

    def clean(self):
        super().clean()
        if self.job_id and self.job.tenant_id != self.tenant_id:
            raise ValidationError({"job": "Sync job belongs to another workspace."})

    @classmethod
    def record(cls, *, job, status="simulated", trigger_source="manual", triggered_by=None,
               direction=None, records_read=0, records_created=0, records_updated=0,
               records_skipped=0, records_failed=0, error_code="", error_message="",
               payload_excerpt="", attempt_no=1, next_retry_at=None, started_at=None,
               finished_at=None, duration_ms=0):
        """The ONLY writer for a run. Snapshots the job's direction and inherits its tenant."""
        return cls.objects.create(
            tenant=job.tenant,
            job=job,
            status=status,
            trigger_source=trigger_source,
            triggered_by=triggered_by,
            direction=direction or job.direction,
            records_read=records_read,
            records_created=records_created,
            records_updated=records_updated,
            records_skipped=records_skipped,
            records_failed=records_failed,
            error_code=error_code,
            error_message=error_message,
            payload_excerpt=payload_excerpt,
            attempt_no=attempt_no,
            next_retry_at=next_retry_at,
            started_at=started_at or timezone.now(),
            finished_at=finished_at,
            duration_ms=duration_ms,
        )

    @property
    def status_badge(self):
        return {
            "success": "badge-green",
            "partial": "badge-amber",
            "failed": "badge-red",
            "simulated": "badge-info",
            "pending": "badge-slate",
            "running": "badge-slate",
            "skipped": "badge-muted",
        }.get(self.status, "badge-slate")
