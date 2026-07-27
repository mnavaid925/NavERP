"""SCM 4.8 Manufacturing — WorkCenter form."""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import TenantUniqueMixin, _employee_parties
from apps.scm.models import WorkCenter


class WorkCenterForm(TenantUniqueMixin, TenantModelForm):
    """The capacity + rate master.

    EXCLUDES `number` (auto). `location` and `org_unit` carry their own tenant, so the base class
    scopes those dropdowns; `supervisor` is narrowed further to parties actually holding the
    `employee` role. Nothing here is derived — load, utilization and the OEE chip are all computed
    from work orders and time logs at read time, so there is no result field to keep off the form.
    """

    class Meta:
        model = WorkCenter
        fields = ["code", "name", "center_type", "location", "org_unit", "supervisor",
                  "capacity_hours_per_day", "efficiency_pct", "setup_minutes",
                  "machine_cost_per_hour", "labor_cost_per_hour", "is_active", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "supervisor" in self.fields:
            self.fields["supervisor"].queryset = _employee_parties(self.tenant)
