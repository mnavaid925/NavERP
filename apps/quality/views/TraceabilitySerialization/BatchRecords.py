from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.quality.forms.TraceabilitySerialization.BatchRecords import BatchRecordForm
from apps.quality.models.TraceabilitySerialization.BatchRecords import BatchRecord
from apps.quality.views._common import quality_object, quality_scope

PAGE_SIZE = 15


@login_required
def batch_record_list(request):
    qs = quality_scope(BatchRecord.objects.all(), request).select_related("supervisor", "qa_reviewer")

    query = request.GET.get("q", "").strip()
    if query:
        qs = qs.filter(
            Q(batch_number__icontains=query)
            | Q(product_code__icontains=query)
            | Q(product_name__icontains=query)
            | Q(title__icontains=query)
            | Q(number__icontains=query)
        )

    selected_status = request.GET.get("status", "").strip()
    if selected_status:
        qs = qs.filter(status=selected_status)

    selected_release_status = request.GET.get("release_status", "").strip()
    if selected_release_status:
        qs = qs.filter(release_status=selected_release_status)

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "batch_records": page_obj.object_list,
        "status_choices": BatchRecord.STATUS_CHOICES,
        "release_status_choices": BatchRecord.RELEASE_STATUS_CHOICES,
        "selected_status": selected_status,
        "selected_release_status": selected_release_status,
        "query": query,
    }
    return render(request, "quality/traceabilityserialization/batch_record/list.html", context)


@login_required
def batch_record_detail(request, pk):
    batch_record = quality_object(
        request,
        BatchRecord,
        pk,
        select_related=[
            "supervisor",
            "qa_reviewer",
            "work_order",
            "master_document",
            "electronic_signature",
            "linked_ncr",
            "linked_deviation",
            "linked_fqc",
        ],
    )
    serialized_items = batch_record.serialized_items.all()[:20] if hasattr(batch_record, "serialized_items") else []

    context = {
        "batch_record": batch_record,
        "serialized_items": serialized_items,
        "can_release": batch_record.can_release,
    }
    return render(request, "quality/traceabilityserialization/batch_record/detail.html", context)


@login_required
def batch_record_create(request):
    if request.method == "POST":
        form = BatchRecordForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            write_audit_log(request.user, obj, "create", tenant=request.tenant)
            messages.success(request, f"Batch Record {obj.number} created successfully.")
            return redirect("quality:batch_record_detail", pk=obj.pk)
    else:
        form = BatchRecordForm(tenant=request.tenant)

    context = {
        "form": form,
        "batch_record": None,
        "is_edit": False,
    }
    return render(request, "quality/traceabilityserialization/batch_record/form.html", context)


@login_required
def batch_record_edit(request, pk):
    obj = quality_object(request, BatchRecord, pk)
    if request.method == "POST":
        form = BatchRecordForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(request.user, obj, "update", tenant=request.tenant)
            messages.success(request, f"Batch Record {obj.number} updated successfully.")
            return redirect("quality:batch_record_detail", pk=obj.pk)
    else:
        form = BatchRecordForm(instance=obj, tenant=request.tenant)

    context = {
        "form": form,
        "batch_record": obj,
        "is_edit": True,
    }
    return render(request, "quality/traceabilityserialization/batch_record/form.html", context)


@login_required
@require_POST
def batch_record_delete(request, pk):
    obj = quality_object(request, BatchRecord, pk)
    if obj.status == "released":
        messages.error(request, f"Batch Record {obj.number} is released and cannot be deleted under GMP retention rules.")
        return redirect("quality:batch_record_detail", pk=obj.pk)
    number = obj.number
    write_audit_log(request.user, obj, "delete", tenant=request.tenant)
    obj.delete()
    messages.success(request, f"Batch Record {number} deleted successfully.")
    return redirect("quality:batch_record_list")


@login_required
@require_POST
def batch_record_release(request, pk):
    obj = quality_object(request, BatchRecord, pk)
    if obj.can_release:
        obj.status = "released"
        obj.release_status = "approved_full"
        obj.qa_decision_at = timezone.now()
        obj.qa_reviewer = request.user
        obj.save()
        write_audit_log(request.user, obj, "release", tenant=request.tenant)
        messages.success(request, f"Batch Record {obj.number} successfully released by QA.")
    else:
        messages.error(
            request,
            "Cannot release batch: ensure checklist is passed, quarantine hold is removed, and linked NCR is closed.",
        )
    return redirect("quality:batch_record_detail", pk=obj.pk)
