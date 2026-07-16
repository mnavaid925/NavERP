"""HRM 3.8 Offer Management — Backgroundverification forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    BackgroundVerification,
    Offer,
)
from apps.hrm.forms.CandidateManagement._helpers import _validate_upload
from apps.hrm.forms.LearningManagement.ALLOWED_OFFER_DOC_EXTENSIONSs import ALLOWED_OFFER_DOC_EXTENSIONS
from apps.hrm.forms.LearningManagement.MAX_OFFER_DOC_BYTESs import MAX_OFFER_DOC_BYTES


class BackgroundVerificationForm(TenantModelForm):
    # SECURITY/workflow: `status` (lifecycle), `result` (set only by the complete action — a form-editable
    # result would bypass the consent→initiate→complete gate), `initiated_at`/`completed_at`/`initiated_by`/
    # `consent_date` (workflow stamps) and the auto `number` are excluded. `offer` is set in the view (from
    # ?offer= or the FK dropdown on plain create).
    class Meta:
        model = BackgroundVerification
        fields = ["offer", "vendor", "check_type", "consent_given", "report_file", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.tenant is not None:
            self.fields["offer"].queryset = (
                Offer.objects.filter(tenant=self.tenant)
                .select_related("application__candidate").order_by("-created_at"))

    def clean_report_file(self):
        return _validate_upload(self.cleaned_data.get("report_file"),
                                allowed_ext=ALLOWED_OFFER_DOC_EXTENSIONS, max_bytes=MAX_OFFER_DOC_BYTES,
                                label="Report")
