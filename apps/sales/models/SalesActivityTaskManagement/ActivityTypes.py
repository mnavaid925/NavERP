"""Sales 8.8 — `ActivityType` (`ATY-`), the tenant's configurable activity-type catalogue.

**WHY THIS IS NEW AND NOT A CRM 1.5 EDIT.** `crm.CommunicationLog.channel` is a closed five-value
field (`call/email/sms/note/meeting`) and `crm.CrmTask.type` another closed five-value field
(`todo/call/email/meeting/follow_up`). Neither is configurable. Every product in the research catalog
lets an admin define org-specific types — "Discovery call", "Technical validation", "Executive sponsor
drop-in" — because a five-value vocabulary does not survive contact with a real sales motion. The
catalogue is genuinely un-owned, so 8.8 adds it rather than forking either field.

**The two choice lists are IMPORTED from CRM 1.5, not copied** (L36 sibling rule — the same shape as
8.7 importing `ROUTING_OPERATORS` from 8.1's engine rather than writing a second validator). A copied
literal list is how two vocabularies drift apart and one of them quietly stops rejecting what the
other rejects. If CRM adds a channel, this type catalogue follows automatically.

**`default_outcome` is a CALL-only concept** and G1 refuses it on any other kind. That is the L39
trap: `default_outcome` and `kind="email"` are each individually perfectly valid — every field passes
its own validator, the form renders, `save()` succeeds — and the *pair* is a category error. A rep
reading "default outcome: Connected" on an email type would expect the system to log their email as a
connected call.
"""
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.crm.models import CommunicationLog, CrmTask
from apps.sales.models._base import TenantNumbered

#: 24 hours. A "default duration" past a day is a data-entry slip, not a very long call.
MAX_DEFAULT_DURATION_SECONDS = 86400


class ActivityType(TenantNumbered):
    """One tenant-defined activity type, carrying the defaults a rep should not retype."""

    NUMBER_PREFIX = "ATY"

    #: IMPORTED from CRM 1.5 — not re-spelled. The activity's own `channel` still lives on
    #: `crm.CommunicationLog`; this is the *catalogue entry* that says which channel it means.
    KIND_CHOICES = CommunicationLog.CHANNEL_CHOICES
    #: IMPORTED from CRM 1.5 — a call outcome, and only a call has one.
    OUTCOME_CHOICES = CommunicationLog.OUTCOME_CHOICES
    #: IMPORTED from CRM 1.5's task model, so a generated task and a hand-typed one rank the same.
    PRIORITY_CHOICES = CrmTask.PRIORITY_CHOICES

    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    kind = models.CharField(max_length=10, choices=KIND_CHOICES, default="call")
    # max_length=20 comfortably fits the longest value, "wrong_number" (13). An 8 here would pass
    # every test that does not run Django's fields.E009 and then fail at the database (L65).
    default_outcome = models.CharField(max_length=20, choices=OUTCOME_CHOICES, blank=True)
    default_duration_seconds = models.PositiveIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(MAX_DEFAULT_DURATION_SECONDS)],
        help_text="Pre-filled call length in seconds. Leave blank to have no default.",
    )
    default_priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default="medium")
    requires_opportunity = models.BooleanField(
        default=False,
        help_text="Logged activities of this type must name the opportunity they advance.",
    )
    is_billable = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    display_order = models.PositiveIntegerField(default=100)

    class Meta:
        ordering = ["display_order", "name"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "name"], name="sales_aty_tenant_name_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="sales_aty_tnt_active_idx"),
            models.Index(fields=["tenant", "kind"], name="sales_aty_tnt_kind_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        # G1 — the L39 pair guard. Both fields are individually valid; the pairing is not.
        if self.default_outcome and self.kind != "call":
            errors["default_outcome"] = (
                f"Only a call has an outcome, and this type is a {self.get_kind_display().lower()}. "
                "Clear the default outcome or change the type to a call."
            )
        # G2 — re-checked here as well as by the field validator, because a model-level caller
        # (seeder, service, management command) skips field validation only on some paths and
        # `full_clean()` is the only place both live.
        if self.default_duration_seconds is not None and self.default_duration_seconds > MAX_DEFAULT_DURATION_SECONDS:
            errors["default_duration_seconds"] = (
                f"A default duration cannot exceed {MAX_DEFAULT_DURATION_SECONDS} seconds (24 hours)."
            )
        if errors:
            raise ValidationError(errors)

    @property
    def default_duration_minutes(self):
        """``default_duration_seconds`` as whole minutes, or ``None`` when unset.

        ``ActivityLog.planned_minutes`` is a *minutes* column, so the conversion lives here once
        rather than being open-coded at each of its two call sites.
        """
        if self.default_duration_seconds is None:
            return None
        return int(self.default_duration_seconds) // 60

    def __str__(self):
        return f"{self.number or '—'} · {self.name}"
