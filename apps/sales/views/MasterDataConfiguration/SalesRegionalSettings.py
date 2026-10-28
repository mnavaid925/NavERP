"""Views for SalesRegionalSetting model."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.sales.forms.MasterDataConfiguration.SalesRegionalSettings import SalesRegionalSettingForm
from apps.sales.models.MasterDataConfiguration.SalesRegionalSettings import SalesRegionalSetting


@login_required
def srg_list(request):
    """List and filter sales regional configuration settings."""
    tenant = request.tenant
    qs = SalesRegionalSetting.objects.filter(tenant=tenant)

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(number__icontains=q)
            | Q(primary_currency__icontains=q)
            | Q(default_quote_terms__icontains=q)
            | Q(statutory_disclaimer__icontains=q)
        )

    selected_region = request.GET.get("region_code", "").strip()
    if selected_region:
        qs = qs.filter(region_code=selected_region)

    selected_framework = request.GET.get("compliance_framework", "").strip()
    if selected_framework:
        qs = qs.filter(compliance_framework=selected_framework)

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
        "settings": page_obj.object_list,
        "regional_settings": page_obj.object_list,
        "region_codes": SalesRegionalSetting.REGION_CODE_CHOICES,
        "compliance_frameworks": SalesRegionalSetting.COMPLIANCE_CHOICES,
        "q": q,
        "selected_region": selected_region,
        "selected_framework": selected_framework,
        "selected_active": selected_active,
    }
    return render(request, "sales/masterdataconfiguration/regionalsetting/list.html", context)


@login_required
def srg_detail(request, pk):
    """Detail view for a specific regional setting."""
    setting = get_object_or_404(
        SalesRegionalSetting.objects.filter(tenant=request.tenant),
        pk=pk,
    )
    return render(
        request,
        "sales/masterdataconfiguration/regionalsetting/detail.html",
        {"setting": setting, "regional_setting": setting},
    )


@login_required
@tenant_admin_required
def srg_create(request):
    """Create a new sales regional setting profile."""
    if request.method == "POST":
        form = SalesRegionalSettingForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            setting = form.save(commit=False)
            setting.tenant = request.tenant
            setting.save()
            write_audit_log(
                request.user,
                setting,
                "create",
                {"detail": f"Created regional setting {setting.number} ({setting.name})"},
                tenant=request.tenant,
            )
            messages.success(request, f"Regional setting {setting.number} created successfully.")
            return redirect("sales:srg_detail", pk=setting.pk)
    else:
        form = SalesRegionalSettingForm(tenant=request.tenant)

    return render(
        request,
        "sales/masterdataconfiguration/regionalsetting/form.html",
        {"form": form, "setting": None, "regional_setting": None, "is_edit": False},
    )


@login_required
@tenant_admin_required
def srg_edit(request, pk):
    """Edit an existing regional setting profile."""
    setting = get_object_or_404(
        SalesRegionalSetting.objects.filter(tenant=request.tenant),
        pk=pk,
    )
    if request.method == "POST":
        form = SalesRegionalSettingForm(request.POST, instance=setting, tenant=request.tenant)
        if form.is_valid():
            setting = form.save()
            write_audit_log(
                request.user,
                setting,
                "update",
                {"detail": f"Updated regional setting {setting.number}"},
                tenant=request.tenant,
            )
            messages.success(request, f"Regional setting {setting.number} updated successfully.")
            return redirect("sales:srg_detail", pk=setting.pk)
    else:
        form = SalesRegionalSettingForm(instance=setting, tenant=request.tenant)

    return render(
        request,
        "sales/masterdataconfiguration/regionalsetting/form.html",
        {"form": form, "setting": setting, "regional_setting": setting, "is_edit": True},
    )


@login_required
@tenant_admin_required
@require_POST
def srg_delete(request, pk):
    """Delete a regional setting profile."""
    setting = get_object_or_404(
        SalesRegionalSetting.objects.filter(tenant=request.tenant),
        pk=pk,
    )
    num = setting.number
    write_audit_log(
        request.user,
        setting,
        "delete",
        {"detail": f"Deleted regional setting {num}"},
        tenant=request.tenant,
    )
    setting.delete()
    messages.success(request, f"Regional setting {num} deleted.")
    return redirect("sales:srg_list")
