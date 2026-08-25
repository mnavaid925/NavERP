"""Procurement 6.8 Contract Management — clause selection + e-signature models.

Two children of the SCM-owned agreement spine:

* ``ContractClauseLink`` — **Contract Authoring & Templating**: which library clauses
  were drafted into this agreement, in section order, with an optional negotiated
  override when the deal deviates from the standard wording.
* ``ContractSigner`` — **E-Signature Integration**: one row per signer (internal
  stakeholder or supplier contact), each holding an unguessable bearer token that
  gates the PUBLIC sign page exactly like crm 1.9's SignerRecord flow.

**Ownership (L29/L36):** both hang off ``scm.SupplierContract`` by FK — the spine's
own lifecycle verbs (activate/renew/terminate) stay scm's; this layer adds the
authoring and signature surface around them. Signature completeness is DERIVED
(``all_signed``), never stored back onto the spine.
"""
import secrets

from apps.procurement.models._base import *  # noqa: F401,F403


class ContractClauseLink(models.Model):
    """One library clause drafted into one supplier agreement.

    No tenant column of its own — tenancy resolves through the contract (the same
    child-row posture as RequisitionAmendmentLine / EventCriterion).
    """

    contract = models.ForeignKey(
        "scm.SupplierContract", on_delete=models.CASCADE,
        related_name="procurement_clause_links")
    clause = models.ForeignKey(
        "procurement.ContractClause", on_delete=models.PROTECT,
        related_name="procurement_clause_links")
    section_order = models.PositiveSmallIntegerField(
        default=1, help_text="Position of this clause within the drafted document")
    custom_text = models.TextField(
        blank=True,
        help_text="Negotiated wording replacing the standard body for THIS agreement")

    class Meta:
        ordering = ["section_order", "id"]
        unique_together = ("contract", "clause")

    @property
    def effective_text(self):
        """The words in force: the negotiation when there is one, standard body otherwise."""
        return self.custom_text or self.clause.body

    def clean(self):
        if (self.contract_id and self.clause_id
                and self.clause.tenant_id != self.contract.tenant_id):
            raise ValidationError(
                {"clause": "That clause belongs to another workspace."})

    def __str__(self):
        return f"{self.contract.number} §{self.section_order}: {self.clause.title}"


class ContractSigner(TenantOwned):
    """One signature slot on a supplier agreement (**E-Signature Integration**).

    The 32-byte URL-safe ``token`` is the bearer credential for the public sign page
    (`procurement:contract_sign_page`) — no login; whoever holds the token signs as
    this row. Completion is derived on the contract page from ``all_signed``; nothing
    is written back to the spine.
    """

    ROLE_CHOICES = [
        ("internal", "Internal stakeholder"),
        ("supplier", "Supplier representative"),
    ]

    contract = models.ForeignKey(
        "scm.SupplierContract", on_delete=models.CASCADE,
        related_name="procurement_signers")
    signer_party = models.ForeignKey(
        "core.Party", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="procurement_contract_signers",
        help_text="The supplier identity signing (blank for internal staff)")
    signer_name = models.CharField(max_length=255)
    signer_email = models.EmailField()
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="internal")
    order = models.PositiveSmallIntegerField(default=1)
    token = models.CharField(max_length=64, unique=True, editable=False)

    viewed_at = models.DateTimeField(null=True, blank=True, editable=False)
    signed_at = models.DateTimeField(null=True, blank=True, editable=False)
    declined_at = models.DateTimeField(null=True, blank=True, editable=False)
    ip_address = models.GenericIPAddressField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["order", "id"]

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(32)
        return super().save(*args, **kwargs)

    @property
    def has_responded(self):
        return self.signed_at is not None or self.declined_at is not None

    def __str__(self):
        return f"{self.signer_name} → {self.contract.number}"
