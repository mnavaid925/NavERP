"""CRM 1.9 Document & Contract Management — DocTemplates forms (split from apps/crm/forms.py)."""
from apps.crm.forms._common import *  # noqa: F401,F403
from apps.crm.models import (
    DocTemplate,
)


class DocTemplateForm(TenantModelForm):
    class Meta:
        model = DocTemplate
        fields = ["name", "template_type", "body", "is_active", "owner"]
        widgets = {"body": forms.Textarea(attrs={"rows": 18})}
