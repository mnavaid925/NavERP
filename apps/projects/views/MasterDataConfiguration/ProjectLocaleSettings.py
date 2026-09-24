"""Projects 7.19 — ProjectLocaleSetting views [PLS-]."""
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q

from apps.accounting.models.GeneralLedger.Currencies import Currency
from apps.core.crud import as_db_int
from apps.core.models import BusinessCalendar, LocaleProfile, Tenant
from apps.core.models.Localization import Language, TimeZone
from apps.projects.forms.MasterDataConfiguration.ProjectLocaleSettings import ProjectLocaleSettingForm
from apps.projects.models.MasterDataConfiguration.ProjectLocaleSettings import ProjectLocaleSetting
from apps.projects.views._common import *


@login_required
def pls_list(request):
    """List project localization settings with filters and stats."""
    qs = ProjectLocaleSetting.objects.filter(tenant=request.tenant).select_related(
        "project", "language", "time_zone", "currency"
    ).order_by("-is_default", "name", "-id")

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(code__icontains=q) | Q(number__icontains=q))

    is_active = request.GET.get("is_active", "").strip()
    if is_active in ("active", "true", "1"):
        is_active = "active"
        qs = qs.filter(is_active=True)
    elif is_active in ("inactive", "false", "0"):
        is_active = "inactive"
        qs = qs.filter(is_active=False)

    language_id = request.GET.get("language", "").strip()
    language_pk = as_db_int(language_id)
    if language_pk is not None and language_pk > 0:
        qs = qs.filter(language_id=language_pk)

    time_zone_id = request.GET.get("time_zone", "").strip()
    time_zone_pk = as_db_int(time_zone_id)
    if time_zone_pk is not None and time_zone_pk > 0:
        qs = qs.filter(time_zone_id=time_zone_pk)

    currency_id = request.GET.get("currency", "").strip()
    currency_pk = as_db_int(currency_id)
    if currency_pk is not None and currency_pk > 0:
        qs = qs.filter(currency_id=currency_pk)

    languages = Language.objects.filter(is_active=True).order_by("name")
    time_zones = TimeZone.objects.filter(is_active=True).order_by("name")
    currencies = Currency.objects.filter(is_active=True).order_by("code")

    workspace_locale = LocaleProfile.objects.filter(
        tenant=request.tenant
    ).select_related("language", "time_zone", "base_currency").first()

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
            "language_id": language_id,
            "time_zone_id": time_zone_id,
            "currency_id": currency_id,
            "languages": languages,
            "time_zones": time_zones,
            "currencies": currencies,
            "workspace_locale": workspace_locale,
            "stats": stats,
            "has_filters": bool(
                q or is_active or language_id or time_zone_id or currency_id
            ),
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
    workspace_locale = LocaleProfile.objects.filter(
        tenant=request.tenant
    ).select_related("language", "time_zone", "base_currency").first()
    return render(
        request,
        "projects/masterdataconfiguration/localesetting/detail.html",
        {
            "locale_setting": setting,
            "working_days_display": setting.working_days_display,
            "workspace_locale": workspace_locale,
        },
    )


@login_required
@tenant_admin_required
def pls_create(request):
    """Create a new project locale setting profile."""
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = ProjectLocaleSettingForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            setting = form.save(commit=False)
            setting.tenant = request.tenant
            setting.save()
            write_audit_log(
                user=request.user,
                obj=setting,
                action="create",
                changes={"name": setting.name, "project_id": setting.project_id},
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
@tenant_admin_required
def pls_edit(request, pk):
    """Edit an existing project locale setting profile."""
    setting = get_object_or_404(ProjectLocaleSetting, pk=pk, tenant=request.tenant)

    if request.method == "POST":
        form = ProjectLocaleSettingForm(request.POST, instance=setting, tenant=request.tenant)
        if form.is_valid():
            updated = form.save()
            write_audit_log(
                user=request.user,
                obj=updated,
                action="update",
                changes={"name": updated.name, "project_id": updated.project_id},
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
@tenant_admin_required
def pls_set_default(request, pk):
    """Promote an active workspace profile into the core locale and business calendar defaults."""
    setting = get_object_or_404(ProjectLocaleSetting, pk=pk, tenant=request.tenant)
    if setting.project_id:
        messages.error(request, "A project override cannot be promoted to the workspace default.")
        return redirect("projects:pls_detail", pk=setting.pk)
    if not setting.is_active:
        messages.error(request, "Activate the profile before promoting it to the workspace default.")
        return redirect("projects:pls_detail", pk=setting.pk)
    with transaction.atomic():
        Tenant.objects.select_for_update().get(pk=request.tenant.pk)
        locked = ProjectLocaleSetting.objects.select_for_update().get(
            pk=setting.pk,
            tenant=request.tenant,
        )
        if locked.project_id or not locked.is_active:
            messages.error(request, "The profile is no longer eligible for promotion.")
            return redirect("projects:pls_detail", pk=locked.pk)
        ProjectLocaleSetting.objects.select_for_update().filter(
            tenant=request.tenant,
            project__isnull=True,
        ).exclude(pk=locked.pk).update(is_default=False)
        LocaleProfile.objects.update_or_create(
            tenant=request.tenant,
            defaults={
                "language": locked.language,
                "base_currency": locked.currency,
                "time_zone": locked.time_zone,
                "date_format": locked.date_format,
                "time_format": locked.time_format,
                "first_day_of_week": locked.first_day_of_week,
                "number_format": locked.number_format,
            },
        )
        BusinessCalendar.objects.update_or_create(
            tenant=request.tenant,
            defaults={
                "working_days": locked.working_days_pattern,
                "timezone_name": locked.time_zone.name if locked.time_zone_id else "",
            },
        )
        locked.is_default = True
        locked.save(update_fields=["is_default"])
        write_audit_log(
            user=request.user,
            obj=locked,
            action="set_default",
            changes={"promoted_to_core_locale": True},
            tenant=request.tenant,
        )
    messages.success(request, f"Locale profile '{locked.name}' now supplies the core workspace defaults.")
    return redirect("projects:pls_detail", pk=locked.pk)
