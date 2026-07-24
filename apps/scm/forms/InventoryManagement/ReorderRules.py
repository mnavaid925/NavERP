"""SCM 4.3 Inventory Management — ReorderRule form (4.7 safety-stock policy fields included)."""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import TenantUniqueMixin
from apps.scm.models import ReorderRule


class ReorderRuleForm(TenantUniqueMixin, TenantModelForm):
    """The rule plus its 4.7 safety-stock POLICY (the inputs a planner sets).

    The seven calculated columns — `avg_daily_demand`, `demand_std_dev`, `abc_class`, `xyz_class`,
    `computed_safety_stock`, `computed_reorder_point`, `last_calculated_at` — are deliberately absent:
    they are produced by `calculate()` and shown read-only, so a typed "computed" number can never
    masquerade as a calculated one.
    """

    class Meta:
        model = ReorderRule
        # item, location, seasonality_profile and demand_forecast all carry their own tenant, so the
        # base class scopes every dropdown here.
        fields = ["item", "location", "reorder_point", "safety_stock", "reorder_quantity",
                  "is_active",
                  # 4.7 safety-stock policy
                  "safety_stock_method", "service_level_pct", "lead_time_days",
                  "lead_time_variability_days", "review_period_days", "seasonality_profile",
                  "demand_forecast"]
