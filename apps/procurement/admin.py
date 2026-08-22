"""Django admin for the procurement app."""
from django.contrib import admin

from .models import (
    ProcurementAlert,
    RequisitionAmendment,
    RequisitionAmendmentLine,
    RequisitionTemplate,
    RequisitionTemplateLine,
    WidgetPreference,
)


class RequisitionTemplateLineInline(admin.TabularInline):
    model = RequisitionTemplateLine
    extra = 0


@admin.register(RequisitionTemplate)
class RequisitionTemplateAdmin(admin.ModelAdmin):
    list_display = ("number", "name", "org_unit", "currency", "is_active", "created_by")
    list_filter = ("tenant", "is_active")
    search_fields = ("number", "name", "description")
    raw_id_fields = ("org_unit", "currency", "created_by")
    readonly_fields = ("number", "created_by", "created_at", "updated_at")
    inlines = [RequisitionTemplateLineInline]


class RequisitionAmendmentLineInline(admin.TabularInline):
    model = RequisitionAmendmentLine
    extra = 0


@admin.register(RequisitionAmendment)
class RequisitionAmendmentAdmin(admin.ModelAdmin):
    list_display = ("number", "requisition", "amendment_type", "status",
                    "requested_by", "decided_by", "decided_at")
    list_filter = ("tenant", "status", "amendment_type")
    search_fields = ("number", "reason", "decision_note")
    raw_id_fields = ("requisition", "requested_by", "decided_by")
    # status/amendment_type are read-only here ON PURPOSE: the admin must not be able to flip a
    # pending amendment to approved without apply() running — decisions go through the view.
    readonly_fields = ("number", "amendment_type", "status", "applied_at",
                       "requested_by", "decided_by", "decided_at",
                       "created_at", "updated_at")
    inlines = [RequisitionAmendmentLineInline]


@admin.register(ProcurementAlert)
class ProcurementAlertAdmin(admin.ModelAdmin):
    list_display = ("title", "kind", "severity", "status", "assigned_to", "due_at", "raised_at")
    list_filter = ("tenant", "status", "kind", "severity")
    search_fields = ("title", "message")
    raw_id_fields = ("assigned_to", "created_by", "acknowledged_by", "resolved_by")
    readonly_fields = ("created_by", "acknowledged_by", "acknowledged_at",
                       "resolved_by", "resolved_at", "raised_at",
                       "created_at", "updated_at")


@admin.register(WidgetPreference)
class WidgetPreferenceAdmin(admin.ModelAdmin):
    list_display = ("user", "widget_key", "is_visible", "updated_at")
    list_filter = ("tenant", "widget_key", "is_visible")
    search_fields = ("user__username",)
