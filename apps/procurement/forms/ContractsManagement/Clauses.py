"""Procurement 6.8 Contract Management — ContractClause forms."""
from apps.procurement.forms._common import *  # noqa: F401,F403
from apps.procurement.models import ContractClause


class ContractClauseForm(TenantModelForm):
    """One library clause. Legal language is admin-gated in the views; the form
    itself stays a plain header form."""

    class Meta:
        model = ContractClause
        fields = ["title", "category", "body", "version",
                  "is_pre_approved", "is_active", "notes"]
        widgets = {"body": forms.Textarea(attrs={"rows": 6})}
