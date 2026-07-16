"""HRM 3.26 Request Management — Assetrequest forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    AssetRequest,
)


class AssetRequestForm(TenantModelForm):
    """Employee's equipment request. The `allocation` link + reviewer/status fields are set by the
    approve/fulfill actions — none appear on the form."""

    class Meta:
        model = AssetRequest
        fields = ["asset_category", "asset_name", "justification", "priority", "needed_by"]
        widgets = {"justification": forms.Textarea(attrs={"rows": 3})}
