"""Procurement 6.11 Order Fulfillment & Tracking — DeliverySchedule forms.

Two forms: the instalment itself, and the one-question "split this line into N" console form.

``scm.PurchaseOrderLine`` carries NO ``tenant`` column of its own (it hangs off the order), so
``TenantModelForm``'s automatic FK scoping cannot reach it — every ``po_line`` queryset is
narrowed explicitly through ``purchase_order__tenant``, and ``clean()`` re-checks the chosen line
against the workspace because a narrowed ``<select>`` is UX, never an authorization boundary.
"""
from apps.core.models import OrgUnit
from apps.procurement.forms._common import *  # noqa: F401,F403
from apps.procurement.forms._common import TenantUniqueMixin, _reject_foreign
from apps.procurement.models import AdvancedShipmentNotice, DeliverySchedule
from apps.scm.models import PurchaseOrderLine


#: ``type="date"`` so the browser renders a real date picker; ``TenantModelForm`` already swaps
#: DateFields onto this widget, but the explicit attrs keep the contract readable at a glance.
_DATE_WIDGET_ATTRS = {"type": "date", "class": "form-input"}


class DeliveryScheduleForm(TenantUniqueMixin, TenantModelForm):
    """Create / edit one instalment.

    ``status`` is deliberately INCLUDED — see the model docstring: this ladder stamps no
    timestamps and no who-stamps off its own status, so there is nothing for a verb method to
    protect and the field is an honest ``<select>``.
    """

    class Meta:
        model = DeliverySchedule
        # EXCLUDED and why: ``tenant`` is stamped by the CRUD helper (and by TenantUniqueMixin
        # before full_clean, so the model's cross-tenant checks have something to compare
        # against); ``number`` is assigned once inside TenantNumbered.save(); ``created_by`` is
        # system authorship stamped by the create view; ``created_at`` / ``updated_at`` are
        # system timestamps a DateInput would silently truncate (L22).
        fields = ["po_line", "sequence", "scheduled_quantity", "need_by_date",
                  "promised_quantity", "promised_date", "status", "ship_to", "delivery_mode",
                  "asn", "change_reason", "notes"]

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        self.fields["po_line"].queryset = (
            PurchaseOrderLine.objects.filter(purchase_order__tenant=tenant)
            .select_related("purchase_order").order_by("-purchase_order_id", "id")
            if tenant is not None else PurchaseOrderLine.objects.none()
        )
        self.fields["ship_to"].queryset = (
            OrgUnit.objects.filter(tenant=tenant) if tenant is not None
            else OrgUnit.objects.none()
        )
        self.fields["asn"].queryset = (
            AdvancedShipmentNotice.objects.filter(tenant=tenant).select_related("purchase_order")
            if tenant is not None else AdvancedShipmentNotice.objects.none()
        )
        for name in ("need_by_date", "promised_date"):
            self.fields[name].widget = forms.DateInput(attrs=dict(_DATE_WIDGET_ATTRS),
                                                       format="%Y-%m-%d")
            self.fields[name].input_formats = ["%Y-%m-%d"]

    def clean(self):
        cleaned = super().clean()
        # Crafted-POST re-check for the FKs whose target model HAS a tenant column…
        _reject_foreign(self, cleaned, ["ship_to", "asn"])
        # …and an explicit one for the FK whose target does NOT (PurchaseOrderLine has no direct
        # ``tenant`` attribute, so _reject_foreign cannot see it — it hangs off the order).
        line = cleaned.get("po_line")
        if line is not None:
            tenant_id = self.tenant.pk if self.tenant is not None else None
            if line.purchase_order.tenant_id != tenant_id:
                self.add_error("po_line", "That record belongs to another workspace.")
        return cleaned


class DeliveryScheduleSplitForm(forms.Form):
    """The four facts a split genuinely needs: which line, how many drops, starting when, how
    far apart. Quantities are computed by ``split_po_line()`` rather than re-typed."""

    po_line = forms.ModelChoiceField(
        label="PO line to split",
        queryset=PurchaseOrderLine.objects.none(),  # narrowed to the workspace in __init__
        widget=forms.Select(attrs={"class": "form-select"}),
        help_text="The ordered line whose remaining quantity is divided into instalments.",
    )
    instalments = forms.IntegerField(
        min_value=2, max_value=DeliverySchedule.MAX_SPLIT_INSTALMENTS, initial=3,
        widget=forms.NumberInput(attrs={"class": "form-input", "min": 2,
                                        "max": DeliverySchedule.MAX_SPLIT_INSTALMENTS}),
        help_text="How many deliveries the remaining quantity is divided into.",
    )
    first_date = forms.DateField(
        label="First need-by date",
        widget=forms.DateInput(attrs=dict(_DATE_WIDGET_ATTRS), format="%Y-%m-%d"),
        input_formats=["%Y-%m-%d"],
    )
    interval_days = forms.IntegerField(
        min_value=1, max_value=365, initial=14,
        widget=forms.NumberInput(attrs={"class": "form-input", "min": 1, "max": 365}),
        help_text="Days between one instalment's need-by date and the next.",
    )

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        self.fields["po_line"].queryset = (
            PurchaseOrderLine.objects.filter(purchase_order__tenant=tenant)
            .select_related("purchase_order").order_by("-purchase_order_id", "id")
            if tenant is not None else PurchaseOrderLine.objects.none()
        )
