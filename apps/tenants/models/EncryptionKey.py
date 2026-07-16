"""tenants — EncryptionKey models (split from apps/tenants/models.py)."""
from apps.tenants.models._base import *  # noqa: F401,F403


class EncryptionKey(models.Model):
    """Per-tenant key handle. The plaintext is shown exactly once on creation/rotation
    and NEVER stored — only its prefix (for identification) and a SHA-256 hash."""

    STATUS_CHOICES = [("active", "Active"), ("rotated", "Rotated"), ("revoked", "Revoked")]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="encryption_keys", db_index=True)
    name = models.CharField(max_length=120)
    prefix = models.CharField(max_length=16, editable=False)
    key_hash = models.CharField(max_length=128, editable=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    last_rotated_at = models.DateTimeField(null=True, blank=True)  # system-set, out of forms (L22)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    @staticmethod
    def generate_plaintext():
        return "nk_" + secrets.token_urlsafe(32)

    def set_secret(self, plaintext):
        self.prefix = plaintext[:10]
        self.key_hash = hashlib.sha256(plaintext.encode()).hexdigest()

    def __str__(self):
        return f"{self.name} ({self.prefix}…)"
