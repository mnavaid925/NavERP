"""Sales 8.9 — URLs for EnablementBoards."""
from django.urls import path

from apps.sales.views.SalesEnablement.EnablementBoards import (
    sales_coaching_workbench,
    sales_competitive_intelligence_library,
    sales_enablement_content_hub,
    sales_playbook_board,
    sales_readiness_board,
)

urlpatterns = [
    path("enablement/hub/", sales_enablement_content_hub, name="enablement_content_hub"),
    path("enablement/playbooks/board/", sales_playbook_board, name="sales_playbook_board"),
    path("enablement/readiness/", sales_readiness_board, name="sales_readiness_board"),
    path("enablement/coaching/workbench/", sales_coaching_workbench, name="sales_coaching_workbench"),
    path("enablement/competitive-intelligence/", sales_competitive_intelligence_library, name="sales_competitive_intelligence_library"),
]
