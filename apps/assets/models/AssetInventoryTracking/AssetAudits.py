from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.assets.models._base import TenantNumbered


class AssetAudit(TenantNumbered):
    """Scheduled cycle count, wall-to-wall physical inventory audit, and discrepancy reconciliation [AAUD-]."""

    NUMBER_PREFIX = "AAUD"

    AUDIT_TYPE_CHOICES = [
        ("wall_to_wall", "Wall-to-Wall Physical Audit"),
        ("cycle_count", "Cyclical Sample Count"),
        ("spot_check", "Ad-Hoc Spot Check"),
        ("custodian_verification", "Custodian Ownership Verification"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft Scheduled"),
        ("scheduled", "Scheduled"),
        ("in_progress", "In Progress"),
        ("completed", "Count Completed"),
        ("reconciled", "Reconciled & Closed"),
        ("cancelled", "Cancelled"),
    ]

    STATUS_CSS = {
        "draft": "badge-slate",
        "scheduled": "badge-info",
        "in_progress": "badge-amber",
        "completed": "badge-info",
        "reconciled": "badge-green",
        "cancelled": "badge-red",
    }

    RECONCILIATION_ACTION_CHOICES = [
        ("pending_review", "Pending Supervisor Review"),
        ("no_action_needed", "No Discrepancy / Closed"),
        ("location_updated", "Asset Location Updated"),
        ("incident_initiated", "Missing Incident Initiated"),
        ("custodian_reassigned", "Custodian Reassigned"),
    ]

    title = models.CharField(max_length=200, help_text="Audit run title, e.g. Q4 Plant Wall-to-Wall Verification")
    audit_type = models.CharField(max_length=30, choices=AUDIT_TYPE_CHOICES, default="cycle_count")
    target_location = models.ForeignKey(
        "scm.Location",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_audits",
        help_text="Target facility, plant, or warehouse stockroom in audit scope",
    )
    target_org_unit = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_audits",
        help_text="Target department or operating division",
    )
    asset_category = models.CharField(max_length=100, blank=True, help_text="Optional asset category filter in scope")

    lead_auditor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lead_asset_audits",
    )
    supervisor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supervised_asset_audits",
    )

    scheduled_date = models.DateField(default=timezone.now, help_text="Scheduled date for physical count execution")
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    is_blind_count = models.BooleanField(
        default=False,
        help_text="Hide expected asset lists from field counters to prevent confirmation bias",
    )
    expected_asset_count = models.PositiveIntegerField(default=0, help_text="Number of assets registered in target scope")
    scanned_asset_count = models.PositiveIntegerField(default=0, help_text="Total number of physical assets scanned/counted")
    matched_asset_count = models.PositiveIntegerField(default=0, help_text="Assets verified present in designated location")
    missing_asset_count = models.PositiveIntegerField(default=0, help_text="Registered assets not located during audit")
    discrepancy_count = models.PositiveIntegerField(default=0, help_text="Location, custodian, or tag discrepancies noted")

    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="draft")
    discrepancy_notes = models.TextField(blank=True, help_text="Summary of count variances and misplaced items")
    reconciliation_action = models.CharField(
        max_length=30,
        choices=RECONCILIATION_ACTION_CHOICES,
        default="pending_review",
    )
    reconciled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reconciled_asset_audits",
    )
    reconciled_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        db_table = "assets_audit"
        ordering = ["-scheduled_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="assets_aaud_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_aaud_ten_stat"),
            models.Index(fields=["tenant", "audit_type"], name="idx_aaud_ten_type"),
            models.Index(fields=["tenant", "scheduled_date"], name="idx_aaud_ten_date"),
            models.Index(fields=["tenant", "created_at"], name="idx_aaud_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title}"

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")
