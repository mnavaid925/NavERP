"""HRM 3.4 Employee Offboarding — Letters views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    SeparationCase,
)


@login_required
def offboarding_letters(request):
    """Landing page for the relieving/experience letters (the 'Experience Letter' sidebar bullet).
    Lists every separation case that has reached a letter-ready status (cleared/settled/completed),
    each row offering the two letter actions + showing whether each was already generated. The letters
    themselves are per-case print views — there is no standalone letter record."""
    qs = (SeparationCase.objects
          .filter(tenant=request.tenant, status__in=SeparationCase.LETTER_READY_STATUSES)
          .select_related("employee__party", "employee__designation"))
    letter_status_choices = [(s, lbl) for s, lbl in SeparationCase.STATUS_CHOICES
                             if s in SeparationCase.LETTER_READY_STATUSES]
    return crud_list(
        request, qs, "hrm/offboarding/letters.html",
        search_fields=["number", "employee__party__name"],
        filters=[("status", "status", False)],
        extra_context={"status_choices": letter_status_choices},
    )
