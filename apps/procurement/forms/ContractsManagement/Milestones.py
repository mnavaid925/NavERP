"""Procurement 6.8 Contract Management — ContractMilestone forms."""
from apps.procurement.forms._common import *  # noqa: F401,F403
from apps.procurement.forms._common import _reject_foreign
from apps.procurement.models import ContractMilestone


class ContractMilestoneForm(TenantModelForm):
    class Meta:
        model = ContractMilestone
        # EXCLUDED and why: ``number`` is auto; ``status``/``completed_*`` move through
        # the complete verb; ``contract`` comes from the URL.
        fields = ["kind", "title", "description", "due_date", "amount", "notes"]

    def clean(self):
        cleaned = super().clean()
        kind = cleaned.get("kind")
        if kind in ("payment", "penalty") and cleaned.get("amount") is None:
            self.add_error("amount",
                           f"A {kind} milestone needs its amount.")
        return cleaned
