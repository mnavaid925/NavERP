"""CRM 1.5 Activity & Communication Management — CommunicationLogs views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    CommunicationLog,
)
from apps.crm.forms import (
    CommunicationLogForm,
)


# ===================== Communication Logs (1.5 Email & Call Integration) =====================
@login_required
def communicationlog_list(request):
    return crud_list(
        request,
        CommunicationLog.objects.filter(tenant=request.tenant).select_related("party"),
        "crm/activities/communicationlog/list.html",
        search_fields=["subject", "number", "body"],
        filters=[("channel", "channel", False), ("direction", "direction", False),
                 ("logged_via", "logged_via", False)],
        extra_context={"channel_choices": CommunicationLog.CHANNEL_CHOICES,
                       "direction_choices": CommunicationLog.DIRECTION_CHOICES,
                       "logged_via_choices": CommunicationLog.LOGGED_VIA_CHOICES},
    )


@login_required
def communicationlog_create(request):
    return crud_create(request, form_class=CommunicationLogForm,
                       template="crm/activities/communicationlog/form.html",
                       success_url="crm:communicationlog_list")


@login_required
def communicationlog_detail(request, pk):
    obj = get_object_or_404(
        CommunicationLog.objects.select_related("party", "owner", "related_opportunity", "related_case"),
        pk=pk, tenant=request.tenant)
    return render(request, "crm/activities/communicationlog/detail.html", {"obj": obj})


@login_required
def communicationlog_edit(request, pk):
    return crud_edit(request, model=CommunicationLog, pk=pk, form_class=CommunicationLogForm,
                     template="crm/activities/communicationlog/form.html",
                     success_url="crm:communicationlog_list")


@login_required
@require_POST
def communicationlog_delete(request, pk):
    return crud_delete(request, model=CommunicationLog, pk=pk, success_url="crm:communicationlog_list")
