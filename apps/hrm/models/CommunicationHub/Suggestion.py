"""HRM 3.27 Communication Hub — Suggestion models (split from apps/hrm/models.py)."""
from apps.hrm.models._base import *  # noqa: F401,F403


class Suggestion(TenantNumbered):
    """3.27 employee idea box, admin-reviewed. Clones the 3.26 request lifecycle field-for-field
    (employee owner FK named `employee`; reviewer stamps named `approver`/`approved_at`) so the shared
    _hr_request_* view helpers apply verbatim. Lifecycle draft -> pending -> approved (label "Accepted")
    / rejected / cancelled, then approved -> implemented (a fulfillment tail like the 3.26 fulfill/issue
    actions). `is_anonymous` suppresses the submitter's name in admin-facing views (display-layer only)."""

    NUMBER_PREFIX = "SUG"

    CATEGORY_CHOICES = [
        ("process", "Process Improvement"),
        ("workplace", "Workplace / Facilities"),
        ("product", "Product / Service"),
        ("cost_saving", "Cost Saving"),
        ("wellbeing", "Wellbeing / Culture"),
        ("other", "Other"),
    ]
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("pending", "Pending"),
        ("approved", "Accepted"),
        ("rejected", "Rejected"),
        ("cancelled", "Cancelled"),
        ("implemented", "Implemented"),
    ]
    OPEN_STATUSES = ("draft", "pending")

    employee = models.ForeignKey("hrm.EmployeeProfile", on_delete=models.CASCADE, related_name="suggestions")
    title = models.CharField(max_length=255)
    body = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="other")
    is_anonymous = models.BooleanField(default=False)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="draft")
    approver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                                 related_name="hrm_suggestion_approvals")
    approved_at = models.DateTimeField(null=True, blank=True)
    decision_note = models.TextField(blank=True)
    implementation_note = models.TextField(blank=True)
    implemented_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "employee", "status"], name="hrm_sug_emp_status_idx"),
            models.Index(fields=["tenant", "status"], name="hrm_sug_tenant_status_idx"),
        ]

    def __str__(self):
        return (f"{self.number} · {self.employee} · {self.title}"
                if self.number else self.title)
