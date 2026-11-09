from decimal import Decimal

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

from apps.assets.models._base import TenantNumbered


class AssetMaintenanceLog(TenantNumbered):
    """
    Authoritative equipment maintenance history ledger, ISO 14224 failure modes,
    labor wrench hours, parts consumed, and repair cost tracking [AMLG-].
    """

    NUMBER_PREFIX = "AMLG"

    MAINTENANCE_TYPE_CHOICES = [
        ("corrective_repair", "Corrective Repair / Breakdown Fix"),
        ("preventive_service", "Scheduled Preventive Service"),
        ("emergency_breakdown", "Emergency Breakdown Response"),
        ("calibration", "Precision Calibration / Alignment"),
        ("inspection", "Safety & Statutory Inspection"),
        ("overhaul", "Major Overhaul / Component Rebuild"),
    ]

    FAILURE_CODE_CHOICES = [
        ("mechanical_wear", "Mechanical Wear / Fatigue"),
        ("electrical_short", "Electrical Short / Fault"),
        ("hydraulic_leak", "Hydraulic / Pneumatic Leak"),
        ("software_fault", "Software / Sensor Glitch"),
        ("operator_error", "Operator Error / Mishandling"),
        ("corrosion", "Corrosion / Chemical Damage"),
        ("thermal_overload", "Thermal Overload / Overheating"),
        ("lubrication_failure", "Lubrication / Fluid Starvation"),
        ("normal_wear", "Normal Operational Wear"),
        ("other", "Other / Unclassified"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft Service Log"),
        ("in_review", "Under Supervisory Review"),
        ("approved", "Approved / Verified"),
        ("posted", "Posted to General Ledger"),
    ]

    STATUS_CSS = {
        "draft": "badge-slate",
        "in_review": "badge-amber",
        "approved": "badge-info",
        "posted": "badge-green",
    }

    MAINTENANCE_TYPE_CSS = {
        "corrective_repair": "badge-amber",
        "preventive_service": "badge-info",
        "emergency_breakdown": "badge-red",
        "calibration": "badge-slate",
        "inspection": "badge-green",
        "overhaul": "badge-purple",
    }

    FAILURE_CODE_CSS = {
        "mechanical_wear": "badge-amber",
        "electrical_short": "badge-red",
        "hydraulic_leak": "badge-blue",
        "software_fault": "badge-slate",
        "operator_error": "badge-muted",
        "corrosion": "badge-amber",
        "thermal_overload": "badge-red",
        "lubrication_failure": "badge-amber",
        "normal_wear": "badge-slate",
        "other": "badge-muted",
    }

    fixed_asset = models.ForeignKey(
        "accounting.FixedAsset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="maintenance_logs",
        help_text="Financial Fixed Asset repaired",
    )
    operational_asset = models.ForeignKey(
        "scm.Asset",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="maintenance_logs",
        help_text="Operational machinery serviced",
    )
    maintenance_request = models.ForeignKey(
        "assets.AssetMaintenanceRequest",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="maintenance_logs",
        help_text="Originating operator breakdown request or ticket",
    )
    maintenance_schedule = models.ForeignKey(
        "assets.AssetMaintenanceSchedule",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="maintenance_logs",
        help_text="Originating preventive maintenance calendar rule",
    )
    service_contract = models.ForeignKey(
        "assets.AssetServiceContract",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="maintenance_logs",
        help_text="Governing vendor service agreement or warranty",
    )
    work_order = models.ForeignKey(
        "scm.MaintenanceWorkOrder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_maintenance_logs",
        help_text="Linked plant maintenance work order",
    )
    service_date = models.DateField(
        default=timezone.now,
        help_text="Date maintenance work was executed",
    )
    completion_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp work was finalized and signed off",
    )
    maintenance_type = models.CharField(
        max_length=32,
        choices=MAINTENANCE_TYPE_CHOICES,
        default="corrective_repair",
    )
    failure_code = models.CharField(
        max_length=32,
        choices=FAILURE_CODE_CHOICES,
        default="normal_wear",
        help_text="Root cause failure category (ISO 14224 / FMEA)",
    )
    downtime_hours = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Actual equipment downtime hours caused by failure",
    )
    meter_reading = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Asset meter / runtime counter at time of service",
    )
    lead_technician = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="maintenance_logs",
        help_text="Primary technician who performed the work",
    )
    service_vendor = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="maintenance_logs",
        help_text="External service provider / contractor",
    )
    labor_hours = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Total technician wrench hours spent",
    )
    labor_cost = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Internal or outsourced labor charge",
    )
    parts_consumed_summary = models.TextField(
        blank=True,
        help_text="Itemized spare parts, quantities, part numbers used (e.g. 2x Filter #FL-90, 5L Oil 15W-40)",
    )
    parts_cost = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="Total spare parts expenditure",
    )
    vendor_invoice_cost = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
        help_text="External vendor invoice charge (if applicable)",
    )
    total_cost = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
        editable=False,
        help_text="Auto-computed total repair cost (labor + parts + vendor)",
    )
    expense_account = models.ForeignKey(
        "accounting.GLAccount",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="asset_maintenance_expenses",
        help_text="Debit: Repair & Maintenance Expense GL Account",
    )
    root_cause_analysis = models.TextField(
        blank=True,
        help_text="FMEA / 5-Why root cause explanation",
    )
    action_taken = models.TextField(
        help_text="Technical narrative of corrective steps, adjustments, and test runs",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft",
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_asset_maintenance_logs",
    )
    approved_at = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-service_date", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="assets_amlg_ten_num_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_amlg_ten_stat"),
            models.Index(fields=["tenant", "service_date"], name="idx_amlg_ten_date"),
            models.Index(fields=["tenant", "maintenance_type"], name="idx_amlg_ten_type"),
            models.Index(fields=["tenant", "failure_code"], name="idx_amlg_ten_fail"),
            models.Index(fields=["tenant", "fixed_asset"], name="idx_amlg_ten_fa"),
        ]

    def __str__(self):
        return f"{self.number} ({self.service_date}) - {self.get_maintenance_type_display()}"

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def maintenance_type_css(self):
        return self.MAINTENANCE_TYPE_CSS.get(self.maintenance_type, "badge-slate")

    @property
    def failure_code_css(self):
        return self.FAILURE_CODE_CSS.get(self.failure_code, "badge-slate")

    def save(self, *args, **kwargs):
        l_cost = self.labor_cost or Decimal("0.00")
        p_cost = self.parts_cost or Decimal("0.00")
        v_cost = self.vendor_invoice_cost or Decimal("0.00")
        self.total_cost = l_cost + p_cost + v_cost
        super().save(*args, **kwargs)

    def submit_review(self):
        self.status = "in_review"
        self.save(update_fields=["status", "updated_at"])

    def approve(self, user):
        self.status = "approved"
        self.approved_by = user
        self.approved_at = timezone.now()
        self.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])

    def post_to_gl(self, user):
        with transaction.atomic():
            self.status = "posted"
            self.save(update_fields=["status", "updated_at"])
            # Update linked contract visit count if linked
            if self.service_contract:
                self.service_contract.record_visit()
            # Update linked schedule completion if linked
            if self.maintenance_schedule:
                self.maintenance_schedule.record_completion(
                    completion_date=self.service_date,
                    completion_meter=self.meter_reading,
                    user=user,
                )
            # Update linked request if resolved
            if self.maintenance_request and self.maintenance_request.status in ["assigned", "in_progress"]:
                self.maintenance_request.resolve(
                    user=user,
                    summary=f"Repaired via {self.number}: {self.action_taken[:150]}",
                )
