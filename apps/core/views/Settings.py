"""core — 0.10 views (system configuration).

Config surfaces, admin-gated. Two computed boards (settings overview, numbering reconciliation) are
the parts that are useful to a member too, but they are admin-gated here because they expose the
workspace's configuration.
"""
import datetime

from django.contrib import messages
from django.db.models import Count
from django.shortcuts import redirect
from django.utils import timezone

from apps.core.views._common import *  # noqa: F401,F403
from apps.core.utils import write_audit_log
from apps.core.settings_engine import (
    get_setting,
    is_feature_enabled,
    prefix_usage,
    validate_custom_value,
)
from apps.core.models import (
    BusinessCalendar,
    CustomFieldDefinition,
    CustomFieldValue,
    FeatureFlag,
    Holiday,
    NumberingScheme,
    SettingDefinition,
    SettingValue,
)
from apps.core.forms import (
    BusinessCalendarForm,
    CustomFieldDefinitionForm,
    CustomFieldValueForm,
    FeatureFlagForm,
    HolidayForm,
    NumberingSchemeForm,
    SettingDefinitionForm,
    SettingValueForm,
)


# =============================================================== bullet 1: settings
@tenant_admin_required
def setting_definition_list(request):
    return crud_list(
        request, SettingDefinition.objects.all(),
        "core/settingdefinition/list.html",
        search_fields=["key", "label", "module_slug", "help_text"],
        filters=[("value_type", "value_type", False), ("module", "module_slug", False)],
        extra_context={"value_type_choices": SettingDefinition.VALUE_TYPE_CHOICES,
                       "modules": SettingDefinition.objects.exclude(module_slug="")
                       .values_list("module_slug", flat=True).distinct()},
    )


@tenant_admin_required
def setting_definition_create(request):
    return crud_create(request, form_class=SettingDefinitionForm,
                       template="core/settingdefinition/form.html",
                       success_url="core:setting_definition_list")


@tenant_admin_required
def setting_definition_edit(request, pk):
    return crud_edit(request, model=SettingDefinition, pk=pk, form_class=SettingDefinitionForm,
                     template="core/settingdefinition/form.html",
                     success_url="core:setting_definition_list")


@require_POST
@tenant_admin_required
def setting_definition_delete(request, pk):
    return crud_delete(request, model=SettingDefinition, pk=pk,
                       success_url="core:setting_definition_list")


@tenant_admin_required
def settings_overview(request):
    """COMPUTED: every definition with THIS tenant's resolved value and where it came from.

    The `is_default` column is the point. A settings page that shows a value without saying whether it
    was set or inherited cannot answer "did someone change this?", which is the only question an
    operator actually has.
    """
    if request.tenant is None:
        messages.info(request, "Settings apply to a tenant workspace.")
        return redirect("dashboard:home")
    overrides = {v.definition_id: v for v in SettingValue.objects.filter(tenant=request.tenant)}
    rows = []
    for definition in SettingDefinition.objects.all():
        result = get_setting(request.tenant, definition.key)
        rows.append({
            "definition": definition,
            "result": result,
            "override": overrides.get(definition.pk),
        })
    context = {
        "rows": rows,
        "definition_count": len(rows),
        "overridden_count": len(overrides),
        "locked_count": sum(1 for r in rows if r["definition"].is_locked),
    }
    return render(request, "core/settingsoverview.html", context)


@tenant_admin_required
def setting_value_edit(request, pk):
    """Set or clear this tenant's override for one definition."""
    definition = get_object_or_404(SettingDefinition, pk=pk)
    if definition.is_locked:
        messages.error(request, "That setting is locked and cannot be overridden.")
        return redirect("core:settings_overview")
    override = SettingValue.objects.filter(tenant=request.tenant, definition=definition).first()
    if request.method == "POST":
        if request.POST.get("_clear"):
            # Clearing DELETES the row, so the tenant goes back to inheriting the default rather
            # than storing an empty string that would read as an explicit empty value.
            if override is not None:
                write_audit_log(request.user, override, "delete")
                override.delete()
            messages.success(request, f"Override cleared — {definition.key} now takes the default.")
            return redirect("core:settings_overview")
        form = SettingValueForm(request.POST, instance=override, definition=definition,
                                tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.definition = definition
            obj.updated_by = request.user
            obj.save()
            write_audit_log(request.user, obj, "update", changes={"verb": "setting_value_edit"})
            messages.success(request, "Override saved.")
            return redirect("core:settings_overview")
    else:
        form = SettingValueForm(instance=override, definition=definition, tenant=request.tenant)
    return render(request, "core/settingvalue/form.html",
                  {"form": form, "definition": definition, "obj": override})


# =============================================================== bullet 2: feature flags
@tenant_admin_required
def feature_flag_list(request):
    return crud_list(
        request,
        FeatureFlag.objects.filter(tenant=request.tenant).prefetch_related("exempt_roles"),
        "core/featureflag/list.html",
        search_fields=["key", "label", "description"],
        filters=[("enabled", "is_enabled", False), ("plan", "applies_to_plan", False)],
        extra_context={"enabled_choices": [("True", "Enabled"), ("False", "Disabled")]},
    )


@tenant_admin_required
def feature_flag_create(request):
    return crud_create(request, form_class=FeatureFlagForm, template="core/featureflag/form.html",
                       success_url="core:feature_flag_list")


@tenant_admin_required
def feature_flag_edit(request, pk):
    return crud_edit(request, model=FeatureFlag, pk=pk, form_class=FeatureFlagForm,
                     template="core/featureflag/form.html", success_url="core:feature_flag_list")


@require_POST
@tenant_admin_required
def feature_flag_delete(request, pk):
    return crud_delete(request, model=FeatureFlag, pk=pk, success_url="core:feature_flag_list")


# =============================================================== bullet 3: numbering
@tenant_admin_required
def numbering_scheme_list(request):
    return crud_list(
        request, NumberingScheme.objects.filter(tenant=request.tenant),
        "core/numberingscheme/list.html",
        search_fields=["document_kind", "prefix", "notes"],
        filters=[("reset_rule", "reset_rule", False), ("active", "is_active", False)],
        extra_context={"reset_choices": NumberingScheme.RESET_CHOICES,
                       "active_choices": [("True", "Active"), ("False", "Inactive")]},
    )


@tenant_admin_required
def numbering_scheme_create(request):
    return crud_create(request, form_class=NumberingSchemeForm,
                       template="core/numberingscheme/form.html",
                       success_url="core:numbering_scheme_list")


@tenant_admin_required
def numbering_scheme_edit(request, pk):
    return crud_edit(request, model=NumberingScheme, pk=pk, form_class=NumberingSchemeForm,
                     template="core/numberingscheme/form.html",
                     success_url="core:numbering_scheme_list")


@require_POST
@tenant_admin_required
def numbering_scheme_delete(request, pk):
    return crud_delete(request, model=NumberingScheme, pk=pk,
                       success_url="core:numbering_scheme_list")


@tenant_admin_required
def numbering_board(request):
    """COMPUTED reconciliation between configured prefixes and the ones models actually mint.

    Two failure modes are surfaced, and both are silent in production: a scheme whose prefix no model
    mints (it does nothing), and a model minting a prefix with no scheme behind it (undocumented
    numbering). Allocation itself stays in `next_number()` — nothing here mints anything.
    """
    usage = prefix_usage()
    configured = {s.prefix: s for s in NumberingScheme.objects.filter(tenant=request.tenant)}
    rows = []
    for prefix, scheme in sorted(configured.items()):
        rows.append({"prefix": prefix, "scheme": scheme,
                     "minted_by": usage["model_prefixes"].get(prefix, [])})
    context = {
        "rows": rows,
        "configured_only": usage["configured_only"],
        "model_only": usage["model_only"],
        "model_prefix_count": len(usage["model_prefixes"]),
        "configured_count": len(configured),
        "used_count": len(usage["used"]),
        # Surfaced so the board cannot imply that a prefix reported as unused is definitely unused.
        "literal_prefixes": usage.get("literal_prefixes", []),
    }
    return render(request, "core/numberingboard.html", context)


# =============================================================== bullet 4: calendar
@tenant_admin_required
def calendar_edit(request):
    """The workspace's working week. Fiscal periods are NOT here — `accounting.FiscalPeriod` owns
    them and the page links out rather than duplicating (L36)."""
    if request.tenant is None:
        messages.info(request, "A calendar belongs to a tenant workspace.")
        return redirect("dashboard:home")
    calendar, _ = BusinessCalendar.objects.get_or_create(
        tenant=request.tenant, defaults={"working_days": [1, 2, 3, 4, 5]})
    if request.method == "POST":
        form = BusinessCalendarForm(request.POST, instance=calendar, tenant=request.tenant)
        if form.is_valid():
            form.save()
            write_audit_log(request.user, calendar, "update", changes={"verb": "calendar_edit"})
            messages.success(request, "Business calendar saved.")
            return redirect("core:calendar_board")
    else:
        form = BusinessCalendarForm(instance=calendar, tenant=request.tenant)
    return render(request, "core/calendar/form.html", {"form": form, "obj": calendar})


@tenant_admin_required
def calendar_board(request):
    """COMPUTED: the working week, upcoming holidays, and a link to the accounting periods."""
    if request.tenant is None:
        messages.info(request, "A calendar belongs to a tenant workspace.")
        return redirect("dashboard:home")
    calendar = BusinessCalendar.objects.filter(tenant=request.tenant).first()
    today = timezone.localdate()
    holidays = Holiday.objects.filter(tenant=request.tenant).order_by("date")
    upcoming = [h for h in holidays if h.date >= today][:10]
    weekday_names = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat", 7: "Sun"}
    context = {
        "calendar": calendar,
        "working_days": [weekday_names[d] for d in (calendar.working_days if calendar else [])],
        "holiday_count": holidays.count(),
        "upcoming": upcoming,
        "today": today,
        "today_is_working": calendar.is_working_day(today) if calendar else None,
        "recurring_count": holidays.filter(is_recurring=True).count(),
    }
    return render(request, "core/calendarboard.html", context)


@tenant_admin_required
def holiday_list(request):
    return crud_list(
        request, Holiday.objects.filter(tenant=request.tenant),
        "core/holiday/list.html",
        search_fields=["name", "region", "notes"],
        filters=[("region", "region", False)],
        extra_context={"regions": Holiday.objects.filter(tenant=request.tenant)
                       .exclude(region="").values_list("region", flat=True).distinct()},
    )


@tenant_admin_required
def holiday_create(request):
    return crud_create(request, form_class=HolidayForm, template="core/holiday/form.html",
                       success_url="core:holiday_list")


@tenant_admin_required
def holiday_edit(request, pk):
    return crud_edit(request, model=Holiday, pk=pk, form_class=HolidayForm,
                     template="core/holiday/form.html", success_url="core:holiday_list")


@require_POST
@tenant_admin_required
def holiday_delete(request, pk):
    return crud_delete(request, model=Holiday, pk=pk, success_url="core:holiday_list")


# =============================================================== bullet 5: custom fields
@tenant_admin_required
def custom_field_list(request):
    return crud_list(
        request,
        CustomFieldDefinition.objects.filter(tenant=request.tenant).annotate(
            value_count=Count("values")),
        "core/customfield/list.html",
        search_fields=["field_key", "label", "entity_label", "module_slug"],
        filters=[("module", "module_slug", False), ("field_type", "field_type", False),
                 ("active", "is_active", False)],
        extra_context={"field_type_choices": CustomFieldDefinition.FIELD_TYPE_CHOICES,
                       "active_choices": [("True", "Active"), ("False", "Inactive")]},
    )


@tenant_admin_required
def custom_field_create(request):
    return crud_create(request, form_class=CustomFieldDefinitionForm,
                       template="core/customfield/form.html",
                       success_url="core:custom_field_list")


@tenant_admin_required
def custom_field_edit(request, pk):
    return crud_edit(request, model=CustomFieldDefinition, pk=pk,
                     form_class=CustomFieldDefinitionForm,
                     template="core/customfield/form.html",
                     success_url="core:custom_field_list")


@require_POST
@tenant_admin_required
def custom_field_delete(request, pk):
    return crud_delete(request, model=CustomFieldDefinition, pk=pk,
                       success_url="core:custom_field_list")


@tenant_admin_required
def custom_field_detail(request, pk):
    """A definition and its stored values."""
    definition = get_object_or_404(CustomFieldDefinition, pk=pk, tenant=request.tenant)
    values = definition.values.filter(tenant=request.tenant).select_related("updated_by")
    return render(request, "core/customfield/detail.html",
                  {"obj": definition, "values": values})


@tenant_admin_required
def custom_field_value_create(request, pk):
    """Write one value. Validation is against the DEFINITION, so a bad value is refused on write
    rather than stored and mis-rendered later."""
    definition = get_object_or_404(CustomFieldDefinition, pk=pk, tenant=request.tenant)
    if request.method == "POST":
        form = CustomFieldValueForm(request.POST, definition=definition, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.definition = definition
            obj.entity_label = definition.entity_label
            obj.updated_by = request.user
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, "Value saved.")
            return redirect("core:custom_field_detail", pk=definition.pk)
    else:
        form = CustomFieldValueForm(definition=definition, tenant=request.tenant)
    return render(request, "core/customfield/value_form.html",
                  {"form": form, "definition": definition})


@require_POST
@tenant_admin_required
def custom_field_value_delete(request, pk):
    """Delete a value. Scoped to the tenant; the definition is the parent."""
    obj = get_object_or_404(CustomFieldValue, pk=pk, tenant=request.tenant)
    definition_pk = obj.definition_id
    write_audit_log(request.user, obj, "delete")
    obj.delete()
    messages.success(request, "Value deleted.")
    return redirect("core:custom_field_detail", pk=definition_pk)


# =============================================================== hub
@tenant_admin_required
def config_overview(request):
    """COMPUTED hub for 0.10 — no table. Reports posture and names what is NOT built."""
    tenant = request.tenant
    if tenant is None:
        messages.info(request, "Configuration applies to a tenant workspace.")
        return redirect("dashboard:home")
    usage = prefix_usage()
    calendar = BusinessCalendar.objects.filter(tenant=tenant).first()
    context = {
        "definition_count": SettingDefinition.objects.count(),
        "override_count": SettingValue.objects.filter(tenant=tenant).count(),
        "flag_count": FeatureFlag.objects.filter(tenant=tenant).count(),
        "flags_on": FeatureFlag.objects.filter(tenant=tenant, is_enabled=True).count(),
        "scheme_count": NumberingScheme.objects.filter(tenant=tenant).count(),
        "configured_only": usage["configured_only"],
        "model_prefix_count": len(usage["model_prefixes"]),
        "calendar": calendar,
        "holiday_count": Holiday.objects.filter(tenant=tenant).count(),
        "custom_field_count": CustomFieldDefinition.objects.filter(tenant=tenant).count(),
        "custom_value_count": CustomFieldValue.objects.filter(tenant=tenant).count(),
        "recent_flags": FeatureFlag.objects.filter(tenant=tenant).order_by("-updated_at")[:5],
    }
    return render(request, "core/configoverview.html", context)
