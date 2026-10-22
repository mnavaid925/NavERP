"""Sales 8.12 — Sales Analytics & Intelligence: Win/Loss Debrief model.

OWNERSHIP RULING (L36/L37): 8.12 declares NO win/loss-reason table and NO
opportunity-outcome table. It EXTENDS the Sales 8.2 spine
(``sales.WinLossReason`` / ``sales.OpportunityOutcome``) by FK and adds only the
*debrief* record — the qualitative, human-written account of why a deal was won
or lost that the numeric spine cannot carry.

``sales.OpportunityOutcome`` is **append-only** (its ``save()``/``delete()``
raise once the row exists), so ``outcome`` is ``PROTECT`` — never ``CASCADE``:
a cascade would try to delete an immutable row.
"""
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models
from django.utils import timezone

from apps.sales.models._base import TenantNumbered

INTERVIEW_CHANNEL_CHOICES = [
    ("interview", "Interview"),
    ("survey", "Survey"),
    ("email_review", "Email Review"),
    ("internal_debrief", "Internal Debrief"),
    ("analysis", "Desk Analysis"),
]

FEEDBACK_TEAM_CHOICES = [
    ("product", "Product"),
    ("marketing", "Marketing"),
    ("sales", "Sales"),
    ("finance", "Finance"),
    ("operations", "Operations"),
    ("other", "Other"),
]

DEBRIEF_STATUS_CHOICES = [
    ("draft", "Draft"),
    ("submitted", "Submitted"),
    ("shared", "Shared with Team"),
    ("actioned", "Actioned"),
    ("closed", "Closed"),
]


class WinLossDebrief(TenantNumbered):
    """A structured win/loss debrief for one closed (or closing) opportunity.

    One debrief per opportunity per tenant (enforced by a unique constraint).
    ``decision_drivers`` holds the recurring reasons the buyer gave, each with a
    sentiment and a 1-5 weight, so the win/loss console can aggregate the
    qualitative signal without a second aggregation engine.
    """

    NUMBER_PREFIX = "WLA"

    opportunity = models.ForeignKey(
        "crm.Opportunity",
        on_delete=models.PROTECT,
        related_name="sales_win_loss_debriefs",
    )
    outcome = models.ForeignKey(
        "sales.OpportunityOutcome",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="sales_win_loss_debriefs",
    )
    primary_reason = models.ForeignKey(
        "sales.WinLossReason",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="sales_win_loss_debriefs",
    )
    account = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_win_loss_debrief_accounts",
    )
    interviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_win_loss_debrief_interviewers",
    )
    action_owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_win_loss_debrief_action_owners",
    )
    communication_log = models.ForeignKey(
        "crm.CommunicationLog",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_win_loss_debriefs",
    )
    debriefed_on = models.DateField(default=timezone.localdate)
    interview_channel = models.CharField(
        max_length=20,
        choices=INTERVIEW_CHANNEL_CHOICES,
        default="interview",
    )
    decision_drivers = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "List of decision drivers, e.g. "
            '[{"driver": "price", "sentiment": "negative", "weight": 4, "quote": "..."}]'
        ),
    )
    buyer_quote = models.TextField(blank=True)
    counterfactual = models.TextField(blank=True)
    feedback_team = models.CharField(
        max_length=20,
        choices=FEEDBACK_TEAM_CHOICES,
        default="sales",
    )
    action_items = models.TextField(blank=True)
    actioned_on = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=12,
        choices=DEBRIEF_STATUS_CHOICES,
        default="draft",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-debriefed_on", "-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="sales_wla_tenant_number_uniq"),
            models.UniqueConstraint(fields=["tenant", "opportunity"], name="sales_wla_tenant_opp_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="sales_wla_tenant_status_idx"),
            models.Index(fields=["tenant", "feedback_team"], name="sales_wla_tenant_fb_idx"),
            models.Index(fields=["tenant", "-debriefed_on"], name="sales_wla_ten_deb_idx"),
            models.Index(fields=["tenant", "interview_channel"], name="sales_wla_ten_chan_idx"),
        ]

    def __str__(self):
        try:
            opportunity = self.opportunity if self.opportunity_id else None
        except ObjectDoesNotExist:
            opportunity = None
        return f"{self.number or 'WLA'} · {opportunity or '—'}"

    def _relation_belongs_to_tenant(self, field_name):
        """True when the FK at ``field_name`` points at a row of this tenant.

        Copied from ``apps/sales/models/OpportunityOutcomes/OpportunityOutcomes.py``
        — a DB existence probe, so a cross-tenant pick is rejected without
        dereferencing the (foreign) object.
        """
        relation_id = getattr(self, f"{field_name}_id", None)
        if not self.tenant_id or not relation_id:
            return True
        field = self._meta.get_field(field_name)
        related_model = field.remote_field.model
        return related_model._default_manager.filter(
            pk=relation_id,
            tenant_id=self.tenant_id,
        ).exists()

    def clean(self):
        super().clean()
        if not self.tenant_id:
            return
        for field_name, message in (
            ("opportunity", "The opportunity must belong to this workspace."),
            ("outcome", "Choose an outcome from this workspace."),
            ("primary_reason", "Choose a win/loss reason from this workspace."),
            ("account", "The selected account belongs to another workspace."),
            ("interviewer", "The interviewer must belong to this workspace."),
            ("action_owner", "The action owner must belong to this workspace."),
            ("communication_log", "The communication log must belong to this workspace."),
        ):
            if not self._relation_belongs_to_tenant(field_name):
                raise ValidationError({field_name: message})

        if self.outcome_id and self.opportunity_id:
            try:
                outcome = self.outcome
            except ObjectDoesNotExist:
                outcome = None
            if outcome is not None and outcome.opportunity_id != self.opportunity_id:
                raise ValidationError(
                    {"outcome": "The outcome must belong to the selected opportunity."}
                )

    @property
    def status_badge_class(self):
        mapping = {
            "draft": "badge-muted",
            "submitted": "badge-info",
            "shared": "badge-slate",
            "actioned": "badge-amber",
            "closed": "badge-green",
        }
        return mapping.get(self.status, "badge-slate")

    @property
    def channel_badge_class(self):
        mapping = {
            "interview": "badge-info",
            "survey": "badge-slate",
            "email_review": "badge-muted",
            "internal_debrief": "badge-slate",
            "analysis": "badge-slate",
        }
        return mapping.get(self.interview_channel, "badge-slate")

    @property
    def feedback_badge_class(self):
        mapping = {
            "product": "badge-info",
            "marketing": "badge-info",
            "sales": "badge-slate",
            "finance": "badge-muted",
            "operations": "badge-muted",
            "other": "badge-muted",
        }
        return mapping.get(self.feedback_team, "badge-slate")

    @property
    def is_open(self):
        return self.status in {"draft", "submitted", "shared"}

    @property
    def driver_count(self):
        return len(self.decision_drivers or [])
