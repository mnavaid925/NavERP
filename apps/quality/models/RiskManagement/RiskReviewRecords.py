from django.conf import settings
from django.db import models

from apps.quality.models._base import TenantNumbered


class RiskReviewRecord(TenantNumbered):
    NUMBER_PREFIX = "QRMR"

    REVIEW_TYPE_CHOICES = (
        ("initial_rmr", "Initial Risk Management Report (RMR)"),
        ("periodic_review", "Scheduled Periodic Review"),
        ("design_change_review", "Design Change / ECO Review"),
        ("post_market_surveillance", "Post-Market Surveillance (PMS) Review"),
        ("complaint_trend_trigger", "Complaint Trend Triggered Review"),
        ("ncr_capa_trigger", "NCR / CAPA Triggered Review"),
    )

    STATUS_CHOICES = (
        ("draft", "Draft"),
        ("under_review", "Under Review"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    )

    REVIEW_TYPE_CSS = {
        "initial_rmr": "badge-info",
        "periodic_review": "badge-slate",
        "design_change_review": "badge-amber",
        "post_market_surveillance": "badge-purple",
        "complaint_trend_trigger": "badge-red",
        "ncr_capa_trigger": "badge-amber",
    }

    STATUS_CSS = {
        "draft": "badge-slate",
        "under_review": "badge-amber",
        "approved": "badge-green",
        "rejected": "badge-red",
    }

    plan = models.ForeignKey(
        "quality.RiskManagementPlan",
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    review_title = models.CharField(max_length=255)
    review_type = models.CharField(
        max_length=32,
        choices=REVIEW_TYPE_CHOICES,
        default="periodic_review",
        db_index=True,
    )
    review_date = models.DateField()
    review_period_start = models.DateField(null=True, blank=True)
    review_period_end = models.DateField(null=True, blank=True)

    pms_sources_reviewed = models.TextField(
        blank=True,
        help_text="Complaints, NCRs, CAPAs, adverse event feeds, scientific literature examined",
    )
    new_hazards_identified = models.BooleanField(
        default=False,
        help_text="Revealed previously unrecognized hazards or situations",
    )
    risk_profile_changed = models.BooleanField(
        default=False,
        help_text="Increased occurrence frequency or severity observed",
    )
    overall_residual_risk_reconfirmed = models.BooleanField(
        default=True,
        help_text="Reconfirmed overall residual risk remains acceptable per ISO 14971 Clause 9",
    )
    findings_summary = models.TextField(
        help_text="Detailed review conclusions and regulatory evaluation",
    )
    action_items_required = models.TextField(
        blank=True,
        help_text="Follow-up design changes, DCOs, or CAPAs initiated",
    )

    status = models.CharField(
        max_length=24,
        choices=STATUS_CHOICES,
        default="draft",
        db_index=True,
    )
    lead_reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="conducted_risk_reviews",
    )
    approved_signature = models.ForeignKey(
        "quality.ElectronicSignatureRecord",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_risk_reviews",
        editable=False,
        help_text="21 CFR Part 11 sign-off",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Risk Review Record"
        verbose_name_plural = "Risk Review Records"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="quality_qrmr_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "plan", "review_type"], name="idx_qrmr_ten_pln_type"),
            models.Index(fields=["tenant", "status"], name="idx_qrmr_ten_status"),
            models.Index(fields=["tenant", "review_date"], name="idx_qrmr_ten_date"),
            models.Index(fields=["tenant", "-created_at"], name="idx_qrmr_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} - {self.review_title}"

    @property
    def review_type_badge(self):
        return self.REVIEW_TYPE_CSS.get(self.review_type, "badge-slate")

    @property
    def status_badge(self):
        return self.STATUS_CSS.get(self.status, "badge-slate")
