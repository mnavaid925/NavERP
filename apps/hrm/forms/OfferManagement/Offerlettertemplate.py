"""HRM 3.8 Offer Management — Offerlettertemplate forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    OfferLetterTemplate,
)


# ----------------------------------------------------------------------- 3.8 Offer Management
class OfferLetterTemplateForm(TenantModelForm):
    class Meta:
        model = OfferLetterTemplate
        fields = ["name", "is_active", "body_html"]
