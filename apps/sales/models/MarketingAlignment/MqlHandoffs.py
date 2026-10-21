"""Sales 8.13 — `MqlHandoff` (`MQL-`), the marketing-to-sales lead handoff.

A handoff is the moment a lead that marketing qualified is passed to sales for a decision. It
records the three things the NavERP bullet asks for:

* **the handoff itself** -- which lead, from which campaign, to which rep, against which SLA;
* **the decision** -- accepted, rejected (with the reason), converted, or expired unanswered;
* **the SLA** -- the deadline, the actual response time, and whether the deadline was missed.

Acceptance rate and SLA compliance are therefore *derived* from the handoff rows rather than
stored, so a handoff can never claim a rate that its own history does not support.

OWNERSHIP (L36/L37): the lead, campaign, opportunity, account, user and currency masters all
already exist (CRM 1.1 / 1.2 / 1.3, core spine, accounts, accounting 2.2). None is declared here.
"""
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone

from apps.sales.models._base import TenantNumbered

HANDOFF_STATUS_CHOICES = [
    ("pending", "Pending Review"),
    ("accepted", "Accepted by Sales"),
    ("rejected", "Rejected by Sales"),
    ("expired", "SLA Expired"),
    ("converted", "Converted to Opportunity"),
]

HANDOFF_SOURCE_CHOICES = [
    ("campaign", "Campaign"),
    ("content", "Content Download"),
    ("event", "Event / Webinar"),
    ("webinar", "Webinar"),
    ("referral", "Referral"),
    ("inbound", "Inbound Request"),
    ("partner", "Partner"),
    ("other", "Other"),
]

# Statuses that mean sales has actually responded to the handoff.
RESPONDED_STATUSES = ("accepted", "rejected", "converted")


class MqlHandoff(TenantNumbered):
    """A marketing qualified lead handed to sales, with a response SLA (8.13)."""

    NUMBER_PREFIX = "MQL"

    lead = models.ForeignKey(
        "crm.Lead",
        on_delete=models.CASCADE,
        related_name="sales_mql_handoffs",
    )
    campaign = models.ForeignKey(
        "crm.Campaign",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_mql_handoffs",
    )
    account = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_mql_handoffs",
        help_text="Target customer account the lead is being handed to.",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_mql_handoff_owners",
        help_text="Marketing owner of the handoff.",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_mql_handoff_assignees",
        help_text="Sales rep who must respond.",
    )
    opportunity = models.ForeignKey(
        "crm.Opportunity",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_mql_handoffs",
        help_text="The deal this handoff produced.",
    )
    status = models.CharField(
        max_length=20,
        choices=HANDOFF_STATUS_CHOICES,
        default="pending",
        db_index=True,
    )
    source_kind = models.CharField(
        max_length=20,
        choices=HANDOFF_SOURCE_CHOICES,
        default="campaign",
    )
    handoff_at = models.DateTimeField(default=timezone.now, db_index=True)
    sla_due_at = models.DateTimeField(
        db_index=True,
        help_text="Response deadline. SLA compliance is a tracked NavERP bullet, so this is required.",
    )
    responded_at = models.DateTimeField(
        null=True,
        blank=True,
        editable=False,
        help_text="Stamped automatically on the first sales response.",
    )
    acceptance_reason = models.CharField(max_length=255, blank=True)
    rejection_reason = models.CharField(max_length=255, blank=True)
    lead_score = models.PositiveSmallIntegerField(
        default=0,
        validators=[MaxValueValidator(100)],
        help_text="Snapshot of the lead score at handoff time.",
    )
    estimated_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(0)],
    )
    currency = models.ForeignKey(
        "accounting.Currency",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_mql_handoffs",
    )
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-handoff_at", "-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "number"],
                name="sales_mql_tenant_number_uniq",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "status"],
                name="sales_mql_tnt_status_idx",
            ),
            models.Index(
                fields=["tenant", "sla_due_at"],
                name="sales_mql_tnt_sla_idx",
            ),
            models.Index(
                fields=["tenant", "lead"],
                name="sales_mql_tnt_lead_idx",
            ),
            models.Index(
                fields=["tenant", "campaign"],
                name="sales_mql_tnt_camp_idx",
            ),
        ]

    def __str__(self):
        lead_name = self.lead.name if self.lead_id else "Lead"
        return f"{self.number} · {lead_name} · {self.get_status_display()}"

    @property
    def is_responded(self):
        return self.responded_at is not None

    # --- THE SLA-BREACH RULE -- one source, two evaluations -------------------------------
    # A handoff is in breach when sales answered AFTER the deadline, or when it has not been
    # answered at all and the deadline has passed. Neither clause looks at `status`: the
    # `expired` status exists precisely to RECORD the unanswered-and-overdue case, so a status
    # filter would hide exactly the rows the status names.
    #
    # `sla_breach_q()` renders these clauses as a SQL filter (used by EVERY aggregate in the
    # module); `_sla_breach_match()` evaluates the same clauses against one row in Python (used
    # by the row badge). Both read this tuple, so the MQL list card, the attribution console
    # and the per-row badge cannot drift apart.
    SLA_BREACH_CLAUSES = ("answered_late", "unanswered_overdue")

    @classmethod
    def sla_breach_q(cls, now=None):
        """The SLA-breach rule as a SQL filter -- the single definition used by every aggregate.

        `now` is the instant the "unanswered and overdue" clause is measured against; it
        defaults to the current time. Pass an explicit `now` when several aggregates in one
        request must be measured against the same instant.
        """
        if now is None:
            now = timezone.now()
        q = Q()
        if "answered_late" in cls.SLA_BREACH_CLAUSES:
            q |= Q(responded_at__isnull=False, responded_at__gt=F("sla_due_at"))
        if "unanswered_overdue" in cls.SLA_BREACH_CLAUSES:
            q |= Q(responded_at__isnull=True, sla_due_at__lt=now)
        return q

    def _sla_breach_match(self, now=None):
        """The same SLA-breach rule, evaluated against this row in Python.

        `sla_breach_q()` cannot be reused verbatim here: its "answered late" clause compares
        two columns of the SAME row (`F("sla_due_at")`), which has no Python equivalent. The
        clauses are therefore evaluated here one by one, against the same
        `SLA_BREACH_CLAUSES` tuple that builds the SQL.
        """
        if self.sla_due_at is None:
            return False
        if now is None:
            now = timezone.now()
        for clause in self.SLA_BREACH_CLAUSES:
            if clause == "answered_late" and self.responded_at is not None:
                if self.responded_at > self.sla_due_at:
                    return True
            elif clause == "unanswered_overdue" and self.responded_at is None:
                if self.sla_due_at < now:
                    return True
        return False

    @property
    def is_sla_breached(self):
        """True when sales answered after the deadline, or has not answered at all.

        An unanswered, overdue handoff is a breach too -- that is the case the SLA exists to
        surface, and it is exactly the "leakage" a MQL-to-SQL rate is supposed to expose.
        """
        return self._sla_breach_match()

    @property
    def response_hours(self):
        """Hours between the handoff and the sales response, or None if unanswered."""
        if self.responded_at is None or self.handoff_at is None:
            return None
        return round((self.responded_at - self.handoff_at).total_seconds() / 3600, 2)

    def save(self, *args, **kwargs):
        # Stamp responded_at on the first transition into a responded status.
        #
        # It is cleared ONLY on the move back to `pending` (the contract's re-open path). An
        # already-answered handoff that is later re-labelled `expired` KEEPS its response time:
        # clearing it would flip the row from "answered late" to "unanswered" in the SLA
        # metric, and would silently destroy the measured response time.
        stamped = False
        if self.status in RESPONDED_STATUSES and self.responded_at is None:
            self.responded_at = timezone.now()
            stamped = True
        elif self.status == "pending":
            self.responded_at = None
            stamped = True
        # A caller that passes `update_fields` must not be able to persist the row while
        # silently dropping the stamp: the in-memory instance would report a response time
        # that never reached the database.
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            fields = set(update_fields)
            if stamped:
                fields.add("responded_at")
            kwargs["update_fields"] = fields
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        tenant_id = self.tenant_id
        if tenant_id:
            # `currency` is deliberately absent: `accounting.Currency` is a GLOBAL master with no
            # tenant FK, so `getattr(currency, "tenant_id", None)` is None and every currency would
            # be rejected as cross-tenant (L29 -- Currency is never tenant-checked).
            for field_name, label in (
                ("lead", "Lead"),
                ("campaign", "Campaign"),
                ("account", "Account"),
                ("owner", "Owner"),
                ("assigned_to", "Assigned rep"),
                ("opportunity", "Opportunity"),
            ):
                related = getattr(self, field_name, None)
                if related is None:
                    continue
                if getattr(related, "tenant_id", None) != tenant_id:
                    raise ValidationError(
                        {field_name: f"{label} must belong to the same workspace."}
                    )
        if self.sla_due_at and self.handoff_at and self.sla_due_at < self.handoff_at:
            raise ValidationError(
                {"sla_due_at": "The SLA deadline cannot be earlier than the handoff time."}
            )
        if self.status == "rejected" and not self.rejection_reason:
            raise ValidationError(
                {"rejection_reason": "A rejected handoff must record why sales rejected it."}
            )
