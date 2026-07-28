"""SCM 4.10 Returns Management — WarrantyClaim form, its typed cost formset and the two
supplier-response payloads.

``amount_claimed`` is NOT on the cost form: it is computed in ``WarrantyClaimCost.save()`` from
``quantity × unit_amount`` and is ``editable=False`` (§7.7). Shipping all three as inputs is how a
row ends up claiming £120 while its own arithmetic says £100.

§7.6 applies to ``lot_serial`` here as well: ``LotSerial.__str__`` reads ``self.item.sku``.
"""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import TenantUniqueMixin, _supplier_parties
from apps.scm.models import WarrantyClaim, WarrantyClaimCost

ZERO = Decimal("0")


class WarrantyClaimForm(TenantUniqueMixin, TenantModelForm):
    """The claim header.

    EXCLUDES the whole negotiation block (§7.7): ``number`` (auto), ``status``, ``submitted_on``,
    ``responded_on``, ``supplier_response_notes``, ``amount_approved``, ``amount_credited``,
    ``credit_reference``, ``credit_received_on``. Those are written by ``warrantyclaim_submit`` /
    ``_record_response`` / ``_record_credit`` — the supplier's side of a two-party negotiation is
    not something we type into a form and then claim they said.
    """

    class Meta:
        model = WarrantyClaim
        fields = ["supplier", "item", "quantity_claimed", "lot_serial", "serial_reference",
                  "return_authorization", "nonconformance", "goods_receipt", "purchase_date",
                  "warranty_start", "warranty_end", "failure_date", "usage_context",
                  "defect_classification", "supplier_rma_number", "submission_channel",
                  "response_due_on", "description", "notes"]
        widgets = {
            "purchase_date": forms.DateInput(attrs={"type": "date"}),
            "warranty_start": forms.DateInput(attrs={"type": "date"}),
            "warranty_end": forms.DateInput(attrs={"type": "date"}),
            "failure_date": forms.DateInput(attrs={"type": "date"}),
            "response_due_on": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "supplier" in self.fields:
            self.fields["supplier"].queryset = _supplier_parties(self.tenant)
        if "lot_serial" in self.fields:
            # §7.6 — LotSerial.__str__ reads item.sku.
            qs = self.fields["lot_serial"].queryset.select_related("item")
            if self.instance.item_id:
                qs = qs.filter(item_id=self.instance.item_id)
            self.fields["lot_serial"].queryset = qs.order_by("item__sku", "number")
        if "item" in self.fields:
            self.fields["item"].queryset = (
                self.fields["item"].queryset.select_related("uom").order_by("sku"))
        if "return_authorization" in self.fields:
            # ReturnAuthorization.__str__ reads customer.name — the same one-query-per-option trap.
            self.fields["return_authorization"].queryset = (
                self.fields["return_authorization"].queryset.select_related("customer")
                .order_by("-requested_on", "-id"))
        if "nonconformance" in self.fields:
            self.fields["nonconformance"].queryset = (
                self.fields["nonconformance"].queryset.select_related("item"))
        if "goods_receipt" in self.fields:
            self.fields["goods_receipt"].queryset = (
                self.fields["goods_receipt"].queryset.select_related("purchase_order"))

    def clean(self):
        cleaned = super().clean()
        item, lot = cleaned.get("item"), cleaned.get("lot_serial")
        if item is not None and lot is not None and lot.item_id != item.pk:
            self.add_error("lot_serial",
                           f"{lot.number} belongs to {lot.item.sku}, not {item.sku}.")
        start, end = cleaned.get("warranty_start"), cleaned.get("warranty_end")
        if start and end and end < start:
            self.add_error("warranty_end", "The cover ends before it starts.")
        purchased, failed = cleaned.get("purchase_date"), cleaned.get("failure_date")
        if purchased and failed and failed < purchased:
            self.add_error("failure_date", "The unit failed before it was bought.")
        return cleaned


class WarrantyClaimCostForm(TenantModelForm):
    """One typed cost line — part, labour, freight, external service, admin or other.

    ``amount_claimed`` is absent by design (computed in ``save()``). ``amount_approved`` IS here
    because a partial approval — accept the part, refuse the labour — is the normal real outcome
    and the whole reason this child table exists rather than a flat ``claim_value`` column.
    """

    class Meta:
        model = WarrantyClaimCost
        fields = ["cost_type", "description", "quantity", "unit_amount", "amount_approved"]

    def clean(self):
        cleaned = super().clean()
        claimed = (cleaned.get("quantity") or ZERO) * (cleaned.get("unit_amount") or ZERO)
        if (cleaned.get("amount_approved") or ZERO) > claimed:
            self.add_error("amount_approved",
                           f"The supplier cannot approve more than the {claimed} claimed on this "
                           "line.")
        return cleaned


class BaseWarrantyClaimCostFormSet(forms.BaseInlineFormSet):
    """§7.2 applied to the cost lines.

    ``can_delete`` stays True because a DRAFT claim is a working document and dropping a mistyped
    cost line has to be possible. What is guarded instead — and guarded explicitly, not by relying
    on ``extra=0`` — is any structural change once the claim has left draft: the row count must
    match what is on file, and nothing may be deleted. A submitted claim's cost lines are what the
    supplier was shown.
    """

    def clean(self):
        super().clean()
        claim = self.instance
        locked = bool(claim.pk) and claim.status not in WarrantyClaim.EDITABLE_STATUSES
        on_file = claim.costs.count() if claim.pk else 0
        if self.initial_form_count() != on_file:
            raise ValidationError(
                "The cost lines on this page no longer match the ones on file — reload the claim "
                "and try again.")
        if locked:
            for form in self.forms:
                if (getattr(form, "cleaned_data", None) or {}).get("DELETE"):
                    raise ValidationError(
                        f"{claim.number} has been submitted — its cost lines are what the "
                        "supplier was shown and cannot be removed.")
            for form in self.extra_forms:
                if getattr(form, "cleaned_data", None) and form.has_changed():
                    raise ValidationError(
                        f"{claim.number} has been submitted — raise a new claim rather than "
                        "adding cost lines to this one.")

        rows = [form for form in self.forms
                if getattr(form, "cleaned_data", None) and not form.cleaned_data.get("DELETE")]
        if not rows:
            raise ValidationError(
                "A claim with no costs asks the supplier for nothing — add at least one line.")


WarrantyClaimCostFormSet = inlineformset_factory(
    WarrantyClaim, WarrantyClaimCost, form=WarrantyClaimCostForm,
    formset=BaseWarrantyClaimCostFormSet, extra=1, can_delete=True, max_num=50,
    validate_max=True,
)


class WarrantyClaimResponseForm(forms.Form):
    """What the supplier came back with.

    ``status`` is a CHOICE here rather than derived, because "approved 80% of it" and "approved all
    of it, at a lower rate" are different answers and only the supplier knows which they gave. The
    view cross-checks the amount against the claim total and refuses an approval of more than was
    asked for — the one thing that would be nonsense whatever they said.
    """

    outcome = forms.ChoiceField(
        choices=[("approved", "Approved in full"), ("partially_approved", "Partially approved"),
                 ("rejected", "Rejected")])
    amount_approved = forms.DecimalField(max_digits=14, decimal_places=2, min_value=ZERO,
                                         initial=ZERO)
    responded_on = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}),
                                   help_text="Defaults to today when left blank")
    supplier_rma_number = forms.CharField(required=False, max_length=64,
                                          label="Their claim reference")
    supplier_response_notes = forms.CharField(required=False, max_length=4000,
                                              widget=forms.Textarea(attrs={"rows": 3}))

    def clean(self):
        cleaned = super().clean()
        outcome = cleaned.get("outcome")
        amount = cleaned.get("amount_approved") or ZERO
        if outcome == "rejected" and amount > ZERO:
            self.add_error("amount_approved",
                           "A rejection approves nothing — leave the amount at zero.")
        if outcome in ("approved", "partially_approved") and amount <= ZERO:
            self.add_error("amount_approved",
                           "An approval with no money on it is a rejection — record the amount.")
        return cleaned


class WarrantyClaimCreditForm(forms.Form):
    """The credit the supplier actually gave us.

    **Records only.** ``accounting.Bill`` has no ``kind`` field, so there is no vendor-credit
    document to draft and SCM drafts nothing (see the model docstring). This is the figure a
    recovery-rate report is computed from.
    """

    amount_credited = forms.DecimalField(max_digits=14, decimal_places=2, min_value=ZERO)
    credit_reference = forms.CharField(max_length=64,
                                       label="Their credit note / reference number")
    credit_received_on = forms.DateField(required=False,
                                         widget=forms.DateInput(attrs={"type": "date"}),
                                         help_text="Defaults to today when left blank")
