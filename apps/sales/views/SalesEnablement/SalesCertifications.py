"""Sales 8.9 — Views for `SalesCertification`."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.core.utils import write_audit_log
from apps.sales.forms.SalesEnablement.SalesCertifications import SalesCertificationForm
from apps.sales.models.SalesEnablement.SalesCertifications import (
    CERTIFICATION_CATEGORY_CHOICES,
    CERTIFICATION_STATUS_CHOICES,
    SalesCertification,
)


@login_required
def sales_certification_list(request):
    qs = (
        SalesCertification.objects.filter(tenant=request.tenant)
        .select_related("rep", "certified_by", "hrm_course")
        .order_by("-certified_at", "-created_at")
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(curriculum_name__icontains=q)
            | Q(rep__username__icontains=q)
            | Q(rep__first_name__icontains=q)
            | Q(rep__last_name__icontains=q)
            | Q(number__icontains=q)
        )

    category = request.GET.get("category", "").strip()
    if category:
        qs = qs.filter(category=category)

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    rep_id = request.GET.get("rep", "").strip()
    if rep_id.isdigit():
        qs = qs.filter(rep_id=int(rep_id))

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    reps = User.objects.filter(tenant=request.tenant, is_active=True)

    context = {
        "certifications": page_obj,
        "category_choices": CERTIFICATION_CATEGORY_CHOICES,
        "status_choices": CERTIFICATION_STATUS_CHOICES,
        "reps": reps,
        "q": q,
        "category": category,
        "status": status,
        "rep_id": rep_id,
    }
    return render(request, "sales/salesenablement/salescertification/list.html", context)


@login_required
def sales_certification_detail(request, pk):
    certification = get_object_or_404(
        SalesCertification.objects.filter(tenant=request.tenant).select_related(
            "rep", "certified_by", "hrm_course"
        ),
        pk=pk,
    )
    context = {"certification": certification}
    return render(request, "sales/salesenablement/salescertification/detail.html", context)


@login_required
def sales_certification_create(request):
    if request.method == "POST":
        form = SalesCertificationForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                obj = form.save(commit=False)
                obj.tenant = request.tenant
                if not obj.certified_by_id and obj.status == "completed":
                    obj.certified_by = request.user
                obj.save()
                write_audit_log(
                    request.user,
                    obj,
                    "create",
                    changes={"curriculum": obj.curriculum_name, "number": obj.number},
                )
            messages.success(request, f"Certification record '{obj.curriculum_name}' created.")
            return redirect("sales:sales_certification_detail", pk=obj.pk)
    else:
        form = SalesCertificationForm(tenant=request.tenant)

    context = {"form": form, "certification": None, "is_edit": False}
    return render(request, "sales/salesenablement/salescertification/form.html", context)


@login_required
def sales_certification_edit(request, pk):
    obj = get_object_or_404(SalesCertification.objects.filter(tenant=request.tenant), pk=pk)
    if request.method == "POST":
        form = SalesCertificationForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                form.save()
                write_audit_log(
                    request.user,
                    obj,
                    "update",
                    changes={"curriculum": obj.curriculum_name, "number": obj.number},
                )
            messages.success(request, f"Certification record '{obj.curriculum_name}' updated.")
            return redirect("sales:sales_certification_detail", pk=obj.pk)
    else:
        form = SalesCertificationForm(instance=obj, tenant=request.tenant)

    context = {"form": form, "certification": obj, "is_edit": True}
    return render(request, "sales/salesenablement/salescertification/form.html", context)


@login_required
@require_POST
def sales_certification_delete(request, pk):
    obj = get_object_or_404(SalesCertification.objects.filter(tenant=request.tenant), pk=pk)
    name = obj.curriculum_name
    number = obj.number
    with transaction.atomic():
        write_audit_log(
            request.user,
            obj,
            "delete",
            changes={"curriculum": name, "number": number},
        )
        obj.delete()
    messages.success(request, f"Certification '{name}' deleted.")
    return redirect("sales:sales_certification_list")

