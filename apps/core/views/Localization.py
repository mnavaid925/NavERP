"""core — 0.15 views (localization & regional settings).

**The one rule that makes this file different from every other sub-module's:** `Language` and
`TimeZone` are GLOBAL registries with no `tenant` FK, so they are the only two views here that are
**not** tenant-scoped. They are `@login_required` (not `@tenant_admin_required`, which reads
`request.tenant`), they filter nothing, and they have **no create/edit/delete routes at all** — a write
would need a platform-admin gate this repo does not have, so the registry is seeder-populated and the
page says so. They must also work for the tenant-less superuser, which is why they take no tenant branch.

`LocaleProfile` and `UserLocalePreference` are **singletons**, so the house list/detail/create/edit/delete
shape does not apply: each gets one edit page. Both write their `tenant` (and the user row its `user`)
explicitly from `commit=False`, because neither key is a form field — a plain `form.save()` would try to
insert a NULL tenant and fail.

The two computed pages read the REAL `accounting.ExchangeRate` rows. They reach accounting through
`django_apps.get_model`, the pattern 0.13 established, so this module never imports a peer app's models
at import time.
"""
from django.apps import apps as django_apps
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

from apps.core.views._common import *  # noqa: F401,F403
from apps.core.utils import write_audit_log
from apps.core.models import (
    Language,
    LocaleProfile,
    StatutoryRule,
    TimeZone,
    UserLocalePreference,
)
from apps.core.forms import (
    LocaleProfileForm,
    StatutoryRuleForm,
    UserLocalePreferenceForm,
)


#: A rate older than this many days is reported as stale. A named constant rather than a literal so the
#: page, the context and any future caller cannot disagree about what "stale" means.
STALE_RATE_DAYS = 7


def _fx_rows(tenant):
    """The newest rate per currency for `tenant`, in ONE query.

    Ordered `(currency__code, -rate_date)` and de-duplicated in Python, so the first row seen for a
    currency IS its newest. The alternative — a `Max("rate_date")` subquery joined back — is the shape
    that silently returns the wrong row when two rates share a date, and it costs a second query.
    """
    ExchangeRate = django_apps.get_model("accounting", "ExchangeRate")
    today = timezone.localdate()
    rows, seen = [], set()
    qs = (ExchangeRate.objects.filter(tenant=tenant)
          .select_related("currency").order_by("currency__code", "-rate_date"))
    for rate in qs:
        if rate.currency_id in seen:
            continue
        seen.add(rate.currency_id)
        rows.append({
            "currency": rate.currency,
            "rate": rate.rate,
            "rate_date": rate.rate_date,
            "source": rate.get_source_display(),
            "age_days": (today - rate.rate_date).days,
        })
    return rows


# ============================================================ bullet 1: the language registry
@login_required
def language_list(request):
    """GLOBAL reference list — no tenant filter, and read-only by design."""
    return crud_list(
        request,
        Language.objects.all(),
        "core/language/list.html",
        search_fields=["code", "name", "native_name"],
        filters=[("rtl", "is_rtl", False), ("active", "is_active", False)],
        extra_context={"rtl_choices": [("True", "Right-to-left"), ("False", "Left-to-right")],
                       "active_choices": [("True", "Active"), ("False", "Inactive")]},
    )


# ============================================================ bullet 5: the time zone registry
@login_required
def timezone_list(request):
    """GLOBAL reference list — no tenant filter, and read-only by design."""
    return crud_list(
        request,
        TimeZone.objects.all(),
        "core/timezone/list.html",
        search_fields=["name", "label"],
        filters=[("dst", "observes_dst", False), ("active", "is_active", False)],
        extra_context={"dst_choices": [("True", "Observes DST"), ("False", "No DST")],
                       "active_choices": [("True", "Active"), ("False", "Inactive")]},
    )


# ============================================================ bullets 2/3/5: the tenant profile
@tenant_admin_required
def locale_profile_edit(request):
    """The workspace's localization profile — a singleton, so one edit page and no delete."""
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace first.")
        return redirect("dashboard:home")

    obj = LocaleProfile.objects.filter(tenant=request.tenant).first()
    if request.method == "POST":
        form = LocaleProfileForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            # `tenant` is not a form field, so it must be set here — `form.save()` alone would try to
            # insert a NULL tenant on the create path and raise IntegrityError.
            obj.tenant = request.tenant
            obj.save()
            write_audit_log(request.user, obj, "update", changes={"verb": "locale_profile_save"})
            messages.success(request, "Regional settings saved.")
            return redirect("core:localization_overview")
    else:
        form = LocaleProfileForm(instance=obj, tenant=request.tenant)
    return render(request, "core/localeprofile/form.html",
                  {"form": form, "obj": obj, "is_edit": True})


# ============================================================ bullet 5: the per-user override
@login_required
def user_locale_edit(request):
    """One person's regional overrides. Blank fields inherit the workspace profile."""
    if request.tenant is None:
        # `UserLocalePreference.tenant` is NOT NULL (every model carries a tenant), so a tenant-less
        # superuser cannot own one. Said plainly rather than 500ing on the insert.
        messages.info(request, "Regional preferences apply to a tenant workspace.")
        return redirect("dashboard:home")

    obj = UserLocalePreference.objects.filter(tenant=request.tenant, user=request.user).first()
    if request.method == "POST":
        form = UserLocalePreferenceForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.user = request.user
            obj.save()
            write_audit_log(request.user, obj, "update", changes={"verb": "user_locale_save"})
            messages.success(request, "Your regional preferences were saved.")
            return redirect("core:localization_overview")
    else:
        form = UserLocalePreferenceForm(instance=obj, tenant=request.tenant)
    return render(request, "core/userlocale/form.html", {"form": form, "obj": obj})


# ============================================================ bullet 4: statutory rules
@tenant_admin_required
def statutory_rule_list(request):
    return crud_list(
        request,
        StatutoryRule.objects.filter(tenant=request.tenant).select_related("tax_code"),
        "core/statutoryrule/list.html",
        search_fields=["name", "jurisdiction", "statutory_report", "notes"],
        filters=[("scheme", "e_invoicing_scheme", False), ("active", "is_active", False)],
        extra_context={"scheme_choices": StatutoryRule.E_INVOICING_CHOICES,
                       "active_choices": [("True", "Active"), ("False", "Inactive")]},
    )


@tenant_admin_required
def statutory_rule_create(request):
    return crud_create(request, form_class=StatutoryRuleForm,
                       template="core/statutoryrule/form.html",
                       success_url="core:statutory_rule_list")


@tenant_admin_required
def statutory_rule_detail(request, pk):
    return crud_detail(request, model=StatutoryRule, pk=pk,
                       template="core/statutoryrule/detail.html", select_related=("tax_code",))


@tenant_admin_required
def statutory_rule_edit(request, pk):
    return crud_edit(request, model=StatutoryRule, pk=pk, form_class=StatutoryRuleForm,
                     template="core/statutoryrule/form.html",
                     success_url="core:statutory_rule_list")


# `@require_POST` sits ABOVE the role gate on purpose: decorators apply bottom-up, so the outermost
# runs first. With the role gate outermost a member's GET would be answered 403 before the method
# check ever ran, and the house standard is 405 for a wrong method regardless of role (7.7's ruling).
@require_POST
@tenant_admin_required
def statutory_rule_delete(request, pk):
    return crud_delete(request, model=StatutoryRule, pk=pk,
                       success_url="core:statutory_rule_list")


# ============================================================ bullet 2/4: the computed board
@tenant_admin_required
def localization_board(request):
    """COMPUTED — reads the REAL `accounting.ExchangeRate` rows. Nothing is stored here."""
    if request.tenant is None:
        messages.info(request, "Localization monitoring applies to a tenant workspace.")
        return redirect("dashboard:home")

    tenant = request.tenant
    Currency = django_apps.get_model("accounting", "Currency")

    rate_rows = _fx_rows(tenant)
    active_currencies = Currency.objects.filter(is_active=True).count()
    zones = TimeZone.objects.filter(is_active=True)
    languages = Language.objects.filter(is_active=True)

    context = {
        "profile": LocaleProfile.objects.filter(tenant=tenant).first(),
        "rate_rows": rate_rows,
        "rate_count": len(rate_rows),
        "stale_rate_count": sum(1 for row in rate_rows if row["age_days"] > STALE_RATE_DAYS),
        "currencies_without_rates": max(active_currencies - len(rate_rows), 0),
        "stale_after_days": STALE_RATE_DAYS,
        "timezone_count": zones.count(),
        "dst_zone_count": zones.filter(observes_dst=True).count(),
        "language_count": languages.count(),
        "rtl_count": languages.filter(is_rtl=True).count(),
        "statutory_count": StatutoryRule.objects.filter(tenant=tenant, is_active=True).count(),
        "e_invoicing_count": StatutoryRule.objects.filter(
            tenant=tenant, is_active=True, e_invoicing_required=True).count(),
        # The board points at accounting rather than duplicating its registers.
        "exchange_rate_url": reverse("accounting:exchange_rate_list"),
        "tax_code_url": reverse("accounting:tax_code_list"),
    }
    return render(request, "core/localizationboard.html", context)


# ============================================================ hub
@tenant_admin_required
def localization_overview(request):
    """COMPUTED hub for 0.15 — no table. Reports posture and names what is NOT built."""
    if request.tenant is None:
        messages.info(request, "Localization settings apply to a tenant workspace.")
        return redirect("dashboard:home")

    tenant = request.tenant
    zones = TimeZone.objects.filter(is_active=True)
    languages = Language.objects.filter(is_active=True)
    rules = StatutoryRule.objects.filter(tenant=tenant)

    context = {
        "profile": LocaleProfile.objects.filter(tenant=tenant).first(),
        "has_profile": LocaleProfile.objects.filter(tenant=tenant).exists(),
        "my_pref": UserLocalePreference.objects.filter(tenant=tenant, user=request.user).first(),
        "language_count": languages.count(),
        "rtl_count": languages.filter(is_rtl=True).count(),
        "timezone_count": zones.count(),
        "dst_zone_count": zones.filter(observes_dst=True).count(),
        "statutory_count": rules.filter(is_active=True).count(),
        "e_invoicing_count": rules.filter(is_active=True, e_invoicing_required=True).count(),
        "user_pref_count": UserLocalePreference.objects.filter(tenant=tenant).count(),
        "recent_rules": rules.order_by("-created_at")[:5],
    }
    return render(request, "core/localizationoverview.html", context)
