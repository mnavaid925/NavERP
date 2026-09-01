"""Procurement 6.13 Invoice & Voucher Management — InvoiceMatchVariance.

The three-way-match **exception register**: one row per check that did not agree, written only
by ``SupplierInvoice.run_match()`` through :meth:`InvoiceMatchVariance.record`.

Discipline worth recording, because a reviewer will otherwise go looking for it:

* **This model carries its OWN ``tenant`` column** (it is ``TenantOwned``), unlike its two
  siblings ``SupplierInvoiceLine`` (scoped through ``invoice``) and the dispute lanes. Every
  queryset filters ``tenant=request.tenant`` and every object lookup is
  ``get_object_or_404(..., tenant=request.tenant)``.
* **There is no create / edit / delete route.** A variance is EVIDENCE, not a record: the
  register is rebuilt from scratch by every ``run_match()``, so a hand-made or hand-edited row
  would be wiped by the next match run and a row edited to look accepted would be a false
  audit trail. The only human verb is :meth:`InvoiceMatchVariance.accept`, which moves
  ``resolution`` and nothing else.
* **``variance_abs`` / ``variance_pct`` are DERIVED** (``editable=False``, recomputed in
  ``save()``) and ``detected_at`` is system-set (``auto_now_add``), so neither may appear in a
  form's ``Meta.fields``.
* **No module-level import of ``SupplierInvoices``.** That module imports THIS one at module
  level (it needs the model for ``run_match()``), so importing back the other way is a
  star-import cycle at URLconf import. The FM references are STRINGS
  (``"procurement.SupplierInvoice"``) and the one helper we need from lane A —
  ``resolve_tolerance`` — is imported LAZILY inside the two methods that call it, exactly the
  shape ``SupplierInvoiceLines.py`` uses for its cumulative aggregates.
"""
from decimal import Decimal, InvalidOperation

from apps.procurement.models._base import *  # noqa: F401,F403

#: Column-width ceilings. ``variance_pct`` is DecimalField(9, 4), so five integer digits is all
#: it holds — a one-cent variance against a unit price of 0.0001 is 999,900% and would otherwise
#: die inside the driver on INSERT, taking the whole ``run_match()`` transaction with it. The
#: stored figure is clamped; the OUTCOME is still judged on the unclamped value lane A computed.
_MAX_PCT = Decimal("99999.9999")


def _finite(value):
    """``value`` as a finite ``Decimal``, or ``None`` (L35/L11).

    ``Decimal("nan")`` and ``Decimal("Infinity")`` both PARSE and then raise on the COMPARISON,
    so finiteness is tested before anything else touches the figure.
    """
    try:
        number = Decimal(value if value is not None else ZERO)
    except (InvalidOperation, ValueError, TypeError, ArithmeticError):
        return None
    return number if number.is_finite() else None


def _as_decimal(value):
    """``value`` as a usable ``Decimal`` — ``ZERO`` for anything unusable."""
    number = _finite(value)
    return ZERO if number is None else number


def _clamp_pct(value):
    """``variance_pct`` held inside its own column width (see ``_MAX_PCT``)."""
    if value is None:
        return None
    return min(max(value, -_MAX_PCT), _MAX_PCT)


VARIANCE_TYPE_CHOICES = [("price", "Unit Price"), ("quantity", "Quantity vs Receipt"),
                         ("quantity_no_receipt", "Quantity vs Order (No Receipt)"),
                         ("over_invoice", "Cumulative Over-Invoicing"),
                         ("total_amount", "Header Total"), ("fx_rate", "FX / Conversion Rate"),
                         ("tax", "Tax Amount"), ("duplicate", "Duplicate Invoice"),
                         ("missing_po", "No PO Reference"), ("missing_receipt", "No Goods Receipt")]
OUTCOME_CHOICES = [("auto_accept", "Auto-Accepted (Within Tolerance)"),
                   ("warn", "Accepted With Warning"), ("block", "Blocked — Outside Tolerance")]
RESOLUTION_CHOICES = [("open", "Open"), ("accepted", "Accepted by AP"),
                      ("disputed", "Disputed With Supplier"),
                      ("credit_memo", "Resolved by Credit Memo"),
                      ("debit_memo", "Resolved by Debit Memo"),
                      ("short_paid", "Resolved by Short Payment"), ("cancelled", "Cancelled")]
BASIS_CHOICES = [("po", "Purchase Order"), ("receipt", "Goods Receipt"),
                 ("header", "Invoice Header")]


class InvoiceMatchVariance(TenantOwned):
    """One three-way-match exception.

    ``invoice_line`` is NULL for a header-level check (the whole document's total, its tax, its
    conversion rate, a duplicate suspicion). ``outcome`` is what the MACHINE decided when the
    row was written; ``resolution`` is what the ACCOUNTS PAYABLE clerk has since done about it,
    and is the only field a human ever moves.
    """

    invoice = models.ForeignKey("procurement.SupplierInvoice", on_delete=models.CASCADE,
                                related_name="variances")
    #: NULL ⇒ a header-level check (total / FX / tax / duplicate), not a line-level one.
    invoice_line = models.ForeignKey("procurement.SupplierInvoiceLine", on_delete=models.CASCADE,
                                     null=True, blank=True, related_name="variances")
    dispute = models.ForeignKey("procurement.InvoiceDispute", on_delete=models.SET_NULL,
                                null=True, blank=True, related_name="variances")

    variance_type = models.CharField(max_length=20, choices=VARIANCE_TYPE_CHOICES)
    basis = models.CharField(max_length=20, choices=BASIS_CHOICES, default="po")

    expected_value = models.DecimalField(max_digits=18, decimal_places=4, default=ZERO)
    actual_value = models.DecimalField(max_digits=18, decimal_places=4, default=ZERO)
    #: DERIVED, SIGNED (actual − expected) — a negative figure is an under-charge.
    variance_abs = models.DecimalField(max_digits=18, decimal_places=4, default=ZERO,
                                       editable=False)
    #: DERIVED, SIGNED percentage; NULL when there is no expected value to divide by.
    variance_pct = models.DecimalField(max_digits=9, decimal_places=4, null=True, blank=True,
                                       editable=False)
    #: The bands that were actually in force — echoed back so the page can show WHY a row is
    #: what it is after the workspace retunes its tolerances.
    tolerance_abs_applied = models.DecimalField(max_digits=18, decimal_places=4, null=True,
                                                blank=True)
    tolerance_pct_applied = models.DecimalField(max_digits=9, decimal_places=4, null=True,
                                                blank=True)

    outcome = models.CharField(max_length=12, choices=OUTCOME_CHOICES, default="auto_accept")
    resolution = models.CharField(max_length=12, choices=RESOLUTION_CHOICES, default="open")
    message = models.CharField(max_length=255, blank=True)
    detected_at = models.DateTimeField(auto_now_add=True)

    #: Only these badge classes exist (theme.css:286-291) — see the template safety rules.
    OUTCOME_CSS = {"auto_accept": "badge-green", "warn": "badge-amber", "block": "badge-red"}
    RESOLUTION_CSS = {"open": "badge-amber", "accepted": "badge-green", "disputed": "badge-red",
                      "credit_memo": "badge-info", "debit_memo": "badge-info",
                      "short_paid": "badge-slate", "cancelled": "badge-muted"}

    class Meta:
        ordering = ["-detected_at", "-id"]
        indexes = [
            # The register's two working filters: "what is blocking me" and "what kind of
            # exception is this".
            models.Index(fields=["tenant", "outcome", "resolution"],
                         name="prc_imv_tnt_outcome_idx"),
            models.Index(fields=["tenant", "variance_type"], name="prc_imv_tnt_type_idx"),
            # The Match Board groups by invoice, and run_match() deletes by invoice.
            models.Index(fields=["invoice"], name="prc_imv_invoice_idx"),
        ]
        verbose_name = "invoice match variance"

    def __str__(self):
        # ``invoice_id`` only: __str__ runs on every admin/list row and must not fan out a query.
        return f"{self.get_variance_type_display()} on invoice #{self.invoice_id}"

    # -- derived ------------------------------------------------------------------------------

    @property
    def outcome_css(self):
        return self.OUTCOME_CSS.get(self.outcome, "badge-slate")

    @property
    def resolution_css(self):
        return self.RESOLUTION_CSS.get(self.resolution, "badge-slate")

    @property
    def is_blocking(self):
        return self.outcome == "block"

    @property
    def is_open(self):
        return self.resolution == "open"

    @property
    def can_accept(self):
        """Whether the Accept verb is offered on this row.

        Lives on the MODEL rather than being annotated per view, because three surfaces gate on it
        — the register, the Match Board and the detail page — and only the detail page used to
        derive it, so the other two silently rendered no Accept button at all. Every one of those
        querysets already ``select_related("invoice")``, so it costs no extra query.
        """
        return self.resolution in ("open", "disputed") and not self.invoice.is_locked

    def explain(self):
        """One readable sentence: what was expected, what arrived, against which band."""
        band_parts = []
        if self.tolerance_pct_applied is not None:
            band_parts.append(f"±{self.tolerance_pct_applied}%")
        if self.tolerance_abs_applied is not None:
            band_parts.append(f"±{self.tolerance_abs_applied}")
        band = " / ".join(band_parts) or "no band"
        pct = f"{self.variance_pct}%" if self.variance_pct is not None else "no percentage"
        return (f"{self.get_variance_type_display()} ({self.get_basis_display()}): expected "
                f"{self.expected_value} → actual {self.actual_value} "
                f"({self.variance_abs}, {pct}) against band {band}.")

    def _derive(self):
        """``(variance_abs, variance_pct)`` from the two figures on the row.

        Delegated to lane A's ``resolve_tolerance`` with NO bands so the stored figures are
        computed by exactly the arithmetic that judged the row — one source of truth, and the
        band comparison itself stays in the resolver. Imported lazily: ``SupplierInvoices.py``
        imports this module at module level, so the dependency has to stay one-directional.
        """
        from apps.procurement.models.InvoiceVoucherManagement.SupplierInvoices import (
            resolve_tolerance)
        _outcome, variance_abs, variance_pct, _pct_band, _abs_band = resolve_tolerance(
            self.expected_value, self.actual_value)
        return variance_abs, _clamp_pct(variance_pct)

    # -- validation ----------------------------------------------------------------------------

    def clean(self):
        errors = {}
        invoice = self.invoice if self.invoice_id else None

        if invoice is not None and self.tenant_id and invoice.tenant_id != self.tenant_id:
            errors["invoice"] = "That invoice belongs to another workspace."

        if self.invoice_line_id:
            # Otherwise a crafted row points at a line on another workspace's invoice and the
            # register then testifies about a document this workspace cannot open.
            if invoice is None or self.invoice_line.invoice_id != invoice.pk:
                errors["invoice_line"] = "That line belongs to a different invoice."

        if self.dispute_id and self.tenant_id and self.dispute.tenant_id != self.tenant_id:
            errors["dispute"] = "That dispute belongs to another workspace."

        for name in ("tolerance_abs_applied", "tolerance_pct_applied"):
            value = getattr(self, name)
            if value is not None and _finite(value) is None:
                errors[name] = "Enter a number."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        # Derived on EVERY write, not only on create: the two figures are a pure function of
        # expected/actual and must never be hand-fed by a caller.
        self.variance_abs, self.variance_pct = self._derive()
        return super().save(*args, **kwargs)

    # -- the single writer ----------------------------------------------------------------------

    @classmethod
    def record(cls, *, invoice, invoice_line=None, variance_type, basis, expected, actual,
               pct_upper=None, pct_lower=None, abs_upper=None, abs_lower=None, message="",
               outcome_override=None, cap=None):
        """Create one exception row — the only way a variance comes into being.

        Called ONLY from ``SupplierInvoice.run_match()``. ``outcome_override`` is the
        unconditional verdict (a missing PO is wrong whatever the numbers say); ``cap="warn"``
        still downgrades it, because a capped check must never block whatever the caller passed.
        """
        from apps.procurement.models.InvoiceVoucherManagement.SupplierInvoices import (
            resolve_tolerance)
        outcome, variance_abs, variance_pct, tol_pct, tol_abs = resolve_tolerance(
            expected, actual, pct_upper=pct_upper, pct_lower=pct_lower, abs_upper=abs_upper,
            abs_lower=abs_lower, cap=cap)
        if outcome_override:
            outcome = "warn" if cap == "warn" and outcome_override == "block" else outcome_override

        obj = cls(
            tenant_id=invoice.tenant_id,
            invoice=invoice,
            invoice_line=invoice_line,
            variance_type=variance_type,
            basis=basis,
            expected_value=_as_decimal(expected),
            actual_value=_as_decimal(actual),
            variance_abs=variance_abs,
            variance_pct=_clamp_pct(variance_pct),
            tolerance_pct_applied=tol_pct,
            tolerance_abs_applied=tol_abs,
            outcome=outcome,
            # A duplicate message is built by joining the match reasons and can overrun the
            # column; truncating here keeps run_match() from dying on the message it wrote.
            message=(message or "")[:255],
        )
        obj.save(force_insert=True)
        return obj

    # -- the one human verb --------------------------------------------------------------------

    def accept(self, user):
        """AP has looked at the exception and accepts it. Returns ``bool``.

        Open and disputed rows can be accepted; a row already settled by a memo, a short payment
        or a cancellation cannot be re-opened by this route — the settlement is a document in
        its own right. ``user`` is accepted for symmetry with the other verbs; authorship of the
        decision is recorded by the caller's audit row.
        """
        if self.resolution not in ("open", "disputed"):
            return False
        self.resolution = "accepted"
        self.save(update_fields=["resolution", "updated_at"])
        return True
