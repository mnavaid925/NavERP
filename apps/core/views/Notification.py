"""core — 0.12 views (notification & communication).

Config surfaces are admin-gated. `my_preferences` is deliberately NOT: bullet 3 names "user
preferences", and a preference a member cannot set for themselves is an admin setting wearing a
different name.
"""
from django.contrib import messages
from django.shortcuts import redirect
from django.utils import timezone

from apps.core.views._common import *  # noqa: F401,F403
from apps.core.utils import write_audit_log
from apps.core.notify import (
    DELIVERY_SOURCES,
    NON_DELIVERY_SOURCES,
    delivery_stats,
    render_template,
    resolve_channels,
)
from apps.core.models import (
    NotificationChannel,
    NotificationPreference,
    NotificationRule,
    NotificationTemplate,
    ProviderConfig,
)
from apps.core.forms import (
    NotificationChannelForm,
    NotificationPreferenceForm,
    NotificationRuleForm,
    NotificationTemplateForm,
    ProviderConfigForm,
)


# =============================================================== bullet 1: channels
@tenant_admin_required
def channel_list(request):
    return crud_list(
        request, NotificationChannel.objects.filter(tenant=request.tenant),
        "core/notifchannel/list.html",
        search_fields=["label", "notes"],
        filters=[("kind", "kind", False), ("enabled", "is_enabled", False)],
        extra_context={"kind_choices": NotificationChannel.KIND_CHOICES,
                       "enabled_choices": [("True", "Enabled"), ("False", "Disabled")]},
    )


@tenant_admin_required
def channel_create(request):
    return crud_create(request, form_class=NotificationChannelForm,
                       template="core/notifchannel/form.html",
                       success_url="core:channel_list")


@tenant_admin_required
def channel_edit(request, pk):
    return crud_edit(request, model=NotificationChannel, pk=pk,
                     form_class=NotificationChannelForm,
                     template="core/notifchannel/form.html", success_url="core:channel_list")


@require_POST
@tenant_admin_required
def channel_delete(request, pk):
    return crud_delete(request, model=NotificationChannel, pk=pk,
                       success_url="core:channel_list")


# =============================================================== bullet 2: templates
@tenant_admin_required
def template_list(request):
    return crud_list(
        request, NotificationTemplate.objects.filter(tenant=request.tenant),
        "core/notiftemplate/list.html",
        search_fields=["code", "name", "subject", "module_slug"],
        filters=[("channel", "channel_kind", False), ("locale", "locale", False),
                 ("active", "is_active", False)],
        extra_context={"kind_choices": NotificationChannel.KIND_CHOICES,
                       "active_choices": [("True", "Active"), ("False", "Inactive")],
                       "locales": NotificationTemplate.objects.filter(tenant=request.tenant)
                       .exclude(locale="").values_list("locale", flat=True).distinct()},
    )


@tenant_admin_required
def template_detail(request, pk):
    obj = get_object_or_404(NotificationTemplate, pk=pk, tenant=request.tenant)
    return render(request, "core/notiftemplate/detail.html", {"obj": obj})


@tenant_admin_required
def template_create(request):
    return crud_create(request, form_class=NotificationTemplateForm,
                       template="core/notiftemplate/form.html",
                       success_url="core:template_list")


@tenant_admin_required
def template_edit(request, pk):
    return crud_edit(request, model=NotificationTemplate, pk=pk,
                     form_class=NotificationTemplateForm,
                     template="core/notiftemplate/form.html", success_url="core:template_list")


@require_POST
@tenant_admin_required
def template_delete(request, pk):
    return crud_delete(request, model=NotificationTemplate, pk=pk,
                       success_url="core:template_list")


@tenant_admin_required
def template_preview(request, pk):
    """Render a template against a sample context.

    The rendering is REAL, so an operator can see the output before a message goes anywhere. The
    sample context is fixed primitives on purpose: a preview that accepted arbitrary JSON would be a
    way to render a stored template against an attacker-chosen context, and the engine's autoescaping
    is the only thing standing between that and markup injection.
    """
    obj = get_object_or_404(NotificationTemplate, pk=pk, tenant=request.tenant)
    sample = {
        "recipient_name": "Ada Lovelace",
        "tenant_name": request.tenant.name if request.tenant else "",
        "amount": "1,250.00",
        "reference": "PO-00042",
        "url": "/core/workflows/",
        "today": timezone.localdate().isoformat(),
    }
    subject, subject_error = render_template(obj.subject, sample)
    body, body_error = render_template(obj.body, sample)
    return render(request, "core/notiftemplate/preview.html", {
        "obj": obj, "sample": sample, "subject": subject, "body": body,
        "error": subject_error or body_error,
    })


# =============================================================== bullet 3: rules
@tenant_admin_required
def rule_list(request):
    return crud_list(
        request,
        NotificationRule.objects.filter(tenant=request.tenant)
        .select_related("channel", "template", "audience_role", "audience_user"),
        "core/notifrule/list.html",
        search_fields=["name", "event", "module_slug", "notes"],
        filters=[("event", "event", False), ("digest", "digest", False),
                 ("active", "is_active", False)],
        extra_context={"digest_choices": NotificationRule.DIGEST_CHOICES,
                       "audience_choices": NotificationRule.AUDIENCE_CHOICES,
                       "active_choices": [("True", "Active"), ("False", "Inactive")],
                       "events": NotificationRule.objects.filter(tenant=request.tenant)
                       .values_list("event", flat=True).distinct()},
    )


@tenant_admin_required
def rule_create(request):
    return crud_create(request, form_class=NotificationRuleForm,
                       template="core/notifrule/form.html", success_url="core:rule_list")


@tenant_admin_required
def rule_edit(request, pk):
    return crud_edit(request, model=NotificationRule, pk=pk, form_class=NotificationRuleForm,
                     template="core/notifrule/form.html", success_url="core:rule_list")


@require_POST
@tenant_admin_required
def rule_delete(request, pk):
    return crud_delete(request, model=NotificationRule, pk=pk, success_url="core:rule_list")


@tenant_admin_required
def rule_resolve(request, pk):
    """Show what a rule WOULD reach, and which preference decided each channel.

    This is the page that answers "why did this person not get the email?". It reports the rule's own
    routing, the channel's enabled state, and — for a chosen member — whether their preference or the
    rule's default decided.
    """
    obj = get_object_or_404(NotificationRule.objects.select_related("channel"), pk=pk,
                            tenant=request.tenant)
    user_id = request.GET.get("user", "").strip()
    subject = None
    resolved = resolve_channels(request.tenant, obj.event)
    if user_id.isdigit():
        subject = User.objects.filter(tenant=request.tenant, pk=int(user_id)).first()
        if subject is not None:
            resolved = resolve_channels(request.tenant, obj.event, subject)
    return render(request, "core/notifrule/resolve.html", {
        "obj": obj,
        "resolved": resolved,
        "subject": subject,
        "members": User.objects.filter(tenant=request.tenant).order_by("email"),
    })


# =============================================================== bullet 3: preferences (self-service)
@login_required
def my_preferences(request):
    """A member's own notification preferences.

    Not admin-gated. Bullet 3 names "user preferences", and a preference a member cannot set for
    themselves is an admin setting with a different label.
    """
    if request.tenant is None:
        messages.info(request, "Notification preferences belong to a tenant workspace.")
        return redirect("dashboard:home")
    # Only events the workspace actually routes are offered — a preference for an event nothing sends
    # would be a control that does nothing.
    events = list(NotificationRule.objects.filter(tenant=request.tenant, is_active=True)
                  .values_list("event", flat=True).distinct().order_by("event"))
    channels = list(NotificationChannel.objects.filter(tenant=request.tenant, is_enabled=True))

    if request.method == "POST":
        created = updated = 0
        for event in events:
            for channel in channels:
                field = "pref_%s_%s" % (event.replace(".", "_"), channel.kind)
                if field not in request.POST:
                    # Only reachable if the template dropped its hidden input. Kept as a guard
                    # rather than an expectation: the hidden field means every cell IS submitted.
                    continue
                # `.get()` returns the LAST value for a repeated key, and the template emits the
                # hidden "off" BEFORE the checkbox, so a ticked box wins.
                wants = request.POST.get(field) == "on"
                pref, made = NotificationPreference.objects.get_or_create(
                    tenant=request.tenant, user=request.user, event=event,
                    channel_kind=channel.kind, defaults={"is_enabled": wants},
                )
                if not made and pref.is_enabled != wants:
                    pref.is_enabled = wants
                    pref.save(update_fields=["is_enabled", "updated_at"])
                    updated += 1
                elif made:
                    created += 1
        write_audit_log(request.user, None, "update",
                        changes={"verb": "my_preferences", "created": created, "updated": updated})
        messages.success(request, "Preferences saved.")
        return redirect("core:my_preferences")

    existing = {(p.event, p.channel_kind): p
                for p in NotificationPreference.objects.filter(tenant=request.tenant,
                                                               user=request.user)}
    grid = []
    for event in events:
        cells = []
        for channel in channels:
            pref = existing.get((event, channel.kind))
            cells.append({
                "channel": channel,
                "field": "pref_%s_%s" % (event.replace(".", "_"), channel.kind),
                "checked": pref.is_enabled if pref else True,
                "explicit": pref is not None,
            })
        grid.append({"event": event, "cells": cells})
    return render(request, "core/my_preferences.html", {
        "grid": grid, "events": events, "channels": channels,
    })


@tenant_admin_required
def preference_list(request):
    return crud_list(
        request,
        NotificationPreference.objects.filter(tenant=request.tenant).select_related("user"),
        "core/notifpref/list.html",
        search_fields=["event", "user__email"],
        filters=[("channel", "channel_kind", False), ("enabled", "is_enabled", False)],
        extra_context={"kind_choices": NotificationChannel.KIND_CHOICES,
                       "enabled_choices": [("True", "Opted in"), ("False", "Opted out")]},
    )


@tenant_admin_required
def preference_create(request):
    return crud_create(request, form_class=NotificationPreferenceForm,
                       template="core/notifpref/form.html",
                       success_url="core:preference_list")


@tenant_admin_required
def preference_edit(request, pk):
    return crud_edit(request, model=NotificationPreference, pk=pk,
                     form_class=NotificationPreferenceForm,
                     template="core/notifpref/form.html", success_url="core:preference_list")


@require_POST
@tenant_admin_required
def preference_delete(request, pk):
    """Deleting a preference row means "no preference" — the rule's default applies again."""
    return crud_delete(request, model=NotificationPreference, pk=pk,
                       success_url="core:preference_list")


# =============================================================== bullet 4: providers
@tenant_admin_required
def provider_list(request):
    return crud_list(
        request,
        ProviderConfig.objects.filter(tenant=request.tenant),
        "core/provider/list.html",
        search_fields=["label", "host", "from_address", "api_endpoint", "notes"],
        filters=[("channel", "channel_kind", False), ("active", "is_active", False)],
        extra_context={"kind_choices": NotificationChannel.KIND_CHOICES,
                       "active_choices": [("True", "Active"), ("False", "Inactive")]},
    )


@tenant_admin_required
def provider_create(request):
    return crud_create(request, form_class=ProviderConfigForm,
                       template="core/provider/form.html", success_url="core:provider_list")


@tenant_admin_required
def provider_edit(request, pk):
    return crud_edit(request, model=ProviderConfig, pk=pk, form_class=ProviderConfigForm,
                     template="core/provider/form.html", success_url="core:provider_list")


@require_POST
@tenant_admin_required
def provider_delete(request, pk):
    return crud_delete(request, model=ProviderConfig, pk=pk, success_url="core:provider_list")


# =============================================================== bullet 5: delivery tracking
@tenant_admin_required
def delivery_board(request):
    """COMPUTED: read from the REAL delivery tables of other apps. Nothing is stored."""
    if request.tenant is None:
        messages.info(request, "Delivery tracking applies to a tenant workspace.")
        return redirect("dashboard:home")
    stats = delivery_stats(request.tenant)
    context = {
        "stats": stats,
        "rows": stats["rows"],
        "skipped": stats["skipped"],
        "totals": stats["totals"],
        "declared_count": len(DELIVERY_SOURCES) + len(NON_DELIVERY_SOURCES),
        "providers": ProviderConfig.objects.filter(tenant=request.tenant, is_active=True)
        .order_by("channel_kind", "priority"),
    }
    return render(request, "core/deliveryboard.html", context)


# =============================================================== hub
@tenant_admin_required
def notification_overview(request):
    """COMPUTED hub for 0.12 — no table. Reports posture and names what is NOT built."""
    tenant = request.tenant
    if tenant is None:
        messages.info(request, "Notification settings apply to a tenant workspace.")
        return redirect("dashboard:home")
    stats = delivery_stats(tenant)
    context = {
        "channel_count": NotificationChannel.objects.filter(tenant=tenant).count(),
        "channels_on": NotificationChannel.objects.filter(tenant=tenant, is_enabled=True).count(),
        "template_count": NotificationTemplate.objects.filter(tenant=tenant, is_active=True).count(),
        "locale_count": NotificationTemplate.objects.filter(tenant=tenant)
        .exclude(locale="").values_list("locale", flat=True).distinct().count(),
        "rule_count": NotificationRule.objects.filter(tenant=tenant, is_active=True).count(),
        "event_count": NotificationRule.objects.filter(tenant=tenant, is_active=True)
        .values_list("event", flat=True).distinct().count(),
        "preference_count": NotificationPreference.objects.filter(tenant=tenant).count(),
        "opted_out": NotificationPreference.objects.filter(tenant=tenant, is_enabled=False).count(),
        "provider_count": ProviderConfig.objects.filter(tenant=tenant, is_active=True).count(),
        "totals": stats["totals"],
        "success_rate": stats["real_success_rate"],
        "rows": stats["rows"],
        "recent_rules": NotificationRule.objects.filter(tenant=tenant)
        .select_related("channel").order_by("-created_at")[:5],
    }
    return render(request, "core/notificationoverview.html", context)
