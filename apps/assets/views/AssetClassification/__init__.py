from apps.assets.views.AssetClassification.AssetCategories import (
    asset_category_create,
    asset_category_delete,
    asset_category_detail,
    asset_category_edit,
    asset_category_list,
)
from apps.assets.views.AssetClassification.AssetCriticalityAssessments import (
    asset_criticality_assessment_approve,
    asset_criticality_assessment_create,
    asset_criticality_assessment_delete,
    asset_criticality_assessment_detail,
    asset_criticality_assessment_edit,
    asset_criticality_assessment_list,
)
from apps.assets.views.AssetClassification.AssetModels import (
    asset_model_create,
    asset_model_delete,
    asset_model_detail,
    asset_model_edit,
    asset_model_list,
)
from apps.assets.views.AssetClassification.AssetSpecificationTemplates import (
    asset_specification_template_create,
    asset_specification_template_delete,
    asset_specification_template_detail,
    asset_specification_template_edit,
    asset_specification_template_list,
)

__all__ = [
    "asset_category_list",
    "asset_category_detail",
    "asset_category_create",
    "asset_category_edit",
    "asset_category_delete",
    "asset_model_list",
    "asset_model_detail",
    "asset_model_create",
    "asset_model_edit",
    "asset_model_delete",
    "asset_criticality_assessment_list",
    "asset_criticality_assessment_detail",
    "asset_criticality_assessment_create",
    "asset_criticality_assessment_edit",
    "asset_criticality_assessment_delete",
    "asset_criticality_assessment_approve",
    "asset_specification_template_list",
    "asset_specification_template_detail",
    "asset_specification_template_create",
    "asset_specification_template_edit",
    "asset_specification_template_delete",
]
