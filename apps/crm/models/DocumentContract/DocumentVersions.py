"""CRM 1.9 Document & Contract Management — DocumentVersions models (split from apps/crm/models.py)."""
from apps.crm.models._base import *  # noqa: F401,F403


# ---- 1.9 File Repository — version-controlled contract revisions -------------------------
class DocumentVersion(models.Model):
    """An **immutable** revision of a ContractDocument (1.9 File Repository / version control).
    Each generate-from-template or file upload creates one; ``ContractDocument.current_version``
    points at the latest ``version_no``. Plain tenant-scoped child — accessed through its parent
    contract; list+detail only, never edited (an audit-grade revision log, like ``WorkflowLog``).
    Contract-revision history is CRM-specific; the generic ``core.Document`` attachment + the future
    Module 13 DMS are a separate, broader repository."""

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="+", db_index=True)
    contract = models.ForeignKey("crm.ContractDocument", on_delete=models.CASCADE, related_name="versions")
    version_no = models.PositiveSmallIntegerField(default=1)
    body_snapshot = models.TextField(blank=True)  # the contract HTML captured at this revision
    file = models.FileField(upload_to="crm/contracts/%Y/%m/", blank=True, null=True)  # uploaded artifact (e.g. signed PDF)
    change_note = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_doc_versions")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-version_no"]
        unique_together = ("tenant", "contract", "version_no")
        indexes = [models.Index(fields=["tenant", "contract"], name="crm_dv_tnt_contract_idx")]

    def __str__(self):
        return f"{self.contract.number} v{self.version_no}"
