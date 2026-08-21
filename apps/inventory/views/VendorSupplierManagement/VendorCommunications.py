"""Inventory 5.2 Vendor / Supplier Management — VendorCommunication views.

Same thin-CRUD shape as the 5.1 catalog views. The follow-up chip is the one filter the
shared ``crud_list`` spec cannot express (it compares a date column against TODAY, not
against a GET value), so it is applied to the queryset before the helper runs; everything
else stays declarative.
"""
import datetime

from django.utils import timezone

from apps.inventory.views._common import *  # noqa: F401,F403
from apps.inventory.forms import VendorCommunicationForm
from apps.inventory.models import VendorCommunication
from apps.inventory.forms._common import _vendor_parties


@login_required
def vendorcommunication_list(request):
    qs = (VendorCommunication.objects.filter(tenant=request.tenant)
          .select_related("party"))
    # Follow-up chip: due = today-or-later, overdue = silently slipped past its date.
    follow_up = request.GET.get("follow_up", "").strip()
    today = timezone.localdate()
    if follow_up == "due":
        qs = qs.filter(follow_up_on__gte=today)
    elif follow_up == "overdue":
        qs = qs.filter(follow_up_on__lt=today)
    return crud_list(
        request, qs, "inventory/vendor/vendorcommunication/list.html",
        search_fields=["number", "subject", "body", "party__name"],
        filters=[("party", "party_id", True), ("channel", "channel", False),
                 ("direction", "direction", False)],
        extra_context={
            "parties": _vendor_parties(request.tenant).order_by("name"),
            "channel_choices": VendorCommunication.CHANNEL_CHOICES,
            "direction_choices": VendorCommunication.DIRECTION_CHOICES,
            "follow_up": follow_up,
            "today": today,
        },
    )


@login_required
def vendorcommunication_create(request):
    return crud_create(
        request, form_class=VendorCommunicationForm,
        template="inventory/vendor/vendorcommunication/form.html",
        success_url="inventory:vendorcommunication_list",
    )


@login_required
def vendorcommunication_detail(request, pk):
    obj = get_object_or_404(
        VendorCommunication.objects.select_related("party"), pk=pk, tenant=request.tenant)
    return render(request, "inventory/vendor/vendorcommunication/detail.html", {
        "obj": obj,
        # The same vendor's other interactions — scoped + self-excluded here rather than
        # trusted from the reverse relation, so a future raw writer cannot render another
        # workspace's rows inline on this page.
        "siblings": (VendorCommunication.objects.filter(tenant=request.tenant, party=obj.party)
                     .exclude(pk=obj.pk).select_related("party")[:8]),
    })


@login_required
def vendorcommunication_edit(request, pk):
    return crud_edit(
        request, model=VendorCommunication, pk=pk, form_class=VendorCommunicationForm,
        template="inventory/vendor/vendorcommunication/form.html",
        success_url="inventory:vendorcommunication_list",
    )


@login_required
@require_POST
def vendorcommunication_delete(request, pk):
    return crud_delete(request, model=VendorCommunication, pk=pk,
                       success_url="inventory:vendorcommunication_list")
