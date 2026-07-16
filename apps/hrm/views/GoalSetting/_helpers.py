"""HRM 3.18 Goal Setting — _helpers views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403


# ============================================================ 3.18 Goal Setting (Performance Mgmt)
def _current_employee_profile(request):
    """Resolve the logged-in user's ``EmployeeProfile`` (via ``User.party`` → reverse O2O), or
    ``None`` for a user with no linked party/profile (e.g. the superuser). Django's reverse-O2O
    ``RelatedObjectDoesNotExist`` subclasses ``AttributeError``, so ``getattr(..., None)`` is safe."""
    party = getattr(request.user, "party", None)
    if party is None:
        return None
    return getattr(party, "employee_profile", None)
