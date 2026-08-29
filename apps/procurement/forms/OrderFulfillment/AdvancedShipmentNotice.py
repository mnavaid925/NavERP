"""Procurement 6.11 Order Fulfillment & Tracking — AdvancedShipmentNotice forms.

Four shapes, one per thing a user actually does:

* ``AdvancedShipmentNoticeForm`` — the header the buyer records from the supplier's notice.
* ``AsnLineFormSet`` — what is on the truck, line by line, against the order's own lines.
* ``AsnDeliveryConfirmForm`` — the arrival + proof-of-delivery block, which is the ONLY way the
  POD fields are ever written (they are ``editable=False`` on the model for exactly that reason).
* ``AsnCancelForm`` — a required reason, because an abandoned notice with no explanation is
  indistinguishable from a mistake.

Every tenant-scoped dropdown is narrowed in ``__init__`` AND re-checked in ``clean()``: a narrowed
``<select>`` is UX, not an authorization boundary — a crafted POST carries whatever pk it likes.
"""
from django import forms
from django.core.exceptions import NON_FIELD_ERRORS
from django.db.models import Q

from apps.procurement.forms._common import *  # noqa: F401,F403
from apps.procurement.forms._common import TenantUniqueMixin, _reject_foreign
from apps.procurement.models import AdvancedShipmentNotice, AsnLine
from apps.scm.models import Carrier, PurchaseOrder, Shipment


class AdvancedShipmentNoticeForm(TenantUniqueMixin, TenantModelForm):
    """The ASN header.

    EXCLUDED and why — every one of these is system-owned, and a field that reaches the form
    reaches a crafted POST:

    * ``tenant`` — stamped by ``crud_create`` / ``TenantUniqueMixin``, never chosen.
    * ``number`` — assigned once by ``TenantNumbered.save()``.
    * ``status`` — moved ONLY by ``submit`` / ``mark_in_transit`` / ``confirm_delivery`` /
      ``cancel``; on the form it would let a POST jump straight to ``delivered``.
    * ``delivered_at`` / ``arrival_condition`` / ``pod_reference`` /
      ``received_signature_name`` / ``confirmed_by`` — the proof-of-delivery block, written only
      by ``asn_confirm_delivery``. ``delivered_at`` in particular is a MOMENT: rendered through a
      date widget it would silently truncate to midnight (L22).
    * ``created_by`` — the signed-in user, never choosable.
    * ``submitted_at`` / ``cancelled_at`` / ``cancellation_reason`` — verb stamps.
    * ``created_at`` / ``updated_at`` — system timestamps.
    """

    class Meta:
        model = AdvancedShipmentNotice
        fields = [
            "purchase_order", "supplier_reference", "source", "ship_date",
            "expected_delivery_date", "carrier", "carrier_name", "tracking_number", "shipment",
            "bill_of_lading_ref", "container_ref", "freight_terms", "package_count",
            "pallet_count", "gross_weight_kg", "volume_cbm", "notes",
        ]
        widgets = {
            "ship_date": forms.DateInput(attrs={"type": "date", "class": "form-input"},
                                         format="%Y-%m-%d"),
            "expected_delivery_date": forms.DateInput(
                attrs={"type": "date", "class": "form-input"}, format="%Y-%m-%d"),
            "notes": forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)

        # A notice is only meaningful against an order goods can still be booked against. On EDIT
        # the order may have moved on since (fully received, closed) — keep it in the queryset so
        # an existing row still renders and validates instead of failing on its own stored value.
        orders = PurchaseOrder.objects.filter(tenant=tenant)
        receivable = orders.filter(status__in=PurchaseOrder.RECEIVABLE_STATUSES)
        current_id = getattr(self.instance, "purchase_order_id", None)
        if current_id:
            receivable = orders.filter(
                Q(status__in=PurchaseOrder.RECEIVABLE_STATUSES) | Q(pk=current_id)
            )
        # ``PurchaseOrder.__str__`` is ``f"{number} · {vendor}"`` — every rendered <option> hops
        # to core.Party for the vendor name, so an unbounded dropdown costs 1 + P queries without
        # this select_related. The chained-__str__ case belongs on the FORM queryset, not just on
        # the list view's.
        self.fields["purchase_order"].queryset = (receivable.select_related("vendor")
                                                  .order_by("-order_date", "-id"))

        self.fields["carrier"].queryset = (Carrier.objects.filter(tenant=tenant)
                                           .select_related("party").order_by("party__name"))
        # An ASN tracks goods coming IN. An outbound shipment in this dropdown would be a
        # different movement entirely; the model's clean() re-checks the same rule.
        self.fields["shipment"].queryset = (Shipment.objects
                                            .filter(tenant=tenant, direction="inbound")
                                            .order_by("-id"))

        if self.instance.pk:
            # Re-pointing a saved ASN at a different order would orphan every AsnLine's po_line
            # FK (they belong to the OLD order). The form drops the field entirely rather than
            # trusting the template to hide it; the edit page shows the order read-only instead.
            self.fields.pop("purchase_order", None)

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["purchase_order", "carrier", "shipment"])
        return cleaned

    def add_error(self, field, error):
        """Re-key a model-level error onto a field this form actually renders.

        ``purchase_order`` is popped out of ``self.fields`` on EDIT (see ``__init__``), but
        ``Model.clean()`` still validates it and ``ModelForm._post_clean`` funnels that error
        dict straight into ``add_error(None, …)`` — where Django raises ``ValueError`` for a key
        with no matching field, i.e. a 500 on POST instead of a rendered message. Anything keyed
        on a dropped field becomes a non-field error here.
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


class AsnLineForm(forms.ModelForm):
    """One declared line. A PLAIN ModelForm on purpose — ``AsnLine`` carries no tenant of its
    own (it is scoped through its parent ASN), so there is no tenant queryset for
    ``TenantModelForm`` to narrow. The ``po_line`` dropdown is narrowed by the FORMSET, which is
    the only layer that knows the parent's purchase order."""

    class Meta:
        model = AsnLine
        fields = [
            "po_line", "item_description", "sku_hint", "uom_hint", "quantity_shipped",
            "package_ref", "lot_number", "serial_number", "expiry_date", "country_of_origin",
            "notes",
        ]
        widgets = {
            "po_line": forms.Select(attrs={"class": "form-select"}),
            "item_description": forms.TextInput(attrs={"class": "form-input"}),
            "sku_hint": forms.TextInput(attrs={"class": "form-input"}),
            "uom_hint": forms.TextInput(attrs={"class": "form-input"}),
            "quantity_shipped": forms.NumberInput(attrs={"class": "form-input", "step": "0.0001",
                                                         "min": "0.0001"}),
            "package_ref": forms.TextInput(attrs={"class": "form-input"}),
            "lot_number": forms.TextInput(attrs={"class": "form-input"}),
            "serial_number": forms.TextInput(attrs={"class": "form-input"}),
            "expiry_date": forms.DateInput(attrs={"type": "date", "class": "form-input"},
                                           format="%Y-%m-%d"),
            "country_of_origin": forms.TextInput(attrs={"class": "form-input"}),
            "notes": forms.TextInput(attrs={"class": "form-input"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # The widget renders %Y-%m-%d for <input type="date">; accept exactly that back.
        self.fields["expiry_date"].input_formats = ["%Y-%m-%d"]
        # Blank copies the PO line's text in AsnLine.save() — don't demand it up front.
        self.fields["item_description"].required = False


class BaseAsnLineFormSet(forms.BaseInlineFormSet):
    """Narrows every row's ``po_line`` to the parent ASN's own order, and re-checks it.

    The narrowing lives here rather than on the form because the purchase order is only known
    once the formset has its instance. The crafted-POST re-check in ``clean()`` still matters:
    a hand-edited POST can carry any line pk at all, and a line from another order (or another
    workspace) must land as a field error, never as a saved row.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        order_id = getattr(self.instance, "purchase_order_id", None)
        if order_id:
            order_lines = self.instance.purchase_order.lines.all()
            for form in self.forms:
                if "po_line" in form.fields:
                    form.fields["po_line"].queryset = order_lines

    def clean(self):
        super().clean()
        order_id = getattr(self.instance, "purchase_order_id", None)
        if not order_id:
            return
        seen = set()
        for form in self.forms:
            if not hasattr(form, "cleaned_data"):
                continue
            data = form.cleaned_data
            if data.get("DELETE"):
                # A row being dropped declares nothing — it must not block its replacement.
                continue
            chosen = data.get("po_line")
            if chosen is None:
                continue
            if chosen.purchase_order_id != order_id:
                form.add_error("po_line", "That line belongs to a different purchase order.")
            elif chosen.pk in seen:
                # Two live rows against one line would double-count the shipped quantity and
                # make the short/over verdict meaningless — refuse the ambiguity.
                form.add_error("po_line", "This PO line is declared by more than one row.")
            seen.add(chosen.pk)


#: ``max_num`` caps a crafted management form at a sane row count — every accepted row is a write.
AsnLineFormSet = inlineformset_factory(
    AdvancedShipmentNotice, AsnLine, form=AsnLineForm, formset=BaseAsnLineFormSet,
    extra=1, can_delete=True, max_num=50, validate_max=True,
)


class AsnDeliveryConfirmForm(forms.Form):
    """The arrival record. The ONLY writer of the ASN's proof-of-delivery block.

    Also rendered hand-built (same field NAMES) as the inline confirm on the delivery-confirmation
    board — which is why the names here are a published interface, not an implementation detail.
    """

    delivered_at = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={"type": "datetime-local", "class": "form-input"},
                                   format="%Y-%m-%dT%H:%M"),
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"],
        help_text="Blank = now",
    )
    arrival_condition = forms.ChoiceField(
        choices=AdvancedShipmentNotice.CONDITION_CHOICES, initial="good",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    pod_reference = forms.CharField(
        label="POD reference", required=False, max_length=64,
        widget=forms.TextInput(attrs={"class": "form-input"}),
    )
    received_signature_name = forms.CharField(
        label="Received / signed by", required=False, max_length=120,
        widget=forms.TextInput(attrs={"class": "form-input"}),
    )


class AsnCancelForm(forms.Form):
    """Why the notice was abandoned. Required — a cancelled ASN with no reason reads as a data
    error rather than a decision, and 6.12's receiving needs to know which it was."""

    cancellation_reason = forms.CharField(
        label="Reason", required=True, max_length=2000,
        widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 2}),
    )
