from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.bi.forms.EmbeddedMobileBi.EmbedApiTokens import EmbedApiTokenForm
from apps.bi.models.EmbeddedMobileBi.EmbedApiTokens import EmbedApiToken
from apps.bi.views._common import bi_object, bi_scope
from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log


@login_required
def embed_api_token_list(request):
    qs = bi_scope(EmbedApiToken.objects.all(), request).select_related(
        "embedded_config", "created_by"
    )

    counts = qs.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status="active")),
        revoked=Count("id", filter=Q(status="revoked")),
    )
    total_count = counts["total"] or 0
    active_count = counts["active"] or 0
    revoked_count = counts["revoked"] or 0

    # Search
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains=q)
            | Q(number__icontains=q)
            | Q(token_prefix__icontains=q)
        )

    # Filters
    status = request.GET.get("status", "").strip()
    if status:
        qs = qs.filter(status=status)

    paginator = Paginator(qs, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "tokens": page_obj,
        "embed_api_tokens": page_obj,
        "total_count": total_count,
        "active_count": active_count,
        "revoked_count": revoked_count,
        "status_choices": EmbedApiToken.STATUS_CHOICES,
    }
    return render(
        request,
        "bi/embedded_mobile_bi/embedapitoken/list.html",
        context,
    )


@login_required
@tenant_admin_required
def embed_api_token_create(request):
    if request.method == "POST":
        form = EmbedApiTokenForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                raw_token, prefix, token_hash = EmbedApiToken.generate_secret()
                token = form.save(commit=False)
                token.tenant = request.tenant
                token.created_by = request.user
                token.token_prefix = prefix
                token.token_hash = token_hash
                token.save()
                write_audit_log(
                    request.user,
                    token,
                    "create",
                    tenant=request.tenant,
                )
            request.session["newly_generated_token"] = raw_token
            messages.success(request, f"API Token '{token.name}' generated successfully. Copy your key now!")
            return redirect("bi:embed_api_token_detail", pk=token.pk)
    else:
        form = EmbedApiTokenForm(tenant=request.tenant)

    return render(
        request,
        "bi/embedded_mobile_bi/embedapitoken/form.html",
        {"form": form, "title": "Generate Embed API Token"},
    )


@login_required
def embed_api_token_detail(request, pk):
    token = bi_object(
        request,
        EmbedApiToken,
        pk,
        select_related=("embedded_config", "created_by"),
    )

    new_key = request.session.pop("newly_generated_token", None)
    scopes_list = token.scopes if isinstance(token.scopes, list) else []
    injected_rls = token.injected_rls_context if isinstance(token.injected_rls_context, dict) else {}

    host = request.get_host()
    scheme = "https" if request.is_secure() else "http"

    token_display = new_key or f"{token.token_prefix}••••••••••••••••••••"

    js_sdk_snippet = (
        f"import {{ NavBiClient }} from '@nav-erp/bi-sdk';\n\n"
        f"const bi = new NavBiClient({{\n"
        f"  endpoint: '{scheme}://{host}',\n"
        f"  apiToken: '{token_display}',\n"
        f"}});\n\n"
        f"// Embed dashboard with token RLS context\n"
        f"await bi.mount('#analytics-container', {{\n"
        f"  configNumber: '{token.embedded_config.number if token.embedded_config else 'EMB-00001'}',\n"
        f"}});"
    )

    curl_snippet = (
        f"curl -X GET '{scheme}://{host}/api/v1/bi/query' \\\n"
        f"  -H 'Authorization: Bearer {token_display}' \\\n"
        f"  -H 'Content-Type: application/json' \\\n"
        f"  -d '{{\"query\": \"SELECT * FROM sales_summary LIMIT 10\"}}'"
    )

    context = {
        "token": token,
        "new_key": new_key,
        "scopes_list": scopes_list,
        "injected_rls": injected_rls,
        "js_sdk_snippet": js_sdk_snippet,
        "curl_snippet": curl_snippet,
    }
    return render(
        request,
        "bi/embedded_mobile_bi/embedapitoken/detail.html",
        context,
    )


@login_required
@tenant_admin_required
def embed_api_token_edit(request, pk):
    token = bi_object(request, EmbedApiToken, pk)

    if request.method == "POST":
        form = EmbedApiTokenForm(request.POST, instance=token, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                token = form.save()
                write_audit_log(
                    request.user,
                    token,
                    "update",
                    tenant=request.tenant,
                )
            messages.success(request, f"Token '{token.name}' updated successfully.")
            return redirect("bi:embed_api_token_detail", pk=token.pk)
    else:
        form = EmbedApiTokenForm(instance=token, tenant=request.tenant)

    return render(
        request,
        "bi/embedded_mobile_bi/embedapitoken/form.html",
        {"form": form, "token": token, "title": f"Edit {token.name}"},
    )


@login_required
@tenant_admin_required
@require_POST
def embed_api_token_delete(request, pk):
    token = bi_object(request, EmbedApiToken, pk)
    with transaction.atomic():
        write_audit_log(
            request.user,
            token,
            "delete",
            tenant=request.tenant,
        )
        token.delete()
    messages.success(request, "API Token deleted.")
    return redirect("bi:embed_api_token_list")


@login_required
@tenant_admin_required
@require_POST
def embed_api_token_revoke(request, pk):
    token = bi_object(request, EmbedApiToken, pk)
    with transaction.atomic():
        token.status = "revoked"
        token.save(update_fields=["status", "updated_at"])
        write_audit_log(
            request.user,
            token,
            "revoke",
            tenant=request.tenant,
        )
    messages.warning(request, f"API Token '{token.name}' has been permanently revoked.")
    return redirect("bi:embed_api_token_detail", pk=token.pk)
