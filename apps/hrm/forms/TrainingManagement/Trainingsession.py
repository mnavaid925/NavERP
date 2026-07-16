"""HRM 3.22 Training Management — Trainingsession forms (split from apps/hrm/forms.py)."""
from apps.hrm.forms._common import *  # noqa: F401,F403
from apps.hrm.models import (
    TrainingSession,
)


class TrainingSessionForm(TenantModelForm):
    # Excludes tenant + auto number. course/instructor_employee are auto tenant-scoped by the base;
    # external_vendor is re-scoped to vendor-role parties, and currency is set from the GLOBAL
    # accounting.Currency master (lazy import — accounting is a runtime, not module-load, dependency).
    class Meta:
        model = TrainingSession
        fields = ["course", "delivery_mode", "status", "start_datetime", "end_datetime", "timezone",
                  "capacity", "waitlist_enabled", "venue_name", "venue_address", "meeting_platform",
                  "meeting_link", "meeting_id", "instructor_employee", "external_instructor_name",
                  "external_vendor", "estimated_cost", "actual_cost", "currency", "invoice_reference", "notes"]
        widgets = {
            # start_datetime/end_datetime get their datetime-local widget + round-trip input_formats
            # from TenantModelForm.__init__ (L22) — no need to re-declare them here.
            "venue_address": forms.Textarea(attrs={"rows": 2, "class": "form-textarea"}),
            "notes": forms.Textarea(attrs={"rows": 2, "class": "form-textarea"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Give the (possibly unsaved) instance its tenant BEFORE validation so the model's clean()
        # double-booking overlap query is tenant-scoped even on create. crud_create only sets
        # obj.tenant AFTER form.is_valid(), so without this the create-path clean() would filter on
        # tenant_id=None and the overlap guard would silently never fire (edit already has it from DB).
        if self.tenant is not None and self.instance is not None:
            self.instance.tenant = self.tenant
        if self.tenant is not None:
            if "external_vendor" in self.fields:
                # The base only filters by tenant; scope to vendor-role parties (mirrors accounting).
                self.fields["external_vendor"].queryset = (
                    Party.objects.filter(tenant=self.tenant, roles__role="vendor").distinct().order_by("name"))
            if "currency" in self.fields:
                from apps.accounting.models import Currency   # lazy — keep accounting a runtime dep
                self.fields["currency"].queryset = Currency.objects.filter(is_active=True).order_by("code")
