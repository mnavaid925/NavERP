from apps.bi.views.PredictiveAnalytics.ForecastExecutions import (
    forecast_execution_create,
    forecast_execution_delete,
    forecast_execution_detail,
    forecast_execution_edit,
    forecast_execution_list,
)
from apps.bi.views.PredictiveAnalytics.OptimizationScenarios import (
    optimization_scenario_create,
    optimization_scenario_delete,
    optimization_scenario_detail,
    optimization_scenario_edit,
    optimization_scenario_list,
    optimization_scenario_solve,
)
from apps.bi.views.PredictiveAnalytics.PredictiveModels import (
    predictive_model_create,
    predictive_model_delete,
    predictive_model_detail,
    predictive_model_edit,
    predictive_model_list,
    predictive_model_train,
)
from apps.bi.views.PredictiveAnalytics.StatisticalAnomalies import (
    statistical_anomaly_create,
    statistical_anomaly_delete,
    statistical_anomaly_detail,
    statistical_anomaly_edit,
    statistical_anomaly_list,
    statistical_anomaly_triage,
)

__all__ = [
    "predictive_model_list",
    "predictive_model_detail",
    "predictive_model_create",
    "predictive_model_edit",
    "predictive_model_delete",
    "predictive_model_train",
    "forecast_execution_list",
    "forecast_execution_detail",
    "forecast_execution_create",
    "forecast_execution_edit",
    "forecast_execution_delete",
    "statistical_anomaly_list",
    "statistical_anomaly_detail",
    "statistical_anomaly_create",
    "statistical_anomaly_edit",
    "statistical_anomaly_delete",
    "statistical_anomaly_triage",
    "optimization_scenario_list",
    "optimization_scenario_detail",
    "optimization_scenario_create",
    "optimization_scenario_edit",
    "optimization_scenario_delete",
    "optimization_scenario_solve",
]
