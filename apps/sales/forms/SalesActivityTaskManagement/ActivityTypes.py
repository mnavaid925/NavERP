"""Sales 8.8 — the `ActivityType` form (`ATY-`).

Excluded from ``Meta.fields``, with the reason for each:

* ``tenant`` — set by ``TenantUniqueMixin`` from the view's ``request.tenant``, never from input.
* ``number`` — ``editable=False`` on ``TenantNumbered``; allocated by ``next_number`` (L22).
* ``created_at`` / ``updated_at`` — ``auto_now*`` stamps.

**The one interesting behaviour here is `__init__`.** `default_outcome` is a CALL-only concept — the
model refuses it on any other kind (G1) — so the field is *disabled* whenever the type is not a
call. Disabled rather than hidden, so the reason stays visible on the page. A disabled field takes
its value from the INSTANCE and never from the POST body, which is what stops a crafted request
flipping ``kind`` back to ``call`` and smuggling an outcome through that the model would otherwise
have refused. The check reads the POST body on a bound form and ``initial`` otherwise, so it holds on
the very first submit of a create form and on a re-post of an edit form — the two moments a static,
render-time check would miss.

The model's own ``clean()`` is still the authority: this is presentation, not enforcement.
"""
from django import forms

from apps.sales.forms._common import TenantModelForm, TenantUniqueMixin
from apps.sales.models.SalesActivityTaskManagement.ActivityTypes import (
    MAX_DEFAULT_DURATION_SECONDS,
    ActivityType,
)


class ActivityTypeForm(TenantUniqueMixin, TenantModelForm):
    """Create or edit one entry in the tenant's activity-type catalogue."""

    class Meta:
        model = ActivityType
        # Excluded, with the reason for each — see the module docstring.
        fields = [
            "name",
            "description",
            "kind",
            "default_outcome",
            "default_duration_seconds",
            "default_priority",
            "requires_opportunity",
            "is_billable",
            "is_active",
            "display_order",
        ]
        widgets = {
            "description": forms.Textarea(attrs={
                "class": "form-textarea",
                "rows": 3,
                "placeholder": "When a rep should reach for this type rather than a plain call...",
            }),
            "default_duration_seconds": forms.NumberInput(attrs={
                "class": "form-input",
                "min": "0",
                "max": str(MAX_DEFAULT_DURATION_SECONDS),
                "step": "30",
            }),
            "display_order": forms.NumberInput(attrs={
                "class": "form-input",
                "min": "0",
                "step": "10",
            }),
        }
        help_texts = {
            "kind": (
                "Which CRM 1.5 channel this type describes. The interaction itself is logged as a "
                "crm.CommunicationLog; this entry names the kind of activity it is."
            ),
            "default_outcome": (
                "Pre-filled call outcome. Only a call has one — the field switches off for every "
                "other kind, and the model refuses the combination."
            ),
            "default_duration_seconds": (
                f"Pre-filled length in seconds, up to {MAX_DEFAULT_DURATION_SECONDS} (24 hours). "
                "It is also what a generated task's planned time is measured in."
            ),
            "requires_opportunity": (
                "Log activities of this type must name the opportunity they advance. Leave off for "
                "housekeeping activity nobody books to a deal."
            ),
            "display_order": "Lower numbers appear first in the register. Default 100.",
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        # An UNKNOWN kind means nothing has been chosen yet. A fresh create form's model default is
        # "call", so the outcome field must stay live there — locking it on an unanswered question
        # would hide a field the author is about to be allowed to fill in.
        if self._selected_kind() not in (None, "", "call"):
            self._lock_outcome()

    def _selected_kind(self):
        """What the author has chosen (or has POSTed) as ``kind``, or ``None`` if undecided.

        Read from the POST body on a bound form and from ``initial`` otherwise, so the lock holds on
        the first post of a create form and on a re-post of an edit form.
        """
        if self.is_bound:
            return self.data.get("kind") or None
        return self.initial.get("kind") or None

    def _lock_outcome(self):
        """Disable ``default_outcome`` and say why on the field itself."""
        outcome = self.fields["default_outcome"]
        outcome.disabled = True
        outcome.required = False
        outcome.help_text = (
            "Only a call has an outcome, so this field is off. Pick the Call kind to set a default."
        )