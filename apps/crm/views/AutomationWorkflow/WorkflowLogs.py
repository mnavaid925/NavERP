"""CRM 1.10 Automation & Workflow Engine — WorkflowLogs views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    WorkflowLog,
    WorkflowRule,
)


# ------------------------------------------------------------ 1.10 Workflow logs (read-only)
@login_required
def workflowlog_list(request):
    return crud_list(
        request,
        # error_msg is shown (truncated) in the list, so don't defer it (defer + template access = N+1).
        WorkflowLog.objects.filter(tenant=request.tenant).select_related("rule"),
        "crm/workflow/workflowlog/list.html",
        search_fields=["record_label", "error_msg"],
        filters=[("status", "status", False), ("rule", "rule_id", True)],
        extra_context={"status_choices": WorkflowLog.STATUS_CHOICES,
                       "rules": WorkflowRule.objects.filter(tenant=request.tenant).only("id", "name").order_by("name")},
    )


@login_required
def workflowlog_detail(request, pk):
    obj = get_object_or_404(WorkflowLog.objects.select_related("rule"), pk=pk, tenant=request.tenant)
    return render(request, "crm/workflow/workflowlog/detail.html", {"obj": obj})
