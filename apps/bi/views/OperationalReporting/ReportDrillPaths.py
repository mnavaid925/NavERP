from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.bi.forms.OperationalReporting.ReportDrillPaths import ReportDrillPathForm
from apps.bi.models.OperationalReporting.ReportDefinitions import ReportDefinition
from apps.bi.models.OperationalReporting.ReportDrillPaths import ReportDrillPath
from apps.bi.views._common import bi_object, bi_scope
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def report_drill_path_list(request):
    qs = bi_scope(
        ReportDrillPath.objects.select_related("source_report", "target_report").all(),
        request,
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(drill_label__icontains=q)
            | Q(source_field__icontains=q)
            | Q(source_report__name__icontains=q)
            | Q(number__icontains=q)
        )

    target_type = request.GET.get("target_type", "").strip()
    if target_type:
        qs = qs.filter(target_type=target_type)

    report_id = request.GET.get("report", "").strip()
    if report_id and report_id.isdigit():
        qs = qs.filter(source_report_id=report_id)

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    reports = ReportDefinition.objects.filter(tenant=request.tenant).order_by("name")

    context = {
        "page_obj": page_obj,
        "drill_paths": page_obj,
        "target_type_choices": ReportDrillPath.TARGET_TYPE_CHOICES,
        "reports": reports,
        "q": q,
        "target_type": target_type,
        "report_id": report_id,
    }
    return render(request, "bi/operational_reporting/report_drill_path/list.html", context)


@login_required
def report_drill_path_detail(request, pk):
    drill_path = bi_object(
        request,
        ReportDrillPath,
        pk,
        select_related=("source_report", "target_report", "source_report__created_by"),
    )
    can_edit = request.user.is_superuser or getattr(request, "is_tenant_admin", False)

    context = {
        "drill_path": drill_path,
        "can_edit": can_edit,
    }
    return render(request, "bi/operational_reporting/report_drill_path/detail.html", context)


@login_required
@tenant_admin_required
def report_drill_path_create(request):
    report_id = request.GET.get("report", "").strip()
    initial = {}
    if report_id and report_id.isdigit():
        source_report = get_object_or_404(ReportDefinition.objects.filter(tenant=request.tenant), pk=report_id)
        initial["source_report"] = source_report

    if request.method == "POST":
        form = ReportDrillPathForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                drill_path = form.save(commit=False)
                drill_path.tenant = request.tenant
                drill_path.save()
                write_audit_log(
                    request.user,
                    drill_path,
                    "create",
                    changes=form.cleaned_data,
                    tenant=request.tenant,
                )
            messages.success(request, f"Drill-through action '{drill_path.drill_label}' created successfully.")
            return redirect("bi:report_drill_path_detail", pk=drill_path.pk)
    else:
        form = ReportDrillPathForm(initial=initial, tenant=request.tenant)

    context = {
        "form": form,
        "drill_path": None,
        "is_edit": False,
    }
    return render(request, "bi/operational_reporting/report_drill_path/form.html", context)


@login_required
@tenant_admin_required
def report_drill_path_edit(request, pk):
    drill_path = bi_object(request, ReportDrillPath, pk)
    if request.method == "POST":
        form = ReportDrillPathForm(request.POST, instance=drill_path, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                drill_path = form.save()
                write_audit_log(
                    request.user,
                    drill_path,
                    "update",
                    changes=form.cleaned_data,
                    tenant=request.tenant,
                )
            messages.success(request, f"Drill-through action '{drill_path.drill_label}' updated successfully.")
            return redirect("bi:report_drill_path_detail", pk=drill_path.pk)
    else:
        form = ReportDrillPathForm(instance=drill_path, tenant=request.tenant)

    context = {
        "form": form,
        "drill_path": drill_path,
        "is_edit": True,
    }
    return render(request, "bi/operational_reporting/report_drill_path/form.html", context)


@login_required
@tenant_admin_required
@require_POST
def report_drill_path_delete(request, pk):
    drill_path = bi_object(request, ReportDrillPath, pk)
    source_pk = drill_path.source_report_id
    label = drill_path.drill_label
    with transaction.atomic():
        write_audit_log(
            request.user,
            drill_path,
            "delete",
            changes={"label": label, "number": drill_path.number},
            tenant=request.tenant,
        )
        drill_path.delete()
    messages.success(request, f"Drill path '{label}' deleted successfully.")
    return redirect("bi:report_definition_detail", pk=source_pk)
