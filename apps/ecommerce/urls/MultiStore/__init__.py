from apps.ecommerce.urls.MultiStore.MultiStoreHub import urlpatterns as hub_urls
from apps.ecommerce.urls.MultiStore.StorefrontInstances import urlpatterns as storefront_urls
from apps.ecommerce.urls.MultiStore.StorefrontCatalogAssignments import urlpatterns as catalog_assignment_urls
from apps.ecommerce.urls.MultiStore.PlatformEnvironments import urlpatterns as environment_urls
from apps.ecommerce.urls.MultiStore.DeploymentPipelines import urlpatterns as deployment_urls

urlpatterns = (
    hub_urls
    + storefront_urls
    + catalog_assignment_urls
    + environment_urls
    + deployment_urls
)
