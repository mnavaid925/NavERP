from django.urls import path

from apps.assets.views.AssetClassification.AssetSpecificationTemplates import (
    asset_specification_template_create,
    asset_specification_template_delete,
    asset_specification_template_detail,
    asset_specification_template_edit,
    asset_specification_template_list,
)

urlpatterns = [
    path("classification/spec-templates/", asset_specification_template_list, name="asset_specification_template_list"),
    path("classification/spec-templates/create/", asset_specification_template_create, name="asset_specification_template_create"),
    path("classification/spec-templates/<int:pk>/", asset_specification_template_detail, name="asset_specification_template_detail"),
    path("classification/spec-templates/<int:pk>/edit/", asset_specification_template_edit, name="asset_specification_template_edit"),
    path("classification/spec-templates/<int:pk>/delete/", asset_specification_template_delete, name="asset_specification_template_delete"),
]
