"""SCM 4.4 Warehouse Management — PickTask form + line formset."""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.models import PickTask, PickTaskLine


class PickTaskForm(TenantModelForm):
    class Meta:
        model = PickTask
        # `status`/`picked_at`/`packed_at` EXCLUDED — they advance via the release/pick/pack actions.
        fields = ["strategy", "zone", "wave_ref", "assigned_to", "ship_to", "notes"]


class PickTaskPackForm(forms.Form):
    """Packing details captured when a picked task is packed.

    Label DATA only — rendering the label and talking to a carrier is 4.6 TMS.
    """

    package_count = forms.IntegerField(min_value=1, required=False,
                                       widget=forms.NumberInput(attrs={"class": "form-input"}))
    package_weight = forms.DecimalField(min_value=Decimal("0"), required=False, decimal_places=3,
                                        widget=forms.NumberInput(attrs={"class": "form-input"}))
    tracking_ref = forms.CharField(max_length=64, required=False,
                                   widget=forms.TextInput(attrs={"class": "form-input"}),
                                   help_text="Carrier tracking reference, if you already have one")


class PickTaskLineForm(TenantModelForm):
    class Meta:
        model = PickTaskLine
        fields = ["item", "lot_serial", "from_location", "quantity_requested",
                  "quantity_picked", "notes"]

    def clean(self):
        cleaned = super().clean()
        item, lot = cleaned.get("item"), cleaned.get("lot_serial")
        requested = cleaned.get("quantity_requested")
        picked = cleaned.get("quantity_picked")
        if item and lot and lot.item_id != item.pk:
            self.add_error("lot_serial", f"{lot.number} belongs to {lot.item.sku}, not {item.sku}.")
        # Over-picking is a data-entry error, not a short pick — a picker can bring less than asked
        # for, never more than the line called for.
        if requested is not None and picked is not None and picked > requested:
            self.add_error("quantity_picked", "Picked quantity cannot exceed the requested quantity.")
        return cleaned


PickTaskLineFormSet = inlineformset_factory(
    PickTask, PickTaskLine, form=PickTaskLineForm, extra=3, can_delete=True,
)
