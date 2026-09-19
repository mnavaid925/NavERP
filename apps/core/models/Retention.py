"""core — 0.8 bullet 3: Retention & Disposal Policies.

**Automated destruction is deliberately NOT implemented.** Two reasons, and both are stated on the
page rather than hidden:

1. Destroying data is a one-way door. The repo has no scheduler, so the only way to automate it is
   to make a page request destructive — a GET (or a stray POST from a bookmark) that silently erases
   rows is a far worse failure than an un-swept retention policy.
2. The project already established (7.10) that **"delete" in this codebase does not erase bytes** —
   Django never unlinks a `FileField` on row delete. A "destruction" feature that reports success
   while the file survives on disk would be actively dishonest.

So this sub-module does the part that is genuinely auditable: it states the schedule per category,
identifies what is past its window, and records a `DisposalRecord` as the evidence of what was
disposed of, when, by whom and how. The act itself is out of band, and the page says so.
"""
from django.utils import timezone

from apps.core.models._base import *  # noqa: F401,F403


class RetentionPolicy(models.Model):
    """How long one category of data is kept, and what should happen at the end of that."""

    ACTION_CHOICES = [
        ("review", "Flag for review"),
        ("delete", "Delete"),
        ("anonymize", "Anonymize"),
        ("archive", "Archive"),
    ]
    BASIS_CHOICES = [
        ("legal", "Legal requirement"),
        ("contract", "Contractual"),
        ("consent", "Consent"),
        ("legitimate_interest", "Legitimate interest"),
        ("operational", "Operational need"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="retention_policies", db_index=True)
    name = models.CharField(max_length=150)
    data_category = models.CharField(max_length=120)
    #: Optional `app_label.Model` this policy governs. Left blank for a category that spans models —
    #: a retention schedule is usually written per business category, not per table.
    model_label = models.CharField(max_length=120, blank=True)
    retention_months = models.PositiveIntegerField(
        default=12, help_text="How long the data is kept from its creation.")
    action = models.CharField(max_length=12, choices=ACTION_CHOICES, default="review")
    basis = models.CharField(max_length=24, choices=BASIS_CHOICES, default="legal")
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["tenant", "is_active"], name="retpol_tenant_active_idx")]

    def __str__(self):
        return f"{self.name} ({self.retention_months}m)"


class DisposalRecord(models.Model):
    """The EVIDENCE that a disposal happened. Written by hand, because the act is out of band."""

    METHOD_CHOICES = [
        ("deleted", "Deleted from the database"),
        ("anonymized", "Anonymized in place"),
        ("archived", "Moved to archive"),
        ("destroyed_media", "Destroyed with the media"),
        ("other", "Other"),
    ]

    tenant = models.ForeignKey("core.Tenant", on_delete=models.CASCADE,
                               related_name="disposal_records", db_index=True)
    policy = models.ForeignKey("core.RetentionPolicy", on_delete=models.SET_NULL, null=True,
                               blank=True, related_name="disposals")
    model_label = models.CharField(max_length=120, blank=True)
    record_count = models.PositiveIntegerField(default=0)
    method = models.CharField(max_length=20, choices=METHOD_CHOICES, default="deleted")
    performed_at = models.DateTimeField(default=timezone.now)
    performed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
                                     blank=True, related_name="+")
    #: Free text for the reference that makes this defensible: a ticket, a job id, a signed runbook.
    evidence = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-performed_at", "-id"]
        indexes = [models.Index(fields=["tenant", "-performed_at"], name="disp_tenant_at_idx")]

    def __str__(self):
        return f"{self.model_label or self.policy} · {self.record_count} · {self.get_method_display()}"
