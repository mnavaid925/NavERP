from django.conf import settings
from django.db import models

from apps.quality.models._base import TenantNumbered


class ManagementReviewInput(TenantNumbered):
    NUMBER_PREFIX = "QMRI"

    CATEGORY_CHOICES = [
        ("audit_results", "1. Audit Results (Internal, Supplier, Regulatory)"),
        ("customer_feedback", "2. Customer Feedback & Complaint Trends"),
        ("process_conformity", "3. Process Performance & Product Conformity"),
        ("capa_status", "4. Status of Corrective & Preventive Actions (CAPA)"),
        ("prior_review_followup", "5. Follow-Up Actions from Prior Reviews"),
        ("changes_affecting_qms", "6. Regulatory Changes & QMS Updates"),
        ("supplier_performance", "7. Supplier Performance & AVL Status"),
        ("resources_training", "8. Resource Adequacy & Training Competency"),
        ("risk_management", "9. Risk Management & Hazard Review"),
        ("other_business", "10. Other Quality Matters"),
    ]

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("compiled", "Data Compiled"),
        ("presented", "Presented in Review"),
        ("accepted", "Accepted by Management"),
    ]

    CATEGORY_CSS = {
        "audit_results": "badge-info",
        "customer_feedback": "badge-amber",
        "process_conformity": "badge-info",
        "capa_status": "badge-red",
        "prior_review_followup": "badge-slate",
        "changes_affecting_qms": "badge-amber",
        "supplier_performance": "badge-info",
        "resources_training": "badge-green",
        "risk_management": "badge-red",
        "other_business": "badge-slate",
    }

    STATUS_CSS = {
        "draft": "badge-muted",
        "compiled": "badge-info",
        "presented": "badge-amber",
        "accepted": "badge-green",
    }

    management_review = models.ForeignKey(
        "quality.ManagementReview",
        on_delete=models.CASCADE,
        related_name="inputs",
    )
    agenda_order = models.PositiveIntegerField(default=1)
    title = models.CharField(max_length=255)
    category = models.CharField(max_length=32, choices=CATEGORY_CHOICES, default="audit_results", db_index=True)
    summary_findings = models.TextField()
    metrics_data = models.TextField(blank=True, help_text="Tabular or key metric figures presented")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft", db_index=True)

    presenter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="presented_review_inputs",
    )

    linked_audit = models.ForeignKey(
        "quality.QualityAudit",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="review_inputs",
    )
    linked_capa = models.ForeignKey(
        "quality.CapaInvestigation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="review_inputs",
    )
    linked_complaint = models.ForeignKey(
        "quality.CustomerComplaint",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="review_inputs",
    )
    linked_ncr = models.ForeignKey(
        "quality.NonConformanceReport",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="review_inputs",
    )

    attachments_summary = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["management_review", "agenda_order", "-created_at"]
        verbose_name = "Management Review Input"
        verbose_name_plural = "Management Review Inputs"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="qmri_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "management_review"], name="idx_qmri_ten_mrv"),
            models.Index(fields=["tenant", "category"], name="idx_qmri_ten_cat"),
            models.Index(fields=["tenant", "status"], name="idx_qmri_ten_status"),
            models.Index(fields=["tenant", "-created_at"], name="idx_qmri_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} — #{self.agenda_order} {self.title}"

    @property
    def category_badge_class(self):
        return self.CATEGORY_CSS.get(self.category, "badge-info")

    @property
    def status_badge_class(self):
        return self.STATUS_CSS.get(self.status, "badge-muted")
