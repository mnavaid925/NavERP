from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.quality.forms.LimsManagement.LabSpecifications import LabSpecificationForm
from apps.quality.models.LimsManagement.LabSpecifications import LabSpecification
from apps.quality.views._common import quality_object, quality_scope

PAGE_SIZE = 15


@login_required
def lab_specification_list(request):
    qs = quality_scope(LabSpecification.objects.all(), request).select_related(
        "sop_document", "approved_by"
    )

    query = request.GET.get("q", "").strip()
    if query:
        qs = qs.filter(
            Q(title__icontains=query)
            | Q(number__icontains=query)
            | Q(product_code__icontains=query)
            | Q(product_name__icontains=query)
            | Q(analytical_method_number__icontains=query)
            | Q(target_parameter_name__icontains=query)
        )

    selected_type = request.GET.get("specification_type", "").strip()
    if selected_type:
        qs = qs.filter(specification_type=selected_type)

    selected_category = request.GET.get("test_category", "").strip()
    if selected_category:
        qs = qs.filter(test_category=selected_category)

    selected_status = request.GET.get("status", "").strip()
    if selected_status:
        qs = qs.filter(status=selected_status)

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "specifications": page_obj.object_list,
        "spec_type_choices": LabSpecification.SPEC_TYPE_CHOICES,
        "test_category_choices": LabSpecification.TEST_CATEGORY_CHOICES,
        "status_choices": LabSpecification.STATUS_CHOICES,
        "selected_type": selected_type,
        "selected_category": selected_category,
        "selected_status": selected_status,
        "query": query,
    }
    return render(request, "quality/lims_management/lab_specification/list.html", context)


@login_required
def lab_specification_detail(request, pk):
    specification = quality_object(
        request,
        LabSpecification,
        pk,
        select_related=["sop_document", "approved_by"],
    )
    worksheets = (
        specification.test_worksheets.select_related("sample", "assigned_analyst").all()[:15]
        if hasattr(specification, "test_worksheets")
        else []
    )

    context = {
        "specification": specification,
        "worksheets": worksheets,
    }
    return render(request, "quality/lims_management/lab_specification/detail.html", context)


@login_required
def lab_specification_create(request):
    if request.method == "POST":
        form = LabSpecificationForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            write_audit_log(request.user, obj, "create", tenant=request.tenant)
            messages.success(request, f"Lab Specification {obj.number} created successfully.")
            return redirect("quality:lab_specification_detail", pk=obj.pk)
    else:
        form = LabSpecificationForm(tenant=request.tenant)

    context = {
        "form": form,
        "specification": None,
        "is_edit": False,
    }
    return render(request, "quality/lims_management/lab_specification/form.html", context)


@login_required
def lab_specification_edit(request, pk):
    obj = quality_object(request, LabSpecification, pk)
    if request.method == "POST":
        form = LabSpecificationForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(request.user, obj, "update", tenant=request.tenant)
            messages.success(request, f"Lab Specification {obj.number} updated successfully.")
            return redirect("quality:lab_specification_detail", pk=obj.pk)
    else:
        form = LabSpecificationForm(instance=obj, tenant=request.tenant)

    context = {
        "form": form,
        "specification": obj,
        "is_edit": True,
    }
    return render(request, "quality/lims_management/lab_specification/form.html", context)


@login_required
@require_POST
@tenant_admin_required
def lab_specification_delete(request, pk):
    obj = quality_object(request, LabSpecification, pk)
    if hasattr(obj, "test_worksheets") and obj.test_worksheets.exists():
        messages.error(
            request,
            f"Lab Specification {obj.number} is linked to existing analytical test worksheets and cannot be deleted.",
        )
        return redirect("quality:lab_specification_detail", pk=obj.pk)
    number = obj.number
    write_audit_log(request.user, obj, "delete", tenant=request.tenant)
    obj.delete()
    messages.success(request, f"Lab Specification {number} deleted successfully.")
    return redirect("quality:lab_specification_list")
