"""Projects 7.18 — ProjectSyncJob model [SYJ-].

The scoped, repeatable unit of transfer between a connector and a local entity scope (the Workato
*recipe* / Fusion *scenario* / Celigo *flow*). Its project scope is read THROUGH its connector — no
second ``project`` column (one source of truth). ``trigger_mode``/``interval_minutes``/``next_run_at``
are recorded intent/stamps; nothing schedules, polls, or wakes on them. ``filter_expression`` is
recorded, never evaluated (scm 4.19 precedent). 7.18 performs no outbound HTTP.
"""
from apps.projects.models._base import *


class ProjectSyncJob(TenantNumbered):
    """A repeatable, scoped data-transfer unit bound to a connector."""

    NUMBER_PREFIX = "SYJ"

    SYNC_ENTITY_CHOICES = [
        ("tasks", "Tasks"),
        ("issues", "Issues"),
        ("risks", "Risks"),
        ("milestones", "Milestones"),
        ("time_entries", "Time Entries"),
        ("resources", "Resources"),
        ("documents", "Documents"),
        ("folders", "Folders"),
        ("budgets", "Budgets"),
        ("cost_lines", "Cost Lines"),
        ("journals", "Journal Entries"),
        ("custom", "Custom / Other"),
    ]
    DIRECTION_CHOICES = [
        ("inbound", "Inbound"),
        ("outbound", "Outbound"),
        ("bidirectional", "Bidirectional"),
    ]
    TRIGGER_MODE_CHOICES = [
        ("manual", "Manual"),
        ("scheduled", "Scheduled"),
        ("event", "Event-driven"),
    ]
    CONFLICT_POLICY_CHOICES = [
        ("local_wins", "Local Wins"),
        ("remote_wins", "Remote Wins"),
        ("newest_wins", "Newest Wins"),
        ("manual", "Manual"),
    ]

    connector = models.ForeignKey(
        "projects.ProjectIntegrationConnector",
        on_delete=models.CASCADE,
        related_name="jobs",
    )
    name = models.CharField(max_length=255)
    entity_scope = models.CharField(max_length=16, choices=SYNC_ENTITY_CHOICES, default="custom")
    direction = models.CharField(max_length=14, choices=DIRECTION_CHOICES, default="bidirectional")
    trigger_mode = models.CharField(max_length=10, choices=TRIGGER_MODE_CHOICES, default="manual")
    interval_minutes = models.PositiveIntegerField(null=True, blank=True)
    schedule_note = models.CharField(max_length=200, blank=True)
    filter_expression = models.TextField(blank=True, help_text="Recorded, never evaluated.")
    conflict_policy = models.CharField(max_length=12, choices=CONFLICT_POLICY_CHOICES, default="manual")
    batch_size = models.PositiveIntegerField(default=100)
    is_active = models.BooleanField(default=True)
    last_run_at = models.DateTimeField(null=True, blank=True, editable=False)
    next_run_at = models.DateTimeField(null=True, blank=True, editable=False)
    run_count = models.PositiveIntegerField(default=0, editable=False)
    last_status = models.CharField(max_length=10, blank=True, editable=False)

    class Meta:
        ordering = ["-created_at", "-id"]
        unique_together = [("tenant", "number"), ("tenant", "connector", "name")]
        indexes = [
            models.Index(fields=["tenant", "connector"], name="syj_tnt_conn_idx"),
            models.Index(fields=["tenant", "connector", "is_active"], name="syj_tnt_conn_act_idx"),
            models.Index(fields=["tenant", "last_status"], name="syj_tnt_status_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.name}"

    def clean(self):
        super().clean()
        if self.connector_id and self.connector.tenant_id != self.tenant_id:
            raise ValidationError({"connector": "Connector belongs to another workspace."})
