"""HRM 3.6 Candidate Management — Communication views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    COMMUNICATION_CHANNEL_CHOICES,
    CandidateCommunication,
    CandidateProfile,
    DELIVERY_STATUS_CHOICES,
)


# --------------------------------------------------------------- Candidate Communications (3.6, read-only)
@login_required
def communication_list(request):
    return crud_list(
        request, CandidateCommunication.objects.filter(tenant=request.tenant)
        .select_related("candidate", "application", "sent_by"),
        "hrm/candidates/communication/list.html",
        search_fields=["number", "subject", "body", "candidate__first_name", "candidate__last_name"],
        filters=[("channel", "channel", False), ("status", "delivery_status", False),
                 ("candidate", "candidate_id", True)],
        extra_context={
            "channel_choices": COMMUNICATION_CHANNEL_CHOICES,
            "delivery_status_choices": DELIVERY_STATUS_CHOICES,
            "candidates": CandidateProfile.objects.filter(tenant=request.tenant)
            .only("pk", "first_name", "last_name", "number"),
        })


@login_required
def communication_detail(request, pk):
    return crud_detail(request, model=CandidateCommunication, pk=pk,
                       template="hrm/candidates/communication/detail.html",
                       select_related=("candidate", "application", "template", "sent_by"))
