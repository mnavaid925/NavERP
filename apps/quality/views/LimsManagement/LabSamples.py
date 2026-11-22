from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.quality.forms.LimsManagement.LabSamples import LabSampleForm
from apps.quality.models.LimsManagement.LabSamples import LabSample
from apps.quality.views._common import quality_object, quality_scope

PAGE_SIZE = 15


@login_required
def lab_sample_list(request):
    qs = quality_scope(LabSample.objects.all(), request).select_related(
        "sampled_by", "received_by", "current_custodian", "facility"
    )

    query = request.GET.get("q", "").strip()
    if query:
        qs = qs.filter(
            Q(sample_name__icontains=query)
            | Q(number__icontains=query)
            | Q(item_code__icontains=query)
            | Q(item_name__icontains=query)
            | Q(source_batch_number__icontains=query)
            | Q(barcode_identifier__icontains=query)
        )

    selected_type = request.GET.get("sample_type", "").strip()
    if selected_type:
        qs = qs.filter(sample_type=selected_type)

    selected_status = request.GET.get("status", "").strip()
    if selected_status:
        qs = qs.filter(status=selected_status)

    selected_storage = request.GET.get("storage_condition", "").strip()
    if selected_storage:
        qs = qs.filter(storage_condition=selected_storage)

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "samples": page_obj.object_list,
        "sample_type_choices": LabSample.SAMPLE_TYPE_CHOICES,
        "status_choices": LabSample.STATUS_CHOICES,
        "storage_condition_choices": LabSample.STORAGE_CONDITION_CHOICES,
        "selected_type": selected_type,
        "selected_status": selected_status,
        "selected_storage": selected_storage,
        "query": query,
    }
    return render(request, "quality/lims_management/lab_sample/list.html", context)


@login_required
def lab_sample_detail(request, pk):
    sample = quality_object(
        request,
        LabSample,
        pk,
        select_related=[
            "sampled_by",
            "received_by",
            "current_custodian",
            "work_order",
            "batch_record",
            "facility",
        ],
    )
    test_worksheets = sample.test_worksheets.all() if hasattr(sample, "test_worksheets") else []
    oos_investigations = sample.oos_investigations.all() if hasattr(sample, "oos_investigations") else []

    context = {
        "sample": sample,
        "test_worksheets": test_worksheets,
        "oos_investigations": oos_investigations,
    }
    return render(request, "quality/lims_management/lab_sample/detail.html", context)


@login_required
def lab_sample_create(request):
    if request.method == "POST":
        form = LabSampleForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            if not obj.sampled_by:
                obj.sampled_by = request.user
            if not obj.sampled_at:
                obj.sampled_at = timezone.now()
            obj.save()
            write_audit_log(request.user, obj, "create", tenant=request.tenant)
            messages.success(request, f"Lab Sample {obj.number} created successfully.")
            return redirect("quality:lab_sample_detail", pk=obj.pk)
    else:
        form = LabSampleForm(tenant=request.tenant)

    context = {
        "form": form,
        "sample": None,
        "is_edit": False,
    }
    return render(request, "quality/lims_management/lab_sample/form.html", context)


@login_required
def lab_sample_edit(request, pk):
    obj = quality_object(request, LabSample, pk)
    if request.method == "POST":
        form = LabSampleForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(request.user, obj, "update", tenant=request.tenant)
            messages.success(request, f"Lab Sample {obj.number} updated successfully.")
            return redirect("quality:lab_sample_detail", pk=obj.pk)
    else:
        form = LabSampleForm(instance=obj, tenant=request.tenant)

    context = {
        "form": form,
        "sample": obj,
        "is_edit": True,
    }
    return render(request, "quality/lims_management/lab_sample/form.html", context)


@login_required
@require_POST
@tenant_admin_required
def lab_sample_delete(request, pk):
    obj = quality_object(request, LabSample, pk)
    if obj.status in ["approved", "in_testing", "testing_completed"] or obj.test_worksheets.exists() or obj.oos_investigations.exists():
        messages.error(
            request,
            f"Lab Sample {obj.number} has linked worksheets/investigations or is active and cannot be deleted under GxP data integrity rules.",
        )
        return redirect("quality:lab_sample_detail", pk=obj.pk)
    number = obj.number
    write_audit_log(request.user, obj, "delete", tenant=request.tenant)
    obj.delete()
    messages.success(request, f"Lab Sample {number} deleted successfully.")
    return redirect("quality:lab_sample_list")


@login_required
@require_POST
def lab_sample_receive(request, pk):
    obj = quality_object(request, LabSample, pk)
    if obj.status == "registered":
        obj.status = "received"
        obj.received_by = request.user
        obj.received_at = timezone.now()
        obj.current_custodian = request.user
        timestamp = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{timestamp}] Received in lab by {request.user.get_full_name() or request.user.username}."
        if obj.chain_of_custody_log:
            obj.chain_of_custody_log += f"\n{entry}"
        else:
            obj.chain_of_custody_log = entry
        obj.save()
        write_audit_log(request.user, obj, "receive", tenant=request.tenant)
        messages.success(request, f"Lab Sample {obj.number} officially received in laboratory.")
    else:
        messages.info(request, f"Lab Sample {obj.number} is already in state '{obj.get_status_display()}'.")
    return redirect("quality:lab_sample_detail", pk=obj.pk)
