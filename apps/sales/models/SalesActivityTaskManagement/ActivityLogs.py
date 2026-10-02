"""Sales 8.8 — `ActivityLog` (`SAL-`), the sales attribution layer over `crm.CommunicationLog`.

**WHAT THIS MODEL IS NOT.** It is not an activity. It holds **no** `channel`, `subject`, `body`,
`direction`, `occurred_at`, `duration_seconds`, `outcome` or `email_message_id` — every one of those
belongs to `crm.CommunicationLog` (CRM 1.5), and re-declaring any of them is the L36/L37 failure this
sub-module exists to avoid. Its one required relationship to the interaction is
`communication_log`, a **1:1** FK (`unique` per tenant): the sales layer never exists without the
CRM record it attributes.

**WHY A LAYER IS NEEDED AT ALL.** `CommunicationLog.related_opportunity` names a deal, but it answers
none of the questions a rep's own activity feed asks: which *territory* this activity advances, which
*account* it was about when the log has no party, which *custom activity type* it was, and whether it
was captured automatically (bullet 1's "automatic capture"). `logged_via` records provenance on the
CRM side; `capture_source` + `is_auto_captured` mirror it on the sales side so the feed filters
without a join.

**THE EMAIL COUNTERS ARE FROZEN EVIDENCE (L22).** `opened_at`, `open_count`, `clicked_at`,
`click_count` and `replied_at` are `editable=False`, so Django excludes them from every ModelForm
automatically. Their only writers are the create view and the two POST verbs
(`activity_log_mark_opened`, `activity_log_mark_clicked`) plus the reply stamp on the detail page.
A rep cannot type "opened 47 times" into the edit form — that is the whole point of the L20 pattern.

**`engagement_level` IS A PROPERTY, NOT A COLUMN (L37).** It is derived from the five counter fields
with a fixed precedence. A stored column would be a sixth thing that has to be kept in step with the
five it summarises, and the first hand-edited row would make it lie.

**MONOTONICITY.** `advance_email_engagement` only ever increments a counter and stamps a first-seen
timestamp. It never decrements and never clears `opened_at`/`clicked_at`: a later non-click event must
not un-open an email, because "was it ever opened" is the question the rollup answers.
"""
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.sales.models._base import TenantNumbered, settings

#: The sales-side mirror of `crm.CommunicationLog.LOGGED_VIA_CHOICES`.
#:
#: It is deliberately a *different* list with a *different* meaning: `logged_via` records how the
#: interaction was captured on the CRM record, while `capture_source` records where the *sales layer*
#: learned about it. `manual` is the only source that is not automatic, which is what makes the G3
#: agreement guard below a genuine two-field invariant rather than a restatement of one field.
CAPTURE_SOURCE_CHOICES = [
    ("manual", "Manual"),
    ("call_log", "Call Log"),
    ("bcc_dropbox", "BCC Dropbox"),
    ("calendar_sync", "Calendar Sync"),
    ("template_task", "Template Task"),
    ("plan_goal", "Plan Goal"),
    ("import", "Import"),
]

#: The subset of `CAPTURE_SOURCE_CHOICES` that means nobody typed this row in by hand.
#: G3 asserts `is_auto_captured == (capture_source in AUTO_CAPTURE_SOURCES)`.
AUTO_CAPTURE_SOURCES = frozenset(
    {value for value, _label in CAPTURE_SOURCE_CHOICES if value != "manual"}
)

#: `engagement_level` display vocabulary. Derived, so it lives as a plain tuple next to the property
#: rather than as a field's `choices=` — there is no column to constrain.
ENGAGEMENT_LEVELS = [
    ("none", "None"),
    ("opened", "Opened"),
    ("clicked", "Clicked"),
    ("replied", "Replied"),
]

#: The weakest→strongest order. A replied email is also opened and clicked, so the rollup's "replied"
#: figure is a subset of "clicked" and not a separate bucket to add to it.
ENGAGEMENT_PRECEDENCE = ["none", "opened", "clicked", "replied"]


class ActivityLog(TenantNumbered):
    """The sales attribution of one ``crm.CommunicationLog``, plus its frozen email engagement."""

    NUMBER_PREFIX = "SAL"

    CAPTURE_SOURCE_CHOICES = CAPTURE_SOURCE_CHOICES
    AUTO_CAPTURE_SOURCES = AUTO_CAPTURE_SOURCES

    # ---- the link to the interaction, which CRM 1.5 owns -------------------------------------
    communication_log = models.ForeignKey(
        "crm.CommunicationLog",
        on_delete=models.CASCADE,
        related_name="sales_activity_logs",
        help_text="The CRM 1.5 interaction this sales activity attributes.",
    )
    # PROTECT, not SET_NULL: a type referenced by historical activity must not vanish under it.
    # Retire it (`is_active = False`) instead — the catalogue keeps the history readable.
    activity_type = models.ForeignKey(
        "sales.ActivityType",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="activity_logs",
    )
    # ---- the attribution CRM 1.5 does not carry ----------------------------------------------
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_activity_logs",
    )
    opportunity = models.ForeignKey(
        "crm.Opportunity",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_activity_logs",
    )
    account = models.ForeignKey(
        "core.Party",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_activity_logs",
    )
    territory = models.ForeignKey(
        "crm.Territory",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sales_activity_logs",
    )
    # ---- bullet 1: automatic capture --------------------------------------------------------
    capture_source = models.CharField(
        max_length=20, choices=CAPTURE_SOURCE_CHOICES, default="manual"
    )
    is_auto_captured = models.BooleanField(default=False)
    # ---- bullet 5: the next step this activity implies ---------------------------------------
    next_best_action = models.CharField(max_length=255, blank=True)
    next_best_action_due = models.DateField(null=True, blank=True)
    # ---- FROZEN EVIDENCE (L22) — written once at create, then only by the POST verbs ----------
    # The local calendar day of `communication_log.occurred_at`. Storing the *day* rather than
    # re-deriving it per query is what lets the stale-deal board ask `.filter(occurred_on__lt=…)`
    # against an index instead of a per-row timezone conversion.
    occurred_on = models.DateField(null=True, blank=True, editable=False)
    planned_minutes = models.PositiveIntegerField(null=True, blank=True, editable=False)
    opened_at = models.DateTimeField(null=True, blank=True, editable=False)
    open_count = models.PositiveIntegerField(default=0, editable=False)
    clicked_at = models.DateTimeField(null=True, blank=True, editable=False)
    click_count = models.PositiveIntegerField(default=0, editable=False)
    replied_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        # Explicit `pk` as the final tie-break: two activities on the same day must have a
        # DETERMINISTIC order, because the "most recent activity" lookup that feeds the suggestion
        # board compares against a date (L61 — an unordered .first() is a latent idempotency bug).
        ordering = ["-occurred_on", "-pk"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "communication_log"],
                name="sales_sal_comm_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "occurred_on"], name="sales_sal_tnt_occd_idx"),
            models.Index(fields=["tenant", "capture_source"], name="sales_sal_tnt_capsrc_idx"),
            models.Index(fields=["tenant", "opportunity"], name="sales_sal_tnt_opp_idx"),
            models.Index(fields=["tenant", "owner"], name="sales_sal_tnt_owner_idx"),
        ]

    # ------------------------------------------------------------------ derived (never stored)

    @property
    def engagement_level(self):
        """``replied`` / ``clicked`` / ``opened`` / ``none`` — derived, never a column (L37).

        Precedence is the "strongest signal seen" reading, so it is monotonic in the right direction:
        an email that was opened and then clicked is ``clicked``, and one that was clicked and then
        replied to is ``replied``. It can only ever move *up*.
        """
        if self.replied_at:
            return "replied"
        if self.clicked_at or self.click_count:
            return "clicked"
        if self.opened_at or self.open_count:
            return "opened"
        return "none"

    @property
    def engagement_label(self):
        return dict(ENGAGEMENT_LEVELS).get(self.engagement_level, "None")

    @property
    def channel(self):
        """Read-through to ``communication_log.channel``.

        A convenience for the list template only. It is a **property**, so there is no column on
        this model named `channel` — grep the model file and there is none, which is the L36 proof
        that 8.8 has not declared a second activity vocabulary.
        """
        return self.communication_log.channel if self.communication_log_id else ""

    # ------------------------------------------------------------------ stamping

    def _stamp_frozen_evidence(self):
        """Fill ``occurred_on`` and ``planned_minutes`` **once**, on first save.

        Guarded by ``is None`` so an ordinary edit re-save never rewrites them: a rep correcting a
        typo on the subject should not silently move an activity to a different day on the rollup.
        """
        if self.occurred_on is None and self.communication_log_id:
            occurred_at = self.communication_log.occurred_at
            if occurred_at is not None:
                # L16: `timezone.localtime` is the only correct day boundary here. A naive
                # `.date()` on a tz-aware stamp reports the UTC day, which is the previous day for
                # most of the Americas and the morning of the next for Asia.
                self.occurred_on = timezone.localtime(occurred_at).date()
        if self.planned_minutes is None:
            minutes = None
            if self.activity_type_id and self.activity_type.default_duration_minutes is not None:
                minutes = self.activity_type.default_duration_minutes
            elif self.communication_log_id and self.communication_log.duration_seconds is not None:
                minutes = int(self.communication_log.duration_seconds) // 60
            self.planned_minutes = 0 if minutes is None else minutes

    def advance_email_engagement(self, *, opened=False, clicked=False, replied=False, when=None):
        """Move the frozen engagement counters forward. MONOTONIC — never decrements.

        Called only by the POST verbs, inside their own transaction. Each counter increments at most
        once per call even if the caller passes two signals, and a first-seen timestamp is never
        overwritten by a later event, so "was it ever opened" cannot be un-answered.
        """
        stamp = when or timezone.now()
        changed = []
        if opened and not self.opened_at:
            self.opened_at = stamp
            changed.append("opened_at")
        if opened:
            self.open_count = (self.open_count or 0) + 1
            changed.append("open_count")
        if clicked and not self.clicked_at:
            self.clicked_at = stamp
            changed.append("clicked_at")
        if clicked:
            self.click_count = (self.click_count or 0) + 1
            changed.append("click_count")
        if replied and not self.replied_at:
            self.replied_at = stamp
            changed.append("replied_at")
        return changed

    # ------------------------------------------------------------------ validation

    def _relation_belongs_to_tenant(self, field_name):
        """True when the named FK is unset or points at a row in THIS workspace.

        An FK to a tenant-scoped model *looks* safe and is not: a seeder or a service that
        hand-builds ``ActivityLog(tenant=A, opportunity=<tenant B>)`` bypasses every form. Copied in
        the same shape as ``TerritoryRule._relation_belongs_to_tenant`` and L4's rule.
        """
        if not self.tenant_id:
            return True
        relation_id = getattr(self, f"{field_name}_id", None)
        if not relation_id:
            return True
        related_model = self._meta.get_field(field_name).remote_field.model
        return related_model._default_manager.filter(
            pk=relation_id, tenant_id=self.tenant_id
        ).exists()

    def clean(self):
        super().clean()
        # L49 — this guard is tenant-INDEPENDENT, so it runs BEFORE the tenant early-return below.
        # A type that insists on a deal cannot be logged without one, and `ActivityType.
        # requires_opportunity` is data, so a seeder must get the same refusal a form does.
        if self.activity_type_id and self.activity_type.requires_opportunity and not self.opportunity_id:
            raise ValidationError(
                {"opportunity": (
                    f"“{self.activity_type.name}” is an activity type that must name the "
                    "opportunity it advances."
                )}
            )
        # G3 — the two fields must agree. This is a NON-FIELD error on purpose: either one of the
        # two is wrong and the author has to be told which pair, so naming a single field would
        # send them to fix the wrong one.
        if (self.capture_source != "manual") != bool(self.is_auto_captured):
            raise ValidationError(
                {
                    "__all__": (
                        f"An activity captured from “{self.get_capture_source_display()}” is "
                        f"{'automatic' if self.capture_source != 'manual' else 'not automatic'}, so "
                        "“Captured automatically” must be ticked "
                        f"{'for' if self.capture_source != 'manual' else 'unless'} that source."
                    )
                }
            )
        if not self.tenant_id:
            # L49: `TenantModelForm` never puts the tenant on the INSTANCE, so `instance.full_clean()`
            # runs while `self.tenant_id` is still None and every guard below this line is a no-op on
            # the form path. Anything tenant-INDEPENDENT must therefore be checked ABOVE this early
            # return — which is why the `requires_opportunity` guard is in `clean()` proper and only
            # the same-tenant FK checks live down here.
            return
        errors = {}
        if not self.communication_log_id:
            errors["communication_log"] = "Choose the interaction this sales activity records."
        elif not self._relation_belongs_to_tenant("communication_log"):
            errors["communication_log"] = "That interaction belongs to another workspace."
        for name, label in [
            ("activity_type", "activity type"),
            ("owner", "owner"),
            ("opportunity", "opportunity"),
            ("account", "account"),
            ("territory", "territory"),
        ]:
            if getattr(self, f"{name}_id") and not self._relation_belongs_to_tenant(name):
                errors[name] = f"That {label} belongs to another workspace."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self._stamp_frozen_evidence()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.number or '—'} · {self.channel or 'activity'} · {self.occurred_on or '—'}"
