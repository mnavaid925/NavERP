"""tenants — EntitlementFeature views (0.19, the commercial feature catalog).

Bullet 2's CATALOG half. Every `extra_context` key here backs a real dropdown and every dropdown has
a key (0.18 [RULING] 3, in BOTH directions). The boolean `addon_choices` uses the literal strings
`"True"` / `"False"` because `crud_list` maps only those ([RULING] 6) — `?addon=yes` would reach
`.filter(is_add_on="yes")`, raise ValueError, and be silently skipped by `crud.py:176`, so the
dropdown would render, appear selected, and do nothing.
"""
from apps.tenants.views._common import *  # noqa: F401,F403
from apps.tenants.models import (
    EntitlementFeature,
)
from apps.tenants.forms import (
    EntitlementFeatureForm,
)


@tenant_admin_required
def entitlementfeature_list(request):
    qs = EntitlementFeature.objects.filter(tenant=request.tenant)
    return crud_list(
        request, qs, "tenants/entitlementfeature/list.html",
        search_fields=["code", "name", "description"],
        filters=[("status", "status", False),
                 ("privilege_type", "privilege_type", False),
                 ("addon", "is_add_on", False)],
        extra_context={
            "status_choices": EntitlementFeature.STATUS_CHOICES,
            "privilege_type_choices": EntitlementFeature.PRIVILEGE_TYPE_CHOICES,
            "addon_choices": [("True", "Add-on"), ("False", "Included")],
        },
    )


@tenant_admin_required
def entitlementfeature_create(request):
    return crud_create(request, form_class=EntitlementFeatureForm,
                       template="tenants/entitlementfeature/form.html",
                       success_url="tenants:entitlementfeature_list")


@tenant_admin_required
def entitlementfeature_detail(request, pk):
    obj = get_object_or_404(EntitlementFeature, pk=pk, tenant=request.tenant)
    return crud_detail(
        request, model=EntitlementFeature, pk=pk,
        template="tenants/entitlementfeature/detail.html",
        # CAPPED AT 50, the `subscription_detail` embedded-list precedent: a feature granted on
        # every plan across many subscriptions would otherwise render an unbounded page.
        extra_context={
            "entitlements": obj.plan_entitlements.select_related("subscription")
                                         .order_by("plan", "feature__code")[:50],
        },
    )


@tenant_admin_required
def entitlementfeature_edit(request, pk):
    return crud_edit(request, model=EntitlementFeature, pk=pk, form_class=EntitlementFeatureForm,
                     template="tenants/entitlementfeature/form.html",
                     success_url="tenants:entitlementfeature_list")


@require_POST
@tenant_admin_required
def entitlementfeature_delete(request, pk):
    """`require_POST` sits ABOVE `tenant_admin_required` on purpose.

    Decorators apply bottom-up, so the OUTERMOST runs first. With the role gate outermost, a
    non-admin member's GET would be answered 403 by the role check before the method check ever ran;
    the house standard is 405 for a wrong method regardless of role.

    **No guard beyond the helper**, and deliberately so: the `usagerecord_delete` billed-row guard is
    NOT copied. An `EntitlementFeature` is a catalog row whose grants cascade, and freezing it would
    mean a mistyped code could never be corrected. `status="archived"` is the retirement path, and
    the list template's delete button says so.
    """
    return crud_delete(request, model=EntitlementFeature, pk=pk,
                       success_url="tenants:entitlementfeature_list")
