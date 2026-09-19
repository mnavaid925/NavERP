"""core — 0.6 module access scope views.

Config surfaces, so they are admin-gated: a member who can edit their own data scope has no data
scope. The one member-facing page here is the access matrix, which is read-only and reports what the
workspace's policy actually is.
"""
from django.contrib import messages
from django.shortcuts import redirect

from apps.core.views._common import *  # noqa: F401,F403
from apps.core.utils import write_audit_log
from apps.core.models import (
    ModuleAccessScope,
    SensitiveFieldMask,
)
from apps.core.forms import (
    ModuleAccessScopeForm,
    SensitiveFieldMaskForm,
)
from apps.core.navigation import parse_catalog


# --------------------------------------------------------------- the registry
@tenant_admin_required
def module_scope_list(request):
    qs = (ModuleAccessScope.objects.filter(tenant=request.tenant)
          .prefetch_related("masks"))
    return crud_list(
        request, qs,
        "core/modulescope/list.html",
        search_fields=["module_slug", "module_title", "notes"],
        # `?module=<slug>` is what each of 0.6's thirteen per-module bullets deep-links to, so one
        # bullet shows THAT module's scope rather than thirteen bullets pointing at one page.
        filters=[("data_scope", "data_scope", False), ("enabled", "is_enabled", False),
                 ("module", "module_slug", False)],
        extra_context={"data_scope_choices": ModuleAccessScope.DATA_SCOPE_CHOICES,
                       "enabled_choices": [("True", "Enabled"), ("False", "Disabled")],
                       "modules": ModuleAccessScope.objects.filter(tenant=request.tenant)
                       .values_list("module_slug", "module_title")},
    )


@tenant_admin_required
def module_scope_detail(request, pk):
    obj = get_object_or_404(ModuleAccessScope.objects.prefetch_related("masks__exempt_roles"),
                            pk=pk, tenant=request.tenant)
    return render(request, "core/modulescope/detail.html",
                  {"obj": obj, "masks": obj.masks.all()})


@tenant_admin_required
def module_scope_create(request):
    return crud_create(request, form_class=ModuleAccessScopeForm,
                       template="core/modulescope/form.html",
                       success_url="core:module_scope_list")


@tenant_admin_required
def module_scope_edit(request, pk):
    return crud_edit(request, model=ModuleAccessScope, pk=pk, form_class=ModuleAccessScopeForm,
                     template="core/modulescope/form.html",
                     success_url="core:module_scope_list")


@require_POST
@tenant_admin_required
def module_scope_delete(request, pk):
    """`require_POST` sits ABOVE `tenant_admin_required`: decorators apply bottom-up, so the
    outermost runs first, and with the role gate outermost a member's GET would be answered 403
    before the method check ran. House standard is 405 for a wrong method regardless of role
    (7.7's ruling) — the sibling `module_scope_sync` already had it right."""
    return crud_delete(request, model=ModuleAccessScope, pk=pk,
                       success_url="core:module_scope_list")


@require_POST
@tenant_admin_required
def module_scope_sync(request):
    """Materialise a scope row for every module in the catalog. Idempotent.

    Explicit rather than automatic so the rows are a recorded decision, and so adding a module to
    `NavERP.md` never silently creates policy. Existing rows keep their settings — this only fills
    the gaps, which is what makes it safe to re-run after the catalog changes.
    """
    existing = set(ModuleAccessScope.objects.filter(tenant=request.tenant)
                   .values_list("module_slug", flat=True))
    created = 0
    for mod in parse_catalog():
        slug = (mod.get("title") or "").lower()
        # `parse_catalog` yields {num, title, submodules}; the slug is derived the same way the
        # module→app map is, lowercased with punctuation dropped, so it matches LIVE_LINKS keys.
        slug = "".join(ch if ch.isalnum() else "" for ch in slug)[:40] or f"module{mod['num']}"
        if slug in existing:
            continue
        ModuleAccessScope.objects.create(
            tenant=request.tenant, module_number=mod["num"], module_slug=slug,
            module_title=mod["title"],
        )
        created += 1
    write_audit_log(request.user, None, "create",
                    changes={"verb": "module_scope_sync", "created": created})
    messages.success(request, f"Added {created} module scope row(s); existing rows were left alone.")
    return redirect("core:module_scope_list")


# --------------------------------------------------------------- field masks
@tenant_admin_required
def field_mask_list(request):
    qs = (SensitiveFieldMask.objects.filter(tenant=request.tenant)
          .select_related("scope").prefetch_related("exempt_roles"))
    return crud_list(
        request, qs,
        "core/fieldmask/list.html",
        search_fields=["field_name", "scope__module_slug", "notes"],
        filters=[("mask_style", "mask_style", False)],
        extra_context={"mask_style_choices": SensitiveFieldMask.MASK_STYLE_CHOICES},
    )


@tenant_admin_required
def field_mask_create(request):
    return crud_create(request, form_class=SensitiveFieldMaskForm,
                       template="core/fieldmask/form.html",
                       success_url="core:field_mask_list")


@tenant_admin_required
def field_mask_edit(request, pk):
    return crud_edit(request, model=SensitiveFieldMask, pk=pk, form_class=SensitiveFieldMaskForm,
                     template="core/fieldmask/form.html",
                     success_url="core:field_mask_list")


@require_POST
@tenant_admin_required
def field_mask_delete(request, pk):
    """See the decorator-order note on `module_scope_delete`."""
    return crud_delete(request, model=SensitiveFieldMask, pk=pk,
                       success_url="core:field_mask_list")


# --------------------------------------------------------------- the matrix (computed)
@login_required
def access_matrix(request):
    """COMPUTED board — no table. Every catalog module against this workspace's configured policy.

    Reports three things per module, and keeps them distinct because conflating them is how a
    policy that does nothing gets mistaken for protection:
      * CONFIGURED — a scope row exists;
      * ENFORCING — that row would actually narrow what a member sees (`enforces_scope`);
      * BUILT — the module has a `LIVE_LINKS` entry at all.
    """
    from apps.core.navigation import LIVE_LINKS

    scopes = {s.module_slug: s for s in
              ModuleAccessScope.objects.filter(tenant=request.tenant).prefetch_related("masks")}
    rows = []
    for mod in parse_catalog():
        num = mod["num"]
        live = sorted(k for k in LIVE_LINKS if k.split(".")[0] == num)
        title = mod["title"]
        slug = "".join(ch if ch.isalnum() else "" for ch in title.lower())[:40] or f"module{num}"
        scope = scopes.get(slug)
        rows.append({
            "num": num, "title": title, "slug": slug,
            "live_count": len(live),
            "scope": scope,
            "enforcing": bool(scope and scope.enforces_scope),
            "mask_count": scope.masks.count() if scope else 0,
        })

    configured = sum(1 for r in rows if r["scope"])
    enforcing = sum(1 for r in rows if r["enforcing"])
    built = sum(1 for r in rows if r["live_count"])
    context = {
        "rows": rows,
        "configured_count": configured,
        "enforcing_count": enforcing,
        "built_count": built,
        "module_count": len(rows),
        "mask_total": SensitiveFieldMask.objects.filter(tenant=request.tenant).count(),
    }
    return render(request, "core/accessmatrix.html", context)
