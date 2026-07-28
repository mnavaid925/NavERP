"""SCM 4.9 Quality Management — NonConformance form + the MRB disposition payload."""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import (TenantUniqueMixin, _employee_parties, _supplier_parties)
from apps.scm.models import NonConformance
from apps.scm.models._base import q2

ZERO = Decimal("0")


class NonConformanceForm(TenantUniqueMixin, TenantModelForm):
    """The finding header.

    EXCLUDES `number` (auto), `status` / `closed_on`, `quarantine_applied` (the quarantine and
    release actions own it) and the whole MRB decision block (the disposition action owns it).

    `cost_of_quality` IS a field and the form is its ONLY writer. It is defaulted — not computed —
    to ``quantity × the item's average cost`` on an unbound form, and after that the human's figure
    stands; nothing ever recomputes it. That is the difference between a default and a derived
    column, and it is why this one is editable while `disposition_quantity` is not.
    """

    class Meta:
        model = NonConformance
        fields = ["source", "inspection", "goods_receipt", "work_order", "shipment", "audit",
                  "item", "lot_serial", "location", "supplier", "quantity_affected", "uom",
                  "defect_category", "severity", "title", "description", "detected_by",
                  "detected_on", "containment_action", "cost_of_quality", "owner", "due_date",
                  "notes"]
        widgets = {
            "detected_on": forms.DateInput(attrs={"type": "date"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # LotSerial.__str__ reads item.sku and WorkOrder.__str__ reads item — one query per
        # rendered <option> without these. QualityInspection.__str__ reads item.sku too.
        for name, related in (("lot_serial", "item"), ("work_order", "item"),
                              ("inspection", "item")):
            if name in self.fields:
                self.fields[name].queryset = self.fields[name].queryset.select_related(related)
        if "lot_serial" in self.fields and self.instance.item_id:
            self.fields["lot_serial"].queryset = self.fields["lot_serial"].queryset.filter(
                item_id=self.instance.item_id)
        if "supplier" in self.fields:
            self.fields["supplier"].queryset = _supplier_parties(self.tenant)
        for name in ("detected_by", "owner"):
            if name in self.fields:
                self.fields[name].queryset = _employee_parties(self.tenant)
        # The QT9 "dollars and cents to poor quality" starting point — offered once, on an unbound
        # form that already knows its item, then owned by whoever types over it.
        if (not self.is_bound and "cost_of_quality" in self.fields
                and not self.initial.get("cost_of_quality")
                and self.instance.item_id and self.instance.quantity_affected):
            self.initial["cost_of_quality"] = q2(
                (self.instance.quantity_affected or ZERO) * (self.instance.item.average_cost or ZERO))

    def clean(self):
        cleaned = super().clean()
        source = cleaned.get("source")
        item = cleaned.get("item")
        if source != "audit" and item is None:
            self.add_error("item", "Name the item — only an audit finding may have none.")
        if item is not None and (cleaned.get("quantity_affected") or ZERO) <= ZERO:
            self.add_error("quantity_affected", "Record how many units are affected.")
        detected_on = cleaned.get("detected_on")
        due_date = cleaned.get("due_date")
        if detected_on and due_date and due_date < detected_on:
            self.add_error("due_date", "The due date cannot precede the detection date.")
        lot = cleaned.get("lot_serial")
        if item and lot and lot.item_id != item.pk:
            self.add_error("lot_serial",
                           f"{lot.number} belongs to {lot.item.sku}, not {item.sku}.")
        return cleaned


class NonConformanceDispositionForm(forms.Form):
    """The Material Review Board decision.

    A plain Form: every field it collects is written to an ``editable=False`` column by
    ``nonconformance_disposition`` inside the same transaction that posts the scrap StockMove, so
    the quantity written and the quantity moved are the same number by construction.
    """

    disposition = forms.ChoiceField(
        choices=[choice for choice in NonConformance.DISPOSITION_CHOICES
                 if choice[0] != "pending"])
    disposition_quantity = forms.DecimalField(
        max_digits=14, decimal_places=4, min_value=ZERO, initial=ZERO,
        help_text="Units this decision covers — a scrap posts exactly this many out of stock")
    disposition_notes = forms.CharField(required=False, max_length=4000,
                                        widget=forms.Textarea(attrs={"rows": 3}))
