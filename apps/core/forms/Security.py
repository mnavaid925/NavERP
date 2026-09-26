"""core — 0.18 forms (threat protection & security operations).

**L22 is absolute here: zero editable `DateTimeField`s for system-set stamps.** Every
stamp a system took — `SecurityThreat.resolved_at` / `resolved_by`; `IpAccessRule.created_at` /
`updated_at`; `VulnerabilityFinding.accepted_at` / `created_at` / `updated_at`;
`SecurityIncident.contained_at` / `eradicated_at` / `recovered_at` / `closed_at` /
`authority_notified_at` / `subjects_notified` / `subjects_notified_at` / `created_at` /
`updated_at` — is out of every `Meta.fields` list below. A person typing a timestamp is a
person inventing an event the system was supposed to record. `regulatory_deadline` is a
property and is never a field, so it can never be typed either.

**The deliberate exceptions, each argued rather than accidental:**

1. `SecurityThreatForm.detected_at` and `SecurityIncidentForm.discovered_at` — a *fact a
   person is declaring*, not a stamp a system took. A finding that cannot say when it
   happened is a finding nobody can age, and for a breach `discovered_at` is literally the
   moment the organisation became aware: the anchor the 72-hour Art. 33 clock runs from.
2. `IpAccessRuleForm.expires_at` — a forward-declared block boundary a human types, the
   0.16 `BackupJob.retain_until` / 0.17 `AlertEvent.muted_until` precedent.
3. `VulnerabilityFindingForm.first_seen_at` / `last_seen_at` / `due_on` — the remediation
   schedule somebody sets. `due_on` is deliberately allowed to stay blank: a defaulted
   deadline is a deadline nobody chose.

`TenantModelForm.__init__` already installs a `datetime-local` widget with matching
`input_formats` for every `DateTimeField` and a date widget for every `DateField`, so
**no widget is re-declared in this file.**

**No form re-implements a `clean()` refusal.** Every rule lives in the model's `clean()`,
so the Django **admin** path — a plain `ModelForm` that bypasses these forms entirely —
is held to exactly the same standard. That is the whole reason the refusals are not
here: duplicating them would create a second place to forget to update one.

**`SecurityIncidentForm.__init__` is the only place a widget is replaced**, and only to
give `is_notifiable` its third state: a `CheckboxInput` cannot express NULL, and NULL
("nobody has decided yet") is the state the 72-hour clock exists to pressure.
"""
from django import forms
from django.utils import timezone

from apps.core.forms._common import *  # noqa: F401,F403
from apps.core.models import (IpAccessRule, SecurityIncident, SecurityThreat,
                               ServiceComponent, VulnerabilityFinding)


class IpAccessRuleForm(TenantModelForm):
    class Meta:
        model = IpAccessRule
        fields = ["cidr", "direction", "action", "scope", "service", "credential",
                  "rate_limit_policy", "reason", "source", "expires_at", "is_active", "notes"]
        labels = {
            "cidr": "IP address or CIDR block",
            "reason": "Why this entry exists (required)",
            "action": "Recorded action (nothing in NavERP enforces this)",
            "scope": "Scope",
            "rate_limit_policy": "Related rate-limit policy (0.13 owns the limit itself)",
        }

    # NO `save()` override, deliberately. `added_by` / `added_by_label` are stamped by the
    # create **view** from `request.user` — there is no request in a form, and a rule created
    # through the admin honestly has no "who asked", so the field stays NULL there, which is
    # true rather than a gap.


class SecurityThreatForm(TenantModelForm):
    class Meta:
        model = SecurityThreat
        fields = ["title", "threat_type", "severity", "status", "detected_at", "alert_event",
                  "rate_limit_policy", "service", "target_user", "target_credential",
                  "mitre_technique", "mitre_tactic", "rule_reference", "waf_action",
                  "defense_mode", "source_ip", "occurrence_count", "summary", "detail",
                  "evidence", "mitigated_by", "notes"]
        labels = {
            "mitre_technique": "MITRE ATT&CK technique (e.g. T1110.001 - free text, not a fixed list)",
            "defense_mode": "Bot/abuse mitigation posture (recorded, not enforced)",
            "waf_action": "WAF action (reference only - NavERP runs no WAF)",
            "evidence": "Evidence (a ticket id, a pasted log line, a screenshot path - not a payload)",
            "alert_event": "Originating alert (0.17's firing - the seam, not a second alert table)",
            "rate_limit_policy": "Rate-limit policy crossed (0.13 owns the limit itself)",
            "detected_at": "When it was observed (declared, not system-stamped)",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Same N+1 defusal as 0.17's `IncidentForm.primary_alert`, and for the same reason:
        # `AlertEvent.__str__` renders its rule, so every `<option>` Django builds calls a method
        # that dereferences a foreign key. Measured there at 200 events = 201 queries. The fix
        # belongs HERE and not in the shared `TenantModelForm` — select_related-ing every FK
        # there would alter every `ModelChoiceField` in every app and put committed tests in
        # three other apps at risk. A local `__init__` cannot be re-filtered away by the base
        # class's tenant-scoping loop, which runs inside `super().__init__()` above.
        field = self.fields.get("alert_event")
        if field is not None and field.queryset is not None:
            field.queryset = (field.queryset
                              .select_related("rule")
                              .order_by("-fired_at", "-id")[:200])
        # `mitigated_by` renders `IpAccessRule.__str__`, which reads two columns on the row
        # itself, so it is not an N+1 — capped anyway, because an operator picking "which rule
        # did we write in response" wants the recent ones, not every rule since the register began.
        field = self.fields.get("mitigated_by")
        if field is not None and field.queryset is not None:
            field.queryset = field.queryset.order_by("-created_at", "-id")[:200]

    def save(self, commit=True):
        # `service_label` is a DENORMALISED SNAPSHOT, not a form field: a person cannot type it
        # and it must not be able to disagree with the service they picked. Written here so the
        # finding still names what was hit after the component is retired.
        #
        # Only written when a service IS chosen. Clearing the service is a legitimate correction
        # (the finding was logged against the wrong component), and overwriting unconditionally
        # would set the snapshot to "" and destroy the very evidence meant to outlive the
        # component. Exactly the `AlertEventForm.service_label` rule.
        obj = super().save(commit=False)
        if obj.service_id:
            obj.service_label = obj.service.name
        elif obj.pk is None:
            obj.service_label = ""
        if commit:
            obj.save()
            self.save_m2m()
        return obj


class VulnerabilityFindingForm(TenantModelForm):
    class Meta:
        model = VulnerabilityFinding
        fields = ["title", "advisory_id", "finding_source", "component", "package_name",
                  "installed_version", "severity", "cvss_score", "epss_score", "fix_available",
                  "fixed_in_version", "status", "accepted_reason", "accepted_by", "due_on",
                  "first_seen_at", "last_seen_at", "scan_frequency", "remediation_note",
                  "evidence", "notes"]
        labels = {
            "scan_frequency": "Declared scan cadence (nothing in NavERP runs a scan)",
            "due_on": "Remediation deadline (blank = none set)",
            "cvss_score": "CVSS score (blank = not scored)",
            "epss_score": "EPSS score (blank = not scored)",
            "fix_available": "Fix available?",
            "severity": "Severity band (CVSS band - not the alert severity)",
            "evidence": "Evidence (where the advisory came from - NavERP ran no scanner)",
            "accepted_reason": "Why the risk is accepted (required when status is risk accepted)",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Narrowed to the tenant's ACTIVE users, and locally for the same reason 0.17 keeps its
        # queryset fixes local: a change to the shared `TenantModelForm` would alter every
        # `ModelChoiceField` in every app and put committed tests in three other apps at risk.
        # `TenantModelForm` has already narrowed this field by tenant inside `super().__init__()`;
        # this adds the "active" half on top, because accepting a risk on behalf of a deprovisioned
        # account is exactly the kind of thing an auditor asks about.
        field = self.fields.get("accepted_by")
        if field is not None and field.queryset is not None:
            field.queryset = field.queryset.filter(is_active=True).order_by("username")

    def save(self, commit=True):
        # `accepted_at` is back-filled ONLY when `accepted_by` is set and the stamp is still empty,
        # so a later edit cannot rewrite when the risk was accepted — the `AlertEventForm.first_seen_at`
        # rule. The moment a person owns an accepted risk is evidence in its own right.
        obj = super().save(commit=False)
        if obj.accepted_by_id and not obj.accepted_at:
            obj.accepted_at = timezone.now()
        if commit:
            obj.save()
            self.save_m2m()
        return obj


class SecurityIncidentForm(TenantModelForm):
    class Meta:
        model = SecurityIncident
        fields = ["title", "incident_class", "status", "severity", "discovered_at", "incident",
                  "primary_threat", "owner", "affected_services", "is_notifiable",
                  "notifiable_reason", "authority_reference", "subject_exemption",
                  "data_subjects_affected", "records_affected", "dpo_contact",
                  "likely_consequences", "measures_taken", "measures_proposed", "forensic_log",
                  "root_cause", "lessons_learned", "evidence", "notes"]
        labels = {
            "is_notifiable": "Notifiable to the supervisory authority? (blank = not yet decided)",
            "forensic_log": "Forensic narrative (what was found, preserved, and still to be "
                            "collected - a narrative, not a log pipeline)",
            "data_subjects_affected": "Approx. data subjects affected (Art. 33(3)(a))",
            "records_affected": "Approx. personal data records affected (Art. 33(3)(a))",
            "dpo_contact": "DPO contact (Art. 33(3)(b))",
            "likely_consequences": "Likely consequences (Art. 33(3)(c))",
            "measures_taken": "Measures taken (Art. 33(3)(d))",
            "measures_proposed": "Measures proposed (Art. 33(3)(d))",
            "discovered_at": "When the organisation became aware (the 72-hour clock runs from here)",
            "subject_exemption": "If data subjects were NOT notified, which Art. 34(3) exemption?",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # The ONE widget replaced in this file, and it earns it. `is_notifiable` is a nullable
        # BooleanField whose NULL means "nobody has decided yet" — a third state, and precisely the
        # state the 72-hour clock exists to pressure. A `CheckboxInput` renders it as an unchecked
        # box, which Django then reads as False: the operator cannot distinguish "we decided no"
        # from "nobody looked", so the record quietly lies about the one thing it exists to record.
        # `NullBooleanField(required=False)` with a three-state `Select` is the only widget that
        # can express all three. The field stays in `Meta.fields`; only its widget changes.
        field = self.fields.get("is_notifiable")
        if field is not None:
            field.field = forms.NullBooleanField(
                required=False,
                widget=forms.Select(choices=[("", "Not yet decided"),
                                             ("unknown", "Not yet decided"),
                                             ("true", "Notifiable"),
                                             ("false", "Not notifiable")]),
            )
            field.widget = field.field.widget
        # Capped for the same reason as 0.17's `primary_alert`: an operator asking "which firing
        # does this breach grow out of" wants recent ones. `select_related("service")` because
        # `AlertEvent.__str__` dereferences it, so an unbounded dropdown is 201 queries at 200 rows.
        field = self.fields.get("primary_threat")
        if field is not None and field.queryset is not None:
            field.queryset = (field.queryset
                              .select_related("service")
                              .order_by("-detected_at", "-id")[:200])
        field = self.fields.get("incident")
        if field is not None and field.queryset is not None:
            field.queryset = field.queryset.order_by("-created_at", "-id")[:200]

    def save(self, commit=True):
        # `owner_label` is a DENORMALISED SNAPSHOT, written only when an owner IS chosen, so the
        # record still names a responder after the account is deleted — the `service_label` rule.
        obj = super().save(commit=False)
        if obj.owner_id:
            obj.owner_label = obj.owner.get_username()
        elif obj.pk is None:
            obj.owner_label = ""
        if commit:
            obj.save()
            self.save_m2m()
        return obj
