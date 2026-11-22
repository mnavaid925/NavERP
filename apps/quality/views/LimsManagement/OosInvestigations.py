from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.quality.forms.LimsManagement.OosInvestigations import OosInvestigationForm
from apps.quality.models.LimsManagement.OosInvestigations import OosInvestigation
from apps.quality.views._common import quality_object, quality_scope

PAGE_SIZE = 15


@login_required
def oos_investigation_list(request):
    qs = quality_scope(OosInvestigation.objects.all(), request).select_related(
        "test_worksheet", "sample", "investigation_lead", "qa_approver", "capa", "non_conformance"
    )

    query = request.GET.get("q", "").strip()
    if query:
        qs = qs.filter(
            Q(title__icontains=query)
            | Q(number__icontains=query)
            | Q(assignable_cause__icontains=query)
            | Q(lab_error_description__icontains=query)
            | Q(sample__number__icontains=query)
            | Q(sample__sample_name__icontains=query)
            | Q(test_worksheet__number__icontains=query)
        )

    selected_phase = request.GET.get("investigation_phase", "").strip()
    if selected_phase:
        qs = qs.filter(investigation_phase=selected_phase)

    selected_status = request.GET.get("status", "").strip()
    if selected_status:
        qs = qs.filter(status=selected_status)

    selected_severity = request.GET.get("severity", "").strip()
    if selected_severity:
        qs = qs.filter(severity=selected_severity)

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "investigations": page_obj.object_list,
        "phase_choices": OosInvestigation.PHASE_CHOICES,
        "status_choices": OosInvestigation.STATUS_CHOICES,
        "severity_choices": OosInvestigation.SEVERITY_CHOICES,
        "selected_phase": selected_phase,
        "selected_status": selected_status,
        "selected_severity": selected_severity,
        "query": query,
    }
    return render(request, "quality/lims_management/oos_investigation/list.html", context)


@login_required
def oos_investigation_detail(request, pk):
    investigation = quality_object(
        request,
        OosInvestigation,
        pk,
        select_related=[
            "test_worksheet",
            "test_worksheet__specification",
            "sample",
            "investigation_lead",
            "qa_approver",
            "capa",
            "non_conformance",
        ],
    )

    context = {
        "investigation": investigation,
    }
    return render(request, "quality/lims_management/oos_investigation/detail.html", context)


@login_required
def oos_investigation_create(request):
    initial = {}
    worksheet_id = request.GET.get("worksheet", "").strip()
    if worksheet_id.isdigit():
        initial["test_worksheet"] = worksheet_id
        try:
            from apps.quality.models.LimsManagement.LabTestWorksheets import LabTestWorksheet
            ws = LabTestWorksheet.objects.select_related("sample").get(pk=worksheet_id, tenant=request.tenant)
            initial["sample"] = ws.sample_id
            initial["title"] = f"OOS Investigation: {ws.title} ({ws.sample.number})"
        except Exception:
            pass

    sample_id = request.GET.get("sample", "").strip()
    if sample_id.isdigit() and "sample" not in initial:
        initial["sample"] = sample_id

    if request.method == "POST":
        form = OosInvestigationForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            if not obj.investigation_lead:
                obj.investigation_lead = request.user
            obj.save()
            write_audit_log(request.user, obj, "create", tenant=request.tenant)
            messages.success(request, f"OOS Investigation {obj.number} created successfully.")
            return redirect("quality:oos_investigation_detail", pk=obj.pk)
    else:
        form = OosInvestigationForm(initial=initial, tenant=request.tenant)

    context = {
        "form": form,
        "investigation": None,
        "is_edit": False,
    }
    return render(request, "quality/lims_management/oos_investigation/form.html", context)


@login_required
def oos_investigation_edit(request, pk):
    obj = quality_object(request, OosInvestigation, pk)
    if request.method == "POST":
        form = OosInvestigationForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(request.user, obj, "update", tenant=request.tenant)
            messages.success(request, f"OOS Investigation {obj.number} updated successfully.")
            return redirect("quality:oos_investigation_detail", pk=obj.pk)
    else:
        form = OosInvestigationForm(instance=obj, tenant=request.tenant)

    context = {
        "form": form,
        "investigation": obj,
        "is_edit": True,
    }
    return render(request, "quality/lims_management/oos_investigation/form.html", context)


@login_required
@require_POST
@tenant_admin_required
def oos_investigation_delete(request, pk):
    obj = quality_object(request, OosInvestigation, pk)
    if obj.status == "closed":
        messages.error(
            request,
            f"OOS Investigation {obj.number} is closed and archived under GxP regulatory audit trail rules.",
        )
        return redirect("quality:oos_investigation_detail", pk=obj.pk)
    number = obj.number
    write_audit_log(request.user, obj, "delete", tenant=request.tenant)
    obj.delete()
    messages.success(request, f"OOS Investigation {number} deleted successfully.")
    return redirect("quality:oos_investigation_list")


@login_required
@tenant_admin_required
@require_POST
def oos_investigation_close(request, pk):
    obj = quality_object(request, OosInvestigation, pk)
    if obj.status == "closed":
        messages.error(request, f"OOS Investigation {obj.number} is already closed.")
        return redirect("quality:oos_investigation_detail", pk=obj.pk)
    obj.status = "closed"
    obj.investigation_phase = "closed"
    obj.closed_at = timezone.now()
    obj.qa_approver = request.user
    obj.save()
    write_audit_log(request.user, obj, "close", tenant=request.tenant)
    messages.success(request, f"OOS Investigation {obj.number} officially closed and approved.")
    return redirect("quality:oos_investigation_detail", pk=obj.pk)
