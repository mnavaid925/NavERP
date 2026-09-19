"""Module access scoping — the enforcement half of 0.6 "Application Module Administration".

`ModuleAccessScope` records the policy per tenant per module. This module is what MAKES IT BITE,
and it is deliberately small, because the honest scope of 0.6 is narrow:

**What this does.** `apply_data_scope()` narrows a queryset to the rows the actor is entitled to see,
and `crud_list()` calls it when a view opts in with `scope_module=`. That is real enforcement at one
integration point, and it is opt-in: a module that does not pass `scope_module` is unaffected.

**What this does NOT do.** It does not retrofit row-level security across the ~150 existing
sub-modules. Doing that properly means auditing every list view in the repo for the correct
owner field, and a blanket change to `crud_list` would silently empty registers in modules whose
models have no such field. So the mechanism is provided, proven, and wired where a module asks for
it — and the access matrix says plainly which modules currently enforce their scope.

**What is not built at all.** Column-level security, consent management, e-signature (21 CFR Part 11),
retention locks, check-in/out controls, PCI scope isolation, and dataset certification. Those are named
on the matrix rather than implied by a scope row existing.
"""
from .models import ModuleAccessScope


def scope_for(tenant, module_slug):
    """The tenant's scope row for one module, or None.

    Returns None rather than a default object on purpose: "no row" means "no policy configured", and
    every caller must decide what that means rather than being handed a fabricated 'all access'.
    """
    if tenant is None or not module_slug:
        return None
    return (ModuleAccessScope.objects
            .filter(tenant=tenant, module_slug=module_slug)
            .first())


def apply_data_scope(qs, request, module_slug, owner_field):
    """Narrow `qs` to what `request.user` may see under the module's configured data scope.

    `owner_field` is the ORM lookup that identifies the acting user on this model (e.g. `"owner"`,
    `"assigned_to"`, `"created_by"`). It is a call-site parameter rather than a column on the scope
    row because a module holds many models and each has its own idea of "mine" — one field name
    cannot be right for all of them.

    Rules, in order:
      * no scope row, scope disabled, or `data_scope="all"` -> unchanged (the default posture, so
        nothing changes until an admin configures it);
      * a superuser or tenant admin -> unchanged (an admin who cannot see the register cannot
        administer it);
      * `data_scope="own"` -> rows where `owner_field` is the actor;
      * `data_scope="team"` -> rows in the actor's own `core.OrgUnit`, falling back to own-records
        when the actor has no OrgUnit. That fallback is deliberate: "team" must never widen to
        everything just because the actor is unassigned.
    """
    scope = scope_for(getattr(request, "tenant", None), module_slug)
    if scope is None or not scope.is_enabled or scope.data_scope == "all":
        return qs

    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        return qs
    if getattr(user, "is_superuser", False) or getattr(user, "is_tenant_admin", False):
        return qs

    if scope.data_scope == "own":
        return qs.filter(**{owner_field: user})

    if scope.data_scope == "team":
        # `Employment.org_unit` is where a user's department actually lives; `User` has no org_unit
        # column, so resolve it once and fall back to own-records rather than widening.
        from .models import Employment
        employment = (Employment.objects
                      .filter(tenant=getattr(request, "tenant", None), party=user.party)
                      .order_by("-id").first())
        if employment is None or employment.org_unit_id is None:
            return qs.filter(**{owner_field: user})
        return qs.filter(**{f"{owner_field}__employment__org_unit_id": employment.org_unit_id})

    return qs


# ------------------------------------------------------------------ field masking
def mask_value(style, value):
    """Apply one mask style to a value. Returns the masked STRING, never the original."""
    if value is None or value == "":
        return value
    text = str(value)
    if style == "full":
        return "••••••"
    if style == "last4":
        return "•" * max(0, len(text) - 4) + text[-4:]
    if style == "email":
        local, _, domain = text.partition("@")
        if not domain:
            return mask_value("partial", text)
        head = local[:1] if local else ""
        return f"{head}{'•' * max(1, len(local) - 1)}@{domain}"
    # "partial" and any unrecognised style: keep the first and last character.
    if len(text) <= 2:
        return "••"
    return f"{text[0]}{'•' * (len(text) - 2)}{text[-1]}"


def mask_for(tenant, module_slug, field_name, value, user):
    """Mask `value` if the tenant has configured a mask for this module+field and the actor's role
    is not exempt. Returns the value unchanged when no mask applies."""
    if value is None or value == "":
        return value
    scope = scope_for(tenant, module_slug)
    if scope is None or not scope.mask_sensitive:
        return value
    rule = scope.masks.filter(field_name=field_name).first()
    if rule is None:
        return value
    role_id = getattr(user, "role_id", None)
    if role_id is not None and rule.exempt_roles.filter(pk=role_id).exists():
        return value
    return mask_value(rule.mask_style, value)
