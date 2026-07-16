"""HRM 3.8 Offer Management — Offer forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    JobApplication,
    Offer,
    OfferApproval,
    OfferLetterTemplate,
)
from apps.hrm.forms.CandidateManagement._helpers import _validate_upload
from apps.hrm.forms.LearningManagement.ALLOWED_OFFER_DOC_EXTENSIONSs import ALLOWED_OFFER_DOC_EXTENSIONS
from apps.hrm.forms.LearningManagement.MAX_OFFER_DOC_BYTESs import MAX_OFFER_DOC_BYTES


class OfferForm(TenantModelForm):
    # SECURITY/workflow: `status` (state machine), the workflow stamps (`extended_by`/`extended_at`/
    # `accepted_at`/`declined_at`/`rescinded_at`/`created_by`) and the auto `number` are excluded — set
    # only by the audited POST actions. `decline_reason`/`decline_notes`/`signature_status` stay on the
    # form as recruiter-editable annotations (mirrors JobApplication.rejection_* being form-editable).
    class Meta:
        model = Offer
        fields = ["application", "offer_letter_template", "base_salary", "currency", "bonus_amount",
                  "bonus_terms", "signing_bonus", "equity_terms", "relocation_assistance",
                  "benefits_summary", "start_date", "expires_on", "decline_reason", "decline_notes",
                  "signed_document", "signature_status", "notes"]
        widgets = {"start_date": forms.DateInput(attrs={"type": "date"}),
                   "expires_on": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Optional on the form so a blank submission defaults from the requisition's salary_currency in
        # the view; the model still carries "USD" as the ultimate fallback.
        self.fields["currency"].required = False
        if self.tenant is not None:
            # select_related the dropdown's __str__ traversal (candidate) to avoid an N+1 per option.
            self.fields["application"].queryset = (
                JobApplication.objects.filter(tenant=self.tenant)
                .select_related("candidate", "requisition").order_by("-applied_at"))
            self.fields["offer_letter_template"].queryset = (
                OfferLetterTemplate.objects.filter(tenant=self.tenant, is_active=True).order_by("name"))

    def clean(self):
        cleaned = super().clean()
        for field in ("base_salary", "bonus_amount", "signing_bonus", "relocation_assistance"):
            value = cleaned.get(field)
            if value is not None and value < 0:
                self.add_error(field, "Amount cannot be negative.")
        return cleaned

    def clean_signed_document(self):
        return _validate_upload(self.cleaned_data.get("signed_document"),
                                allowed_ext=ALLOWED_OFFER_DOC_EXTENSIONS, max_bytes=MAX_OFFER_DOC_BYTES,
                                label="Signed document")


class OfferApprovalForm(TenantModelForm):
    # SECURITY: `status`, `decided_at`, `decided_by` are excluded — set only by the approve/reject
    # actions. `offer` is set in the view (the step is added from the offer hub). Mirrors
    # RequisitionApprovalForm exactly.
    class Meta:
        model = OfferApproval
        fields = ["step_order", "approver", "approver_role", "comments"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["approver"].queryset = (
                get_user_model().objects.filter(tenant=self.tenant, is_active=True).order_by("username"))
        else:
            self.fields["approver"].queryset = get_user_model().objects.none()
