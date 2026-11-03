import hashlib
import secrets
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.ecommerce.forms.IntegrationApi.ApiCredentials import ApiCredentialForm
from apps.ecommerce.models.IntegrationApi.ApiCredentials import ApiCredential
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def api_credential_list(request):
    qs = ecommerce_scope(ApiCredential.objects.all(), request)

    search_query = request.GET.get("q", "").strip()
    if search_query:
        qs = qs.filter(
            Q(name__icontains=search_query)
            | Q(client_id__icontains=search_query)
            | Q(number__icontains=search_query)
            | Q(scopes__icontains=search_query)
        )

    tier_filter = request.GET.get("tier", "").strip()
    if tier_filter:
        qs = qs.filter(tier=tier_filter)

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status=status_filter)

    stats = qs.aggregate(
        total_count=Count("id"),
        active_count=Count("id", filter=Q(status="active")),
        revoked_count=Count("id", filter=Q(status="revoked")),
    )
    total_count = stats["total_count"]
    active_count = stats["active_count"]
    revoked_count = stats["revoked_count"]

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "credentials": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "total_count": total_count,
        "active_count": active_count,
        "revoked_count": revoked_count,
        "search_query": search_query,
        "q": search_query,
        "tier_filter": tier_filter,
        "status_filter": status_filter,
        "tier_choices": ApiCredential.TIER_CHOICES,
        "status_choices": ApiCredential.STATUS_CHOICES,
    }
    return render(request, "ecommerce/integration_api/api_credential/list.html", context)


# Route alias
apicredential_list = api_credential_list


@login_required
def api_credential_detail(request, pk):
    credential = ecommerce_object(ApiCredential, pk, request)
    new_raw_secret = request.session.pop(f"new_secret_{credential.pk}", None)

    context = {
        "credential": credential,
        "new_raw_secret": new_raw_secret,
    }
    return render(request, "ecommerce/integration_api/api_credential/detail.html", context)


# Route alias
apicredential_detail = api_credential_detail


@login_required
def api_credential_create(request):
    if request.method == "POST":
        form = ApiCredentialForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            credential = form.save(commit=False)
            credential.tenant = request.tenant
            credential.created_by = request.user

            prefix = "pub" if credential.tier == "storefront_public" else "live"
            credential.client_id = f"nep_{prefix}_{secrets.token_hex(12)}"

            raw_secret = f"nep_sec_{secrets.token_urlsafe(32)}"
            credential.client_secret_hash = hashlib.sha256(raw_secret.encode("utf-8")).hexdigest()
            credential.secret_prefix = raw_secret[:12] + "..."
            credential.save()

            request.session[f"new_secret_{credential.pk}"] = raw_secret

            write_audit_log(
                request.user,
                credential,
                "create",
                changes={
                    "name": credential.name,
                    "tier": credential.tier,
                    "client_id": credential.client_id,
                },
                tenant=request.tenant,
            )
            messages.success(
                request,
                f"API Credential '{credential.name}' provisioned. Please copy the secret key now; it will not be shown again.",
            )
            return redirect("ecommerce:apicredential_detail", pk=credential.pk)
    else:
        form = ApiCredentialForm(tenant=request.tenant)

    context = {
        "form": form,
        "credential": None,
        "is_edit": False,
    }
    return render(request, "ecommerce/integration_api/api_credential/form.html", context)


# Route alias
apicredential_create = api_credential_create


@login_required
def api_credential_edit(request, pk):
    credential = ecommerce_object(ApiCredential, pk, request)

    if request.method == "POST":
        form = ApiCredentialForm(request.POST, instance=credential, tenant=request.tenant)
        if form.is_valid():
            credential = form.save()
            write_audit_log(
                request.user,
                credential,
                "update",
                changes={"name": credential.name, "status": credential.status, "scopes": credential.scopes},
                tenant=request.tenant,
            )
            messages.success(request, f"API Credential '{credential.name}' updated.")
            return redirect("ecommerce:apicredential_detail", pk=credential.pk)
    else:
        form = ApiCredentialForm(instance=credential, tenant=request.tenant)

    context = {
        "form": form,
        "credential": credential,
        "is_edit": True,
    }
    return render(request, "ecommerce/integration_api/api_credential/form.html", context)


# Route alias
apicredential_edit = api_credential_edit


@login_required
@require_POST
def api_credential_delete(request, pk):
    credential = ecommerce_object(ApiCredential, pk, request)
    name = credential.name
    write_audit_log(
        request.user,
        credential,
        "delete",
        changes={"name": name, "client_id": credential.client_id},
        tenant=request.tenant,
    )
    credential.delete()
    messages.success(request, f"API Credential '{name}' deleted.")
    return redirect("ecommerce:apicredential_list")


# Route alias
apicredential_delete = api_credential_delete


@login_required
@require_POST
def api_credential_revoke(request, pk):
    credential = ecommerce_object(ApiCredential, pk, request)
    credential.status = "revoked"
    credential.revoked_at = timezone.now()
    credential.save(update_fields=["status", "revoked_at"])

    write_audit_log(
        request.user,
        credential,
        "revoke",
        changes={"status": "revoked"},
        tenant=request.tenant,
    )
    messages.warning(request, f"API Credential '{credential.name}' has been permanently revoked.")
    return redirect("ecommerce:apicredential_detail", pk=credential.pk)


# Route alias
apicredential_revoke = api_credential_revoke
