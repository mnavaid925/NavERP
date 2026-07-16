"""tenants — BrandingSetting models (split from apps/tenants/models.py)."""
from apps.tenants.models._base import *  # noqa: F401,F403


class BrandingSetting(models.Model):
    tenant = models.OneToOneField("core.Tenant", on_delete=models.CASCADE, related_name="branding", db_index=True)
    logo = models.ImageField(upload_to="branding/", null=True, blank=True)
    primary_color = models.CharField(max_length=7, default="#2563eb", validators=[HEX_COLOR])
    accent_color = models.CharField(max_length=7, default="#1d4ed8", validators=[HEX_COLOR])
    email_from_name = models.CharField(max_length=120, blank=True)
    email_footer = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def save(self, *args, **kwargs):
        # Enforce the hex validator on every save (defense-in-depth vs CSS injection
        # into inline style= — covers programmatic writes that bypass the form).
        HEX_COLOR(self.primary_color)
        HEX_COLOR(self.accent_color)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Branding · {self.tenant}"
