"""core — Tenant models (split from apps/core/models.py)."""
from django.core.validators import RegexValidator

from apps.core.models._base import *  # noqa: F401,F403


#: A custom workspace domain, e.g. ``acme.example.com``. Requires at least one dot (a custom
#: domain is not a bare hostname) and refuses a label that starts or ends with a hyphen, which
#: is what makes ``-acme.com`` and ``acme-.com`` invalid rather than merely unusual.
#: Case-tolerant on purpose: ``clean()`` lowercases, so a user may type ``ACME.example.com``.
DOMAIN = RegexValidator(
    r"^(?=.{1,253}$)(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))+$",
    "Enter a valid domain, e.g. acme.example.com.",
)


class Tenant(models.Model):
    """A customer workspace. Root of all tenant-scoped data."""

    PLAN_CHOICES = [
        ("free", "Free"),
        ("starter", "Starter"),
        ("pro", "Pro"),
        ("enterprise", "Enterprise"),
    ]

    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=120, unique=True)
    #: 0.1 "Tenant Onboarding — domain provisioning". ``null=True`` (not just blank) so the
    #: unique constraint permits many tenants with no domain: MySQL treats NULLs as distinct,
    #: whereas a blank string would collide on the second domain-less tenant.
    domain = models.CharField(
        max_length=253,
        unique=True,
        null=True,
        blank=True,
        validators=[DOMAIN],
        help_text="Custom domain for this workspace, e.g. acme.example.com.",
    )
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default="free")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def clean(self):
        super().clean()
        # Normalise after the validators have run (they are case-tolerant by design), so the
        # stored value is always lowercase and two tenants cannot differ only by case.
        if self.domain:
            self.domain = self.domain.strip().lower()

    def __str__(self):
        return self.name
