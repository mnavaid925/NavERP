"""HRM 3.4 Employee Offboarding — RelievingLetter views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.views.EmployeeOffboarding._helpers import _generate_letter
from apps.hrm.views.EmployeeOffboarding._helpers import _generate_letter


@login_required
@require_POST
def separationcase_generate_relieving_letter(request, pk):
    return _generate_letter(request, pk, kind="relieving",
                            template="hrm/offboarding/relieving_letter.html")
