from apps.bi.views.DataQuality.DataQualityExceptions import (
    data_quality_exception_create,
    data_quality_exception_delete,
    data_quality_exception_detail,
    data_quality_exception_edit,
    data_quality_exception_list,
    data_quality_exception_remediate,
)
from apps.bi.views.DataQuality.DataQualityProfiles import (
    data_quality_profile_create,
    data_quality_profile_delete,
    data_quality_profile_detail,
    data_quality_profile_edit,
    data_quality_profile_list,
    data_quality_profile_run,
)
from apps.bi.views.DataQuality.DataQualityRules import (
    data_quality_rule_create,
    data_quality_rule_delete,
    data_quality_rule_detail,
    data_quality_rule_edit,
    data_quality_rule_list,
    data_quality_rule_run,
)
from apps.bi.views.DataQuality.DataQualityScorecards import (
    data_quality_scorecard_create,
    data_quality_scorecard_delete,
    data_quality_scorecard_detail,
    data_quality_scorecard_edit,
    data_quality_scorecard_list,
    data_quality_scorecard_recalculate,
)
from apps.bi.views.DataQuality.QualityOverviewViews import quality_overview

__all__ = [
    "data_quality_profile_list",
    "data_quality_profile_create",
    "data_quality_profile_detail",
    "data_quality_profile_edit",
    "data_quality_profile_delete",
    "data_quality_profile_run",
    "data_quality_rule_list",
    "data_quality_rule_create",
    "data_quality_rule_detail",
    "data_quality_rule_edit",
    "data_quality_rule_delete",
    "data_quality_rule_run",
    "data_quality_exception_list",
    "data_quality_exception_create",
    "data_quality_exception_detail",
    "data_quality_exception_edit",
    "data_quality_exception_delete",
    "data_quality_exception_remediate",
    "data_quality_scorecard_list",
    "data_quality_scorecard_create",
    "data_quality_scorecard_detail",
    "data_quality_scorecard_edit",
    "data_quality_scorecard_delete",
    "data_quality_scorecard_recalculate",
    "quality_overview",
]
