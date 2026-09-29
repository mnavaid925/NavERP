"""Sales 8.6 Order Management — the auditable order hold.

SCM 4.5 OWNS the sales order. What 4.5 could offer a hold was two columns —
``SalesOrder.credit_hold`` and ``hold_reason`` — written by one hard-coded credit/fraud
evaluation inside ``salesorder_submit`` and cleared by one hard-coded
``salesorder_release_hold``. There is no record of *who* held an order, *when*, *why in
numbers*, or *which* hold is holding it; the newest reason simply overwrites the last one.
This model is that missing record: one hold = one reason = one owner = one checkout.

The ownership ruling is L36/L37 and it shapes every line below:

* ``sales_order`` is an FK **into** ``scm.SalesOrder``, never a second order master. 8.6
  writes back exactly two fields on that order — ``credit_hold`` and ``hold_reason`` — and
  both are ``editable=False`` on 4.5's side. 4.5's ``salesorder_release_hold`` remains the
  release verb for 4.5's OWN credit/fraud hold; nothing here writes ``SalesOrder.status``.
* ``evaluation_snapshot`` is **frozen evidence**: server-generated, ``editable=False`` and
  off the form (L22). A user-supplied snapshot is a forgeable account of why an order was
  held, which is worse than no account at all. A hold raised by a rule records the observed
  figure against the threshold AT THE MOMENT it fired, so a rule re-tuned next month cannot
  rewrite why an order was held last month.
* ``severity`` is **copied** from the rule at fire time for the same reason. It is a fact
  about a past event, not a live reference to a mutable configuration row.
* ``rule`` is ``SET_NULL``, never ``PROTECT``. Deleting a rule retires configuration; it
  must never cascade into deleting the evidence of a hold a customer is still waiting on.
* Every money figure in the snapshot is rendered in **PYTHON** from an already-fetched
  object, never with an ``F()`` expression — the SQLite integer-division trap that
  ``scm.SalesOrder.recalc_totals()`` documents silently drops fractional cents.

The **checkout** is the concurrency control: two clerks must not clear the same hold at the
same time, and a hold must not sit unowned for a week. ``checked_out_by`` is claimed by one
named POST verb and released by another, and only the holder or a tenant admin may release
it.
"""
import json
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from apps.sales.models._base import TenantNumbered
from apps.sales.models.OrderManagement.OrderValidationRules import OrderValidationRule


ZERO = Decimal("0")


def _evidence(value):
    """One evaluation figure rendered JSON-safely, with money kept EXACT.

    A ``Decimal`` is emitted as its own string rather than cast to a float: this blob is
    frozen evidence of a commercial decision, and a float round-trip is how "5000.00"
    quietly becomes "4999.999999" in a column somebody later reads as a threshold breach.
    Anything unrecognised degrades to ``str()`` rather than raising — a snapshot that failed
    to build would lose the hold itself, which is the one thing this record must not do.
    """
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    return str(value)


def build_evaluation_snapshot(rule, findings, order=None, hold_type="manual", actor=None):
    """The frozen evidence dict for one hold — built here, never accepted from a form.

    ``rule`` may be ``None`` (a hand-placed manual hold) and ``findings`` may be empty: the
    snapshot still records WHO placed it, WHEN, against WHICH order and with WHAT thresholds
    in force, which is the part a person cannot reconstruct a month later.

    Money is read off the already-fetched ``order`` in Python. The snapshot is NOT saved here
    — the caller owns the transaction that writes the hold, so a rule evaluation and the row
    it produces land together or not at all.
    """
    now = timezone.now()
    findings = list(findings or [])
    snapshot = {
        "captured_at": now.isoformat(),
        "hold_type": hold_type or "manual",
        "raised_by": str(actor) if actor else "",
        "rule_number": (getattr(rule, "number", "") or ""),
        "rule_name": (getattr(rule, "name", "") or ""),
        "rule_type": (getattr(rule, "rule_type", "") or ""),
        "severity": (getattr(rule, "severity", "") or ""),
        # The thresholds IN FORCE when this fired. A rule edited tomorrow does not get to
        # restate the numbers this hold was raised on.
        "rule_parameters": (
            dict(rule.parameters) if rule is not None and isinstance(rule.parameters, dict) else {}
        ),
        "findings": [
            {
                "rule": str(finding.get("rule", "")),
                "rule_type": str(finding.get("rule_type", "")),
                "severity": str(finding.get("severity", "")),
                "message": str(finding.get("message", "")),
                "observed": _evidence(finding.get("observed")),
                "threshold": _evidence(finding.get("threshold")),
            }
            for finding in findings
            if isinstance(finding, dict)
        ],
    }
    if order is not None:
        snapshot["order_number"] = getattr(order, "number", "") or ""
        snapshot["order_status"] = getattr(order, "status", "") or ""
        snapshot["order_total"] = _evidence(getattr(order, "total", None))
        snapshot["order_customer"] = getattr(getattr(order, "customer", None), "name", "") or ""
    return snapshot



class OrderHold(TenantNumbered):
    """One auditable, checkout-able hold on an SCM sales order [OHD-]."""

    NUMBER_PREFIX = "OHD"

    #: Where the hold came from. The VALUE is what a view, template or fixture compares
    #: against; the label is display only. The ORDER is pinned — a badge or fixture keyed on
    #: position breaks.
    HOLD_TYPE_CHOICES = [
        ("credit", "Credit Hold"),
        ("fraud", "Fraud Review"),
        ("validation", "Validation Failure"),
        ("manual", "Manual Hold"),
    ]
    #: The lifecycle of the hold itself. Workflow-governed: written only by the raise /
    #: clear / supersede verbs, never by the form (L22).
    STATUS_CHOICES = [
        ("open", "Open"),
        ("cleared", "Cleared"),
        ("superseded", "Superseded"),
    ]
    #: The SAME axis as ``OrderValidationRule.SEVERITY_CHOICES``, re-exported rather than
    #: re-typed. A hold's badge and its rule's badge must never be able to disagree, and two
    #: hand-maintained copies of one tuple is how they eventually do.
    SEVERITY_CHOICES = list(OrderValidationRule.SEVERITY_CHOICES)

    #: The only status a human may act on.
    OPEN_STATUS = "open"

    # L36/L37: an FK INTO the order SCM 4.5 owns — never a second order master.
    sales_order = models.ForeignKey(
        "scm.SalesOrder",
        on_delete=models.CASCADE,
        related_name="order_holds",
    )
    # SET_NULL, never PROTECT: deleting a rule retires configuration. It must not delete the
    # evidence of why an order is still being held, so the FK nulls and the snapshot stands.
    rule = models.ForeignKey(
        "sales.OrderValidationRule",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="raised_holds",
        help_text="The rule that fired, if this hold came from the rule set. Blank = placed by hand.",
    )
    # PROTECT: a customer who is the reason for a hold is not a row we may quietly lose.
    party = models.ForeignKey(
        "core.Party",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="order_holds",
        help_text="The customer this hold is about. Defaults to the order's own customer.",
    )
    hold_type = models.CharField(max_length=24, choices=HOLD_TYPE_CHOICES, default="credit")
    reason = models.TextField()
    # COPIED from the rule at fire time, deliberately: re-tuning a rule next month must not be
    # able to rewrite why an order was held last month. Never authorable.
    severity = models.CharField(max_length=12, choices=SEVERITY_CHOICES, default="hold", editable=False)
    # Workflow-governed — written only by the raise / clear / supersede verbs.
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default="open", editable=False)
    # FROZEN EVIDENCE, server-generated. L22: a user-supplied snapshot is a forgeable account
    # of why an order was held, so it is off the form and cannot be set by a view either.
    evaluation_snapshot = models.JSONField(
        default=dict,
        blank=True,
        editable=False,
        help_text="Frozen, server-generated evidence of the evaluation that raised this hold.",
    )

    # Every field below is ACTION-STAMPED (L22): each is written by exactly one named POST
    # view, and none of them is on the form.
    raised_at = models.DateTimeField(default=timezone.now, editable=False)
    raised_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_holds_raised",
        editable=False,
    )
    checked_out_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_holds_checked_out",
        editable=False,
    )
    checked_out_at = models.DateTimeField(null=True, blank=True, editable=False)
    cleared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_holds_cleared",
        editable=False,
    )
    cleared_at = models.DateTimeField(null=True, blank=True, editable=False)
    # The ONLY authorable lifecycle field: a human writes the justification. A hold released
    # with no stated reason is the thing this whole model exists to prevent.
    clear_note = models.TextField(blank=True)
    superseded_by = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="supersedes",
        editable=False,
    )

    class Meta:
        # Newest first: a hold workbench is a work QUEUE, and the queue is read top-down.
        ordering = ["-raised_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="sales_ohd_tenant_number_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="sales_ohd_tnt_status_idx"),
            models.Index(fields=["tenant", "sales_order"], name="sales_ohd_tnt_order_idx"),
        ]

    # ------------------------------------------------------------------ state

    @property
    def is_open(self):
        """True while this hold is still holding the order."""
        return self.status == self.OPEN_STATUS

    @property
    def is_checked_out(self):
        """True while a user owns the working-on-it checkout."""
        return self.checked_out_by_id is not None

    @property
    def is_cleared(self):
        return self.status == "cleared"

    # ------------------------------------------------------------------ snapshot

    @property
    def parsed_snapshot(self) -> dict:
        """``evaluation_snapshot`` as a dict, or ``{}`` — never a raw string, never a raise.

        The column is a JSONField, so Django normally hands back the parsed object already;
        this guards the two shapes that would otherwise blow up the one page whose whole job
        is to explain a decision: a row written by a build that stored a bare string, and a
        hand-edited row holding a JSON array. The detail page renders THIS, so a malformed
        blob degrades to an empty panel rather than a 500.
        """
        raw = self.evaluation_snapshot
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, (str, bytes)):
            try:
                parsed = json.loads(raw)
            except (TypeError, ValueError):
                return {}
            return parsed if isinstance(parsed, dict) else {}
        return {}

    # ------------------------------------------------------------------ validation

    def _relation_belongs_to_tenant(self, field_name):
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
        # NOTE the absent snapshot guard, and do not add one. `OrderHoldForm.Meta.fields` is
        # ["sales_order","rule","party","hold_type","reason","clear_note"] and
        # `evaluation_snapshot` is `editable=False` (frozen evidence, L22), so a ValidationError
        # keyed on it routes through Django's `add_error(None, …)` and raises ValueError — a 500
        # on BOTH create and edit, and a *data-dependent* one, so the same form saves for one hold
        # and 500s for another depending on invisible prior state. That is the 0.20 close-out
        # finding verbatim. The sibling `OrderAmendment` gets this right by normalising the
        # equivalent field in `save()` instead; `save()` below does the same here.
        super().clean()
        if not self.tenant_id:
            return
        # A hold on another workspace's order is the one combination that would let a clerk
        # release a hold on a customer they cannot otherwise see.
        if not self._relation_belongs_to_tenant("sales_order"):
            raise ValidationError({"sales_order": "The sales order must belong to this workspace."})
        if not self._relation_belongs_to_tenant("rule"):
            raise ValidationError({"rule": "The validation rule must belong to this workspace."})
        if not self._relation_belongs_to_tenant("party"):
            raise ValidationError({"party": "The customer must belong to this workspace."})

    def save(self, *args, **kwargs):
        # The one place a malformed snapshot is repaired, and deliberately NOT in ``clean()``:
        # ``evaluation_snapshot`` is not on the form (it is frozen evidence, L22), so a
        # ValidationError keyed on it routes through ``add_error(None, …)`` and raises ValueError
        # — a 500 on both create and edit. Normalising here keeps the field out of the validation
        # path while still guaranteeing every reader gets the mapping ``parsed_snapshot`` promises.
        if not isinstance(self.evaluation_snapshot, dict):
            self.evaluation_snapshot = {}
        return super().save(*args, **kwargs)

    def __str__(self):
        order_number = self.sales_order.number if self.sales_order_id else "—"
        return f"{self.number or '—'} · {order_number} · {self.reason[:60]}"

