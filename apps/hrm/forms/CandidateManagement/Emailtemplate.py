"""HRM 3.6 Candidate Management — Emailtemplate forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    CandidateEmailTemplate,
)


class CandidateEmailTemplateForm(TenantModelForm):
    class Meta:
        model = CandidateEmailTemplate
        fields = ["name", "template_type", "subject", "body_html", "is_active", "is_auto_send"]
