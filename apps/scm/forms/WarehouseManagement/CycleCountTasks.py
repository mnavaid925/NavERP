"""SCM 4.4 Warehouse Management — CycleCountTask form + count-sheet formset."""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.models import CycleCountTask, CycleCountTaskLine


class CycleCountTaskForm(TenantModelForm):
    class Meta:
        model = CycleCountTask
        # `status` and every timestamp EXCLUDED — they advance via start/complete/reconcile/cancel.
        # `adjustment` is set by the reconcile action.
        fields = ["location", "scheduled_date", "count_method", "assigned_to", "notes"]


class CycleCountTaskLineForm(TenantModelForm):
    """A count-sheet row. Only ``counted_quantity`` is the counter's to fill in.

    ``expected_quantity`` is deliberately NOT a form field: it is snapshotted server-side when the
    count starts. Exposing it would turn a blind count into a "confirm the number on screen" exercise
    and let a counter paper over a real discrepancy.
    """

    class Meta:
        model = CycleCountTaskLine
        fields = ["item", "lot_serial", "counted_quantity", "notes"]

    def clean(self):
        cleaned = super().clean()
        item, lot = cleaned.get("item"), cleaned.get("lot_serial")
        if item and lot and lot.item_id != item.pk:
            self.add_error("lot_serial", f"{lot.number} belongs to {lot.item.sku}, not {item.sku}.")
        return cleaned


CycleCountTaskLineFormSet = inlineformset_factory(
    CycleCountTask, CycleCountTaskLine, form=CycleCountTaskLineForm, extra=3, can_delete=True,
)
