"""Views for SalesMethodology model."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.sales.forms.MasterDataConfiguration.SalesMethodologies import SalesMethodologyForm
from apps.sales.models.MasterDataConfiguration.SalesMethodologies import SalesMethodology
from apps.sales.models.OpportunityPipeline.Pipelines import Pipeline


@login_required
def smd_list(request):
    """List and filter sales methodology templates."""
    tenant = request.tenant
    qs = SalesMethodology.objects.filter(tenant=tenant).select_related(
        "pipeline", "gating_stage"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(number__icontains=q)
            | Q(coaching_guidelines__icontains=q)
        )

    selected_framework = request.GET.get("framework", "").strip()
    if selected_framework:
        qs = qs.filter(framework=selected_framework)

    selected_pipeline = request.GET.get("pipeline", "").strip()
    if selected_pipeline and selected_pipeline.isdigit():
        qs = qs.filter(pipeline_id=int(selected_pipeline))

    selected_active = request.GET.get("is_active", "").strip()
    if selected_active in ["true", "1"]:
        qs = qs.filter(is_active=True)
    elif selected_active in ["false", "0"]:
        qs = qs.filter(is_active=False)

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    pipelines = Pipeline.objects.filter(tenant=tenant, is_active=True)

    context = {
        "page_obj": page_obj,
        "methodologies": page_obj.object_list,
        "frameworks": SalesMethodology.FRAMEWORK_CHOICES,
        "pipelines": pipelines,
        "q": q,
        "selected_framework": selected_framework,
        "selected_pipeline": selected_pipeline,
        "selected_active": selected_active,
    }
    return render(request, "sales/masterdataconfiguration/salesmethodology/list.html", context)


@login_required
def smd_detail(request, pk):
    """Detail view for a specific sales methodology template."""
    methodology = get_object_or_404(
        SalesMethodology.objects.filter(tenant=request.tenant).select_related(
            "pipeline", "gating_stage"
        ),
        pk=pk,
    )
    return render(
        request,
        "sales/masterdataconfiguration/salesmethodology/detail.html",
        {"methodology": methodology},
    )


@login_required
def smd_create(request):
    """Create a new sales methodology template."""
    if request.method == "POST":
        form = SalesMethodologyForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            methodology = form.save(commit=False)
            methodology.tenant = request.tenant
            methodology.save()
            write_audit_log(
                request.user,
                "create",
                methodology,
                f"Created sales methodology {methodology.number} ({methodology.name})",
            )
            messages.success(request, f"Sales methodology {methodology.number} created successfully.")
            return redirect("sales:smd_detail", pk=methodology.pk)
    else:
        form = SalesMethodologyForm(tenant=request.tenant)

    return render(
        request,
        "sales/masterdataconfiguration/salesmethodology/form.html",
        {"form": form, "methodology": None, "is_edit": False},
    )


@login_required
def smd_edit(request, pk):
    """Edit an existing sales methodology template."""
    methodology = get_object_or_404(
        SalesMethodology.objects.filter(tenant=request.tenant),
        pk=pk,
    )
    if request.method == "POST":
        form = SalesMethodologyForm(request.POST, instance=methodology, tenant=request.tenant)
        if form.is_valid():
            methodology = form.save()
            write_audit_log(
                request.user,
                "update",
                methodology,
                f"Updated sales methodology {methodology.number}",
            )
            messages.success(request, f"Sales methodology {methodology.number} updated successfully.")
            return redirect("sales:smd_detail", pk=methodology.pk)
    else:
        form = SalesMethodologyForm(instance=methodology, tenant=request.tenant)

    return render(
        request,
        "sales/masterdataconfiguration/salesmethodology/form.html",
        {"form": form, "methodology": methodology, "is_edit": True},
    )


@login_required
@require_POST
def smd_delete(request, pk):
    """Delete a sales methodology template."""
    methodology = get_object_or_404(
        SalesMethodology.objects.filter(tenant=request.tenant),
        pk=pk,
    )
    num = methodology.number
    write_audit_log(
        request.user,
        "delete",
        methodology,
        f"Deleted sales methodology {num}",
    )
    methodology.delete()
    messages.success(request, f"Sales methodology {num} deleted.")
    return redirect("sales:smd_list")
