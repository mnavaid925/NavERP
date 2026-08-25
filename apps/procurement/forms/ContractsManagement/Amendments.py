"""Procurement 6.8 Contract Management — ContractAmendment forms.

The amendment proposes header changes; blank fields mean "leave the standing term".
Decisions (approve/reject) are POST verbs in the views, not editable form fields.
"""
from apps.procurement.forms._common import *  # noqa: F401,F403
from apps.procurement.forms._common import _reject_foreign
from apps.procurement.models import ContractAmendment
from apps.scm.models import SupplierContract


class ContractAmendmentForm(TenantModelForm):
    class Meta:
        model = ContractAmendment
        # EXCLUDED and why: ``number`` is auto; ``status``/``*_at``/``decided_by`` move
        # only through the decision verbs; ``contract`` comes from the URL, not the form.
        fields = ["reason", "proposed_end_date", "proposed_value",
                  "proposed_auto_renew", "proposed_notice_days", "proposed_summary"]
        widgets = {"proposed_summary": forms.Textarea(attrs={"rows": 3})}

    def clean(self):
        cleaned = super().clean()
        if not any(cleaned.get(f) is not None for f in
                   ("proposed_end_date", "proposed_value",
                    "proposed_auto_renew", "proposed_notice_days")) \
                and not (cleaned.get("proposed_summary") or "").strip():
            raise forms.ValidationError(
                "Propose at least one change — every term blank with no clause digest "
                "amends nothing.")
        return cleaned


class ContractAmendmentDecisionForm(forms.Form):
    """Note captured when approving or rejecting a contract amendment (optional).

    Deliberately NOT ``AmendmentDecisionForm`` — 6.2's requisition-amendment decision
    form owns that name in the shared forms package, and a second binding here would
    shadow it by import order (the L47 failure with no error at all).
    """

    decision_note = forms.CharField(required=False, max_length=2000,
                                    widget=forms.Textarea(attrs={"rows": 2}))


def amendable_contracts(tenant):
    """Spine agreements that accept a new amendment right now (the create-page picker)."""
    return SupplierContract.objects.filter(
        tenant=tenant,
        status__in=ContractAmendment.AMENDABLE_STATUSES).order_by("-created_at")
