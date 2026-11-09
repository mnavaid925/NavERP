from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.assets.models._base import TenantNumbered


class AssetMaintenanceRequest(TenantNumbered):
    """
    Operator breakdown and preventive repair intake ticketing, urgency triage,
    downtime tracking, and technician/vendor dispatching record [AMRQ-].
    """

    NUMBER_PREFIX = "AMRQ"

    REQUEST_TYPE_CHOICES = [
        ("breakdown_repair", "Breakdown Repair"),
        ("preventive_inspection", "Preventive Inspection"),
        ("safety_hazard", "Safety / Environmental Hazard"),
        ("calibration", "Calibration / Alignment"),
        ("facility_upkeep", "Facility Upkeep"),
    ]

    URGENCY_CHOICES = [
        ("low", "Low (Non-urgent)"),
        ("medium", "Medium (Standard)"),
        ("high", "High (Production Impact)"),
        ("critical", "Critical (Total Shutdown / Safety)"),
    ]

    STATUS_CHOICES = [
        ("submitted", "Submitted"),
        ("triaged", "Triaged / Accepted"),
        ("assigned", "Assigned / Dispatched"),
        ("in_progress", "Work in Progress"),
        ("resolved", "Resolved / Repaired"),
        ("rejected", "Rejected"),
        ("closed", "Closed / Verified"),
    ]

    STATUS_CSS = {
        "submitted": "badge-info",
        "triaged": "badge-slate",
        "assigned": "badge-amber",
        "in_progress": "badge-amber",
        "resolved": "badge-green",
        "rejected": "badge-red",
        "closed": "badge-muted",
    }

    URGENCY_CSS = {
        "critical": "badge-red",
        "high": "badge-amber",
        "medium": "badge-info",
        "low": "badge-slate",
    }

    REQUEST_TYPE_CSS = {
        "breakdown_repair": "badge-red",
        "preventive_inspection": "badge-info",
        "safety_hazard": "badge-amber",
        "calibration": "badge-slate",
        "facility_upkeep": "badge-muted",
    }

    title = models.CharField(
        max_length=255,
        help_text="Brief title or symptom summary of the malfunction/request",
    )
    fixed_asset = models.ForeignKey(
        "accounting.FixedAsset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="maintenance_requests",
        help_text="Financial Fixed Asset in accounting register",
    )
    operational_asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="maintenance_requests",
        help_text="Operational machinery or equipment master",
    )
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submitted_asset_maintenance_requests",
        help_text="Staff user who reported the issue",
    )
    department = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_maintenance_requests",
        help_text="Requesting department or location cost center",
    )
    request_type = models.CharField(
        max_length=32,
        choices=REQUEST_TYPE_CHOICES,
        default="breakdown_repair",
        help_text="Classification of maintenance issue",
    )
    urgency = models.CharField(
        max_length=20,
        choices=URGENCY_CHOICES,
        default="medium",
        help_text="Operational urgency tier",
    )
    is_breakdown = models.BooleanField(
        default=False,
        help_text="Flag indicating asset is completely inoperable / production halted",
    )
    downtime_started_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when equipment stopped operating",
    )
    symptom_description = models.TextField(
        help_text="Detailed description of malfunction, noises, visual leaks, or error codes",
    )
    triage_notes = models.TextField(
        blank=True,
        help_text="Maintenance supervisor assessment, hazard check, and prioritization notes",
    )
    assigned_technician = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_asset_maintenance_requests",
        help_text="Internal technician assigned to perform repair",
    )
    assigned_vendor = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_asset_maintenance_requests",
        help_text="External contractor or OEM service vendor",
    )
    service_contract = models.ForeignKey(
        "assets.AssetServiceContract",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="maintenance_requests",
        help_text="Active third-party service contract covering this asset",
    )
    dispatched_work_order = models.ForeignKey(
        "scm.MaintenanceWorkOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_maintenance_requests",
        help_text="Linked shopfloor operational maintenance work order",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="submitted",
        help_text="Lifecycle state of maintenance ticket",
    )
    resolution_summary = models.TextField(
        blank=True,
        help_text="Technical summary of corrective action taken and parts replaced",
    )
    resolved_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp when repair was finished and verified",
    )
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="resolved_asset_maintenance_requests",
        help_text="Technician or supervisor who signed off on resolution",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="assets_amrq_ten_num_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_amrq_ten_stat"),
            models.Index(fields=["tenant", "urgency"], name="idx_amrq_ten_urg"),
            models.Index(fields=["tenant", "is_breakdown"], name="idx_amrq_ten_bkdn"),
            models.Index(fields=["tenant", "fixed_asset"], name="idx_amrq_ten_fa"),
        ]

    def __str__(self):
        return f"{self.number} - {self.title}"

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def urgency_css(self):
        return self.URGENCY_CSS.get(self.urgency, "badge-slate")

    @property
    def request_type_css(self):
        return self.REQUEST_TYPE_CSS.get(self.request_type, "badge-slate")

    def triage(self, urgency=None, triage_notes=""):
        if urgency:
            self.urgency = urgency
        if triage_notes:
            self.triage_notes = triage_notes
        self.status = "triaged"
        self.save(update_fields=["urgency", "triage_notes", "status", "updated_at"])

    def dispatch(self, technician=None, vendor=None, service_contract=None, work_order=None):
        if technician:
            self.assigned_technician = technician
        if vendor:
            self.assigned_vendor = vendor
        if service_contract:
            self.service_contract = service_contract
        if work_order:
            self.dispatched_work_order = work_order
        self.status = "assigned"
        self.save(
            update_fields=[
                "assigned_technician",
                "assigned_vendor",
                "service_contract",
                "dispatched_work_order",
                "status",
                "updated_at",
            ]
        )

    def start_work(self):
        self.status = "in_progress"
        self.save(update_fields=["status", "updated_at"])

    def resolve(self, user, summary=""):
        self.status = "resolved"
        self.resolved_by = user
        self.resolved_at = timezone.now()
        if summary:
            self.resolution_summary = summary
        self.save(
            update_fields=[
                "status",
                "resolved_by",
                "resolved_at",
                "resolution_summary",
                "updated_at",
            ]
        )

    def close(self):
        self.status = "closed"
        self.save(update_fields=["status", "updated_at"])

    def reject(self, reason=""):
        self.status = "rejected"
        if reason:
            self.resolution_summary = f"REJECTED: {reason}"
        self.save(update_fields=["status", "resolution_summary", "updated_at"])
