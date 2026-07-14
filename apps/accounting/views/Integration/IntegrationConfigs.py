"""Accounting 2.15 Integration & API — IntegrationConfigs views (split from views.py/views_advanced.py)."""
from apps.accounting.views._common import *  # noqa: F401,F403
from apps.accounting.models import (
    IntegrationConfig,
)
from apps.accounting.forms import (
    IntegrationConfigForm,
)


# ================================================================= 2.15 Integration & API
@login_required
def integration_list(request):
    return crud_list(
        request, IntegrationConfig.objects.filter(tenant=request.tenant),
        "accounting/integration/list.html",
        search_fields=["name", "provider"],
        filters=[("category", "category", False), ("status", "status", False),
                 ("is_active", "is_active", False)],
        extra_context={"category_choices": IntegrationConfig.CATEGORY_CHOICES,
                       "status_choices": IntegrationConfig.STATUS_CHOICES},
    )


@login_required
def integration_create(request):
    return crud_create(request, form_class=IntegrationConfigForm, template="accounting/integration/form.html",
                       success_url="accounting:integration_list")


@login_required
def integration_detail(request, pk):
    obj = get_object_or_404(IntegrationConfig, pk=pk, tenant=request.tenant)
    # One-time reveal of a freshly rotated key (L25 — pop-once session key, never flashed).
    reveal = request.session.pop("_integration_key_reveal", None)
    plaintext_once = reveal["secret"] if reveal and reveal.get("pk") == obj.pk else None
    return render(request, "accounting/integration/detail.html", {"obj": obj, "plaintext_once": plaintext_once})


@tenant_admin_required
def integration_edit(request, pk):
    return crud_edit(request, model=IntegrationConfig, pk=pk, form_class=IntegrationConfigForm,
                     template="accounting/integration/form.html", success_url="accounting:integration_list")


@tenant_admin_required
@require_POST
def integration_delete(request, pk):
    return crud_delete(request, model=IntegrationConfig, pk=pk, success_url="accounting:integration_list")


@tenant_admin_required
@require_POST
def integration_rotate_key(request, pk):
    obj = get_object_or_404(IntegrationConfig, pk=pk, tenant=request.tenant)
    secret = IntegrationConfig.generate_secret()
    with transaction.atomic():
        obj.set_secret(secret)
        obj.status = "connected"
        obj.save(update_fields=["api_key_prefix", "api_key_hash", "status", "updated_at"])
    # Reveal exactly once on the redirect target — never via messages (would persist in the session, L25).
    request.session["_integration_key_reveal"] = {"pk": obj.pk, "secret": secret}
    write_audit_log(request.user, obj, "update", {"action": "rotate_key"})
    messages.success(request, "API key rotated — copy it now; it won't be shown again.")
    return redirect("accounting:integration_detail", pk=pk)
