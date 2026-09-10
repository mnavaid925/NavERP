"""Projects 7.6 — QualityPlan form.

``status``, ``approved_by``, ``approved_at`` and ``created_by`` are OFF the model form: the
lifecycle is verb-driven (approve / supersede), so the plan keeps its evidence stamps. The approver
and the moment are written by ``qpl_approve``, never by a generic edit.

``TenantUniqueMixin`` is mixed in FIRST: ``QualityPlan.clean()`` compares two chosen FKs' project
against ``self.project``, and the mixin is what stamps ``instance.tenant`` before ``full_clean()``
runs on CREATE (without it every create is falsely rejected as cross-tenant).
"""
from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.projects.models import QualityPlan


class QualityPlanForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = QualityPlan
        fields = ["project", "wbs_node", "source_risk", "title", "description",
                  "acceptance_criteria", "verification_method", "standard_reference",
                  "regulatory_requirement", "owner", "planned_review_date"]

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["project", "wbs_node", "source_risk", "owner"])
        return cleaned
