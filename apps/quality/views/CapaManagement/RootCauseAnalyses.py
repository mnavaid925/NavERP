import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.quality.forms.CapaManagement.RootCauseAnalyses import RootCauseAnalysisForm
from apps.quality.models.CapaManagement.CapaInvestigations import CapaInvestigation
from apps.quality.models.CapaManagement.RootCauseAnalyses import RootCauseAnalysis
from apps.quality.views._common import quality_object, quality_scope


def csv_safe(value):
    if value is None:
        return ""
    text = str(value)
    if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r", "%")):
        return f"'{text}"
    return text


@login_required
def root_cause_analysis_list(request):
    qs = quality_scope(RootCauseAnalysis.objects.all(), request).select_related(
        "capa", "lead_investigator", "verified_by"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(number__icontains=q)
            | Q(problem_statement__icontains=q)
            | Q(root_cause_summary__icontains=q)
            | Q(escape_point_gap__icontains=q)
            | Q(capa__number__icontains=q)
            | Q(capa__title__icontains=q)
        )

    method_filter = request.GET.get("method", "").strip()
    if method_filter:
        qs = qs.filter(rca_method=method_filter)

    category_filter = request.GET.get("category", "").strip()
    if category_filter:
        qs = qs.filter(root_cause_category=category_filter)

    capa_filter = request.GET.get("capa", "").strip()
    if capa_filter.isdigit():
        qs = qs.filter(capa_id=int(capa_filter))

    base_qs = quality_scope(RootCauseAnalysis.objects.all(), request)
    stats = base_qs.aggregate(
        total_count=Count("id"),
        verified_count=Count("id", filter=Q(status="verified")),
    )

    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "rcas": page_obj,
        "total_count": stats["total_count"] or 0,
        "verified_count": stats["verified_count"] or 0,
        "q": q,
        "method_filter": method_filter,
        "category_filter": category_filter,
        "rca_method_choices": RootCauseAnalysis.RCA_METHOD_CHOICES,
        "root_cause_category_choices": RootCauseAnalysis.ROOT_CAUSE_CATEGORY_CHOICES,
    }
    return render(request, "quality/capamanagement/root_cause_analysis/list.html", context)


@login_required
def root_cause_analysis_detail(request, pk):
    rca = quality_object(
        request,
        RootCauseAnalysis,
        pk,
        select_related=["capa", "lead_investigator", "verified_by"],
    )
    linked_actions = rca.actions.all().select_related("assigned_to", "verified_by")

    context = {
        "rca": rca,
        "linked_actions": linked_actions,
    }
    return render(request, "quality/capamanagement/root_cause_analysis/detail.html", context)


@login_required
def root_cause_analysis_create(request):
    initial = {}
    capa_param = request.GET.get("capa", "").strip()
    if capa_param.isdigit():
        initial["capa"] = int(capa_param)

    if request.method == "POST":
        form = RootCauseAnalysisForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            rca = form.save()
            write_audit_log(request.user, rca, "create", tenant=request.tenant)
            messages.success(request, f"Root Cause Analysis {rca.number} initialized successfully.")
            return redirect("quality:root_cause_analysis_detail", pk=rca.pk)
    else:
        form = RootCauseAnalysisForm(initial=initial, tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
    }
    return render(request, "quality/capamanagement/root_cause_analysis/form.html", context)


@login_required
def root_cause_analysis_edit(request, pk):
    rca = quality_object(request, RootCauseAnalysis, pk)
    if rca.status == "verified":
        messages.warning(request, f"RCA {rca.number} has been verified and cannot be directly modified.")
        return redirect("quality:root_cause_analysis_detail", pk=rca.pk)

    if request.method == "POST":
        form = RootCauseAnalysisForm(request.POST, instance=rca, tenant=request.tenant)
        if form.is_valid():
            rca = form.save()
            write_audit_log(request.user, rca, "update", tenant=request.tenant)
            messages.success(request, f"Root Cause Analysis {rca.number} updated successfully.")
            return redirect("quality:root_cause_analysis_detail", pk=rca.pk)
    else:
        form = RootCauseAnalysisForm(instance=rca, tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": True,
        "rca": rca,
    }
    return render(request, "quality/capamanagement/root_cause_analysis/form.html", context)


@require_POST
@tenant_admin_required
def root_cause_analysis_delete(request, pk):
    rca = quality_object(request, RootCauseAnalysis, pk)
    if rca.status == "verified":
        messages.error(request, "Cannot delete a verified Root Cause Analysis record.")
        return redirect("quality:root_cause_analysis_detail", pk=rca.pk)
    if rca.capa.status == "closed":
        messages.error(request, "Cannot delete records belonging to a closed CAPA.")
        return redirect("quality:root_cause_analysis_detail", pk=rca.pk)
    num = rca.number
    capa_pk = rca.capa_id
    write_audit_log(request.user, rca, "delete", tenant=request.tenant)
    rca.delete()
    messages.success(request, f"Root Cause Analysis {num} was deleted.")
    return redirect("quality:capa_investigation_detail", pk=capa_pk)


@require_POST
@login_required
def root_cause_analysis_verify(request, pk):
    rca = quality_object(request, RootCauseAnalysis, pk)
    verification_notes = request.POST.get("verification_notes", "").strip()

    rca.status = "verified"
    rca.verified_by = request.user
    rca.verified_date = timezone.now().date()
    if verification_notes:
        rca.verification_notes = verification_notes
    rca.save()

    write_audit_log(request.user, rca, "verify", tenant=request.tenant)
    messages.success(request, f"Root Cause Analysis {rca.number} has been verified by Quality Engineering.")
    return redirect("quality:root_cause_analysis_detail", pk=rca.pk)


@login_required
def root_cause_analysis_export(request):
    qs = quality_scope(RootCauseAnalysis.objects.all(), request).select_related(
        "capa", "lead_investigator", "verified_by"
    )

    response = HttpResponse(content_type="text/csv")
    filename = f"Root_Cause_Analyses_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "RCA Number",
        "CAPA Number",
        "Method",
        "Category",
        "Problem Statement",
        "Root Cause Summary",
        "Status",
        "Lead Investigator",
        "Verified By",
        "Verified Date",
        "Created At",
    ])

    for r in qs:
        writer.writerow([
            csv_safe(r.number),
            csv_safe(r.capa.number if r.capa else ""),
            csv_safe(r.get_rca_method_display()),
            csv_safe(r.get_root_cause_category_display()),
            csv_safe(r.problem_statement),
            csv_safe(r.root_cause_summary),
            csv_safe(r.get_status_display()),
            csv_safe(r.lead_investigator.username if r.lead_investigator else ""),
            csv_safe(r.verified_by.username if r.verified_by else ""),
            csv_safe(r.verified_date),
            csv_safe(r.created_at.strftime("%Y-%m-%d %H:%M")),
        ])

    write_audit_log(request.user, RootCauseAnalysis(), "export", tenant=request.tenant)
    return response
