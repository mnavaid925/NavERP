"""Identity & access models: User (custom), RBAC Role/Permission, and UserInvite."""
import secrets

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone

from .managers import UserManager


class Permission(models.Model):
    """RBAC permission catalog (global, not tenant-scoped). Bundled into Roles."""

    codename = models.CharField(max_length=120, unique=True)  # e.g. "accounts.user.manage"
    name = models.CharField(max_length=255)
    module = models.CharField(max_length=50, default="core")  # module number/slug grouping

    class Meta:
        ordering = ["module", "codename"]

    def __str__(self):
        return self.codename


class Role(models.Model):
    """A named bundle of permissions assigned to users within a tenant."""

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="roles", db_index=True)
    name = models.CharField(max_length=120)
    description = models.CharField(max_length=255, blank=True)
    permissions = models.ManyToManyField("accounts.Permission", blank=True, related_name="roles")
    is_system = models.BooleanField(default=False)  # seeded roles — protected from deletion

    class Meta:
        ordering = ["name"]
        unique_together = ("tenant", "name")

    def __str__(self):
        return self.name


class User(AbstractBaseUser, PermissionsMixin):
    """Custom user. Login is by email (or username via the auth backend).

    ``tenant`` is nullable: the superuser ``admin`` has tenant=None by design and sees
    no module data. ``party`` links the login to the Party that represents this person.
    """

    STATUS_CHOICES = [
        ("active", "Active"),
        ("suspended", "Suspended"),
        ("archived", "Archived"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.SET_NULL, null=True, blank=True,
                               related_name="users", db_index=True)
    party = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True,
                              related_name="users")
    role = models.ForeignKey("accounts.Role", on_delete=models.SET_NULL, null=True, blank=True,
                             related_name="users")

    email = models.EmailField(unique=True)
    username = models.CharField(max_length=150, unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)

    is_tenant_admin = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    objects = UserManager()

    class Meta:
        ordering = ["email"]

    def __str__(self):
        return self.email

    def get_full_name(self):
        full = f"{self.first_name} {self.last_name}".strip()
        return full or self.username

    def get_short_name(self):
        return self.first_name or self.username

    @property
    def initials(self):
        a = (self.first_name[:1] or self.email[:1]).upper()
        b = (self.last_name[:1] or "").upper()
        return (a + b) or "?"


class UserInvite(models.Model):
    """Pending invitation for someone to join a tenant. Accepted via a tokenized link."""

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("expired", "Expired"),
        ("revoked", "Revoked"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE, related_name="invites", db_index=True)
    email = models.EmailField()
    role = models.ForeignKey("accounts.Role", on_delete=models.SET_NULL, null=True, blank=True,
                             related_name="invites")
    token = models.CharField(max_length=64, unique=True, editable=False)  # secret — excluded from forms (L20)
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                   blank=True, related_name="sent_invites")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)  # system-set, out of forms (L22)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(32)
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(days=7)
        super().save(*args, **kwargs)

    def is_expired(self):
        return timezone.now() > self.expires_at

    def __str__(self):
        return f"{self.email} → {self.tenant}"
