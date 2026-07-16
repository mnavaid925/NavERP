"""core — Document models (split from apps/core/models.py)."""
from apps.core.models._base import *  # noqa: F401,F403


class Document(models.Model):
    """Generic file attachment for any record (DMS module later layers folders/versions on top)."""

    CLASSIFICATION_CHOICES = [
        ("public", "Public"),
        ("internal", "Internal"),
        ("confidential", "Confidential"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="documents", db_index=True)
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.BigIntegerField(null=True, blank=True)
    related = GenericForeignKey("content_type", "object_id")
    file = models.FileField(upload_to="documents/%Y/%m/")
    name = models.CharField(max_length=255)
    classification = models.CharField(max_length=20, choices=CLASSIFICATION_CHOICES, default="internal")
    version = models.CharField(max_length=20, default="1.0")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.name
