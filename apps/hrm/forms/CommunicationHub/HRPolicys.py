"""HRM 3.27 Communication Hub — HRPolicys forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    HRPolicy,
)
from apps.hrm.forms.CandidateManagement._helpers import _validate_upload
from apps.hrm.forms.CommunicationHub.ALLOWED_COMPLIANCE_DOC_EXTENSIONSs import ALLOWED_COMPLIANCE_DOC_EXTENSIONS
from apps.hrm.forms.CommunicationHub.MAX_COMPLIANCE_DOC_BYTESs import MAX_COMPLIANCE_DOC_BYTES


class HRPolicyForm(TenantModelForm):
    # published_at is stamped by the publish action; acknowledgments are raised there too.
    class Meta:
        model = HRPolicy
        fields = ["title", "category", "version_number", "previous_version", "applicable_org_unit",
                  "summary", "body", "document", "status", "effective_from", "requires_acknowledgment"]
        widgets = {"summary": forms.Textarea(attrs={"rows": 2}), "body": forms.Textarea(attrs={"rows": 10})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "status" in self.fields:
            # WARNING (review finding): "published" must NOT be settable from this form. Publishing
            # goes through hrpolicy_publish, which stamps published_at AND raises a pending
            # PolicyAcknowledgment for every targeted employee. Setting it here would skip both — and
            # then permanently lock the policy out of the real publish action, whose own guard refuses
            # to run on an already-published policy. So the form offers draft/archived only.
            allowed = [c for c in HRPolicy.STATUS_CHOICES if c[0] != "published"]
            if self.instance.pk and self.instance.status == "published":
                # An already-published policy keeps its value (an edit must not silently demote it to
                # draft) and may only move on to archived.
                allowed = [c for c in HRPolicy.STATUS_CHOICES if c[0] in ("published", "archived")]
            self.fields["status"].choices = allowed
        if self.tenant is not None:
            if "applicable_org_unit" in self.fields:
                self.fields["applicable_org_unit"].queryset = (
                    OrgUnit.objects.filter(tenant=self.tenant, kind="department").order_by("name"))
            if "previous_version" in self.fields:
                qs = HRPolicy.objects.filter(tenant=self.tenant)
                if self.instance.pk:
                    qs = qs.exclude(pk=self.instance.pk)  # a policy can't supersede itself
                self.fields["previous_version"].queryset = qs.order_by("-created_at")

    def clean_status(self):
        """Defence in depth behind the narrowed choices above — a crafted POST must not be able to
        publish a policy (and thereby skip the acknowledgment rows)."""
        status = self.cleaned_data.get("status")
        already_published = bool(self.instance.pk and self.instance.status == "published")
        if status == "published" and not already_published:
            raise forms.ValidationError(
                "Publish a policy from its detail page — that is what raises the acknowledgment "
                "requests. It cannot be published from this form.")
        return status

    def clean(self):
        cleaned = super().clean()
        # unique_together(tenant, title, version_number) — Django skips validate_unique because tenant is
        # form-excluded, so a duplicate would 500 on save instead of showing a field error.
        title, version = cleaned.get("title"), cleaned.get("version_number")
        if title and version and self.tenant is not None:
            dupe = HRPolicy.objects.filter(tenant=self.tenant, title=title, version_number=version)
            if self.instance.pk:
                dupe = dupe.exclude(pk=self.instance.pk)
            if dupe.exists():
                self.add_error("version_number", "This policy already has a version with that number.")
        return cleaned

    def clean_document(self):
        return _validate_upload(self.cleaned_data.get("document"),
                                allowed_ext=ALLOWED_COMPLIANCE_DOC_EXTENSIONS,
                                max_bytes=MAX_COMPLIANCE_DOC_BYTES, label="Policy Document")
