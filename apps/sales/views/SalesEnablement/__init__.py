"""Sales 8.9 — SalesEnablement views package re-exports."""
from apps.sales.views.SalesEnablement.CoachingScorecards import (
    coaching_scorecard_acknowledge,
    coaching_scorecard_create,
    coaching_scorecard_delete,
    coaching_scorecard_detail,
    coaching_scorecard_edit,
    coaching_scorecard_list,
)
from apps.sales.views.SalesEnablement.EnablementBoards import (
    sales_coaching_workbench,
    sales_competitive_intelligence_library,
    sales_enablement_content_hub,
    sales_playbook_board,
    sales_readiness_board,
)
from apps.sales.views.SalesEnablement.EnablementContents import (
    enablement_content_create,
    enablement_content_delete,
    enablement_content_detail,
    enablement_content_edit,
    enablement_content_list,
    enablement_content_share,
)
from apps.sales.views.SalesEnablement.SalesCertifications import (
    sales_certification_create,
    sales_certification_delete,
    sales_certification_detail,
    sales_certification_edit,
    sales_certification_list,
)
from apps.sales.views.SalesEnablement.SalesPlaybooks import (
    sales_playbook_create,
    sales_playbook_delete,
    sales_playbook_detail,
    sales_playbook_edit,
    sales_playbook_list,
)

__all__ = [
    # EnablementContent
    "enablement_content_list",
    "enablement_content_detail",
    "enablement_content_create",
    "enablement_content_edit",
    "enablement_content_delete",
    "enablement_content_share",
    # SalesPlaybook
    "sales_playbook_list",
    "sales_playbook_detail",
    "sales_playbook_create",
    "sales_playbook_edit",
    "sales_playbook_delete",
    # SalesCertification
    "sales_certification_list",
    "sales_certification_detail",
    "sales_certification_create",
    "sales_certification_edit",
    "sales_certification_delete",
    # CoachingScorecard
    "coaching_scorecard_list",
    "coaching_scorecard_detail",
    "coaching_scorecard_create",
    "coaching_scorecard_edit",
    "coaching_scorecard_delete",
    "coaching_scorecard_acknowledge",
    # Boards
    "sales_enablement_content_hub",
    "sales_playbook_board",
    "sales_readiness_board",
    "sales_coaching_workbench",
    "sales_competitive_intelligence_library",
]
