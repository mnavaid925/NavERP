"""Projects 7.7 — ScopeItem form + the companion form its lifecycle verbs bind.

``status``, ``outcome`` and ``closed_at`` are OFF the model form: the boundary registry moves
open → validated → realized / retired through the audited verbs, and the verb that writes the
outcome also stamps ``closed_at`` in the same request.

``TenantUniqueMixin`` is mixed in FIRST because ``ScopeItem.clean()`` compares the chosen
requirement's project against ``self.project``.
"""
from apps.projects.forms._common import *  # noqa: F401,F403
from apps.projects.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.projects.models import ScopeItem


class ScopeItemForm(TenantUniqueMixin, TenantModelForm):
    class Meta:
        model = ScopeItem
        fields = ["project", "requirement", "item_type", "statement", "description", "impact_area",
                  "owner", "identified_date", "review_date"]

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["project", "requirement", "owner"])
        return cleaned


class ScopeItemOutcomeForm(forms.Form):
    """The ``sci_realize`` / ``sci_retire`` verbs' body: what actually happened to the item."""

    outcome = forms.CharField(
        required=True, widget=forms.Textarea(attrs={"rows": 3, "class": "form-textarea"}),
        help_text="What happened — the assumption held, the constraint bit, the item is retired.")
