"""Procurement 6.11 Order Fulfillment & Tracking — Backorder forms.

The record form captures what a buyer genuinely knows about a shortfall (how much, why, what was
promised); the two small action forms carry the reschedule and the closure note. ``status``,
``reschedule_count``, ``closed_at``, ``closure_note`` and ``alert`` are NOT on any form — they move
only through the model's verb methods, so a crafted POST cannot close a backorder or rewrite how
many times its promise has already slipped.
"""
from django import forms

from apps.procurement.forms._common import *  # noqa: F401,F403
from apps.procurement.forms._common import TenantUniqueMixin, _reject_foreign
from apps.procurement.models import AdvancedShipmentNotice, Backorder, DeliverySchedule
from apps.scm.models import PurchaseOrderLine


class BackorderForm(TenantUniqueMixin, TenantModelForm):
    """Record / amend one outstanding shortfall against a purchase order line.

    ``TenantUniqueMixin`` comes FIRST so ``instance.tenant`` is stamped before ``full_clean()``:
    ``Backorder.clean()`` compares every chosen FK's tenant against ``self.tenant_id``, and without
    the stamp every CREATE would be falsely rejected as cross-tenant (the CRUD helper assigns the
    real tenant only after ``is_valid()``).
    """

    class Meta:
        model = Backorder
        # EXCLUDED and why:
        #   tenant            — stamped by the create view / TenantUniqueMixin, never chooseable.
        #   number            — assigned once by TenantNumbered.save().
        #   status            — moves ONLY through reschedule()/fulfil()/cancel().
        #   reschedule_count  — stamped by reschedule(); a buyer must not type their slip count down.
        #   closed_at,
        #   closure_note      — stamped by the closing verbs.
        #   alert             — set by raise_alert(); the link is a system fact, not an input.
        #   created_by        — system authorship.
        #   created_at,
        #   updated_at        — system timestamps.
        fields = ["po_line", "delivery_schedule", "asn", "quantity_backordered",
                  "reason", "reason_note", "original_promise_date", "revised_promise_date",
                  "notes"]

    def __init__(self, *args, tenant=None, **kwargs):
        # Forward `tenant` — TenantModelForm stores it as self.tenant, which BOTH the automatic
        # FK scoping and _reject_foreign() below read. Dropping it silently disables both.
        super().__init__(*args, tenant=tenant, **kwargs)

        # `po_line` is the one FK TenantModelForm's automatic scoping CANNOT narrow:
        # scm.PurchaseOrderLine has no tenant column of its own (it is scoped through its order),
        # so an unscoped ModelChoiceField would both DISPLAY and ACCEPT another workspace's lines.
        line_qs = PurchaseOrderLine.objects.none()
        if tenant is not None:
            line_qs = (PurchaseOrderLine.objects
                       .filter(purchase_order__tenant=tenant)
                       .select_related("purchase_order")
                       .order_by("-purchase_order_id", "id"))
        self.fields["po_line"].queryset = line_qs

        if tenant is not None:
            # Both of these DO carry a tenant column, so the base class has already scoped them —
            # re-stated explicitly (with ordering + select_related) so the dropdowns read well and
            # the scoping is visible at the point a reviewer looks for it.
            self.fields["delivery_schedule"].queryset = (
                DeliverySchedule.objects.filter(tenant=tenant)
                .select_related("po_line", "po_line__purchase_order")
                .order_by("-id"))
            self.fields["asn"].queryset = (
                AdvancedShipmentNotice.objects.filter(tenant=tenant)
                .select_related("purchase_order").order_by("-id"))
        else:
            self.fields["delivery_schedule"].queryset = DeliverySchedule.objects.none()
            self.fields["asn"].queryset = AdvancedShipmentNotice.objects.none()

        # Date widgets: TenantModelForm already swaps every DateField to
        # DateInput(type="date", class="form-input") AND sets the matching input_formats — replacing
        # the widget here would keep the look and silently drop the parse formats (L22).

    def clean(self):
        cleaned = super().clean()
        # A narrowed <select> is UX, not an authorization boundary: re-check every tenant-scoped FK
        # so a hand-edited POST carrying another workspace's pk renders as a field error.
        _reject_foreign(self, cleaned, ["delivery_schedule", "asn"])
        # po_line cannot go through _reject_foreign — PurchaseOrderLine has no `tenant` attribute,
        # so getattr(chosen, "tenant_id", None) would be None and compare "equal" for a tenant-less
        # user. Its workspace lives one hop up, on the order.
        line = cleaned.get("po_line")
        if line is not None:
            tenant_id = self.tenant.pk if self.tenant is not None else None
            if line.purchase_order.tenant_id != tenant_id:
                self.add_error("po_line", "That record belongs to another workspace.")
        return cleaned


class BackorderRescheduleForm(forms.Form):
    """The supplier has moved the date. Both fields are REQUIRED: a promise that slips without a
    stated reason is exactly the thing this register exists to stop being invisible."""

    revised_promise_date = forms.DateField(
        required=True, label="New promised date",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-input"},
                               format="%Y-%m-%d"),
        input_formats=["%Y-%m-%d"],
    )
    reason_note = forms.CharField(
        required=True, max_length=255, label="Why the date moved",
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
    )


class BackorderCloseForm(forms.Form):
    """Shared by the Fulfil and Cancel POSTs — both close the row and both want the same note."""

    closure_note = forms.CharField(
        required=False, max_length=255, label="Closure note",
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
    )
