from django.conf import settings
from django.db import models

from apps.quality.models._base import TenantNumbered


class FieldAction(TenantNumbered):
    NUMBER_PREFIX = "QFMA"

    ACTION_TYPE_CHOICES = (
        ("recall_removal", "Product Recall (Physical Removal / Return)"),
        ("fsca_safety_notice", "Field Safety Corrective Action (FSCA / Notice)"),
        ("field_correction_rework", "Field Correction / Software Patch / On-site Rework"),
        ("safety_advisory_alert", "Safety Advisory / Updated Instructions for Use"),
        ("market_withdrawal", "Market Withdrawal (Non-Violative Commercial)"),
    )

    RECALL_CLASS_CHOICES = (
        ("class_i_critical", "Class I Recall (High Risk: Death / Serious Injury)"),
        ("class_ii_moderate", "Class II Recall (Moderate Risk: Temporary / Reversible)"),
        ("class_iii_minor", "Class III Recall (Low Risk: Unlikely Health Consequence)"),
        ("fsca_safety_alert", "Field Safety Alert (Advisory Only)"),
        ("not_classified", "Unclassified / Initial Assessment"),
    )

    ACTION_STATUS_CHOICES = (
        ("planning", "Strategy & Health Hazard Evaluation"),
        ("regulatory_consultation", "Agency Notification & Recall Strategy Review"),
        ("notifications_dispatched", "Consignee Notifications Dispatched"),
        ("quarantine_in_progress", "Field Quarantine & Recovery In Progress"),
        ("reconciliation_complete", "Reconciliation Complete (Audit In Progress)"),
        ("closed_terminated", "Recall Terminated & Agency Concurred"),
        ("cancelled", "Cancelled / Abandoned"),
    )

    ACTION_TYPE_CSS = {
        "recall_removal": "badge-red",
        "fsca_safety_notice": "badge-amber",
        "field_correction_rework": "badge-info",
        "safety_advisory_alert": "badge-slate",
        "market_withdrawal": "badge-muted",
    }

    RECALL_CLASS_CSS = {
        "class_i_critical": "badge-red",
        "class_ii_moderate": "badge-amber",
        "class_iii_minor": "badge-info",
        "fsca_safety_alert": "badge-amber",
        "not_classified": "badge-slate",
    }

    STATUS_CSS = {
        "planning": "badge-slate",
        "regulatory_consultation": "badge-amber",
        "notifications_dispatched": "badge-info",
        "quarantine_in_progress": "badge-amber",
        "reconciliation_complete": "badge-info",
        "closed_terminated": "badge-green",
        "cancelled": "badge-muted",
    }

    title = models.CharField(max_length=255, help_text="Recall / Field Action title")
    action_type = models.CharField(max_length=32, choices=ACTION_TYPE_CHOICES, default="recall_removal", db_index=True)
    recall_class = models.CharField(max_length=32, choices=RECALL_CLASS_CHOICES, default="not_classified", db_index=True)
    initiating_complaint = models.ForeignKey(
        "quality.CustomerComplaint",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="field_actions",
        help_text="Triggering customer complaint",
    )
    coordinator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="coordinated_field_actions",
    )
    initiation_date = models.DateField(db_index=True, help_text="Official initiation date of the field action")
    status = models.CharField(max_length=30, choices=ACTION_STATUS_CHOICES, default="planning", db_index=True)

    affected_product_code = models.CharField(max_length=100, db_index=True, help_text="Affected item / model catalog code")
    affected_product_name = models.CharField(max_length=255, help_text="Commercial product name")
    affected_lot_numbers = models.TextField(help_text="Comma-separated or list of recalled batch/lot numbers")
    distribution_start_date = models.DateField(null=True, blank=True, help_text="Earliest shipment date of affected lots")
    distribution_end_date = models.DateField(null=True, blank=True, help_text="Latest shipment date of affected lots")

    reason_for_action = models.TextField(help_text="Statement of defect, failure mode, and health hazard justification")
    hhe_summary = models.TextField(blank=True, help_text="Clinical Health Hazard Evaluation risk assessment rationale")
    fsn_document = models.ForeignKey(
        "quality.ControlledDocument",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="field_actions",
        help_text="Controlled Field Safety Notice customer communication letter",
    )

    total_units_distributed = models.PositiveIntegerField(default=0, help_text="Total population of affected units shipped to commerce")
    consignees_targeted = models.PositiveIntegerField(default=0, help_text="Total number of accounts / hospitals receiving notification")
    consignees_notified = models.PositiveIntegerField(default=0, help_text="Number of consignees successfully delivered notification")
    consignees_responded = models.PositiveIntegerField(default=0, help_text="Number of consignees returning acknowledgment certificates")
    units_quarantined_field = models.PositiveIntegerField(default=0, help_text="Units held in customer quarantine awaiting disposition")
    units_recovered_destroyed = models.PositiveIntegerField(default=0, help_text="Units physically returned to factory or certified destroyed")

    regulatory_agency_notified = models.CharField(max_length=100, blank=True, help_text="e.g. FDA CDRH Recall Operations, BfArM, MHRA")
    regulatory_recall_number = models.CharField(
        max_length=100,
        blank=True,
        help_text="Agency designated recall classification identifier (e.g. FDA Z-####-2026)",
    )
    agency_notification_date = models.DateField(null=True, blank=True)
    termination_date = models.DateField(null=True, blank=True, help_text="Date regulatory authority formally concurred with recall closure")
    closure_summary = models.TextField(blank=True, help_text="Final effectiveness audit and reconciliation summary")

    class Meta:
        ordering = ["-initiation_date", "-created_at"]
        verbose_name = "Field Action & Recall"
        verbose_name_plural = "Field Actions & Recalls"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="quality_qfma_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_qfma_ten_status"),
            models.Index(fields=["tenant", "action_type"], name="idx_qfma_ten_atype"),
            models.Index(fields=["tenant", "recall_class"], name="idx_qfma_ten_rclass"),
            models.Index(fields=["tenant", "affected_product_code"], name="idx_qfma_ten_pcode"),
            models.Index(fields=["tenant", "initiation_date"], name="idx_qfma_ten_idate"),
            models.Index(fields=["tenant", "-created_at"], name="idx_qfma_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} - {self.title}"

    @property
    def reconciliation_rate(self):
        if not self.total_units_distributed:
            return 0
        accounted = self.units_quarantined_field + self.units_recovered_destroyed
        return min(100, int((accounted / self.total_units_distributed) * 100))

    @property
    def consignee_response_rate(self):
        if not self.consignees_targeted:
            return 0
        return min(100, int((self.consignees_responded / self.consignees_targeted) * 100))

    @property
    def is_active(self):
        return self.status not in ["closed_terminated", "cancelled"]
