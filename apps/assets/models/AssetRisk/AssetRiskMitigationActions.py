from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.assets.models._base import TenantNumbered


class AssetRiskMitigationAction(TenantNumbered):
    """
    Asset Risk Mitigation Action [ARMA-].
    Tracks actionable risk treatment tasks, contingency plans, alternative supplier planning
    for geopolitical / supply chain resilience, spare buffers, and post-implementation effectiveness evaluation.
    Aligned with ISO 31000 Risk Treatment.
    """

    NUMBER_PREFIX = "ARMA"

    ACTION_TYPE_CHOICES = [
        ("engineering_control", "Engineering Design & Safeguard Control"),
        ("redundancy_addition", "Redundancy & Backup System Addition"),
        ("firmware_security_patch", "Firmware Patch / OT Cyber Hardening"),
        ("insurance_transfer", "Insurance Coverage & Risk Transfer"),
        ("supplier_diversification", "Alternative Supplier / Dual Sourcing"),
        ("spare_parts_buffer", "Critical Spare Parts Buffer Inventory"),
        ("procedure_training", "Standard Operating Procedure & Training"),
        ("preventive_inspection", "Enhanced PM & Predictive Telemetry"),
    ]

    PRIORITY_CHOICES = [
        ("critical", "Critical (Immediate Action)"),
        ("high", "High Priority"),
        ("medium", "Medium Priority"),
        ("low", "Low Priority"),
    ]

    STATUS_CHOICES = [
        ("planned", "Action Planned"),
        ("in_progress", "Implementation In Progress"),
        ("completed", "Completed (Pending Validation)"),
        ("verified_effective", "Verified Effective (Closed)"),
        ("deferred", "Deferred / Rescheduled"),
        ("cancelled", "Cancelled"),
    ]

    EFFECTIVENESS_CHOICES = [
        ("pending_evaluation", "Pending Evaluation"),
        ("highly_effective", "Highly Effective (Residual Risk Reduced)"),
        ("partially_effective", "Partially Effective (Minor Residual Risk)"),
        ("ineffective", "Ineffective (Requires Further Action)"),
    ]

    STATUS_CSS = {
        "planned": "badge-slate",
        "in_progress": "badge-amber",
        "completed": "badge-info",
        "verified_effective": "badge-green",
        "deferred": "badge-muted",
        "cancelled": "badge-red",
    }

    PRIORITY_CSS = {
        "critical": "badge-red",
        "high": "badge-amber",
        "medium": "badge-info",
        "low": "badge-slate",
    }

    ACTION_TYPE_CSS = {
        "engineering_control": "badge-info",
        "redundancy_addition": "badge-purple",
        "firmware_security_patch": "badge-amber",
        "insurance_transfer": "badge-slate",
        "supplier_diversification": "badge-green",
        "spare_parts_buffer": "badge-info",
        "procedure_training": "badge-slate",
        "preventive_inspection": "badge-info",
    }

    EFFECTIVENESS_CSS = {
        "pending_evaluation": "badge-slate",
        "highly_effective": "badge-green",
        "partially_effective": "badge-amber",
        "ineffective": "badge-red",
    }

    tenant = models.ForeignKey(
        "core.Tenant",
        on_delete=models.CASCADE,
        related_name="asset_mitigation_actions",
    )
    title = models.CharField(
        max_length=255,
        help_text="Remediation task title",
    )
    risk = models.ForeignKey(
        "assets.AssetRiskRegister",
        on_delete=models.CASCADE,
        related_name="mitigation_actions",
        help_text="Parent asset risk being mitigated",
    )
    action_type = models.CharField(
        max_length=30,
        choices=ACTION_TYPE_CHOICES,
        default="engineering_control",
    )
    description = models.TextField(
        blank=True,
        help_text="Detailed implementation scope and technical deliverables",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_asset_mitigations",
        help_text="Assigned engineer or specialist",
    )
    alternative_supplier = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="risk_alternative_suppliers",
        help_text="Alternative vendor for dual-sourcing / supply resilience",
    )
    target_completion_date = models.DateField(
        help_text="Required remediation deadline",
    )
    actual_completion_date = models.DateField(
        null=True,
        blank=True,
    )
    estimated_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    actual_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    priority = models.CharField(
        max_length=20,
        choices=PRIORITY_CHOICES,
        default="medium",
    )
    status = models.CharField(
        max_length=24,
        choices=STATUS_CHOICES,
        default="planned",
    )
    verification_notes = models.TextField(
        blank=True,
        help_text="Post-implementation verification observations",
    )
    effectiveness_rating = models.CharField(
        max_length=24,
        choices=EFFECTIVENESS_CHOICES,
        default="pending_evaluation",
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="assets_arma_ten_num_uniq",
            )
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_arma_ten_stat"),
            models.Index(fields=["tenant", "priority"], name="idx_arma_ten_prio"),
            models.Index(fields=["tenant", "action_type"], name="idx_arma_ten_type"),
            models.Index(fields=["tenant", "risk"], name="idx_arma_ten_rsk"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title} ({self.get_status_display()})"

    @property
    def status_badge_class(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def priority_badge_class(self):
        return self.PRIORITY_CSS.get(self.priority, "badge-slate")

    @property
    def action_type_badge_class(self):
        return self.ACTION_TYPE_CSS.get(self.action_type, "badge-slate")

    @property
    def effectiveness_badge_class(self):
        return self.EFFECTIVENESS_CSS.get(self.effectiveness_rating, "badge-slate")
