from apps.ecommerce.views.MultiStore.MultiStoreHub import multi_store_hub
from apps.ecommerce.views.MultiStore.StorefrontInstances import (
    storefront_instance_list,
    storefront_instance_detail,
    storefront_instance_create,
    storefront_instance_edit,
    storefront_instance_delete,
    storefront_toggle_status,
)
from apps.ecommerce.views.MultiStore.StorefrontCatalogAssignments import (
    storefront_catalog_assignment_list,
    storefront_catalog_assignment_detail,
    storefront_catalog_assignment_create,
    storefront_catalog_assignment_edit,
    storefront_catalog_assignment_delete,
)
from apps.ecommerce.views.MultiStore.PlatformEnvironments import (
    platform_environment_list,
    platform_environment_detail,
    platform_environment_create,
    platform_environment_edit,
    platform_environment_delete,
)
from apps.ecommerce.views.MultiStore.DeploymentPipelines import (
    deployment_pipeline_list,
    deployment_pipeline_detail,
    deployment_pipeline_create,
    deployment_pipeline_edit,
    deployment_pipeline_delete,
    deployment_promote,
    deployment_rollback,
)

__all__ = [
    "multi_store_hub",
    "storefront_instance_list",
    "storefront_instance_detail",
    "storefront_instance_create",
    "storefront_instance_edit",
    "storefront_instance_delete",
    "storefront_toggle_status",
    "storefront_catalog_assignment_list",
    "storefront_catalog_assignment_detail",
    "storefront_catalog_assignment_create",
    "storefront_catalog_assignment_edit",
    "storefront_catalog_assignment_delete",
    "platform_environment_list",
    "platform_environment_detail",
    "platform_environment_create",
    "platform_environment_edit",
    "platform_environment_delete",
    "deployment_pipeline_list",
    "deployment_pipeline_detail",
    "deployment_pipeline_create",
    "deployment_pipeline_edit",
    "deployment_pipeline_delete",
    "deployment_promote",
    "deployment_rollback",
]
