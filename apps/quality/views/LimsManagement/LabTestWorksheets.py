from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.quality.forms.LimsManagement.LabTestWorksheets import LabTestWorksheetForm
from apps.quality.models.LimsManagement.LabTestWorksheets import LabTestWorksheet
from apps.quality.views._common import quality_object, quality_scope

PAGE_SIZE = 15


@login_required
def lab_test_worksheet_list(request):
    qs = quality_scope(LabTestWorksheet.objects.all(), request).select_related(
        "sample", "specification", "assigned_analyst", "reviewer", "instrument"
    )

    query = request.GET.get("q", "").strip()
    if query:
        qs = qs.filter(
            Q(title__icontains=query)
            | Q(number__icontains=query)
            | Q(instrument_name__icontains=query)
            | Q(reagent_lot_number__icontains=query)
            | Q(sample__number__icontains=query)
            | Q(sample__sample_name__icontains=query)
            | Q(specification__title__icontains=query)
            | Q(specification__product_code__icontains=query)
        )

    selected_status = request.GET.get("status", "").strip()
    if selected_status:
        qs = qs.filter(status=selected_status)

    selected_disposition = request.GET.get("disposition", "").strip()
    if selected_disposition:
        qs = qs.filter(disposition=selected_disposition)

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "worksheets": page_obj.object_list,
        "status_choices": LabTestWorksheet.STATUS_CHOICES,
        "disposition_choices": LabTestWorksheet.DISPOSITION_CHOICES,
        "selected_status": selected_status,
        "selected_disposition": selected_disposition,
        "query": query,
    }
    return render(request, "quality/lims_management/lab_test_worksheet/list.html", context)


@login_required
def lab_test_worksheet_detail(request, pk):
    worksheet = quality_object(
        request,
        LabTestWorksheet,
        pk,
        select_related=[
            "sample",
            "specification",
            "assigned_analyst",
            "reviewer",
            "instrument",
        ],
    )
    oos_investigations = (
        worksheet.oos_investigations.all()
        if hasattr(worksheet, "oos_investigations")
        else []
    )

    context = {
        "worksheet": worksheet,
        "oos_investigations": oos_investigations,
    }
    return render(request, "quality/lims_management/lab_test_worksheet/detail.html", context)


@login_required
def lab_test_worksheet_create(request):
    initial = {}
    sample_id = request.GET.get("sample", "").strip()
    if sample_id.isdigit():
        initial["sample"] = sample_id
    spec_id = request.GET.get("specification", "").strip()
    if spec_id.isdigit():
        initial["specification"] = spec_id

    if request.method == "POST":
        form = LabTestWorksheetForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            if not obj.assigned_analyst:
                obj.assigned_analyst = request.user
            obj.save()
            write_audit_log(request.user, obj, "create", tenant=request.tenant)
            messages.success(request, f"Lab Test Worksheet {obj.number} created successfully.")
            return redirect("quality:lab_test_worksheet_detail", pk=obj.pk)
    else:
        form = LabTestWorksheetForm(initial=initial, tenant=request.tenant)

    context = {
        "form": form,
        "worksheet": None,
        "is_edit": False,
    }
    return render(request, "quality/lims_management/lab_test_worksheet/form.html", context)


@login_required
def lab_test_worksheet_edit(request, pk):
    obj = quality_object(request, LabTestWorksheet, pk)
    if request.method == "POST":
        form = LabTestWorksheetForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(request.user, obj, "update", tenant=request.tenant)
            messages.success(request, f"Lab Test Worksheet {obj.number} updated successfully.")
            return redirect("quality:lab_test_worksheet_detail", pk=obj.pk)
    else:
        form = LabTestWorksheetForm(instance=obj, tenant=request.tenant)

    context = {
        "form": form,
        "worksheet": obj,
        "is_edit": True,
    }
    return render(request, "quality/lims_management/lab_test_worksheet/form.html", context)


@login_required
@require_POST
@tenant_admin_required
def lab_test_worksheet_delete(request, pk):
    obj = quality_object(request, LabTestWorksheet, pk)
    if obj.status == "approved" or obj.oos_investigations.exists():
        messages.error(
            request,
            f"Lab Test Worksheet {obj.number} has linked OOS investigations or is approved and cannot be deleted under GxP laboratory records compliance.",
        )
        return redirect("quality:lab_test_worksheet_detail", pk=obj.pk)
    number = obj.number
    write_audit_log(request.user, obj, "delete", tenant=request.tenant)
    obj.delete()
    messages.success(request, f"Lab Test Worksheet {number} deleted successfully.")
    return redirect("quality:lab_test_worksheet_list")


@login_required
@require_POST
def lab_test_worksheet_complete(request, pk):
    obj = quality_object(request, LabTestWorksheet, pk)
    if obj.status not in ["assigned", "in_progress"]:
        messages.error(request, f"Worksheet {obj.number} cannot be completed from its current status.")
        return redirect("quality:lab_test_worksheet_detail", pk=obj.pk)
    obj.status = "review_pending"
    obj.completion_timestamp = timezone.now()
    if not obj.execution_date:
        obj.execution_date = timezone.now().date()
    obj.save()
    write_audit_log(request.user, obj, "complete", tenant=request.tenant)
    messages.success(request, f"Worksheet {obj.number} marked completed and submitted for QA review.")
    return redirect("quality:lab_test_worksheet_detail", pk=obj.pk)
