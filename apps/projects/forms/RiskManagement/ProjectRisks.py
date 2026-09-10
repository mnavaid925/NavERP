"""Projects 7.5 — ProjectRisk form + the close verb's small companion form.

``status``, ``closed_at`` and ``created_by`` are OFF the model form: the lifecycle is verb-driven
(realize / close / reopen), so the register keeps its evidence stamps. ``RiskClosureForm`` is the
``rsk_close`` verb's optional capture — a plain ``forms.Form`` (not a ModelForm) so the closure note
is written by the verb that also stamps ``closed_at``, never by a generic edit.

``TenantUniqueMixin`` is mixed in FIRST: ``ProjectRisk.clean()`` compares two chosen FKs' project
against ``self.project``, and the mixin is what stamps ``instance.tenant`` before ``full_clean()``
runs on CREATE (without it every create is falsely rejected as cross-tenant).
"""
from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.projects.models import ProjectRisk


class ProjectRiskForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ProjectRisk
        fields = ["project", "wbs_node", "title", "description", "cause", "effect", "category",
                  "risk_type", "probability", "impact", "cost_impact", "schedule_impact_days",
                  "response_strategy", "response_note", "trigger", "contingency_plan", "owner",
                  "identified_by", "identified_date", "review_date", "residual_probability",
                  "residual_impact", "contingency_account", "lessons_learned"]

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["project", "wbs_node", "owner", "identified_by",
                                        "contingency_account"])
        return cleaned


class RiskClosureForm(forms.Form):
    """The ``rsk_close`` verb's body: the lesson the closed risk leaves behind (optional)."""

    lessons_learned = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 3}),
        help_text="What this risk taught the project. Feeds the monitoring page's lessons lens.")
