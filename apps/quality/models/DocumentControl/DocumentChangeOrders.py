from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.quality.models._base import TenantNumbered


class DocumentChangeOrder(TenantNumbered):
    NUMBER_PREFIX = "QDCR"

    CHANGE_TYPE_CHOICES = [
        ("new_document", "New Document Creation"),
        ("major_revision", "Major Revision"),
        ("minor_revision", "Minor Revision"),
        ("obsoletion", "Document Obsoletion"),
        ("emergency_change", "Emergency Urgent Change"),
    ]

    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("standard", "Standard"),
        ("high", "High"),
        ("critical_urgent", "Critical / Urgent"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted for Review"),
        ("in_assessment", "Impact Assessment"),
        ("ccb_review", "CCB Review"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("implemented", "Implemented & Closed"),
        ("cancelled", "Cancelled"),
    ]

    CCB_DECISION_CHOICES = [
        ("pending", "Pending CCB Review"),
        ("approved", "CCB Approved"),
        ("rejected", "CCB Rejected"),
        ("waived", "CCB Review Waived"),
    ]

    STATUS_CSS = {
        "draft": "badge-slate",
        "submitted": "badge-info",
        "in_assessment": "badge-amber",
        "ccb_review": "badge-info",
        "approved": "badge-green",
        "rejected": "badge-red",
        "implemented": "badge-green",
        "cancelled": "badge-muted",
    }

    PRIORITY_CSS = {
        "low": "badge-slate",
        "standard": "badge-info",
        "high": "badge-amber",
        "critical_urgent": "badge-red",
    }

    CCB_DECISION_CSS = {
        "pending": "badge-amber",
        "approved": "badge-green",
        "rejected": "badge-red",
        "waived": "badge-slate",
    }

    title = models.CharField(max_length=255)
    change_type = models.CharField(max_length=28, choices=CHANGE_TYPE_CHOICES, default="major_revision")
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default="standard")
    document = models.ForeignKey(
        "quality.ControlledDocument", on_delete=models.CASCADE, related_name="change_orders"
    )
    target_revision = models.CharField(max_length=20, default="1.1")
    reason_for_change = models.TextField(help_text="Regulatory / operational justification for this change.")
    change_description = models.TextField(help_text="Detailed summary of additions, modifications, or deletions.")
    regulatory_impact = models.BooleanField(
        default=False, help_text="Does this change require regulatory notification or filings (e.g. FDA 510(k), CE mark)?"
    )
    training_required = models.BooleanField(
        default=True, help_text="Does this change trigger mandatory read-and-acknowledge retraining?"
    )
    impact_assessment = models.TextField(
        blank=True, help_text="Scope analysis of affected processes, equipment, and validation."
    )
    status = models.CharField(max_length=24, choices=STATUS_CHOICES, default="draft", db_index=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="requested_change_orders"
    )
    target_effective_date = models.DateField(null=True, blank=True)
    ccb_decision = models.CharField(max_length=20, choices=CCB_DECISION_CHOICES, default="pending")
    ccb_decision_date = models.DateField(null=True, blank=True)
    ccb_decision_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="ccb_decisions"
    )
    closure_notes = models.TextField(blank=True)
    closed_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Document Change Order"
        verbose_name_plural = "Document Change Orders"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="quality_qdcr_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_qdcr_ten_status"),
            models.Index(fields=["tenant", "document", "status"], name="idx_qdcr_ten_doc_stat"),
            models.Index(fields=["tenant", "requested_by"], name="idx_qdcr_ten_reqby"),
            models.Index(fields=["tenant", "change_type"], name="idx_qdcr_ten_type"),
            models.Index(fields=["tenant", "priority"], name="idx_qdcr_ten_prio"),
        ]

    def __str__(self):
        return f"{self.number} - {self.title}"
