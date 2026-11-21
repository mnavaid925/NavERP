from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.quality.forms.TraceabilitySerialization.ProductRecalls import ProductRecallForm
from apps.quality.models.TraceabilitySerialization.ProductRecalls import ProductRecall
from apps.quality.views._common import quality_object, quality_scope

PAGE_SIZE = 15


@login_required
def product_recall_list(request):
    qs = quality_scope(ProductRecall.objects.all(), request).select_related("coordinator")

    query = request.GET.get("q", "").strip()
    if query:
        qs = qs.filter(
            Q(title__icontains=query)
            | Q(item_code__icontains=query)
            | Q(item_name__icontains=query)
            | Q(affected_lot_numbers__icontains=query)
            | Q(number__icontains=query)
        )

    selected_class = request.GET.get("recall_class", "").strip()
    if selected_class:
        qs = qs.filter(recall_class=selected_class)

    selected_status = request.GET.get("status", "").strip()
    if selected_status:
        qs = qs.filter(status=selected_status)

    selected_mock = request.GET.get("is_mock_recall", "").strip()
    if selected_mock == "true":
        qs = qs.filter(is_mock_recall=True)
    elif selected_mock == "false":
        qs = qs.filter(is_mock_recall=False)

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "product_recalls": page_obj.object_list,
        "recall_class_choices": ProductRecall.RECALL_CLASS_CHOICES,
        "status_choices": ProductRecall.RECALL_STATUS_CHOICES,
        "selected_class": selected_class,
        "selected_status": selected_status,
        "selected_mock": selected_mock,
        "query": query,
    }
    return render(request, "quality/traceabilityserialization/product_recall/list.html", context)


@login_required
def product_recall_detail(request, pk):
    product_recall = quality_object(
        request,
        ProductRecall,
        pk,
        select_related=[
            "coordinator",
            "closure_approved_by",
            "customer_complaint",
            "capa_investigation",
        ],
    )

    context = {
        "product_recall": product_recall,
    }
    return render(request, "quality/traceabilityserialization/product_recall/detail.html", context)


@login_required
def product_recall_create(request):
    if request.method == "POST":
        form = ProductRecallForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            if obj.status in ["completed", "terminated"] and not obj.closed_at:
                obj.closed_at = timezone.now()
            obj.save()
            form.save_m2m()
            write_audit_log(request.user, obj, "create", tenant=request.tenant)
            messages.success(request, f"Product Recall {obj.number} initiated successfully.")
            return redirect("quality:product_recall_detail", pk=obj.pk)
    else:
        form = ProductRecallForm(tenant=request.tenant)

    context = {
        "form": form,
        "product_recall": None,
        "is_edit": False,
    }
    return render(request, "quality/traceabilityserialization/product_recall/form.html", context)


@login_required
def product_recall_edit(request, pk):
    obj = quality_object(request, ProductRecall, pk)
    if request.method == "POST":
        form = ProductRecallForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            if obj.status in ["completed", "terminated"] and not obj.closed_at:
                obj.closed_at = timezone.now()
            obj.save()
            form.save_m2m()
            write_audit_log(request.user, obj, "update", tenant=request.tenant)
            messages.success(request, f"Product Recall {obj.number} updated successfully.")
            return redirect("quality:product_recall_detail", pk=obj.pk)
    else:
        form = ProductRecallForm(instance=obj, tenant=request.tenant)

    context = {
        "form": form,
        "product_recall": obj,
        "is_edit": True,
    }
    return render(request, "quality/traceabilityserialization/product_recall/form.html", context)


@login_required
@require_POST
@tenant_admin_required
def product_recall_delete(request, pk):
    obj = quality_object(request, ProductRecall, pk)
    number = obj.number
    write_audit_log(request.user, obj, "delete", tenant=request.tenant)
    obj.delete()
    messages.success(request, f"Product Recall {number} deleted successfully.")
    return redirect("quality:product_recall_list")
