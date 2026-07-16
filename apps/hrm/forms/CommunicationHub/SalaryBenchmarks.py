"""HRM 3.27 Communication Hub — SalaryBenchmarks forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    JobGrade,
    SalaryBenchmark,
)
from apps.hrm.forms.CommunicationHub._helpers import _scope_currency


class SalaryBenchmarkForm(TenantModelForm):
    class Meta:
        model = SalaryBenchmark
        fields = ["job_grade", "designation", "source", "region", "currency",
                  "percentile_25", "percentile_50", "percentile_75", "percentile_90", "survey_date", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _scope_currency(self)
        if self.tenant is not None and "job_grade" in self.fields:
            self.fields["job_grade"].queryset = (
                JobGrade.objects.filter(tenant=self.tenant, is_active=True).order_by("level_order", "name"))

    def clean(self):
        cleaned = super().clean()
        # Percentiles should be non-negative and non-decreasing (P25 <= P50 <= P75 <= P90) when present.
        seq = [("percentile_25", "P25"), ("percentile_50", "P50"),
               ("percentile_75", "P75"), ("percentile_90", "P90")]
        prev_field, prev_val = None, None
        for field, label in seq:
            v = cleaned.get(field)
            if v is not None and v < 0:
                self.add_error(field, "Must be zero or greater.")
            elif v is not None and prev_val is not None and v < prev_val:
                self.add_error(field, f"{label} cannot be less than the lower percentile.")
            if v is not None:
                prev_field, prev_val = field, v
        return cleaned
