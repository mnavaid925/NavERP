"""Core app test fixtures."""
import pytest
from django.test import Client


@pytest.fixture
def party_a(db, tenant_a):
    from apps.core.models import Party
    return Party.objects.create(tenant=tenant_a, name="Acme Party", kind="organization")


@pytest.fixture
def party_b(db, tenant_b):
    from apps.core.models import Party
    return Party.objects.create(tenant=tenant_b, name="Globex Party", kind="organization")


# ------------------------------------------------------------------ 0.15 Localization
# APPEND-ONLY (L43): the two fixtures above are never rewritten; everything below is added.

@pytest.fixture
def localization_languages(db):
    """3 GLOBAL languages — two of them RTL.

    Global, so there is no `tenant` argument and no tenant scoping. Count assertions on this table must be
    scoped by `code`/`name` rather than by `.count()`, because the table is shared with anything else that
    creates a language.
    """
    from apps.core.models import Language
    return [
        Language.objects.create(code="en", name="English", native_name="English", is_default=True),
        Language.objects.create(code="ar", name="Arabic", native_name="العربية", is_rtl=True),
        Language.objects.create(code="he", name="Hebrew", native_name="עברית", is_rtl=True),
    ]


@pytest.fixture
def localization_zones(db):
    """3 GLOBAL zones covering both DST postures and a non-hour offset."""
    from apps.core.models import TimeZone
    return [
        TimeZone.objects.create(name="UTC", label="UTC", utc_offset_minutes=0),
        TimeZone.objects.create(name="Asia/Kolkata", label="Kolkata (IST)",
                                utc_offset_minutes=330),
        TimeZone.objects.create(name="Europe/London", label="London (GMT/BST)",
                                utc_offset_minutes=0, observes_dst=True),
    ]


@pytest.fixture
def localization_profile(db, tenant_a, localization_languages, localization_zones):
    """The tenant_a singleton profile."""
    from apps.core.models import LocaleProfile
    return LocaleProfile.objects.create(
        tenant=tenant_a,
        language=localization_languages[0],
        time_zone=localization_zones[0],
        first_day_of_week=1,
    )


@pytest.fixture
def localization_rules(db, tenant_a, tenant_b):
    """2 rules for tenant_a, 1 for tenant_b — the isolation test needs a real foreign row."""
    import datetime

    from apps.core.models import StatutoryRule
    today = datetime.date(2026, 1, 1)
    return {
        "a": [
            StatutoryRule.objects.create(
                tenant=tenant_a, name="EU VAT e-invoicing", jurisdiction="European Union",
                e_invoicing_required=True, e_invoicing_scheme="peppol",
                statutory_report="EC Sales List", effective_from=today),
            StatutoryRule.objects.create(
                tenant=tenant_a, name="US sales tax filing", jurisdiction="United States",
                effective_from=today),
        ],
        "b": StatutoryRule.objects.create(
            tenant=tenant_b, name="Globex Filing", jurisdiction="Globex Land",
            effective_from=today),
    }


@pytest.fixture
def localization_statutory_payload():
    """Valid POST fields for a StatutoryRule — a helper, not a DB fixture."""
    return {
        "name": "New Compliance Rule",
        "jurisdiction": "Test Jurisdiction",
        "tax_code": "",
        "e_invoicing_scheme": "none",
        "statutory_report": "",
        "effective_from": "2026-01-01",
        "effective_to": "",
        "is_active": "on",
        "notes": "",
    }
