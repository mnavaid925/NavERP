"""HRM 3.11 Time Tracking — GeoFences forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    GeoFence,
)


class GeoFenceForm(TenantModelForm):
    class Meta:
        model = GeoFence
        fields = ["name", "address", "latitude", "longitude", "radius_m", "is_active"]
        widgets = {
            "latitude": forms.NumberInput(attrs={"step": "0.000001", "class": "form-input"}),
            "longitude": forms.NumberInput(attrs={"step": "0.000001", "class": "form-input"}),
        }
