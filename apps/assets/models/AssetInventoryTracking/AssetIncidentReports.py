from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.assets.models._base import TenantNumbered


class AssetIncidentReport(TenantNumbered):
    """Incident governance for lost, stolen, damaged beyond repair, or missing assets [AINC-]."""

    NUMBER_PREFIX = "AINC"

    INCIDENT_TYPE_CHOICES = [
        ("lost", "Lost / Misplaced in Field"),
        ("stolen", "Stolen / Burglary"),
        ("missing_in_audit", "Missing During Physical Audit"),
        ("damaged_beyond_repair", "Damaged Beyond Economical Repair"),
        ("vandalism", "Vandalism / Sabotage"),
    ]

    SEVERITY_CHOICES = [
        ("low", "Low (Non-critical / Low Value)"),
        ("medium", "Medium (Standard Asset)"),
        ("high", "High (Production Impact)"),
        ("critical", "Critical (Core Infrastructure / Safety)"),
    ]

    STATUS_CHOICES = [
        ("reported", "Reported / Under Review"),
        ("under_investigation", "Under Active Investigation"),
        ("confirmed_lost", "Confirmed Lost / Missing"),
        ("recovered", "Recovered & Returned"),
        ("write_off_pending", "Pending Write-Off Approval"),
        ("written_off", "Written Off / Decommissioned"),
        ("closed", "Closed Without Recovery"),
    ]

    STATUS_CSS = {
        "reported": "badge-slate",
        "under_investigation": "badge-amber",
        "confirmed_lost": "badge-red",
        "recovered": "badge-green",
        "write_off_pending": "badge-amber",
        "written_off": "badge-muted",
        "closed": "badge-muted",
    }

    RESOLUTION_ACTION_CHOICES = [
        ("pending", "Pending Investigation"),
        ("recovered", "Asset Recovered"),
        ("replacement_sourced", "Replacement Asset Sourced"),
        ("written_off", "Approved for Write-Off"),
        ("unresolved_closed", "Closed Unresolved"),
    ]

    title = models.CharField(max_length=200, help_text="Incident title, e.g. Stolen Fluke Thermal Imager")
    asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.CASCADE,
        related_name="incident_reports",
        help_text="Operational physical asset subject to incident",
    )
    incident_type = models.CharField(max_length=30, choices=INCIDENT_TYPE_CHOICES, default="lost")
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default="medium")
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="reported")
    resolution_action = models.CharField(max_length=30, choices=RESOLUTION_ACTION_CHOICES, default="pending")

    # Chronology & Geography
    incident_date = models.DateField(default=timezone.now, help_text="Date incident occurred or asset was noticed missing")
    last_known_location = models.ForeignKey(
        "scm.Location",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_incidents",
        help_text="Facility or stockroom where asset was last verified",
    )
    location_details = models.CharField(max_length=255, blank=True, help_text="Specific bay, job site, or transit vehicle")

    # Stakeholders
    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reported_asset_incidents",
    )
    custodian_at_loss = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="custodian_asset_incidents",
        help_text="Accountable custodian or borrower when incident occurred",
    )
    investigator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="investigated_asset_incidents",
        help_text="Assigned plant security or risk investigator",
    )

    # Law Enforcement
    police_report_filed = models.BooleanField(default=False)
    police_report_number = models.CharField(max_length=100, blank=True, help_text="Official law enforcement case/incident number")
    police_precinct = models.CharField(max_length=120, blank=True, help_text="Police department or jurisdiction")
    police_filing_date = models.DateField(null=True, blank=True)

    # Insurance Claims
    insurance_claim_filed = models.BooleanField(default=False)
    insurance_carrier = models.CharField(max_length=120, blank=True, help_text="Commercial property or equipment insurer")
    insurance_claim_number = models.CharField(max_length=100, blank=True, help_text="Carrier claim identifier")
    estimated_loss_value = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Estimated replacement value or book loss",
    )
    insurance_claimed_amount = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Amount submitted on insurance claim",
    )
    insurance_settled_amount = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Actual payout settled by insurer",
    )

    # Narrative & Findings
    incident_description = models.TextField(help_text="Detailed narrative of circumstances, eyewitness accounts...")
    investigation_findings = models.TextField(blank=True, help_text="Root-cause investigation, security camera review, findings...")

    # Write-Off & Disposal Initiation
    write_off_authorized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="authorized_asset_write_offs",
        help_text="Tenant Admin or Financial Controller who authorized asset write-off",
    )
    write_off_date = models.DateField(null=True, blank=True)
    write_off_notes = models.TextField(blank=True, help_text="Financial GL write-off reference, salvage scrap authorization...")

    class Meta:
        db_table = "assets_incident_report"
        ordering = ["-incident_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="assets_ainc_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_ainc_ten_stat"),
            models.Index(fields=["tenant", "incident_type"], name="idx_ainc_ten_type"),
            models.Index(fields=["tenant", "severity"], name="idx_ainc_ten_sev"),
            models.Index(fields=["tenant", "asset"], name="idx_ainc_ten_asset"),
            models.Index(fields=["tenant", "created_at"], name="idx_ainc_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title} ({self.asset.number if self.asset else 'Asset'})"
