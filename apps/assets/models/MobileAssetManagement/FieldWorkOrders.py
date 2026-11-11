from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.assets.models._base import TenantNumbered


class FieldWorkOrder(TenantNumbered):
    """
    Mobile field technician job dispatch, en-route / on-site status tracking,
    wrench-time logging, parts requisition, and digital customer/supervisor signoff [MFWO-].
    """

    NUMBER_PREFIX = "MFWO"

    WORK_ORDER_TYPE_CHOICES = [
        ("emergency_repair", "Emergency Breakdown Repair"),
        ("scheduled_pm", "Scheduled Preventive Service"),
        ("inspection_followup", "Inspection Defect Remediation"),
        ("calibration", "On-Site Precision Calibration"),
        ("installation", "Equipment Installation / Commissioning"),
    ]

    PRIORITY_CHOICES = [
        ("low", "Low Priority"),
        ("medium", "Medium Priority"),
        ("high", "High Priority"),
        ("urgent", "Urgent / Critical Outage"),
    ]

    STATUS_CHOICES = [
        ("dispatched", "Dispatched / In Queue"),
        ("en_route", "Technician En Route"),
        ("on_site", "Technician On Site"),
        ("in_progress", "Work In Progress"),
        ("paused", "Paused / Waiting Parts"),
        ("completed", "Work Completed"),
        ("cancelled", "Cancelled"),
    ]

    STATUS_CSS = {
        "dispatched": "badge-slate",
        "en_route": "badge-info",
        "on_site": "badge-amber",
        "in_progress": "badge-amber",
        "paused": "badge-muted",
        "completed": "badge-green",
        "cancelled": "badge-red",
    }

    PRIORITY_CSS = {
        "low": "badge-slate",
        "medium": "badge-info",
        "high": "badge-amber",
        "urgent": "badge-red",
    }

    WORK_ORDER_TYPE_CSS = {
        "emergency_repair": "badge-red",
        "scheduled_pm": "badge-green",
        "inspection_followup": "badge-info",
        "calibration": "badge-slate",
        "installation": "badge-purple",
    }

    title = models.CharField(max_length=200, help_text="Brief title of the field service task")
    work_order_type = models.CharField(max_length=32, choices=WORK_ORDER_TYPE_CHOICES, default="scheduled_pm")
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default="medium")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="dispatched")
    asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.CASCADE,
        related_name="field_work_orders",
        help_text="Subject operational equipment serviced",
    )
    fixed_asset = models.ForeignKey(
        "accounting.FixedAsset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="field_work_orders",
    )
    assigned_technician = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="assigned_field_work_orders",
    )
    maintenance_request = models.ForeignKey(
        "assets.AssetMaintenanceRequest",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="field_work_orders",
    )
    scheduled_start = models.DateTimeField(default=timezone.now)
    scheduled_end = models.DateTimeField(null=True, blank=True)
    actual_arrival = models.DateTimeField(null=True, blank=True, help_text="Recorded when technician clocks on-site")
    completed_at = models.DateTimeField(null=True, blank=True, help_text="Timestamp of job wrap-up")
    labor_wrench_minutes = models.PositiveIntegerField(default=0, help_text="Actual wrench time logged in minutes")
    safety_lockout_confirmed = models.BooleanField(default=False, help_text="LOTO safety protocol verified before repair")
    parts_requisition_notes = models.TextField(blank=True, help_text="Parts, gaskets, fluids, or filters requisitioned")
    estimated_parts_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    work_performed_notes = models.TextField(blank=True, help_text="Technical writeup of diagnosis and root cause remedy")
    signature_name = models.CharField(max_length=150, blank=True, help_text="Supervisor or customer contact signee")
    signature_designation = models.CharField(max_length=100, blank=True, help_text="Title of person signing verification")
    signed_at = models.DateTimeField(null=True, blank=True)
    dispatch_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    dispatch_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    completion_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    completion_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    client_sync_id = models.CharField(max_length=64, blank=True)
    is_offline_captured = models.BooleanField(default=False)
    synced_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-scheduled_start", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="assets_mfwo_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_mfwo_ten_stat"),
            models.Index(fields=["tenant", "priority"], name="idx_mfwo_ten_prio"),
            models.Index(fields=["tenant", "work_order_type"], name="idx_mfwo_ten_type"),
            models.Index(fields=["tenant", "scheduled_start"], name="idx_mfwo_ten_sched"),
        ]

    def __str__(self):
        return f"{self.number} - {self.title} ({self.get_status_display()})"

    @property
    def status_badge_class(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def priority_badge_class(self):
        return self.PRIORITY_CSS.get(self.priority, "badge-slate")

    @property
    def type_badge_class(self):
        return self.WORK_ORDER_TYPE_CSS.get(self.work_order_type, "badge-slate")
