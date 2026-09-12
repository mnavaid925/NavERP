"""Projects 7.7 — Requirement forms + the two companion forms its verbs bind.

``status``, ``rejection_reason``, the approval pair and the verification pair are OFF the model
form: the lifecycle is verb-driven (submit / approve / reject / implement / verify), so the register
keeps its evidence stamps. ``RequirementRejectionForm`` is the ``req_reject`` verb's mandatory
reason, and ``RequirementVerificationForm`` is the ``req_verify`` verb's optional note — both are
plain ``forms.Form``s so the text is written by the verb that also stamps the evidence columns,
never by a generic edit.

``TenantUniqueMixin`` is mixed in FIRST: ``Requirement.clean()`` compares two chosen FKs' project
against ``self.project``, and the mixin is what stamps ``instance.tenant`` before ``full_clean()``
runs on CREATE.
"""
from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.projects.models import Requirement


class RequirementForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = Requirement
        fields = ["project", "parent", "wbs_node", "title", "description", "requirement_type",
                  "elicitation_method", "elicitation_note", "source_party", "priority",
                  "acceptance_criteria", "version", "verification_method", "owner",
                  "requested_by"]

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["project", "parent", "wbs_node", "source_party", "owner",
                                        "requested_by"])
        return cleaned


class RequirementRejectionForm(forms.Form):
    """The ``req_reject`` verb's body: a rejection without a reason is not actionable."""

    reason = forms.CharField(
        required=True, widget=forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        help_text="Why the requirement was rejected. Stored on the register row.")


class RequirementVerificationForm(forms.Form):
    """The ``req_verify`` verb's body: how the acceptance criteria were actually confirmed."""

    note = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        help_text="How the acceptance criteria were confirmed (optional).")
