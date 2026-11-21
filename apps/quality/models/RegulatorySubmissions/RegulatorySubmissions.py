from django.conf import settings
from django.db import models
from django.db.models import Index, UniqueConstraint
from django.utils import timezone

from apps.quality.models._base import TenantNumbered


class RegulatorySubmission(TenantNumbered):
    NUMBER_PREFIX = "QSUB"

    SUBMISSION_TYPE_CHOICES = [
        ("510k", "510(k) Premarket Notification"),
        ("pma", "Premarket Approval (PMA)"),
        ("de_novo", "De Novo Classification"),
        ("ce_tech_file", "CE Technical Documentation (MDR/IVDR)"),
        ("hde", "Humanitarian Device Exemption (HDE)"),
        ("ind", "Investigational New Drug (IND)"),
        ("nda", "New Drug Application (NDA)"),
        ("health_canada", "Health Canada Medical Device Licence (MDL)"),
        ("pmda", "Japan PMDA Shonin / Ninsho"),
        ("nmpa", "China NMPA Registration"),
        ("other", "Other Health Authority Dossier"),
    ]

    DEVICE_CLASS_CHOICES = [
        ("class_i", "Class I / Exempt"),
        ("class_iia", "Class IIa"),
        ("class_iib", "Class IIb"),
        ("class_iii", "Class III / High Risk"),
        ("unclassified", "Unclassified / Combo"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft / Scoping"),
        ("authoring", "Authoring & Compilation"),
        ("internal_review", "Internal QA/RA Review"),
        ("submitted", "Submitted to Authority"),
        ("under_review", "Under Authority Review"),
        ("deficiency_response", "Deficiency / AI Response"),
        ("approved_cleared", "Approved / Cleared"),
        ("rejected", "Rejected / Not Approvable"),
        ("withdrawn", "Withdrawn"),
    ]

    STATUS_CSS = {
        "draft": "badge-slate",
        "authoring": "badge-info",
        "internal_review": "badge-amber",
        "submitted": "badge-info",
        "under_review": "badge-info",
        "deficiency_response": "badge-amber",
        "approved_cleared": "badge-green",
        "rejected": "badge-red",
        "withdrawn": "badge-muted",
    }

    title = models.CharField(max_length=255)
    submission_type = models.CharField(
        max_length=30, choices=SUBMISSION_TYPE_CHOICES, default="510k"
    )
    target_authority = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="regulatory_submissions",
    )
    org_unit = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="regulatory_submissions",
    )
    product_name = models.CharField(max_length=255)
    product_code = models.CharField(max_length=100, blank=True)
    device_class = models.CharField(
        max_length=20, choices=DEVICE_CLASS_CHOICES, default="class_iib", db_index=True
    )
    application_number = models.CharField(
        max_length=100, blank=True, db_index=True, help_text="e.g. K230123, P210045, MDR-TF-008"
    )
    status = models.CharField(
        max_length=30, choices=STATUS_CHOICES, default="draft"
    )
    planned_submission_date = models.DateField(null=True, blank=True)
    actual_submission_date = models.DateField(null=True, blank=True, db_index=True)
    decision_date = models.DateField(null=True, blank=True)
    lead_author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="authored_submissions",
    )
    qa_approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_submissions",
    )
    technical_dossier = models.ForeignKey(
        "quality.ControlledDocument",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="regulatory_submissions",
    )
    technical_sections_summary = models.TextField(
        blank=True, help_text="Summary of technical modules, GSPR checklist, bench testing, biocompatibility"
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at", "number"]
        verbose_name = "Regulatory Submission"
        verbose_name_plural = "Regulatory Submissions"
        constraints = [
            UniqueConstraint(fields=["tenant", "number"], name="quality_qsub_ten_num_uniq"),
        ]
        indexes = [
            Index(fields=["tenant", "-created_at"], name="idx_qsub_ten_created"),
            Index(fields=["tenant", "status"], name="idx_qsub_ten_status"),
            Index(fields=["tenant", "submission_type"], name="idx_qsub_ten_subtype"),
            Index(fields=["tenant", "product_code"], name="idx_qsub_ten_prod"),
        ]

    def __str__(self):
        return f"{self.number} — {self.title}"

    @property
    def is_submitted(self):
        return self.status in ["submitted", "under_review", "deficiency_response", "approved_cleared"]

    @property
    def is_approved(self):
        return self.status == "approved_cleared"

    @property
    def days_under_review(self):
        if not self.actual_submission_date:
            return 0
        end = self.decision_date or timezone.now().date()
        return (end - self.actual_submission_date).days

    @property
    def status_css(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")
