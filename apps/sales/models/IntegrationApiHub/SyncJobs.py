"""Sales 8.18 — SalesSyncJob model."""
from django.db import models

from apps.sales.models._base import TenantNumbered

ENTITY_SCOPE_CHOICES = [
    ("order_to_cash", "Order-to-Cash (ERP)"),
    ("lead_lifecycle", "Lead & Contact Lifecycle (Marketing)"),
    ("deal_alerts", "Deal & Milestone Alerts (Comms)"),
    ("bi_warehouse_feed", "BI & Data Warehouse Export"),
    ("contract_envelope_status", "E-Signature & Contract Envelopes"),
]

DIRECTION_CHOICES = [
    ("bidirectional", "Two-Way Bidirectional (⇄)"),
    ("outbound", "Outbound NavERP → Remote (→)"),
    ("inbound", "Inbound Remote → NavERP (←)"),
]

CONFLICT_POLICY_CHOICES = [
    ("last_updated_wins", "Last Updated Timestamp Wins"),
    ("local_wins", "NavERP Record Wins"),
    ("remote_wins", "Remote System Wins"),
    ("flag_manual", "Flag Conflict for Manual Review"),
]

CADENCE_CHOICES = [
    ("realtime_event", "Real-time Event-Driven"),
    ("hourly", "Hourly Batch"),
    ("daily", "Daily Scheduled"),
    ("weekly", "Weekly Scheduled"),
    ("manual_only", "Manual On-Demand Only"),
]

STATUS_CHOICES = [
    ("active", "Active / Scheduled"),
    ("paused", "Paused / Inactive"),
    ("error", "Execution Error"),
]


class SalesSyncJob(TenantNumbered):
    NUMBER_PREFIX = "SSJ"

    name = models.CharField(max_length=150)
    connector = models.ForeignKey(
        "sales.SalesIntegrationConnector",
        on_delete=models.CASCADE,
        related_name="sync_jobs",
    )
    entity_scope = models.CharField(max_length=30, choices=ENTITY_SCOPE_CHOICES, default="order_to_cash")
    sync_direction = models.CharField(max_length=20, choices=DIRECTION_CHOICES, default="outbound")
    conflict_policy = models.CharField(max_length=30, choices=CONFLICT_POLICY_CHOICES, default="last_updated_wins")
    cadence = models.CharField(max_length=30, choices=CADENCE_CHOICES, default="hourly")
    filter_expression = models.CharField(max_length=255, blank=True, default="", help_text="SQL or OData filter expression (e.g. status='confirmed')")
    batch_size = models.PositiveIntegerField(default=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    last_run_at = models.DateTimeField(null=True, blank=True)
    next_run_at = models.DateTimeField(null=True, blank=True)
    total_runs_count = models.PositiveIntegerField(default=0)
    total_records_synced = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="sales_ssj_tenant_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "connector", "status"], name="sales_ssj_conn_stat_idx"),
            models.Index(fields=["tenant", "entity_scope"], name="sales_ssj_scope_idx"),
        ]

    def __str__(self):
        return f"{self.number} — {self.name} ({self.get_entity_scope_display()})"
