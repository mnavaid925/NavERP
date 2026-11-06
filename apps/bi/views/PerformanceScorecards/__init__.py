from apps.bi.views.PerformanceScorecards.KpiDefinitions import (
    kpi_definition_create,
    kpi_definition_delete,
    kpi_definition_detail,
    kpi_definition_edit,
    kpi_definition_list,
    kpi_definition_refresh,
)
from apps.bi.views.PerformanceScorecards.PerformanceScorecards import (
    performance_scorecard_create,
    performance_scorecard_delete,
    performance_scorecard_detail,
    performance_scorecard_edit,
    performance_scorecard_list,
    performance_scorecard_recalculate,
    performance_scorecard_strategy_map,
)
from apps.bi.views.PerformanceScorecards.ScorecardKpiAssignments import (
    scorecard_kpi_assignment_create,
    scorecard_kpi_assignment_delete,
    scorecard_kpi_assignment_detail,
    scorecard_kpi_assignment_edit,
    scorecard_kpi_assignment_list,
    scorecard_kpi_assignment_record_actual,
)
from apps.bi.views.PerformanceScorecards.StrategicObjectives import (
    strategic_objective_create,
    strategic_objective_delete,
    strategic_objective_detail,
    strategic_objective_edit,
    strategic_objective_list,
)

__all__ = [
    "kpi_definition_list",
    "kpi_definition_create",
    "kpi_definition_detail",
    "kpi_definition_edit",
    "kpi_definition_delete",
    "kpi_definition_refresh",
    "performance_scorecard_list",
    "performance_scorecard_create",
    "performance_scorecard_detail",
    "performance_scorecard_edit",
    "performance_scorecard_delete",
    "performance_scorecard_recalculate",
    "performance_scorecard_strategy_map",
    "scorecard_kpi_assignment_list",
    "scorecard_kpi_assignment_create",
    "scorecard_kpi_assignment_detail",
    "scorecard_kpi_assignment_edit",
    "scorecard_kpi_assignment_delete",
    "scorecard_kpi_assignment_record_actual",
    "strategic_objective_list",
    "strategic_objective_create",
    "strategic_objective_detail",
    "strategic_objective_edit",
    "strategic_objective_delete",
]
