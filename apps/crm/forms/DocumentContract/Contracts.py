"""CRM 1.9 Document & Contract Management — Contracts forms (split from apps/crm/forms.py)."""
from apps.crm.forms._common import *  # noqa: F401,F403
from apps.crm.models import (
    ContractDocument,
    SignerRecord,
)


class ContractDocumentForm(TenantModelForm):
    class Meta:
        model = ContractDocument
        # WARNING: status/current_version/body_snapshot are system-managed. body_snapshot is now
        # GENERATED from the linked template (contractdocument_generate) or captured as a
        # DocumentVersion — never hand-typed; status/current_version are owned by the signing flow +
        # version actions. Excluded so a member can't forge a "signed" contract or inject HTML via POST.
        fields = ["name", "template", "opportunity", "account", "expires_at", "owner"]


class SignerRecordForm(TenantModelForm):
    """Inline on the ContractDocument detail page; tenant/contract/token set in the view."""

    class Meta:
        model = SignerRecord
        fields = ["signer_party", "signer_name", "signer_email"]  # order auto-assigned in the view
