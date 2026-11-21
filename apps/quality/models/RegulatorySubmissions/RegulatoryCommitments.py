from django.conf import settings
from django.db import models
from django.db.models import Index, UniqueConstraint
from django.utils import timezone

from apps.quality.models._base import TenantNumbered


class RegulatoryCommitment(TenantNumbered):
    NUMBER_PREFIX = "QCOM"

    COMMITMENT_TYPE_CHOICES = [
        ("agency_deficiency", "Deficiency / Additional Information Request"),
        ("post_approval_study", "Post-Approval Clinical / Performance Study"),
        ("annual_report", "Annual Status Report / Periodic Summary"),
        ("labeling_update", "Mandated Labeling / IFU Revision"),
        ("stability_monitoring", "Ongoing Stability / Shelf-Life Study"),
        ("inspection_483_response", "Inspection Observation (483) Response"),
        ("pmcf_commitment", "Post-Market Clinical Follow-up Commitment"),
        ("other", "Other Regulatory Commitment"),
    ]

    STATUS_CHOICES = [
        ("open", "Open / Assigned"),
        ("in_progress", "In Progress / Authoring"),
        ("submitted_to_agency", "Submitted to Agency"),
        ("agency_accepted", "Agency Accepted / Fulfilled"),
        ("overdue", "Overdue"),
        ("waived", "Waived / Superseded"),
    ]

    STATUS_CSS = {
        "open": "badge-info",
        "in_progress": "badge-amber",
        "submitted_to_agency": "badge-info",
        "agency_accepted": "badge-green",
        "overdue": "badge-red",
        "waived": "badge-slate",
    }

    title = models.CharField(max_length=255)
    commitment_type = models.CharField(
        max_length=30, choices=COMMITMENT_TYPE_CHOICES, default="agency_deficiency"
    )
    regulatory_agency = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="regulatory_commitments",
    )
    linked_submission = models.ForeignKey(
        "quality.RegulatorySubmission",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="regulatory_commitments",
    )
    linked_registration = models.ForeignKey(
        "quality.ProductRegistration",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="regulatory_commitments",
    )
    linked_inspection = models.ForeignKey(
        "quality.RegulatoryInspectionHost",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="regulatory_commitments",
    )
    agency_reference_number = models.CharField(
        max_length=100, blank=True, help_text="Deficiency item number, 483 item number, or tracking ID"
    )
    correspondence_date = models.DateField(null=True, blank=True)
    commitment_description = models.TextField()
    responsible_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="owned_commitments",
    )
    due_date = models.DateField()
    completion_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=25, choices=STATUS_CHOICES, default="open"
    )
    verification_method = models.TextField(
        blank=True, help_text="Test data, protocol, labeling file, or formal response package"
    )
    agency_feedback = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["due_date", "number"]
        verbose_name = "Regulatory Commitment"
        verbose_name_plural = "Regulatory Commitments"
        constraints = [
            UniqueConstraint(fields=["tenant", "number"], name="quality_qcom_ten_num_uniq"),
        ]
        indexes = [
            Index(fields=["tenant", "status"], name="idx_qcom_ten_status"),
            Index(fields=["tenant", "due_date"], name="idx_qcom_ten_due"),
            Index(fields=["tenant", "commitment_type"], name="idx_qcom_ten_type"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title}"

    @property
    def is_overdue(self):
        if self.status in ["open", "in_progress"] and self.due_date < timezone.now().date():
            return True
        return self.status == "overdue"

    @property
    def days_remaining(self):
        return (self.due_date - timezone.now().date()).days

    @property
    def status_css(self):
        if self.is_overdue and self.status in ["open", "in_progress"]:
            return "badge-red"
        return self.STATUS_CSS.get(self.status, "badge-slate")
