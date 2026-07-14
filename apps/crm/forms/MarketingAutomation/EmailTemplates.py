"""CRM 1.3 Marketing Automation — EmailTemplates forms (split from apps/crm/forms.py)."""
from apps.crm.forms._common import *  # noqa: F401,F403
from apps.crm.models import (
    EmailTemplate,
)


class EmailTemplateForm(TenantModelForm):
    class Meta:
        model = EmailTemplate
        fields = ["name", "category", "subject", "preheader", "body", "from_name",
                  "from_email", "is_active", "owner"]
        widgets = {"body": forms.Textarea(attrs={"rows": 16})}
