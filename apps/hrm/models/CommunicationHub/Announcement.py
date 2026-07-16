"""HRM 3.27 Communication Hub — Announcement models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class Announcement(TenantNumbered):
    """3.27 admin-authored company announcement — news / policy / event, audience-targeted (all / a
    department / a designation) with a draft -> published -> archived lifecycle + pinning + optional
    expiry. Employees read the published, un-expired, for-them feed; admins author/manage."""

    NUMBER_PREFIX = "ANN"

    CATEGORY_CHOICES = [
        ("general", "General"),
        ("news", "News"),
        ("policy", "Policy"),
        ("event", "Event"),
        ("it", "IT"),
        ("hr", "HR"),
        ("benefits", "Benefits"),
    ]
    AUDIENCE_TYPE_CHOICES = [
        ("all", "All Employees"),
        ("department", "A Department"),
        ("designation", "A Designation"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("published", "Published"),
        ("archived", "Archived"),
    ]

    title = models.CharField(max_length=255)
    body = models.TextField()
    category = models.CharField(max_length=15, choices=CATEGORY_CHOICES, default="general")
    audience_type = models.CharField(max_length=15, choices=AUDIENCE_TYPE_CHOICES, default="all")
    target_department = models.ForeignKey("core.OrgUnit", on_delete=models.SET_NULL, null=True, blank=True,
                                          related_name="announcements", limit_choices_to={"kind": "department"})
    target_designation = models.ForeignKey("hrm.Designation", on_delete=models.SET_NULL, null=True, blank=True,
                                           related_name="announcements")
    is_pinned = models.BooleanField(default=False)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    published_at = models.DateTimeField(null=True, blank=True, editable=False)
    expires_at = models.DateField(null=True, blank=True)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                               editable=False, related_name="hrm_announcement_authored")

    class Meta:
        ordering = ["-is_pinned", "-published_at", "-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="hrm_ann_tenant_status_idx"),
        ]

    def clean(self):
        super().clean()
        if self.audience_type == "department" and self.target_department_id is None:
            raise ValidationError({"target_department": "Select the department this announcement targets."})
        if self.audience_type == "designation" and self.target_designation_id is None:
            raise ValidationError({"target_designation": "Select the designation this announcement targets."})

    def __str__(self):
        return f"{self.number} · {self.title}" if self.number else self.title
