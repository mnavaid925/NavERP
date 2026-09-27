"""tenants — PlanEntitlement views (0.19, plan grants + subscription-level overrides).

Bullet 2's GRANT half. `feature_choices` is a QUERYSET, so the template's pk comparison must be
`{% if request.GET.feature == f.pk|stringformat:"d" %}` — NEVER `|slugify`; a pk is not a slug, and
the rule exists because it has already broken once. The filter is declared
`("feature", "feature_id", True)`, so `?feature=abc` and `?feature=0` are both skipped rather than
silently emptying the register (L11).
"""
from apps.tenants.views._common import *  # noqa: F401,F403
from apps.tenants.models import (
    EntitlementFeature,
    PlanEntitlement,
)
from apps.tenants.forms import (
    PlanEntitlementForm,
)


@tenant_admin_required
def planentitlement_list(request):
    qs = (PlanEntitlement.objects.filter(tenant=request.tenant)
          .select_related("feature", "subscription"))
    return crud_list(
        request, qs, "tenants/planentitlement/list.html",
        search_fields=["privilege_value", "notes"],
        filters=[("plan", "plan", False),
                 ("feature", "feature_id", True),
                 ("enabled", "is_enabled", False),
                 ("addon", "is_add_on", False)],
        extra_context={
            "plan_choices": PlanEntitlement.PLAN_CHOICES,
            "feature_choices": EntitlementFeature.objects
                                   .filter(tenant=request.tenant).order_by("code"),
            # Literal "True"/"False" only — crud_list maps those two and nothing else ([RULING] 6).
            "enabled_choices": [("True", "Enabled"), ("False", "Disabled")],
            "addon_choices": [("True", "Add-on"), ("False", "Included")],
        },
    )


@tenant_admin_required
def planentitlement_create(request):
    return crud_create(request, form_class=PlanEntitlementForm,
                       template="tenants/planentitlement/form.html",
                       success_url="tenants:planentitlement_list")


@tenant_admin_required
def planentitlement_detail(request, pk):
    obj = get_object_or_404(
        PlanEntitlement.objects.select_related("feature", "subscription"),
        pk=pk, tenant=request.tenant,
    )
    # All three lists CAPPED AT 50, the embedded-list precedent from 0.1.
    plan_grants = (PlanEntitlement.objects.filter(tenant=request.tenant, feature_id=obj.feature_id,
                                                  subscription__isnull=True)
                   .order_by("plan")[:50])
    overrides = (PlanEntitlement.objects.filter(tenant=request.tenant, feature_id=obj.feature_id,
                                                subscription__isnull=False)
                 .order_by("subscription_id")[:50])
    # A REAL derived value, not a tautology, and it is what makes [RULING] 3's read-order rule
    # visible. Built as a dict comprehension over the ALREADY-FETCHED list — never a per-row
    # `.filter()`, which re-queries on every render (the `_usage_summary` docstring, verbatim).
    overridden_features = {grant.feature_id: grant.privilege_value for grant in plan_grants}
    return crud_detail(
        request, model=PlanEntitlement, pk=pk,
        template="tenants/planentitlement/detail.html",
        extra_context={
            "plan_grants": plan_grants,
            "overrides": overrides,
            "overridden_features": overridden_features,
        },
    )


@tenant_admin_required
def planentitlement_edit(request, pk):
    return crud_edit(request, model=PlanEntitlement, pk=pk, form_class=PlanEntitlementForm,
                     template="tenants/planentitlement/form.html",
                     success_url="tenants:planentitlement_list")


@require_POST
@tenant_admin_required
def planentitlement_delete(request, pk):
    """`require_POST` OUTSIDE the role gate — 405 for a wrong method regardless of role. See
    `entitlementfeature_delete` for the full decorator-order rationale."""
    return crud_delete(request, model=PlanEntitlement, pk=pk,
                       success_url="tenants:planentitlement_list")
