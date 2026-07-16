"""HRM 3.34 Expense Management — _helpers views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    ExpenseClaim,
)
from apps.hrm.views.PersonalInformation._helpers import _can_manage_own_child


def _get_own_claim(request, pk):
    obj = get_object_or_404(ExpenseClaim, pk=pk, tenant=request.tenant)
    if not _can_manage_own_child(request, obj):
        raise PermissionDenied("This claim belongs to another employee.")
    return obj
