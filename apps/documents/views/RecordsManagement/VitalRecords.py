from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render

from apps.core.models import OrgUnit
from apps.documents.models.RecordsManagement.RecordDeclarations import RecordDeclaration
from apps.documents.views._common import documents_scope


@login_required
def vital_records_list(request):
    """Register of mission-critical vital records essential for disaster recovery and operational continuity."""
    qs = documents_scope(
        RecordDeclaration.objects.filter(is_vital_record=True),
        request,
    ).select_related("document", "version", "retention_schedule", "retention_schedule__department", "declared_by")

    department_id = request.GET.get("department", "").strip()
    if department_id.isdigit():
        qs = qs.filter(retention_schedule__department_id=int(department_id))

    query = request.GET.get("q", "").strip()
    if query:
        qs = qs.filter(
            Q(number__icontains=query)
            | Q(document__title__icontains=query)
            | Q(document__document_number__icontains=query)
            | Q(retention_schedule__name__icontains=query)
            | Q(notes__icontains=query)
        )

    qs = qs.order_by("-declaration_date")
    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    departments = OrgUnit.objects.filter(tenant=request.tenant).order_by("name")

    context = {
        "vital_records": page_obj,
        "page_obj": page_obj,
        "paginator": paginator,
        "departments": departments,
        "query": query,
    }
    return render(request, "documents/records_management/vital_records/list.html", context)
