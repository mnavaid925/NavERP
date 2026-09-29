"""Sales 8.6 Order Management — the order-validation, hold, amendment and revenue forms.

Every form here follows the same two rules the models do:

* **No frozen evidence is authorable.** ``evaluation_snapshot``, ``impact_snapshot`` and
  ``decision_note`` are off every form and are written by their own named verb (L22). A
  justification a later form edit could rewrite is not evidence of why somebody said yes.
* **Every FK queryset is narrowed to ``tenant=self.tenant``**, so a form can only ever be
  pointed at this workspace's own rows.

The two child forms (`OrderAmendmentLineForm`, `PerformanceObligationForm`) deliberately EXCLUDE
their parent FK: it is set by the parent view, never taken from user input.
"""
from .OrderAmendments import (
    OrderAmendmentDecisionForm,
    OrderAmendmentForm,
    OrderAmendmentLineForm,
)
from .OrderHolds import OrderHoldActionForm, OrderHoldForm
from .OrderValidationRules import OrderValidationRuleForm
from .RevenueSchedules import PerformanceObligationForm, RevenueScheduleForm

__all__ = [
    "OrderValidationRuleForm",
    "OrderHoldForm",
    "OrderHoldActionForm",
    "OrderAmendmentForm",
    "OrderAmendmentLineForm",
    "OrderAmendmentDecisionForm",
    "RevenueScheduleForm",
    "PerformanceObligationForm",
]
