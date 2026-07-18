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


class BaseCycleCountTaskLineFormSet(forms.BaseInlineFormSet):
    """Once the count has STARTED, the sheet's composition is frozen — only counts may be entered.

    ``expected_quantity`` is snapshotted exactly once, by ``cyclecounttask_start``, over the lines
    that existed AT THAT MOMENT. So a row added afterwards — or an existing row re-pointed at a
    different item — carries the model default of 0 as its "expected", and reconcile would then post
    the entire counted quantity as a found-stock variance: a fabricated `StockAdjustment` against an
    item that was never snapshotted, approved by an admin who has no way to see it from the sheet.
    Freezing the composition is what makes the snapshot mean anything (code + security review found
    this independently). The counter can still type ``counted_quantity`` and ``notes`` — that is the
    whole job — they just can't change WHAT is being counted.
    """

    def __init__(self, *args, lock_sheet=False, **kwargs):
        self.lock_sheet = lock_sheet
        super().__init__(*args, **kwargs)
        if not lock_sheet:
            return
        self.extra = 0  # set before self.forms is built (it is a lazy cached_property)
        for form in self.forms:
            # `disabled` makes Django ignore the POSTed value and keep the initial one, so this
            # holds against a crafted request, not just against the rendered page.
            for name in ("item", "lot_serial"):
                if name in form.fields:
                    form.fields[name].disabled = True
            if "DELETE" in form.fields:
                form.fields["DELETE"].disabled = True

    def clean(self):
        super().clean()
        if not self.lock_sheet:
            return
        # `extra = 0` shapes the rendered page; a hand-rolled POST can still inflate the management
        # form's TOTAL_FORMS, so the rule is enforced here too.
        if any(f.instance.pk is None and f.has_changed() for f in self.forms):
            raise ValidationError(
                "This count has already started, so its item list is frozen — you can enter counts "
                "but not add items. Cancel it and schedule a new count to count something else."
            )


CycleCountTaskLineFormSet = inlineformset_factory(
    CycleCountTask, CycleCountTaskLine, form=CycleCountTaskLineForm,
    formset=BaseCycleCountTaskLineFormSet, extra=3, can_delete=True,
)
