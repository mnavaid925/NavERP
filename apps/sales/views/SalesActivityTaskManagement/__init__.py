"""Sales 8.8 — view re-exports. Adding a view WITHOUT adding it here is a bug (L36 §2a rule 1).

The three entity modules plus the boards module. ``Boards`` is imported last so the boards' names
cannot shadow an entity view of the same name if one is ever added.
"""
from .ActivityTypes import (
    activity_type_create,
    activity_type_delete,
    activity_type_detail,
    activity_type_edit,
    activity_type_list,
)
from .ActivityLogs import (
    activity_log_create,
    activity_log_delete,
    activity_log_detail,
    activity_log_edit,
    activity_log_list,
    activity_log_mark_clicked,
    activity_log_mark_opened,
    activity_log_mark_replied,
)
from .TaskTemplates import (
    task_template_create,
    task_template_delete,
    task_template_detail,
    task_template_edit,
    task_template_generate,
    task_template_list,
)
from .SalesPlanCycles import (
    sales_plan_cycle_create,
    sales_plan_cycle_delete,
    sales_plan_cycle_detail,
    sales_plan_cycle_edit,
    sales_plan_cycle_list,
    sales_plan_cycle_toggle,
    sales_plan_goal_add,
    sales_plan_goal_delete,
)
from .Boards import (
    sales_activity_plan,
    sales_email_engagement,
    sales_next_best_actions,
)

__all__ = [
    "activity_type_list", "activity_type_create", "activity_type_detail",
    "activity_type_edit", "activity_type_delete",
    "activity_log_list", "activity_log_create", "activity_log_detail",
    "activity_log_edit", "activity_log_delete",
    "activity_log_mark_opened", "activity_log_mark_clicked", "activity_log_mark_replied",
    "task_template_list", "task_template_create", "task_template_detail",
    "task_template_edit", "task_template_delete", "task_template_generate",
    "sales_plan_cycle_list", "sales_plan_cycle_create", "sales_plan_cycle_detail",
    "sales_plan_cycle_edit", "sales_plan_cycle_delete", "sales_plan_cycle_toggle",
    "sales_plan_goal_add", "sales_plan_goal_delete",
    "sales_activity_plan", "sales_next_best_actions", "sales_email_engagement",
]