"""core — 0.17 forms (monitoring, logging & observability).

**L22 is absolute here: zero editable `DateTimeField`s.** Every system-set stamp —
`last_status_at`, `fired_at`, `acknowledged_at`, `resolved_at`, `first_seen_at`, `last_seen_at`,
`notified_at`, `created_at`, `updated_at` — is out of every `Meta.fields` list below. A `DateInput`
widget on a nullable `DateTimeField` truncates the time component, and a person typing a timestamp is a
person inventing an event that a system was supposed to record.

**The two deliberate exceptions, both argued rather than accidental:**

1. `AlertEventForm.muted_until` — a forward-declared mute boundary a human types, exactly the 0.16
   `BackupJob.retain_until` precedent. It is not system-set: nothing in NavERP enforces a mute.
2. `IncidentForm`'s `started_at` / `scheduled_for` / `scheduled_until` — the schedule a person is
   DECLARING, not a stamp a system took. A `scheduled_maintenance` notice that cannot say when its
   window opens is not a notice. `TenantModelForm.__init__` already installs a `datetime-local` widget
   with matching `input_formats` for all three, so no widget is re-declared here.

**Two `save()` overrides, and only two, both writing a field the form does not expose:**
`ServiceComponentForm` stamps `last_status_at` (in the FORM rather than the view, so the Django admin
gets it too — one extra query per edit POST and nowhere else), and `AlertEventForm` writes the
`service_label` snapshot and `first_seen_at`.

`AlertRuleForm.clean_name` is the **only** `clean_*` in this file, and it exists because `tenant` is
deliberately not a `Meta.fields` member: Django's `_get_unique_checks()` discards a `unique_together`
naming an excluded field, so `(tenant, name)` would otherwise reach the database as an `IntegrityError`
500 on both create and edit. The same guard `StatutoryRuleForm.clean_name` already ships.
"""
from django import forms
from django.utils import timezone

from apps.core.forms._common import *  # noqa: F401,F403
from apps.core.models import AlertEvent, AlertRule, Incident, ServiceComponent


class ServiceComponentForm(TenantModelForm):
    class Meta:
        model = ServiceComponent
        fields = ["name", "code", "kind", "description", "owner_role", "is_public", "is_critical",
                  "display_order", "current_status", "notes", "is_active"]
        labels = {
            "owner_role": "Owning role",
            # The label is what makes the field honest, and the detail page repeats it.
            "current_status": "Current status (hand-set — nothing probes this)",
        }

    def save(self, commit=True):
        # `last_status_at` is system-set (L22) and out of `Meta.fields`, stamped HERE rather than in the
        # view so the Django admin path gets it too — the admin uses a plain ModelForm and would
        # otherwise leave the stamp permanently NULL on every admin edit.
        #
        # The honest reading of "last status change" is "when a person last changed the status by hand",
        # because nothing probes this component. One extra query per edit POST, nowhere else: the
        # comparison is against the PERSISTED value, so re-saving without changing the status does not
        # touch the stamp and cannot make the row look freshly checked.
        obj = super().save(commit=False)
        if obj.pk:
            before = (ServiceComponent.objects.filter(pk=obj.pk)
                      .values_list("current_status", flat=True).first())
            if before != obj.current_status:
                obj.last_status_at = timezone.now()
        if commit:
            obj.save()
            self.save_m2m()
        return obj


class AlertRuleForm(TenantModelForm):
    class Meta:
        model = AlertRule
        fields = ["name", "service", "module_slug", "metric_key", "comparator", "warning_threshold",
                  "critical_threshold", "must_persist_seconds", "frequency", "severity", "category",
                  "no_data_action", "notification_rule", "is_active", "notes"]
        labels = {
            "must_persist_seconds": "Must persist (seconds)",
            "no_data_action": "When there is no data",
            "notification_rule": "Notify via (0.12 rule)",
        }

    def clean_name(self):
        # `(tenant, name)` is `unique_together`, but `tenant` is NOT a `Meta.fields` member, so Django
        # DROPS the whole tuple from validation (`_get_unique_checks()` discards a `unique_together`
        # containing an excluded field) and a duplicate name reaches the database as an `IntegrityError`
        # 500 on both create and edit. Enforce it here, scoped to this tenant — the same guard
        # `StatutoryRuleForm.clean_name` already ships (`apps/core/forms/Localization.py`).
        name = self.cleaned_data.get("name")
        if name and self.tenant is not None:
            qs = AlertRule.objects.filter(tenant=self.tenant, name=name)
            if self.instance and self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(
                    "An alert rule with this name already exists in this workspace — edit the existing "
                    "one or choose a different name.")
        return name


class AlertEventForm(TenantModelForm):
    class Meta:
        model = AlertEvent
        fields = ["rule", "service", "severity_at_fire", "observed_value", "threshold_at_fire",
                  "message", "detail", "muted_until", "evidence"]
        labels = {
            "severity_at_fire": "Severity at fire (snapshot)",
            "threshold_at_fire": "Threshold at fire",
            "muted_until": "Muted until (a recorded mute — nothing enforces it)",
        }

    def save(self, commit=True):
        # `service_label` is a DENORMALISED SNAPSHOT, not a form field: a person cannot type it, and it
        # must not be able to disagree with the service they picked. Written here so the row still reads
        # after the component is deleted — which is the whole reason `AlertEvent.service` is SET_NULL.
        #
        # It is only written when a service IS chosen. Clearing the service is a legitimate correction
        # (the firing was logged against the wrong component), and overwriting unconditionally would set
        # the snapshot to "" and destroy the very evidence that is meant to outlive the component. On an
        # edit with no service the existing snapshot is preserved instead.
        #
        # `first_seen_at` is written here too, rather than in the create view, so the admin path gets it:
        # a report with no first-seen time is a report whose age nobody can compute. Only ever
        # back-filled when empty, so a later edit cannot rewrite the original first sighting.
        obj = super().save(commit=False)
        if obj.service_id:
            obj.service_label = obj.service.name
        elif obj.pk is None:
            obj.service_label = ""
        if obj.fired_at and not obj.first_seen_at:
            obj.first_seen_at = obj.fired_at
        if commit:
            obj.save()
            self.save_m2m()
        return obj


class IncidentForm(TenantModelForm):
    class Meta:
        model = Incident
        fields = ["title", "service", "affected_services", "primary_alert", "incident_type", "status",
                  "impact", "public_note", "internal_note", "progress_pct", "started_at",
                  "scheduled_for", "scheduled_until", "is_active", "notes"]
        labels = {
            "affected_services": "Also affecting",
            "primary_alert": "Originating alert",
            "progress_pct": "Progress (%)",
            "public_note": "Public note (what a status page would show)",
            "internal_note": "Internal note (never public)",
        }
    # NO `save()` override, deliberately: there is no snapshot to write and no system stamp this form is
    # allowed to set. `resolved_at` is derived in the MODEL's `save()` and `notified_at` is written only
    # by the POST-only `incident_notify` action. Confirm this before adding one (plan §2.4).

