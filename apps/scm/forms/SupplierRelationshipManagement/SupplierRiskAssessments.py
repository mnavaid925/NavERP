"""SCM 4.2 SRM — SupplierRiskAssessment form."""
from apps.scm.forms._common import *  # noqa: F401,F403
from apps.scm.forms._common import _supplier_parties
from apps.scm.models import SupplierRiskAssessment


class SupplierRiskAssessmentForm(TenantModelForm):
    class Meta:
        model = SupplierRiskAssessment
        # `status` EXCLUDED (submit/review actions). `risk_level`/`risk_index` derived; `assessed_by` set
        # to request.user on create. The four factor scores drive the derived level.
        fields = [
            "party", "assessment_date",
            "financial_score", "geopolitical_score", "compliance_score", "operational_score",
            "mitigation_plan", "next_review_date", "notes",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "party" in self.fields:
            self.fields["party"].queryset = _supplier_parties(self.tenant)
