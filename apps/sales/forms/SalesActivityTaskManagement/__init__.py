"""Sales 8.8 — form re-exports. Adding a form WITHOUT adding it here is a bug (L36 §2a rule 1)."""
from .ActivityTypes import ActivityTypeForm
from .ActivityLogs import SELECTABLE_CAPTURE_SOURCES, ActivityLogForm
from .TaskTemplates import TaskTemplateForm, TaskTemplateStepForm
from .SalesPlanCycles import ActivityGoalForm, SalesPlanCycleForm

__all__ = [
    "ActivityTypeForm",
    "ActivityLogForm",
    "SELECTABLE_CAPTURE_SOURCES",
    "TaskTemplateForm",
    "TaskTemplateStepForm",
    "SalesPlanCycleForm",
    "ActivityGoalForm",
]