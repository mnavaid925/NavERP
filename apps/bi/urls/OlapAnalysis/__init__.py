from apps.bi.urls.OlapAnalysis.OlapCubes import (
    urlpatterns as cube_urls,
)
from apps.bi.urls.OlapAnalysis.PivotViews import (
    urlpatterns as pivot_urls,
)
from apps.bi.urls.OlapAnalysis.WhatIfScenarios import (
    urlpatterns as scenario_urls,
)
from apps.bi.urls.OlapAnalysis.WritebackCells import (
    urlpatterns as writeback_cell_urls,
)

urlpatterns = cube_urls + pivot_urls + scenario_urls + writeback_cell_urls
