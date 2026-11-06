from apps.bi.views.OlapAnalysis.OlapCubes import (
    olap_cube_create,
    olap_cube_delete,
    olap_cube_detail,
    olap_cube_edit,
    olap_cube_list,
    olap_cube_refresh,
)
from apps.bi.views.OlapAnalysis.PivotViews import (
    pivot_view_create,
    pivot_view_delete,
    pivot_view_detail,
    pivot_view_edit,
    pivot_view_list,
    pivot_view_matrix,
)
from apps.bi.views.OlapAnalysis.WhatIfScenarios import (
    what_if_scenario_commit,
    what_if_scenario_create,
    what_if_scenario_delete,
    what_if_scenario_detail,
    what_if_scenario_edit,
    what_if_scenario_list,
    what_if_scenario_simulate,
)
from apps.bi.views.OlapAnalysis.WritebackCells import (
    writeback_cell_create,
    writeback_cell_delete,
    writeback_cell_detail,
    writeback_cell_edit,
    writeback_cell_list,
)

__all__ = [
    "olap_cube_list",
    "olap_cube_detail",
    "olap_cube_create",
    "olap_cube_edit",
    "olap_cube_delete",
    "olap_cube_refresh",
    "pivot_view_list",
    "pivot_view_detail",
    "pivot_view_create",
    "pivot_view_edit",
    "pivot_view_delete",
    "pivot_view_matrix",
    "what_if_scenario_list",
    "what_if_scenario_detail",
    "what_if_scenario_create",
    "what_if_scenario_edit",
    "what_if_scenario_delete",
    "what_if_scenario_simulate",
    "what_if_scenario_commit",
    "writeback_cell_list",
    "writeback_cell_detail",
    "writeback_cell_create",
    "writeback_cell_edit",
    "writeback_cell_delete",
]
