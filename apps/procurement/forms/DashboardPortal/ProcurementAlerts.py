"""Procurement 6.1 User Dashboard & Portal — ProcurementAlert form."""
from apps.procurement.forms._common import *  # noqa: F401,F403
from apps.procurement.forms._common import _reject_foreign
from apps.procurement.models import ProcurementAlert


class ProcurementAlertForm(TenantModelForm):
    """Raise / edit an alert in the Task & Alert Center.

    ``status`` and the whole acknowledgement/resolution stamp are NOT form fields: they advance
    through the Acknowledge / Resolve actions, never by hand-editing a row into "resolved" (the
    scm requisition ``status``-excluded rule). ``assigned_to`` targets ``User``, whose nullable
    ``tenant`` makes it auto-scoped by TenantModelForm — and the crafted-POST re-check below keeps
    a hand-added option from assigning work to another workspace's member.
    """

    class Meta:
        model = ProcurementAlert
        # created_by/acknowledged_*/resolved_*/raised_at are stamped, not asked.
        fields = ["kind", "severity", "title", "message", "link_url", "due_at", "assigned_to"]

    def clean(self):
        cleaned = super().clean()
        _reject_foreign(self, cleaned, ["assigned_to"])
        return cleaned
