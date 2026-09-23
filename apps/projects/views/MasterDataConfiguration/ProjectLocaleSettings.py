"""Projects 7.19 — ProjectLocaleSetting views [PLS-]."""
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q

from apps.accounting.models.GeneralLedger.Currencies import Currency
from apps.core.models.Localization import Language, TimeZone
from apps.projects.forms.MasterDataConfiguration.ProjectLocaleSettings import ProjectLocaleSettingForm
from apps.projects.models.MasterDataConfiguration.ProjectLocaleSettings import ProjectLocaleSetting
from apps.projects.views._common import *


@login_required
def pls_list(request):
    """List project localization settings with filters and stats."""
    qs = ProjectLocaleSetting.objects.filter(tenant=request.tenant).select_related(
        "project", "language", "time_zone", "currency"
    )

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q) | Q(number__icontains=q))

    is_active = request.GET.get("is_active", "").strip()
    if is_active in ("active", "true", "1"):
        qs = qs.filter(is_active=True)
    elif is_active in ("inactive", "false", "0"):
        qs = qs.filter(is_active=False)

    stats = ProjectLocaleSetting.objects.filter(tenant=request.tenant).aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(is_active=True)),
        default_profiles=Count("id", filter=Q(is_default=True)),
        project_overrides=Count("id", filter=Q(project__isnull=False)),
    )

    paginator = Paginator(qs, 15)
    page_obj = paginator.get_page(request.GET.get("page"))

    return render(
        request,
        "projects/masterdataconfiguration/localesetting/list.html",
        {
            "locale_settings": page_obj.object_list,
            "page_obj": page_obj,
            "q": q,
            "is_active": is_active,
            "stats": stats,
        },
    )


@login_required
def pls_detail(request, pk):
    """View details of a project locale setting profile."""
    setting = get_object_or_404(
        ProjectLocaleSetting.objects.select_related("project", "language", "time_zone", "currency"),
        pk=pk,
        tenant=request.tenant,
    )
    return render(
        request,
        "projects/masterdataconfiguration/localesetting/detail.html",
        {
            "locale_setting": setting,
            "working_days_display": setting.working_days_display,
        },
    )


@login_required
def pls_create(request):
    """Create a new project locale setting profile."""
    if request.method == "POST":
        form = ProjectLocaleSettingForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            setting = form.save(commit=False)
            setting.tenant = request.tenant
            if setting.is_default and not setting.project_id:
                ProjectLocaleSetting.objects.filter(
                    tenant=request.tenant, project__isnull=True, is_default=True
                ).update(is_default=False)
            setting.save()
            write_audit_log(
                user=request.user,
                obj=setting,
                action="create",
                changes={"name": setting.name, "is_default": setting.is_default},
                tenant=request.tenant,
            )
            messages.success(request, f"Locale profile '{setting.name}' created successfully.")
            return redirect("projects:pls_detail", pk=setting.pk)
    else:
        form = ProjectLocaleSettingForm(tenant=request.tenant)

    return render(
        request,
        "projects/masterdataconfiguration/localesetting/form.html",
        {
            "form": form,
            "is_edit": False,
        },
    )


@login_required
def pls_edit(request, pk):
    """Edit an existing project locale setting profile."""
    setting = get_object_or_404(ProjectLocaleSetting, pk=pk, tenant=request.tenant)

    if request.method == "POST":
        form = ProjectLocaleSettingForm(request.POST, instance=setting, tenant=request.tenant)
        if form.is_valid():
            updated = form.save(commit=False)
            if updated.is_default and not updated.project_id:
                ProjectLocaleSetting.objects.filter(
                    tenant=request.tenant, project__isnull=True, is_default=True
                ).exclude(pk=setting.pk).update(is_default=False)
            updated.save()
            write_audit_log(
                user=request.user,
                obj=updated,
                action="update",
                changes={"name": updated.name, "is_default": updated.is_default},
                tenant=request.tenant,
            )
            messages.success(request, f"Locale profile '{updated.name}' updated successfully.")
            return redirect("projects:pls_detail", pk=updated.pk)
    else:
        form = ProjectLocaleSettingForm(instance=setting, tenant=request.tenant)

    return render(
        request,
        "projects/masterdataconfiguration/localesetting/form.html",
        {
            "form": form,
            "locale_setting": setting,
            "is_edit": True,
        },
    )


@login_required
@require_POST
@tenant_admin_required
def pls_delete(request, pk):
    """Delete a project locale setting profile."""
    setting = get_object_or_404(ProjectLocaleSetting, pk=pk, tenant=request.tenant)
    name = setting.name
    write_audit_log(
        user=request.user,
        obj=setting,
        action="delete",
        changes={"name": name},
        tenant=request.tenant,
    )
    setting.delete()
    messages.success(request, f"Locale profile '{name}' deleted successfully.")
    return redirect("projects:pls_list")


@login_required
@require_POST
def pls_set_default(request, pk):
    """Set profile as default workspace project locale setting."""
    setting = get_object_or_404(ProjectLocaleSetting, pk=pk, tenant=request.tenant)
    with transaction.atomic():
        ProjectLocaleSetting.objects.filter(
            tenant=request.tenant, project__isnull=True
        ).update(is_default=False)
        setting.is_default = True
        setting.save(update_fields=["is_default"])
        write_audit_log(
            user=request.user,
            obj=setting,
            action="update",
            changes={"set_default": True},
            tenant=request.tenant,
        )
    messages.success(request, f"Locale profile '{setting.name}' is now the default workspace configuration.")
    return redirect("projects:pls_detail", pk=setting.pk)
