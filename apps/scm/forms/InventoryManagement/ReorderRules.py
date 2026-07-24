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

    #: Fields that ARE the buying decision — 4.3's reorder alerts and suggested quantities read
    #: these two, so writing them is the same privileged act `safety_stock_apply` gates on tenant
    #: admin. Without this, a non-admin could read the calculated numbers off the safety-stock
    #: report and type them straight in here, one click away, defeating that gate entirely.
    ADMIN_ONLY_FIELDS = ("safety_stock", "reorder_point")

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

    def __init__(self, *args, is_tenant_admin=False, **kwargs):
        super().__init__(*args, **kwargs)
        if not is_tenant_admin:
            for name in self.ADMIN_ONLY_FIELDS:
                if name in self.fields:
                    # `disabled` (not readonly): Django ignores the SUBMITTED value entirely and
                    # keeps the instance's, so a crafted POST cannot set it either.
                    self.fields[name].disabled = True
                    self.fields[name].help_text = (
                        "Set by a workspace admin, or by applying a calculated policy on the Safety "
                        "Stock page.")
        # `demand_forecast` sizes THIS rule's buffer from a forecast's error — it has to be a
        # forecast for the same item, or the rule would be sized from a different product's plan.
        if "demand_forecast" in self.fields and self.instance.item_id:
            self.fields["demand_forecast"].queryset = (
                self.fields["demand_forecast"].queryset.filter(item_id=self.instance.item_id))
