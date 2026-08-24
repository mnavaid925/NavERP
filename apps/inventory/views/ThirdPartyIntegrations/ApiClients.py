"""Inventory 5.19 Third-Party Integrations & API — ApiClient CRUD + token/revoke verb views."""
from django.db.models import Count

from apps.core.decorators import tenant_admin_required
from apps.inventory.forms.ThirdPartyIntegrations.ApiClients import ApiClientForm
from apps.inventory.models.ThirdPartyIntegrations._choices import (
    API_PROTOCOL_CHOICES,
    API_STATUS_CHOICES,
)
from apps.inventory.models.ThirdPartyIntegrations.ApiClients import ApiClient
from apps.inventory.views._common import *  # noqa: F401,F403


@login_required
def apiclient_list(request):
    """List API clients with search, status/protocol filtering and a KPI strip."""
    qs = ApiClient.objects.filter(tenant=request.tenant)

    # Search & filters — junk GET values (status=zzz) fall back to "" instead of echoing back
    # into context and rendering a silently empty register. Applied pre-pagination.
    valid_statuses = dict(API_STATUS_CHOICES)
    valid_protocols = dict(API_PROTOCOL_CHOICES)

    status = request.GET.get("status", "").strip()
    if status and status not in valid_statuses:
        status = ""
    if status:
        qs = qs.filter(status=status)

    protocol = request.GET.get("protocol", "").strip()
    if protocol and protocol not in valid_protocols:
        protocol = ""
    if protocol:
        qs = qs.filter(protocol=protocol)

    # KPIs across the tenant's full client register — one grouped query, not three COUNTs.
    status_counts = {
        row["status"]: row["n"]
        for row in ApiClient.objects.filter(tenant=request.tenant)
        .values("status")
        .annotate(n=Count("id"))
    }
    stats = {
        "total": sum(status_counts.values()),
        "active": status_counts.get("active", 0),
        "revoked": status_counts.get("revoked", 0),
    }

    return crud_list(
        request,
        qs,
        "inventory/integration/apiclient/list.html",
        search_fields=["name", "scopes"],
        filters=(),
        extra_context={
            "stats": stats,
            "status_choices": API_STATUS_CHOICES,
            "status": status,
            "protocol_choices": API_PROTOCOL_CHOICES,
            "protocol": protocol,
            "is_admin": bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)),
        },
    )


@login_required
def apiclient_detail(request, pk):
    """View details of an API client (token/revoke buttons gated on is_admin)."""
    return crud_detail(
        request,
        model=ApiClient,
        pk=pk,
        template="inventory/integration/apiclient/detail.html",
        extra_context={
            "is_admin": bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)),
        },
    )


@tenant_admin_required
def apiclient_create(request):
    """Register a new API client."""
    return crud_create(
        request,
        form_class=ApiClientForm,
        template="inventory/integration/apiclient/form.html",
        success_url="inventory:apiclient_list",
    )


@tenant_admin_required
def apiclient_edit(request, pk):
    """Edit an existing API client's registration details."""
    return crud_edit(
        request,
        model=ApiClient,
        pk=pk,
        form_class=ApiClientForm,
        template="inventory/integration/apiclient/form.html",
        success_url="inventory:apiclient_list",
    )


@tenant_admin_required
@require_POST
def apiclient_delete(request, pk):
    """Delete an API client record."""
    return crud_delete(
        request,
        model=ApiClient,
        pk=pk,
        success_url="inventory:apiclient_list",
    )


@tenant_admin_required
@require_POST
def apiclient_issue_token(request, pk):
    """Issue (or rotate) the client's token — reveal the plaintext EXACTLY ONCE.

    ``generate_api_token()`` mints from the CSPRNG; ``set_api_token()`` persists ONLY the 6-char
    prefix + SHA-256 digest via a narrow ``update_fields`` save. The plaintext goes into the flash
    message once — it is never stored and can never be retrieved again. The audit row records that
    an issue happened, NEVER the plaintext or the hash.

    A REVOKED client is refused outright: minting fresh credentials for it would quietly resurrect
    an identity its owner (or an admin) retired, and once a gateway honors the hashes that token
    is access again. Revocation is one-way by design — register a new client instead. The refusal
    happens BEFORE any credential change, so nothing is overwritten, no plaintext is revealed and
    no success audit row is written.
    """
    obj = get_object_or_404(ApiClient, pk=pk, tenant=request.tenant)
    if obj.status != "active":
        messages.error(request, "Client is revoked — issue a new client instead.")
        return redirect("inventory:apiclient_detail", pk=obj.pk)
    secret = ApiClient.generate_api_token()
    obj.set_api_token(secret)
    obj.save(update_fields=["api_token_prefix", "api_token_hash", "updated_at"])
    write_audit_log(request.user, obj, "update", {"action": "issue_api_token"})
    messages.success(
        request,
        f"API token for {obj.number}: {secret} — copy it now; it will never be shown again.",
    )
    return redirect("inventory:apiclient_detail", pk=obj.pk)


@tenant_admin_required
@require_POST
def apiclient_revoke(request, pk):
    """Revoke an active client — the ONLY writer of status/revoked_at (verb-driven lifecycle)."""
    obj = get_object_or_404(ApiClient, pk=pk, tenant=request.tenant)
    already = obj.status != "active"
    obj.revoke()
    write_audit_log(request.user, obj, "update", {"action": "revoke_api_client"})
    if already:
        messages.info(request, f"API client {obj.number} was already revoked.")
    else:
        messages.success(request, f"API client {obj.number} revoked — its token no longer represents access.")
    return redirect("inventory:apiclient_detail", pk=obj.pk)
