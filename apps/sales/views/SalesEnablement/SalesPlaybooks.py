"""Sales 8.9 — Views for `SalesPlaybook`."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.sales.forms.SalesEnablement.SalesPlaybooks import SalesPlaybookForm
from apps.sales.models.OpportunityPipeline.Pipelines import Pipeline
from apps.sales.models.SalesEnablement.SalesPlaybooks import (
    PLAYBOOK_STATUS_CHOICES,
    SELLING_MOTION_CHOICES,
    SalesPlaybook,
)


@login_required
def sales_playbook_list(request):
    qs = (
        SalesPlaybook.objects.filter(tenant=request.tenant)
        .select_related("pipeline", "owner")
        .order_by("-updated_at")
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(summary__icontains=q)
            | Q(target_audience__icontains=q)
            | Q(number__icontains=q)
        )

    motion_type = request.GET.get("motion_type", "").strip()
    if motion_type:
        qs = qs.filter(motion_type=motion_type)

    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    pipeline_id = request.GET.get("pipeline", "").strip()
    if pipeline_id.isdigit():
        qs = qs.filter(pipeline_id=int(pipeline_id))

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    pipelines = Pipeline.objects.filter(tenant=request.tenant, is_active=True)

    context = {
        "playbooks": page_obj,
        "motion_type_choices": SELLING_MOTION_CHOICES,
        "status_choices": PLAYBOOK_STATUS_CHOICES,
        "pipelines": pipelines,
        "q": q,
        "motion_type": motion_type,
        "status": status,
        "pipeline_id": pipeline_id,
    }
    return render(request, "sales/salesenablement/salesplaybook/list.html", context)


@login_required
def sales_playbook_detail(request, pk):
    playbook = get_object_or_404(
        SalesPlaybook.objects.filter(tenant=request.tenant).select_related(
            "pipeline", "owner"
        ),
        pk=pk,
    )
    context = {"playbook": playbook}
    return render(request, "sales/salesenablement/salesplaybook/detail.html", context)


@login_required
def sales_playbook_create(request):
    if request.method == "POST":
        form = SalesPlaybookForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            if not obj.owner_id:
                obj.owner = request.user
            obj.save()
            write_audit_log(
                request.user,
                obj,
                "create",
                changes={"name": obj.name, "number": obj.number},
            )
            messages.success(request, f"Sales playbook '{obj.name}' created.")
            return redirect("sales:sales_playbook_detail", pk=obj.pk)
    else:
        form = SalesPlaybookForm(tenant=request.tenant)

    context = {"form": form, "playbook": None, "is_edit": False}
    return render(request, "sales/salesenablement/salesplaybook/form.html", context)


@login_required
def sales_playbook_edit(request, pk):
    obj = get_object_or_404(SalesPlaybook.objects.filter(tenant=request.tenant), pk=pk)
    if request.method == "POST":
        form = SalesPlaybookForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            form.save()
            write_audit_log(
                request.user,
                obj,
                "update",
                changes={"name": obj.name, "number": obj.number},
            )
            messages.success(request, f"Sales playbook '{obj.name}' updated.")
            return redirect("sales:sales_playbook_detail", pk=obj.pk)
    else:
        form = SalesPlaybookForm(instance=obj, tenant=request.tenant)

    context = {"form": form, "playbook": obj, "is_edit": True}
    return render(request, "sales/salesenablement/salesplaybook/form.html", context)


@login_required
@require_POST
def sales_playbook_delete(request, pk):
    obj = get_object_or_404(SalesPlaybook.objects.filter(tenant=request.tenant), pk=pk)
    name = obj.name
    number = obj.number
    write_audit_log(
        request.user,
        obj,
        "delete",
        changes={"name": name, "number": number},
    )
    obj.delete()
    messages.success(request, f"Sales playbook '{name}' deleted.")
    return redirect("sales:sales_playbook_list")
