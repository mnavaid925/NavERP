"""HRM 3.27 Communication Hub — _helpers forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403


# The per-priority (response, resolution) hour-field pairs on HelpdeskSLAPolicy — used by the form's
# clean() so a resolution target can never be shorter than its own response target.
_SLA_HOUR_PAIRS = [
    ("urgent_response_hours", "urgent_resolution_hours", "Urgent"),
    ("high_response_hours", "high_resolution_hours", "High"),
    ("medium_response_hours", "medium_resolution_hours", "Medium"),
    ("low_response_hours", "low_resolution_hours", "Low"),
]


def _scope_currency(form):
    """Scope a form's ``currency`` field to active currencies (the GLOBAL master isn't tenant-scoped, so
    TenantModelForm's auto-scoper skips it)."""
    if "currency" in form.fields:
        from apps.accounting.models import Currency
        form.fields["currency"].queryset = Currency.objects.filter(is_active=True).order_by("code")
