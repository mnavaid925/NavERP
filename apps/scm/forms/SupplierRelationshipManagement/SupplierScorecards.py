"""SCM 4.2 SRM — SupplierScorecard form."""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import _supplier_parties
from apps.scm.models import SupplierScorecard


class SupplierScorecardForm(TenantModelForm):
    class Meta:
        model = SupplierScorecard
        # `status`/`number` EXCLUDED (status advances via publish/archive; number auto). `overall_score`
        # and `grade` are derived. The four dimension scores ARE editable — a scorecard can be filled
        # by hand or, with `manual_override` off, auto-derived from 4.1 signals in the view.
        fields = [
            "party", "period_start", "period_end",
            "delivery_score", "quality_score", "price_score", "responsiveness_score",
            "manual_override", "notes",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "party" in self.fields:
            self.fields["party"].queryset = _supplier_parties(self.tenant)

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("period_start"), cleaned.get("period_end")
        if start and end and end < start:
            self.add_error("period_end", "The period end cannot be before its start.")
        return cleaned
