"""core — 0.8's privacy mechanisms: the PII data map and the statutory clock.

Kept out of the views so both are independently testable, and so the heuristics are readable in one
place. The honesty rules are the important part of this file:

* `scan_pii_fields()` is a HEURISTIC over the SCHEMA (model field names), not a scan of the DATA. It
  reads no row values and makes no claim about what is actually stored. Every row it produces is
  recorded as `suggested`, and a human must confirm it — a compliance report that presents a
  name-matching guess as a finding is worse than no report.
* `statutory_window_days()` takes the STRICTEST enabled framework. A workspace cannot be compliant
  with one regime by missing another's deadline.
"""
import re

from django.apps import apps as django_apps

from .models import RegulatoryFramework

#: Field-name patterns and what they suggest. Deliberately conservative and readable: the value of a
#: data map is that a human can audit the reasoning, so this is a table rather than a model.
#:
#: Each entry is (regex, category, sensitivity). Anchored loosely on purpose — `bank_account_number`
#: and `account_number` should both match `account`, while `accounting_period` should not.
PII_FIELD_PATTERNS = [
    (r"(^|_)e?mail($|_)", "identifier", "medium"),
    (r"(^|_)(phone|mobile|fax|msisdn)($|_)", "identifier", "medium"),
    (r"(^|_)(first_name|last_name|full_name|surname|given_name)($|_)", "identifier", "medium"),
    (r"(^|_)(national_id|ssn|social_security|passport|tax_id|nino|aadhaar)($|_)", "identifier", "high"),
    (r"(^|_)(dob|date_of_birth|birth_date)($|_)", "identifier", "high"),
    (r"(^|_)(postal|postcode|zip|street|city|country)($|_)", "location", "medium"),
    (r"(^|_)(current_address|permanent_address|home_address|delivery_address|billing_address)($|_)",
     "location", "medium"),
    (r"(^|_)(latitude|longitude|geo|gps)($|_)", "location", "high"),
    (r"(^|_)(last_known_location|last_seen_location|home_location|work_location)($|_)",
     "location", "medium"),
    (r"(^|_)(bank|iban|swift|account_number|routing|sort_code|card|pan|cvv)($|_)", "financial", "high"),
    (r"(^|_)(salary|wage|payroll|compensation|bonus)($|_)", "financial", "high"),
    (r"(^|_)(diagnosis|medical|health|condition|medication|allergy|disability)($|_)", "health", "high"),
    (r"(^|_)(biometric|fingerprint|face_id|iris|retina|voiceprint)($|_)", "biometric", "high"),
    (r"(^|_)(ip_address|device_id|session_key|cookie|user_agent)($|_)", "online", "medium"),
    (r"(^|_)(race|ethnicity|religion|political|sexual_orientation|trade_union)($|_)", "special", "high"),
    (r"(^|_)(password|secret|token|api_key|private_key)($|_)", "online", "high"),
]

#: Field names that are almost always false positives. Kept as an explicit deny-list rather than
#: hoping the patterns miss them, because a data map full of noise gets ignored — which is the real
#: failure mode of every PII scanner ever shipped.
#:
#: `is_*` flags are excluded wholesale: a boolean like `is_metro_city` describes a record, it does not
#: hold a location, and matching it on the `city` pattern added pure noise.
PII_FALSE_POSITIVE_HINTS = (
    "created_at", "updated_at", "deleted_at", "occurred_at", "performed_at", "received_at",
    "due_at", "reviewed_at", "expires_at", "started_at", "completed_at", "last_login",
)

#: Suffix/prefix shapes that are structurally not personal data. A bare `location` on a warehouse
#: model is a BIN, not a person's whereabouts: a first pass matched 46 of them (`qc_location`,
#: `dock_location`, `quarantine_location`, `from_location`, …) and drowned the real hits. Matching is
#: name-based and cannot tell a bin from a home, so the safe move is to not claim the ambiguous ones
#: — the human confirmation step is what promotes a real one.
PII_STRUCTURAL_HINTS = (
    "location_type", "location_or_link", "location_text", "location_id",
)

#: App labels whose fields are infrastructure rather than personal data.
PII_SKIP_APPS = ("contenttypes", "auth", "admin", "sessions", "django_celery_beat")


def scan_pii_fields():
    """Yield (model_label, field_name, category, sensitivity) for fields whose NAME suggests PII.

    Schema only — no row values are read. Callers must record these as `suggested`.

    Iterates `concrete_fields`, NOT `get_fields()`. The latter also returns REVERSE relations and
    M2M accessors, which are named after the related model's `related_name` — so a first pass
    produced 284 "candidates" that were mostly `core.Tenant.health_metrics`,
    `core.OrgUnit.procurement_routing_rules` and similar accessors, none of which store anything. A
    data map full of noise gets ignored, which is the failure mode this scan exists to avoid. Only
    real columns can hold personal data.
    """
    seen = []
    for model in django_apps.get_models():
        app_label = model._meta.app_label
        if app_label in PII_SKIP_APPS:
            continue
        model_label = f"{app_label}.{model.__name__}"
        for field in model._meta.concrete_fields:
            name = getattr(field, "name", None)
            if not name or name in PII_FALSE_POSITIVE_HINTS or name in PII_STRUCTURAL_HINTS:
                continue
            # A boolean flag describes a record; it does not hold personal data.
            if name.startswith("is_") or name.startswith("has_"):
                continue
            for pattern, category, sensitivity in PII_FIELD_PATTERNS:
                if re.search(pattern, name, re.IGNORECASE):
                    seen.append((model_label, name, category, sensitivity))
                    break
    return seen


def statutory_window_days(tenant):
    """The STRICTEST enabled framework's DSAR window, or None when nothing is enabled.

    None is returned rather than a default of 30 on purpose: a deadline the workspace cannot point at
    a regime for is a fabricated obligation, and the DSAR then records no due date at all.
    """
    windows = list(RegulatoryFramework.objects
                   .filter(tenant=tenant, is_enabled=True)
                   .values_list("dsar_window_days", flat=True))
    if not windows:
        return None
    return min(windows)
