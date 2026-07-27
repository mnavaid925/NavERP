"""SCM 4.8 Manufacturing — ProductionTimeLog form."""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import TenantUniqueMixin, _employee_parties
from apps.scm.models import ProductionTimeLog, WorkOrder


class ProductionTimeLogForm(TenantUniqueMixin, TenantModelForm):
    """One booked shop-floor interval.

    EXCLUDES `number` (auto) and `duration_minutes` (derived from the interval in `save()` — typing
    it would let the booked duration disagree with its own start/end). `work_order` and
    `work_center` carry their own tenant so the base class scopes them; `operator` is narrowed to
    parties holding the `employee` role.

    The work-order dropdown offers only OPEN runs. A log against a draft run has nothing to record,
    and one against a closed run is the freeze the model docstring describes — the view enforces the
    same rule for edits, since a run can close after the form was rendered.
    """

    class Meta:
        model = ProductionTimeLog
        fields = ["work_order", "work_center", "operation", "entry_type", "operator",
                  "started_at", "ended_at", "quantity_completed", "quantity_scrapped",
                  "downtime_reason", "notes"]
        widgets = {
            "started_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "ended_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "operator" in self.fields:
            self.fields["operator"].queryset = _employee_parties(self.tenant)
        if "work_order" in self.fields:
            open_runs = self.fields["work_order"].queryset.filter(
                status__in=WorkOrder.OPEN_STATUSES)
            # Keep the row's own work order selectable while editing even if the run has since moved
            # on — otherwise the bound form would fail validation on a field the user never touched.
            current_id = getattr(self.instance, "work_order_id", None)
            if current_id is not None:
                open_runs = self.fields["work_order"].queryset.filter(
                    Q(status__in=WorkOrder.OPEN_STATUSES) | Q(pk=current_id))
            self.fields["work_order"].queryset = open_runs.select_related("item")
