import csv

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.quality.forms.CalibrationAnalysis.MeasurementSystemAnalyses import MeasurementSystemAnalysisForm
from apps.quality.models.CalibrationAnalysis.CalibrationGages import CalibrationGage
from apps.quality.models.CalibrationAnalysis.MeasurementSystemAnalyses import MeasurementSystemAnalysis
from apps.quality.views._common import _csv_safe, quality_object, quality_scope

PAGE_SIZE = 15


@login_required
def measurement_system_analysis_list(request):
    qs = quality_scope(MeasurementSystemAnalysis.objects.all(), request).select_related(
        "gage", "study_protocol_doc", "study_lead", "approved_by"
    )

    search_query = request.GET.get("q", "").strip()
    if search_query:
        qs = qs.filter(
            Q(number__icontains=search_query)
            | Q(study_title__icontains=search_query)
            | Q(gage__gage_id__icontains=search_query)
            | Q(gage__name__icontains=search_query)
            | Q(characteristic_name__icontains=search_query)
        )

    study_type_filter = request.GET.get("study_type", "").strip()
    if study_type_filter:
        qs = qs.filter(study_type=study_type_filter)

    result_filter = request.GET.get("study_result", "").strip()
    if result_filter:
        qs = qs.filter(study_result=result_filter)

    total_studies = qs.count()
    base_qs = quality_scope(MeasurementSystemAnalysis.objects.all(), request)
    acceptable_count = base_qs.filter(study_result="acceptable").count()

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "msa_studies": page_obj,
        "page_obj": page_obj,
        "search_query": search_query,
        "study_type_filter": study_type_filter,
        "result_filter": result_filter,
        "study_type_choices": MeasurementSystemAnalysis.STUDY_TYPE_CHOICES,
        "result_choices": MeasurementSystemAnalysis.RESULT_CHOICES,
        "total_studies": total_studies,
        "acceptable_count": acceptable_count,
    }
    return render(request, "quality/calibrationanalysis/measurement_system_analysis/list.html", context)


@login_required
def measurement_system_analysis_detail(request, pk):
    msa = quality_object(
        request, MeasurementSystemAnalysis, pk,
        select_related=("gage", "study_protocol_doc", "study_lead", "approved_by")
    )

    context = {
        "msa_study": msa,
        "obj": msa,
    }
    return render(request, "quality/calibrationanalysis/measurement_system_analysis/detail.html", context)


@login_required
def measurement_system_analysis_create(request):
    initial = {}
    gage_pk = request.GET.get("gage")
    if gage_pk and gage_pk.isdigit():
        initial["gage"] = gage_pk

    if request.method == "POST":
        form = MeasurementSystemAnalysisForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            msa = form.save(commit=False)
            msa.tenant = request.tenant
            msa.save()
            write_audit_log(request.user, msa, "create", tenant=request.tenant)
            messages.success(request, f"MSA Study {msa.number} created.")
            return redirect("quality:measurement_system_analysis_detail", pk=msa.pk)
    else:
        form = MeasurementSystemAnalysisForm(initial=initial, tenant=request.tenant)

    context = {
        "form": form,
        "msa_study": None,
        "obj": None,
        "is_edit": False,
    }
    return render(request, "quality/calibrationanalysis/measurement_system_analysis/form.html", context)


@login_required
def measurement_system_analysis_edit(request, pk):
    msa = quality_object(request, MeasurementSystemAnalysis, pk)
    if request.method == "POST":
        form = MeasurementSystemAnalysisForm(request.POST, instance=msa, tenant=request.tenant)
        if form.is_valid():
            msa = form.save()
            write_audit_log(request.user, msa, "update", tenant=request.tenant)
            messages.success(request, f"MSA Study {msa.number} updated.")
            return redirect("quality:measurement_system_analysis_detail", pk=msa.pk)
    else:
        form = MeasurementSystemAnalysisForm(instance=msa, tenant=request.tenant)

    context = {
        "form": form,
        "msa_study": msa,
        "obj": msa,
        "is_edit": True,
    }
    return render(request, "quality/calibrationanalysis/measurement_system_analysis/form.html", context)


@require_POST
@login_required
@tenant_admin_required
def measurement_system_analysis_delete(request, pk):
    msa = quality_object(request, MeasurementSystemAnalysis, pk)
    number = msa.number
    write_audit_log(request.user, msa, "delete", tenant=request.tenant)
    msa.delete()
    messages.success(request, f"MSA Study {number} deleted.")
    return redirect("quality:measurement_system_analysis_list")


@login_required
def measurement_system_analysis_export_csv(request):
    qs = quality_scope(MeasurementSystemAnalysis.objects.all(), request).select_related("gage").order_by("-study_date")
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="msa_studies.csv"'
    response["X-Content-Type-Options"] = "nosniff"

    writer = csv.writer(response)
    writer.writerow([
        "Study #", "Title", "Gage Tag", "Type", "Method",
        "Characteristic", "Study Date", "%GRR", "P/T Ratio", "NDC", "Verdict"
    ])
    for m in qs:
        writer.writerow([
            _csv_safe(m.number),
            _csv_safe(m.study_title),
            _csv_safe(m.gage.gage_id),
            _csv_safe(m.get_study_type_display()),
            _csv_safe(m.get_analysis_method_display()),
            _csv_safe(m.characteristic_name),
            _csv_safe(m.study_date.isoformat() if m.study_date else ""),
            _csv_safe(str(m.percent_gage_rr_study_variation)),
            _csv_safe(str(m.percent_tolerance_pt_ratio)),
            _csv_safe(str(m.number_of_distinct_categories_ndc)),
            _csv_safe(m.get_study_result_display()),
        ])
    return response
