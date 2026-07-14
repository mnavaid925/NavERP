"""CRM 1.5 Activity & Communication Management — Tasks views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    CrmTask,
)
from apps.crm.forms import (
    CrmTaskForm,
)


# =============================================================== Tasks (1.5)
@login_required
def task_list(request):
    return crud_list(
        request, CrmTask.objects.filter(tenant=request.tenant).select_related("owner"),
        "crm/activities/task/list.html",
        search_fields=["subject", "number"],
        filters=[("status", "status", False), ("priority", "priority", False), ("type", "type", False)],
        extra_context={"status_choices": CrmTask.STATUS_CHOICES,
                       "priority_choices": CrmTask.PRIORITY_CHOICES,
                       "type_choices": CrmTask.TYPE_CHOICES},
    )


@login_required
def task_create(request):
    return crud_create(request, form_class=CrmTaskForm, template="crm/activities/task/form.html",
                       success_url="crm:task_list")


@login_required
def task_detail(request, pk):
    obj = get_object_or_404(
        CrmTask.objects.select_related(
            "owner", "party", "related_opportunity", "related_case", "recurrence_parent"),
        pk=pk, tenant=request.tenant)
    return render(request, "crm/activities/task/detail.html", {"obj": obj})


@login_required
def task_edit(request, pk):
    return crud_edit(request, model=CrmTask, pk=pk, form_class=CrmTaskForm,
                     template="crm/activities/task/form.html", success_url="crm:task_list")


@login_required
@require_POST
def task_delete(request, pk):
    return crud_delete(request, model=CrmTask, pk=pk, success_url="crm:task_list")
