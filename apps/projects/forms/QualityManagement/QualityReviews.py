"""Projects 7.6 — QualityReview form.

``status``, ``closed_at`` and ``created_by`` are OFF the model form: the lifecycle is verb-driven
(report / close), so the review keeps its evidence stamps. The improvement block
(``improvement_action`` / ``improvement_owner`` / ``improvement_due_date`` / ``improvement_status``)
IS on the form — it is planning data the reviewer records, not a verb-written stamp.

``TenantUniqueMixin`` is mixed in FIRST: ``QualityReview.clean()`` compares two chosen FKs' project
against ``self.project``, and the mixin is what stamps ``instance.tenant`` before ``full_clean()``
runs on CREATE (without it every create is falsely rejected as cross-tenant).
"""
from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.projects.models import QualityReview


class QualityReviewForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = QualityReview
        fields = ["project", "wbs_node", "quality_plan", "title", "scope", "review_type",
                  "checklist", "findings", "reviewer", "review_date", "maturity_score",
                  "improvement_action", "improvement_owner", "improvement_due_date",
                  "improvement_status"]

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned,
                        ["project", "wbs_node", "quality_plan", "reviewer", "improvement_owner"])
        return cleaned
