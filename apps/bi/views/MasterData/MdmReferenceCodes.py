from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.bi.forms.MasterData.MdmReferenceCodeForms import MdmReferenceCodeForm
from apps.bi.models.MasterData.MdmReferenceCodes import MdmReferenceCode
from apps.bi.views._common import bi_object, bi_scope
from apps.core.utils import write_audit_log


@login_required
def mdm_reference_code_list(request):
    queryset = bi_scope(MdmReferenceCode.objects.all(), request).select_related("superseded_by")

    q = request.GET.get("q", "").strip()[:100]
    if q:
        queryset = queryset.filter(
            Q(canonical_code__icontains=q)
            | Q(canonical_name__icontains=q)
            | Q(source_code__icontains=q)
            | Q(source_system__icontains=q)
            | Q(code_set__icontains=q)
        )

    code_set_filter = request.GET.get("code_set", "").strip()
    if code_set_filter:
        queryset = queryset.filter(code_set=code_set_filter)

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        queryset = queryset.filter(status=status_filter)

    source_system_filter = request.GET.get("source_system", "").strip()
    if source_system_filter:
        queryset = queryset.filter(source_system=source_system_filter)

    all_tenant_codes = bi_scope(MdmReferenceCode.objects.all(), request)
    counts = all_tenant_codes.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status="active")),
    )
    total_count = counts["total"]
    active_count = counts["active"]
    code_sets = (
        all_tenant_codes.values_list("code_set", flat=True)
        .distinct()
        .order_by("code_set")
    )

    paginator = Paginator(queryset.order_by("code_set", "canonical_code", "source_system"), 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "reference_codes": page_obj,
        "status_choices": MdmReferenceCode.STATUS_CHOICES,
        "code_sets": code_sets,
        "total_count": total_count,
        "active_count": active_count,
    }
    return render(request, "bi/master_data/reference_code/list.html", context)


@login_required
def mdm_reference_code_detail(request, pk):
    reference_code = bi_object(request, MdmReferenceCode, pk, select_related=("superseded_by",))
    superseding_codes = reference_code.superseded_codes.all().order_by("canonical_code")

    context = {
        "reference_code": reference_code,
        "superseded_by": reference_code.superseded_by,
        "superseding_codes": superseding_codes,
    }
    return render(request, "bi/master_data/reference_code/detail.html", context)


@login_required
def mdm_reference_code_create(request):
    if request.method == "POST":
        form = MdmReferenceCodeForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            code_obj = form.save(commit=False)
            code_obj.tenant = request.tenant
            code_obj.save()
            write_audit_log(
                request.user,
                code_obj,
                "create",
                changes=f"Created reference code {code_obj.number} ({code_obj.code_set}:{code_obj.canonical_code})",
                tenant=request.tenant,
            )
            messages.success(request, f"Reference code '{code_obj.canonical_code}' created successfully.")
            return redirect("bi:mdm_reference_code_detail", pk=code_obj.pk)
    else:
        form = MdmReferenceCodeForm(tenant=request.tenant)

    context = {
        "form": form,
        "reference_code": None,
        "is_edit": False,
    }
    return render(request, "bi/master_data/reference_code/form.html", context)


@login_required
def mdm_reference_code_edit(request, pk):
    reference_code = bi_object(request, MdmReferenceCode, pk)

    if request.method == "POST":
        form = MdmReferenceCodeForm(request.POST, instance=reference_code, tenant=request.tenant)
        if form.is_valid():
            saved_code = form.save()
            write_audit_log(
                request.user,
                saved_code,
                "update",
                changes=f"Updated reference code {saved_code.number}",
                tenant=request.tenant,
            )
            messages.success(request, f"Reference code '{saved_code.canonical_code}' updated successfully.")
            return redirect("bi:mdm_reference_code_detail", pk=saved_code.pk)
    else:
        form = MdmReferenceCodeForm(instance=reference_code, tenant=request.tenant)

    context = {
        "form": form,
        "reference_code": reference_code,
        "is_edit": True,
    }
    return render(request, "bi/master_data/reference_code/form.html", context)


@login_required
@require_POST
def mdm_reference_code_delete(request, pk):
    reference_code = bi_object(request, MdmReferenceCode, pk)
    code_number = reference_code.number
    code_label = f"{reference_code.code_set}:{reference_code.canonical_code}"

    write_audit_log(
        request.user,
        reference_code,
        "delete",
        changes=f"Deleted reference code {code_number} ({code_label})",
        tenant=request.tenant,
    )
    reference_code.delete()
    messages.success(request, f"Reference code {code_number} deleted successfully.")
    return redirect("bi:mdm_reference_code_list")
