"""Procurement 6.8 Contract Management — ContractClause model.

**Contract Authoring & Templating** bullet: "Tools to draft contracts using standard,
pre-approved legal clauses." This is that library: one tenant-scoped row per reusable
clause, authored once by the people who own legal language, then SELECTED onto any
number of supplier agreements via ``Contracts.py::ContractClauseLink`` (with a
per-contract negotiated override when the deal deviates from the standard wording).

Plain configuration posture (the ApprovalRoutingRule ruling): the row is read by the
authoring surface, never referenced as a document of record, so it carries no number.

**Ownership (L29/L36):** the agreement itself is ``scm.SupplierContract`` (SCM 4.2/4.12).
This sub-module authors, signs and tracks AROUND that spine and never re-declares it.
"""
from apps.procurement.models._base import *  # noqa: F401,F403


class ContractClause(TenantOwned):
    """One pre-approved legal clause in the tenant's authoring library."""

    CATEGORY_CHOICES = [
        ("legal", "Legal & Liability"),
        ("payment", "Payment Terms"),
        ("delivery", "Delivery & Acceptance"),
        ("confidentiality", "Confidentiality"),
        ("termination", "Termination"),
        ("compliance", "Compliance"),
        ("other", "Other"),
    ]

    title = models.CharField(max_length=200)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="other")
    body = models.TextField(
        help_text="The standard wording inserted into drafted contracts")
    version = models.CharField(
        max_length=20, blank=True,
        help_text="Legal revision tag, e.g. 'v2.1' — informational only")
    is_pre_approved = models.BooleanField(
        default=True,
        help_text="Signed off by legal; unapproved clauses render flagged on the contract page")
    is_active = models.BooleanField(default=True)
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["category", "title", "id"]
        indexes = [
            models.Index(fields=["tenant", "is_active"], name="prc_ccl_tnt_active_idx"),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_category_display()})"
