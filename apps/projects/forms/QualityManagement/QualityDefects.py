"""Projects 7.6 — QualityDefect forms.

``QualityDefectForm`` carries the punch-list entry data. ``project_issue``, ``status``,
``root_cause``, ``resolution_note``, ``resolved_by``, ``resolved_at`` and ``created_by`` are all
OFF it: the bridge to the issue register is the POST-only ``qdf_raise_issue`` verb and the
resolution is ``qdf_resolve``'s — so the evidence trail keeps its stamps and the defect register
never becomes a second issue log (Ruling 2). ``lessons_learned`` IS on the form: like 7.5's risk
register, the takeaway is recorded by the people who disposition the item, and the repository it
feeds is 7.10's.

``DefectResolutionForm`` is ``qdf_resolve``'s body — a plain ``forms.Form`` (not a ModelForm) so
the root cause and the resolution note are written by the verb that also stamps
``resolved_by``/``resolved_at``, never by a generic edit.

``TenantUniqueMixin`` is mixed in FIRST: ``QualityDefect.clean()`` compares three chosen FKs'
project against ``self.project``, and the mixin is what stamps ``instance.tenant`` before
``full_clean()`` runs on CREATE (without it every create is falsely rejected as cross-tenant).
"""
from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.projects.models import QualityDefect


class QualityDefectForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = QualityDefect
        fields = ["project", "wbs_node", "quality_plan", "inspection", "title", "description",
                  "defect_category", "severity", "disposition", "owner", "identified_date",
                  "due_date", "lessons_learned"]

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned,
                        ["project", "wbs_node", "quality_plan", "inspection", "owner"])
        return cleaned


class DefectResolutionForm(forms.Form):
    """The ``qdf_resolve`` verb's body: what actually caused the defect and what was done about
    it. The note is required — a resolution without a recorded action is not a resolution."""

    root_cause = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        help_text="What actually caused this defect — feeds the improvement page's trend lens.")
    resolution_note = forms.CharField(
        required=True, widget=forms.Textarea(attrs={"class": "form-textarea", "rows": 3}),
        help_text="What was done to disposition this defect.")
