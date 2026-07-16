"""HRM 3.8 Offer Management — PreboardingItems forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    PreboardingItem,
)
from apps.hrm.forms.CandidateManagement._helpers import _validate_upload
from apps.hrm.forms.LearningManagement.ALLOWED_PREBOARDING_DOC_EXTENSIONSs import ALLOWED_PREBOARDING_DOC_EXTENSIONS
from apps.hrm.forms.LearningManagement.MAX_OFFER_DOC_BYTESs import MAX_OFFER_DOC_BYTES


class PreboardingItemForm(TenantModelForm):
    # Inline-add on the offer detail hub; `offer` is set in the view. `status`/`submitted_at`/
    # `verified_by`/`verified_at`/`reminder_sent_at` are workflow-owned (the submit/verify/reject/
    # send-invite actions stamp them).
    class Meta:
        model = PreboardingItem
        fields = ["document_type", "is_required", "uploaded_file", "notes"]

    def clean_uploaded_file(self):
        return _validate_upload(self.cleaned_data.get("uploaded_file"),
                                allowed_ext=ALLOWED_PREBOARDING_DOC_EXTENSIONS, max_bytes=MAX_OFFER_DOC_BYTES,
                                label="Document")
