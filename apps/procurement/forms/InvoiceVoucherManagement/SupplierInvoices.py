"""Procurement 6.13 Invoice & Voucher Management — SupplierInvoice forms.

Three shapes, one per thing a user actually does:

* ``SupplierInvoiceForm`` — the header a human keys in. Everything money-shaped, everything
  match-shaped and everything ledger-shaped is EXCLUDED: those are system-owned, and a field
  that reaches the form reaches a crafted POST.
* ``SupplierInvoiceLineFormSet`` — the lines, inline, prefix ``lines`` (the inlineformset default,
  because the child FK declares ``related_name="lines"``).
* ``CaptureUploadForm`` — the **Capture Invoice** upload. It is a plain ``Form``: it validates a
  file, it does not model one. The ``core.Document`` it produces is created by the view.

Tenant discipline: every dropdown is narrowed to the workspace in ``__init__`` AND re-checked in
``clean()`` (a narrowed ``<select>`` is UX, not an authorization boundary). ``scm.PurchaseOrder``
and ``scm.GoodsReceiptNote`` both carry a ``tenant`` column, so ``TenantModelForm`` scopes them —
but a tenant-less user (the superuser is ``tenant=None``) is scoped to nothing, so the form empties
every queryset rather than offering another workspace's rows.
"""
from decimal import Decimal, InvalidOperation

from django.core.exceptions import NON_FIELD_ERRORS, ValidationError

from apps.procurement.forms._common import *  # noqa: F401,F403
from apps.procurement.forms._common import TenantUniqueMixin, _reject_foreign
# NOT-YET-WIRED entities of this SAME sub-module: import the entity MODULE directly — a
# ``from apps.procurement.forms import X`` is a star-import cycle until the Integrator wires the
# sub-package, and it would 500 at URLconf import.
from apps.procurement.forms.InvoiceVoucherManagement.SupplierInvoiceLines import SupplierInvoiceLineForm
from apps.procurement.models.InvoiceVoucherManagement.SupplierInvoiceLines import SupplierInvoiceLine
from apps.procurement.models.InvoiceVoucherManagement.SupplierInvoices import SupplierInvoice
from apps.scm.models import GoodsReceiptNote, PurchaseOrder

#: L35 — every hand-parsed money figure is checked for finiteness AND capped at what its column
#: can hold, because "1e400" parses cleanly and then dies inside the driver.
_MONEY_CEILING = Decimal(10) ** 16          # Decimal(18, 2)

#: ``fx_rate`` is Decimal(14, 6) — eight integer digits, not sixteen.
_FX_CEILING = Decimal(10) ** 8


def _safe_decimal(raw, ceiling, label):
    """Return ``(value, error_or_None)``. L35: is_finite(), magnitude cap, explicit rejection branch."""
    try:
        value = Decimal(str(raw).strip())
    except (InvalidOperation, ValueError, ArithmeticError, TypeError):
        return None, f"Enter a valid number for {label}."
    if not value.is_finite():
        return None, f"Enter a finite number for {label}."
    if abs(value) >= ceiling:
        return None, f"{label} is too large."
    return value, None


class SupplierInvoiceForm(TenantUniqueMixin, TenantModelForm):
    """The invoice header.

    ``TenantUniqueMixin`` comes FIRST so ``instance.tenant`` is stamped before ``full_clean()``:
    ``SupplierInvoice.clean()`` compares every chosen FK's tenant against ``self.tenant_id``, and
    without the stamp every CREATE would be falsely rejected as cross-tenant.

    EXCLUDED and why — every one is system-owned:

    * ``tenant`` — stamped by the view / ``TenantUniqueMixin``.
    * ``number`` — assigned once by ``TenantNumbered.save()``.
    * ``bill`` / ``journal_entry`` — written ONLY by ``approve()``. On a form they would let a POST
      point an invoice at another invoice's ledger entry.
    * ``source_submission`` / ``duplicate_of`` — written by the capture flow and the duplicate
      review; both are evidence, not choices.
    * ``invoice_number_norm`` — derived from ``invoice_number`` in ``save()``.
    * ``due_date`` / ``discount_date`` / ``discount_expiry_date`` — derived from the payment term.
      A typed due date is exactly how a discount gets silently missed.
    * ``subtotal`` / ``tax_total`` / ``total`` / ``amount_paid`` — derived from the lines.
    * ``match_basis`` / ``match_status`` / ``match_notes`` — written by ``run_match()`` and the
      block/override verbs.
    * ``status`` — moved ONLY by the verb methods.
    * ``source`` / ``extraction_confidence`` / ``extraction_raw_text`` — capture provenance, stamped
      by the capture view.
    * ``approved_by`` / ``approved_at`` — the approval, never choosable.
    """

    class Meta:
        model = SupplierInvoice
        fields = ["vendor", "purchase_order", "goods_receipt", "payment_term", "currency",
                  "tax_code", "invoice_type", "invoice_number", "external_ref", "invoice_date",
                  "posting_date", "discount_base", "discount_grace_days", "fx_rate", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)

        if tenant is None:
            # A tenant-less user must not be OFFERED another workspace's rows, and must not be
            # able to post one either.
            for name in ("vendor", "purchase_order", "goods_receipt", "payment_term", "tax_code",
                         "currency", "document", "source_submission"):
                if name in self.fields and name != "currency":
                    self.fields[name].queryset = self.fields[name].queryset.none()
        else:
            # Ordered newest-first: the invoice being keyed is almost always against a recent
            # order and a recent receipt. TenantModelForm has already narrowed these; this is
            # presentation, not authorization.
            #
            # NEVER slice these. ``ModelChoiceField.to_python`` calls ``queryset.get(pk=…)``, and a
            # sliced queryset raises ``TypeError: Cannot filter a query once a slice has been
            # taken`` — which Django swallows into ``invalid_choice``, so every submitted order or
            # receipt came back as "Select a valid choice" and a PO-matched invoice could not be
            # saved at all. Narrow with a filter if the dropdown ever needs bounding.
            if "purchase_order" in self.fields:
                self.fields["purchase_order"].queryset = (
                    PurchaseOrder.objects.filter(tenant=tenant)
                    .select_related("vendor").order_by("-order_date", "-id"))
            if "goods_receipt" in self.fields:
                self.fields["goods_receipt"].queryset = (
                    GoodsReceiptNote.objects.filter(tenant=tenant)
                    .select_related("purchase_order").order_by("-receipt_date", "-id"))
            # currency is deliberately left ALONE — accounting.Currency is GLOBAL, so scoping it
            # to a tenant would empty the dropdown.

        if self.instance.pk and self.instance.status not in SupplierInvoice.EDITABLE_STATUSES:
            # Once an invoice has been captured, re-pointing it at a different order or receipt
            # would orphan its lines (they belong to the OLD document). Dropped from the form
            # rather than trusted to the template to hide.
            self.fields.pop("purchase_order", None)
            self.fields.pop("goods_receipt", None)

    def add_error(self, field, error):
        """Re-key a model-level error onto a field this form actually renders.

        ``purchase_order`` / ``goods_receipt`` are popped out of ``self.fields`` on a non-editable
        invoice, but ``Model.clean()`` still validates them and ``ModelForm._post_clean`` funnels
        that error dict straight into ``add_error(None, …)`` — where Django raises ``ValueError``
        for a key with no matching field, i.e. a 500 on POST instead of a rendered message
        (the 6.12 ``ReceiptDiscrepancyForm`` precedent, same hazard, same fix).
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
        _reject_foreign(self, cleaned,
                        ["vendor", "purchase_order", "goods_receipt", "payment_term", "tax_code"])

        # L40 §3 — vendor agreement, enforced here as well as in the model so the error lands on
        # the field the user can actually change.
        vendor = cleaned.get("vendor")
        order = cleaned.get("purchase_order")
        if vendor is not None and order is not None and order.vendor_id != vendor.pk:
            self.add_error("purchase_order", "That purchase order belongs to a different vendor.")
        receipt = cleaned.get("goods_receipt")
        if vendor is not None and receipt is not None and receipt.purchase_order_id:
            if receipt.purchase_order.vendor_id != vendor.pk:
                self.add_error("goods_receipt", "That goods receipt belongs to a different vendor.")

        raw_rate = cleaned.get("fx_rate")
        if raw_rate is not None:
            value, error = _safe_decimal(raw_rate, _FX_CEILING, "Conversion rate")
            if error:
                self.add_error("fx_rate", error)
            else:
                cleaned["fx_rate"] = value

        return cleaned


#: The lines formset. ``prefix`` is left at the inlineformset default, which is the child FK's
#: accessor name — ``lines`` — so the template's form loop and the POST body agree without either
#: side hard-coding it twice.
SupplierInvoiceLineFormSet = inlineformset_factory(
    SupplierInvoice, SupplierInvoiceLine, form=SupplierInvoiceLineForm,
    fields=["po_line", "receipt_line", "item", "description", "sku_hint", "uom_hint", "quantity",
            "unit_price", "tax_rate_pct", "gl_account", "tax_code"],
    extra=1, can_delete=True,
)


class CaptureUploadForm(forms.Form):
    """Stage one of **Capture Invoice** — the file.

    The page must never claim to "OCR" (the contract is explicit): ``pdfplumber`` is not installed
    in any current deployment, so the designed path is a manual keying form with an honest warning.
    """

    document_file = forms.FileField(
        label="Invoice file",
        widget=forms.FileInput(attrs={"class": "form-input", "accept": ".pdf"}),
        help_text="A PDF with a text layer — scanned images cannot be read automatically.",
    )

    def clean_document_file(self):
        # Imported LOCALLY and deliberately NOT taken from the procurement forms package, where
        # CatalogManagement defines its own, different MAX_UPLOAD_BYTES (2 MB) — a package-level
        # re-export would make which limit applies depend on import order.
        import os

        from apps.core.forms._common import ALLOWED_DOC_EXTENSIONS, MAX_UPLOAD_BYTES

        upload = self.cleaned_data.get("document_file")
        if upload and hasattr(upload, "name"):
            ext = os.path.splitext(upload.name)[1].lower()
            if ext not in ALLOWED_DOC_EXTENSIONS:
                raise forms.ValidationError(f"File type '{ext}' is not allowed.")
            if getattr(upload, "size", 0) and upload.size > MAX_UPLOAD_BYTES:
                raise forms.ValidationError(
                    f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.")
        return upload
