"""Projects 7.7 — ScopeVerification form + the companion form its acceptance verbs bind.

``acceptance_status``, ``decision_note`` and the ``accepted_by``/``accepted_at`` pair are OFF the
model form: the acceptance gate is a formal workflow (accept / reject / waive) and the verb that
decides also stamps the evidence.

``TenantUniqueMixin`` is mixed in FIRST because ``ScopeVerification.clean()`` compares the chosen
work package's and the chosen requirement's project against ``self.project``.
"""
from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.projects.models import ScopeVerification


class ScopeVerificationForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ScopeVerification
        fields = ["project", "wbs_node", "requirement", "deliverable", "method", "result",
                  "inspected_by", "inspection_date", "findings"]

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["project", "wbs_node", "requirement", "inspected_by"])
        return cleaned


class VerificationDecisionForm(forms.Form):
    """The ``svr_accept`` / ``svr_reject`` / ``svr_waive`` verbs' body.

    The note is optional at the form level because an acceptance often needs none; the
    ``svr_reject`` view additionally refuses a blank one, because a rejection without a written
    reason is not actionable.
    """

    note = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        help_text="The acceptance decision's reasoning (required when rejecting).")
