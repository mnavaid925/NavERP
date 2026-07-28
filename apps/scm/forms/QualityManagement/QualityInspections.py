"""SCM 4.9 Quality Management — QualityInspection form, result formset and the two action forms."""
from datetime import date

from django.core.validators import MaxValueValidator, MinValueValidator

from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import (TenantUniqueMixin, _customer_parties, _employee_parties,
                                    _supplier_parties)
from apps.scm.models import InspectionResult, QualityInspection

ZERO = Decimal("0")

#: An inspection type and the plan type that serves it. Kept here rather than on the model because
#: it exists solely to narrow a dropdown — the model never needs to translate between the two.
_PLAN_TYPE_FOR = {
    "incoming": "incoming_receipt",
    "in_process": "in_process",
    "outgoing": "outgoing_shipment",
    "periodic_stock": "periodic_stock",
}

#: Bound every free-typed date the way 4.8's schedule form does. Nothing here does date arithmetic
#: today, but an unbounded 9999-12-31 has already turned an ordinary POST into an uncaught
#: OverflowError once in this module, and bounding the input is cheaper than catching it.
_MIN_DATE = date(2000, 1, 1)
_MAX_DATE = date(2100, 12, 31)


class QualityInspectionForm(TenantUniqueMixin, TenantModelForm):
    """The inspection header.

    EXCLUDES `number` (auto), `status` / `usage_decision` / `action_taken` (the lifecycle and
    decision actions own them) and the three CoA stamp columns (the issue action owns them) — see
    the model's single-writer rule.

    The four quantities ARE typed: they are the inspector's observations, not derived figures.
    `clean()` mirrors the model's arithmetic so a bad pair lands on the field instead of surfacing
    as a full-form error.
    """

    class Meta:
        model = QualityInspection
        fields = ["plan", "inspection_type", "goods_receipt", "work_order", "shipment", "item",
                  "lot_serial", "location", "supplier", "quantity_inspected", "sample_size",
                  "quantity_accepted", "quantity_rejected", "inspector", "inspected_on",
                  "supplier_coa_reference", "notes"]
        widgets = {"inspected_on": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        chosen_type = self._chosen("inspection_type") or "incoming"
        chosen_item = self._chosen_id("item")

        if "plan" in self.fields:
            scope = Q(is_active=True, plan_type=_PLAN_TYPE_FOR.get(chosen_type, "incoming_receipt"))
            # Keep the row's own plan selectable while editing even if it was since deactivated —
            # otherwise the bound form fails validation on a field the user never touched.
            if self.instance.plan_id:
                scope |= Q(pk=self.instance.plan_id)
            self.fields["plan"].queryset = self.fields["plan"].queryset.filter(scope)

        # LotSerial.__str__ dereferences item.sku and WorkOrder.__str__ dereferences item — one
        # query per rendered <option> without these. On a lot-tracked tenant that alone cost 140
        # queries on a single 4.8 page. Shipment.__str__ is number + direction, no walk, so it
        # needs no select_related.
        if "lot_serial" in self.fields:
            lots = self.fields["lot_serial"].queryset.select_related("item")
            if chosen_item:
                # A lot belongs to exactly one item, so offering the whole tenant's lots is both a
                # long list and a validation error waiting to happen.
                lots = lots.filter(item_id=chosen_item)
            elif self.instance.lot_serial_id:
                lots = lots.filter(pk=self.instance.lot_serial_id)
            else:
                lots = lots.none()
            self.fields["lot_serial"].queryset = lots
        if "work_order" in self.fields:
            self.fields["work_order"].queryset = (
                self.fields["work_order"].queryset
                .filter(Q(status__in=("released", "in_progress", "completed"))
                        | Q(pk=self.instance.work_order_id))
                .select_related("item"))
        if "goods_receipt" in self.fields:
            self.fields["goods_receipt"].queryset = self.fields["goods_receipt"].queryset.filter(
                Q(status="received") | Q(pk=self.instance.goods_receipt_id))
        if "shipment" in self.fields:
            shipments = self.fields["shipment"].queryset
            if chosen_type == "outgoing":
                shipments = shipments.filter(Q(direction="outbound")
                                             | Q(pk=self.instance.shipment_id))
            self.fields["shipment"].queryset = shipments
        if "supplier" in self.fields:
            self.fields["supplier"].queryset = _supplier_parties(self.tenant)
        if "inspector" in self.fields:
            self.fields["inspector"].queryset = _employee_parties(self.tenant)

    def _chosen(self, name):
        """The submitted value on a bound form, else the instance's — dropdowns narrow on both."""
        if self.is_bound:
            return (self.data.get(self.add_prefix(name)) or "").strip()
        return getattr(self.instance, name, None)

    def _chosen_id(self, name):
        """The submitted FK id on a bound form, else the instance's. ``None`` for junk input."""
        if self.is_bound:
            raw = (self.data.get(self.add_prefix(name)) or "").strip()
            return int(raw) if raw.isdigit() else None
        return getattr(self.instance, f"{name}_id", None)

    def clean(self):
        cleaned = super().clean()
        inspected = cleaned.get("quantity_inspected") or ZERO
        accepted = cleaned.get("quantity_accepted") or ZERO
        rejected = cleaned.get("quantity_rejected") or ZERO
        if accepted + rejected > inspected:
            self.add_error("quantity_accepted",
                           f"Accepted ({accepted}) plus rejected ({rejected}) exceeds the "
                           f"{inspected} inspected.")
        if (cleaned.get("sample_size") or ZERO) > inspected:
            self.add_error("sample_size", "The sample cannot be larger than the quantity inspected.")
        item = cleaned.get("item")
        lot = cleaned.get("lot_serial")
        if item and lot and lot.item_id != item.pk:
            self.add_error("lot_serial",
                           f"{lot.number} belongs to {lot.item.sku}, not {item.sku}.")
        return cleaned


class InspectionResultForm(TenantModelForm):
    """One result row — only what the inspector types.

    The whole snapshot block (name, type, unit, limits, test method, the three flags) is
    `editable=False` on the model and rendered as read-only text by the template. `result` IS a
    field, but ``InspectionResult.save()`` overwrites it for a measurement: see ``_evaluate``.
    """

    class Meta:
        model = InspectionResult
        fields = ["measured_value", "text_value", "result", "notes"]


class BaseInspectionResultFormSet(forms.BaseInlineFormSet):
    """Only one rule lives here, and the omission is deliberate.

    "Every mandatory row must carry a value" is enforced by ``qualityinspection_complete``, NOT
    here: a half-filled in-progress inspection has to stay savable, or an inspector cannot put the
    clipboard down. What the formset does guard is a row claiming a verdict a measurement cannot
    support.
    """

    def clean(self):
        super().clean()
        # The snapshot is the record a certificate rests on, so it may not be hand-extended.
        # `extra=0` does NOT prevent this: on a bound formset `initial_form_count()` comes from the
        # POSTed management form, so a crafted post can declare extra rows. An injected row would
        # take defaults for the whole snapshot block (it is editable=False, so construct_instance
        # skips it) — a blank name, no limits — and `_evaluate` returns "pass" for a measurement
        # with a value and no limits. There is no legitimate flow that submits an unsaved row.
        for form in self.forms:
            if form.instance.pk is None and form.has_changed():
                raise ValidationError(
                    "Result rows are snapshotted from the plan by Generate results — they cannot "
                    "be added here.")
        for form in self.forms:
            if not getattr(form, "cleaned_data", None) or form.cleaned_data.get("DELETE"):
                continue
            if getattr(form.instance, "characteristic_type", None) != "measurement":
                continue
            verdict = form.cleaned_data.get("result")
            if verdict and verdict != "pending" and form.cleaned_data.get("measured_value") is None:
                form.add_error("measured_value",
                               f"Record the measured value for {form.instance.characteristic_name} "
                               "— its verdict is derived from the specification limits.")


# extra=0: result rows are SNAPSHOTTED from the plan by generate_results(), never hand-added — an
# extra blank row would have no characteristic name, no limits and nothing to evaluate against.
#
# can_delete=False for the same reason, and it is the stronger half: `generate_results()`
# short-circuits on `self.results.exists()`, so a removed row can NEVER be regenerated, and both
# `evaluated_result` and `coa_blockers()` only ever count the survivors. Deleting the one failing
# characteristic would silently turn a failed inspection into a certifiable one, with nothing left
# in the record to show a row had been there.
InspectionResultFormSet = inlineformset_factory(
    QualityInspection, InspectionResult, form=InspectionResultForm,
    formset=BaseInspectionResultFormSet, extra=0, can_delete=False, max_num=200, validate_max=True,
)


class QualityInspectionDecisionForm(forms.Form):
    """The SAP-style usage decision — a sign-off, which is why its view is tenant-admin gated."""

    usage_decision = forms.ChoiceField(
        choices=[choice for choice in QualityInspection.USAGE_DECISION_CHOICES
                 if choice[0] != "pending"],
        help_text="What happens to the lot now the verdict is in")
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}),
                            max_length=2000,
                            help_text="Appended to the inspection's notes with the decision")


class QualityInspectionCoAIssueForm(forms.Form):
    """Issue the certificate — who it is issued to, and on what date.

    The recipient is scoped to CUSTOMER parties: a Certificate of Analysis is a document sent with
    a shipment, so a supplier or a carrier in that dropdown would only ever be a mis-click.
    """

    coa_issued_to = forms.ModelChoiceField(queryset=Party.objects.none(), required=False,
                                           label="Issued to",
                                           help_text="The customer receiving the certificate")
    issued_on = forms.DateField(
        required=False, widget=forms.DateInput(attrs={"type": "date"}),
        validators=[MinValueValidator(_MIN_DATE), MaxValueValidator(_MAX_DATE)],
        help_text="Defaults to now when left blank")

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.tenant = tenant
        self.fields["coa_issued_to"].queryset = _customer_parties(tenant)
