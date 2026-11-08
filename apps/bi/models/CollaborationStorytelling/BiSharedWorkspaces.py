from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.utils.text import slugify

from apps.bi.models._base import TenantNumbered

HEX_COLOR_VALIDATOR = RegexValidator(
    r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$",
    "Enter a valid hex color, e.g. #3b82f6",
)


class BiSharedWorkspace(TenantNumbered):
    NUMBER_PREFIX = "WSPC"

    ACCESS_LEVEL_CHOICES = [
        ("viewer", "Viewer (Read-Only)"),
        ("contributor", "Contributor (Add Content)"),
        ("member", "Member (Edit & Share)"),
        ("admin", "Workspace Admin"),
    ]

    STATUS_CHOICES = [
        ("active", "Active"),
        ("archived", "Archived"),
    ]

    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, blank=True)
    description = models.TextField(blank=True)

    department = models.ForeignKey(
        "core.OrgUnit",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bi_workspaces",
        help_text="Linked organizational unit / department",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bi_owned_workspaces",
        help_text="Primary custodian / workspace lead",
    )

    default_access_level = models.CharField(
        max_length=20,
        choices=ACCESS_LEVEL_CHOICES,
        default="contributor",
        help_text="Default permissions for new workspace collaborators",
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default="active")

    is_public = models.BooleanField(
        default=False,
        help_text="Visible to all tenant users with BI access",
    )
    is_favorite = models.BooleanField(
        default=False,
        help_text="Pinned as top-priority workspace for the tenant",
    )
    color = models.CharField(max_length=20, default="#3b82f6", validators=[HEX_COLOR_VALIDATOR])
    icon = models.CharField(max_length=50, default="folder")

    pinned_dashboard_ids = models.JSONField(
        default=list,
        blank=True,
        help_text="List of BiDashboard IDs pinned to this workspace",
    )
    pinned_report_ids = models.JSONField(
        default=list,
        blank=True,
        help_text="List of ReportDefinition IDs pinned to this workspace",
    )
    pinned_story_ids = models.JSONField(
        default=list,
        blank=True,
        help_text="List of BiDataStory IDs pinned to this workspace",
    )
    members_json = models.JSONField(
        default=list,
        blank=True,
        help_text="JSON list of workspace members and access overrides [{'user_id': 1, 'role': 'admin'}]",
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="bi_created_workspaces",
    )

    class Meta:
        db_table = "bi_shared_workspace"
        ordering = ["-is_favorite", "name"]
        constraints = [
            models.UniqueConstraint(fields=["tenant", "number"], name="bi_wspc_ten_num_uniq"),
            models.UniqueConstraint(fields=["tenant", "slug"], name="bi_wspc_ten_slug_uniq"),
        ]
        indexes = [
            models.Index(fields=["tenant", "status"], name="idx_wspc_ten_stat"),
            models.Index(fields=["tenant", "default_access_level"], name="idx_swsp_ten_dacc"),
            models.Index(fields=["tenant", "department"], name="idx_wspc_ten_dept"),
            models.Index(fields=["tenant", "owner"], name="idx_wspc_ten_owner"),
            models.Index(fields=["tenant", "created_at"], name="idx_wspc_ten_created"),
        ]

    def __str__(self):
        return f"{self.number} - {self.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name) or "workspace"
            slug = base_slug
            counter = 1
            qs = BiSharedWorkspace.objects.filter(tenant=self.tenant)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            while qs.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)
