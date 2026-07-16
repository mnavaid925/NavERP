"""tenants — EncryptionKey views (split from apps/tenants/views.py)."""
from apps.tenants.views._common import *  # noqa: F401,F403
from apps.tenants.models import (
    EncryptionKey,
)
from apps.tenants.forms import (
    EncryptionKeyForm,
)


# ========================================================== Encryption keys
@tenant_admin_required
def encryptionkey_list(request):
    return crud_list(
        request, EncryptionKey.objects.filter(tenant=request.tenant),
        "tenants/encryptionkey/list.html",
        search_fields=["name", "prefix"],
        filters=[("status", "status", False)],
        extra_context={"status_choices": EncryptionKey.STATUS_CHOICES},
    )


@tenant_admin_required
def encryptionkey_create(request):
    if request.method == "POST":
        form = EncryptionKeyForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            key = form.save(commit=False)
            key.tenant = request.tenant
            plaintext = EncryptionKey.generate_plaintext()
            key.set_secret(plaintext)
            key.save()
            write_audit_log(request.user, key, "create")
            # L25: reveal the plaintext exactly once via a pop-once session key (never via messages).
            request.session[KEY_REVEAL_SESSION] = {"pk": key.pk, "secret": plaintext}
            messages.success(request, "Encryption key created. Copy the secret now — it won't be shown again.")
            return redirect("tenants:encryptionkey_detail", pk=key.pk)
    else:
        form = EncryptionKeyForm(tenant=request.tenant)
    return render(request, "tenants/encryptionkey/form.html", {"form": form, "is_edit": False})


@tenant_admin_required
def encryptionkey_detail(request, pk):
    obj = get_object_or_404(EncryptionKey, pk=pk, tenant=request.tenant)
    reveal = request.session.pop(KEY_REVEAL_SESSION, None)
    plaintext_once = reveal["secret"] if reveal and reveal.get("pk") == obj.pk else None
    return render(request, "tenants/encryptionkey/detail.html",
                  {"obj": obj, "plaintext_once": plaintext_once})


@tenant_admin_required
def encryptionkey_edit(request, pk):
    return crud_edit(request, model=EncryptionKey, pk=pk, form_class=EncryptionKeyForm,
                     template="tenants/encryptionkey/form.html",
                     success_url="tenants:encryptionkey_list")


@tenant_admin_required
@require_POST
def encryptionkey_rotate(request, pk):
    key = get_object_or_404(EncryptionKey, pk=pk, tenant=request.tenant)
    plaintext = EncryptionKey.generate_plaintext()
    key.set_secret(plaintext)
    key.status = "active"
    key.last_rotated_at = timezone.now()
    key.save()
    write_audit_log(request.user, key, "update", {"action": "rotate"})
    request.session[KEY_REVEAL_SESSION] = {"pk": key.pk, "secret": plaintext}
    messages.success(request, "Key rotated. Copy the new secret now — it won't be shown again.")
    return redirect("tenants:encryptionkey_detail", pk=key.pk)


@tenant_admin_required
@require_POST
def encryptionkey_delete(request, pk):
    return crud_delete(request, model=EncryptionKey, pk=pk, success_url="tenants:encryptionkey_list")
