from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import render

from apps.ecommerce.models.MultiStore.StorefrontInstances import StorefrontInstance
from apps.ecommerce.models.MultiStore.PlatformEnvironments import PlatformEnvironment
from apps.ecommerce.models.MultiStore.DeploymentPipelines import DeploymentPipeline
from apps.ecommerce.views._common import ecommerce_scope


@login_required
def multi_store_hub(request):
    storefronts_qs = ecommerce_scope(StorefrontInstance.objects.all(), request)
    environments_qs = ecommerce_scope(PlatformEnvironment.objects.all(), request)
    pipelines_qs = ecommerce_scope(DeploymentPipeline.objects.all(), request)

    storefront_stats = storefronts_qs.aggregate(
        total=Count("id"),
        active=Count("id", filter=Q(status="active")),
    )
    total_storefronts = storefront_stats["total"]
    active_storefronts = storefront_stats["active"]

    environment_stats = environments_qs.aggregate(
        total=Count("id"),
        production=Count("id", filter=Q(env_type="production")),
    )
    total_environments = environment_stats["total"]
    production_environments = environment_stats["production"]

    storefronts = storefronts_qs.select_related("default_currency", "root_category")[:6]
    environments = environments_qs.select_related("storefront")[:6]
    recent_pipelines = pipelines_qs.select_related("environment", "promoted_by")[:8]

    context = {
        "total_storefronts": total_storefronts,
        "active_storefronts": active_storefronts,
        "total_environments": total_environments,
        "production_environments": production_environments,
        "storefronts": storefronts,
        "environments": environments,
        "recent_pipelines": recent_pipelines,
    }
    return render(request, "ecommerce/multi_store/multi_store_hub.html", context)
