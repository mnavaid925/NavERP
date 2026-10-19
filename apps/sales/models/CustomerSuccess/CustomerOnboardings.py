"""Sales 8.11 — Customer Onboarding model."""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from apps.sales.models._base import TenantNumbered

PLAYBOOK_CHOICES = [
    ("enterprise_high_touch", "Enterprise High-Touch (90 Days)"),
    ("midmarket_standard", "Mid-Market Standard (45 Days)"),
    ("smb_accelerated", "SMB Accelerated (21 Days)"),
    ("tech_touch_automated", "Tech-Touch Automated"),
]

STAGE_CHOICES = [
    ("kickoff", "Kickoff & Alignment"),
    ("architecture_design", "Architecture & Solution Design"),
    ("configuration", "System Configuration"),
    ("data_migration", "Data Migration"),
    ("training", "User & Admin Training"),
    ("uat_testing", "User Acceptance Testing"),
    ("go_live", "Production Go-Live"),
    ("completed", "Completed & Handed to CS"),
    ("stalled", "Stalled / On Hold"),
]

STATUS_CHOICES = [
    ("not_started", "Not Started"),
    ("in_progress", "In Progress"),
    ("on_track", "On Track"),
    ("at_risk", "At Risk"),
    ("blocked", "Blocked"),
    ("completed", "Completed"),
]


class CustomerOnboarding(TenantNumbered):
    NUMBER_PREFIX = "COB"

    account = models.ForeignKey(
        "core.Party",
        on_delete=models.CASCADE,
        related_name="sales_customer_onboardings",
    )
    lead_csm = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="sales_managed_onboardings",
        help_text="Assigned Customer Success Manager or Implementation Consultant",
    )
    sales_order = models.ForeignKey(
        "scm.SalesOrder",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sales_onboardings",
        help_text="Sales order initiating this customer implementation",
    )
    title = models.CharField(
        max_length=160,
        help_text="e.g. Acme Corp Enterprise Platform Launch & Migration",
    )
    playbook_template = models.CharField(
        max_length=30,
        choices=PLAYBOOK_CHOICES,
        default="midmarket_standard",
    )
    stage = models.CharField(
        max_length=25,
        choices=STAGE_CHOICES,
        default="kickoff",
    )
    status = models.CharField(
        max_length=15,
        choices=STATUS_CHOICES,
        default="in_progress",
    )
    kickoff_date = models.DateField(default=timezone.localdate)
    target_go_live_date = models.DateField()
    actual_go_live_date = models.DateField(null=True, blank=True)
    time_to_value_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Elapsed calendar days from kickoff to verified production go-live",
    )
    progress_pct = models.PositiveSmallIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Overall implementation completion percentage (0-100%)",
    )
    executive_sponsor_name = models.CharField(
        max_length=120,
        blank=True,
        help_text="Client executive sponsor name",
    )
    executive_sponsor_email = models.EmailField(
        blank=True,
        help_text="Client executive sponsor email address",
    )
    milestones_config = models.JSONField(
        default=list,
        blank=True,
        help_text="Checkable list of implementation milestones: [{'name': 'x', 'due': 'y', 'done': True}]",
    )
    blockers = models.TextField(
        blank=True,
        help_text="Identified roadblocks, technical impediments, or client delays",
    )
    success_criteria = models.TextField(
        blank=True,
        help_text="Agreed business outcomes and technical acceptance criteria",
    )

    class Meta:
        ordering = ["target_go_live_date", "-kickoff_date"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="sales_cob_tenant_number_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "account", "status"], name="sales_cob_acct_stat_idx"),
            models.Index(fields=["tenant", "stage"], name="sales_cob_stage_idx"),
            models.Index(fields=["tenant", "target_go_live_date"], name="sales_cob_date_idx"),
        ]

    def __str__(self):
        return f"{self.number or 'COB'} - {self.title} ({self.get_stage_display()})"

    def clean(self):
        super().clean()
        if self.account_id and self.tenant_id:
            if self.account.tenant_id != self.tenant_id:
                raise ValidationError({"account": "The selected customer account belongs to another workspace."})

        if self.lead_csm_id and self.tenant_id:
            if getattr(self.lead_csm, "tenant_id", None) != self.tenant_id:
                raise ValidationError({"lead_csm": "The lead CSM must belong to this workspace."})

        if self.sales_order_id and self.tenant_id:
            if self.sales_order.tenant_id != self.tenant_id:
                raise ValidationError({"sales_order": "The linked order belongs to another workspace."})

        if self.target_go_live_date and self.kickoff_date:
            if self.target_go_live_date < self.kickoff_date:
                raise ValidationError({"target_go_live_date": "Target go-live date cannot be earlier than kickoff date."})

        if self.actual_go_live_date and self.kickoff_date:
            if self.actual_go_live_date < self.kickoff_date:
                raise ValidationError({"actual_go_live_date": "Actual go-live date cannot be earlier than kickoff date."})

    def save(self, *args, **kwargs):
        if self.actual_go_live_date and self.kickoff_date:
            self.time_to_value_days = max(0, (self.actual_go_live_date - self.kickoff_date).days)
        super().save(*args, **kwargs)

    @property
    def status_badge_class(self):
        mapping = {
            "completed": "badge-green",
            "on_track": "badge-green",
            "in_progress": "badge-amber",
            "at_risk": "badge-red",
            "blocked": "badge-red",
            "not_started": "badge-slate",
        }
        return mapping.get(self.status, "badge-slate")

    @property
    def stage_badge_class(self):
        mapping = {
            "kickoff": "badge-slate",
            "architecture_design": "badge-info",
            "configuration": "badge-info",
            "data_migration": "badge-info",
            "training": "badge-info",
            "uat_testing": "badge-info",
            "go_live": "badge-green",
            "completed": "badge-green",
            "stalled": "badge-muted",
        }
        return mapping.get(self.stage, "badge-slate")
