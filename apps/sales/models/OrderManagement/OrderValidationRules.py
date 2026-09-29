"""Sales 8.6 Order Management — the typed order-validation rule set.

``apps.scm`` OWNS the sales order. SCM 4.5 hard-coded exactly two hold checks into
``salesorder_submit`` (a credit check and a fraud flag) and wrote the outcome onto
``SalesOrder.credit_hold`` / ``hold_reason``. This module replaces that fixed pair with a
tenant-configurable, TYPED rule set: a new rule type is a row of data, not a migration and
not a code change inside another team's app.

Nothing here declares a second order master. ``evaluate(order)`` takes an ``scm.SalesOrder``
it is HANDED and reads it; it never constructs one, never writes one, and never reaches into
SCM's status machine. That ownership ruling is L36/L37 and it is the reason this file imports
no SCM model at module scope — the order is duck-typed on the handful of attributes the rules
actually read, which also keeps every rule unit-testable against a plain stub.

Thresholds live in the ``parameters`` JSON blob rather than in a column per rule type, which is
the whole point of the design: ``{"amount": 5000}`` today, ``{"pct": 12.5}`` tomorrow, and a
rule type nobody has heard of yet is still just data. Unknown keys are ignored rather than
rejected, so a rule row written by a newer build survives a rollback.

Every money and percentage figure is computed in PYTHON over a fetched set, never with an
``F()`` expression or a database-side division — the SQLite integer-division trap that
``scm.SalesOrder.recalc_totals()`` documents silently drops fractional cents instead of raising.
"""
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.sales.models._base import TenantNumbered


ZERO = Decimal("0")



class OrderValidationRule(TenantNumbered):
    """One tenant-configured validation rule [OVR-], evaluated against an SCM sales order."""

    NUMBER_PREFIX = "OVR"

    #: Typed axes. The VALUE is what a view, template or fixture compares against; the label
    #: is display only. The ORDER is pinned — a badge or fixture keyed on position breaks.
    RULE_TYPE_CHOICES = [
        ("credit_limit", "Credit Limit Exceeded"),
        ("order_value", "Order Value Ceiling"),
        ("margin_floor", "Margin Floor"),
        ("discount_ceiling", "Line Discount Ceiling"),
        ("unmapped_item", "Unmapped Item Present"),
        ("missing_ship_to", "Missing Ship-To Address"),
        ("expired_quote", "Source Quote Expired"),
        ("inactive_item", "Inactive Item On Order"),
    ]
    SEVERITY_CHOICES = [
        ("block", "Block Submission"),
        ("hold", "Place On Hold"),
        ("warn", "Warn Only"),
    ]
    ACTIVE_ON_CHOICES = [
        ("submit", "On Submit"),
        ("amendment", "On Amendment"),
        ("both", "On Submit And Amendment"),
    ]

    #: Severities that keep an order from going out unattended. ``warn`` never does.
    BLOCKING_SEVERITIES = ("block", "hold")

    name = models.CharField(max_length=255)
    rule_type = models.CharField(max_length=24, choices=RULE_TYPE_CHOICES, default="credit_limit")
    severity = models.CharField(max_length=12, choices=SEVERITY_CHOICES, default="hold")
    active_on = models.CharField(max_length=12, choices=ACTIVE_ON_CHOICES, default="submit")
    parameters = models.JSONField(
        default=dict,
        blank=True,
        help_text='JSON thresholds for this rule type, e.g. {"amount": 5000} or {"pct": 12.5}.',
    )
    # Null = every customer. A blank rule is the workspace-wide default, which is why the FK
    # is nullable rather than required.
    party = models.ForeignKey(
        "core.Party",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="order_validation_rules",
    )
    priority = models.PositiveIntegerField(default=10)
    is_active = models.BooleanField(default=True)
    description = models.TextField(blank=True)

    class Meta:
        # Priority first (lowest number fires first), then number so the order is stable.
        ordering = ["priority", "number"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="sales_ovr_tenant_number_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "rule_type"], name="sales_ovr_tnt_type_idx"),
            models.Index(fields=["tenant", "is_active"], name="sales_ovr_tnt_active_idx"),
        ]

    # ------------------------------------------------------------------ parameter access

    def _param(self, key, default=None):
        """One threshold from ``parameters`` as a Decimal, or ``default`` when unusable.

        A JSON blob is user input: a key can arrive as a number, a numeric string, a bool or a
        nested object. Anything that is not a finite decimal is treated as ABSENT rather than
        raising, so one bad key cannot make an otherwise-valid rule explode mid-evaluation.
        ``bool`` is excluded explicitly — ``True`` is an ``int``, and ``Decimal("True")`` is
        not a number anybody meant to write.
        """
        raw = self.parameters.get(key) if isinstance(self.parameters, dict) else None
        if raw is None or isinstance(raw, bool):
            return default
        try:
            value = Decimal(str(raw))
        except (InvalidOperation, TypeError, ValueError):
            return default
        return value if value.is_finite() else default

    # ------------------------------------------------------------------ applicability

    def applies_to(self, order):
        """True when this rule is in force for ``order``.

        An inactive rule, and a rule scoped to a different customer, is skipped. A rule scoped
        to a ``party`` fires only for that customer, which is how a workspace carves out "this
        account gets a tighter credit line" without duplicating the whole rule set per account.
        """
        if order is None or not self.is_active:
            return False
        if self.party_id and order.customer_id != self.party_id:
            return False
        return True

    def runs_on(self, stage):
        """True when ``active_on`` covers ``stage`` (``"submit"`` or ``"amendment"``)."""
        return self.active_on in ("both", stage)

    @property
    def is_blocking(self):
        """True when this rule, when it fires, keeps the order from going out unattended."""
        return self.is_active and self.severity in self.BLOCKING_SEVERITIES

    # ------------------------------------------------------------------ evaluation

    def evaluate(self, order):
        """Run this ONE rule against ``order`` → ``(findings, block)``.

        PURE. It reads the order and the rule's own row and returns; it never writes, never
        saves, and never touches ``SalesOrder.status`` / ``credit_hold`` / ``hold_reason``.
        Deciding what to persist for a finding is the caller's job (8.6's hold workbench),
        which is the same split SCM 4.5 used for ``_evaluate_hold``.

        Returns ``([], False)`` when the rule does not apply or does not fire, so a caller can
        loop the whole active rule set and look only at what comes back. ``findings`` is always
        a LIST, never ``None`` — a caller must never have to tell "no result" from "no problem".
        """
        if not self.applies_to(order):
            return [], False

        observed, threshold, message = self._measure(order)
        if observed is None or threshold is None or message is None:
            return [], False
        if not self._breached(observed, threshold):
            return [], False

        finding = {
            "rule": self.number or self.name,
            "rule_type": self.rule_type,
            "severity": self.severity,
            "message": message,
            "observed": observed,
            "threshold": threshold,
        }
        # Only a "block"-severity rule refuses outright; a "hold" is a finding a human clears,
        # so it returns block=False and lets the caller raise the hold instead.
        return [finding], self.severity == "block"

    def _breached(self, observed, threshold):
        """Comparison direction is per rule type: a ceiling breaches HIGH, a floor breaches LOW."""
        if self.rule_type == "margin_floor":
            return observed < threshold
        return observed > threshold

    def _measure(self, order):
        """→ ``(observed, threshold, message)``, or all-``None`` when not measurable.

        Returning "not measurable" instead of guessing is deliberate. A margin floor on an order
        whose lines carry no mapped item has no cost basis; reporting 0% margin would invent a
        violation out of missing data.
        """
        handlers = {
            "credit_limit": self._measure_credit_limit,
            "order_value": self._measure_order_value,
            "margin_floor": self._measure_margin_floor,
            "discount_ceiling": self._measure_discount_ceiling,
            "unmapped_item": self._measure_unmapped_item,
            "missing_ship_to": self._measure_missing_ship_to,
            "expired_quote": self._measure_expired_quote,
            "inactive_item": self._measure_inactive_item,
        }
        handler = handlers.get(self.rule_type)
        if handler is None:
            return None, None, None
        return handler(order)

    def _open_receivable(self, order):
        """Σ balance due across the customer's open AR invoices, summed in PYTHON.

        One annotated query rather than N ``Invoice.balance_due()`` calls: each of those runs
        its own aggregate over the payment allocations, so the obvious loop is an N+1 on every
        credit check. No division happens here, so this plain Sum is the safe kind.
        """
        from apps.accounting.models import Invoice

        invoices = Invoice.objects.filter(
            tenant_id=self.tenant_id,
            party_id=order.customer_id,
            status__in=Invoice.OPEN_STATUSES,
        ).annotate(
            _paid=Coalesce(
                Sum("allocations__allocated_amount", filter=Q(allocations__payment__status="confirmed")),
                Value(ZERO),
                output_field=DecimalField(max_digits=18, decimal_places=2),
            )
        )
        outstanding = ZERO
        for invoice in invoices:
            outstanding += (invoice.total or ZERO) - (invoice._paid or ZERO)
        return outstanding

    def _profile_credit_limit(self, order):
        """The customer profile's own published limit, or None when there is no profile."""
        from apps.accounting.models import CustomerProfile

        profile = CustomerProfile.objects.filter(
            tenant_id=self.tenant_id,
            party_id=order.customer_id,
        ).only("credit_limit").first()
        return profile.credit_limit if profile is not None else None

    def _measure_credit_limit(self, order):
        exposure = (order.total or ZERO) + self._open_receivable(order)
        # An explicit ``limit`` on the rule wins; otherwise fall back to the customer profile's
        # own figure, so the common case needs no parameter typed at all. No profile and no
        # parameter means there is no published limit to breach — not a limit of zero. The
        # ``is None`` test rather than ``or`` so a deliberate ``{"limit": 0}`` is honoured.
        threshold = self._param("limit", self._param("amount"))
        if threshold is None:
            threshold = self._profile_credit_limit(order)
        if threshold is None:
            return None, None, None
        return exposure, threshold, f"Exposure of {exposure} exceeds the credit limit of {threshold}."

    def _measure_order_value(self, order):
        threshold = self._param("amount", self._param("value"))
        if threshold is None:
            return None, None, None
        total = order.total or ZERO
        return total, threshold, f"Order value of {total} exceeds the ceiling of {threshold}."

    def _measure_margin_floor(self, order):
        threshold = self._param("pct", self._param("margin_pct"))
        if threshold is None:
            return None, None, None
        # Decimal arithmetic over a fetched set, in Python. An F()-expression percentage
        # integer-divides on SQLite and reports a margin wrong by whole points.
        revenue, cost = ZERO, ZERO
        for line in order.lines.select_related("item"):
            revenue += line.line_subtotal
            if line.item_id:
                cost += (line.quantity_ordered or ZERO) * (line.item.standard_cost or ZERO)
        if revenue <= ZERO:
            return None, None, None
        margin = (revenue - cost) / revenue * Decimal("100")
        shown = margin.quantize(Decimal("0.01"))
        return margin, threshold, f"Margin of {shown}% is below the floor of {threshold}%."

    def _measure_discount_ceiling(self, order):
        threshold = self._param("pct", self._param("discount_pct"))
        if threshold is None:
            return None, None, None
        lines = list(order.lines.all())
        if not lines:
            return None, None, None
        worst = max((line.discount_pct or ZERO) for line in lines)
        return worst, threshold, f"A line discount of {worst}% exceeds the ceiling of {threshold}%."

    def _measure_unmapped_item(self, order):
        # 4.5 already refuses to submit an order carrying an unmapped line; this rule makes the
        # threshold the tenant's to set rather than SCM's, and lets a small allowance pass.
        count = Decimal(sum(1 for line in order.lines.all() if not line.item_id))
        allowed = self._param("max_unmapped", ZERO)
        return count, allowed, f"{count} order line(s) still have no mapped item."

    def _measure_missing_ship_to(self, order):
        present = Decimal("1") if order.ship_to_address_id else ZERO
        return present, ZERO, "The order has no ship-to address."

    def _measure_expired_quote(self, order):
        quote = order.source_quote if order.source_quote_id else None
        if quote is None or not quote.valid_until:
            return None, None, None
        days = Decimal((timezone.localdate() - quote.valid_until).days)
        return days, ZERO, f"Source quote {quote.number or ''} expired on {quote.valid_until}."

    def _measure_inactive_item(self, order):
        lines = [line for line in order.lines.select_related("item") if line.item_id]
        if not lines:
            return None, None, None
        count = Decimal(sum(1 for line in lines if not line.item.is_active))
        return count, ZERO, f"{count} order line(s) reference an inactive item."

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
        # A malformed blob is a FORM error, never a 500: JSONField would happily persist a list
        # or a bare string here, and every reader in this module assumes a mapping.
        if not isinstance(self.parameters or {}, dict):
            raise ValidationError({"parameters": "Parameters must be a JSON object."})
        super().clean()
        if not self.tenant_id:
            return
        if not self._relation_belongs_to_tenant("party"):
            raise ValidationError({"party": "The customer must belong to this workspace."})

    def save(self, *args, **kwargs):
        if not isinstance(self.parameters, dict):
            self.parameters = {}
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.number or '—'} · {self.name}"


