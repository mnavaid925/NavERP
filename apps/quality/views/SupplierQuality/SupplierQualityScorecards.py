import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.crud import crud_create, crud_delete, crud_edit
from apps.core.decorators import tenant_admin_required
from apps.core.models import Party
from apps.core.utils import write_audit_log
from apps.quality.forms.SupplierQuality.SupplierQualityScorecards import (
    SupplierQualityScorecardForm,
)
from apps.quality.models.SupplierQuality.SupplierQualityScorecards import (
    SupplierQualityScorecard,
)

PAGE_SIZE = 15


def _csv_safe(val):
    if val is None:
        return ""
    s = str(val)
    if s.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + s
    return s


@login_required
def supplier_quality_scorecard_list(request):
    qs = SupplierQualityScorecard.objects.filter(tenant=request.tenant).select_related(
        "supplier", "evaluated_by"
    )

    search_query = request.GET.get("q", "").strip()
    if search_query:
        qs = qs.filter(
            Q(number__icontains=search_query)
            | Q(supplier__name__icontains=search_query)
            | Q(evaluation_notes__icontains=search_query)
        )

    current_status = request.GET.get("status", "").strip()
    if current_status:
        qs = qs.filter(status=current_status)

    current_grade = request.GET.get("grade", "").strip()
    if current_grade:
        qs = qs.filter(grade=current_grade)

    current_cadence = request.GET.get("cadence", "").strip()
    if current_cadence:
        qs = qs.filter(cadence=current_cadence)

    current_supplier = request.GET.get("supplier", "").strip()
    if current_supplier.isdigit():
        qs = qs.filter(supplier_id=int(current_supplier))

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page")
    scorecards = paginator.get_page(page_number)

    suppliers = Party.objects.filter(
        tenant=request.tenant, roles__role__in=("supplier", "vendor")
    ).distinct().order_by("name")
    if not suppliers.exists():
        suppliers = Party.objects.filter(tenant=request.tenant).order_by("name")

    context = {
        "scorecards": scorecards,
        "cadence_choices": SupplierQualityScorecard.CADENCE_CHOICES,
        "grade_choices": SupplierQualityScorecard.GRADE_CHOICES,
        "status_choices": SupplierQualityScorecard.STATUS_CHOICES,
        "suppliers": suppliers,
        "search_query": search_query,
        "current_status": current_status,
        "current_grade": current_grade,
        "current_cadence": current_cadence,
        "current_supplier": current_supplier,
    }
    return render(
        request,
        "quality/supplierquality/supplier_quality_scorecard/list.html",
        context,
    )


@login_required
def supplier_quality_scorecard_detail(request, pk):
    scorecard = get_object_or_404(
        SupplierQualityScorecard.objects.filter(tenant=request.tenant).select_related(
            "supplier", "evaluated_by"
        ),
        pk=pk,
    )
    context = {
        "scorecard": scorecard,
    }
    return render(
        request,
        "quality/supplierquality/supplier_quality_scorecard/detail.html",
        context,
    )


@login_required
def supplier_quality_scorecard_create(request):
    if request.method == "POST":
        form = SupplierQualityScorecardForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            scorecard = form.save(commit=False)
            scorecard.tenant = request.tenant
            scorecard.save()
            form.save_m2m()
            write_audit_log(request.user, scorecard, "create", tenant=request.tenant)
            messages.success(request, f"Scorecard {scorecard.number} generated successfully.")
            return redirect("quality:supplier_quality_scorecard_detail", pk=scorecard.pk)
    else:
        form = SupplierQualityScorecardForm(tenant=request.tenant)
    context = {
        "form": form,
        "is_edit": False,
        "scorecard": None,
    }
    return render(
        request,
        "quality/supplierquality/supplier_quality_scorecard/form.html",
        context,
    )


@login_required
def supplier_quality_scorecard_edit(request, pk):
    scorecard = get_object_or_404(SupplierQualityScorecard, pk=pk, tenant=request.tenant)
    if request.method == "POST":
        form = SupplierQualityScorecardForm(request.POST, instance=scorecard, tenant=request.tenant)
        if form.is_valid():
            scorecard = form.save()
            write_audit_log(request.user, scorecard, "update", tenant=request.tenant)
            messages.success(request, f"Scorecard {scorecard.number} updated successfully.")
            return redirect("quality:supplier_quality_scorecard_detail", pk=scorecard.pk)
    else:
        form = SupplierQualityScorecardForm(instance=scorecard, tenant=request.tenant)
    context = {
        "form": form,
        "is_edit": True,
        "scorecard": scorecard,
    }
    return render(
        request,
        "quality/supplierquality/supplier_quality_scorecard/form.html",
        context,
    )


@login_required
@require_POST
def supplier_quality_scorecard_delete(request, pk):
    scorecard = get_object_or_404(SupplierQualityScorecard, pk=pk, tenant=request.tenant)
    write_audit_log(request.user, scorecard, "delete", tenant=request.tenant)
    scorecard.delete()
    messages.success(request, f"Scorecard {scorecard.number} deleted successfully.")
    return redirect("quality:supplier_quality_scorecard_list")


@login_required
def supplier_quality_scorecard_export(request):
    qs = SupplierQualityScorecard.objects.filter(tenant=request.tenant).select_related("supplier", "evaluated_by")
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="supplier_quality_scorecards.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Scorecard #",
        "Supplier",
        "Cadence",
        "Period Start",
        "Period End",
        "Status",
        "Overall Score",
        "Grade",
        "Lot Acceptance (30%)",
        "Defect PPM (25%)",
        "SCAR Response (20%)",
        "Audit Score (15%)",
        "Documentation (10%)",
        "Lots Received",
        "Lots Rejected",
        "Evaluated By",
    ])
    for obj in qs:
        writer.writerow([
            _csv_safe(obj.number),
            _csv_safe(obj.supplier.name if obj.supplier else ""),
            _csv_safe(obj.get_cadence_display()),
            _csv_safe(obj.period_start),
            _csv_safe(obj.period_end),
            _csv_safe(obj.get_status_display()),
            _csv_safe(obj.overall_score),
            _csv_safe(obj.get_grade_display()),
            _csv_safe(obj.lot_acceptance_rate_score),
            _csv_safe(obj.defect_ppm_score),
            _csv_safe(obj.scar_responsiveness_score),
            _csv_safe(obj.audit_compliance_score),
            _csv_safe(obj.documentation_coa_score),
            _csv_safe(obj.total_lots_received),
            _csv_safe(obj.lots_rejected),
            _csv_safe(obj.evaluated_by.get_full_name() if obj.evaluated_by else ""),
        ])
    return response


@login_required
@require_POST
@tenant_admin_required
def supplier_quality_scorecard_publish(request, pk):
    scorecard = get_object_or_404(SupplierQualityScorecard, pk=pk, tenant=request.tenant)
    if scorecard.status != "published":
        scorecard.status = "published"
        scorecard.save(update_fields=["status", "updated_at"])
        write_audit_log(
            request.user,
            scorecard,
            "publish",
            tenant=request.tenant,
        )
        messages.success(request, f"Scorecard {scorecard.number} has been published successfully.")
    else:
        messages.info(request, f"Scorecard {scorecard.number} is already published.")
    return redirect("quality:supplier_quality_scorecard_detail", pk=scorecard.pk)
