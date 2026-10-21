"""Sales 8.14 — ChannelConflict model."""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.sales.models._base import TenantNumbered

CONFLICT_TYPE_CHOICES = [
    ("direct_vs_indirect", "Direct Sales vs. Partner Conflict"),
    ("partner_vs_partner", "Partner vs. Partner Collision"),
    ("territory_overlap", "Territory Boundary Dispute"),
    ("named_account_infringement", "Named Enterprise Account Infringement"),
]

SEVERITY_CHOICES = [
    ("low", "Low"),
    ("medium", "Medium"),
    ("high", "High"),
    ("critical", "Critical (Escalated to CRO)"),
]

CONFLICT_STATUS_CHOICES = [
    ("open", "Open / Investigating"),
    ("in_mediation", "In Active Mediation"),
    ("resolved", "Resolved & Adjudicated"),
    ("dismissed", "Dismissed / Ineligible"),
    ("escalated", "Escalated to Executive"),
]

ESCALATION_LEVEL_CHOICES = [
    ("l1_cam", "Level 1: Channel Account Manager (CAM)"),
    ("l2_channel_chief", "Level 2: Channel Chief / VP Channels"),
    ("l3_executive_cro", "Level 3: Executive Adjudication (CRO)"),
]

RESOLUTION_CHOICES = [
    ("pending", "Pending Determination"),
    ("partner_favored", "Partner Exclusivity Upheld"),
    ("direct_favored", "Direct Sales Precedence Upheld"),
    ("split_commission", "Commission / Revenue Split Imposed"),
    ("co_sell_mandate", "Mandated Joint Co-Sell Agreement"),
    ("deal_cancelled", "Deal Cancelled / Disqualified"),
]


class ChannelConflict(TenantNumbered):
    NUMBER_PREFIX = "CCF"

    conflict_type = models.CharField(
        max_length=35,
        choices=CONFLICT_TYPE_CHOICES,
        default="direct_vs_indirect",
    )
    severity = models.CharField(
        max_length=15,
        choices=SEVERITY_CHOICES,
        default="medium",
    )
    status = models.CharField(
        max_length=20,
        choices=CONFLICT_STATUS_CHOICES,
        default="open",
    )
    deal_registration = models.ForeignKey(
        "sales.DealRegistration",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="channel_conflicts",
        help_text="Disputed partner deal registration",
    )
    opportunity = models.ForeignKey(
        "crm.Opportunity",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_channel_conflicts",
        help_text="Disputed CRM opportunity",
    )
    claimant_partner = models.ForeignKey(
        "core.Party",
        on_delete=models.CASCADE,
        related_name="sales_claimed_conflicts",
        help_text="Partner lodging the channel conflict dispute",
    )
    competing_partner = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_opposing_conflicts",
        help_text="Competing partner firm in partner vs. partner dispute",
    )
    direct_sales_rep = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_direct_conflicts",
        help_text="Direct AE involved in dispute",
    )
    client_account = models.ForeignKey(
        "core.Party",
        on_delete=models.CASCADE,
        related_name="sales_account_conflicts",
        help_text="Contested enterprise customer account",
    )
    territory = models.ForeignKey(
        "crm.Territory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_conflict_territories",
    )
    escalation_level = models.CharField(
        max_length=25,
        choices=ESCALATION_LEVEL_CHOICES,
        default="l1_cam",
    )
    escalated_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_escalated_conflicts",
    )
    resolution_outcome = models.CharField(
        max_length=30,
        choices=RESOLUTION_CHOICES,
        default="pending",
    )
    split_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Revenue or commission split percentage assigned to partner",
    )
    resolution_rationale = models.TextField(blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_adjudicated_conflicts",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="sales_ccf_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="sales_ccf_stat_idx"),
            models.Index(fields=["tenant", "conflict_type"], name="sales_ccf_type_idx"),
            models.Index(fields=["tenant", "claimant_partner"], name="sales_ccf_part_idx"),
            models.Index(fields=["tenant", "escalation_level"], name="sales_ccf_esc_idx"),
        ]

    def __str__(self):
        partner_name = getattr(self.claimant_partner, "name", "Partner")
        client_name = getattr(self.client_account, "name", "Client")
        return f"{self.number} — {self.get_conflict_type_display()} ({partner_name} vs. {client_name})"

    def clean(self):
        super().clean()
        if self.claimant_partner_id and hasattr(self, "tenant_id"):
            if self.claimant_partner.tenant_id != self.tenant_id:
                raise ValidationError({"claimant_partner": "The claimant partner belongs to another workspace."})

        if self.client_account_id and hasattr(self, "tenant_id"):
            if self.client_account.tenant_id != self.tenant_id:
                raise ValidationError({"client_account": "The customer account belongs to another workspace."})

        if self.claimant_partner_id and self.client_account_id and self.claimant_partner_id == self.client_account_id:
            raise ValidationError({"client_account": "The claimant partner cannot lodge a conflict against itself as the customer account."})

        if self.competing_partner_id and hasattr(self, "tenant_id"):
            if self.competing_partner.tenant_id != self.tenant_id:
                raise ValidationError({"competing_partner": "The competing partner belongs to another workspace."})
            if self.competing_partner_id == self.claimant_partner_id:
                raise ValidationError({"competing_partner": "Competing partner cannot be identical to claimant partner."})

        if self.territory_id and hasattr(self, "tenant_id"):
            if self.territory.tenant_id != self.tenant_id:
                raise ValidationError({"territory": "The disputed territory belongs to another workspace."})

        if self.deal_registration_id and hasattr(self, "tenant_id"):
            if self.deal_registration.tenant_id != self.tenant_id:
                raise ValidationError({"deal_registration": "The linked deal registration belongs to another workspace."})

        if self.opportunity_id and hasattr(self, "tenant_id"):
            if self.opportunity.tenant_id != self.tenant_id:
                raise ValidationError({"opportunity": "The linked opportunity belongs to another workspace."})

        if self.status == "resolved":
            if self.resolution_outcome == "pending":
                raise ValidationError({"resolution_outcome": "Resolved conflicts must have a specific adjudication outcome."})
            if not self.resolved_at:
                raise ValidationError({"resolved_at": "Resolved conflicts must have a resolution timestamp."})

    @property
    def status_badge_class(self):
        mapping = {
            "resolved": "badge-green",
            "in_mediation": "badge-info",
            "open": "badge-amber",
            "escalated": "badge-red",
            "dismissed": "badge-slate",
        }
        return mapping.get(self.status, "badge-slate")

    @property
    def severity_badge_class(self):
        mapping = {
            "low": "badge-slate",
            "medium": "badge-info",
            "high": "badge-amber",
            "critical": "badge-red",
        }
        return mapping.get(self.severity, "badge-slate")

    @property
    def escalation_badge_class(self):
        mapping = {
            "l1_cam": "badge-slate",
            "l2_channel_chief": "badge-amber",
            "l3_executive_cro": "badge-red",
        }
        return mapping.get(self.escalation_level, "badge-slate")
