"""SCM 4.11 Supply Chain Analytics — SupplyChainAlert, the exception queue [ALR-].

**Why STORED and not derived.** Acknowledgement, assignment, snooze and a resolution note are *human
state no aggregate can reproduce*. A purely computed exception list forgets that somebody already
looked at it — which is exactly the alert-fatigue failure the planning suites name. So the numbers on
an alert are recomputed by the detector, but the triage columns are written only by the five workflow
methods below and never by a form.

**Import direction.** The metric vocabulary comes from ``_choices`` (pure data), *never* from
``apps.scm.analytics`` — that module imports the model layer, so the edge has to run one way or the
package will not import. See the module docstring of ``_choices.py``.

**4.11 is read-only over 4.1-4.10.** An alert writes no ``StockMove`` and no ``JournalEntry``; it
points at the rows that caused it and records what a person decided about them.

--------------------------------------------------------------------------------------------------
WHY DE-DUPE IS ENFORCED IN THE DETECTOR AND NOT BY A DATABASE CONSTRAINT
--------------------------------------------------------------------------------------------------
A breach that keeps breaching must not accumulate one row per detection pass. The guard is
``analytics.detect_alerts()``: inside ``transaction.atomic()`` it resolves the whole open set for the
tenant by :attr:`dedupe_key` in ONE query and **updates** the matching open row (``observed_value``,
``impact_value``, ``detail``, ``last_seen_at``) instead of creating a second one. That is deliberate,
and both of the obvious database-level alternatives are worse:

* ``unique_together = ("tenant", "kpi_target", "dimension_key", "status")`` — a **resolved** row would
  permanently block the next *genuine* breach of the same thing, which is the opposite of what an
  alert queue is for; and because ``status`` is part of the key it still permits one duplicate per
  status anyway. It fails in both directions at once.
* ``UniqueConstraint(fields=[...], condition=Q(status__in=OPEN_STATUSES))`` — the shape that *looks*
  right. **MariaDB has no partial indexes**, so Django silently omits a conditional constraint on this
  backend: it would protect nothing in the deployment that matters. Worse, the test settings run on
  SQLite, which *does* support them — the constraint would be created there, pass every test, and be
  absent in production. A guard that exists only under test is more dangerous than no guard.

The application-level guard is also the only one that can express the real rule: *re-fire an existing
open alert, do not raise a new one*. A constraint can only refuse a write; it cannot merge one.
--------------------------------------------------------------------------------------------------

**Lifecycle contract for the views.** :meth:`acknowledge` / :meth:`assign` / :meth:`snooze` /
:meth:`resolve` / :meth:`dismiss` each return the ``{field: [before, after]}`` diff for
``write_audit_log`` (the ``ReorderRule.apply_computed`` shape). An **empty dict means nothing
changed** — the alert was already in that state, or is already closed — so the view messages that and
skips the audit write. Every one is no-op safe: re-resolving a resolved alert cannot blank the
original resolver. A ``ValidationError`` is raised only for a caller-supplied value that is out of
range (:meth:`snooze`'s day count), never for a wrong status.
"""
from datetime import timedelta

from apps.scm.models._base import *  # noqa: F401,F403
from apps.scm.models.SupplyChainAnalytics._choices import (
    ALERT_STATUS_CHOICES,
    ALERT_TYPE_CHOICES,
    METRIC_CHOICES,
    OPEN_ALERT_STATUSES,
    SEVERITY_CHOICES,
)


class SupplyChainAlert(TenantNumbered):
    """One supply-chain exception awaiting triage [ALR-] — the number, its subject, and who acted."""

    NUMBER_PREFIX = "ALR"

    #: Still demanding attention. Owned by ``_choices`` so the detector, the model and the pages that
    #: filter on it cannot drift apart.
    OPEN_STATUSES = OPEN_ALERT_STATUSES

    #: The six nullable subject FKs, in one place: ``clean()`` walks them for the tenant check and a
    #: template can render "what this is about" without a six-branch if-chain.
    SUBJECT_FIELDS = ("item", "party", "carrier", "shipment", "purchase_order", "location")

    #: Snooze bounds. Public so the action form validates the same window the model enforces.
    MIN_SNOOZE_DAYS = 1
    MAX_SNOOZE_DAYS = 90

    #: Colour-named badge classes — ``theme.css`` has NO ``badge-success``/``-warning``/``-danger``
    #: (L33, four recurrences). Kept beside the choices so every page renders the same colour.
    SEVERITY_CSS = {"critical": "badge-red", "warning": "badge-amber", "info": "badge-info"}
    STATUS_CSS = {"open": "badge-red", "acknowledged": "badge-amber", "snoozed": "badge-info",
                  "resolved": "badge-green", "dismissed": "badge-muted"}

    # --- what fired -------------------------------------------------------------------------------
    # Nullable: a rule-based exception ("tracking stale > N hours") legitimately has no target behind
    # it, and deleting a target must not delete the history of what it once raised.
    kpi_target = models.ForeignKey("scm.KpiTarget", on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="alerts")
    # Closed set, not free text: the detail page links straight to the metric's report page, and
    # clean() has to be able to check this against the target's own metric.
    metric = models.CharField(max_length=40, choices=METRIC_CHOICES, blank=True,
                              help_text="Registry key — blank for a pure rule-based exception")
    alert_type = models.CharField(max_length=24, choices=ALERT_TYPE_CHOICES, default="kpi_breach")
    title = models.CharField(max_length=200)
    severity = models.CharField(max_length=8, choices=SEVERITY_CHOICES, default="warning")

    observed_value = models.DecimalField(max_digits=16, decimal_places=4, null=True, blank=True,
                                         help_text="What was measured")
    threshold_value = models.DecimalField(max_digits=16, decimal_places=4, null=True, blank=True,
                                          help_text="What it was measured against")
    # Value at risk, and the DEFAULT ORDERING KEY — a queue ranked by count teaches people to ignore
    # it; one ranked by money puts the exception worth acting on at the top.
    impact_value = models.DecimalField(max_digits=14, decimal_places=2, default=0,
                                       help_text="Value at risk — what acting on this is worth")

    # `dimension_key` is machine-side (part of the de-dupe key); `dimension_label` is what a person
    # reads. Kept apart so renaming an item never changes what the detector matches on.
    dimension_key = models.CharField(max_length=64, blank=True)
    dimension_label = models.CharField(max_length=160, blank=True)

    # --- what it is about -------------------------------------------------------------------------
    # Six typed FKs rather than one generic object id: a bare int carries neither a tenant nor a type,
    # so it can point at a deleted or cross-tenant row (L40 §3). All SET_NULL — an alert is a record
    # that something happened and must survive the subject being retired. DISTINCT related_names
    # throughout: two FKs from one model onto the same target without them is a SystemCheckError, and
    # `core.Party` already carries sales_orders / accounting_invoices / scm_scorecards / demand_signals.
    item = models.ForeignKey("scm.Item", on_delete=models.SET_NULL, null=True, blank=True,
                             related_name="scm_alerts")
    party = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True,
                              related_name="scm_supply_alerts",
                              help_text="Supplier or customer this exception is about")
    carrier = models.ForeignKey("scm.Carrier", on_delete=models.SET_NULL, null=True, blank=True,
                                related_name="scm_alerts")
    shipment = models.ForeignKey("scm.Shipment", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="scm_alerts")
    purchase_order = models.ForeignKey("scm.PurchaseOrder", on_delete=models.SET_NULL, null=True,
                                       blank=True, related_name="scm_alerts")
    location = models.ForeignKey("scm.Location", on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="scm_alerts")

    #: The evidence rows behind the number — every score renders its own arithmetic rather than
    #: asking the reader to trust it (the ``SupplierScorecard.signal_summary`` precedent).
    detail = models.JSONField(default=dict, blank=True)

    # --- triage state (workflow-controlled — no form writes any of this, L22) ---------------------
    status = models.CharField(max_length=14, choices=ALERT_STATUS_CHOICES, default="open",
                              editable=False)
    #: ``<alert_type>:<dimension_key>[:<target pk>]`` for detector-written rows, blank for hand-raised
    #: ones. The detector's single-query lookup key — see the module docstring for why this is not a
    #: database constraint.
    dedupe_key = models.CharField(max_length=120, blank=True, db_index=True)

    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                    blank=True, related_name="scm_alerts_assigned")
    acknowledged_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
                                        null=True, blank=True, editable=False,
                                        related_name="scm_alerts_acknowledged")
    acknowledged_at = models.DateTimeField(null=True, blank=True, editable=False)
    snoozed_until = models.DateField(null=True, blank=True, editable=False)
    # Also the "closed by" pair for a DISMISSAL: there is deliberately no separate `dismissed_by`,
    # because both are terminal and an unattributed close is an audit hole. `status` is what says
    # whether the exception was fixed or judged not worth acting on.
    resolved_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                    blank=True, editable=False, related_name="scm_alerts_resolved")
    resolved_at = models.DateTimeField(null=True, blank=True, editable=False)
    resolution_note = models.TextField(blank=True)

    raised_at = models.DateTimeField(default=timezone.now, editable=False)
    #: The re-fire stamp. A breach that keeps breaching shows "still breaching" by moving this,
    #: WITHOUT a duplicate row.
    last_seen_at = models.DateTimeField(default=timezone.now, editable=False)
    notes = models.TextField(blank=True)

    class Meta:
        # Rank by material impact, not by count — the whole point of an exception queue.
        ordering = ["-impact_value", "-raised_at", "-id"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="scm_alr_tnt_status_idx"),
            models.Index(fields=["tenant", "severity"], name="scm_alr_tnt_sev_idx"),
            models.Index(fields=["tenant", "raised_at"], name="scm_alr_tnt_raised_idx"),
            models.Index(fields=["tenant", "assigned_to"], name="scm_alr_tnt_asg_idx"),
            # The detector's hot path: one equality lookup over the open set per detection pass.
            models.Index(fields=["tenant", "dedupe_key"], name="scm_alr_tnt_dedupe_idx"),
        ]

    def __str__(self):
        return (f"{self.number or 'ALR'} · {self.get_alert_type_display()} · "
                f"{self.dimension_label or 'network'}")

    def clean(self):
        super().clean()
        # An alert and the target it names must agree on MORE than the tenant (L40 §3): a target
        # measuring supplier on-time delivery cannot be the evidence for a dead-stock alert, and the
        # detail page's "open the metric" link would land on the wrong report page if it could.
        if self.kpi_target_id and self.tenant_id:
            target = self.kpi_target
            if target.tenant_id != self.tenant_id:
                raise ValidationError({"kpi_target": "That target belongs to another tenant."})
            if not self.metric:
                # Normalise rather than nag: choosing a target IS choosing its metric.
                self.metric = target.metric
            elif self.metric != target.metric:
                raise ValidationError({"metric": "This metric is not the one that target measures — "
                                                 "pick the matching target, or leave the metric "
                                                 "blank to inherit it."})
        # A narrowed dropdown is UX, not a guard (L39 §2): a crafted POST can still name another
        # tenant's row, so the combination is validated here as well. The related objects are already
        # cached by the form's own FK validation, so this costs no extra query on the normal path.
        if self.tenant_id:
            for name in self.SUBJECT_FIELDS:
                if getattr(self, f"{name}_id", None) is None:
                    continue
                if getattr(self, name).tenant_id != self.tenant_id:
                    raise ValidationError({name: "That record belongs to another tenant."})

    # --- derived (nothing below is stored) --------------------------------------------------------
    @property
    def is_open(self):
        """Still demanding attention — the gate every workflow action below shares."""
        return self.status in self.OPEN_STATUSES

    @property
    def is_snooze_expired(self):
        """A snooze that has run out. Snoozing is suppression, not closure, so the queue has to be
        able to hand the row back — otherwise ``snoozed`` is a black hole (L39 §4). The list page's
        "needs attention" filter is therefore
        ``Q(status__in=("open", "acknowledged")) | Q(status="snoozed", snoozed_until__lt=today)``.
        """
        return bool(self.status == "snoozed" and self.snoozed_until
                    and self.snoozed_until < timezone.localdate())

    @property
    def severity_css(self):
        """Colour-named badge class for ``severity``. ``theme.css`` has no semantic badge names."""
        return self.SEVERITY_CSS.get(self.severity, "badge-slate")

    @property
    def status_css(self):
        """Colour-named badge class for ``status`` — open is red because open means unattended."""
        return self.STATUS_CSS.get(self.status, "badge-slate")

    @property
    def subject_label(self):
        """The one line that says what this is about, for a list row that has no room for six FKs."""
        if self.dimension_label:
            return self.dimension_label
        for name in self.SUBJECT_FIELDS:
            if getattr(self, f"{name}_id", None) is not None:
                return str(getattr(self, name))
        return "Network-wide"

    # --- workflow (the ONLY writers of the triage columns) ----------------------------------------
    # Each returns the {field: [before, after]} audit diff, or {} when nothing changed. Kept on the
    # model so the five views stay thin and so the seeder and the tests drive the same code path the
    # buttons do.

    @staticmethod
    def _actor(user):
        """A saveable user or None — a view is ``@login_required``, but an AnonymousUser passed by a
        management command would otherwise raise on assignment rather than simply going unattributed."""
        return user if getattr(user, "pk", None) else None

    def _end_snooze(self, changes, fields):
        """Drop a live suppression window when the alert leaves ``snoozed``.

        ``snoozed_until`` is a deadline, not history: leaving a future date on an acknowledged or
        closed alert makes "is this still suppressed?" unanswerable for every later filter. The audit
        diff records that it was cleared, so nothing is lost.
        """
        if self.snoozed_until is None:
            return
        changes["snoozed_until"] = [str(self.snoozed_until), ""]
        self.snoozed_until = None
        fields.append("snoozed_until")

    def acknowledge(self, user):
        """Somebody has seen it. No-op once acknowledged — the first acknowledger is the true one."""
        if not self.is_open or self.status == "acknowledged":
            return {}
        changes = {"status": [self.status, "acknowledged"]}
        fields = ["status", "acknowledged_by", "acknowledged_at", "updated_at"]
        self._end_snooze(changes, fields)
        self.status = "acknowledged"
        self.acknowledged_by = self._actor(user)
        self.acknowledged_at = timezone.now()
        self.save(update_fields=fields)
        return changes

    def assign(self, user_obj):
        """Put a name on it. ``None`` un-assigns; assigning the same person again is a no-op.

        Only while open: handing a closed exception to somebody is a queue that never empties.
        """
        if not self.is_open:
            return {}
        new_pk = getattr(user_obj, "pk", None)
        if self.assigned_to_id == new_pk:
            return {}
        before = str(self.assigned_to) if self.assigned_to_id else ""
        self.assigned_to = user_obj if new_pk else None
        self.save(update_fields=["assigned_to", "updated_at"])
        return {"assigned_to": [before, str(user_obj) if new_pk else ""]}

    def snooze(self, days):
        """Suppress it for ``days`` (1-90). Re-snoozing extends or shortens the window.

        The bound is validated here and not only on the form: a wrong VALUE is rejected loudly, while
        a wrong STATE stays a silent no-op, because only the first is the caller's mistake.
        """
        try:
            days = int(days)
        except (TypeError, ValueError):
            raise ValidationError({"days": "Enter a whole number of days."})
        if not self.MIN_SNOOZE_DAYS <= days <= self.MAX_SNOOZE_DAYS:
            raise ValidationError({"days": f"Snooze for between {self.MIN_SNOOZE_DAYS} and "
                                           f"{self.MAX_SNOOZE_DAYS} days."})
        if not self.is_open:
            return {}
        until = timezone.localdate() + timedelta(days=days)
        if self.status == "snoozed" and self.snoozed_until == until:
            return {}
        changes = {"snoozed_until": [str(self.snoozed_until or ""), str(until)]}
        if self.status != "snoozed":
            changes["status"] = [self.status, "snoozed"]
        self.status = "snoozed"
        self.snoozed_until = until
        self.save(update_fields=["status", "snoozed_until", "updated_at"])
        return changes

    def resolve(self, user, note=""):
        """Close it as dealt with. No-op once closed — re-resolving must not blank the first resolver.

        Reachable from every open status, including an alert the detector has re-fired: a re-fire only
        moves ``last_seen_at`` and leaves the row open, so it never strands the button (L39 §1).
        """
        if not self.is_open:
            return {}
        changes = {"status": [self.status, "resolved"]}
        fields = ["status", "resolved_by", "resolved_at", "resolution_note", "updated_at"]
        self._end_snooze(changes, fields)
        self.status = "resolved"
        self.resolved_by = self._actor(user)
        self.resolved_at = timezone.now()
        self.resolution_note = (note or "").strip()
        if self.resolution_note:
            # Truncated: the audit payload is an index of what changed, not a second copy of the note.
            changes["resolution_note"] = ["", self.resolution_note[:200]]
        self.save(update_fields=fields)
        return changes

    def dismiss(self, user):
        """Close it as not worth acting on. Attributed through the same ``resolved_by`` pair — see
        that field's comment for why there is no separate ``dismissed_by``. No-op once closed."""
        if not self.is_open:
            return {}
        changes = {"status": [self.status, "dismissed"]}
        fields = ["status", "resolved_by", "resolved_at", "updated_at"]
        self._end_snooze(changes, fields)
        self.status = "dismissed"
        self.resolved_by = self._actor(user)
        self.resolved_at = timezone.now()
        self.save(update_fields=fields)
        return changes
