"""SCM 4.8 Manufacturing — WorkOrder form, component formset and the two action forms."""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import TenantUniqueMixin
from apps.scm.models import BillOfMaterials, WorkOrder, WorkOrderComponent

ZERO = Decimal("0")


class WorkOrderForm(TenantUniqueMixin, TenantModelForm):
    """The run header.

    EXCLUDES `number` (auto), `status` / `actual_start` / `actual_end` (the lifecycle actions own
    them), and `quantity_produced` / `quantity_scrapped` / `produced_unit_cost` / `released_by`
    (written only by the posting actions — see the model's single-writer rule). Every FK here
    carries its own tenant, so the base class scopes the dropdowns.

    `bom` is narrowed to active recipes for the chosen item, but ONLY on edit — on create the item
    is not known until the form is bound, so the full active list is offered and `WorkOrder.clean()`
    is what actually refuses a BOM that produces a different item.
    """

    class Meta:
        model = WorkOrder
        fields = ["item", "uom", "bom", "quantity_planned", "order_policy", "sales_order",
                  "work_center", "priority", "planned_start", "planned_end", "schedule_direction",
                  "due_date", "component_location", "output_location", "output_lot_serial", "notes"]
        widgets = {
            "planned_start": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "planned_end": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # TenantModelForm scopes these querysets but adds no select_related, and both these models'
        # __str__ dereferences a SECOND FK (LotSerial → item.sku, SalesOrder → customer.name). One
        # query per rendered <option> — on a lot-tracked tenant that alone made this page unusable.
        for name, related in (("sales_order", "customer"), ("output_lot_serial", "item")):
            if name in self.fields:
                self.fields[name].queryset = self.fields[name].queryset.select_related(related)
        if "bom" in self.fields:
            base = self.fields["bom"].queryset
            item_id = getattr(self.instance, "item_id", None)
            scope = Q(status="active")
            if item_id is not None:
                scope &= Q(item_id=item_id)
            # Keep the row's own BOM selectable while editing even if it was since marked obsolete —
            # otherwise the bound form fails validation on a field the user never touched.
            current_id = getattr(self.instance, "bom_id", None)
            if current_id is not None:
                scope |= Q(pk=current_id)
            self.fields["bom"].queryset = base.filter(scope).select_related("item")


class WorkOrderComponentForm(TenantModelForm):
    """One snapshotted material line.

    `quantity_issued` is NOT a field — the issue action is its only writer, and the template renders
    it as read-only text. Exposing it as an input would let a planner type a consumption the stock
    ledger never saw.
    """

    class Meta:
        model = WorkOrderComponent
        fields = ["sequence", "item", "quantity_required", "uom", "lot_serial", "issue_method",
                  "unit_cost", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Formset fields are deep-copied per form, so an unrelated lot_serial queryset re-resolves
        # every option's __str__ (which reads item.sku) once per row on the page.
        if "lot_serial" in self.fields:
            self.fields["lot_serial"].queryset = (
                self.fields["lot_serial"].queryset.select_related("item"))


# extra=3, matching BOMLineFormSet. With extra=0 a component line could never be hand-added or
# re-added after deletion, which made the "no BOM, hand-entered components" path unreachable — and
# the release guard's "add or explode at least one component" message impossible to satisfy.
WorkOrderComponentFormSet = inlineformset_factory(
    WorkOrder, WorkOrderComponent, form=WorkOrderComponentForm, extra=3, can_delete=True,
)


class WorkOrderScheduleForm(forms.Form):
    """The scheduling helper — arithmetic only, deliberately not a solver.

    Forward fills `planned_end` from the start plus the BOM's in-house lead time; backward fills
    `planned_start` from the due date minus it. Finite-capacity scheduling that levels across work
    centres is a later pass (4.11 territory); pretending to do it here with a one-line formula would
    be worse than being explicit that this is date arithmetic.
    """

    direction = forms.ChoiceField(choices=WorkOrder.SCHEDULE_DIRECTION_CHOICES)
    anchor_date = forms.DateField(
        widget=forms.DateInput(attrs={"type": "date"}),
        help_text="Start date when scheduling forward; due date when scheduling backward")
    lead_time_days = forms.IntegerField(
        min_value=0, max_value=3650, required=False,
        help_text="Defaults to the BOM's in-house production time")


class WorkOrderReportForm(forms.Form):
    """Report finished output — the form behind the production posting.

    Both quantities are optional-but-not-both-zero: a run can report pure scrap. The work order's
    remaining quantity is validated in the view, where the row is locked.
    """

    quantity_good = forms.DecimalField(max_digits=14, decimal_places=4, min_value=ZERO,
                                       required=False, initial=ZERO)
    quantity_scrapped = forms.DecimalField(max_digits=14, decimal_places=4, min_value=ZERO,
                                           required=False, initial=ZERO)
    backflush = forms.BooleanField(
        required=False, initial=True,
        help_text="Also consume the components marked 'backflush' in proportion to the output")

    def clean(self):
        cleaned = super().clean()
        good = cleaned.get("quantity_good") or ZERO
        scrapped = cleaned.get("quantity_scrapped") or ZERO
        if good <= ZERO and scrapped <= ZERO:
            raise ValidationError("Report a good quantity, a scrapped quantity, or both.")
        return cleaned
