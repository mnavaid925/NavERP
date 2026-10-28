"""Views for SalesCustomEntityDefinition model."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.sales.forms.MasterDataConfiguration.SalesCustomEntityDefinitions import SalesCustomEntityDefinitionForm
from apps.sales.models.MasterDataConfiguration.SalesCustomEntityDefinitions import SalesCustomEntityDefinition


@login_required
def sco_list(request):
    """List and filter custom entity and field definitions."""
    tenant = request.tenant
    qs = SalesCustomEntityDefinition.objects.filter(tenant=tenant)

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(entity_code__icontains=q)
            | Q(number__icontains=q)
            | Q(formula_expression__icontains=q)
            | Q(description__icontains=q)
        )

    selected_target_model = request.GET.get("target_model", "").strip()
    if selected_target_model:
        qs = qs.filter(target_model=selected_target_model)

    selected_field_type = request.GET.get("field_type", "").strip()
    if selected_field_type:
        qs = qs.filter(field_type=selected_field_type)

    selected_active = request.GET.get("is_active", "").strip()
    if selected_active in ["true", "1"]:
        qs = qs.filter(is_active=True)
    elif selected_active in ["false", "0"]:
        qs = qs.filter(is_active=False)

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "definitions": page_obj.object_list,
        "target_models": SalesCustomEntityDefinition.TARGET_MODEL_CHOICES,
        "field_types": SalesCustomEntityDefinition.FIELD_TYPE_CHOICES,
        "q": q,
        "selected_target_model": selected_target_model,
        "selected_field_type": selected_field_type,
        "selected_active": selected_active,
    }
    return render(request, "sales/masterdataconfiguration/customentitydefinition/list.html", context)


@login_required
def sco_detail(request, pk):
    """Detail view for a custom entity or field definition."""
    definition = get_object_or_404(
        SalesCustomEntityDefinition.objects.filter(tenant=request.tenant),
        pk=pk,
    )
    return render(
        request,
        "sales/masterdataconfiguration/customentitydefinition/detail.html",
        {"definition": definition},
    )


@login_required
def sco_create(request):
    """Create a new custom entity or field definition."""
    if request.method == "POST":
        form = SalesCustomEntityDefinitionForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            definition = form.save(commit=False)
            definition.tenant = request.tenant
            definition.save()
            write_audit_log(
                request.user,
                "create",
                definition,
                f"Created custom entity definition {definition.number} ({definition.name})",
            )
            messages.success(request, f"Custom definition {definition.number} created successfully.")
            return redirect("sales:sco_detail", pk=definition.pk)
    else:
        form = SalesCustomEntityDefinitionForm(tenant=request.tenant)

    return render(
        request,
        "sales/masterdataconfiguration/customentitydefinition/form.html",
        {"form": form, "definition": None, "is_edit": False},
    )


@login_required
def sco_edit(request, pk):
    """Edit an existing custom entity or field definition."""
    definition = get_object_or_404(
        SalesCustomEntityDefinition.objects.filter(tenant=request.tenant),
        pk=pk,
    )
    if request.method == "POST":
        form = SalesCustomEntityDefinitionForm(request.POST, instance=definition, tenant=request.tenant)
        if form.is_valid():
            definition = form.save()
            write_audit_log(
                request.user,
                "update",
                definition,
                f"Updated custom entity definition {definition.number}",
            )
            messages.success(request, f"Custom definition {definition.number} updated successfully.")
            return redirect("sales:sco_detail", pk=definition.pk)
    else:
        form = SalesCustomEntityDefinitionForm(instance=definition, tenant=request.tenant)

    return render(
        request,
        "sales/masterdataconfiguration/customentitydefinition/form.html",
        {"form": form, "definition": definition, "is_edit": True},
    )


@login_required
@require_POST
def sco_delete(request, pk):
    """Delete a custom entity or field definition."""
    definition = get_object_or_404(
        SalesCustomEntityDefinition.objects.filter(tenant=request.tenant),
        pk=pk,
    )
    num = definition.number
    write_audit_log(
        request.user,
        "delete",
        definition,
        f"Deleted custom entity definition {num}",
    )
    definition.delete()
    messages.success(request, f"Custom definition {num} deleted.")
    return redirect("sales:sco_list")
