"""Procurement 6.13 Invoice & Voucher Management — InvoiceDispute form.

One shape: ``InvoiceDisputeForm``, the raise-or-edit form.

Everything the system owns is EXCLUDED, and each exclusion is a deliberate one:

* ``tenant`` — stamped by the view / ``TenantUniqueMixin``.
* ``number`` — assigned once by ``TenantNumbered.save()``.
* ``supplier`` — denormalised from ``invoice.vendor`` in ``InvoiceDispute.save()``. Offered as a
  field it would let a POST argue a dispute against one supplier while pointing at another's
  invoice.
* ``status`` — moved ONLY by the verb methods (``editable=False`` as well).
* ``resolution`` / ``resolution_note`` / ``resolved_at`` — written by ``resolve()``, never typed.
* ``raised_by`` / ``raised_at`` — the authorship stamp.
* ``credit_memo_invoice`` — written by the resolve view when it mints a memo.

Tenant discipline: every dropdown is narrowed to the workspace in ``__init__`` AND re-checked in
``clean()`` (a narrowed ``<select>`` is UX, not an authorization boundary). ``SupplierInvoice``
carries a ``tenant`` column so ``TenantModelForm`` scopes it; ``SupplierInvoiceLine`` does NOT, so
it is narrowed through its header — and re-checked the same way, because
``_reject_foreign`` compares ``tenant_id`` on the row itself and would reject every line.

A saved dispute cannot be re-pointed: ``invoice`` and ``invoice_line`` are POPPED on edit, so a
crafted POST cannot move an existing argument onto another invoice.
"""
from decimal import Decimal, InvalidOperation

from django.core.exceptions import NON_FIELD_ERRORS, ValidationError

from apps.procurement.forms._common import *  # noqa: F401,F403
from apps.procurement.forms._common import TenantUniqueMixin, _reject_foreign
# NOT-YET-WIRED entities of this SAME sub-module: import the entity MODULE directly, never
# ``from apps.procurement.models import X`` — the sub-package is not wired until the Integrator
# lands it and a package-level re-export is a star-import cycle at URLconf import.
from apps.procurement.models.InvoiceVoucherManagement.InvoiceDisputes import InvoiceDispute
from apps.procurement.models.InvoiceVoucherManagement.SupplierInvoiceLines import SupplierInvoiceLine
from apps.procurement.models.InvoiceVoucherManagement.SupplierInvoices import SupplierInvoice

#: L35 — ``disputed_amount`` is Decimal(14, 2), so a magnitude check has to happen before the
#: figure is compared or written; ``1e400`` parses cleanly and then dies inside the driver.
_MONEY_CEILING = Decimal(10) ** 12


def _finite(value):
    """``value`` as a finite ``Decimal``, or ``None`` (L35/L11)."""
    try:
        number = Decimal(value if value is not None else Decimal("0"))
    except (InvalidOperation, ValueError, TypeError, ArithmeticError):
        return None
    return number if number.is_finite() else None


def _as_decimal(value):
    """``value`` as a usable ``Decimal`` — ``ZERO`` for anything unusable."""
    number = _finite(value)
    return ZERO if number is None else number


class InvoiceDisputeForm(TenantUniqueMixin, TenantModelForm):
    """Raise or amend a dispute against a supplier invoice.

    ``TenantUniqueMixin`` comes FIRST so ``instance.tenant`` is stamped before ``full_clean()``:
    ``InvoiceDispute.clean()`` compares the invoice's and the supplier's tenant against
    ``self.tenant_id``, and without the stamp every CREATE would be falsely rejected as
    cross-tenant.
    """

    class Meta:
        model = InvoiceDispute
        fields = ["invoice", "invoice_line", "reason_code", "supplier_contact",
                  "disputed_amount", "description", "assigned_to", "due_date"]
        widgets = {
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)

        if tenant is None:
            # A tenant-less user (the superuser) must not be OFFERED another workspace's rows and
            # must not be able to post one either.
            for name in ("invoice", "invoice_line"):
                self.fields[name].queryset = self.fields[name].queryset.none()
        else:
            # Newest first: the invoice being disputed is almost always a recent one.
            # TenantModelForm has already scoped ``invoice`` (SupplierInvoice HAS a tenant);
            # this is presentation, not authorization.
            self.fields["invoice"].queryset = (
                SupplierInvoice.objects.filter(tenant=tenant)
                .select_related("vendor").order_by("-invoice_date", "-id"))
            # SupplierInvoiceLine has NO tenant column — it is scoped through its header, and
            # narrowed to the disputed invoice's own lines once the dispute exists.
            rows = (SupplierInvoiceLine.objects.filter(invoice__tenant=tenant)
                    .select_related("invoice").order_by("-id"))
            if self.instance.pk and self.instance.invoice_id:
                rows = rows.filter(invoice_id=self.instance.invoice_id)
            self.fields["invoice_line"].queryset = rows
            # ``assigned_to`` targets ``accounts.User``, whose nullable ``tenant`` makes it
            # auto-scoped by TenantModelForm.

        if self.instance.pk:
            # A saved dispute must not be re-pointed at another invoice — its reason, its amount
            # and its variance evidence all describe the document it was raised on. Dropped from
            # the form rather than trusted to the template to hide.
            self.fields.pop("invoice", None)
            self.fields.pop("invoice_line", None)

    def add_error(self, field, error):
        """Re-key a model-level error onto a field this form actually renders.

        ``invoice`` / ``invoice_line`` are popped out of ``self.fields`` on edit, but
        ``Model.clean()`` still validates them and ``ModelForm._post_clean`` funnels that error
        dict straight into ``add_error(None, …)`` — where Django raises ``ValueError`` for a key
        with no matching field, i.e. a 500 on POST instead of a rendered message (the 6.12
        ``ReceiptDiscrepancyForm`` precedent, same hazard, same fix).
        """
        if field is None and isinstance(error, ValidationError) and hasattr(error, "error_dict"):
            remapped = {}
            for name, messages in error.error_dict.items():
                key = name if (name == NON_FIELD_ERRORS or name in self.fields) else NON_FIELD_ERRORS
                remapped.setdefault(key, []).extend(messages)
            error = ValidationError(remapped)
        elif field is not None and field != NON_FIELD_ERRORS and field not in self.fields:
            field = None
        super().add_error(field, error)

    def clean(self):
        cleaned = super().clean()

        # The crafted-POST re-check. ``invoice`` carries a tenant column of its own;
        # ``invoice_line`` does NOT, so it is checked through the invoice it belongs to —
        # passing it to _reject_foreign would compare a nonexistent ``tenant_id`` and reject
        # every line, valid or not.
        _reject_foreign(self, cleaned, ["invoice"])
        line = cleaned.get("invoice_line")
        if line is not None:
            tenant_id = self.tenant.pk if self.tenant is not None else None
            if line.invoice.tenant_id != tenant_id:
                self.add_error("invoice_line", "That record belongs to another workspace.")

        amount = cleaned.get("disputed_amount")
        if amount is not None:
            value = _finite(amount)
            if value is None or value.copy_abs() >= _MONEY_CEILING:
                self.add_error("disputed_amount",
                               "Enter a disputed amount below 1,000,000,000,000.")
            else:
                cleaned["disputed_amount"] = value
                # ``invoice`` is not a field on edit — the instance's own invoice is what the
                # amount has to be measured against there.
                invoice = cleaned.get("invoice")
                if invoice is None and self.instance.pk and self.instance.invoice_id:
                    invoice = self.instance.invoice
                if invoice is not None and invoice.total is not None:
                    if value > _as_decimal(invoice.total).copy_abs():
                        self.add_error(
                            "disputed_amount",
                            "The disputed amount cannot be more than the invoice total.")

        return cleaned
