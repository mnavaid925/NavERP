from django.urls import path
from apps.ecommerce.views.MultiStore import DeploymentPipelines as views

urlpatterns = [
    path("multi-store/deployments/", views.deployment_pipeline_list, name="deployment_pipeline_list"),
    path("multi-store/deployments/create/", views.deployment_pipeline_create, name="deployment_pipeline_create"),
    path("multi-store/deployments/<int:pk>/", views.deployment_pipeline_detail, name="deployment_pipeline_detail"),
    path("multi-store/deployments/<int:pk>/edit/", views.deployment_pipeline_edit, name="deployment_pipeline_edit"),
    path("multi-store/deployments/<int:pk>/delete/", views.deployment_pipeline_delete, name="deployment_pipeline_delete"),
    path("multi-store/deployments/<int:pk>/promote/", views.deployment_promote, name="deployment_promote"),
    path("multi-store/deployments/<int:pk>/rollback/", views.deployment_rollback, name="deployment_rollback"),
]
