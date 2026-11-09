from apps.assets.views.AssetPerformance.AssetDowntimeLogs import (
    asset_downtime_log_create,
    asset_downtime_log_delete,
    asset_downtime_log_detail,
    asset_downtime_log_edit,
    asset_downtime_log_list,
    asset_downtime_log_resolve,
)
from apps.assets.views.AssetPerformance.AssetEnergyReadings import (
    asset_energy_reading_create,
    asset_energy_reading_delete,
    asset_energy_reading_detail,
    asset_energy_reading_edit,
    asset_energy_reading_list,
    asset_energy_reading_validate,
)
from apps.assets.views.AssetPerformance.AssetOeeRecords import (
    asset_oee_record_create,
    asset_oee_record_delete,
    asset_oee_record_detail,
    asset_oee_record_edit,
    asset_oee_record_finalize,
    asset_oee_record_list,
)
from apps.assets.views.AssetPerformance.AssetPerformanceScorecards import (
    asset_performance_scorecard_create,
    asset_performance_scorecard_delete,
    asset_performance_scorecard_detail,
    asset_performance_scorecard_edit,
    asset_performance_scorecard_list,
    asset_performance_scorecard_publish,
)

__all__ = [
    "asset_downtime_log_list",
    "asset_downtime_log_detail",
    "asset_downtime_log_create",
    "asset_downtime_log_edit",
    "asset_downtime_log_delete",
    "asset_downtime_log_resolve",
    "asset_oee_record_list",
    "asset_oee_record_detail",
    "asset_oee_record_create",
    "asset_oee_record_edit",
    "asset_oee_record_delete",
    "asset_oee_record_finalize",
    "asset_energy_reading_list",
    "asset_energy_reading_detail",
    "asset_energy_reading_create",
    "asset_energy_reading_edit",
    "asset_energy_reading_delete",
    "asset_energy_reading_validate",
    "asset_performance_scorecard_list",
    "asset_performance_scorecard_detail",
    "asset_performance_scorecard_create",
    "asset_performance_scorecard_edit",
    "asset_performance_scorecard_delete",
    "asset_performance_scorecard_publish",
]
