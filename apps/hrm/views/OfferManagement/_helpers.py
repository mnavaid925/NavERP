"""HRM 3.8 Offer Management — _helpers views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    BackgroundVerification,
    Offer,
    PreboardingItem,
)


def _offer_or_404(request, pk):
    return get_object_or_404(
        Offer.objects.filter(tenant=request.tenant)
        .select_related("application__candidate", "application__requisition__hiring_manager__party",
                        "offer_letter_template"), pk=pk)


def _bgv_or_404(request, pk):
    return get_object_or_404(
        BackgroundVerification.objects.filter(tenant=request.tenant)
        .select_related("offer__application__candidate"), pk=pk)


# --------------------------------------------------------------- Pre-boarding Items (3.8, inline on offer)
def _preboarding_or_404(request, pk):
    return get_object_or_404(
        PreboardingItem.objects.filter(tenant=request.tenant).select_related("offer__application__candidate"),
        pk=pk)
