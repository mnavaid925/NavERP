"""HRM 3.11 Time Tracking — PublicHolidays forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    PublicHoliday,
)


class PublicHolidayForm(TenantModelForm):
    class Meta:
        model = PublicHoliday
        fields = ["date", "name", "is_optional", "category"]
