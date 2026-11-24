from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.core.models import OrgUnit
from apps.documents.models.WorkflowAutomation.DocumentProcessDefinitions import (
    DocumentProcessDefinition,
)
from apps.documents.services.workflow_automation import compute_process_analytics
from apps.documents.views._common import safe_parse_date


@login_required
def process_analytics_dashboard(request):
    """Process performance analytics: cycle times, throughput, bottlenecks, and process mining."""
    proc_id_raw = request.GET.get("process_definition", "").strip()
    selected_process_id = proc_id_raw if proc_id_raw.isdigit() else ""

    dept_id_raw = request.GET.get("department", "").strip()
    selected_department_id = dept_id_raw if dept_id_raw.isdigit() else ""

    date_from_str = request.GET.get("date_from", "").strip()
    date_to_str = request.GET.get("date_to", "").strip()
    date_from = safe_parse_date(date_from_str) if date_from_str else None
    date_to = safe_parse_date(date_to_str) if date_to_str else None

    analytics = compute_process_analytics(
        tenant=request.tenant,
        process_def_id=selected_process_id or None,
        department_id=selected_department_id or None,
        date_from=date_from,
        date_to=date_to,
    )

    process_definitions = DocumentProcessDefinition.objects.filter(
        tenant=request.tenant
    ).order_by("code", "-version_number")
    departments = OrgUnit.objects.filter(tenant=request.tenant).order_by("name")

    context = {
        "analytics": analytics,
        "process_definitions": process_definitions,
        "departments": departments,
        "selected_process_id": selected_process_id,
        "selected_department_id": selected_department_id,
        "date_from": date_from_str,
        "date_to": date_to_str,
    }
    return render(
        request,
        "documents/workflow_automation/analytics_dashboard.html",
        context,
    )
