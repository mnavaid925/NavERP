import csv

from django.apps import apps
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.quality.forms.InProcessQuality.FirstArticleInspections import FirstArticleInspectionForm
from apps.quality.models.InProcessQuality.FirstArticleInspections import FirstArticleInspection

PAGE_SIZE = 15


def _csv_safe(val):
    if val is None:
        return ""
    s = str(val)
    if s.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + s
    return s


@login_required
def first_article_inspection_list(request):
    qs = FirstArticleInspection.objects.filter(tenant=request.tenant).select_related(
        "work_order", "work_center", "inspector", "approved_by", "non_conformance"
    )

    search_query = request.GET.get("q", "").strip()
    if search_query:
        qs = qs.filter(
            Q(number__icontains=search_query)
            | Q(title__icontains=search_query)
            | Q(item_code__icontains=search_query)
            | Q(item_name__icontains=search_query)
            | Q(drawing_number__icontains=search_query)
            | Q(machine_tooling_id__icontains=search_query)
            | Q(production_order_number__icontains=search_query)
        )

    current_status = request.GET.get("status", "").strip()
    if current_status:
        qs = qs.filter(status=current_status)

    current_type = request.GET.get("fai_type", "").strip()
    if current_type:
        qs = qs.filter(fai_type=current_type)

    current_reason = request.GET.get("setup_reason", "").strip()
    if current_reason:
        qs = qs.filter(setup_reason=current_reason)

    current_verdict = request.GET.get("release_verdict", "").strip()
    if current_verdict:
        qs = qs.filter(release_verdict=current_verdict)

    current_work_center = request.GET.get("work_center", "").strip()
    if current_work_center.isdigit():
        qs = qs.filter(work_center_id=int(current_work_center))

    total_fais_count = FirstArticleInspection.objects.filter(tenant=request.tenant).count()
    approved_count = FirstArticleInspection.objects.filter(tenant=request.tenant, status="approved_run_released").count()
    conditional_count = FirstArticleInspection.objects.filter(tenant=request.tenant, status="conditional_approval").count()
    rejected_count = FirstArticleInspection.objects.filter(tenant=request.tenant, status="rejected_setup_hold").count()

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    work_centers = []
    try:
        WorkCenter = apps.get_model("scm", "WorkCenter")
        work_centers = list(WorkCenter.objects.filter(tenant=request.tenant).only("id", "code", "name").order_by("code"))
    except LookupError:
        pass

    context = {
        "page_obj": page_obj,
        "fais": page_obj,
        "status_choices": FirstArticleInspection.STATUS_CHOICES,
        "fai_type_choices": FirstArticleInspection.FAI_TYPE_CHOICES,
        "setup_reason_choices": FirstArticleInspection.SETUP_REASON_CHOICES,
        "verdict_choices": FirstArticleInspection.RELEASE_VERDICT_CHOICES,
        "work_centers": work_centers,
        "total_fais_count": total_fais_count,
        "approved_count": approved_count,
        "conditional_count": conditional_count,
        "rejected_count": rejected_count,
        "search_query": search_query,
        "current_status": current_status,
        "current_type": current_type,
        "current_reason": current_reason,
        "current_verdict": current_verdict,
        "current_work_center": current_work_center,
    }
    return render(
        request,
        "quality/inprocessquality/first_article_inspection/list.html",
        context,
    )


@login_required
def first_article_inspection_detail(request, pk):
    fai = get_object_or_404(
        FirstArticleInspection.objects.filter(tenant=request.tenant).select_related(
            "work_order", "work_center", "inspector", "approved_by", "non_conformance"
        ),
        pk=pk,
    )
    context = {
        "fai": fai,
    }
    return render(
        request,
        "quality/inprocessquality/first_article_inspection/detail.html",
        context,
    )


@login_required
def first_article_inspection_create(request):
    if request.method == "POST":
        form = FirstArticleInspectionForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            fai = form.save(commit=False)
            fai.tenant = request.tenant
            if fai.status == "approved_run_released" or fai.release_verdict == "released":
                fai.approved_by = request.user
                fai.approved_at = timezone.now()
            fai.save()
            form.save_m2m()
            write_audit_log(request.user, fai, "create", tenant=request.tenant)
            messages.success(request, f"First Article Inspection {fai.number} recorded successfully.")
            return redirect("quality:first_article_inspection_detail", pk=fai.pk)
    else:
        form = FirstArticleInspectionForm(tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
        "fai": None,
        "title": "New First Article Inspection",
    }
    return render(
        request,
        "quality/inprocessquality/first_article_inspection/form.html",
        context,
    )


@login_required
def first_article_inspection_edit(request, pk):
    fai = get_object_or_404(FirstArticleInspection, pk=pk, tenant=request.tenant)
    if request.method == "POST":
        form = FirstArticleInspectionForm(request.POST, instance=fai, tenant=request.tenant)
        if form.is_valid():
            fai = form.save(commit=False)
            if (fai.status == "approved_run_released" or fai.release_verdict == "released") and not fai.approved_at:
                fai.approved_by = request.user
                fai.approved_at = timezone.now()
            fai.save()
            form.save_m2m()
            write_audit_log(request.user, fai, "update", tenant=request.tenant)
            messages.success(request, f"First Article Inspection {fai.number} updated successfully.")
            return redirect("quality:first_article_inspection_detail", pk=fai.pk)
    else:
        form = FirstArticleInspectionForm(instance=fai, tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": True,
        "fai": fai,
        "title": f"Edit First Article Inspection: {fai.number}",
    }
    return render(
        request,
        "quality/inprocessquality/first_article_inspection/form.html",
        context,
    )


@login_required
@require_POST
@tenant_admin_required
def first_article_inspection_release(request, pk):
    fai = get_object_or_404(FirstArticleInspection, pk=pk, tenant=request.tenant)
    if fai.status == "approved_run_released":
        messages.info(request, "Production run is already approved and released.")
        return redirect("quality:first_article_inspection_detail", pk=fai.pk)

    if fai.total_characteristics_inspected <= 0:
        messages.error(request, "Cannot release production run: Total characteristics inspected must be greater than zero.")
        return redirect("quality:first_article_inspection_detail", pk=fai.pk)

    if fai.characteristics_out_of_spec > 0:
        messages.error(request, "Cannot release production run: Characteristics have out-of-spec dimensions.")
        return redirect("quality:first_article_inspection_detail", pk=fai.pk)

    fai.status = "approved_run_released"
    fai.release_verdict = "released"
    fai.approved_by = request.user
    fai.approved_at = timezone.now()
    fai.as9102_form1_complete = True
    fai.as9102_form2_complete = True
    fai.as9102_form3_complete = True
    fai.save()
    write_audit_log(request.user, fai, "release", tenant=request.tenant)
    messages.success(request, f"Production run released for {fai.number}. Machine setup approved.")
    return redirect("quality:first_article_inspection_detail", pk=fai.pk)


@login_required
@require_POST
@tenant_admin_required
def first_article_inspection_delete(request, pk):
    fai = get_object_or_404(FirstArticleInspection, pk=pk, tenant=request.tenant)
    number = fai.number
    write_audit_log(request.user, fai, "delete", tenant=request.tenant)
    fai.delete()
    messages.success(request, f"First Article Inspection {number} deleted successfully.")
    return redirect("quality:first_article_inspection_list")


@login_required
def first_article_inspection_export_csv(request):
    qs = FirstArticleInspection.objects.filter(tenant=request.tenant).order_by("-created_at")

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="first_article_inspections.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "FAI Number",
        "Title",
        "FAI Type",
        "Setup Reason",
        "Status",
        "Release Verdict",
        "Item Code",
        "Drawing Number",
        "Revision",
        "Total Characteristics",
        "Conforming",
        "Out of Spec",
        "Max Deviation",
        "AS9102 Forms Verified",
        "Approved At",
    ])
    for item in qs:
        as9102_str = "Complete" if item.as9102_completed_all else "Incomplete"
        writer.writerow([
            _csv_safe(item.number),
            _csv_safe(item.title),
            _csv_safe(item.get_fai_type_display()),
            _csv_safe(item.get_setup_reason_display()),
            _csv_safe(item.get_status_display()),
            _csv_safe(item.get_release_verdict_display()),
            _csv_safe(item.item_code),
            _csv_safe(item.drawing_number),
            _csv_safe(item.drawing_revision),
            _csv_safe(item.total_characteristics_inspected),
            _csv_safe(item.characteristics_conforming),
            _csv_safe(item.characteristics_out_of_spec),
            _csv_safe(item.max_deviation_found),
            _csv_safe(as9102_str),
            _csv_safe(item.approved_at),
        ])

    return response
