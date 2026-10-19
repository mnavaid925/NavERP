"""Sales 8.11 — Customer Business Review (QBR/EBR) model."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.sales.models._base import TenantNumbered

REVIEW_PERIOD_CHOICES = [
    ("q1", "Q1 Review"),
    ("q2", "Q2 Review"),
    ("q3", "Q3 Review"),
    ("q4", "Q4 Review"),
    ("mid_year", "Mid-Year Review"),
    ("annual", "Annual Executive Review"),
]

STATUS_CHOICES = [
    ("scheduled", "Scheduled"),
    ("materials_prepared", "Materials Prepared"),
    ("conducted", "Conducted / Completed"),
    ("follow_up_sent", "Follow-Up Action Items Sent"),
    ("cancelled", "Cancelled"),
]

TEMPLATE_CHOICES = [
    ("executive_value", "Executive Value & ROI Review"),
    ("technical_roadmap", "Technical Architecture & Roadmap"),
    ("renewal_alignment", "Renewal & Partnership Alignment"),
    ("operational_cadence", "Standard Operational Cadence"),
]

CASE_STUDY_CHOICES = [
    ("none", "Not Candidate"),
    ("identified", "Candidate Identified"),
    ("interview_scheduled", "Interview Scheduled"),
    ("drafting", "Drafting Case Study"),
    ("approved", "Client Approved"),
    ("published", "Published"),
]


class CustomerBusinessReview(TenantNumbered):
    NUMBER_PREFIX = "QBR"

    account = models.ForeignKey(
        "core.Party",
        on_delete=models.CASCADE,
        related_name="sales_customer_business_reviews",
    )
    lead_csm = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="sales_led_qbrs",
        help_text="Customer Success Manager hosting the review",
    )
    account_plan = models.ForeignKey(
        "sales.AccountPlan",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sales_qbr_reviews",
        help_text="Strategic account plan aligning quarterly goals and whitespace",
    )
    title = models.CharField(
        max_length=160,
        help_text="e.g. Acme Corp Q3 2026 Executive Business Review",
    )
    review_period = models.CharField(
        max_length=20,
        choices=REVIEW_PERIOD_CHOICES,
        default="q1",
    )
    review_year = models.PositiveIntegerField(
        default=2026,
    )
    scheduled_date = models.DateField()
    completed_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date review was actually conducted",
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="scheduled",
    )
    template_type = models.CharField(
        max_length=30,
        choices=TEMPLATE_CHOICES,
        default="executive_value",
    )
    executive_sponsor_attended = models.BooleanField(
        default=False,
        help_text="Confirmed presence of customer executive sponsor",
    )
    client_attendees = models.TextField(
        blank=True,
        help_text="Customer stakeholders and executives attending",
    )
    internal_attendees = models.TextField(
        blank=True,
        help_text="Internal account team and executive sponsor attendees",
    )
    health_score_at_review = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Snapshot of account health score at the time of review",
    )
    key_achievements = models.TextField(
        blank=True,
        help_text="Quantified business value delivered and milestones reached",
    )
    challenges_and_risks = models.TextField(
        blank=True,
        help_text="Open service issues, feature gaps, or commercial risks raised",
    )
    action_items = models.JSONField(
        default=list,
        blank=True,
        help_text="Agreed post-review actions: [{'task': 'x', 'owner': 'y', 'due': 'z', 'status': 'open'}]",
    )
    is_referenceable = models.BooleanField(
        default=False,
        help_text="Customer agreed to serve as verified commercial reference",
    )
    reference_types_permitted = models.JSONField(
        default=list,
        blank=True,
        help_text="Permitted reference motions: ['calls', 'site_visits', 'quotes', 'case_study']",
    )
    case_study_status = models.CharField(
        max_length=25,
        choices=CASE_STUDY_CHOICES,
        default="none",
    )
    testimonial_quote = models.TextField(
        blank=True,
        help_text="Verified customer quote approved for sales and marketing collateral",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-scheduled_date", "-review_year"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="sales_qbr_tenant_number_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "account", "status"], name="sales_qbr_acct_stat_idx"),
            models.Index(fields=["tenant", "status"], name="sales_qbr_ten_stat_idx"),
            models.Index(fields=["tenant", "scheduled_date"], name="sales_qbr_date_idx"),
            models.Index(fields=["tenant", "is_referenceable"], name="sales_qbr_ref_idx"),
        ]

    def __str__(self):
        return f"{self.number or 'QBR'} - {self.title} ({self.get_status_display()})"

    def clean(self):
        super().clean()
        if self.account_id and self.tenant_id:
            if self.account.tenant_id != self.tenant_id:
                raise ValidationError({"account": "The selected customer account belongs to another workspace."})

        if self.lead_csm_id and self.tenant_id:
            if getattr(self.lead_csm, "tenant_id", None) != self.tenant_id:
                raise ValidationError({"lead_csm": "The lead CSM must belong to this workspace."})

        if self.account_plan_id and self.tenant_id:
            if self.account_plan.tenant_id != self.tenant_id:
                raise ValidationError({"account_plan": "The linked account plan belongs to another workspace."})

        if self.completed_date and self.status == "scheduled":
            raise ValidationError({"status": "A review with a recorded completion date cannot be in Scheduled status."})

    @property
    def status_badge_class(self):
        mapping = {
            "conducted": "badge-green",
            "follow_up_sent": "badge-green",
            "scheduled": "badge-info",
            "materials_prepared": "badge-amber",
            "cancelled": "badge-red",
        }
        return mapping.get(self.status, "badge-slate")

    @property
    def case_study_badge_class(self):
        mapping = {
            "published": "badge-green",
            "approved": "badge-green",
            "drafting": "badge-amber",
            "interview_scheduled": "badge-amber",
            "identified": "badge-info",
            "none": "badge-slate",
        }
        return mapping.get(self.case_study_status, "badge-slate")
