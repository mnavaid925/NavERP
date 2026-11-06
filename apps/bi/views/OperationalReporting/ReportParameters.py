from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.bi.forms.OperationalReporting.ReportParameters import ReportParameterForm
from apps.bi.models.OperationalReporting.ReportDefinitions import ReportDefinition
from apps.bi.models.OperationalReporting.ReportParameters import ReportParameter
from apps.bi.views._common import bi_object, bi_scope
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def report_parameter_list(request):
    qs = bi_scope(ReportParameter.objects.select_related("report").all(), request)

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(prompt_label__icontains=q)
            | Q(parameter_name__icontains=q)
            | Q(report__name__icontains=q)
            | Q(number__icontains=q)
        )

    parameter_type = request.GET.get("parameter_type", "").strip()
    if parameter_type:
        qs = qs.filter(parameter_type=parameter_type)

    report_id = request.GET.get("report", "").strip()
    if report_id and report_id.isdigit():
        qs = qs.filter(report_id=report_id)

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    reports = (
        ReportDefinition.objects.filter(tenant=request.tenant)
        .only("id", "name", "number")
        .order_by("name")
    )

    context = {
        "page_obj": page_obj,
        "parameters": page_obj,
        "type_choices": ReportParameter.PARAMETER_TYPE_CHOICES,
        "reports": reports,
        "q": q,
        "parameter_type": parameter_type,
        "report_id": report_id,
    }
    return render(request, "bi/operational_reporting/report_parameter/list.html", context)


@login_required
def report_parameter_detail(request, pk):
    parameter = bi_object(
        request,
        ReportParameter,
        pk,
        select_related=("report", "report__created_by"),
    )
    can_edit = request.user.is_superuser or getattr(request, "is_tenant_admin", False)

    context = {
        "parameter": parameter,
        "report": parameter.report,
        "can_edit": can_edit,
    }
    return render(request, "bi/operational_reporting/report_parameter/detail.html", context)


@login_required
@tenant_admin_required
def report_parameter_create(request):
    report_id = request.GET.get("report", "").strip()
    initial = {}
    if report_id and report_id.isdigit():
        report = get_object_or_404(ReportDefinition.objects.filter(tenant=request.tenant), pk=report_id)
        initial["report"] = report

    if request.method == "POST":
        form = ReportParameterForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                parameter = form.save(commit=False)
                parameter.tenant = request.tenant
                parameter.save()
                write_audit_log(
                    request.user,
                    parameter,
                    "create",
                    changes=form.cleaned_data,
                    tenant=request.tenant,
                )
            messages.success(request, f"Parameter '{parameter.prompt_label}' added successfully.")
            return redirect("bi:report_parameter_detail", pk=parameter.pk)
    else:
        form = ReportParameterForm(initial=initial, tenant=request.tenant)

    context = {
        "form": form,
        "parameter": None,
        "is_edit": False,
    }
    return render(request, "bi/operational_reporting/report_parameter/form.html", context)


@login_required
@tenant_admin_required
def report_parameter_edit(request, pk):
    parameter = bi_object(request, ReportParameter, pk)
    if request.method == "POST":
        form = ReportParameterForm(request.POST, instance=parameter, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                parameter = form.save()
                write_audit_log(
                    request.user,
                    parameter,
                    "update",
                    changes=form.cleaned_data,
                    tenant=request.tenant,
                )
            messages.success(request, f"Parameter '{parameter.prompt_label}' updated successfully.")
            return redirect("bi:report_parameter_detail", pk=parameter.pk)
    else:
        form = ReportParameterForm(instance=parameter, tenant=request.tenant)

    context = {
        "form": form,
        "parameter": parameter,
        "is_edit": True,
    }
    return render(request, "bi/operational_reporting/report_parameter/form.html", context)


@login_required
@tenant_admin_required
@require_POST
def report_parameter_delete(request, pk):
    parameter = bi_object(request, ReportParameter, pk)
    report_pk = parameter.report_id
    label = parameter.prompt_label
    with transaction.atomic():
        write_audit_log(
            request.user,
            parameter,
            "delete",
            changes={"label": label, "number": parameter.number},
            tenant=request.tenant,
        )
        parameter.delete()
    messages.success(request, f"Parameter '{label}' deleted successfully.")
    return redirect("bi:report_definition_detail", pk=report_pk)
