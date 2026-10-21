import ast
import inspect
from decimal import Decimal
from pathlib import Path

import pytest
from django.test import Client
from django.utils import timezone


LEADMANAGEMENT_PAGE_SIZE = 15

LEADMANAGEMENT_MODEL_FIELDS = {
    "LeadScoreEvent": (
        "tenant", "created_at", "lead", "signal_category", "event_type", "score_delta",
        "source_kind", "source_ref", "reason", "effective_until", "idempotency_key",
        "corrects_event", "occurred_at", "recorded_by",
    ),
    "LeadQualification": (
        "tenant", "created_at", "updated_at", "lead", "framework", "status", "country_code",
        "region", "city", "industry", "employee_count", "seniority", "budget_status",
        "budget_amount", "budget_currency", "authority_level", "need_summary",
        "expected_purchase_on", "economic_buyer", "decision_criteria", "decision_process",
        "technical_requirements", "pain_points", "success_metrics", "disqualification_reason",
        "assessed_by", "assessed_at", "next_review_on", "notes",
    ),
    "LeadRoutingRule": (
        "tenant", "created_at", "updated_at", "name", "description", "is_active", "priority",
        "match_mode", "conditions", "is_catch_all", "assignment_mode", "default_owner",
        "territory", "fallback_owner", "max_open_leads", "cursor", "last_assigned_owner",
        "last_assigned_at",
    ),
    "LeadNurtureEnrollment": (
        "tenant", "created_at", "updated_at", "number", "lead", "email_campaign", "status",
        "trigger_kind", "score_at_enrollment", "consent_purpose", "consent_evidence", "owner",
        "started_at", "last_touch_at", "next_touch_at", "touch_count", "completed_at",
        "exit_reason", "notes",
    ),
}

LEADMANAGEMENT_CHOICES = {
    "LeadScoreEvent": {
        "signal_category": (
            ("behavioral", "Behavioral"), ("demographic", "Demographic"),
            ("qualification", "Qualification"), ("manual", "Manual"), ("decay", "Decay"),
            ("correction", "Correction"),
        ),
        "event_type": (
            ("form_submitted", "Form Submitted"), ("email_open", "Email Open"),
            ("email_click", "Email Click"), ("web_visit", "Website Visit"),
            ("content_download", "Content Download"), ("event_attendance", "Event Attendance"),
            ("meeting_booked", "Meeting Booked"), ("demo_request", "Demo Request"),
            ("call_connected", "Call Connected"), ("reply_received", "Reply Received"),
            ("fit_match", "Fit Match"), ("fit_mismatch", "Fit Mismatch"),
            ("unsubscribe", "Unsubscribe"), ("manual_adjustment", "Manual Adjustment"),
            ("decay", "Score Decay"), ("correction", "Correction"),
        ),
        "source_kind": (
            ("form_submission", "Form Submission"), ("campaign_member", "Campaign Member"),
            ("communication_log", "Communication Log"), ("qualification", "Qualification"),
            ("web_tracking", "Web Tracking"), ("api", "API"), ("manual", "Manual"),
        ),
    },
    "LeadQualification": {
        "framework": (("bant", "BANT"), ("meddic", "MEDDIC"), ("both", "BANT + MEDDIC")),
        "status": (
            ("unassessed", "Unassessed"), ("partially_qualified", "Partially Qualified"),
            ("qualified", "Qualified"), ("disqualified", "Disqualified"),
            ("archived", "Archived"),
        ),
        "seniority": (
            ("unknown", "Unknown"), ("individual_contributor", "Individual Contributor"),
            ("manager", "Manager"), ("director", "Director"), ("executive", "Executive"),
            ("owner", "Owner"),
        ),
        "budget_status": (
            ("unknown", "Unknown"), ("not_confirmed", "Not Confirmed"),
            ("confirmed", "Confirmed"), ("adequate", "Adequate"),
            ("insufficient", "Insufficient"),
        ),
        "authority_level": (
            ("unknown", "Unknown"), ("influencer", "Influencer"), ("user", "User"),
            ("manager", "Manager"), ("director", "Director"), ("executive", "Executive"),
            ("owner", "Owner"),
        ),
    },
    "LeadRoutingRule": {
        "match_mode": (("all", "All conditions"), ("any", "Any condition")),
        "assignment_mode": (
            ("fixed_owner", "Fixed Owner"), ("territory_manager", "Territory Manager"),
            ("round_robin", "Round Robin"),
        ),
    },
    "LeadNurtureEnrollment": {
        "status": (
            ("pending", "Pending"), ("active", "Active"), ("paused", "Paused"),
            ("completed", "Completed"), ("cancelled", "Cancelled"), ("replied", "Replied"),
            ("converted", "Converted"),
        ),
        "trigger_kind": (
            ("manual", "Manual"), ("score_threshold", "Score Threshold"),
            ("form_source", "Form Source"), ("qualification", "Qualification"),
            ("recycled", "Recycled"),
        ),
        "exit_reason": (
            ("qualified", "Qualified"), ("disqualified", "Disqualified"),
            ("replied", "Replied"), ("converted", "Converted"),
            ("unsubscribed", "Unsubscribed"), ("bounced", "Bounced"),
            ("cancelled", "Cancelled"), ("completed", "Completed"), ("manual", "Manual"),
        ),
    },
}

LEADMANAGEMENT_DECISION_STATUSES = (
    ("partially_qualified", "Partially Qualified"),
    ("qualified", "Qualified"),
    ("disqualified", "Disqualified"),
    ("archived", "Archived"),
)

LEADMANAGEMENT_RELATION_FIELDS = {
    "LeadScoreEvent": {
        "tenant": ("core.Tenant", "CASCADE", "+", False, False, True),
        "lead": ("crm.Lead", "PROTECT", "sales_score_events", False, False, True),
        "corrects_event": ("sales.LeadScoreEvent", "SET_NULL", "corrections", True, True, True),
        "recorded_by": ("accounts.User", "SET_NULL", "sales_recorded_score_events", True, True, False),
    },
    "LeadQualification": {
        "tenant": ("core.Tenant", "CASCADE", "+", False, False, True),
        "lead": ("crm.Lead", "PROTECT", "sales_qualification", False, False, True),
        "budget_currency": ("accounting.Currency", "SET_NULL", "+", True, True, True),
        "assessed_by": ("accounts.User", "SET_NULL", "sales_lead_assessments", True, True, True),
    },
    "LeadRoutingRule": {
        "tenant": ("core.Tenant", "CASCADE", "+", False, False, True),
        "default_owner": ("accounts.User", "SET_NULL", "sales_default_routing_rules", True, True, True),
        "territory": ("crm.Territory", "SET_NULL", "sales_routing_rules", True, True, True),
        "fallback_owner": ("accounts.User", "SET_NULL", "sales_fallback_routing_rules", True, True, True),
        "last_assigned_owner": ("accounts.User", "SET_NULL", "sales_last_routing_rules", True, True, False),
    },
    "LeadNurtureEnrollment": {
        "tenant": ("core.Tenant", "CASCADE", "+", False, False, True),
        "lead": ("crm.Lead", "PROTECT", "sales_nurture_enrollments", False, False, True),
        "email_campaign": ("crm.EmailCampaign", "PROTECT", "sales_nurture_enrollments", False, False, True),
        "consent_purpose": ("core.ConsentPurpose", "PROTECT", "sales_nurture_enrollments", True, True, True),
        "owner": ("accounts.User", "SET_NULL", "sales_nurture_enrollments", True, True, True),
    },
}

LEADMANAGEMENT_M2M_FIELDS = {
    "LeadRoutingRule": {
        "eligible_owners": ("accounts.User", True, "sales_routing_rules"),
    },
}

LEADMANAGEMENT_UNIQUE_CONSTRAINTS = {
    "LeadScoreEvent": {
        ("sales_lse_tenant_key_uniq", ("tenant", "idempotency_key")),
    },
    "LeadQualification": set(),
    "LeadRoutingRule": {
        ("sales_lrr_tenant_name_uniq", ("tenant", "name")),
    },
    "LeadNurtureEnrollment": {
        ("sales_lne_tenant_lead_campaign_uniq", ("tenant", "lead", "email_campaign")),
        ("sales_lne_tenant_number_uniq", ("tenant", "number")),
    },
}

LEADMANAGEMENT_INDEXES = {
    "LeadScoreEvent": {
        ("sales_lse_tnt_lead_idx", ("tenant", "lead", "-occurred_at")),
        ("sales_lse_tnt_type_idx", ("tenant", "event_type", "-occurred_at")),
        ("sales_lse_tnt_source_idx", ("tenant", "source_kind", "source_ref")),
    },
    "LeadQualification": {
        ("sales_lq_tnt_status_idx", ("tenant", "status")),
        ("sales_lq_tnt_framework_idx", ("tenant", "framework")),
        ("sales_lq_tnt_review_idx", ("tenant", "next_review_on")),
    },
    "LeadRoutingRule": {
        ("sales_lrr_tnt_active_idx", ("tenant", "is_active", "priority")),
        ("sales_lrr_tnt_mode_idx", ("tenant", "assignment_mode")),
    },
    "LeadNurtureEnrollment": {
        ("sales_lne_tnt_status_idx", ("tenant", "status", "next_touch_at")),
        ("sales_lne_tnt_campaign_idx", ("tenant", "email_campaign", "status")),
    },
}

LEADMANAGEMENT_FIELD_DEFAULTS = {
    "LeadQualification": {
        "framework": "bant",
        "status": "unassessed",
        "seniority": "unknown",
        "budget_status": "unknown",
        "authority_level": "unknown",
    },
    "LeadRoutingRule": {
        "is_active": True,
        "priority": 100,
        "match_mode": "all",
        "conditions": [],
        "is_catch_all": False,
    },
    "LeadNurtureEnrollment": {
        "status": "pending",
        "trigger_kind": "manual",
        "score_at_enrollment": None,
        "touch_count": 0,
    },
}

LEADMANAGEMENT_FORM_FIELDS = {
    "LeadScoreAdjustmentForm": ("lead", "score_delta", "reason"),
    "LeadScoreCorrectionForm": ("lead", "corrects_event", "score_delta", "reason"),
    "LeadQualificationForm": (
        "lead", "framework", "country_code", "region", "city", "industry", "employee_count",
        "seniority", "budget_status", "budget_amount", "budget_currency", "authority_level",
        "need_summary", "expected_purchase_on", "economic_buyer", "decision_criteria",
        "decision_process", "technical_requirements", "pain_points", "success_metrics",
        "next_review_on", "notes",
    ),
    "LeadQualificationDecisionForm": ("status", "disqualification_reason", "notes"),
    "LeadRoutingRuleForm": (
        "name", "description", "is_active", "priority", "match_mode", "conditions",
        "is_catch_all", "assignment_mode", "default_owner", "territory", "eligible_owners",
        "fallback_owner", "max_open_leads",
    ),
    "LeadRoutingPreviewForm": ("lead",),
    "LeadRoutingRunForm": ("lead",),
    "LeadNurtureEnrollmentForm": (
        "lead", "email_campaign", "trigger_kind", "consent_purpose", "consent_evidence",
        "owner", "notes",
    ),
    "LeadNurtureActivationForm": ("next_touch_at",),
    "LeadNurtureExitForm": ("exit_reason", "notes"),
}

LEADMANAGEMENT_URLS = {
    "sales_root": "",
    "lead_overview": "overview/",
    "lead_handoff": "leads/<int:pk>/handoff/",
    "lead_score_event_list": "score-events/",
    "lead_score_event_adjust": "score-events/adjust/",
    "lead_score_event_recompute": "score-events/recompute/",
    "lead_score_event_detail": "score-events/<int:pk>/",
    "lead_score_event_correct": "score-events/<int:pk>/correct/",
    "lead_qualification_list": "qualifications/",
    "lead_qualification_create": "qualifications/add/",
    "lead_qualification_detail": "qualifications/<int:pk>/",
    "lead_qualification_edit": "qualifications/<int:pk>/edit/",
    "lead_qualification_delete": "qualifications/<int:pk>/delete/",
    "lead_qualification_partial": "qualifications/<int:pk>/partial/",
    "lead_qualification_qualify": "qualifications/<int:pk>/qualify/",
    "lead_qualification_disqualify": "qualifications/<int:pk>/disqualify/",
    "lead_qualification_archive": "qualifications/<int:pk>/archive/",
    "lead_qualification_recalculate": "qualifications/<int:pk>/recalculate/",
    "lead_qualification_route_preview": "qualifications/<int:pk>/route-preview/",
    "lead_routing_rule_list": "routing-rules/",
    "lead_routing_rule_create": "routing-rules/add/",
    "lead_routing_rule_detail": "routing-rules/<int:pk>/",
    "lead_routing_rule_edit": "routing-rules/<int:pk>/edit/",
    "lead_routing_rule_delete": "routing-rules/<int:pk>/delete/",
    "lead_routing_rule_toggle": "routing-rules/<int:pk>/toggle/",
    "lead_routing_rule_preview": "routing-rules/<int:pk>/preview/",
    "lead_routing_rule_run": "routing-rules/<int:pk>/run/",
    "lead_nurture_enrollment_list": "nurture-enrollments/",
    "lead_nurture_enrollment_create": "nurture-enrollments/add/",
    "lead_nurture_enrollment_detail": "nurture-enrollments/<int:pk>/",
    "lead_nurture_enrollment_edit": "nurture-enrollments/<int:pk>/edit/",
    "lead_nurture_enrollment_delete": "nurture-enrollments/<int:pk>/delete/",
    "lead_nurture_enrollment_activate": "nurture-enrollments/<int:pk>/activate/",
    "lead_nurture_enrollment_pause": "nurture-enrollments/<int:pk>/pause/",
    "lead_nurture_enrollment_resume": "nurture-enrollments/<int:pk>/resume/",
    "lead_nurture_enrollment_complete": "nurture-enrollments/<int:pk>/complete/",
    "lead_nurture_enrollment_cancel": "nurture-enrollments/<int:pk>/cancel/",
    "lead_nurture_enrollment_reply": "nurture-enrollments/<int:pk>/reply/",
    "lead_nurture_enrollment_convert_exit": "nurture-enrollments/<int:pk>/convert-exit/",
}

LEADMANAGEMENT_URL_VIEWS = {
    name: ("lead_overview" if name == "sales_root" else name)
    for name in LEADMANAGEMENT_URLS
}

LEADMANAGEMENT_VIEW_CONTEXT_KEYS = {
    "lead_overview": frozenset({
        "stats", "leads", "qualifications", "routing_rules", "enrollments",
        "enrollment_states", "enrollment_labels", "latest_score_events", "duplicate_warnings",
        "recent_activity",
    }),
    "lead_handoff": frozenset(),
    "lead_score_event_list": frozenset({
        "object_list", "page_obj", "q", "date_from", "date_to", "signal_category_choices",
        "event_type_choices", "source_kind_choices", "leads",
    }),
    "lead_score_event_detail": frozenset({
        "obj", "lead", "projection_score", "projection_rating", "inverse_score_delta",
        "can_correct",
    }),
    "lead_score_event_adjust": frozenset(),
    "lead_score_event_correct": frozenset(),
    "lead_score_event_recompute": frozenset(),
    "lead_qualification_list": frozenset({
        "object_list", "page_obj", "q", "status_choices", "framework_choices",
        "seniority_choices", "budget_status_choices", "authority_level_choices", "assessors",
        "review_due", "leads",
    }),
    "lead_qualification_create": frozenset({"form", "is_edit", "leads"}),
    "lead_qualification_detail": frozenset({
        "obj", "lead", "score_events", "enrollments", "routing_preview", "preview_form",
        "decision_form",
    }),
    "lead_qualification_edit": frozenset({"form", "obj", "is_edit", "leads"}),
    "lead_qualification_delete": frozenset(),
    "lead_qualification_partial": frozenset(),
    "lead_qualification_qualify": frozenset(),
    "lead_qualification_disqualify": frozenset(),
    "lead_qualification_archive": frozenset(),
    "lead_qualification_recalculate": frozenset(),
    "lead_qualification_route_preview": frozenset({
        "obj", "lead", "score_events", "enrollments", "routing_preview", "preview_form",
        "decision_form",
    }),
    "lead_routing_rule_list": frozenset({
        "object_list", "page_obj", "q", "assignment_mode_choices", "match_mode_choices",
        "active_choices", "territories", "users",
    }),
    "lead_routing_rule_create": frozenset({"form", "is_edit", "territories", "users"}),
    "lead_routing_rule_detail": frozenset({
        "obj", "eligible_owners", "leads", "preview_form", "preview_result", "conditions_json",
    }),
    "lead_routing_rule_edit": frozenset({"form", "obj", "is_edit", "territories", "users"}),
    "lead_routing_rule_delete": frozenset(),
    "lead_routing_rule_toggle": frozenset(),
    "lead_routing_rule_preview": frozenset({
        "obj", "eligible_owners", "leads", "preview_form", "preview_result", "conditions_json",
    }),
    "lead_routing_rule_run": frozenset(),
    "lead_nurture_enrollment_list": frozenset({
        "object_list", "page_obj", "q", "status_choices", "trigger_kind_choices", "drip_campaigns",
        "owners", "leads", "next_touch",
    }),
    "lead_nurture_enrollment_create": frozenset({
        "form", "is_edit", "leads", "drip_campaigns", "consent_purposes", "owners",
    }),
    "lead_nurture_enrollment_detail": frozenset({
        "obj", "lead", "email_campaign", "consent_purpose", "activation_form", "exit_form",
    }),
    "lead_nurture_enrollment_edit": frozenset({
        "form", "obj", "is_edit", "leads", "drip_campaigns", "consent_purposes", "owners",
    }),
    "lead_nurture_enrollment_delete": frozenset(),
    "lead_nurture_enrollment_activate": frozenset(),
    "lead_nurture_enrollment_pause": frozenset(),
    "lead_nurture_enrollment_resume": frozenset(),
    "lead_nurture_enrollment_complete": frozenset(),
    "lead_nurture_enrollment_cancel": frozenset(),
    "lead_nurture_enrollment_reply": frozenset(),
    "lead_nurture_enrollment_convert_exit": frozenset(),
}

LEADMANAGEMENT_EVENT_DELTAS = {
    "form_submitted": 5,
    "email_open": 2,
    "email_click": 8,
    "web_visit": 1,
    "content_download": 6,
    "event_attendance": 4,
    "meeting_booked": 10,
    "demo_request": 15,
    "call_connected": 8,
    "reply_received": 12,
    "fit_match": 20,
    "fit_mismatch": -15,
    "unsubscribe": -25,
    "decay": -5,
}

LEADMANAGEMENT_SCORE_BANDS = ((0, 39, "cold"), (40, 69, "warm"), (70, 100, "hot"))

LEADMANAGEMENT_ROUTING_FIELDS = frozenset({
    "source", "status", "rating", "score", "est_value", "owner_id", "company", "title",
    "email_present", "phone_present", "qualification_status", "framework", "country_code",
    "region", "city", "industry", "employee_count", "seniority", "budget_status",
    "authority_level", "expected_purchase_on",
})

LEADMANAGEMENT_ROUTING_OPERATORS = frozenset({
    "eq", "ne", "in", "not_in", "contains", "icontains", "gt", "gte", "lt", "lte", "is_set",
    "is_empty",
})

LEADMANAGEMENT_ROUTING_LIMITS = (20, 16 * 1024)

LEADMANAGEMENT_NURTURE_EXIT_TARGETS = {
    "completed": frozenset({"completed"}),
    "cancelled": frozenset({
        "cancelled", "qualified", "disqualified", "unsubscribed", "bounced", "manual",
    }),
    "replied": frozenset({"replied"}),
    "converted": frozenset({"converted"}),
}


def _leadmanagement_tenant_id(tenant):
    return getattr(tenant, "pk", tenant)


def _leadmanagement_assert_same_tenant(tenant, **relations):
    tenant_id = _leadmanagement_tenant_id(tenant)
    for name, record in relations.items():
        if record is not None:
            assert record.tenant_id == tenant_id, f"{name} must belong to the requested tenant"


def _leadmanagement_assert_global(record):
    assert not hasattr(record, "tenant_id"), "global masters must not have a tenant FK"


def _leadmanagement_account(tenant, **overrides):
    from apps.core.models import Party

    fields = {
        "tenant": tenant,
        "kind": "organization",
        "name": f"{tenant.slug.title()} Test Account",
    }
    fields.update(overrides)
    return Party.objects.create(**fields)


def _leadmanagement_lead(tenant, owner=None, **overrides):
    from apps.crm.models import Lead

    _leadmanagement_assert_same_tenant(tenant, owner=owner)
    label = tenant.slug.title()
    fields = {
        "tenant": tenant,
        "owner": owner,
        "name": f"{label} Lead",
        "company": f"{label} Industries",
        "title": "Operations Director",
        "email": f"lead@{tenant.slug}.example",
        "phone": "+1-555-0100",
        "source": "web",
        "rating": "warm",
        "status": "new",
        "score": 25,
        "est_value": Decimal("75000.00"),
        "description": "Deterministic tenant-safe 8.1 lead fixture.",
    }
    fields.update(overrides)
    return Lead.objects.create(**fields)


def _leadmanagement_opportunity(tenant, lead, account, currency=None, owner=None, **overrides):
    from apps.crm.models import Opportunity

    _leadmanagement_assert_same_tenant(tenant, lead=lead, account=account, owner=owner)
    _leadmanagement_assert_global(currency)
    label = tenant.slug.title()
    fields = {
        "tenant": tenant,
        "account": account,
        "primary_contact": None,
        "stage": "qualification",
        "forecast_category": "pipeline",
        "amount": Decimal("75000.00"),
        "currency": currency,
        "probability": 40,
        "close_date": timezone.localdate() + timezone.timedelta(days=45),
        "owner": owner,
        "source_lead": lead,
        "next_step": "Confirm the qualified buying committee.",
        "next_step_due_date": timezone.localdate() + timezone.timedelta(days=7),
        "description": f"{label} qualification opportunity linked to the canonical lead.",
    }
    fields.update(overrides)
    return Opportunity.objects.create(**fields)


def _leadmanagement_territory(tenant, manager=None, **overrides):
    from apps.crm.models import Territory

    _leadmanagement_assert_same_tenant(tenant, manager=manager)
    label = tenant.slug.title()
    fields = {
        "tenant": tenant,
        "name": f"{label} Territory",
        "region": "North",
        "segment": "Mid-market",
        "manager": manager,
        "is_active": True,
        "description": "Deterministic active routing territory.",
    }
    fields.update(overrides)
    return Territory.objects.create(**fields)


def _leadmanagement_campaign(tenant, owner=None, **overrides):
    from apps.crm.models import Campaign

    _leadmanagement_assert_same_tenant(tenant, owner=owner)
    label = tenant.slug.title()
    fields = {
        "tenant": tenant,
        "name": f"{label} Nurture Campaign",
        "type": "email",
        "objective": "nurture",
        "status": "active",
        "start_date": timezone.localdate(),
        "budget_planned": Decimal("10000.00"),
        "budget_actual": Decimal("0.00"),
        "expected_revenue": Decimal("50000.00"),
        "actual_revenue": Decimal("0.00"),
        "target_size": 100,
        "owner": owner,
        "description": "Canonical CRM campaign used by the 8.1 nurture fixture.",
    }
    fields.update(overrides)
    return Campaign.objects.create(**fields)


def _leadmanagement_email_campaign(tenant, campaign, owner=None, **overrides):
    from apps.crm.models import EmailCampaign

    _leadmanagement_assert_same_tenant(tenant, campaign=campaign, owner=owner)
    label = tenant.slug.title()
    fields = {
        "tenant": tenant,
        "campaign": campaign,
        "name": f"{label} Drip Campaign",
        "send_type": "drip",
        "status": "scheduled",
        "scheduled_at": timezone.now() + timezone.timedelta(days=7),
        "owner": owner,
    }
    fields.update(overrides)
    return EmailCampaign.objects.create(**fields)


def _leadmanagement_consent_purpose(tenant, **overrides):
    from apps.core.models import ConsentPurpose

    fields = {
        "tenant": tenant,
        "name": "Marketing Email",
        "code": "marketing-email",
        "lawful_basis": "consent",
        "is_optional": True,
        "description": "Consent purpose reference for deterministic 8.1 tests.",
        "is_active": True,
    }
    fields.update(overrides)
    return ConsentPurpose.objects.create(**fields)


def _leadmanagement_score_event(
    tenant,
    lead,
    recorded_by=None,
    event_type="form_submitted",
    **overrides,
):
    from apps.sales.services import record_score_event

    _leadmanagement_assert_same_tenant(tenant, lead=lead, recorded_by=recorded_by)
    source_kind = "manual" if event_type in {"manual_adjustment", "correction"} else "form_submission"
    if event_type in {"fit_match", "fit_mismatch"}:
        source_kind = "qualification"
    values = {
        "score_delta": None,
        "signal_category": None,
        "source_kind": source_kind,
        "source_ref": f"leadmanagement:{event_type}",
        "reason": "Deterministic scoring fact for the 8.1 suite.",
        "idempotency_key": None,
    }
    values.update(overrides)
    return record_score_event(lead, tenant, event_type=event_type, recorded_by=recorded_by, **values)


def _leadmanagement_qualification(tenant, lead, currency, assessed_by=None, **overrides):
    from apps.sales.models import LeadQualification

    _leadmanagement_assert_same_tenant(tenant, lead=lead, assessed_by=assessed_by)
    _leadmanagement_assert_global(currency)
    fields = {
        "tenant": tenant,
        "lead": lead,
        "framework": "bant",
        "status": "unassessed",
        "country_code": "US",
        "region": "North",
        "city": "Springfield",
        "industry": "Industrial Technology",
        "employee_count": 240,
        "seniority": "director",
        "budget_status": "confirmed",
        "budget_amount": Decimal("75000.00"),
        "budget_currency": currency,
        "authority_level": "director",
        "need_summary": "Replace fragmented lead intake and manual territory assignment.",
        "expected_purchase_on": timezone.localdate() + timezone.timedelta(days=45),
        "economic_buyer": "Operations Director",
        "decision_criteria": "Time to value, adoption, and total operating cost.",
        "decision_process": "Director review followed by finance approval.",
        "technical_requirements": "CRM integration and role-based access.",
        "pain_points": "Slow routing and inconsistent qualification evidence.",
        "success_metrics": "Reduce response time and improve qualified conversion.",
        "assessed_by": assessed_by,
        "next_review_on": timezone.localdate() + timezone.timedelta(days=14),
        "notes": "Deterministic unassessed BANT fixture.",
    }
    fields.update(overrides)
    obj = LeadQualification(**fields)
    obj.full_clean()
    obj.save()
    return obj


def _leadmanagement_routing_rule(
    tenant,
    default_owner=None,
    territory=None,
    eligible_owners=(),
    fallback_owner=None,
    **overrides,
):
    from apps.sales.models import LeadRoutingRule

    _leadmanagement_assert_same_tenant(
        tenant,
        default_owner=default_owner,
        territory=territory,
        fallback_owner=fallback_owner,
    )
    for owner in eligible_owners:
        _leadmanagement_assert_same_tenant(tenant, eligible_owner=owner)
    fields = {
        "tenant": tenant,
        "name": "Active lead fixed owner",
        "description": "Routes new leads to the tenant administrator.",
        "is_active": True,
        "priority": 10,
        "match_mode": "all",
        "conditions": [{"field": "status", "operator": "eq", "value": "new"}],
        "is_catch_all": False,
        "assignment_mode": "fixed_owner",
        "default_owner": default_owner,
        "territory": territory,
        "fallback_owner": fallback_owner,
        "max_open_leads": 25,
    }
    fields.update(overrides)
    obj = LeadRoutingRule(**fields)
    obj.full_clean()
    obj.save()
    obj.eligible_owners.set(eligible_owners)
    obj.full_clean()
    return obj


def _leadmanagement_nurture_enrollment(
    tenant,
    lead,
    email_campaign,
    consent_purpose,
    owner=None,
    **overrides,
):
    from apps.sales.models import LeadNurtureEnrollment

    _leadmanagement_assert_same_tenant(
        tenant,
        lead=lead,
        email_campaign=email_campaign,
        consent_purpose=consent_purpose,
        owner=owner,
    )
    fields = {
        "tenant": tenant,
        "lead": lead,
        "email_campaign": email_campaign,
        "status": "pending",
        "trigger_kind": "manual",
        "consent_purpose": consent_purpose,
        "consent_evidence": "Consent reference captured in fixture evidence.",
        "owner": owner,
        "next_touch_at": timezone.now() + timezone.timedelta(days=3),
        "notes": "State-only nurture enrollment; no ESP or worker exists.",
    }
    fields.update(overrides)
    obj = LeadNurtureEnrollment(**fields)
    obj.save()
    obj.full_clean()
    return obj


@pytest.fixture
def leadmanagement_tenant_a(tenant_a):
    return tenant_a


@pytest.fixture
def leadmanagement_tenant_b(tenant_b):
    return tenant_b


@pytest.fixture
def leadmanagement_admin_a(admin_user):
    return admin_user


@pytest.fixture
def leadmanagement_member_a(member_user):
    return member_user


@pytest.fixture
def leadmanagement_admin_b(admin_b):
    return admin_b


@pytest.fixture
def leadmanagement_member_b(db, tenant_b):
    from apps.accounts.models import User

    return User.objects.create_user(
        email="member@globex.com",
        username="member_globex",
        password="TestPass123!",
        tenant=tenant_b,
        is_tenant_admin=False,
    )


@pytest.fixture
def leadmanagement_admin_client_a(client_a):
    return client_a


@pytest.fixture
def leadmanagement_member_client_a(member_client):
    return member_client


@pytest.fixture
def leadmanagement_admin_client_b(client_b):
    return client_b


@pytest.fixture
def leadmanagement_member_client_b(db, leadmanagement_member_b):
    client = Client()
    client.force_login(leadmanagement_member_b)
    return client


@pytest.fixture
def leadmanagement_currency(db):
    from apps.accounting.models import Currency

    obj, _ = Currency.objects.get_or_create(
        code="USD",
        defaults={"name": "US Dollar", "symbol": "$"},
    )
    return obj


@pytest.fixture
def leadmanagement_account_a(db, leadmanagement_tenant_a):
    return _leadmanagement_account(leadmanagement_tenant_a)


@pytest.fixture
def leadmanagement_account_b(db, leadmanagement_tenant_b):
    return _leadmanagement_account(leadmanagement_tenant_b)


@pytest.fixture
def leadmanagement_lead_a(db, leadmanagement_tenant_a, leadmanagement_admin_a):
    return _leadmanagement_lead(leadmanagement_tenant_a, owner=leadmanagement_admin_a)


@pytest.fixture
def leadmanagement_lead_b(db, leadmanagement_tenant_b, leadmanagement_admin_b):
    return _leadmanagement_lead(leadmanagement_tenant_b, owner=leadmanagement_admin_b)


@pytest.fixture
def leadmanagement_opportunity_a(
    db,
    leadmanagement_tenant_a,
    leadmanagement_account_a,
    leadmanagement_lead_a,
    leadmanagement_currency,
    leadmanagement_admin_a,
):
    return _leadmanagement_opportunity(
        leadmanagement_tenant_a,
        leadmanagement_lead_a,
        leadmanagement_account_a,
        currency=leadmanagement_currency,
        owner=leadmanagement_admin_a,
    )


@pytest.fixture
def leadmanagement_opportunity_b(
    db,
    leadmanagement_tenant_b,
    leadmanagement_account_b,
    leadmanagement_lead_b,
    leadmanagement_currency,
    leadmanagement_admin_b,
):
    return _leadmanagement_opportunity(
        leadmanagement_tenant_b,
        leadmanagement_lead_b,
        leadmanagement_account_b,
        currency=leadmanagement_currency,
        owner=leadmanagement_admin_b,
    )


@pytest.fixture
def leadmanagement_territory_a(db, leadmanagement_tenant_a, leadmanagement_admin_a):
    return _leadmanagement_territory(leadmanagement_tenant_a, manager=leadmanagement_admin_a)


@pytest.fixture
def leadmanagement_territory_b(db, leadmanagement_tenant_b, leadmanagement_admin_b):
    return _leadmanagement_territory(leadmanagement_tenant_b, manager=leadmanagement_admin_b)


@pytest.fixture
def leadmanagement_campaign_a(db, leadmanagement_tenant_a, leadmanagement_admin_a):
    return _leadmanagement_campaign(leadmanagement_tenant_a, owner=leadmanagement_admin_a)


@pytest.fixture
def leadmanagement_campaign_b(db, leadmanagement_tenant_b, leadmanagement_admin_b):
    return _leadmanagement_campaign(leadmanagement_tenant_b, owner=leadmanagement_admin_b)


@pytest.fixture
def leadmanagement_email_campaign_a(
    db,
    leadmanagement_tenant_a,
    leadmanagement_campaign_a,
    leadmanagement_admin_a,
):
    return _leadmanagement_email_campaign(
        leadmanagement_tenant_a,
        leadmanagement_campaign_a,
        owner=leadmanagement_admin_a,
    )


@pytest.fixture
def leadmanagement_email_campaign_b(
    db,
    leadmanagement_tenant_b,
    leadmanagement_campaign_b,
    leadmanagement_admin_b,
):
    return _leadmanagement_email_campaign(
        leadmanagement_tenant_b,
        leadmanagement_campaign_b,
        owner=leadmanagement_admin_b,
    )


@pytest.fixture
def leadmanagement_consent_purpose_a(db, leadmanagement_tenant_a):
    return _leadmanagement_consent_purpose(leadmanagement_tenant_a)


@pytest.fixture
def leadmanagement_consent_purpose_b(db, leadmanagement_tenant_b):
    return _leadmanagement_consent_purpose(leadmanagement_tenant_b)


@pytest.fixture
def leadmanagement_score_event_a(db, leadmanagement_tenant_a, leadmanagement_lead_a, leadmanagement_admin_a):
    return _leadmanagement_score_event(
        leadmanagement_tenant_a,
        leadmanagement_lead_a,
        recorded_by=leadmanagement_admin_a,
    )


@pytest.fixture
def leadmanagement_score_event_b(db, leadmanagement_tenant_b, leadmanagement_lead_b, leadmanagement_admin_b):
    return _leadmanagement_score_event(
        leadmanagement_tenant_b,
        leadmanagement_lead_b,
        recorded_by=leadmanagement_admin_b,
    )


@pytest.fixture
def leadmanagement_qualification_a(
    db,
    leadmanagement_tenant_a,
    leadmanagement_lead_a,
    leadmanagement_currency,
):
    return _leadmanagement_qualification(
        leadmanagement_tenant_a,
        leadmanagement_lead_a,
        leadmanagement_currency,
    )


@pytest.fixture
def leadmanagement_qualification_b(
    db,
    leadmanagement_tenant_b,
    leadmanagement_lead_b,
    leadmanagement_currency,
):
    return _leadmanagement_qualification(
        leadmanagement_tenant_b,
        leadmanagement_lead_b,
        leadmanagement_currency,
    )


@pytest.fixture
def leadmanagement_routing_rule_a(db, leadmanagement_tenant_a, leadmanagement_admin_a):
    return _leadmanagement_routing_rule(
        leadmanagement_tenant_a,
        default_owner=leadmanagement_admin_a,
    )


@pytest.fixture
def leadmanagement_routing_rule_b(db, leadmanagement_tenant_b, leadmanagement_admin_b):
    return _leadmanagement_routing_rule(
        leadmanagement_tenant_b,
        default_owner=leadmanagement_admin_b,
    )


@pytest.fixture
def leadmanagement_nurture_enrollment_a(
    db,
    leadmanagement_tenant_a,
    leadmanagement_lead_a,
    leadmanagement_email_campaign_a,
    leadmanagement_consent_purpose_a,
    leadmanagement_admin_a,
):
    return _leadmanagement_nurture_enrollment(
        leadmanagement_tenant_a,
        leadmanagement_lead_a,
        leadmanagement_email_campaign_a,
        leadmanagement_consent_purpose_a,
        owner=leadmanagement_admin_a,
    )


@pytest.fixture
def leadmanagement_nurture_enrollment_b(
    db,
    leadmanagement_tenant_b,
    leadmanagement_lead_b,
    leadmanagement_email_campaign_b,
    leadmanagement_consent_purpose_b,
    leadmanagement_admin_b,
):
    return _leadmanagement_nurture_enrollment(
        leadmanagement_tenant_b,
        leadmanagement_lead_b,
        leadmanagement_email_campaign_b,
        leadmanagement_consent_purpose_b,
        owner=leadmanagement_admin_b,
    )


def _leadmanagement_dict_keys(node):
    if not isinstance(node, ast.Dict):
        return set()
    return {
        key.value
        for key in node.keys
        if isinstance(key, ast.Constant) and isinstance(key.value, str)
    }


def _leadmanagement_extra_context(call):
    for keyword in call.keywords:
        if keyword.arg == "extra_context":
            return _leadmanagement_dict_keys(keyword.value)
    return set()


def _leadmanagement_view_context_keys(view):
    module = inspect.getmodule(view)
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    function = next(
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == view.__name__
    )
    keys = set()
    for node in ast.walk(function):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Attribute):
            call_name = node.func.attr
        elif isinstance(node.func, ast.Name):
            call_name = node.func.id
        else:
            continue
        if call_name == "render":
            for argument in node.args:
                keys.update(_leadmanagement_dict_keys(argument))
        elif call_name == "crud_list":
            keys.update({"object_list", "page_obj", "q"})
            keys.update(_leadmanagement_extra_context(node))
        elif call_name == "crud_create":
            keys.update({"form", "is_edit"})
            keys.update(_leadmanagement_extra_context(node))
        elif call_name == "crud_edit":
            keys.update({"form", "obj", "is_edit"})
            keys.update(_leadmanagement_extra_context(node))
    return frozenset(keys)


def test_leadmanagement_contract_models():
    from django.conf import settings
    from django.db import models as django_models
    from apps.sales import models as sales_models

    assert settings.DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3"
    assert settings.DATABASES["default"]["NAME"] == ":memory:"
    classes = {
        "LeadScoreEvent": sales_models.LeadScoreEvent,
        "LeadQualification": sales_models.LeadQualification,
        "LeadRoutingRule": sales_models.LeadRoutingRule,
        "LeadNurtureEnrollment": sales_models.LeadNurtureEnrollment,
    }
    delete_functions = {
        "CASCADE": django_models.CASCADE,
        "PROTECT": django_models.PROTECT,
        "SET_NULL": django_models.SET_NULL,
    }
    for name, model in classes.items():
        actual_fields = tuple(
            field.name
            for field in model._meta.fields
            if not field.primary_key
        )
        assert actual_fields == LEADMANAGEMENT_MODEL_FIELDS[name]
        for field_name, expected_choices in LEADMANAGEMENT_CHOICES.get(name, {}).items():
            actual_choices = tuple(tuple(choice) for choice in model._meta.get_field(field_name).choices)
            assert actual_choices == expected_choices
        for field_name, expected in LEADMANAGEMENT_RELATION_FIELDS.get(name, {}).items():
            field = model._meta.get_field(field_name)
            actual = (
                field.related_model._meta.label,
                field.remote_field.on_delete.__name__,
                field.remote_field.related_name,
                field.null,
                field.blank,
                field.editable,
            )
            target, delete_name, related_name, null, blank, editable = expected
            assert actual == (target, delete_name, related_name, null, blank, editable)
            assert field.remote_field.on_delete is delete_functions[delete_name]
        for field_name, expected in LEADMANAGEMENT_M2M_FIELDS.get(name, {}).items():
            field = model._meta.get_field(field_name)
            target, blank, related_name = expected
            assert field.related_model._meta.label == target
            assert field.blank == blank
            assert field.remote_field.related_name == related_name
        actual_constraints = {
            (
                constraint.name,
                tuple(field if isinstance(field, str) else field.name for field in constraint.fields),
            )
            for constraint in model._meta.constraints
        }
        assert actual_constraints == LEADMANAGEMENT_UNIQUE_CONSTRAINTS[name]
        actual_indexes = {
            (index.name, tuple(index.fields))
            for index in model._meta.indexes
        }
        assert actual_indexes == LEADMANAGEMENT_INDEXES[name]
        for field_name, expected in LEADMANAGEMENT_FIELD_DEFAULTS.get(name, {}).items():
            field = model._meta.get_field(field_name)
            actual_default = field.default() if callable(field.default) else field.default
            expected_default = expected() if callable(expected) else expected
            if actual_default.__class__.__name__ == "NOT_PROVIDED" and expected_default is None:
                continue
            assert actual_default == expected_default
    assert sales_models.LeadNurtureEnrollment.NUMBER_PREFIX == "LNE"
    assert sales_models.LeadNurtureEnrollment._meta.get_field("number").max_length == 20
    assert sales_models.LeadNurtureEnrollment._meta.get_field("number").editable is False


def test_leadmanagement_contract_forms():
    from apps.sales import forms

    for name, expected_fields in LEADMANAGEMENT_FORM_FIELDS.items():
        form_class = getattr(forms, name)
        assert tuple(form_class.base_fields) == expected_fields
        if hasattr(form_class, "_meta") and getattr(form_class._meta, "model", None):
            assert tuple(form_class._meta.fields) == expected_fields
    assert tuple(forms.LeadQualificationDecisionForm.base_fields["status"].choices) == LEADMANAGEMENT_DECISION_STATUSES


def test_leadmanagement_contract_urls():
    from django.urls import reverse
    from apps.sales import urls as sales_urls

    assert sales_urls.app_name == "sales"
    patterns = {pattern.name: pattern for pattern in sales_urls.urlpatterns if pattern.name}
    for name, route in LEADMANAGEMENT_URLS.items():
        assert name in patterns
        assert str(patterns[name].pattern) == route
        assert patterns[name].callback.__name__ == LEADMANAGEMENT_URL_VIEWS[name]
        kwargs = {"pk": 1} if "<int:pk>" in route else {}
        assert reverse(f"sales:{name}", kwargs=kwargs) == f"/sales/{route}".replace("<int:pk>", "1")


def test_leadmanagement_contract_contexts():
    from apps.sales import views as sales_views

    for view_name, expected_keys in LEADMANAGEMENT_VIEW_CONTEXT_KEYS.items():
        view = getattr(sales_views, view_name)
        assert _leadmanagement_view_context_keys(view) == expected_keys, view_name


def _contactaccountmanagement_tenant_id(tenant):
    return getattr(tenant, "pk", tenant)


def _contactaccountmanagement_assert_same_tenant(tenant, **relations):
    tenant_id = _contactaccountmanagement_tenant_id(tenant)
    for name, record in relations.items():
        if record is not None:
            assert record.tenant_id == tenant_id, f"{name} must belong to the requested tenant"


def _contactaccountmanagement_user(tenant, key, *, is_tenant_admin=False, **overrides):
    from apps.accounts.models import User

    fields = {
        "email": f"{key}@{tenant.slug}.example",
        "username": f"{key}_{tenant.slug}",
        "password": "TestPass123!",
        "tenant": tenant,
        "is_tenant_admin": is_tenant_admin,
    }
    fields.update(overrides)
    fields["tenant"] = tenant
    return User.objects.create_user(**fields)


def _contactaccountmanagement_party(tenant, kind, name, **overrides):
    from apps.core.models import Party

    fields = {
        "tenant": tenant,
        "kind": kind,
        "name": name,
    }
    fields.update(overrides)
    fields["tenant"] = tenant
    fields["kind"] = kind
    party = Party(**fields)
    party.full_clean()
    party.save()
    return party


def _contactaccountmanagement_organization_party(tenant, *, name=None, **overrides):
    return _contactaccountmanagement_party(
        tenant,
        "organization",
        name or f"{tenant.name} Canonical Organization",
        **overrides,
    )


def _contactaccountmanagement_person_party(tenant, *, name=None, **overrides):
    return _contactaccountmanagement_party(
        tenant,
        "person",
        name or f"{tenant.name} Canonical Person",
        **overrides,
    )


def _contactaccountmanagement_account_profile(tenant, party, *, parent=None, owner=None, **overrides):
    from apps.crm.models import AccountProfile

    parent_value = parent if parent is not None else overrides.get("parent_account")
    owner_value = owner if owner is not None else overrides.get("owner")
    _contactaccountmanagement_assert_same_tenant(
        tenant,
        party=party,
        parent_account=parent_value,
        owner=owner_value,
    )
    assert party.kind == "organization"
    if parent_value is not None:
        assert parent_value.kind == "organization"
    fields = {
        "tenant": tenant,
        "party": party,
        "industry": "technology",
        "website": f"https://{tenant.slug}.example",
        "annual_revenue": Decimal("5000000.00"),
        "employee_count": 125,
        "owner": owner_value,
        "description": f"Deterministic CRM account profile for {tenant.name}.",
    }
    fields.update(overrides)
    fields.update({
        "tenant": tenant,
        "party": party,
        "parent_account": parent_value,
        "owner": owner_value,
    })
    profile = AccountProfile(**fields)
    profile.full_clean()
    profile.save()
    return profile


def _contactaccountmanagement_contact_profile(tenant, party, *, account=None, owner=None, **overrides):
    from apps.crm.models import ContactProfile

    account_value = account if account is not None else overrides.get("account")
    owner_value = owner if owner is not None else overrides.get("owner")
    _contactaccountmanagement_assert_same_tenant(
        tenant,
        party=party,
        account=account_value,
        owner=owner_value,
    )
    assert party.kind == "person"
    if account_value is not None:
        assert account_value.kind == "organization"
    fields = {
        "tenant": tenant,
        "party": party,
        "job_title": "Operations Director",
        "department": "Operations",
        "email": f"contact@{tenant.slug}.example",
        "phone": "+1-555-0100",
        "mobile": "+1-555-0101",
        "account": account_value,
        "linkedin": f"https://www.linkedin.com/in/{tenant.slug}-contact",
        "owner": owner_value,
        "description": f"Deterministic CRM contact profile for {tenant.name}.",
        "source": "web",
    }
    fields.update(overrides)
    fields.update({
        "tenant": tenant,
        "party": party,
        "account": account_value,
        "owner": owner_value,
    })
    profile = ContactProfile(**fields)
    profile.full_clean()
    profile.save()
    return profile


def _contactaccountmanagement_consent_purpose(tenant, *, code="contact-enrichment", name=None, **overrides):
    from apps.core.models import ConsentPurpose

    fields = {
        "tenant": tenant,
        "name": name or f"{tenant.name} contact enrichment",
        "code": code,
        "lawful_basis": "consent",
        "is_optional": True,
        "description": "Deterministic lawful-basis purpose for contact enrichment tests.",
        "is_active": True,
    }
    fields.update(overrides)
    fields["tenant"] = tenant
    purpose = ConsentPurpose(**fields)
    purpose.full_clean()
    purpose.save()
    return purpose


def _contactaccountmanagement_reports_to(tenant, contact, manager, **overrides):
    from apps.core.models import PartyRelationship

    _contactaccountmanagement_assert_same_tenant(tenant, contact=contact, manager=manager)
    assert contact.kind == "person"
    assert manager.kind == "person"
    assert contact.pk != manager.pk
    fields = {
        "tenant": tenant,
        "from_party": contact,
        "to_party": manager,
        "kind": "reports_to",
    }
    fields.update(overrides)
    fields.update({
        "tenant": tenant,
        "from_party": contact,
        "to_party": manager,
        "kind": "reports_to",
    })
    relationship = PartyRelationship(**fields)
    relationship.full_clean()
    relationship.save()
    return relationship


def _contactaccountmanagement_stakeholder(tenant, account, contact, *, role="decision_maker", **overrides):
    from datetime import timedelta

    from apps.sales.models import AccountStakeholder

    _contactaccountmanagement_assert_same_tenant(tenant, account=account, contact=contact)
    assert account.kind == "organization"
    assert contact.kind == "person"
    assert account.pk != contact.pk
    fields = {
        "tenant": tenant,
        "account": account,
        "contact": contact,
        "role": role,
        "influence": "high",
        "attitude": "positive",
        "relationship_strength": "strong",
        "status": "active",
        "valid_from": timezone.localdate() - timedelta(days=30),
        "valid_to": None,
        "notes": "Deterministic buying-center stakeholder for Contact & Account Management tests.",
    }
    fields.update(overrides)
    fields.update({
        "tenant": tenant,
        "account": account,
        "contact": contact,
    })
    stakeholder = AccountStakeholder(**fields)
    stakeholder.full_clean()
    stakeholder.save()
    return stakeholder


def _contactaccountmanagement_classification(tenant, account, classified_by=None, **overrides):
    from datetime import timedelta

    from apps.sales.models import AccountClassification

    classified_by_value = classified_by if classified_by is not None else overrides.get("classified_by")
    _contactaccountmanagement_assert_same_tenant(tenant, account=account, classified_by=classified_by_value)
    assert account.kind == "organization"
    today = timezone.localdate()
    fields = {
        "tenant": tenant,
        "account": account,
        "tier": "strategic",
        "lifecycle_stage": "prospect",
        "strategic_priority": "high",
        "revenue_potential": "high",
        "wallet_category": "large",
        "rationale": "Deterministic strategic account classification for coverage tests.",
        "effective_on": today,
        "review_due_on": today + timedelta(days=90),
        "classified_by": classified_by_value,
    }
    fields.update(overrides)
    fields.update({
        "tenant": tenant,
        "account": account,
        "classified_by": classified_by_value,
    })
    classification = AccountClassification(**fields)
    classification.full_clean()
    classification.save()
    return classification


def _contactaccountmanagement_plan(tenant, account, owner, *, opportunities=(), **overrides):
    from datetime import timedelta

    from apps.sales.models import AccountPlan

    _contactaccountmanagement_assert_same_tenant(tenant, account=account, owner=owner)
    assert account.kind == "organization"
    opportunity_values = tuple(opportunities or ())
    for opportunity in opportunity_values:
        _contactaccountmanagement_assert_same_tenant(tenant, opportunity=opportunity)
        assert opportunity.account_id == account.pk
    today = timezone.localdate()
    fields = {
        "tenant": tenant,
        "account": account,
        "title": f"{tenant.name} Account Growth Plan",
        "period_start": today,
        "period_end": today + timedelta(days=90),
        "status": "draft",
        "owner": owner,
        "business_drivers": "Deterministic account business drivers.",
        "objectives": "Deterministic measurable account objectives.",
        "strategy": "Deterministic account strategy.",
        "strengths": "Deterministic account strengths.",
        "weaknesses": "Deterministic account weaknesses.",
        "opportunities": "Deterministic account opportunities.",
        "threats": "Deterministic account threats.",
        "white_space_assessment": "Product mapping is intentionally unavailable in this fixture.",
        "growth_initiatives": "Deterministic growth initiatives.",
        "risk_summary": "Deterministic account risk summary.",
        "next_review_on": today + timedelta(days=30),
    }
    fields.update(overrides)
    fields.update({
        "tenant": tenant,
        "account": account,
        "owner": owner,
    })
    plan = AccountPlan(**fields)
    plan.save()
    if opportunity_values:
        plan.related_opportunities.set(opportunity_values)
    return plan


def _contactaccountmanagement_enrichment_event(
    tenant,
    party,
    requested_by,
    *,
    legal_basis_purpose=None,
    **overrides,
):
    from decimal import Decimal

    from apps.sales.models import PartyEnrichmentEvent

    purpose_value = legal_basis_purpose if legal_basis_purpose is not None else overrides.get("legal_basis_purpose")
    _contactaccountmanagement_assert_same_tenant(
        tenant,
        party=party,
        requested_by=requested_by,
        legal_basis_purpose=purpose_value,
    )
    if party.kind == "organization":
        default_changes = {"industry": {"value": "energy", "confidence": 0.95}}
        default_kind = "firmographic"
    else:
        default_changes = {"job_title": {"value": "VP Operations", "confidence": 0.95}}
        default_kind = "contact"
    fields = {
        "tenant": tenant,
        "party": party,
        "kind": default_kind,
        "source_kind": "manual",
        "source_name": "Manual review",
        "source_reference": "contactaccountmanagement:manual",
        "status": "proposed",
        "match_confidence": Decimal("0.9500"),
        "changes": default_changes,
        "legal_basis_purpose": purpose_value,
        "requested_by": requested_by,
        "occurred_at": timezone.now(),
    }
    fields.update(overrides)
    fields.update({
        "tenant": tenant,
        "party": party,
        "requested_by": requested_by,
        "legal_basis_purpose": purpose_value,
    })
    event = PartyEnrichmentEvent(**fields)
    event.full_clean()
    event.save()
    return event


@pytest.fixture
def contactaccountmanagement_tenant_a(tenant_a):
    return tenant_a


@pytest.fixture
def contactaccountmanagement_tenant_b(tenant_b):
    return tenant_b


@pytest.fixture
def contactaccountmanagement_admin_a(admin_user):
    return admin_user


@pytest.fixture
def contactaccountmanagement_admin_b(admin_b):
    return admin_b


@pytest.fixture
def contactaccountmanagement_member_a(member_user):
    return member_user


@pytest.fixture
def contactaccountmanagement_member_b(db, contactaccountmanagement_tenant_b):
    return _contactaccountmanagement_user(contactaccountmanagement_tenant_b, "member")


@pytest.fixture
def contactaccountmanagement_admin_client_a(client_a):
    return client_a


@pytest.fixture
def contactaccountmanagement_admin_client_b(client_b):
    return client_b


@pytest.fixture
def contactaccountmanagement_member_client_a(member_client):
    return member_client


@pytest.fixture
def contactaccountmanagement_member_client_b(db, contactaccountmanagement_member_b):
    client = Client()
    client.force_login(contactaccountmanagement_member_b)
    return client


@pytest.fixture
def contactaccountmanagement_account_a(db, contactaccountmanagement_tenant_a):
    return _contactaccountmanagement_organization_party(
        contactaccountmanagement_tenant_a,
        name="Acme Canonical Organization",
    )


@pytest.fixture
def contactaccountmanagement_account_b(db, contactaccountmanagement_tenant_b):
    return _contactaccountmanagement_organization_party(
        contactaccountmanagement_tenant_b,
        name="Globex Canonical Organization",
    )


@pytest.fixture
def contactaccountmanagement_account_child_a(db, contactaccountmanagement_tenant_a):
    return _contactaccountmanagement_organization_party(
        contactaccountmanagement_tenant_a,
        name="Acme Child Organization",
    )


@pytest.fixture
def contactaccountmanagement_account_child_b(db, contactaccountmanagement_tenant_b):
    return _contactaccountmanagement_organization_party(
        contactaccountmanagement_tenant_b,
        name="Globex Child Organization",
    )


@pytest.fixture
def contactaccountmanagement_contact_a(db, contactaccountmanagement_tenant_a):
    return _contactaccountmanagement_person_party(
        contactaccountmanagement_tenant_a,
        name="Acme Primary Contact",
    )


@pytest.fixture
def contactaccountmanagement_contact_b(db, contactaccountmanagement_tenant_b):
    return _contactaccountmanagement_person_party(
        contactaccountmanagement_tenant_b,
        name="Globex Primary Contact",
    )


@pytest.fixture
def contactaccountmanagement_manager_a(db, contactaccountmanagement_tenant_a):
    return _contactaccountmanagement_person_party(
        contactaccountmanagement_tenant_a,
        name="Acme Contact Manager",
    )


@pytest.fixture
def contactaccountmanagement_manager_b(db, contactaccountmanagement_tenant_b):
    return _contactaccountmanagement_person_party(
        contactaccountmanagement_tenant_b,
        name="Globex Contact Manager",
    )


@pytest.fixture
def contactaccountmanagement_account_profile_a(
    db,
    contactaccountmanagement_tenant_a,
    contactaccountmanagement_account_a,
    contactaccountmanagement_admin_a,
):
    return _contactaccountmanagement_account_profile(
        contactaccountmanagement_tenant_a,
        contactaccountmanagement_account_a,
        owner=contactaccountmanagement_admin_a,
    )


@pytest.fixture
def contactaccountmanagement_account_profile_b(
    db,
    contactaccountmanagement_tenant_b,
    contactaccountmanagement_account_b,
    contactaccountmanagement_admin_b,
):
    return _contactaccountmanagement_account_profile(
        contactaccountmanagement_tenant_b,
        contactaccountmanagement_account_b,
        owner=contactaccountmanagement_admin_b,
    )


@pytest.fixture
def contactaccountmanagement_account_child_profile_a(
    db,
    contactaccountmanagement_tenant_a,
    contactaccountmanagement_account_child_a,
    contactaccountmanagement_account_profile_a,
    contactaccountmanagement_admin_a,
):
    return _contactaccountmanagement_account_profile(
        contactaccountmanagement_tenant_a,
        contactaccountmanagement_account_child_a,
        parent=contactaccountmanagement_account_profile_a.party,
        owner=contactaccountmanagement_admin_a,
    )


@pytest.fixture
def contactaccountmanagement_account_child_profile_b(
    db,
    contactaccountmanagement_tenant_b,
    contactaccountmanagement_account_child_b,
    contactaccountmanagement_account_profile_b,
    contactaccountmanagement_admin_b,
):
    return _contactaccountmanagement_account_profile(
        contactaccountmanagement_tenant_b,
        contactaccountmanagement_account_child_b,
        parent=contactaccountmanagement_account_profile_b.party,
        owner=contactaccountmanagement_admin_b,
    )


@pytest.fixture
def contactaccountmanagement_contact_profile_a(
    db,
    contactaccountmanagement_tenant_a,
    contactaccountmanagement_contact_a,
    contactaccountmanagement_account_a,
    contactaccountmanagement_admin_a,
):
    return _contactaccountmanagement_contact_profile(
        contactaccountmanagement_tenant_a,
        contactaccountmanagement_contact_a,
        account=contactaccountmanagement_account_a,
        owner=contactaccountmanagement_admin_a,
    )


@pytest.fixture
def contactaccountmanagement_contact_profile_b(
    db,
    contactaccountmanagement_tenant_b,
    contactaccountmanagement_contact_b,
    contactaccountmanagement_account_b,
    contactaccountmanagement_admin_b,
):
    return _contactaccountmanagement_contact_profile(
        contactaccountmanagement_tenant_b,
        contactaccountmanagement_contact_b,
        account=contactaccountmanagement_account_b,
        owner=contactaccountmanagement_admin_b,
    )


@pytest.fixture
def contactaccountmanagement_consent_purpose_a(db, contactaccountmanagement_tenant_a):
    return _contactaccountmanagement_consent_purpose(contactaccountmanagement_tenant_a)


@pytest.fixture
def contactaccountmanagement_consent_purpose_b(db, contactaccountmanagement_tenant_b):
    return _contactaccountmanagement_consent_purpose(contactaccountmanagement_tenant_b)


@pytest.fixture
def contactaccountmanagement_stakeholder_a(
    db,
    contactaccountmanagement_tenant_a,
    contactaccountmanagement_account_a,
    contactaccountmanagement_contact_a,
):
    return _contactaccountmanagement_stakeholder(
        contactaccountmanagement_tenant_a,
        contactaccountmanagement_account_a,
        contactaccountmanagement_contact_a,
        role="decision_maker",
    )


@pytest.fixture
def contactaccountmanagement_stakeholder_b(
    db,
    contactaccountmanagement_tenant_b,
    contactaccountmanagement_account_b,
    contactaccountmanagement_contact_b,
):
    return _contactaccountmanagement_stakeholder(
        contactaccountmanagement_tenant_b,
        contactaccountmanagement_account_b,
        contactaccountmanagement_contact_b,
        role="champion",
    )


@pytest.fixture
def contactaccountmanagement_classification_a(
    db,
    contactaccountmanagement_tenant_a,
    contactaccountmanagement_account_a,
    contactaccountmanagement_admin_a,
):
    return _contactaccountmanagement_classification(
        contactaccountmanagement_tenant_a,
        contactaccountmanagement_account_a,
        classified_by=contactaccountmanagement_admin_a,
    )


@pytest.fixture
def contactaccountmanagement_classification_b(
    db,
    contactaccountmanagement_tenant_b,
    contactaccountmanagement_account_b,
    contactaccountmanagement_admin_b,
):
    return _contactaccountmanagement_classification(
        contactaccountmanagement_tenant_b,
        contactaccountmanagement_account_b,
        classified_by=contactaccountmanagement_admin_b,
    )


@pytest.fixture
def contactaccountmanagement_plan_a(
    db,
    contactaccountmanagement_tenant_a,
    contactaccountmanagement_account_a,
    contactaccountmanagement_admin_a,
):
    return _contactaccountmanagement_plan(
        contactaccountmanagement_tenant_a,
        contactaccountmanagement_account_a,
        contactaccountmanagement_admin_a,
    )


@pytest.fixture
def contactaccountmanagement_plan_b(
    db,
    contactaccountmanagement_tenant_b,
    contactaccountmanagement_account_b,
    contactaccountmanagement_admin_b,
):
    return _contactaccountmanagement_plan(
        contactaccountmanagement_tenant_b,
        contactaccountmanagement_account_b,
        contactaccountmanagement_admin_b,
    )


@pytest.fixture
def contactaccountmanagement_enrichment_event_a(
    db,
    contactaccountmanagement_tenant_a,
    contactaccountmanagement_account_a,
    contactaccountmanagement_admin_a,
):
    return _contactaccountmanagement_enrichment_event(
        contactaccountmanagement_tenant_a,
        contactaccountmanagement_account_a,
        contactaccountmanagement_admin_a,
    )


@pytest.fixture
def contactaccountmanagement_enrichment_event_b(
    db,
    contactaccountmanagement_tenant_b,
    contactaccountmanagement_account_b,
    contactaccountmanagement_admin_b,
):
    return _contactaccountmanagement_enrichment_event(
        contactaccountmanagement_tenant_b,
        contactaccountmanagement_account_b,
        contactaccountmanagement_admin_b,
    )


@pytest.fixture
def contactaccountmanagement_reports_to_a(
    db,
    contactaccountmanagement_tenant_a,
    contactaccountmanagement_contact_a,
    contactaccountmanagement_manager_a,
):
    return _contactaccountmanagement_reports_to(
        contactaccountmanagement_tenant_a,
        contactaccountmanagement_contact_a,
        contactaccountmanagement_manager_a,
    )


@pytest.fixture
def contactaccountmanagement_reports_to_b(
    db,
    contactaccountmanagement_tenant_b,
    contactaccountmanagement_contact_b,
    contactaccountmanagement_manager_b,
):
    return _contactaccountmanagement_reports_to(
        contactaccountmanagement_tenant_b,
        contactaccountmanagement_contact_b,
        contactaccountmanagement_manager_b,
    )


# ============================================================================
# 8.2 Opportunity & Pipeline Management Test Helpers and Fixtures
# ============================================================================

OPPORTUNITYPIPELINE_PAGE_SIZE = 15

OPPORTUNITYPIPELINE_MODEL_FIELDS = {
    "OpportunityPipeline": (
        "tenant", "created_at", "updated_at", "number", "name", "code",
        "description", "is_default", "is_active", "currency", "owner",
    ),
    "PipelineStage": (
        "tenant", "created_at", "updated_at", "pipeline", "name", "code",
        "sequence", "stage_kind", "probability", "target_days",
        "require_competitor", "is_active",
    ),
    "OpportunityPipelinePlacement": (
        "tenant", "created_at", "updated_at", "opportunity", "pipeline",
        "current_stage", "stage_entered_at", "probability_override",
    ),
    "OpportunityTeamMember": (
        "tenant", "created_at", "updated_at", "opportunity", "user",
        "role", "notes", "is_active",
    ),
    "CompetitorProfile": (
        "tenant", "created_at", "updated_at", "party", "website",
        "tier", "strengths", "weaknesses", "pricing_model", "notes", "is_active",
    ),
    "OpportunityCompetitor": (
        "tenant", "created_at", "updated_at", "opportunity", "competitor_profile",
        "threat_level", "strategy_notes", "is_primary",
    ),
    "WinLossReason": (
        "tenant", "created_at", "updated_at", "name", "code", "result",
        "category", "requires_competitor", "notes", "is_active",
    ),
    "OpportunityOutcome": (
        "tenant", "created_at", "updated_at", "opportunity", "result",
        "reason", "competitor_link", "closed_at", "recorded_by",
        "decision_maker_feedback", "notes",
    ),
}

OPPORTUNITYPIPELINE_CHOICES = {
    "PipelineStage": {
        "stage_kind": (
            ("open", "Open"),
            ("won", "Won"),
            ("lost", "Lost"),
        ),
    },
    "OpportunityTeamMember": {
        "role": (
            ("owner", "Deal Owner"),
            ("co_owner", "Co-Owner"),
            ("sales_rep", "Sales Representative"),
            ("solutions_engineer", "Solutions Engineer"),
            ("executive_sponsor", "Executive Sponsor"),
            ("subject_matter_expert", "Subject Matter Expert"),
            ("proposal_manager", "Proposal Manager"),
            ("legal_counsel", "Legal / Contracts Counsel"),
            ("finance_commercial", "Finance / Commercial"),
            ("customer_success", "Customer Success / Delivery"),
            ("channel_manager", "Channel / Partner Manager"),
            ("approver", "Deal Desk Approver"),
            ("observer", "Observer"),
        ),
    },
    "CompetitorProfile": {
        "tier": (
            ("tier_1", "Tier 1 - Primary"),
            ("tier_2", "Tier 2 - Secondary"),
            ("tier_3", "Tier 3 - Emerging"),
            ("niche", "Niche Specialist"),
        ),
    },
    "OpportunityCompetitor": {
        "threat_level": (
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
            ("critical", "Critical"),
        ),
    },
    "WinLossReason": {
        "result": (
            ("won", "Won Only"),
            ("lost", "Lost Only"),
            ("both", "Applicable to Both"),
        ),
        "category": (
            ("product", "Product & Features"),
            ("price", "Pricing & Commercials"),
            ("relationship", "Relationship & Service"),
            ("timing", "Timing & Budget Delay"),
            ("competition", "Competitor Preference"),
            ("internal_priority", "Customer Internal Priority Shift"),
            ("compliance", "Security & Compliance"),
            ("other", "Other"),
        ),
    },
    "OpportunityOutcome": {
        "result": (
            ("won", "Closed Won"),
            ("lost", "Closed Lost"),
        ),
    },
}


def _opportunitypipeline_tenant_id(tenant):
    return tenant.pk if hasattr(tenant, "pk") else tenant


def _opportunitypipeline_user(tenant, email_prefix="user", *, is_admin=False, **overrides):
    from apps.accounts.models import User

    tid = _opportunitypipeline_tenant_id(tenant)
    email = overrides.pop("email", f"{email_prefix}_{tid}_{timezone.now().timestamp()}@example.com")
    username = overrides.pop("username", email.split("@")[0][:30])
    user = User.objects.create_user(
        email=email,
        username=username,
        password="password",
        tenant=tenant,
        is_tenant_admin=is_admin,
        **overrides,
    )
    return user


def _opportunitypipeline_party(tenant, name=None, kind="organization", **overrides):
    from apps.core.models import Party

    tid = _opportunitypipeline_tenant_id(tenant)
    name = name or f"Party_{tid}_{timezone.now().timestamp()}"
    return Party.objects.create(
        tenant=tenant,
        name=name,
        kind=kind,
        **overrides,
    )


def _opportunitypipeline_opportunity(tenant, title=None, owner=None, stage="prospecting", amount=Decimal("15000.00"), **overrides):
    from apps.crm.models import Opportunity

    deal_name = overrides.pop("name", None) or overrides.pop("title", None) or title or f"Deal_{tid}_{timezone.now().timestamp()}"
    account = overrides.pop("account", None)
    if account is None:
        account = _opportunitypipeline_party(tenant, name=f"AccountParty_{deal_name}")
    return Opportunity.objects.create(
        tenant=tenant,
        name=deal_name,
        account=account,
        owner=owner,
        stage=stage,
        amount=amount,
        **overrides,
    )


def _opportunitypipeline_pipeline(tenant, name="Standard Pipeline", code=None, is_default=False, owner=None, **overrides):
    from apps.sales.models.OpportunityPipeline.Pipelines import Pipeline

    overrides.pop("code", None)
    overrides.pop("owner", None)
    overrides.pop("currency", None)
    return Pipeline.objects.create(
        tenant=tenant,
        name=name,
        is_default=is_default,
        **overrides,
    )


def _opportunitypipeline_stage(tenant, pipeline, name="Discovery", sequence=10, stage_kind="open", probability=20, target_days=14, **overrides):
    from apps.sales.models.OpportunityPipeline.Pipelines import PipelineStage

    code = overrides.pop("code", f"stg_{sequence}")
    if stage_kind == "won":
        crm_key = "closed_won"
        prob = 100
        fc = "closed"
    elif stage_kind == "lost":
        crm_key = "closed_lost"
        prob = 0
        fc = "closed"
    else:
        crm_key = "proposal"
        prob = probability
        fc = "pipeline"
    crm_stage_key = overrides.pop("crm_stage_key", crm_key)
    probability = overrides.pop("probability", prob)
    forecast_category = overrides.pop("forecast_category", fc)
    return PipelineStage.objects.create(
        tenant=tenant,
        pipeline=pipeline,
        name=name,
        code=code,
        sequence=sequence,
        stage_kind=stage_kind,
        crm_stage_key=crm_stage_key,
        probability=probability,
        forecast_category=forecast_category,
        target_days=target_days,
        **overrides,
    )


def _opportunitypipeline_placement(tenant, opportunity, pipeline, current_stage, **overrides):
    from apps.sales.models import OpportunityPipelinePlacement

    return OpportunityPipelinePlacement.objects.create(
        tenant=tenant,
        opportunity=opportunity,
        pipeline=pipeline,
        current_stage=current_stage,
        stage_entered_at=overrides.pop("stage_entered_at", timezone.now()),
        **overrides,
    )


def _opportunitypipeline_team_member(tenant, opportunity, user, role="sales_support", **overrides):
    from apps.sales.models import OpportunityTeamMember

    valid_roles = dict(OpportunityTeamMember.ROLE_CHOICES)
    role_mapped = {
        "sales_rep": "sales_support",
        "solutions_engineer": "solution_consultant",
        "proposal_manager": "sales_support",
        "legal_counsel": "sales_support",
        "finance_commercial": "sales_support",
        "customer_success": "sales_support",
        "channel_manager": "collaborator",
        "owner": "co_owner",
        "technical_lead": "solution_consultant",
        "subject_matter_expert": "solution_consultant",
    }
    actual_role = role_mapped.get(role, role)
    if actual_role not in valid_roles:
        actual_role = "sales_support"
    overrides.pop("notes", None)
    return OpportunityTeamMember.objects.create(
        tenant=tenant,
        opportunity=opportunity,
        user=user,
        role=actual_role,
        **overrides,
    )


def _opportunitypipeline_competitor_profile(tenant, party=None, website_url=None, **overrides):
    from apps.sales.models import CompetitorProfile

    if party is None:
        party = _opportunitypipeline_party(tenant, name=f"Competitor_{timezone.now().timestamp()}")
    url = overrides.pop("website", None) or website_url or overrides.pop("website_url", "https://competitor.example.com")
    overrides.pop("tier", None)
    return CompetitorProfile.objects.create(
        tenant=tenant,
        party=party,
        website_url=url,
        **overrides,
    )


def _opportunitypipeline_opportunity_competitor(tenant, opportunity, competitor_profile, **overrides):
    from apps.sales.models import OpportunityCompetitor

    overrides.pop("threat_level", None)
    overrides.pop("strategy_notes", None)
    relationship = overrides.pop("relationship", "evaluating")
    if relationship not in dict(OpportunityCompetitor.RELATIONSHIP_CHOICES):
        relationship = "evaluating"
    return OpportunityCompetitor.objects.create(
        tenant=tenant,
        opportunity=opportunity,
        competitor_profile=competitor_profile,
        relationship=relationship,
        **overrides,
    )


def _opportunitypipeline_win_loss_reason(tenant, name="Product Fit", code=None, result="both", category="product_fit", **overrides):
    from apps.sales.models import WinLossReason

    code = code or f"R{int(timezone.now().timestamp() % 10000)}"
    category_map = {
        "product": "product_fit",
        "competition": "competition",
        "price": "price",
        "timing": "timing",
        "relationship": "relationship",
    }
    cat = category_map.get(category, category)
    if cat not in dict(WinLossReason.CATEGORY_CHOICES):
        cat = "other"
    overrides.pop("requires_competitor", None)
    overrides.pop("notes", None)
    return WinLossReason.objects.create(
        tenant=tenant,
        name=name,
        code=code,
        result=result,
        category=cat,
        **overrides,
    )


def _opportunitypipeline_outcome(tenant, opportunity, result="won", reason=None, recorded_by=None, **overrides):
    from apps.sales.models import OpportunityOutcome

    overrides.pop("decision_maker_feedback", None)
    if reason is None:
        reason = _opportunitypipeline_win_loss_reason(tenant, result=result)
    return OpportunityOutcome.objects.create(
        tenant=tenant,
        opportunity=opportunity,
        result=result,
        reason=reason,
        recorded_by=recorded_by,
        **overrides,
    )


@pytest.fixture
def opportunitypipeline_tenant_a(db):
    from apps.core.models import Tenant

    tenant, _ = Tenant.objects.get_or_create(name="Acme Corp", slug="acme")
    return tenant


@pytest.fixture
def opportunitypipeline_tenant_b(db):
    from apps.core.models import Tenant

    tenant, _ = Tenant.objects.get_or_create(name="Globex Corp", slug="globex")
    return tenant


@pytest.fixture
def opportunitypipeline_admin_a(db, opportunitypipeline_tenant_a):
    return _opportunitypipeline_user(opportunitypipeline_tenant_a, "admin_a", is_admin=True)


@pytest.fixture
def opportunitypipeline_admin_b(db, opportunitypipeline_tenant_b):
    return _opportunitypipeline_user(opportunitypipeline_tenant_b, "admin_b", is_admin=True)


@pytest.fixture
def opportunitypipeline_user_a(db, opportunitypipeline_tenant_a):
    return _opportunitypipeline_user(opportunitypipeline_tenant_a, "user_a", is_admin=False)


@pytest.fixture
def opportunitypipeline_user_b(db, opportunitypipeline_tenant_b):
    return _opportunitypipeline_user(opportunitypipeline_tenant_b, "user_b", is_admin=False)


@pytest.fixture
def opportunitypipeline_client_a(opportunitypipeline_admin_a):
    client = Client()
    client.force_login(opportunitypipeline_admin_a)
    return client


@pytest.fixture
def opportunitypipeline_client_b(opportunitypipeline_admin_b):
    client = Client()
    client.force_login(opportunitypipeline_admin_b)
    return client


@pytest.fixture
def opportunitypipeline_client_member_a(opportunitypipeline_user_a):
    client = Client()
    client.force_login(opportunitypipeline_user_a)
    return client


@pytest.fixture
def opportunitypipeline_pipeline_a(db, opportunitypipeline_tenant_a, opportunitypipeline_admin_a):
    pipeline = _opportunitypipeline_pipeline(opportunitypipeline_tenant_a, name="Acme Direct", code="ACME_DIR", is_default=True, owner=opportunitypipeline_admin_a)
    _opportunitypipeline_stage(opportunitypipeline_tenant_a, pipeline, name="Discovery", sequence=10, stage_kind="open", probability=20)
    _opportunitypipeline_stage(opportunitypipeline_tenant_a, pipeline, name="Proposal", sequence=20, stage_kind="open", probability=50)
    _opportunitypipeline_stage(opportunitypipeline_tenant_a, pipeline, name="Negotiation", sequence=30, stage_kind="open", probability=80)
    _opportunitypipeline_stage(opportunitypipeline_tenant_a, pipeline, name="Closed Won", sequence=90, stage_kind="won", probability=100)
    _opportunitypipeline_stage(opportunitypipeline_tenant_a, pipeline, name="Closed Lost", sequence=100, stage_kind="lost", probability=0)
    return pipeline


@pytest.fixture
def opportunitypipeline_pipeline_b(db, opportunitypipeline_tenant_b, opportunitypipeline_admin_b):
    pipeline = _opportunitypipeline_pipeline(opportunitypipeline_tenant_b, name="Globex Direct", code="GLB_DIR", is_default=True, owner=opportunitypipeline_admin_b)
    _opportunitypipeline_stage(opportunitypipeline_tenant_b, pipeline, name="Initial", sequence=10, stage_kind="open", probability=10)
    _opportunitypipeline_stage(opportunitypipeline_tenant_b, pipeline, name="Won", sequence=90, stage_kind="won", probability=100)
    _opportunitypipeline_stage(opportunitypipeline_tenant_b, pipeline, name="Lost", sequence=100, stage_kind="lost", probability=0)
    return pipeline


@pytest.fixture
def opportunitypipeline_opportunity_a(db, opportunitypipeline_tenant_a, opportunitypipeline_admin_a):
    return _opportunitypipeline_opportunity(opportunitypipeline_tenant_a, "Big Enterprise Acme Deal", owner=opportunitypipeline_admin_a)


@pytest.fixture
def opportunitypipeline_opportunity_b(db, opportunitypipeline_tenant_b, opportunitypipeline_admin_b):
    return _opportunitypipeline_opportunity(opportunitypipeline_tenant_b, "Globex Major Deal", owner=opportunitypipeline_admin_b)


@pytest.fixture
def opportunitypipeline_placement_a(db, opportunitypipeline_tenant_a, opportunitypipeline_opportunity_a, opportunitypipeline_pipeline_a):
    stage = opportunitypipeline_pipeline_a.stages.filter(stage_kind="open").first()
    return _opportunitypipeline_placement(opportunitypipeline_tenant_a, opportunitypipeline_opportunity_a, opportunitypipeline_pipeline_a, stage)


@pytest.fixture
def opportunitypipeline_competitor_a(db, opportunitypipeline_tenant_a):
    return _opportunitypipeline_competitor_profile(opportunitypipeline_tenant_a, website="https://competitor-a.com")


@pytest.fixture
def opportunitypipeline_reason_a(db, opportunitypipeline_tenant_a):
    return _opportunitypipeline_win_loss_reason(opportunitypipeline_tenant_a, name="Superior Features", code="FEAT_A", result="won")



# ============================================================================
# 8.4 Sales Forecasting Test Helpers and Fixtures
# ============================================================================

SALESFORECASTING_MODEL_FIELDS = {
    "ForecastPeriod": (
        "tenant", "created_at", "updated_at", "number", "name", "period_type",
        "period_year", "period_number", "start_date", "end_date", "rollup_dimension",
        "reporting_currency", "fx_rate_source_date", "is_active", "is_locked",
    ),
    "ForecastSubmission": (
        "tenant", "created_at", "updated_at", "number", "period", "owner", "org_unit",
        "territory", "pipeline", "quota_ref", "submitted_by", "reviewed_by", "status",
        "omitted_amount", "pipeline_amount", "best_case_amount", "commit_amount",
        "closed_amount", "weighted_amount", "quota_amount", "actual_amount",
        "submitted_at", "reviewed_at", "review_note", "ai_predicted_pipeline",
        "ai_predicted_best_case", "ai_predicted_commit", "ai_confidence_pct",
        "ai_model_name", "ai_model_version", "ai_generated_at", "ai_explanation", "notes",
    ),
    "ForecastAdjustment": (
        "tenant", "created_at", "updated_at", "number", "submission", "opportunity",
        "placement", "created_by", "adjustment_kind", "target_field", "original_value",
        "adjusted_value", "original_category", "adjusted_category", "reason_code", "note",
        "is_reverted", "reverted_at", "revert_reason",
    ),
    "ForecastScenario": (
        "tenant", "created_at", "updated_at", "number", "period", "owner", "name",
        "scenario_type", "probability_pct", "is_baseline", "is_selected",
        "pipeline_delta_pct", "best_case_delta_pct", "commit_delta_pct",
        "projected_commit_amount", "projected_total_amount", "assumption_notes",
    ),
}

SALESFORECASTING_CHOICES = {
    "ForecastPeriod": {
        "rollup_dimension": (
            ("user", "Sales Representative"),
            ("org_unit", "Organizational Unit"),
            ("territory", "Territory"),
        ),
    },
    "ForecastSubmission": {
        "status": (
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("locked", "Locked"),
        ),
    },
    "ForecastAdjustment": {
        "adjustment_kind": (
            ("direct", "Direct"),
            ("indirect", "Indirect"),
            ("revert", "Revert"),
        ),
        "target_field": (
            ("category", "Forecast Category"),
            ("amount", "Amount"),
        ),
        "reason_code": (
            ("new_deal", "New Deal Added"),
            ("deal_advanced", "Deal Advanced A Stage"),
            ("deal_slipped", "Deal Slipped"),
            ("deal_lost", "Deal Lost"),
            ("deal_won", "Deal Won"),
            ("amount_revised", "Amount Revised"),
            ("timing_revised", "Timing Revised"),
            ("territory_reassigned", "Territory Reassigned"),
            ("manager_judgement", "Manager Judgement"),
            ("correction", "Data Correction"),
        ),
    },
    "ForecastScenario": {
        "scenario_type": (
            ("upside", "Upside"),
            ("base", "Base"),
            ("downside", "Downside"),
            ("custom", "Custom"),
        ),
    },
}



def _salesforecasting_tenant_id(tenant):
    return tenant.pk if hasattr(tenant, "pk") else tenant


def _salesforecasting_user(tenant, email_prefix="user", *, is_admin=False, **overrides):
    from apps.accounts.models import User

    tid = _salesforecasting_tenant_id(tenant)
    email = overrides.pop("email", f"{email_prefix}_{tid}_{timezone.now().timestamp()}@example.com")
    username = overrides.pop("username", email.split("@")[0][:30])
    return User.objects.create_user(
        email=email,
        username=username,
        password="password",
        tenant=tenant,
        is_tenant_admin=is_admin,
        **overrides,
    )


def _salesforecasting_org_unit(tenant, name=None, kind="department", parent=None, **overrides):
    from apps.core.models import OrgUnit

    tid = _salesforecasting_tenant_id(tenant)
    name = name or f"OrgUnit_{tid}_{timezone.now().timestamp()}"
    return OrgUnit.objects.create(
        tenant=tenant,
        name=name,
        kind=kind,
        parent=parent,
        **overrides,
    )


def _salesforecasting_currency(code="USD", name="US Dollar", symbol="$"):
    """``accounting.Currency`` is GLOBAL (no tenant FK) -- never tenant-scoped (L29)."""
    from apps.accounting.models import Currency

    currency, _ = Currency.objects.get_or_create(
        code=code,
        defaults={"name": name, "symbol": symbol, "is_active": True},
    )
    return currency


def _salesforecasting_pipeline(tenant, name="Standard Pipeline", is_default=False, **overrides):
    from apps.sales.models.OpportunityPipeline.Pipelines import Pipeline

    overrides.pop("code", None)
    overrides.pop("owner", None)
    overrides.pop("currency", None)
    return Pipeline.objects.create(
        tenant=tenant,
        name=name,
        is_default=is_default,
        **overrides,
    )



def _salesforecasting_period(
    tenant,
    name="Forecast Period",
    period_type="quarter",
    period_year=None,
    period_number=1,
    reporting_currency=None,
    is_active=True,
    is_locked=False,
    **overrides,
):
    from apps.sales.models.SalesForecasting.ForecastPeriods import ForecastPeriod

    if period_year is None:
        period_year = timezone.localdate().year
    return ForecastPeriod.objects.create(
        tenant=tenant,
        name=name,
        period_type=period_type,
        period_year=period_year,
        period_number=period_number,
        reporting_currency=reporting_currency,
        is_active=is_active,
        is_locked=is_locked,
        **overrides,
    )


def _salesforecasting_submission(
    tenant,
    period,
    owner=None,
    status="draft",
    org_unit=None,
    pipeline=None,
    pipeline_amount=Decimal("10000.00"),
    best_case_amount=Decimal("8000.00"),
    commit_amount=Decimal("5000.00"),
    **overrides,
):
    from apps.sales.models.SalesForecasting.ForecastSubmissions import ForecastSubmission

    overrides.setdefault("closed_amount", Decimal("0.00"))
    overrides.setdefault("omitted_amount", Decimal("0.00"))
    overrides.setdefault("weighted_amount", Decimal("6000.00"))
    overrides.setdefault("quota_amount", Decimal("20000.00"))
    overrides.setdefault("actual_amount", Decimal("9000.00"))
    return ForecastSubmission.objects.create(
        tenant=tenant,
        period=period,
        owner=owner,
        status=status,
        org_unit=org_unit,
        pipeline=pipeline,
        pipeline_amount=pipeline_amount,
        best_case_amount=best_case_amount,
        commit_amount=commit_amount,
        **overrides,
    )



def _salesforecasting_adjustment(
    tenant,
    submission,
    reason_code="manager_judgement",
    adjustment_kind="direct",
    target_field="category",
    adjusted_category="commit",
    adjusted_value=None,
    **overrides,
):
    from apps.sales.models.SalesForecasting.ForecastAdjustments import ForecastAdjustment

    return ForecastAdjustment.objects.create(
        tenant=tenant,
        submission=submission,
        adjustment_kind=adjustment_kind,
        target_field=target_field,
        adjusted_category=adjusted_category,
        adjusted_value=adjusted_value,
        reason_code=reason_code,
        **overrides,
    )


def _salesforecasting_scenario(
    tenant,
    period,
    name="Upside Case",
    scenario_type="upside",
    owner=None,
    is_baseline=False,
    is_selected=False,
    pipeline_delta_pct=Decimal("10.00"),
    best_case_delta_pct=Decimal("5.00"),
    commit_delta_pct=Decimal("0.00"),
    **overrides,
):
    from apps.sales.models.SalesForecasting.ForecastScenarios import ForecastScenario

    return ForecastScenario.objects.create(
        tenant=tenant,
        period=period,
        owner=owner,
        name=name,
        scenario_type=scenario_type,
        is_baseline=is_baseline,
        is_selected=is_selected,
        pipeline_delta_pct=pipeline_delta_pct,
        best_case_delta_pct=best_case_delta_pct,
        commit_delta_pct=commit_delta_pct,
        **overrides,
    )



@pytest.fixture
def salesforecasting_tenant_a(db):
    from apps.core.models import Tenant

    tenant, _ = Tenant.objects.get_or_create(name="Acme Corp", slug="acme")
    return tenant


@pytest.fixture
def salesforecasting_tenant_b(db):
    from apps.core.models import Tenant

    tenant, _ = Tenant.objects.get_or_create(name="Globex Corp", slug="globex")
    return tenant


@pytest.fixture
def salesforecasting_admin_a(db, salesforecasting_tenant_a):
    return _salesforecasting_user(salesforecasting_tenant_a, "fc_admin_a", is_admin=True)


@pytest.fixture
def salesforecasting_rep_a(db, salesforecasting_tenant_a):
    """A plain rep: not a tenant admin, so the privileged-action lanes have a subject."""
    return _salesforecasting_user(salesforecasting_tenant_a, "fc_rep_a", is_admin=False)


@pytest.fixture
def salesforecasting_admin_b(db, salesforecasting_tenant_b):
    return _salesforecasting_user(salesforecasting_tenant_b, "fc_admin_b", is_admin=True)


@pytest.fixture
def salesforecasting_client_a(salesforecasting_admin_a):
    client = Client()
    client.force_login(salesforecasting_admin_a)
    return client


@pytest.fixture
def salesforecasting_client_b(salesforecasting_admin_b):
    client = Client()
    client.force_login(salesforecasting_admin_b)
    return client


@pytest.fixture
def salesforecasting_client_rep_a(salesforecasting_rep_a):
    client = Client()
    client.force_login(salesforecasting_rep_a)
    return client


@pytest.fixture
def salesforecasting_currency(db):
    return _salesforecasting_currency()



@pytest.fixture
def salesforecasting_org_unit_parent_a(db, salesforecasting_tenant_a):
    return _salesforecasting_org_unit(salesforecasting_tenant_a, name="Acme Group", kind="company")


@pytest.fixture
def salesforecasting_org_unit_child_a(db, salesforecasting_tenant_a, salesforecasting_org_unit_parent_a):
    return _salesforecasting_org_unit(
        salesforecasting_tenant_a,
        name="Acme East Sales",
        kind="department",
        parent=salesforecasting_org_unit_parent_a,
    )


@pytest.fixture
def salesforecasting_org_unit_b(db, salesforecasting_tenant_b):
    return _salesforecasting_org_unit(salesforecasting_tenant_b, name="Globex Group", kind="company")


@pytest.fixture
def salesforecasting_pipeline_a(db, salesforecasting_tenant_a):
    return _salesforecasting_pipeline(salesforecasting_tenant_a, name="Acme Direct", is_default=True)


@pytest.fixture
def salesforecasting_pipeline_b(db, salesforecasting_tenant_b):
    return _salesforecasting_pipeline(salesforecasting_tenant_b, name="Globex Direct", is_default=True)


@pytest.fixture
def salesforecasting_period_a(db, salesforecasting_tenant_a, salesforecasting_currency):
    """The tenant's current quarter -- the window most board assertions read."""
    today = timezone.localdate()
    return _salesforecasting_period(
        salesforecasting_tenant_a,
        name=f"Q{(today.month - 1) // 3 + 1} {today.year}",
        period_type="quarter",
        period_year=today.year,
        period_number=(today.month - 1) // 3 + 1,
        reporting_currency=salesforecasting_currency,
    )


@pytest.fixture
def salesforecasting_past_period_a(db, salesforecasting_tenant_a):
    """A closed window: ``period_elapsed_pct`` must read 100, not divide by zero."""
    today = timezone.localdate()
    return _salesforecasting_period(
        salesforecasting_tenant_a,
        name=f"Q4 {today.year - 1}",
        period_type="quarter",
        period_year=today.year - 1,
        period_number=4,
    )



@pytest.fixture
def salesforecasting_period_b(db, salesforecasting_tenant_b):
    """The IDOR lane's target: a period that belongs to the OTHER workspace."""
    today = timezone.localdate()
    return _salesforecasting_period(
        salesforecasting_tenant_b,
        name="Globex Current Quarter",
        period_type="quarter",
        period_year=today.year,
        period_number=(today.month - 1) // 3 + 1,
    )


@pytest.fixture
def salesforecasting_submission_a(
    db,
    salesforecasting_tenant_a,
    salesforecasting_period_a,
    salesforecasting_rep_a,
    salesforecasting_org_unit_child_a,
    salesforecasting_pipeline_a,
):
    return _salesforecasting_submission(
        salesforecasting_tenant_a,
        salesforecasting_period_a,
        owner=salesforecasting_rep_a,
        org_unit=salesforecasting_org_unit_child_a,
        pipeline=salesforecasting_pipeline_a,
    )


@pytest.fixture
def salesforecasting_adjustment_a(db, salesforecasting_tenant_a, salesforecasting_submission_a):
    return _salesforecasting_adjustment(
        salesforecasting_tenant_a,
        salesforecasting_submission_a,
        reason_code="deal_won",
    )


@pytest.fixture
def salesforecasting_scenario_a(db, salesforecasting_tenant_a, salesforecasting_period_a, salesforecasting_admin_a):
    return _salesforecasting_scenario(
        salesforecasting_tenant_a,
        salesforecasting_period_a,
        name="Acme Upside",
        owner=salesforecasting_admin_a,
    )


# ===== 8.6 Order Management (appended by the 8.6 test-contract step) =====
# Fixtures and record factories ONLY -- no test bodies (the 8.5 precedent). Every helper is
# ``_ordermanagement_*`` and every fixture ``ordermanagement_*`` so 8.1-8.5 cannot be shadowed.
from datetime import timedelta  # noqa: E402

# The 8.1-8.5 conftest above does not import Tenant/User at module scope, so the 8.6 section
# brings its own aliases rather than editing imports another sub-module owns.
from apps.core.models import Tenant as _OmTenant  # noqa: E402
from apps.scm.models import SalesOrder, SalesOrderLine  # noqa: E402
from apps.sales.models import (  # noqa: E402
    OrderAmendment,
    OrderAmendmentLine,
    OrderHold,
    OrderValidationRule,
    PerformanceObligation,
    RevenueSchedule,
)


def _ordermanagement_party(tenant, name="Order Test Customer", kind="customer"):
    from apps.core.models import Party as _OmParty

    return _OmParty.objects.create(tenant=tenant, name=name, kind=kind)


def _ordermanagement_order(tenant, status="submitted", unit_price="100.00", **over):
    """A real SCM 4.5 order to hang 8.6 rows off. 8.6 never creates an order itself."""
    party = over.pop("customer", None) or _ordermanagement_party(tenant)
    order = SalesOrder.objects.create(
        tenant=tenant, customer=party, status=status, order_date=timezone.localdate(), **over,
    )
    # 4.5 recomputes totals from its lines, so a line is what makes `total` meaningful.
    SalesOrderLine.objects.create(
        sales_order=order, description="Widget", quantity_ordered=Decimal("10.00"),
        unit_price=Decimal(unit_price), discount_pct=Decimal("0.00"), tax_pct=Decimal("0.00"),
    )
    order.recalc_totals()
    order.refresh_from_db()
    return order


def _ordermanagement_order_line(order, item=None, quantity="10.00", price="100.00"):
    return SalesOrderLine.objects.create(
        sales_order=order, item=item, description="Widget",
        quantity_ordered=Decimal(quantity), unit_price=Decimal(price),
        discount_pct=Decimal("0.00"), tax_pct=Decimal("0.00"),
    )


def _ordermanagement_rule(tenant, name="Credit ceiling", rule_type="order_value",
                          severity="hold", active_on="submit", parameters=None,
                          is_active=True, party=None, priority=10):
    rule = OrderValidationRule(
        tenant=tenant, name=name, rule_type=rule_type, severity=severity,
        active_on=active_on, parameters=parameters if parameters is not None else {},
        is_active=is_active, party=party, priority=priority,
    )
    rule.save()
    return rule


def _ordermanagement_hold(tenant, order, rule=None, hold_type="credit", status="open",
                          severity="hold", reason="Customer is over their credit limit.",
                          snapshot=None, **over):
    hold = OrderHold(
        tenant=tenant, sales_order=order, rule=rule,
        party=over.pop("party", None) or order.customer,
        hold_type=hold_type, status=status, severity=severity, reason=reason,
        evaluation_snapshot=snapshot if snapshot is not None else {
            "rule": rule.number if rule else "manual",
            "rule_type": rule.rule_type if rule else "manual",
            "severity": severity,
            "message": "Seeded evaluation",
            "observed": "1000.00",
            "threshold": "500.00",
        },
        **over,
    )
    hold.save()
    return hold


def _ordermanagement_amendment(tenant, order=None, change_type="quantity", status="draft",
                               reason="Customer doubled the quantity.", **over):
    """An amendment against an SCM order; a default order is made when none is supplied."""
    order = order or _ordermanagement_order(tenant, status="submitted")
    amendment = OrderAmendment(
        tenant=tenant, sales_order=order, change_type=change_type, status=status,
        reason=reason, **over,
    )
    amendment.save()
    return amendment


def _ordermanagement_amendment_line(amendment, order_line, operation="update",
                                    new_quantity="20.00", new_unit_price=None):
    line = OrderAmendmentLine(
        amendment=amendment, sales_order_line=order_line, operation=operation,
        new_quantity=Decimal(new_quantity) if new_quantity else None,
        new_unit_price=Decimal(new_unit_price) if new_unit_price else None,
    )
    line.full_clean()
    line.save()
    return line


def _ordermanagement_schedule(tenant, order, status="active", method="over_time",
                              standard="asc606", fiscal_period=None):
    schedule = RevenueSchedule(
        tenant=tenant, sales_order=order, status=status, method=method,
        compliance_standard=standard, fiscal_period=fiscal_period,
    )
    schedule.save()
    return schedule


def _ordermanagement_obligation(tenant, schedule, order_line=None, item=None,
                                 allocation_pct="50.00", recognize_on=None,
                                 obligation_type="goods", description="Goods delivered"):
    obligation = PerformanceObligation(
        schedule=schedule, sales_order_line=order_line, item=item,
        obligation_type=obligation_type, description=description,
        allocation_pct=Decimal(allocation_pct), recognize_on=recognize_on,
    )
    obligation.full_clean()
    obligation.save()
    return obligation


@pytest.fixture
def ordermanagement_tenant_a(db):
    return _OmTenant.objects.create(name="Order Mgmt A", slug="order-mgmt-a")


@pytest.fixture
def ordermanagement_tenant_b(db):
    return _OmTenant.objects.create(name="Order Mgmt B", slug="order-mgmt-b")


def _ordermanagement_admin(tenant, username):
    from apps.accounts.models import User as _OmUser

    # A raw ``password=`` kwarg is stored as the literal string, so ``client.login`` would
    # always fail. Hash it through the same setter the seeder uses.
    user = _OmUser.objects.create(
        username=username, tenant=tenant, is_tenant_admin=True, is_active=True,
        is_staff=True,
    )
    user.set_password("password")
    user.save()
    return user


@pytest.fixture
def ordermanagement_admin_a(ordermanagement_tenant_a):
    return _ordermanagement_admin(ordermanagement_tenant_a, "om_admin_a")


@pytest.fixture
def ordermanagement_admin_b(ordermanagement_tenant_b):
    return _ordermanagement_admin(ordermanagement_tenant_b, "om_admin_b")


@pytest.fixture
def ordermanagement_client_a(db, ordermanagement_admin_a):
    c = Client()
    assert c.login(username=ordermanagement_admin_a.username, password="password")
    return c


@pytest.fixture
def ordermanagement_client_b(db, ordermanagement_admin_b):
    c = Client()
    assert c.login(username=ordermanagement_admin_b.username, password="password")
    return c


#: Every 8.6 url name, pinned (L7). A name the contract lists but the URLconf lacks is a
#: NoReverseMatch the moment a template links to it.
ORDERMANAGEMENT_URL_NAMES = (
    "order_capture_board", "order_fulfillment_board", "order_history_board",
    "order_timeline", "reorder_customers_board", "renewals_due_board",
    "revenue_recognition_board", "order_validate", "order_repeat",
    "order_backorder_resolve",
    "order_validation_rule_list", "order_validation_rule_create",
    "order_validation_rule_detail", "order_validation_rule_edit",
    "order_validation_rule_delete",
    "order_hold_list", "order_hold_create", "order_hold_bulk_raise",
    "order_hold_bulk_clear", "order_hold_raise", "order_hold_detail",
    "order_hold_edit", "order_hold_delete", "order_hold_checkout",
    "order_hold_release_checkout", "order_hold_clear",
    "order_hold_clear_and_submit",
    "order_amendment_list", "order_amendment_create", "order_amendment_open_queue",
    "order_amendment_detail", "order_amendment_edit", "order_amendment_delete",
    "order_amendment_impact", "order_amendment_decide", "order_amendment_apply",
    "order_amendment_withdraw", "order_amendment_line_add",
    "order_amendment_line_edit", "order_amendment_line_delete",
    "revenue_schedule_list", "revenue_schedule_create", "revenue_schedule_detail",
    "revenue_schedule_edit", "revenue_schedule_delete",
    "revenue_schedule_obligation_add", "revenue_schedule_obligation_edit",
    "revenue_schedule_obligation_delete", "revenue_schedule_recognize",
)

#: kwargs needed to reverse a name that takes an argument. The bulk verbs take none.
ORDERMANAGEMENT_URL_KWARGS = {
    "order_timeline": {"pk": 1},
    "order_validate": {"order_pk": 1},
    "order_repeat": {"pk": 1},
    "order_backorder_resolve": {"allocation_pk": 1},
    "order_hold_raise": {"order_id": 1},
    "order_validation_rule_detail": {"pk": 1},
    "order_validation_rule_edit": {"pk": 1},
    "order_validation_rule_delete": {"pk": 1},
    "order_hold_detail": {"pk": 1},
    "order_hold_edit": {"pk": 1},
    "order_hold_delete": {"pk": 1},
    "order_hold_checkout": {"pk": 1},
    "order_hold_release_checkout": {"pk": 1},
    "order_hold_clear": {"pk": 1},
    "order_hold_clear_and_submit": {"pk": 1},
    "order_amendment_detail": {"pk": 1},
    "order_amendment_edit": {"pk": 1},
    "order_amendment_delete": {"pk": 1},
    "order_amendment_impact": {"pk": 1},
    "order_amendment_decide": {"pk": 1},
    "order_amendment_apply": {"pk": 1},
    "order_amendment_withdraw": {"pk": 1},
    "order_amendment_line_add": {"pk": 1},
    "order_amendment_line_edit": {"pk": 1, "line_pk": 1},
    "order_amendment_line_delete": {"pk": 1, "line_pk": 1},
    "revenue_schedule_detail": {"pk": 1},
    "revenue_schedule_edit": {"pk": 1},
    "revenue_schedule_delete": {"pk": 1},
    "revenue_schedule_obligation_add": {"pk": 1},
    "revenue_schedule_obligation_edit": {"pk": 1, "obligation_pk": 1},
    "revenue_schedule_obligation_delete": {"pk": 1, "obligation_pk": 1},
    "revenue_schedule_recognize": {"pk": 1},
}


ORDERMANAGEMENT_CHOICES = {
    "OrderValidationRule": {
        "RULE_TYPE_CHOICES": [
            ("credit_limit", "Credit Limit Exceeded"), ("order_value", "Order Value Ceiling"),
            ("margin_floor", "Margin Floor"), ("discount_ceiling", "Line Discount Ceiling"),
            ("unmapped_item", "Unmapped Item Present"),
            ("missing_ship_to", "Missing Ship-To Address"),
            ("expired_quote", "Source Quote Expired"),
            ("inactive_item", "Inactive Item On Order"),
        ],
        "SEVERITY_CHOICES": [
            ("block", "Block Submission"), ("hold", "Place On Hold"), ("warn", "Warn Only"),
        ],
        "ACTIVE_ON_CHOICES": [
            ("submit", "On Submit"), ("amendment", "On Amendment"),
            ("both", "On Submit And Amendment"),
        ],
    },
    "OrderHold": {
        "HOLD_TYPE_CHOICES": [
            ("credit", "Credit Hold"), ("fraud", "Fraud Review"),
            ("validation", "Validation Failure"), ("manual", "Manual Hold"),
        ],
        "STATUS_CHOICES": [
            ("open", "Open"), ("cleared", "Cleared"), ("superseded", "Superseded"),
        ],
    },
    "OrderAmendment": {
        "CHANGE_TYPE_CHOICES": [
            ("quantity", "Quantity Change"), ("price", "Price Change"),
            ("add_line", "Add Line"), ("remove_line", "Remove Line"),
            ("cancel", "Cancel Order"),
        ],
        "STATUS_CHOICES": [
            ("draft", "Draft"), ("pending", "Pending Approval"), ("approved", "Approved"),
            ("rejected", "Rejected"), ("applied", "Applied"), ("withdrawn", "Withdrawn"),
            ("superseded", "Superseded"),
        ],
    },
    "RevenueSchedule": {
        "STATUS_CHOICES": [
            ("draft", "Draft"), ("active", "Active"), ("complete", "Complete"),
            ("void", "Void"),
        ],
        "METHOD_CHOICES": [
            ("point_in_time", "Point In Time"), ("over_time", "Over Time"),
            ("milestone", "Milestone"),
        ],
        "COMPLIANCE_STANDARD_CHOICES": [
            ("asc606", "ASC 606"), ("ifrs15", "IFRS 15"), ("both", "ASC 606 & IFRS 15"),
        ],
    },
    "PerformanceObligation": {
        "OBLIGATION_TYPE_CHOICES": [
            ("goods", "Goods"), ("services", "Services"), ("subscription", "Subscription"),
            ("milestone", "Milestone"), ("warranty", "Warranty"),
        ],
        "RECOGNITION_METHOD_CHOICES": [
            ("point_in_time", "Point In Time"), ("over_time", "Over Time"),
            ("milestone", "Milestone"),
        ],
    },
}

ORDERMANAGEMENT_MODEL_FIELDS = {
    "OrderValidationRule": (
        "id", "tenant", "created_at", "updated_at", "number", "name", "rule_type",
        "severity", "active_on", "parameters", "party", "priority", "is_active",
        "description",
    ),
    "OrderHold": (
        "id", "tenant", "created_at", "updated_at", "number", "sales_order", "rule",
        "party", "hold_type", "reason", "severity", "status", "evaluation_snapshot",
        "raised_at", "raised_by", "checked_out_by", "checked_out_at", "cleared_by",
        "cleared_at", "clear_note", "superseded_by",
    ),
    "OrderAmendment": (
        "id", "tenant", "created_at", "updated_at", "number", "sales_order",
        "change_type", "status", "reason", "document", "impact_snapshot",
        "requested_by", "requested_at", "decided_by", "decided_at", "decision_note",
        "applied_at", "applied_by", "notes",
    ),
    "OrderAmendmentLine": (
        "id", "amendment", "sales_order_line", "operation", "new_quantity",
        "new_unit_price", "note",
    ),
    "RevenueSchedule": (
        "id", "tenant", "created_at", "updated_at", "number", "sales_order", "status",
        "method", "compliance_standard", "fiscal_period", "journal_entry", "notes",
    ),
    "PerformanceObligation": (
        "id", "schedule", "sales_order_line", "item", "obligation_type", "description",
        "allocation_pct", "recognition_method", "recognize_on", "evidence_reference",
        "allocated_amount", "recognized_amount", "milestone_label",
    ),
}


# ==============================================================================
# SALES 8.7 -- TERRITORY & QUOTA MANAGEMENT FIXTURES AND BUILDERS
# ==============================================================================

TERRITORYQUOTAMANAGEMENT_MODEL_CHOICES = {
    "TerritoryRule": {
        "SEGMENT_TYPE_CHOICES": [
            ("geographic", "Geographic"),
            ("industry", "Industry"),
            ("account_size", "Account Size"),
            ("product_line", "Product Line"),
            ("named_account", "Named Account"),
            ("mixed", "Mixed"),
        ],
        "MATCH_MODE_CHOICES": [
            ("all", "All Conditions (AND)"),
            ("any", "Any Condition (OR)"),
        ],
        "ALIGNMENT_TYPE_CHOICES": [
            ("primary", "Primary"),
            ("secondary", "Secondary"),
            ("overlay", "Overlay"),
        ],
        "ASSIGNMENT_SCOPE_CHOICES": [
            ("exact", "This Territory Only"),
            ("subtree", "This Territory And Children"),
        ],
    },
    "AccountTerritoryAssignment": {
        "ASSIGNMENT_SOURCE_CHOICES": [
            ("manual", "Manual"),
            ("rule", "Assignment Rule"),
            ("named_account", "Named Account"),
            ("inherited", "Inherited From Parent"),
        ],
    },
    "TerritoryMember": {
        "MEMBER_ROLE_CHOICES": [
            ("ae", "Account Executive"),
            ("sdr", "Sales Development Rep (SDR)"),
            ("hunter", "Hunter (New Business)"),
            ("farmer", "Farmer (Account Manager)"),
            ("overlay_specialist", "Overlay Specialist"),
            ("sales_engineer", "Sales Engineer / Solutions Architect"),
        ],
        "ASSIGNMENT_TYPE_CHOICES": [
            ("direct", "Direct Named"),
            ("shared", "Shared Territory Pool"),
            ("overlay", "Overlay Specialist"),
        ],
    },
    "QuotaPlan": {
        "METHOD_CHOICES": [
            ("top_down", "Top-Down"),
            ("bottom_up", "Bottom-Up"),
        ],
        "ALLOCATION_BASIS_CHOICES": [
            ("historical_revenue", "Historical Revenue"),
            ("pipeline", "Open Pipeline"),
            ("account_count", "Account Count"),
            ("territory_potential", "Territory Potential"),
            ("manual", "Manual"),
        ],
        "BASELINE_SOURCE_CHOICES": [
            ("previous_period", "Previous Period"),
            ("previous_year", "Previous Year"),
            ("custom", "Custom"),
        ],
        "TARGET_TYPE_CHOICES": [
            ("revenue", "Revenue"),
            ("units", "Units"),
            ("bookings", "Bookings"),
        ],
        "PHASING_CHOICES": [
            ("equal", "Equal"),
            ("seasonal", "Seasonal"),
        ],
        "STATUS_CHOICES": [
            ("draft", "Draft"),
            ("submitted", "Submitted for Approval"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("locked", "Locked"),
        ],
    },
}

TERRITORYQUOTAMANAGEMENT_MODEL_FIELDS = {
    "TerritoryRule": (
        "id", "tenant", "created_at", "updated_at", "number", "name",
        "segment_type", "match_mode", "alignment_type", "assignment_scope",
        "target_territory", "priority", "is_catch_all", "conditions",
        "effective_from", "effective_to", "is_active", "description",
        "last_run_at", "last_run_matched_count",
    ),
    "AccountTerritoryAssignment": (
        "id", "tenant", "created_at", "updated_at", "number", "account",
        "territory", "alignment_type", "assignment_source", "rule",
        "owner", "effective_from", "effective_to", "assigned_by", "notes",
    ),
    "TerritoryMember": (
        "id", "tenant", "created_at", "updated_at", "territory", "user",
        "member_role", "assignment_type", "coverage_split_pct",
        "paired_user", "is_primary", "effective_from", "effective_to", "notes",
    ),
    "QuotaPlan": (
        "id", "tenant", "created_at", "updated_at", "number", "quota_ref",
        "forecast_period", "territory", "owner", "method", "allocation_basis",
        "baseline_source", "growth_target_pct", "attrition_relief_pct",
        "stretch_target_pct", "uplift_allowed", "target_type", "phasing",
        "parameters", "status", "is_active", "notes", "submitted_by",
        "approved_by", "submitted_at", "approved_at", "calculated_at",
    ),
}


def _territoryquotamanagement_account(tenant, name="Acme Customer Account", **overrides):
    from apps.core.models import Party

    label = f"{timezone.now().timestamp():.6f}"[-6:]
    defaults = {
        "tenant": tenant,
        "name": f"{name} {label}",
        "kind": "organization",
    }
    defaults.update(overrides)
    return Party.objects.create(**defaults)


def _territoryquotamanagement_crm_territory(tenant, name="Americas", **overrides):
    from apps.crm.models import Territory

    label = f"{timezone.now().timestamp():.6f}"[-6:]
    defaults = {
        "tenant": tenant,
        "name": f"{name} {label}",
        "is_active": True,
        "description": "CRM Territory for Sales 8.7 test suite.",
    }
    defaults.update(overrides)
    return Territory.objects.create(**defaults)


def _territoryquotamanagement_crm_quota(
    tenant,
    owner=None,
    territory=None,
    target_amount=Decimal("100000.00"),
    period_type="quarter",
    period_year=None,
    period_number=1,
    **overrides,
):
    from apps.crm.models import SalesQuota

    if period_year is None:
        period_year = timezone.localdate().year
    defaults = {
        "tenant": tenant,
        "owner": owner,
        "territory": territory,
        "target_amount": target_amount,
        "period_type": period_type,
        "period_year": period_year,
        "period_number": period_number,
    }
    defaults.update(overrides)
    return SalesQuota.objects.create(**defaults)


def _territoryquotamanagement_rule(
    tenant,
    target_territory=None,
    name="Midwest Geo Rule",
    segment_type="geographic",
    match_mode="all",
    alignment_type="primary",
    assignment_scope="exact",
    conditions=None,
    **overrides,
):
    from apps.sales.models.TerritoryQuotaManagement.TerritoryRules import TerritoryRule

    if target_territory is None:
        target_territory = _territoryquotamanagement_crm_territory(tenant)
    if conditions is None and segment_type != "named_account" and not overrides.get("is_catch_all"):
        conditions = [{"field": "state", "operator": "eq", "value": "IL"}]
    defaults = {
        "tenant": tenant,
        "name": name,
        "target_territory": target_territory,
        "segment_type": segment_type,
        "match_mode": match_mode,
        "alignment_type": alignment_type,
        "assignment_scope": assignment_scope,
        "priority": 100,
        "is_active": True,
        "conditions": conditions if conditions is not None else [],
        "effective_from": timezone.localdate(),
    }
    defaults.update(overrides)
    return TerritoryRule.objects.create(**defaults)


def _territoryquotamanagement_assignment(
    tenant,
    account,
    territory=None,
    alignment_type="primary",
    assignment_source="manual",
    **overrides,
):
    from apps.sales.models.TerritoryQuotaManagement.AccountTerritoryAssignments import (
        AccountTerritoryAssignment,
    )

    if territory is None:
        territory = _territoryquotamanagement_crm_territory(tenant)
    defaults = {
        "tenant": tenant,
        "account": account,
        "territory": territory,
        "alignment_type": alignment_type,
        "assignment_source": assignment_source,
        "effective_from": timezone.localdate(),
    }
    defaults.update(overrides)
    return AccountTerritoryAssignment.objects.create(**defaults)


def _territoryquotamanagement_member(
    tenant,
    territory,
    user,
    member_role="ae",
    assignment_type="direct",
    is_primary=True,
    **overrides,
):
    from apps.sales.models.TerritoryQuotaManagement.TerritoryMembers import TerritoryMember

    defaults = {
        "tenant": tenant,
        "territory": territory,
        "user": user,
        "member_role": member_role,
        "assignment_type": assignment_type,
        "is_primary": is_primary,
        "coverage_split_pct": Decimal("100.00") if assignment_type == "direct" else None,
        "effective_from": timezone.localdate(),
    }
    defaults.update(overrides)
    return TerritoryMember.objects.create(**defaults)


def _territoryquotamanagement_quotaplan(
    tenant,
    quota_ref=None,
    forecast_period=None,
    owner=None,
    territory=None,
    method="top_down",
    allocation_basis="historical_revenue",
    status="draft",
    **overrides,
):
    from apps.sales.models.TerritoryQuotaManagement.QuotaPlans import QuotaPlan

    if territory is None:
        territory = _territoryquotamanagement_crm_territory(tenant)
    if forecast_period is None:
        forecast_period = _salesforecasting_period(tenant)
    if quota_ref is None:
        quota_ref = _territoryquotamanagement_crm_quota(
            tenant,
            owner=owner,
            territory=territory,
            period_type=forecast_period.period_type,
            period_year=forecast_period.period_year,
            period_number=forecast_period.period_number,
        )
    defaults = {
        "tenant": tenant,
        "quota_ref": quota_ref,
        "forecast_period": forecast_period,
        "territory": territory,
        "owner": owner,
        "method": method,
        "allocation_basis": allocation_basis,
        "baseline_source": "previous_year",
        "growth_target_pct": Decimal("15.00"),
        "attrition_relief_pct": Decimal("5.00"),
        "status": status,
        "target_type": "revenue",
        "phasing": "equal",
    }
    defaults.update(overrides)
    return QuotaPlan.objects.create(**defaults)


@pytest.fixture
def tqm_tenant_a(tenant_a):
    return tenant_a


@pytest.fixture
def tqm_tenant_b(tenant_b):
    return tenant_b


@pytest.fixture
def tqm_admin_a(admin_user):
    return admin_user


@pytest.fixture
def tqm_member_a(member_user):
    return member_user


@pytest.fixture
def tqm_account_a(tqm_tenant_a):
    return _territoryquotamanagement_account(tqm_tenant_a)


@pytest.fixture
def tqm_territory(tqm_tenant_a):
    return _territoryquotamanagement_crm_territory(tqm_tenant_a)


@pytest.fixture
def tqm_quota(tqm_tenant_a, tqm_territory, tqm_admin_a):
    return _territoryquotamanagement_crm_quota(
        tqm_tenant_a, territory=tqm_territory, owner=tqm_admin_a
    )


@pytest.fixture
def tqm_rule(tqm_tenant_a, tqm_territory):
    return _territoryquotamanagement_rule(tqm_tenant_a, target_territory=tqm_territory)


@pytest.fixture
def tqm_assignment(tqm_tenant_a, tqm_territory, tqm_account_a):
    return _territoryquotamanagement_assignment(
        tqm_tenant_a, account=tqm_account_a, territory=tqm_territory
    )


@pytest.fixture
def tqm_member(tqm_tenant_a, tqm_territory, tqm_admin_a):
    return _territoryquotamanagement_member(
        tqm_tenant_a, territory=tqm_territory, user=tqm_admin_a
    )


@pytest.fixture
def tqm_quotaplan(tqm_tenant_a, tqm_quota, tqm_territory, tqm_admin_a):
    return _territoryquotamanagement_quotaplan(
        tqm_tenant_a, quota_ref=tqm_quota, territory=tqm_territory, owner=tqm_admin_a
    )


# ==============================================================================
# SUB-MODULE 8.9 — SALES ENABLEMENT TEST CONTRACT & FIXTURES
# ==============================================================================

SALESENABLEMENT_PAGE_SIZE = 15

SALESENABLEMENT_MODEL_FIELDS = {
    "EnablementContent": (
        "id", "tenant", "created_at", "updated_at", "number", "title",
        "description", "content_type", "document", "external_url",
        "competitor", "target_stage", "target_persona", "pipeline_stage",
        "author", "tags", "version", "is_client_facing", "is_active",
        "expires_on", "view_count", "share_count",
    ),
    "SalesPlaybook": (
        "id", "tenant", "created_at", "updated_at", "number", "name",
        "summary", "motion_type", "pipeline", "status", "target_audience",
        "discovery_questions", "talk_tracks", "objection_scripts",
        "dos_and_donts", "exit_criteria", "owner", "version", "is_active",
    ),
    "SalesCertification": (
        "id", "tenant", "created_at", "updated_at", "number", "curriculum_name",
        "category", "rep", "status", "score_percent", "passing_score_percent",
        "certified_by", "certified_at", "expires_at", "accreditation_notes",
        "hrm_course",
    ),
    "CoachingScorecard": (
        "id", "tenant", "created_at", "updated_at", "number", "communication_log",
        "activity_log", "coach", "coachee", "recording_url", "discovery_score",
        "value_prop_score", "objection_handling_score", "next_steps_score",
        "overall_score", "talk_listen_ratio_percent", "call_sentiment",
        "transcript_summary", "key_strengths", "areas_for_improvement",
        "action_items", "review_status", "evaluated_on",
    ),
}

SALESENABLEMENT_CHOICES = {
    "EnablementContent": {
        "content_type": (
            ("battle_card", "Battle Card"),
            ("pitch_deck", "Pitch Deck"),
            ("case_study", "Case Study"),
            ("product_sheet", "Product One-Pager"),
            ("whitepaper", "Whitepaper / Research"),
            ("demo_script", "Demo Script / Flow"),
            ("email_template", "Outreach Email Template"),
            ("proposal_template", "Proposal Snippet"),
        ),
        "target_stage": (
            ("all", "All Stages"),
            ("prospecting", "Prospecting / Discovery"),
            ("qualification", "Qualification"),
            ("demo_eval", "Demo & Solution Evaluation"),
            ("proposal_neg", "Proposal & Negotiation"),
            ("closing", "Closing"),
            ("post_sale", "Expansion & Retention"),
        ),
        "target_persona": (
            ("all", "All Personas"),
            ("c_level", "Executive / C-Suite"),
            ("vp_director", "VP / Director"),
            ("manager", "Functional Manager"),
            ("technical_buyer", "IT & Technical Buyer"),
            ("end_user", "End-User Specialist"),
            ("procurement", "Procurement / Legal"),
        ),
    },
    "SalesPlaybook": {
        "motion_type": (
            ("new_business", "New Business (Land)"),
            ("expansion", "Account Expansion (Upsell/Cross-sell)"),
            ("renewal", "Contract Renewal"),
            ("competitive_displacement", "Competitive Takeout / Displacement"),
            ("partner_co_selling", "Partner Co-Selling"),
        ),
        "status": (
            ("draft", "Draft"),
            ("published", "Published"),
            ("under_review", "Under Review"),
            ("archived", "Archived"),
        ),
    },
    "SalesCertification": {
        "category": (
            ("onboarding", "New Rep Onboarding Curriculum"),
            ("product_certification", "Product / Solution Certification"),
            ("methodology", "Sales Methodology (MEDDPICC, Challenger, SPICED)"),
            ("compliance", "Security, Privacy & Regulatory Compliance"),
            ("pitch_accreditation", "Pitch & Demo Accreditation"),
        ),
        "status": (
            ("enrolled", "Enrolled / In Progress"),
            ("completed", "Completed / Passed"),
            ("failed", "Failed / Requires Retake"),
            ("expired", "Expired"),
        ),
    },
    "CoachingScorecard": {
        "call_sentiment": (
            ("positive", "Positive / Enthusiastic"),
            ("neutral", "Neutral / Professional"),
            ("skeptical", "Skeptical / Challenging"),
            ("negative", "Negative / Frustrated"),
        ),
        "review_status": (
            ("draft", "Draft Evaluation"),
            ("shared", "Shared with Rep"),
            ("acknowledged", "Acknowledged by Rep"),
        ),
    },
}


def _salesenablement_competitor(tenant, name="Alpha Corp", **overrides):
    from apps.core.models import Party
    from apps.sales.models import CompetitorProfile

    label = f"{timezone.now().timestamp():.6f}"[-6:]
    party = Party.objects.create(
        tenant=tenant,
        name=f"{name} {label}",
        kind="organization",
    )
    defaults = {
        "tenant": tenant,
        "party": party,
        "market_position": "Tier 1 Enterprise Competitor",
        "strengths": "Brand legacy, large salesforce",
        "weaknesses": "Outdated UI, high implementation cost",
        "win_strategy": "Highlight modern API and total cost of ownership",
        "is_active": True,
    }
    defaults.update(overrides)
    return CompetitorProfile.objects.create(**defaults)


def _salesenablement_document(tenant, name="Collateral Doc", **overrides):
    from apps.core.models import Document

    label = f"{timezone.now().timestamp():.6f}"[-6:]
    defaults = {
        "tenant": tenant,
        "name": f"{name} {label}",
    }
    defaults.update(overrides)
    return Document.objects.create(**defaults)


def _salesenablement_content(tenant, author=None, **overrides):
    from apps.sales.models import EnablementContent

    label = f"{timezone.now().timestamp():.6f}"[-6:]
    defaults = {
        "tenant": tenant,
        "title": f"Enterprise Pitch Deck {label}",
        "content_type": "pitch_deck",
        "version": "1.0",
        "target_persona": "c_level",
        "description": "Standard enterprise executive presentation.",
        "tags": "enterprise,pitch,deck",
        "is_client_facing": True,
        "is_active": True,
        "author": author,
    }
    defaults.update(overrides)
    return EnablementContent.objects.create(**defaults)


def _salesenablement_playbook(tenant, owner=None, **overrides):
    from apps.sales.models import SalesPlaybook

    label = f"{timezone.now().timestamp():.6f}"[-6:]
    defaults = {
        "tenant": tenant,
        "name": f"Enterprise New Logo Playbook {label}",
        "motion_type": "new_business",
        "version": "1.0",
        "summary": "Step-by-step guidance for acquiring Fortune 500 accounts.",
        "target_audience": "Enterprise Account Executives",
        "discovery_questions": "MEDDPICC: Metrics, Economic Buyer, Decision Criteria",
        "talk_tracks": "Focus on high ROI and quick time to value.",
        "objection_scripts": "Pricing objection: Anchor on ROI.",
        "dos_and_donts": "Do: quantify ROI. Don't: trash competitor.",
        "exit_criteria": "Signed MSA and Security Addendum.",
        "status": "published",
        "is_active": True,
        "owner": owner,
    }
    defaults.update(overrides)
    return SalesPlaybook.objects.create(**defaults)


def _salesenablement_certification(tenant, rep=None, certified_by=None, **overrides):
    from apps.sales.models import SalesCertification

    label = f"{timezone.now().timestamp():.6f}"[-6:]
    defaults = {
        "tenant": tenant,
        "curriculum_name": f"Enterprise Sales Methodology {label}",
        "category": "methodology",
        "rep": rep,
        "status": "enrolled",
        "passing_score_percent": Decimal("80.00"),
        "accreditation_notes": "Internal Sales Academy",
    }
    defaults.update(overrides)
    return SalesCertification.objects.create(**defaults)


def _salesenablement_scorecard(tenant, coach=None, coachee=None, communication_log=None, **overrides):
    from apps.crm.models import CommunicationLog
    from apps.sales.models import CoachingScorecard

    if communication_log is None:
        communication_log = CommunicationLog.objects.create(
            tenant=tenant,
            channel="call",
            subject="Coaching Discovery Call",
            owner=coach or coachee,
        )
    label = f"{timezone.now().timestamp():.6f}"[-6:]
    defaults = {
        "tenant": tenant,
        "communication_log": communication_log,
        "evaluated_on": timezone.now().date(),
        "coach": coach,
        "coachee": coachee,
        "discovery_score": 4,
        "value_prop_score": 4,
        "objection_handling_score": 4,
        "next_steps_score": 4,
        "talk_listen_ratio_percent": 45,
        "call_sentiment": "positive",
        "key_strengths": "Great active listening and pain point qualification.",
        "areas_for_improvement": "More concrete next step timelines.",
        "action_items": "Send follow-up recap email within 2 hours.",
        "review_status": "draft",
    }
    defaults.update(overrides)
    return CoachingScorecard.objects.create(**defaults)


@pytest.fixture
def enablement_content_a(tenant_a, admin_user):
    return _salesenablement_content(tenant_a, author=admin_user)


@pytest.fixture
def enablement_content_b(tenant_b, admin_b):
    return _salesenablement_content(tenant_b, author=admin_b)


@pytest.fixture
def sales_playbook_a(tenant_a, admin_user):
    return _salesenablement_playbook(tenant_a, owner=admin_user)


@pytest.fixture
def sales_playbook_b(tenant_b, admin_b):
    return _salesenablement_playbook(tenant_b, owner=admin_b)


@pytest.fixture
def sales_certification_a(tenant_a, member_user, admin_user):
    return _salesenablement_certification(tenant_a, rep=member_user, certified_by=admin_user)


@pytest.fixture
def sales_certification_b(tenant_b, admin_b):
    return _salesenablement_certification(tenant_b, rep=admin_b, certified_by=admin_b)


@pytest.fixture
def coaching_scorecard_a(tenant_a, admin_user, member_user):
    return _salesenablement_scorecard(tenant_a, coach=admin_user, coachee=member_user)


@pytest.fixture
def coaching_scorecard_b(tenant_b, admin_b):
    return _salesenablement_scorecard(tenant_b, coach=admin_b, coachee=admin_b)


# ==============================================================================
# SUB-MODULE 8.10 — INCENTIVE COMPENSATION MANAGEMENT TEST CONTRACT & FIXTURES
# ==============================================================================

INCENTIVECOMPENSATION_PAGE_SIZE = 15

INCENTIVECOMPENSATION_MODEL_FIELDS = {
    "CommissionPlan": (
        "id", "tenant", "created_at", "updated_at", "number", "name", "code",
        "description", "plan_type", "tier_mode", "status", "payout_frequency",
        "effective_start", "effective_end", "currency", "target_region",
        "base_rate_pct", "tiers_config", "spif_config", "draw_amount",
        "is_draw_recoverable", "clawback_window_days", "tax_withholding_pct",
        "sales_quota", "owner",
    ),
    "CommissionEarning": (
        "id", "tenant", "created_at", "updated_at", "number", "plan", "payee",
        "opportunity", "sales_order", "credit_type", "split_percentage",
        "deal_amount", "credited_volume", "attainment_pct_at_close",
        "applied_rate_pct", "base_commission_amount", "spif_amount",
        "gross_commission", "deal_currency", "exchange_rate", "functional_amount",
        "status", "earned_date", "clawback_parent", "statement",
    ),
    "CommissionStatement": (
        "id", "tenant", "created_at", "updated_at", "number", "statement_number",
        "payee", "plan", "period_start", "period_end", "status",
        "total_credited_volume", "total_base_commission", "total_accelerator_amount",
        "total_spif_amount", "gross_earnings", "draw_advance_paid", "draw_recovered",
        "adjustments_amount", "clawbacks_deducted", "tax_withholding_amount",
        "net_payout", "approved_by", "approved_at", "locked_at", "payroll_run",
        "notes",
    ),
    "CommissionAdjustment": (
        "id", "tenant", "created_at", "updated_at", "number", "statement",
        "earning", "payee", "adjustment_type", "amount", "status", "reason",
        "dispute_comments", "requested_by", "approved_by", "effective_date",
    ),
}

INCENTIVECOMPENSATION_CHOICES = {
    "CommissionPlan": {
        "plan_type": (
            ("flat_revenue", "Flat Revenue %"),
            ("gross_margin", "Gross Margin %"),
            ("tiered_quota", "Tiered Quota Attainment"),
            ("spif_only", "SPIF / Bonus Only"),
            ("hybrid", "Hybrid (Revenue + Tier + SPIF)"),
        ),
        "tier_mode": (
            ("incremental", "Incremental / Marginal Brackets"),
            ("retroactive", "Retroactive / All-In Payout"),
            ("not_applicable", "Not Applicable (Flat/No Tiers)"),
        ),
        "status": (
            ("draft", "Draft"),
            ("active", "Active"),
            ("archived", "Archived"),
        ),
        "payout_frequency": (
            ("monthly", "Monthly"),
            ("quarterly", "Quarterly"),
            ("semi_annual", "Semi-Annual"),
            ("annual", "Annual"),
        ),
    },
    "CommissionEarning": {
        "credit_type": (
            ("direct", "Direct Rep Credit"),
            ("split", "Team Deal Split"),
            ("overlay", "Overlay / Specialist Credit"),
            ("manager_override", "Manager Rollup / Override"),
            ("spif_bonus", "SPIF Campaign Bonus"),
        ),
        "status": (
            ("pending", "Pending Calculation"),
            ("calculated", "Calculated / Verified"),
            ("approved", "Approved for Payout"),
            ("paid", "Paid out"),
            ("clawed_back", "Clawed Back"),
        ),
    },
    "CommissionStatement": {
        "status": (
            ("draft", "Draft / Calculation"),
            ("under_review", "Under Rep Review"),
            ("approved", "Approved by Manager"),
            ("locked", "Locked / Finalized"),
            ("exported", "Exported to Payroll"),
            ("paid", "Settled / Paid"),
        ),
    },
    "CommissionAdjustment": {
        "adjustment_type": (
            ("clawback_cancellation", "Clawback — Deal Cancelled"),
            ("dispute_resolution", "Dispute Resolution"),
            ("manual_bonus", "Discretionary / Manual Bonus"),
            ("draw_recovery", "Draw Recovery Deduction"),
            ("split_correction", "Deal Split Correction"),
            ("true_up_reconciliation", "Period True-up Reconciliation"),
        ),
        "status": (
            ("draft", "Draft"),
            ("submitted", "Submitted / Disputed"),
            ("under_review", "Under Review"),
            ("disputed", "Active Dispute"),
            ("approved", "Approved"),
            ("applied", "Applied to Statement"),
            ("rejected", "Rejected"),
        ),
    },
}


def _incentivecompensation_currency(code="USD", name="US Dollar", symbol="$"):
    from apps.accounting.models import Currency
    currency, _ = Currency.objects.get_or_create(
        code=code,
        defaults={"name": name, "symbol": symbol, "is_active": True},
    )
    return currency


def _incentivecompensation_plan(tenant, currency=None, owner=None, **overrides):
    import uuid
    from apps.sales.models import CommissionPlan
    if currency is None:
        currency = _incentivecompensation_currency()
    defaults = {
        "tenant": tenant,
        "name": "Standard Enterprise Quota Plan",
        "code": f"std-plan-{tenant.id}-{uuid.uuid4().hex[:10]}",
        "description": "Standard AE baseline compensation plan.",
        "plan_type": "flat_revenue",
        "tier_mode": "not_applicable",
        "status": "active",
        "payout_frequency": "monthly",
        "effective_start": timezone.now().date(),
        "currency": currency,
        "base_rate_pct": Decimal("8.50"),
        "tiers_config": [],
        "spif_config": [],
        "draw_amount": Decimal("0.00"),
        "is_draw_recoverable": True,
        "clawback_window_days": 90,
        "tax_withholding_pct": Decimal("20.00"),
        "owner": owner,
    }
    defaults.update(overrides)
    return CommissionPlan.objects.create(**defaults)


def _incentivecompensation_earning(tenant, plan=None, payee=None, currency=None, **overrides):
    from apps.sales.models import CommissionEarning
    if currency is None:
        currency = _incentivecompensation_currency()
    if plan is None:
        plan = _incentivecompensation_plan(tenant, currency=currency)
    defaults = {
        "tenant": tenant,
        "plan": plan,
        "payee": payee,
        "credit_type": "direct",
        "split_percentage": Decimal("100.00"),
        "deal_amount": Decimal("50000.00"),
        "deal_currency": currency,
        "credited_volume": Decimal("50000.00"),
        "attainment_pct_at_close": Decimal("100.00"),
        "applied_rate_pct": Decimal("8.50"),
        "base_commission_amount": Decimal("4250.00"),
        "spif_amount": Decimal("0.00"),
        "gross_commission": Decimal("4250.00"),
        "exchange_rate": Decimal("1.000000"),
        "functional_amount": Decimal("4250.00"),
        "status": "calculated",
        "earned_date": timezone.now().date(),
    }
    defaults.update(overrides)
    return CommissionEarning.objects.create(**defaults)


def _incentivecompensation_statement(tenant, plan=None, payee=None, **overrides):
    from apps.sales.models import CommissionStatement
    if plan is None:
        plan = _incentivecompensation_plan(tenant)
    today = timezone.now().date()
    p_start = today.replace(day=1)
    defaults = {
        "tenant": tenant,
        "statement_number": f"STMT-{p_start.strftime('%Y%m')}-{payee.id if payee else 1}",
        "payee": payee,
        "plan": plan,
        "period_start": p_start,
        "period_end": today,
        "status": "draft",
        "total_credited_volume": Decimal("50000.00"),
        "total_base_commission": Decimal("4250.00"),
        "total_accelerator_amount": Decimal("0.00"),
        "total_spif_amount": Decimal("0.00"),
        "gross_earnings": Decimal("4250.00"),
        "draw_advance_paid": Decimal("0.00"),
        "draw_recovered": Decimal("0.00"),
        "adjustments_amount": Decimal("0.00"),
        "clawbacks_deducted": Decimal("0.00"),
        "tax_withholding_amount": Decimal("850.00"),
        "net_payout": Decimal("3400.00"),
    }
    defaults.update(overrides)
    return CommissionStatement.objects.create(**defaults)


def _incentivecompensation_adjustment(tenant, payee=None, statement=None, earning=None, **overrides):
    from apps.sales.models import CommissionAdjustment
    defaults = {
        "tenant": tenant,
        "statement": statement,
        "earning": earning,
        "payee": payee,
        "adjustment_type": "manual_bonus",
        "amount": Decimal("500.00"),
        "status": "draft",
        "reason": "Quarterly performance bonus adjustment.",
        "effective_date": timezone.now().date(),
    }
    defaults.update(overrides)
    return CommissionAdjustment.objects.create(**defaults)


@pytest.fixture
def icm_currency(db):
    return _incentivecompensation_currency()


@pytest.fixture
def commission_plan_a(tenant_a, icm_currency, admin_user):
    return _incentivecompensation_plan(tenant_a, currency=icm_currency, owner=admin_user)


@pytest.fixture
def commission_plan_b(tenant_b, icm_currency, admin_b):
    return _incentivecompensation_plan(tenant_b, currency=icm_currency, owner=admin_b)


@pytest.fixture
def commission_earning_a(tenant_a, commission_plan_a, member_user, icm_currency):
    return _incentivecompensation_earning(tenant_a, plan=commission_plan_a, payee=member_user, currency=icm_currency)


@pytest.fixture
def commission_earning_b(tenant_b, commission_plan_b, admin_b, icm_currency):
    return _incentivecompensation_earning(tenant_b, plan=commission_plan_b, payee=admin_b, currency=icm_currency)


@pytest.fixture
def commission_statement_a(tenant_a, commission_plan_a, member_user):
    return _incentivecompensation_statement(tenant_a, plan=commission_plan_a, payee=member_user)


@pytest.fixture
def commission_statement_b(tenant_b, commission_plan_b, admin_b):
    return _incentivecompensation_statement(tenant_b, plan=commission_plan_b, payee=admin_b)


@pytest.fixture
def commission_adjustment_a(tenant_a, member_user, commission_statement_a, commission_earning_a):
    return _incentivecompensation_adjustment(
        tenant_a, payee=member_user, statement=commission_statement_a, earning=commission_earning_a
    )


@pytest.fixture
def commission_adjustment_b(tenant_b, admin_b, commission_statement_b, commission_earning_b):
    return _incentivecompensation_adjustment(
        tenant_b, payee=admin_b, statement=commission_statement_b, earning=commission_earning_b
    )


# ==============================================================================
# Sales 8.11 — Customer Success & Account Management Fixtures & Test Contract
# ==============================================================================

CUSTOMERSUCCESS_MODEL_FIELDS = {
    "CustomerHealthScore": (
        "id", "tenant", "created_at", "updated_at", "number", "account",
        "evaluation_date", "overall_score", "health_band", "previous_score",
        "score_trend", "product_usage_score", "support_ticket_score",
        "nps_sentiment_score", "relationship_score", "renewal_risk_score",
        "risk_level", "risk_reasons", "active_alert_message", "is_churn_risk",
        "license_utilization_pct", "open_support_tickets", "latest_nps",
        "last_activity_date", "notes",
    ),
    "CustomerRenewal": (
        "id", "tenant", "created_at", "updated_at", "number", "account",
        "owner", "original_order", "renewal_name", "contract_reference",
        "current_arr", "projected_renewal_arr", "expansion_amount", "currency",
        "renewal_date", "target_close_date", "stage", "churn_risk_flag",
        "renewal_probability_pct", "auto_renewal", "notice_period_days",
        "expansion_opportunity", "notes",
    ),
    "CustomerOnboarding": (
        "id", "tenant", "created_at", "updated_at", "number", "account",
        "lead_csm", "sales_order", "title", "playbook_template", "stage",
        "status", "kickoff_date", "target_go_live_date", "actual_go_live_date",
        "time_to_value_days", "progress_pct", "executive_sponsor_name",
        "executive_sponsor_email", "milestones_config", "blockers",
        "success_criteria",
    ),
    "CustomerBusinessReview": (
        "id", "tenant", "created_at", "updated_at", "number", "account",
        "lead_csm", "account_plan", "title", "review_period", "review_year",
        "scheduled_date", "completed_date", "status", "template_type",
        "executive_sponsor_attended", "client_attendees", "internal_attendees",
        "health_score_at_review", "key_achievements", "challenges_and_risks",
        "action_items", "is_referenceable", "reference_types_permitted",
        "case_study_status", "testimonial_quote", "notes",
    ),
}

CUSTOMERSUCCESS_CHOICES = {
    "CustomerHealthScore": {
        "health_band": (("green", "Healthy (75-100)"), ("yellow", "Needs Attention (50-74)"), ("red", "At Risk (0-49)")),
        "score_trend": (("improving", "Improving"), ("stable", "Stable"), ("declining", "Declining")),
        "risk_level": (("low", "Low Risk"), ("medium", "Medium Risk"), ("high", "High Risk"), ("critical", "Critical Risk")),
    },
    "CustomerRenewal": {
        "stage": (
            ("upcoming", "Upcoming (90+ Days)"), ("engagement", "Active Engagement"),
            ("proposal_sent", "Renewal Proposal Sent"), ("negotiation", "Contract Negotiation"),
            ("renewed", "Renewed (Closed-Won)"), ("expanded", "Renewed & Expanded"),
            ("churned", "Churned (Closed-Lost)"), ("contracted_down", "Contracted Down"),
        ),
        "churn_risk_flag": (("low", "Low"), ("medium", "Medium"), ("high", "High"), ("critical", "Critical")),
    },
    "CustomerOnboarding": {
        "playbook_template": (
            ("enterprise_high_touch", "Enterprise High-Touch (90 Days)"),
            ("midmarket_standard", "Mid-Market Standard (45 Days)"),
            ("smb_accelerated", "SMB Accelerated (21 Days)"),
            ("tech_touch_automated", "Tech-Touch Automated"),
        ),
        "stage": (
            ("kickoff", "Kickoff & Alignment"), ("architecture_design", "Architecture & Solution Design"),
            ("configuration", "System Configuration"), ("data_migration", "Data Migration"),
            ("training", "User & Admin Training"), ("uat_testing", "User Acceptance Testing"),
            ("go_live", "Production Go-Live"), ("completed", "Completed & Handed to CS"),
            ("stalled", "Stalled / On Hold"),
        ),
        "status": (
            ("not_started", "Not Started"), ("in_progress", "In Progress"),
            ("on_track", "On Track"), ("at_risk", "At Risk"),
            ("blocked", "Blocked"), ("completed", "Completed"),
        ),
    },
    "CustomerBusinessReview": {
        "review_period": (
            ("q1", "Q1 Review"), ("q2", "Q2 Review"), ("q3", "Q3 Review"),
            ("q4", "Q4 Review"), ("mid_year", "Mid-Year Review"),
            ("annual", "Annual Executive Review"),
        ),
        "status": (
            ("scheduled", "Scheduled"), ("materials_prepared", "Materials Prepared"),
            ("conducted", "Conducted / Completed"), ("follow_up_sent", "Follow-Up Action Items Sent"),
            ("cancelled", "Cancelled"),
        ),
        "template_type": (
            ("executive_value", "Executive Value & ROI Review"),
            ("technical_roadmap", "Technical Architecture & Roadmap"),
            ("renewal_alignment", "Renewal & Partnership Alignment"),
            ("operational_cadence", "Standard Operational Cadence"),
        ),
        "case_study_status": (
            ("none", "Not Candidate"), ("identified", "Candidate Identified"),
            ("interview_scheduled", "Interview Scheduled"), ("drafting", "Drafting Case Study"),
            ("approved", "Client Approved"), ("published", "Published"),
        ),
    },
}

CUSTOMERSUCCESS_URLS = {
    "customer_health_console": "customer-success/health-console/",
    "customer_renewal_pipeline": "customer-success/renewal-pipeline/",
    "customer_onboarding_hub": "customer-success/onboarding-hub/",
    "customer_advocacy_hub": "customer-success/advocacy-hub/",
    "customer_qbr_studio": "customer-success/qbr-studio/",
    "customer_health_score_list": "customer-success/health-scores/",
    "customer_health_score_create": "customer-success/health-scores/create/",
    "customer_health_score_detail": "customer-success/health-scores/<int:pk>/",
    "customer_health_score_edit": "customer-success/health-scores/<int:pk>/edit/",
    "customer_health_score_delete": "customer-success/health-scores/<int:pk>/delete/",
    "customer_renewal_list": "customer-success/renewals/",
    "customer_renewal_create": "customer-success/renewals/create/",
    "customer_renewal_detail": "customer-success/renewals/<int:pk>/",
    "customer_renewal_edit": "customer-success/renewals/<int:pk>/edit/",
    "customer_renewal_delete": "customer-success/renewals/<int:pk>/delete/",
    "customer_onboarding_list": "customer-success/onboardings/",
    "customer_onboarding_create": "customer-success/onboardings/create/",
    "customer_onboarding_detail": "customer-success/onboardings/<int:pk>/",
    "customer_onboarding_edit": "customer-success/onboardings/<int:pk>/edit/",
    "customer_onboarding_delete": "customer-success/onboardings/<int:pk>/delete/",
    "customer_business_review_list": "customer-success/business-reviews/",
    "customer_business_review_create": "customer-success/business-reviews/create/",
    "customer_business_review_detail": "customer-success/business-reviews/<int:pk>/",
    "customer_business_review_edit": "customer-success/business-reviews/<int:pk>/edit/",
    "customer_business_review_delete": "customer-success/business-reviews/<int:pk>/delete/",
}


def _customersuccess_party(tenant, name="Customer Alpha"):
    from apps.core.models import Party, PartyRole
    party = Party.objects.create(tenant=tenant, name=name, kind="organization")
    PartyRole.objects.create(tenant=tenant, party=party, role="customer")
    return party


def _customersuccess_health_score(tenant, account, **overrides):
    from apps.sales.models import CustomerHealthScore
    from django.utils import timezone
    defaults = {
        "tenant": tenant,
        "account": account,
        "evaluation_date": timezone.localdate(),
        "overall_score": 85,
        "health_band": "green",
        "score_trend": "improving",
        "risk_level": "low",
        "product_usage_score": 85,
        "support_ticket_score": 85,
        "nps_sentiment_score": 85,
        "relationship_score": 85,
        "renewal_risk_score": 85,
        "risk_reasons": [],
        "active_alert_message": "",
        "is_churn_risk": False,
        "license_utilization_pct": Decimal("85.00"),
        "open_support_tickets": 1,
        "latest_nps": 50,
        "notes": "Healthy account.",
    }
    defaults.update(overrides)
    return CustomerHealthScore.objects.create(**defaults)


def _customersuccess_renewal(tenant, account, owner, currency, **overrides):
    from apps.sales.models import CustomerRenewal
    from datetime import date
    defaults = {
        "tenant": tenant,
        "account": account,
        "owner": owner,
        "currency": currency,
        "renewal_name": f"{account.name} 2026 Renewal",
        "contract_reference": "CNT-TEST-01",
        "current_arr": Decimal("100000.00"),
        "projected_renewal_arr": Decimal("110000.00"),
        "expansion_amount": Decimal("10000.00"),
        "renewal_date": date(2026, 6, 1),
        "target_close_date": date(2026, 5, 15),
        "stage": "upcoming",
        "churn_risk_flag": "low",
        "renewal_probability_pct": 80,
        "auto_renewal": False,
        "notice_period_days": 60,
        "notes": "Targeting expansion.",
    }
    defaults.update(overrides)
    return CustomerRenewal.objects.create(**defaults)


def _customersuccess_onboarding(tenant, account, lead_csm, **overrides):
    from apps.sales.models import CustomerOnboarding
    from datetime import date
    defaults = {
        "tenant": tenant,
        "account": account,
        "lead_csm": lead_csm,
        "title": f"{account.name} Implementation",
        "playbook_template": "enterprise_high_touch",
        "stage": "kickoff",
        "status": "in_progress",
        "kickoff_date": date(2026, 2, 1),
        "target_go_live_date": date(2026, 4, 30),
        "progress_pct": 20,
        "executive_sponsor_name": "Alice Smith",
        "executive_sponsor_email": "alice@example.com",
        "milestones_config": [{"name": "Kickoff", "due": "2026-02-05", "done": True}],
        "success_criteria": "Successful deployment.",
        "blockers": "",
    }
    defaults.update(overrides)
    return CustomerOnboarding.objects.create(**defaults)


def _customersuccess_business_review(tenant, account, lead_csm, **overrides):
    from apps.sales.models import CustomerBusinessReview
    from datetime import date
    defaults = {
        "tenant": tenant,
        "account": account,
        "lead_csm": lead_csm,
        "title": f"{account.name} Q1 Executive Review",
        "review_period": "q1",
        "review_year": 2026,
        "scheduled_date": date(2026, 3, 15),
        "status": "scheduled",
        "template_type": "executive_value",
        "executive_sponsor_attended": True,
        "client_attendees": "Alice Smith (VP)",
        "internal_attendees": "CSM Lead",
        "health_score_at_review": 85,
        "key_achievements": "Time to value decreased.",
        "challenges_and_risks": "",
        "action_items": [],
        "is_referenceable": True,
        "reference_types_permitted": ["case_study", "reference_calls"],
        "case_study_status": "identified",
        "testimonial_quote": "Great partnership.",
        "notes": "",
    }
    defaults.update(overrides)
    return CustomerBusinessReview.objects.create(**defaults)


@pytest.fixture
def cs_account_a(tenant_a):
    return _customersuccess_party(tenant_a, name="Acme Customer A")


@pytest.fixture
def cs_account_b(tenant_b):
    return _customersuccess_party(tenant_b, name="Globex Customer B")


@pytest.fixture
def cs_health_score_a(tenant_a, cs_account_a):
    return _customersuccess_health_score(tenant_a, cs_account_a)


@pytest.fixture
def cs_health_score_b(tenant_b, cs_account_b):
    return _customersuccess_health_score(tenant_b, cs_account_b)


@pytest.fixture
def cs_renewal_a(tenant_a, cs_account_a, admin_user, icm_currency):
    return _customersuccess_renewal(tenant_a, cs_account_a, admin_user, icm_currency)


@pytest.fixture
def cs_renewal_b(tenant_b, cs_account_b, admin_b, icm_currency):
    return _customersuccess_renewal(tenant_b, cs_account_b, admin_b, icm_currency)


@pytest.fixture
def cs_onboarding_a(tenant_a, cs_account_a, admin_user):
    return _customersuccess_onboarding(tenant_a, cs_account_a, admin_user)


@pytest.fixture
def cs_onboarding_b(tenant_b, cs_account_b, admin_b):
    return _customersuccess_onboarding(tenant_b, cs_account_b, admin_b)


@pytest.fixture
def cs_qbr_a(tenant_a, cs_account_a, admin_user):
    return _customersuccess_business_review(tenant_a, cs_account_a, admin_user)


@pytest.fixture
def cs_qbr_b(tenant_b, cs_account_b, admin_b):
    return _customersuccess_business_review(tenant_b, cs_account_b, admin_b)


# ==============================================================================
# 8.14 Partner & Channel Management Test Contract & Fixtures
# ==============================================================================

PARTNERCHANNEL_PAGE_SIZE = 15

PARTNERCHANNEL_MODEL_FIELDS = {
    "PartnerProfile": (
        "tenant", "created_at", "updated_at", "number", "partner", "partner_type",
        "onboarding_status", "tier", "tier_effective_date", "tier_review_date",
        "application_date", "agreement_signed_at", "agreement_document", "channel_manager",
        "authorized_territory", "currency", "annual_revenue_target", "actual_revenue_ytd",
        "required_certifications_count", "active_certifications_count", "base_discount_pct",
        "deal_reg_margin_pct", "portal_access_enabled", "notes",
    ),
    "DealRegistration": (
        "tenant", "created_at", "updated_at", "number", "partner", "customer_account",
        "deal_name", "estimated_value", "currency", "expected_close_date", "submission_date",
        "status", "rejection_reason", "protection_start_date", "protection_end_date",
        "exclusivity_status", "protected_margin_pct", "extension_count", "is_conflicted",
        "conflict_summary", "opportunity", "reviewed_by", "reviewed_at", "partner_rep_name",
        "partner_rep_email", "notes",
    ),
    "JointAccountPlan": (
        "tenant", "created_at", "updated_at", "number", "partner", "client_account",
        "plan_name", "plan_year", "period_start", "period_end", "status",
        "target_revenue", "actual_revenue", "currency", "vendor_lead", "partner_lead_name",
        "partner_lead_email", "co_sell_motion", "strategic_objectives",
        "joint_value_proposition", "action_items", "collateral_document", "notes",
    ),
    "ChannelConflict": (
        "tenant", "created_at", "updated_at", "number", "conflict_type", "severity",
        "status", "deal_registration", "opportunity", "claimant_partner", "competing_partner",
        "direct_sales_rep", "client_account", "territory", "escalation_level",
        "escalated_to", "resolution_outcome", "split_percentage", "resolution_rationale",
        "resolved_by", "resolved_at", "description",
    ),
}

PARTNERCHANNEL_CHOICES = {
    "PartnerProfile": {
        "partner_type": (
            ("reseller", "Reseller / VAR"),
            ("system_integrator", "System Integrator (SI)"),
            ("distributor", "Distributor"),
            ("isv_technology", "ISV / Technology Partner"),
            ("referral", "Referral / Affiliate"),
            ("consulting", "Consulting & Advisory"),
        ),
        "onboarding_status": (
            ("applied", "Application Submitted"),
            ("under_review", "Under Review"),
            ("agreement_pending", "Agreement Pending"),
            ("onboarding", "Onboarding & Training"),
            ("active", "Active Certified Partner"),
            ("suspended", "Suspended"),
            ("terminated", "Terminated"),
        ),
        "tier": (
            ("registered", "Registered Partner"),
            ("bronze", "Bronze"),
            ("silver", "Silver"),
            ("gold", "Gold"),
            ("platinum", "Platinum"),
        ),
    },
    "DealRegistration": {
        "status": (
            ("submitted", "Submitted / Pending"),
            ("under_review", "Under Review"),
            ("approved", "Approved & Protected"),
            ("rejected", "Rejected"),
            ("expired", "Protection Expired"),
            ("converted", "Converted to Opportunity"),
            ("conflicted", "Channel Conflicted"),
        ),
        "exclusivity_status": (
            ("pending", "Pending Approval"),
            ("exclusive", "Full Exclusivity"),
            ("non_exclusive", "Non-Exclusive"),
            ("expired", "Expired"),
            ("revoked", "Revoked"),
        ),
    },
    "JointAccountPlan": {
        "status": (
            ("draft", "Drafting"),
            ("active", "Active & Executing"),
            ("achieved", "Targets Achieved"),
            ("underperforming", "Underperforming"),
            ("closed", "Closed"),
        ),
        "co_sell_motion": (
            ("partner_led", "Partner Led Co-Sell"),
            ("vendor_led", "Vendor Led Co-Sell"),
            ("joint_pursuit", "Equal Joint Pursuit"),
            ("services_only", "Partner Services Only"),
        ),
    },
    "ChannelConflict": {
        "conflict_type": (
            ("direct_vs_indirect", "Direct Sales vs. Partner Conflict"),
            ("partner_vs_partner", "Partner vs. Partner Collision"),
            ("territory_overlap", "Territory Boundary Dispute"),
            ("named_account_infringement", "Named Enterprise Account Infringement"),
        ),
        "severity": (
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
            ("critical", "Critical (Escalated to CRO)"),
        ),
        "status": (
            ("open", "Open / Investigating"),
            ("in_mediation", "In Active Mediation"),
            ("resolved", "Resolved & Adjudicated"),
            ("dismissed", "Dismissed / Ineligible"),
            ("escalated", "Escalated to Executive"),
        ),
        "escalation_level": (
            ("l1_cam", "Level 1: Channel Account Manager (CAM)"),
            ("l2_channel_chief", "Level 2: Channel Chief / VP Channels"),
            ("l3_executive_cro", "Level 3: Executive Adjudication (CRO)"),
        ),
        "resolution_outcome": (
            ("pending", "Pending Determination"),
            ("partner_favored", "Partner Exclusivity Upheld"),
            ("direct_favored", "Direct Sales Precedence Upheld"),
            ("split_commission", "Commission / Revenue Split Imposed"),
            ("co_sell_mandate", "Mandated Joint Co-Sell Agreement"),
            ("deal_cancelled", "Deal Cancelled / Disqualified"),
        ),
    },
}

PARTNERCHANNEL_URL_PATTERNS = {
    "partner_profile_list": "partner-channel/partners/",
    "partner_profile_create": "partner-channel/partners/new/",
    "partner_profile_detail": "partner-channel/partners/<int:pk>/",
    "partner_profile_edit": "partner-channel/partners/<int:pk>/edit/",
    "partner_profile_delete": "partner-channel/partners/<int:pk>/delete/",
    "deal_registration_list": "partner-channel/deal-registrations/",
    "deal_registration_create": "partner-channel/deal-registrations/new/",
    "deal_registration_detail": "partner-channel/deal-registrations/<int:pk>/",
    "deal_registration_edit": "partner-channel/deal-registrations/<int:pk>/edit/",
    "deal_registration_delete": "partner-channel/deal-registrations/<int:pk>/delete/",
    "deal_registration_approve": "partner-channel/deal-registrations/<int:pk>/approve/",
    "deal_registration_reject": "partner-channel/deal-registrations/<int:pk>/reject/",
    "deal_registration_convert": "partner-channel/deal-registrations/<int:pk>/convert/",
    "joint_account_plan_list": "partner-channel/joint-plans/",
    "joint_account_plan_create": "partner-channel/joint-plans/new/",
    "joint_account_plan_detail": "partner-channel/joint-plans/<int:pk>/",
    "joint_account_plan_edit": "partner-channel/joint-plans/<int:pk>/edit/",
    "joint_account_plan_delete": "partner-channel/joint-plans/<int:pk>/delete/",
    "channel_conflict_list": "partner-channel/conflicts/",
    "channel_conflict_create": "partner-channel/conflicts/new/",
    "channel_conflict_detail": "partner-channel/conflicts/<int:pk>/",
    "channel_conflict_edit": "partner-channel/conflicts/<int:pk>/edit/",
    "channel_conflict_delete": "partner-channel/conflicts/<int:pk>/delete/",
    "channel_conflict_escalate": "partner-channel/conflicts/<int:pk>/escalate/",
    "channel_conflict_resolve": "partner-channel/conflicts/<int:pk>/resolve/",
    "partner_performance_console": "partner-channel/console/",
}


def _partnerchannel_currency(code="USD", symbol="$", name="US Dollar"):
    from apps.accounting.models import Currency
    currency, _ = Currency.objects.get_or_create(
        code=code,
        defaults={"name": name, "symbol": symbol, "is_active": True},
    )
    return currency


def _partnerchannel_party(tenant, name="Partner Acme", role="partner"):
    from apps.core.models import Party, PartyRole
    party = Party.objects.create(tenant=tenant, name=name, kind="organization")
    PartyRole.objects.create(tenant=tenant, party=party, role=role)
    return party


def _partnerchannel_partner_profile(tenant, partner, currency, **overrides):
    from apps.sales.models import PartnerProfile
    from django.utils import timezone
    defaults = {
        "tenant": tenant,
        "partner": partner,
        "partner_type": "reseller",
        "onboarding_status": "active",
        "tier": "gold",
        "tier_effective_date": timezone.localdate(),
        "application_date": timezone.localdate(),
        "agreement_signed_at": timezone.now(),
        "annual_revenue_target": Decimal("500000.00"),
        "actual_revenue_ytd": Decimal("250000.00"),
        "currency": currency,
        "base_discount_pct": Decimal("10.00"),
        "deal_reg_margin_pct": Decimal("15.00"),
        "portal_access_enabled": True,
        "active_certifications_count": 4,
    }
    defaults.update(overrides)
    return PartnerProfile.objects.create(**defaults)


def _partnerchannel_deal_registration(tenant, partner, customer_account, currency, **overrides):
    from apps.sales.models import DealRegistration
    from datetime import timedelta
    from django.utils import timezone
    now = timezone.localdate()
    defaults = {
        "tenant": tenant,
        "partner": partner,
        "customer_account": customer_account,
        "deal_name": "Enterprise Cloud Migration",
        "estimated_value": Decimal("120000.00"),
        "currency": currency,
        "expected_close_date": now + timedelta(days=60),
        "submission_date": now,
        "status": "approved",
        "exclusivity_status": "exclusive",
        "protection_start_date": now,
        "protection_end_date": now + timedelta(days=90),
        "protected_margin_pct": Decimal("20.00"),
    }
    defaults.update(overrides)
    return DealRegistration.objects.create(**defaults)


def _partnerchannel_joint_account_plan(tenant, partner, client_account, currency, **overrides):
    from apps.sales.models import JointAccountPlan
    from datetime import timedelta
    from django.utils import timezone
    now = timezone.localdate()
    defaults = {
        "tenant": tenant,
        "partner": partner,
        "client_account": client_account,
        "plan_name": "2026 Enterprise Co-Sell Strategy",
        "plan_year": 2026,
        "period_start": now,
        "period_end": now + timedelta(days=180),
        "status": "active",
        "target_revenue": Decimal("350000.00"),
        "actual_revenue": Decimal("75000.00"),
        "currency": currency,
        "partner_lead_name": "Jane Smith",
        "co_sell_motion": "joint_pursuit",
        "strategic_objectives": "Joint cloud modernization",
        "joint_value_proposition": "Turnkey ERP + managed services",
        "action_items": [{"task": "Q1 discovery workshop"}, {"task": "Q2 architecture review"}],
    }
    defaults.update(overrides)
    return JointAccountPlan.objects.create(**defaults)


def _partnerchannel_channel_conflict(tenant, claimant_partner, client_account, **overrides):
    from apps.sales.models import ChannelConflict
    defaults = {
        "tenant": tenant,
        "conflict_type": "direct_vs_indirect",
        "severity": "medium",
        "status": "open",
        "claimant_partner": claimant_partner,
        "client_account": client_account,
        "escalation_level": "l1_cam",
        "split_percentage": Decimal("0.00"),
        "description": "Direct rep engaged account already registered by partner",
    }
    defaults.update(overrides)
    return ChannelConflict.objects.create(**defaults)


@pytest.fixture
def pc_currency():
    return _partnerchannel_currency()


@pytest.fixture
def pc_partner_a(tenant_a):
    return _partnerchannel_party(tenant_a, name="Acme Premier Partner", role="partner")


@pytest.fixture
def pc_partner_b(tenant_b):
    return _partnerchannel_party(tenant_b, name="Globex Channel Partner", role="partner")


@pytest.fixture
def pc_customer_a(tenant_a):
    return _partnerchannel_party(tenant_a, name="Acme Enterprise Client", role="customer")


@pytest.fixture
def pc_customer_b(tenant_b):
    return _partnerchannel_party(tenant_b, name="Globex Enterprise Client", role="customer")


@pytest.fixture
def pc_profile_a(tenant_a, pc_partner_a, pc_currency, admin_user):
    return _partnerchannel_partner_profile(tenant_a, pc_partner_a, pc_currency, channel_manager=admin_user)


@pytest.fixture
def pc_profile_b(tenant_b, pc_partner_b, pc_currency, admin_b):
    return _partnerchannel_partner_profile(tenant_b, pc_partner_b, pc_currency, channel_manager=admin_b)


@pytest.fixture
def pc_deal_reg_a(tenant_a, pc_partner_a, pc_customer_a, pc_currency):
    return _partnerchannel_deal_registration(tenant_a, pc_partner_a, pc_customer_a, pc_currency)


@pytest.fixture
def pc_deal_reg_b(tenant_b, pc_partner_b, pc_customer_b, pc_currency):
    return _partnerchannel_deal_registration(tenant_b, pc_partner_b, pc_customer_b, pc_currency)


@pytest.fixture
def pc_joint_plan_a(tenant_a, pc_partner_a, pc_customer_a, pc_currency, admin_user):
    return _partnerchannel_joint_account_plan(
        tenant_a, pc_partner_a, pc_customer_a, pc_currency, vendor_lead=admin_user
    )


@pytest.fixture
def pc_joint_plan_b(tenant_b, pc_partner_b, pc_customer_b, pc_currency, admin_b):
    return _partnerchannel_joint_account_plan(
        tenant_b, pc_partner_b, pc_customer_b, pc_currency, vendor_lead=admin_b
    )


@pytest.fixture
def pc_conflict_a(tenant_a, pc_partner_a, pc_customer_a, pc_deal_reg_a):
    return _partnerchannel_channel_conflict(
        tenant_a, pc_partner_a, pc_customer_a, deal_registration=pc_deal_reg_a
    )


@pytest.fixture
def pc_conflict_b(tenant_b, pc_partner_b, pc_customer_b, pc_deal_reg_b):
    return _partnerchannel_channel_conflict(
        tenant_b, pc_partner_b, pc_customer_b, deal_registration=pc_deal_reg_b
    )





