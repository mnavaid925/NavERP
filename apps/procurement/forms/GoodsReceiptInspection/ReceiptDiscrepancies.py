"""Procurement 6.12 Goods Receipt & Inspection — ReceiptDiscrepancy forms.

Four shapes, one per thing a user actually does:

* ``ReceiptDiscrepancyForm`` — the finding itself, raised against a receipt (or one of its lines).
* ``DiscrepancyNotifyForm`` — the "we told the supplier" stamp, the ONLY writer of
  ``vendor_notified_on``.
* ``DiscrepancyResolveForm`` — the closure, where the remedy is MANDATORY: Ariba's rule is that
  rejecting goods means saying replace-or-credit, and "resolved, reason unknown" is not a record.
* ``DiscrepancyCancelForm`` — withdrawing a finding, reason optional (a mis-count needs no essay).

Every tenant-scoped dropdown is narrowed in ``__init__`` AND re-checked in ``clean()``: a narrowed
``<select>`` is UX, not an authorization boundary — a crafted POST carries whatever pk it likes.
``goods_receipt_line`` is the sharp one: ``scm.GoodsReceiptLine`` has NO tenant column (it is
scoped through its header), so ``TenantModelForm`` cannot auto-scope it and an unnarrowed field
would both DISPLAY and ACCEPT another workspace's line.
"""
from django import forms
from django.core.exceptions import NON_FIELD_ERRORS, ValidationError

from apps.procurement.forms._common import *  # noqa: F401,F403
from apps.procurement.forms._common import TenantUniqueMixin, _reject_foreign
from apps.inventory.models import QuarantineOrder
from apps.procurement.models import ReceiptDiscrepancy, ReturnToVendor
from apps.scm.models import GoodsReceiptLine, GoodsReceiptNote, NonConformance


class ReceiptDiscrepancyForm(TenantUniqueMixin, TenantModelForm):
    """The finding.

    ``TenantUniqueMixin`` comes FIRST so ``instance.tenant`` is stamped before ``full_clean()``:
    ``ReceiptDiscrepancy.clean()`` compares every chosen FK's tenant against ``self.tenant_id``,
    and without the stamp every CREATE would be falsely rejected as cross-tenant.

    EXCLUDED and why — every one of these is system-owned, and a field that reaches the form
    reaches a crafted POST:

    * ``tenant`` — stamped by the view / ``TenantUniqueMixin``, never chosen.
    * ``number`` — assigned once by ``TenantNumbered.save()``.
    * ``status`` — moved ONLY by ``notify_vendor`` / ``resolve`` / ``cancel``; on the form it
      would let a POST jump straight to ``resolved`` without ever recording a remedy.
    * ``vendor_notified_on`` — stamped by ``notify_vendor``; typed here it would claim we told
      the supplier on a day we did not.
    * ``resolved_at`` / ``resolved_by`` / ``resolution_notes`` — the closure block, written only
      by ``resolve`` / ``cancel``. ``resolved_at`` in particular is a MOMENT: rendered through a
      date widget it would silently truncate to midnight (L22).
    * ``created_by`` — the signed-in user, never choosable.
    * ``created_at`` / ``updated_at`` — system timestamps.
    """

    class Meta:
        model = ReceiptDiscrepancy
        fields = [
            "goods_receipt", "goods_receipt_line", "kind", "severity", "quantity_affected",
            "item_description", "sku_hint", "lot_number", "serial_number", "expiry_date",
            "description", "evidence", "evidence_url", "remedy", "vendor_reference",
            "nonconformance", "quarantine_order", "return_to_vendor",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"class": "form-textarea", "rows": 4}),
            "quantity_affected": forms.NumberInput(attrs={"class": "form-input",
                                                          "step": "0.0001", "min": "0"}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)

        if tenant is None:
            # A tenant-less user (the superuser has tenant=None) must never be offered another
            # workspace's rows, and must never be able to post one either.
            for name in ("goods_receipt", "goods_receipt_line", "nonconformance",
                         "quarantine_order", "return_to_vendor"):
                if name in self.fields:
                    self.fields[name].queryset = self.fields[name].queryset.none()
        else:
            # A cancelled receipt is not something to raise a claim against — but keep the
            # instance's own receipt in range on EDIT so a saved row still validates.
            receipts = (GoodsReceiptNote.objects.filter(tenant=tenant)
                        .exclude(status="cancelled")
                        .select_related("purchase_order", "purchase_order__vendor")
                        .order_by("-receipt_date", "-id"))
            if "goods_receipt" in self.fields:
                self.fields["goods_receipt"].queryset = receipts

            # THE tenant hole: GoodsReceiptLine has no tenant column, so TenantModelForm's
            # auto-scoping skips it entirely. Scope through the header, and narrow to the
            # instance's own receipt once there is one — a line from a different receipt is
            # refused by the model's clean() anyway, so offering it is only a way to fail.
            lines = (GoodsReceiptLine.objects.filter(goods_receipt__tenant=tenant)
                     .select_related("goods_receipt", "po_line")
                     .order_by("-goods_receipt_id", "id"))
            if self.instance.pk and self.instance.goods_receipt_id:
                lines = lines.filter(goods_receipt_id=self.instance.goods_receipt_id)
            self.fields["goods_receipt_line"].queryset = lines

            self.fields["nonconformance"].queryset = (
                NonConformance.objects.filter(tenant=tenant).order_by("-id"))
            self.fields["quarantine_order"].queryset = (
                QuarantineOrder.objects.filter(tenant=tenant).order_by("-id"))
            self.fields["return_to_vendor"].queryset = (
                ReturnToVendor.objects.filter(tenant=tenant)
                .select_related("vendor").order_by("-id"))

        # Blank copies the receipt line's text in ReceiptDiscrepancy.save() — don't demand it.
        self.fields["item_description"].required = False

        if self.instance.pk:
            # Re-pointing a saved finding at a different receipt would orphan its
            # ``goods_receipt_line`` FK (that line belongs to the OLD receipt). The form drops the
            # field entirely rather than trusting the template to hide it; the edit page renders
            # the receipt read-only instead.
            self.fields.pop("goods_receipt", None)

    def clean_evidence(self):
        """Extension allowlist then size cap, the house rule for every upload.

        The two constants are imported LOCALLY and are deliberately NOT re-exported from
        ``apps/procurement/forms/__init__.py``: ``forms/CatalogManagement/UploadBatches.py``
        already defines its own, different ``MAX_UPLOAD_BYTES`` (2 MB), and a package-level
        re-export would make which limit applies depend on import order.
        """
        import os

        from apps.core.forms._common import ALLOWED_DOC_EXTENSIONS, MAX_UPLOAD_BYTES

        upload = self.cleaned_data.get("evidence")
        if upload and hasattr(upload, "name"):
            ext = os.path.splitext(upload.name)[1].lower()
            if ext not in ALLOWED_DOC_EXTENSIONS:
                raise forms.ValidationError(f"File type '{ext}' is not allowed.")
            if getattr(upload, "size", 0) and upload.size > MAX_UPLOAD_BYTES:
                raise forms.ValidationError(
                    f"File exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit.")
        return upload

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned,
                        ["goods_receipt", "nonconformance", "quarantine_order",
                         "return_to_vendor"])

        # ``goods_receipt_line`` cannot go through _reject_foreign — it has no ``tenant``
        # attribute at all, so the shared helper would compare None against the tenant pk and
        # reject every valid line. Walk its header instead.
        line = cleaned.get("goods_receipt_line")
        if line is not None:
            tenant_id = self.tenant.pk if self.tenant is not None else None
            if line.goods_receipt.tenant_id != tenant_id:
                self.add_error("goods_receipt_line",
                               "That record belongs to another workspace.")
        return cleaned

    def add_error(self, field, error):
        """Re-key a model-level error onto a field this form actually renders.

        ``goods_receipt`` is popped out of ``self.fields`` on EDIT (see ``__init__``), but
        ``Model.clean()`` still validates it and ``ModelForm._post_clean`` funnels that error
        dict straight into ``add_error(None, …)`` — where Django raises ``ValueError`` for a key
        with no matching field, i.e. a 500 on POST instead of a rendered message. Anything keyed
        on a dropped field becomes a non-field error here (the AdvancedShipmentNoticeForm
        precedent, same hazard, same fix).
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


class DiscrepancyNotifyForm(forms.Form):
    """The "we told the supplier" stamp. The ONLY writer of ``vendor_notified_on``.

    Both fields are optional: the common case is a buyer clicking the button the moment they send
    the email, and the supplier's own case number usually arrives days later.
    """

    vendor_reference = forms.CharField(
        label="Supplier reference", required=False, max_length=64,
        widget=forms.TextInput(attrs={"class": "form-input"}),
        help_text="The supplier's own claim / case number, if they have given one",
    )
    vendor_notified_on = forms.DateField(
        label="Notified on", required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-input"},
                               format="%Y-%m-%d"),
        input_formats=["%Y-%m-%d"],
        help_text="Blank = today",
    )


class DiscrepancyResolveForm(forms.Form):
    """The closure. The remedy is REQUIRED — a rejected delivery closed without saying
    replace-or-credit leaves both sides with a different memory of what was agreed, and the
    notes are what a supplier scorecard dispute is later argued from."""

    remedy = forms.ChoiceField(
        choices=ReceiptDiscrepancy.REMEDY_CHOICES, required=True,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    resolution_notes = forms.CharField(
        label="Resolution notes", required=True, max_length=2000,
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
    )


class DiscrepancyCancelForm(forms.Form):
    """Withdrawing a finding. The reason is optional — the usual cause is a mis-count found
    minutes later, and demanding an essay for that just trains people to type "n/a"."""

    resolution_notes = forms.CharField(
        label="Reason", required=False, max_length=2000,
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
    )
