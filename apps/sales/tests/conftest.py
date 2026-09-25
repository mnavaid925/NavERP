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
