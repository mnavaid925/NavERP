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
from django.db.models import Count, Max, Q
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


def _audit_changes(form):
    """The `{field: new_value}` diff for a hand-rolled singleton save's audit row.

    A two-line local twin of `crud._changed`, which stays private: it is named explicitly by ~15 call
    sites across scm/hrm/procurement/projects, so promoting it would mean a cross-app rename for no
    behavioural gain. Neither `LocaleProfile` nor `UserLocalePreference` carries a field on
    `_SENSITIVE_AUDIT_FIELDS`, so the redaction branch is not reproduced here.
    """
    return {name: str(form.cleaned_data.get(name))[:200] for name in form.changed_data}


def _fx_rows(tenant):
    """The newest rate per currency for `tenant` — two queries, O(currencies) rows out.

    One grouped `Max("rate_date")` per currency, then the matching rows fetched back and ordered by
    currency code. The previous implementation fetched the tenant's ENTIRE rate history, joined and
    sorted it, then discarded all but the newest row per currency in Python — O(currencies × days)
    rows transferred for O(currencies) rows of output (measured: 2,193 rows → 207 ms, ≈1.7 s at
    10 currencies × 5 years).

    Its docstring justified that shape by claiming a `Max("rate_date")` subquery "returns the wrong
    row when two rates share a date". **That is false for this model:**
    `ExchangeRate.Meta.unique_together = ("tenant", "currency", "rate_date")` makes two rows for the
    same tenant + currency + date impossible, so the newest date is unique per currency and the
    aggregate cannot be ambiguous. The same unique index backs the grouped subquery below.
    """
    ExchangeRate = django_apps.get_model("accounting", "ExchangeRate")
    today = timezone.localdate()

    newest = list(ExchangeRate.objects.filter(tenant=tenant)
                  .values("currency_id").annotate(newest_date=Max("rate_date")))
    if not newest:
        return []
    # `filter(Q())` with an empty Q matches EVERY row, so the empty case is handled above.
    match = Q()
    for row in newest:
        match |= Q(currency_id=row["currency_id"], rate_date=row["newest_date"])
    qs = (ExchangeRate.objects.filter(tenant=tenant).filter(match)
          .select_related("currency").order_by("currency__code"))
    return [{
        "currency": rate.currency,
        "rate": rate.rate,
        "rate_date": rate.rate_date,
        "source": rate.get_source_display(),
        "age_days": (today - rate.rate_date).days,
    } for rate in qs]


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
            write_audit_log(request.user, obj, "update",
                            changes={"verb": "locale_profile_save", **_audit_changes(form)})
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
            write_audit_log(request.user, obj, "update",
                            changes={"verb": "user_locale_save", **_audit_changes(form)})
            messages.success(request, "Your regional preferences were saved.")
            # Redirect to THIS page, not to the admin-gated overview: a plain member is a supported
            # actor here (@login_required), and `localization_overview` would answer 403 — exactly the
            # dead end 0.12's `my_preferences` avoids by redirecting to itself.
            return redirect("core:user_locale_edit")
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
    # One conditional aggregate per table instead of a COUNT per stat card.
    zone_stats = TimeZone.objects.aggregate(
        total=Count("id", filter=Q(is_active=True)),
        dst=Count("id", filter=Q(is_active=True, observes_dst=True)))
    language_stats = Language.objects.aggregate(
        total=Count("id", filter=Q(is_active=True)),
        rtl=Count("id", filter=Q(is_active=True, is_rtl=True)))
    rule_stats = StatutoryRule.objects.filter(tenant=tenant).aggregate(
        total=Count("id", filter=Q(is_active=True)),
        e_invoicing=Count("id", filter=Q(is_active=True, e_invoicing_required=True)))
    # `base_currency` is rendered, so load that FK with the row rather than lazily.
    profile = (LocaleProfile.objects.filter(tenant=tenant)
               .select_related("base_currency").first())

    context = {
        "profile": profile,
        "base_currency": profile.base_currency if profile else None,
        "rate_rows": rate_rows,
        "rate_count": len(rate_rows),
        "stale_rate_count": sum(1 for row in rate_rows if row["age_days"] > STALE_RATE_DAYS),
        "currencies_without_rates": max(active_currencies - len(rate_rows), 0),
        "stale_after_days": STALE_RATE_DAYS,
        "timezone_count": zone_stats["total"],
        "dst_zone_count": zone_stats["dst"],
        "language_count": language_stats["total"],
        "rtl_count": language_stats["rtl"],
        "statutory_count": rule_stats["total"],
        "e_invoicing_count": rule_stats["e_invoicing"],
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
    zone_stats = TimeZone.objects.aggregate(
        total=Count("id", filter=Q(is_active=True)),
        dst=Count("id", filter=Q(is_active=True, observes_dst=True)))
    language_stats = Language.objects.aggregate(
        total=Count("id", filter=Q(is_active=True)),
        rtl=Count("id", filter=Q(is_active=True, is_rtl=True)))
    rules = StatutoryRule.objects.filter(tenant=tenant)
    rule_stats = rules.aggregate(
        total=Count("id", filter=Q(is_active=True)),
        e_invoicing=Count("id", filter=Q(is_active=True, e_invoicing_required=True)))
    # Fetched ONCE — the "configured" flag is derived from it, not a second query for the same
    # singleton row; the FK targets are rendered, so they ride along.
    profile = (LocaleProfile.objects.filter(tenant=tenant)
               .select_related("language", "base_currency", "time_zone").first())

    context = {
        "profile": profile,
        "has_profile": profile is not None,
        "my_pref": UserLocalePreference.objects.filter(tenant=tenant, user=request.user).first(),
        "language_count": language_stats["total"],
        "rtl_count": language_stats["rtl"],
        "timezone_count": zone_stats["total"],
        "dst_zone_count": zone_stats["dst"],
        "statutory_count": rule_stats["total"],
        "e_invoicing_count": rule_stats["e_invoicing"],
        "user_pref_count": UserLocalePreference.objects.filter(tenant=tenant).count(),
        "recent_rules": rules.order_by("-created_at")[:5],
    }
    return render(request, "core/localizationoverview.html", context)
