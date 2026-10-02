"""Sales 8.8 — the `ActivityLog` form (`SAL-`).

Excluded from ``Meta.fields``, with the reason for each:

* ``tenant`` — set by ``TenantUniqueMixin`` from the view's ``request.tenant``, never from input.
* ``number`` — ``editable=False`` on ``TenantNumbered``; allocated by ``next_number`` (L22).
* **Every frozen evidence field** — ``occurred_on``, ``planned_minutes``, ``opened_at``,
  ``open_count``, ``clicked_at``, ``click_count``, ``replied_at``. All are ``editable=False``, so
  Django excludes them from the form automatically; naming them here would be redundant. They are
  written only by the create view and the three POST verbs. This is **L20** in its purest form: a
  rep must not be able to type "opened 47 times" into an edit form, because a rep *is* the one party
  with an incentive to do so.
* ``created_at`` / ``updated_at`` — ``auto_now*`` stamps.

**`Meta.fields` is deliberately short.** There is no ``channel``, no ``subject``, no ``occurred_at``,
no ``duration_seconds`` — the form offers the author only the *attribution*, because the interaction
was already recorded on `crm.CommunicationLog` and 8.8 does not get a second set of controls for it
(L36).

**`capture_source` and `is_auto_captured` are kept IN AGREEMENT by the form, not only by the model.**
The model raises a non-field error (G3) and that is the authority; this form pre-writes the checkbox
so the common case never has to round-trip through an error. It is set on POST and cleared on an
unbound render, so an edit form never shows a stale tick against a manual source.

**`communication_log` is narrowed to logs that have no sales layer yet.** Offering an
already-attributed log would let the second POST lose to a unique constraint and surface as a 500 —
the exact failure L49 describes for `LicenseAssignment`.
"""
from django import forms

from apps.sales.forms._common import (
    TenantModelForm,
    TenantUniqueMixin,
    _reject_foreign,
    tenant_users,
)
from apps.sales.models.SalesActivityTaskManagement.ActivityLogs import (
    AUTO_CAPTURE_SOURCES,
    ActivityLog,
)

#: The auto-capture sources a normal author can pick. `import` is left OUT deliberately: it is a
#: bulk/technical source, and a rep filling in this form by hand claiming "this row was imported" is
#: the provenance lie the whole frozen-evidence design exists to prevent.
SELECTABLE_CAPTURE_SOURCES = [
    ("manual", "Manual"),
    ("call_log", "Call Log"),
    ("bcc_dropbox", "BCC Dropbox"),
    ("calendar_sync", "Calendar Sync"),
    ("template_task", "Template Task"),
    ("plan_goal", "Plan Goal"),
]


class ActivityLogForm(TenantUniqueMixin, TenantModelForm):
    """Attach the sales attribution to one already-logged ``crm.CommunicationLog``."""

    class Meta:
        model = ActivityLog
        # Excluded, with the reason for each — see the module docstring. NOTE: no channel / subject /
        # duration / outcome field appears here, and none may be added — they belong to CRM 1.5.
        fields = [
            "communication_log",
            "activity_type",
            "owner",
            "opportunity",
            "account",
            "territory",
            "capture_source",
            "is_auto_captured",
            "next_best_action",
            "next_best_action_due",
        ]
        widgets = {
            "next_best_action": forms.TextInput(attrs={
                "class": "form-input",
                "placeholder": "Send the revised pricing to the economic buyer",
            }),
            "next_best_action_due": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
        }
        help_texts = {
            "communication_log": (
                "The CRM 1.5 interaction this sales activity attributes. Only interactions that have "
                "no sales layer yet are offered."
            ),
            "activity_type": (
                "Which catalogue entry this is. Leave blank for an interaction with no matching type."
            ),
            "is_auto_captured": (
                "Ticked when the interaction reached this page by itself. Keep it in step with the "
                "capture source — the model refuses the two disagreeing."
            ),
            "next_best_action": (
                "What this activity implies comes next. Left blank, the suggestion board proposes "
                "one from its own rules instead."
            ),
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        self.fields["capture_source"].choices = SELECTABLE_CAPTURE_SOURCES
        self._sync_auto_flag()

    def _sync_auto_flag(self):
        """Keep the checkbox honest about the chosen source, on POST and on a fresh render.

        On a bound form the posted source decides, so the checkbox can never be left disagreeing with
        a field the author just changed. On an unbound form the checkbox is cleared to match the
        rendered source: an edit form shows the STORED source, and a stored `manual` row must not
        arrive with the tick already on.
        """
        if self.is_bound:
            source = self.data.get("capture_source")
            self.initial["is_auto_captured"] = source in AUTO_CAPTURE_SOURCES
        else:
            source = self.initial.get("capture_source") or self.instance.capture_source or "manual"
            self.initial["is_auto_captured"] = source in AUTO_CAPTURE_SOURCES

    def clean(self):
        cleaned = super().clean()
        tenant_id = getattr(self.tenant, "pk", self.tenant)
        if tenant_id is None:
            self.add_error(None, "A tenant workspace is required.")
        elif self.instance.pk and self.instance.tenant_id != tenant_id:
            self.add_error(None, "The sales activity must belong to this workspace.")
        # Belt and braces on top of every narrowed queryset: the queryset alone rejects a cross-tenant
        # pk with "Select a valid choice", and this says WHY in the author's terms.
        _reject_foreign(self, cleaned, ["communication_log", "activity_type", "owner",
                                        "opportunity", "account", "territory"])
        return cleaned