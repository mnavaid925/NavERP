"""tenants — BrandingSetting forms (split from apps/tenants/forms.py)."""
from apps.tenants.forms._common import *  # noqa: F401,F403
from apps.tenants.models import (
    BrandingSetting,
)


class BrandingSettingForm(TenantModelForm):
    class Meta:
        model = BrandingSetting
        fields = ["logo", "primary_color", "accent_color", "email_from_name", "email_footer"]
        widgets = {
            "primary_color": forms.TextInput(attrs={"type": "color", "class": "form-input"}),
            "accent_color": forms.TextInput(attrs={"type": "color", "class": "form-input"}),
        }
