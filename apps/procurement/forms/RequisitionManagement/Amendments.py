"""Procurement 6.2 Requisition Management â€” RequisitionAmendments forms.

The request form captures the PROPOSED change (header fields + a line-change formset); the
decide forms capture only the reason, mirroring scm's approve/reject/cancel reason forms.
"""
from django import forms

from apps.procurement.forms._common import *  # noqa: F401,F403
from apps.procurement.forms._common import _reject_foreign
from apps.procurement.models import RequisitionAmendment, RequisitionAmendmentLine


class RequisitionAmendmentForm(TenantModelForm):
    class Meta:
        model = RequisitionAmendment
        # EXCLUDED and why: ``number`` is assigned once by TenantNumbered.save(); ``status``
        # advances through approve/reject; ``requested_by``/``decided_by``/``decided_at``/
        # ``applied_at``/``decision_note`` are system-set by those same actions; ``requisition``
        # is pinned by the URL in the view (never a choosable field).
        fields = ["amendment_type", "reason", "new_required_by", "new_justification"]

    def clean(self):
        cleaned = super().clean()
        # A cancellation carries no proposed changes â€” mirror the model's rule at form level so
        # the user sees it as a field error instead of a 500 from full_clean().
        if cleaned.get("amendment_type") == "cancel":
            for field in ("new_required_by", "new_justification"):
                if cleaned.get(field):
                    self.add_error(field, "A cancellation does not carry proposed changes.")
        return cleaned


class RequisitionAmendmentLineForm(TenantModelForm):
    class Meta:
        model = RequisitionAmendmentLine
        fields = ["action", "target_line", "item_description", "sku_hint", "uom_hint",
                  "quantity", "estimated_unit_price", "needed_by"]


class BaseRequisitionAmendmentLineFormSet(forms.BaseInlineFormSet):
    """Scopes the ``target_line`` dropdown to THIS amendment's requisition and validates each row.

    The queryset narrowing happens here rather than per-form because the parent requisition is
    only known once the formset has its instance; the crafted-POST re-check still matters (a hand-
    edited POST can carry any line pk), so ``clean()`` verifies every chosen target actually
    belongs to the amended requisition.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        requisition = getattr(self.instance, "requisition", None)
        if requisition is not None:
            for form in self.forms:
                if "target_line" in form.fields:
                    form.fields["target_line"].queryset = requisition.lines.all()

    def clean(self):
        super().clean()
        requisition = getattr(self.instance, "requisition", None)
        if requisition is None:
            return
        seen_targets = []
        for form in self.forms:
            if not hasattr(form, "cleaned_data"):
                continue
            data = form.cleaned_data
            if data.get("DELETE"):
                continue  # a row being dropped proposes nothing â€” it must not block its twin
            target = data.get("target_line")
            if target is not None:
                if target.requisition_id != requisition.pk:
                    form.add_error("target_line",
                                   "That line belongs to a different requisition.")
                elif target in seen_targets:
                    # Two live rows against one line would apply in form order and silently keep
                    # only the last (or double-delete) â€” refuse the ambiguity instead.
                    form.add_error("target_line", "This line is targeted by more than one row.")
                seen_targets.append(target)


RequisitionAmendmentLineFormSet = inlineformset_factory(
    RequisitionAmendment, RequisitionAmendmentLine, form=RequisitionAmendmentLineForm,
    # max_num caps a crafted management form at a sane row count â€” each accepted row becomes a
    # line write on approval.
    formset=BaseRequisitionAmendmentLineFormSet, extra=1, can_delete=True, max_num=25, validate_max=True,
)

#: The two decide forms are deliberately plain Forms: they capture a REASON about a decision that
#: has already been made on an existing row â€” there is no model fields behind them beyond
#: decision_note, which only the approve/reject actions write.


class AmendmentDecisionForm(forms.Form):
    """Reason captured when approving or rejecting an amendment (optional on approve)."""

    decision_note = forms.CharField(required=False, max_length=2000,
                                    widget=forms.Textarea(attrs={"class": "form-textarea",
                                                                 "rows": 2}),
                                    help_text="Recorded against the decision")
