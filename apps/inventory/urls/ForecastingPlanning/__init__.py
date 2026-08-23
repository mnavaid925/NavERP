from .PlanningBoard import urlpatterns as _fp_board
from .StockLevelPlans import urlpatterns as _fp_slp

urlpatterns = [
    *_fp_slp,
    *_fp_board,
]
