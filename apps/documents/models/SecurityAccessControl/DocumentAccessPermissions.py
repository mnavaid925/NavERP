from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.documents.models._base import TenantNumbered


class DocumentAccessPermission(TenantNumbered):
    """
    Granular Access Control List (ACL) entry mapping a Document or DocumentFolder
    to a User, OrgUnit, Role, or Tenant-wide scope with capability flags and time-bounding.
    """

    NUMBER_PREFIX = "DPRM"

    GRANTEE_TYPE_CHOICES = (
        ("user", "Specific User"),
        ("org_unit", "Organizational Unit (Department)"),
        ("role", "Standardized Role"),
        ("tenant_wide", "Tenant-Wide (All Employees)"),
    )

    PERMISSION_LEVEL_CHOICES = (
        ("viewer", "Viewer (Read & Preview Only)"),
        ("commenter", "Commenter (Read & Annotate)"),
        ("editor", "Editor (Read, Edit, & Version)"),
        ("manager", "Manager (Read, Edit, & Share)"),
        ("owner", "Owner (Full Control & Admin)"),
        ("custom", "Custom Capabilities Matrix"),
    )

    GRANTEE_TYPE_CSS = {
        "user": "badge-info",
        "org_unit": "badge-slate",
        "role": "badge-amber",
        "tenant_wide": "badge-slate",
    }

    PERMISSION_LEVEL_CSS = {
        "viewer": "badge-slate",
        "commenter": "badge-info",
        "editor": "badge-amber",
        "manager": "badge-amber",
        "owner": "badge-green",
        "custom": "badge-muted",
    }

    document = models.ForeignKey(
        "documents.Document",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="access_permissions",
    )
    folder = models.ForeignKey(
        "documents.DocumentFolder",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="access_permissions",
    )
    grantee_type = models.CharField(
        max_length=20,
        choices=GRANTEE_TYPE_CHOICES,
        default="user",
        db_index=True,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="document_permissions",
    )
    org_unit = models.ForeignKey(
        "core.OrgUnit",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="document_permissions",
    )
    role_name = models.CharField(max_length=50, blank=True)
    permission_level = models.CharField(
        max_length=20,
        choices=PERMISSION_LEVEL_CHOICES,
        default="viewer",
    )

    # Capability flags
    can_read = models.BooleanField(default=True)
    can_write = models.BooleanField(default=False)
    can_delete = models.BooleanField(default=False)
    can_download = models.BooleanField(default=True)
    can_print = models.BooleanField(default=True)
    can_share = models.BooleanField(default=False)

    # Inheritance & Validity
    is_inherited = models.BooleanField(default=False)
    inherited_from_folder = models.ForeignKey(
        "documents.DocumentFolder",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inherited_permissions",
    )
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)

    # Telemetry
    access_count = models.PositiveIntegerField(default=0)
    last_accessed_at = models.DateTimeField(null=True, blank=True)
    notes = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="granted_document_permissions",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Document Access Permission"
        verbose_name_plural = "Document Access Permissions"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="doc_dprm_ten_num_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "document", "is_active"], name="doc_dprm_tnt_doc_act_idx"),
            models.Index(fields=["tenant", "user", "is_active"], name="doc_dprm_tnt_usr_act_idx"),
            models.Index(fields=["tenant", "folder", "is_active"], name="doc_dprm_tnt_fld_act_idx"),
        ]

    def __str__(self):
        target = self.document.title if self.document else (self.folder.name if self.folder else "General")
        grantee = self.grantee_display
        return f"{self.number} ({grantee} -> {target})"

    @property
    def grantee_display(self):
        if self.grantee_type == "user" and self.user:
            return self.user.get_full_name() or self.user.username
        elif self.grantee_type == "org_unit" and self.org_unit:
            return f"OrgUnit: {self.org_unit.name}"
        elif self.grantee_type == "role":
            return f"Role: {self.role_name}"
        elif self.grantee_type == "tenant_wide":
            return "Tenant-Wide"
        return "Unassigned"

    @property
    def is_currently_valid(self):
        if not self.is_active:
            return False
        now = timezone.now()
        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        return True

    @property
    def grantee_type_badge(self):
        return self.GRANTEE_TYPE_CSS.get(self.grantee_type, "badge-slate")

    @property
    def permission_level_badge(self):
        return self.PERMISSION_LEVEL_CSS.get(self.permission_level, "badge-slate")
