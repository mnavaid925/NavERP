"""core — 0.13 views (integration & API management).

Config surfaces, admin-gated. The credential-issue view is the one that matters most: it is the ONLY
place a plaintext key is ever visible, and it shows it exactly once.
"""
from django.contrib import messages
from django.shortcuts import redirect
from django.utils import timezone

from apps.core.views._common import *  # noqa: F401,F403
from apps.core.utils import write_audit_log
from apps.core.integration import (
    CONNECTION_SOURCES,
    NON_TRACKED_SOURCES,
    TRAFFIC_SOURCES,
    integration_health,
)
from apps.core.models import (
    ApiCredential,
    ConnectorDefinition,
    MappingTemplate,
    RateLimitPolicy,
    SyncSchedule,
)
from apps.core.forms import (
    ApiCredentialForm,
    ConnectorDefinitionForm,
    MappingTemplateForm,
    RateLimitPolicyForm,
    SyncScheduleForm,
)


# =============================================================== bullet 1: credentials
@tenant_admin_required
def credential_list(request):
    return crud_list(
        request,
        ApiCredential.objects.filter(tenant=request.tenant).select_related("created_by"),
        "core/apicredential/list.html",
        search_fields=["label", "prefix", "scopes"],
        filters=[("kind", "kind", False), ("active", "is_active", False)],
        extra_context={"kind_choices": ApiCredential.KIND_CHOICES,
                       "active_choices": [("True", "Active"), ("False", "Inactive")]},
    )


@tenant_admin_required
def credential_issue(request):
    """Issue a credential and show the plaintext ONCE.

    The plaintext is never stored — only its prefix and a SHA-256 hash — so this render is the only
    opportunity to copy it. That is the same one-way pattern `tenants.EncryptionKey` established, and
    the page says so rather than leaving the operator to discover it.
    """
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace first.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = ApiCredentialForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            credential = form.save(commit=False)
            credential.tenant = request.tenant
            credential.created_by = request.user
            plaintext = ApiCredential.generate_plaintext()
            credential.set_plaintext(plaintext)
            credential.save()
            write_audit_log(request.user, credential, "create",
                            changes={"verb": "api_credential_issue"})
            return render(request, "core/apicredential/issued.html",
                          {"obj": credential, "plaintext": plaintext})
    else:
        form = ApiCredentialForm(tenant=request.tenant)
    return render(request, "core/apicredential/form.html", {"form": form, "is_issue": True})


@tenant_admin_required
def credential_edit(request, pk):
    return crud_edit(request, model=ApiCredential, pk=pk, form_class=ApiCredentialForm,
                     template="core/apicredential/form.html", success_url="core:credential_list")


@require_POST
@tenant_admin_required
def credential_revoke(request, pk):
    """Revoke a credential. The row is KEPT and deactivated, not deleted.

    A deleted credential leaves no trace of the key that was in circulation; a deactivated one keeps
    the prefix, the scopes and the last-used stamp, which is what an investigator needs.
    """
    obj = get_object_or_404(ApiCredential, pk=pk, tenant=request.tenant)
    if not obj.is_active:
        messages.info(request, "That credential is already revoked.")
    else:
        obj.is_active = False
        obj.save(update_fields=["is_active"])
        write_audit_log(request.user, obj, "update", changes={"verb": "api_credential_revoke"})
        messages.success(request, "Credential revoked. The record is kept for the audit trail.")
    return redirect("core:credential_list")


@require_POST
@tenant_admin_required
def credential_delete(request, pk):
    return crud_delete(request, model=ApiCredential, pk=pk, success_url="core:credential_list")


# =============================================================== bullet 1: rate limits
@tenant_admin_required
def rate_limit_list(request):
    return crud_list(
        request,
        RateLimitPolicy.objects.filter(tenant=request.tenant).select_related("credential"),
        "core/ratelimit/list.html",
        search_fields=["name", "notes"],
        filters=[("window", "window", False), ("active", "is_active", False)],
        extra_context={"window_choices": RateLimitPolicy.WINDOW_CHOICES,
                       "active_choices": [("True", "Active"), ("False", "Inactive")]},
    )


@tenant_admin_required
def rate_limit_create(request):
    return crud_create(request, form_class=RateLimitPolicyForm,
                       template="core/ratelimit/form.html", success_url="core:rate_limit_list")


@tenant_admin_required
def rate_limit_edit(request, pk):
    return crud_edit(request, model=RateLimitPolicy, pk=pk, form_class=RateLimitPolicyForm,
                     template="core/ratelimit/form.html", success_url="core:rate_limit_list")


@require_POST
@tenant_admin_required
def rate_limit_delete(request, pk):
    return crud_delete(request, model=RateLimitPolicy, pk=pk, success_url="core:rate_limit_list")


# =============================================================== bullet 3: connectors
@tenant_admin_required
def connector_list(request):
    return crud_list(
        request,
        ConnectorDefinition.objects.filter(tenant=request.tenant),
        "core/connector/list.html",
        search_fields=["name", "vendor", "description", "engine_label"],
        filters=[("category", "category", False), ("installed", "is_installed", False)],
        extra_context={"category_choices": ConnectorDefinition.CATEGORY_CHOICES,
                       "installed_choices": [("True", "Installed"), ("False", "Not installed")]},
    )


@tenant_admin_required
def connector_create(request):
    return crud_create(request, form_class=ConnectorDefinitionForm,
                       template="core/connector/form.html", success_url="core:connector_list")


@tenant_admin_required
def connector_edit(request, pk):
    return crud_edit(request, model=ConnectorDefinition, pk=pk, form_class=ConnectorDefinitionForm,
                     template="core/connector/form.html", success_url="core:connector_list")


@require_POST
@tenant_admin_required
def connector_delete(request, pk):
    return crud_delete(request, model=ConnectorDefinition, pk=pk,
                       success_url="core:connector_list")


# =============================================================== bullet 4: mapping + sync
@tenant_admin_required
def mapping_list(request):
    return crud_list(
        request,
        MappingTemplate.objects.filter(tenant=request.tenant),
        "core/mapping/list.html",
        search_fields=["name", "source_format", "target_label", "notes"],
        filters=[("direction", "direction", False), ("active", "is_active", False)],
        extra_context={"direction_choices": MappingTemplate.DIRECTION_CHOICES,
                       "active_choices": [("True", "Active"), ("False", "Inactive")]},
    )


@tenant_admin_required
def mapping_detail(request, pk):
    obj = get_object_or_404(MappingTemplate, pk=pk, tenant=request.tenant)
    return render(request, "core/mapping/detail.html", {"obj": obj, "rows": obj.mappings or []})


@tenant_admin_required
def mapping_create(request):
    return crud_create(request, form_class=MappingTemplateForm,
                       template="core/mapping/form.html", success_url="core:mapping_list")


@tenant_admin_required
def mapping_edit(request, pk):
    return crud_edit(request, model=MappingTemplate, pk=pk, form_class=MappingTemplateForm,
                     template="core/mapping/form.html", success_url="core:mapping_list")


@require_POST
@tenant_admin_required
def mapping_delete(request, pk):
    return crud_delete(request, model=MappingTemplate, pk=pk, success_url="core:mapping_list")


@tenant_admin_required
def sync_list(request):
    return crud_list(
        request,
        SyncSchedule.objects.filter(tenant=request.tenant)
        .select_related("mapping_template", "connector"),
        "core/syncschedule/list.html",
        search_fields=["name", "entity_label", "notes"],
        filters=[("direction", "direction", False), ("transport", "transport", False),
                 ("frequency", "frequency", False)],
        extra_context={"direction_choices": SyncSchedule.DIRECTION_CHOICES,
                       "transport_choices": SyncSchedule.TRANSPORT_CHOICES,
                       "frequency_choices": SyncSchedule.FREQUENCY_CHOICES},
    )


@tenant_admin_required
def sync_create(request):
    return crud_create(request, form_class=SyncScheduleForm,
                       template="core/syncschedule/form.html", success_url="core:sync_list")


@tenant_admin_required
def sync_edit(request, pk):
    return crud_edit(request, model=SyncSchedule, pk=pk, form_class=SyncScheduleForm,
                     template="core/syncschedule/form.html", success_url="core:sync_list")


@require_POST
@tenant_admin_required
def sync_delete(request, pk):
    return crud_delete(request, model=SyncSchedule, pk=pk, success_url="core:sync_list")


# =============================================================== bullet 5: monitoring
@tenant_admin_required
def integration_board(request):
    """COMPUTED: read from the REAL integration tables of five apps. Nothing is stored."""
    if request.tenant is None:
        messages.info(request, "Integration monitoring applies to a tenant workspace.")
        return redirect("dashboard:home")
    health = integration_health(request.tenant)
    context = {
        "health": health,
        "connections": health["connections"],
        "traffic": health["traffic"],
        "skipped": health["skipped"],
        "totals": health["totals"],
        "declared_count": len(CONNECTION_SOURCES) + len(TRAFFIC_SOURCES) + len(NON_TRACKED_SOURCES),
        "connectors": ConnectorDefinition.objects.filter(tenant=request.tenant,
                                                         is_installed=True),
        "schedules": SyncSchedule.objects.filter(tenant=request.tenant, is_active=True),
    }
    return render(request, "core/integrationboard.html", context)


# =============================================================== hub
@tenant_admin_required
def integration_overview(request):
    """COMPUTED hub for 0.13 — no table. Reports posture and names what is NOT built."""
    tenant = request.tenant
    if tenant is None:
        messages.info(request, "Integration settings apply to a tenant workspace.")
        return redirect("dashboard:home")
    health = integration_health(tenant)
    credentials = ApiCredential.objects.filter(tenant=tenant)
    context = {
        "credential_count": credentials.count(),
        "credentials_active": credentials.filter(is_active=True).count(),
        # Filtered in the DB rather than by calling the `is_expired` property per row: a property
        # cannot be a queryset filter, and counting in Python would fetch every credential.
        "credentials_expired": credentials.filter(expires_at__lte=timezone.now()).count(),
        "credentials_used": credentials.exclude(last_used_at__isnull=True).count(),
        "limit_count": RateLimitPolicy.objects.filter(tenant=tenant, is_active=True).count(),
        "connector_count": ConnectorDefinition.objects.filter(tenant=tenant, is_active=True).count(),
        "connectors_installed": ConnectorDefinition.objects.filter(tenant=tenant,
                                                                   is_installed=True).count(),
        "mapping_count": MappingTemplate.objects.filter(tenant=tenant, is_active=True).count(),
        "schedule_count": SyncSchedule.objects.filter(tenant=tenant, is_active=True).count(),
        "totals": health["totals"],
        "success_rate": health["traffic_success_rate"],
        "connections": health["connections"],
        "recent_credentials": credentials.order_by("-created_at")[:5],
    }
    return render(request, "core/integrationoverview.html", context)
