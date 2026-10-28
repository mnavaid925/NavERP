"""Sub-module 8.19 Master Data & Configuration — Security & Multi-Tenancy Test Suite.

Subslug: masterdataconfig
Prefix for test functions: test_masterdataconfig_*
Prefix for helper functions: _masterdataconfig_*

Covers:
1. Multi-Tenant Data Isolation & Cross-Tenant IDOR:
   - Client authenticated as Tenant A requesting Tenant B objects (Price Book Entries,
     Custom Entity Definitions, Methodologies, Regional Settings) across detail, edit,
     and delete views -> returns 404 Not Found.
   - Cross-tenant delete attempts via POST return 404 and do not delete foreign records.
   - Cross-tenant edit attempts via POST return 404 and do not modify foreign records.
   - Client authenticated as Tenant B requesting Tenant A objects -> returns 404 Not Found.
   - List views and central Overview Dashboard never leak Tenant B data or statistics into Tenant A's session.
2. Authentication & Authorization (AuthN & AuthZ):
   - All 21 routes reject unauthenticated access and redirect to login (302).
   - Administrative authorization: Non-admin tenant members (member_client) receive 403 Forbidden
     on all 12 mutating endpoints (4 create, 4 edit, 4 delete).
   - Non-admin tenant members can safely read all 9 read surfaces (overview, lists, details).
   - Tenant admin users have full access to create and update records.
3. HTTP Method Enforcement:
   - Destructive endpoints (@require_POST) reject GET requests with 405 Method Not Allowed
     without deleting the records.
4. Foreign Key Injection & Cross-Tenant Association Attacks:
   - Submitting create or edit forms with foreign keys (price_book, product, item, pipeline, gating_stage)
     belonging to another tenant is strictly rejected with a clean validation error.
   - Model clean() enforcement raises ValidationError on cross-tenant or mismatched associations.
5. Mass Assignment & Privilege Escalation:
   - Forged POST bodies containing system fields (tenant, tenant_id, number, created_at)
     are ignored on creation and cannot overwrite database values on edit.
6. Adversarial & Input Chaos:
   - Malformed regex patterns in custom entity definition validation rules are rejected with ValidationError.
   - Out-of-bounds numeric inputs (cooling_off_days > 365, min_passing_score > 100, negative prices, floor > list)
     are strictly rejected by form/model validators.
   - Extreme string lengths (10,000+ chars) in CharFields are rejected by max_length validation.
   - Malformed JSON payloads in volume tier breaks and qualification criteria are rejected cleanly.
7. CSRF Protection:
   - Mutating POST requests without CSRF token return 403 Forbidden.
"""
from decimal import Decimal
import uuid
import pytest
from django.core.exceptions import ValidationError
from django.test import Client
from django.urls import reverse

from apps.crm.models import PriceBook, Product
from apps.sales.models import (
    Pipeline,
    PipelineStage,
    SalesCustomEntityDefinition,
    SalesMethodology,
    SalesPriceBookEntry,
    SalesRegionalSetting,
)
from apps.sales.tests.conftest import (
    _masterdataconfig_custom_entity,
    _masterdataconfig_methodology,
    _masterdataconfig_price_book,
    _masterdataconfig_price_book_entry,
    _masterdataconfig_product,
    _masterdataconfig_regional_setting,
)
from apps.scm.models import Item

pytestmark = pytest.mark.django_db


# ==============================================================================
# Helper Functions (_masterdataconfig_*)
# ==============================================================================

def _masterdataconfig_csrf_client(user):
    """Return a test client with strict CSRF check enforcement enabled."""
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)
    return client


def _masterdataconfig_all_routes(pbe, sco, smd, srg):
    """Return all 21 route names and URL argument tuples for 8.19 Master Data & Configuration."""
    return [
        # Overview (1)
        ("sales:master_data_overview", []),
        # SalesPriceBookEntry (5)
        ("sales:pbe_list", []),
        ("sales:pbe_create", []),
        ("sales:pbe_detail", [pbe.pk]),
        ("sales:pbe_edit", [pbe.pk]),
        ("sales:pbe_delete", [pbe.pk]),
        # SalesCustomEntityDefinition (5)
        ("sales:sco_list", []),
        ("sales:sco_create", []),
        ("sales:sco_detail", [sco.pk]),
        ("sales:sco_edit", [sco.pk]),
        ("sales:sco_delete", [sco.pk]),
        # SalesMethodology (5)
        ("sales:smd_list", []),
        ("sales:smd_create", []),
        ("sales:smd_detail", [smd.pk]),
        ("sales:smd_edit", [smd.pk]),
        ("sales:smd_delete", [smd.pk]),
        # SalesRegionalSetting (5)
        ("sales:srg_list", []),
        ("sales:srg_create", []),
        ("sales:srg_detail", [srg.pk]),
        ("sales:srg_edit", [srg.pk]),
        ("sales:srg_delete", [srg.pk]),
    ]


def _masterdataconfig_mutating_endpoints(pbe, sco, smd, srg):
    """Return all 12 create, edit, and delete mutation endpoints that require tenant admin privilege."""
    return [
        # 4 Create endpoints
        ("get", reverse("sales:pbe_create")),
        ("post", reverse("sales:pbe_create")),
        ("get", reverse("sales:sco_create")),
        ("post", reverse("sales:sco_create")),
        ("get", reverse("sales:smd_create")),
        ("post", reverse("sales:smd_create")),
        ("get", reverse("sales:srg_create")),
        ("post", reverse("sales:srg_create")),
        # 4 Edit endpoints
        ("get", reverse("sales:pbe_edit", args=[pbe.pk])),
        ("post", reverse("sales:pbe_edit", args=[pbe.pk])),
        ("get", reverse("sales:sco_edit", args=[sco.pk])),
        ("post", reverse("sales:sco_edit", args=[sco.pk])),
        ("get", reverse("sales:smd_edit", args=[smd.pk])),
        ("post", reverse("sales:smd_edit", args=[smd.pk])),
        ("get", reverse("sales:srg_edit", args=[srg.pk])),
        ("post", reverse("sales:srg_edit", args=[srg.pk])),
        # 4 Delete endpoints
        ("post", reverse("sales:pbe_delete", args=[pbe.pk])),
        ("post", reverse("sales:sco_delete", args=[sco.pk])),
        ("post", reverse("sales:smd_delete", args=[smd.pk])),
        ("post", reverse("sales:srg_delete", args=[srg.pk])),
    ]


def _masterdataconfig_item(tenant, sku=None, name="Hardware Appliance", **overrides):
    """Helper to create a test SCM inventory item for price book entry linking."""
    if sku is None:
        sku = f"ITM-{uuid.uuid4().hex[:8]}"
    defaults = {
        "tenant": tenant,
        "sku": sku,
        "name": name,
        "item_type": "stock",
        "tracking": "none",
        "costing_method": "weighted_avg",
    }
    defaults.update(overrides)
    return Item.objects.create(**defaults)


def _masterdataconfig_pipeline(tenant, name="Sales Pipeline", **overrides):
    """Helper to create a test pipeline for methodology tests."""
    defaults = {
        "tenant": tenant,
        "name": name,
        "is_active": True,
        "is_default": False,
    }
    defaults.update(overrides)
    return Pipeline.objects.create(**defaults)


def _masterdataconfig_stage(tenant, pipeline, name="Technical Gate Stage", code=None, **overrides):
    """Helper to create a test pipeline stage for methodology tests."""
    if code is None:
        code = f"stg_{uuid.uuid4().hex[:8]}"
    defaults = {
        "tenant": tenant,
        "pipeline": pipeline,
        "name": name,
        "code": code,
        "sequence": 10,
        "stage_kind": "open",
        "crm_stage_key": "qualification",
        "probability": 25,
        "forecast_category": "pipeline",
        "is_active": True,
    }
    defaults.update(overrides)
    return PipelineStage.objects.create(**defaults)


def _masterdataconfig_pbe_payload(price_book, product, item=None, **overrides):
    """Generate a valid payload dictionary for SalesPriceBookEntry form submission."""
    defaults = {
        "price_book": price_book.pk if hasattr(price_book, "pk") else price_book,
        "product": product.pk if hasattr(product, "pk") else product,
        "item": (item.pk if hasattr(item, "pk") else item) if item else "",
        "sku_code": "SKU-SEC-101",
        "currency_code": "USD",
        "list_price": "1200.00",
        "floor_price": "900.00",
        "pricing_model": "flat",
        "min_quantity": "1.00",
        "valid_from": "2026-01-01",
        "valid_to": "2026-12-31",
        "volume_tier_breaks_raw": '[{"min_qty": 10, "discount_pct": 5.0, "unit_price": 1140.0}]',
        "is_active": True,
        "notes": "Security test price book entry.",
    }
    defaults.update(overrides)
    return defaults


def _masterdataconfig_sco_payload(**overrides):
    """Generate a valid payload dictionary for SalesCustomEntityDefinition form submission."""
    defaults = {
        "name": "SecOps Audit Signoff",
        "entity_code": "secops_audit_signoff_c",
        "target_model": "opportunity",
        "field_type": "boolean",
        "is_required": False,
        "formula_expression": "",
        "lookup_target_model": "",
        "picklist_options_raw": "",
        "validation_rule": "",
        "display_order": 10,
        "is_active": True,
        "description": "Security compliance signoff field.",
    }
    defaults.update(overrides)
    return defaults


def _masterdataconfig_smd_payload(pipeline=None, gating_stage=None, **overrides):
    """Generate a valid payload dictionary for SalesMethodology form submission."""
    defaults = {
        "name": "MEDDPICC Compliance Gate",
        "framework": "meddpicc",
        "pipeline": (pipeline.pk if hasattr(pipeline, "pk") else pipeline) if pipeline else "",
        "gating_stage": (gating_stage.pk if hasattr(gating_stage, "pk") else gating_stage) if gating_stage else "",
        "min_passing_score": 75,
        "is_mandatory_gate": True,
        "qualification_criteria_raw": '[{"key": "metrics", "label": "Quantified Economic Impact", "weight": 20, "is_required": true}]',
        "coaching_guidelines": "Verify economic buyer signoff before stage advancement.",
        "is_active": True,
    }
    defaults.update(overrides)
    return defaults


def _masterdataconfig_srg_payload(**overrides):
    """Generate a valid payload dictionary for SalesRegionalSetting form submission."""
    defaults = {
        "name": "DACH Regional Compliance",
        "region_code": "DACH",
        "primary_currency": "EUR",
        "supported_currencies_raw": "EUR, CHF",
        "date_format": "DD.MM.YYYY",
        "number_format": "1.234,56",
        "tax_display_mode": "tax_inclusive",
        "default_quote_terms": "Zahlbar innerhalb von 30 Tagen netto.",
        "statutory_disclaimer": "Allgemeine Geschaeftsbedingungen der Region DACH.",
        "compliance_framework": "gdpr_commercial",
        "cooling_off_days": 14,
        "is_default": False,
        "is_active": True,
    }
    defaults.update(overrides)
    return defaults


# ==============================================================================
# 1. Multi-Tenant Data Isolation & Cross-Tenant IDOR
# ==============================================================================

def test_masterdataconfig_cross_tenant_idor_detail_views_return_404(
    client_a,
    mdc_price_book_entry_b,
    mdc_custom_entity_b,
    mdc_methodology_b,
    mdc_regional_setting_b,
):
    """Client authenticated as Tenant A requesting Tenant B detail views returns 404 Not Found."""
    targets = [
        ("sales:pbe_detail", [mdc_price_book_entry_b.pk]),
        ("sales:sco_detail", [mdc_custom_entity_b.pk]),
        ("sales:smd_detail", [mdc_methodology_b.pk]),
        ("sales:srg_detail", [mdc_regional_setting_b.pk]),
    ]
    for route_name, args in targets:
        url = reverse(route_name, args=args)
        resp = client_a.get(url)
        assert resp.status_code == 404, f"IDOR vulnerability: {route_name} for Tenant B object did not return 404!"


def test_masterdataconfig_cross_tenant_idor_edit_views_return_404(
    client_a,
    mdc_price_book_entry_b,
    mdc_custom_entity_b,
    mdc_methodology_b,
    mdc_regional_setting_b,
):
    """Client authenticated as Tenant A attempting to GET or POST edit Tenant B objects returns 404 without modifying records."""
    orig_pbe_notes = mdc_price_book_entry_b.notes
    orig_sco_name = mdc_custom_entity_b.name
    orig_smd_name = mdc_methodology_b.name
    orig_srg_name = mdc_regional_setting_b.name

    targets = [
        ("sales:pbe_edit", [mdc_price_book_entry_b.pk], {"notes": "Hacked Notes"}),
        ("sales:sco_edit", [mdc_custom_entity_b.pk], {"name": "Hacked Entity"}),
        ("sales:smd_edit", [mdc_methodology_b.pk], {"name": "Hacked Methodology"}),
        ("sales:srg_edit", [mdc_regional_setting_b.pk], {"name": "Hacked Regional"}),
    ]
    for route_name, args, post_data in targets:
        url = reverse(route_name, args=args)
        get_resp = client_a.get(url)
        assert get_resp.status_code == 404, f"GET {route_name} for foreign object expected 404, got {get_resp.status_code}"

        post_resp = client_a.post(url, data=post_data)
        assert post_resp.status_code == 404, f"POST {route_name} for foreign object expected 404, got {post_resp.status_code}"

    # Verify no records were modified in DB
    mdc_price_book_entry_b.refresh_from_db()
    assert mdc_price_book_entry_b.notes == orig_pbe_notes

    mdc_custom_entity_b.refresh_from_db()
    assert mdc_custom_entity_b.name == orig_sco_name

    mdc_methodology_b.refresh_from_db()
    assert mdc_methodology_b.name == orig_smd_name

    mdc_regional_setting_b.refresh_from_db()
    assert mdc_regional_setting_b.name == orig_srg_name


def test_masterdataconfig_cross_tenant_idor_delete_views_return_404(
    client_a,
    mdc_price_book_entry_b,
    mdc_custom_entity_b,
    mdc_methodology_b,
    mdc_regional_setting_b,
):
    """Client authenticated as Tenant A attempting to POST delete foreign objects returns 404 and does not delete records."""
    targets = [
        ("sales:pbe_delete", [mdc_price_book_entry_b.pk], SalesPriceBookEntry, mdc_price_book_entry_b.pk),
        ("sales:sco_delete", [mdc_custom_entity_b.pk], SalesCustomEntityDefinition, mdc_custom_entity_b.pk),
        ("sales:smd_delete", [mdc_methodology_b.pk], SalesMethodology, mdc_methodology_b.pk),
        ("sales:srg_delete", [mdc_regional_setting_b.pk], SalesRegionalSetting, mdc_regional_setting_b.pk),
    ]
    for route_name, args, model_cls, pk in targets:
        url = reverse(route_name, args=args)
        resp = client_a.post(url)
        assert resp.status_code == 404, f"POST {route_name} for foreign object expected 404, got {resp.status_code}"
        assert model_cls.objects.filter(pk=pk).exists(), f"{model_cls.__name__} {pk} should not have been deleted!"


def test_masterdataconfig_cross_tenant_idor_reverse_tenant_b_cannot_access_tenant_a(
    client_b,
    mdc_price_book_entry_a,
    mdc_custom_entity_a,
    mdc_methodology_a,
    mdc_regional_setting_a,
):
    """Client authenticated as Tenant B accessing Tenant A objects returns 404 on all detail, edit, and delete routes."""
    targets = [
        ("sales:pbe_detail", [mdc_price_book_entry_a.pk], "get"),
        ("sales:pbe_edit", [mdc_price_book_entry_a.pk], "get"),
        ("sales:pbe_delete", [mdc_price_book_entry_a.pk], "post"),
        ("sales:sco_detail", [mdc_custom_entity_a.pk], "get"),
        ("sales:sco_edit", [mdc_custom_entity_a.pk], "get"),
        ("sales:sco_delete", [mdc_custom_entity_a.pk], "post"),
        ("sales:smd_detail", [mdc_methodology_a.pk], "get"),
        ("sales:smd_edit", [mdc_methodology_a.pk], "get"),
        ("sales:smd_delete", [mdc_methodology_a.pk], "post"),
        ("sales:srg_detail", [mdc_regional_setting_a.pk], "get"),
        ("sales:srg_edit", [mdc_regional_setting_a.pk], "get"),
        ("sales:srg_delete", [mdc_regional_setting_a.pk], "post"),
    ]
    for route_name, args, method in targets:
        url = reverse(route_name, args=args)
        client_fn = getattr(client_b, method)
        resp = client_fn(url)
        assert resp.status_code == 404, f"{route_name} by Tenant B for Tenant A object expected 404, got {resp.status_code}"


def test_masterdataconfig_cross_tenant_list_views_never_leak_foreign_data(
    client_a,
    mdc_price_book_entry_a,
    mdc_price_book_entry_b,
    mdc_custom_entity_a,
    mdc_custom_entity_b,
    mdc_methodology_a,
    mdc_methodology_b,
    mdc_regional_setting_a,
    mdc_regional_setting_b,
):
    """List views strictly scope records to the active tenant and never leak foreign tenant objects or text into responses."""
    # Ensure distinct distinguishing values on tenant B objects
    mdc_price_book_entry_b.sku_code = "SKU-ISOLATED-FOREIGN-B"
    mdc_price_book_entry_b.save(update_fields=["sku_code"])

    mdc_custom_entity_b.name = "Isolated Foreign Entity Beta"
    mdc_custom_entity_b.save(update_fields=["name"])

    mdc_methodology_b.name = "Isolated Foreign Methodology Beta"
    mdc_methodology_b.save(update_fields=["name"])

    mdc_regional_setting_b.name = "Isolated Foreign Regional Beta"
    mdc_regional_setting_b.save(update_fields=["name"])

    # 1. Price Book Entries list
    resp_pbe = client_a.get(reverse("sales:pbe_list"))
    assert resp_pbe.status_code == 200
    pbe_entries = list(resp_pbe.context["entries"])
    assert mdc_price_book_entry_a in pbe_entries
    assert mdc_price_book_entry_b not in pbe_entries
    assert "SKU-ISOLATED-FOREIGN-B" not in resp_pbe.content.decode("utf-8")

    # 2. Custom Entity Definitions list
    resp_sco = client_a.get(reverse("sales:sco_list"))
    assert resp_sco.status_code == 200
    sco_definitions = list(resp_sco.context["definitions"])
    assert mdc_custom_entity_a in sco_definitions
    assert mdc_custom_entity_b not in sco_definitions
    assert "Isolated Foreign Entity Beta" not in resp_sco.content.decode("utf-8")

    # 3. Methodologies list
    resp_smd = client_a.get(reverse("sales:smd_list"))
    assert resp_smd.status_code == 200
    smd_methodologies = list(resp_smd.context["methodologies"])
    assert mdc_methodology_a in smd_methodologies
    assert mdc_methodology_b not in smd_methodologies
    assert "Isolated Foreign Methodology Beta" not in resp_smd.content.decode("utf-8")

    # 4. Regional Settings list
    resp_srg = client_a.get(reverse("sales:srg_list"))
    assert resp_srg.status_code == 200
    srg_settings = list(resp_srg.context["settings"])
    assert mdc_regional_setting_a in srg_settings
    assert mdc_regional_setting_b not in srg_settings
    assert "Isolated Foreign Regional Beta" not in resp_srg.content.decode("utf-8")


def test_masterdataconfig_cross_tenant_overview_dashboard_never_leaks_foreign_data(
    client_a,
    tenant_a,
    mdc_price_book_entry_a,
    mdc_price_book_entry_b,
    mdc_custom_entity_a,
    mdc_custom_entity_b,
    mdc_methodology_a,
    mdc_methodology_b,
    mdc_regional_setting_a,
    mdc_regional_setting_b,
):
    """Central Overview Dashboard calculates KPIs and recent item previews strictly within the active tenant."""
    mdc_price_book_entry_b.sku_code = "SKU-LEAK-PROBE-B"
    mdc_price_book_entry_b.save(update_fields=["sku_code"])

    mdc_custom_entity_b.name = "Secret Dashboard Leak Entity B"
    mdc_custom_entity_b.save(update_fields=["name"])

    resp = client_a.get(reverse("sales:master_data_overview"))
    assert resp.status_code == 200
    ctx = resp.context

    # Assert KPI counts strictly match Tenant A records
    kpis = ctx["kpis"]
    assert kpis["total_price_book_entries"] == SalesPriceBookEntry.objects.filter(tenant=tenant_a).count()
    assert kpis["total_custom_definitions"] == SalesCustomEntityDefinition.objects.filter(tenant=tenant_a).count()
    assert kpis["total_methodologies"] == SalesMethodology.objects.filter(tenant=tenant_a).count()
    assert kpis["total_regional_settings"] == SalesRegionalSetting.objects.filter(tenant=tenant_a).count()

    # Assert recent items lists strictly exclude Tenant B objects
    assert mdc_price_book_entry_b not in ctx["recent_price_book_entries"]
    assert mdc_custom_entity_b not in ctx["recent_custom_entities"]
    assert mdc_methodology_b not in ctx["recent_methodologies"]
    assert mdc_regional_setting_b not in ctx["recent_regional_settings"]

    body = resp.content.decode("utf-8")
    assert "SKU-LEAK-PROBE-B" not in body
    assert "Secret Dashboard Leak Entity B" not in body


# ==============================================================================
# 2. Authentication & Authorization (AuthN & AuthZ)
# ==============================================================================

def test_masterdataconfig_unauthenticated_access_redirects_all_routes_to_login(
    client,
    mdc_price_book_entry_a,
    mdc_custom_entity_a,
    mdc_methodology_a,
    mdc_regional_setting_a,
):
    """Anonymous visitors accessing any of the 21 Master Data & Configuration routes redirect to login (302)."""
    routes = _masterdataconfig_all_routes(
        mdc_price_book_entry_a,
        mdc_custom_entity_a,
        mdc_methodology_a,
        mdc_regional_setting_a,
    )
    assert len(routes) == 21

    for route_name, args in routes:
        url = reverse(route_name, args=args)
        resp = client.get(url)
        assert resp.status_code == 302, f"Expected 302 login redirect for {route_name}, got {resp.status_code}"
        assert "/login/" in resp.url, f"Expected /login/ in redirect URL for {route_name}, got {resp.url}"


def test_masterdataconfig_tenant_admin_required_blocks_non_admin_member_on_all_12_mutations(
    member_client,
    mdc_price_book_entry_a,
    mdc_custom_entity_a,
    mdc_methodology_a,
    mdc_regional_setting_a,
):
    """Non-admin tenant members receive 403 PermissionDenied on all 12 mutating endpoints (create, edit, delete)."""
    mutations = _masterdataconfig_mutating_endpoints(
        mdc_price_book_entry_a,
        mdc_custom_entity_a,
        mdc_methodology_a,
        mdc_regional_setting_a,
    )
    assert len(mutations) == 20  # 4 create (get+post) + 4 edit (get+post) + 4 delete (post)

    for method, url in mutations:
        client_fn = getattr(member_client, method)
        resp = client_fn(url)
        assert resp.status_code == 403, (
            f"{method.upper()} {url} by non-admin member expected 403 PermissionDenied, got {resp.status_code}"
        )


def test_masterdataconfig_non_admin_member_can_safely_read_surfaces(
    member_client,
    mdc_price_book_entry_a,
    mdc_custom_entity_a,
    mdc_methodology_a,
    mdc_regional_setting_a,
):
    """Non-admin tenant members can safely access all 9 read surfaces (overview, lists, details)."""
    read_surfaces = [
        ("sales:master_data_overview", []),
        ("sales:pbe_list", []),
        ("sales:pbe_detail", [mdc_price_book_entry_a.pk]),
        ("sales:sco_list", []),
        ("sales:sco_detail", [mdc_custom_entity_a.pk]),
        ("sales:smd_list", []),
        ("sales:smd_detail", [mdc_methodology_a.pk]),
        ("sales:srg_list", []),
        ("sales:srg_detail", [mdc_regional_setting_a.pk]),
    ]
    for route_name, args in read_surfaces:
        url = reverse(route_name, args=args)
        resp = member_client.get(url)
        assert resp.status_code == 200, f"Member GET {route_name} expected 200 OK, got {resp.status_code}"


def test_masterdataconfig_tenant_admin_user_has_full_mutation_access(
    client_a,
    tenant_a,
):
    """Tenant admin users have full access to create surfaces and can successfully submit mutations."""
    # Can access create GET
    create_urls = [
        reverse("sales:pbe_create"),
        reverse("sales:sco_create"),
        reverse("sales:smd_create"),
        reverse("sales:srg_create"),
    ]
    for url in create_urls:
        resp = client_a.get(url)
        assert resp.status_code == 200

    # Can create custom entity definition
    payload = _masterdataconfig_sco_payload(name="Admin Permitted Entity", entity_code="admin_entity_c")
    resp_post = client_a.post(reverse("sales:sco_create"), payload)
    assert resp_post.status_code == 302
    assert SalesCustomEntityDefinition.objects.filter(tenant=tenant_a, entity_code="admin_entity_c").exists()


# ==============================================================================
# 3. HTTP Method Enforcement
# ==============================================================================

def test_masterdataconfig_http_method_enforcement_delete_endpoints_reject_get(
    client_a,
    mdc_price_book_entry_a,
    mdc_custom_entity_a,
    mdc_methodology_a,
    mdc_regional_setting_a,
):
    """Destructive delete endpoints (@require_POST) reject GET with 405 Method Not Allowed without deleting records."""
    delete_targets = [
        ("sales:pbe_delete", [mdc_price_book_entry_a.pk], SalesPriceBookEntry, mdc_price_book_entry_a.pk),
        ("sales:sco_delete", [mdc_custom_entity_a.pk], SalesCustomEntityDefinition, mdc_custom_entity_a.pk),
        ("sales:smd_delete", [mdc_methodology_a.pk], SalesMethodology, mdc_methodology_a.pk),
        ("sales:srg_delete", [mdc_regional_setting_a.pk], SalesRegionalSetting, mdc_regional_setting_a.pk),
    ]
    for route_name, args, model_cls, pk in delete_targets:
        url = reverse(route_name, args=args)
        resp = client_a.get(url)
        assert resp.status_code == 405, (
            f"GET {route_name} expected 405 Method Not Allowed, got {resp.status_code}"
        )
        assert model_cls.objects.filter(pk=pk).exists(), f"{model_cls.__name__} {pk} was deleted on GET request!"


# ==============================================================================
# 4. Foreign Key Injection & Cross-Tenant Association Attacks
# ==============================================================================

def test_masterdataconfig_fk_injection_price_book_entry_foreign_price_book_rejected(
    client_a,
    tenant_a,
    tenant_b,
):
    """Submitting a create form with a PriceBook foreign key belonging to Tenant B is rejected with a form error."""
    pb_b = _masterdataconfig_price_book(tenant_b, name="Tenant B Price Book")
    prod_a = _masterdataconfig_product(tenant_a, name="Tenant A Product")

    payload = _masterdataconfig_pbe_payload(price_book=pb_b, product=prod_a)
    resp = client_a.post(reverse("sales:pbe_create"), payload)

    assert resp.status_code == 200
    form = resp.context["form"]
    assert not form.is_valid()
    assert "price_book" in form.errors
    assert not SalesPriceBookEntry.objects.filter(tenant=tenant_a, price_book=pb_b).exists()


def test_masterdataconfig_fk_injection_price_book_entry_foreign_product_rejected(
    client_a,
    tenant_a,
    tenant_b,
):
    """Submitting a create form with a Product foreign key belonging to Tenant B is rejected with a form error."""
    pb_a = _masterdataconfig_price_book(tenant_a, name="Tenant A Price Book")
    prod_b = _masterdataconfig_product(tenant_b, name="Tenant B Product")

    payload = _masterdataconfig_pbe_payload(price_book=pb_a, product=prod_b)
    resp = client_a.post(reverse("sales:pbe_create"), payload)

    assert resp.status_code == 200
    form = resp.context["form"]
    assert not form.is_valid()
    assert "product" in form.errors
    assert not SalesPriceBookEntry.objects.filter(tenant=tenant_a, product=prod_b).exists()


def test_masterdataconfig_fk_injection_price_book_entry_foreign_item_rejected(
    client_a,
    tenant_a,
    tenant_b,
):
    """Submitting a create form with an inventory Item foreign key belonging to Tenant B is rejected with a form error."""
    pb_a = _masterdataconfig_price_book(tenant_a, name="Tenant A Price Book Alpha")
    prod_a = _masterdataconfig_product(tenant_a, name="Tenant A Product Alpha")
    item_b = _masterdataconfig_item(tenant_b, name="Tenant B Hardware Item")

    payload = _masterdataconfig_pbe_payload(price_book=pb_a, product=prod_a, item=item_b)
    resp = client_a.post(reverse("sales:pbe_create"), payload)

    assert resp.status_code == 200
    form = resp.context["form"]
    assert not form.is_valid()
    assert "item" in form.errors
    assert not SalesPriceBookEntry.objects.filter(tenant=tenant_a, item=item_b).exists()


def test_masterdataconfig_fk_injection_price_book_entry_edit_foreign_fk_rejected(
    client_a,
    tenant_a,
    tenant_b,
    mdc_price_book_entry_a,
):
    """Submitting an edit form attempting to switch PriceBook to Tenant B is rejected with form error and does not mutate record."""
    pb_b = _masterdataconfig_price_book(tenant_b, name="Tenant B Price Book Attack")
    orig_price_book = mdc_price_book_entry_a.price_book

    payload = _masterdataconfig_pbe_payload(price_book=pb_b, product=mdc_price_book_entry_a.product)
    resp = client_a.post(reverse("sales:pbe_edit", args=[mdc_price_book_entry_a.pk]), payload)

    assert resp.status_code == 200
    form = resp.context["form"]
    assert not form.is_valid()
    assert "price_book" in form.errors

    mdc_price_book_entry_a.refresh_from_db()
    assert mdc_price_book_entry_a.price_book == orig_price_book


def test_masterdataconfig_fk_injection_methodology_foreign_pipeline_rejected(
    client_a,
    tenant_a,
    tenant_b,
):
    """Submitting methodology create form with Pipeline belonging to Tenant B is rejected with form error."""
    pipe_b = _masterdataconfig_pipeline(tenant_b, name="Foreign Tenant Pipeline B")

    payload = _masterdataconfig_smd_payload(pipeline=pipe_b)
    resp = client_a.post(reverse("sales:smd_create"), payload)

    assert resp.status_code == 200
    form = resp.context["form"]
    assert not form.is_valid()
    assert "pipeline" in form.errors
    assert not SalesMethodology.objects.filter(tenant=tenant_a, pipeline=pipe_b).exists()


def test_masterdataconfig_fk_injection_methodology_foreign_gating_stage_rejected(
    client_a,
    tenant_a,
    tenant_b,
):
    """Submitting methodology create form with PipelineStage belonging to Tenant B is rejected with form error."""
    pipe_a = _masterdataconfig_pipeline(tenant_a, name="Active Pipeline A")
    pipe_b = _masterdataconfig_pipeline(tenant_b, name="Foreign Pipeline B")
    stage_b = _masterdataconfig_stage(tenant_b, pipe_b, name="Foreign Stage B")

    payload = _masterdataconfig_smd_payload(pipeline=pipe_a, gating_stage=stage_b)
    resp = client_a.post(reverse("sales:smd_create"), payload)

    assert resp.status_code == 200
    form = resp.context["form"]
    assert not form.is_valid()
    assert "gating_stage" in form.errors
    assert not SalesMethodology.objects.filter(tenant=tenant_a, gating_stage=stage_b).exists()


def test_masterdataconfig_fk_injection_methodology_edit_foreign_fk_rejected(
    client_a,
    tenant_a,
    tenant_b,
    mdc_methodology_a,
):
    """Submitting an edit form attempting to assign foreign pipeline is rejected and does not mutate record."""
    pipe_b = _masterdataconfig_pipeline(tenant_b, name="Foreign Pipeline For Edit Attack")
    orig_pipeline = mdc_methodology_a.pipeline

    payload = _masterdataconfig_smd_payload(pipeline=pipe_b)
    resp = client_a.post(reverse("sales:smd_edit", args=[mdc_methodology_a.pk]), payload)

    assert resp.status_code == 200
    form = resp.context["form"]
    assert not form.is_valid()
    assert "pipeline" in form.errors

    mdc_methodology_a.refresh_from_db()
    assert mdc_methodology_a.pipeline == orig_pipeline


def test_masterdataconfig_model_clean_rejects_cross_tenant_price_book_entry_fk(
    tenant_a,
    tenant_b,
):
    """Direct model full_clean() on SalesPriceBookEntry raises ValidationError if price_book, product, or item belongs to foreign tenant."""
    pb_b = _masterdataconfig_price_book(tenant_b)
    prod_a = _masterdataconfig_product(tenant_a)
    prod_b = _masterdataconfig_product(tenant_b)
    item_b = _masterdataconfig_item(tenant_b)

    # 1. Foreign PriceBook
    entry_foreign_pb = SalesPriceBookEntry(
        tenant=tenant_a,
        price_book=pb_b,
        product=prod_a,
        list_price=Decimal("100.00"),
        floor_price=Decimal("80.00"),
        min_quantity=Decimal("1.00"),
    )
    with pytest.raises(ValidationError) as exc:
        entry_foreign_pb.full_clean()
    assert "price_book" in exc.value.message_dict

    # 2. Foreign Product
    pb_a = _masterdataconfig_price_book(tenant_a)
    entry_foreign_prod = SalesPriceBookEntry(
        tenant=tenant_a,
        price_book=pb_a,
        product=prod_b,
        list_price=Decimal("100.00"),
        floor_price=Decimal("80.00"),
        min_quantity=Decimal("1.00"),
    )
    with pytest.raises(ValidationError) as exc:
        entry_foreign_prod.full_clean()
    assert "product" in exc.value.message_dict

    # 3. Foreign Item
    entry_foreign_item = SalesPriceBookEntry(
        tenant=tenant_a,
        price_book=pb_a,
        product=prod_a,
        item=item_b,
        list_price=Decimal("100.00"),
        floor_price=Decimal("80.00"),
        min_quantity=Decimal("1.00"),
    )
    with pytest.raises(ValidationError) as exc:
        entry_foreign_item.full_clean()
    assert "item" in exc.value.message_dict


def test_masterdataconfig_model_clean_rejects_cross_tenant_methodology_fk(
    tenant_a,
    tenant_b,
):
    """Direct model full_clean() on SalesMethodology raises ValidationError if pipeline or gating_stage belongs to foreign tenant."""
    pipe_b = _masterdataconfig_pipeline(tenant_b)

    methodology = SalesMethodology(
        tenant=tenant_a,
        name="Cross Tenant Attack Methodology",
        framework="meddic",
        pipeline=pipe_b,
    )
    with pytest.raises(ValidationError) as exc:
        methodology.full_clean()
    assert "pipeline" in exc.value.message_dict


def test_masterdataconfig_model_clean_rejects_mismatched_pipeline_stage_fk(
    tenant_a,
):
    """Direct model full_clean() on SalesMethodology raises ValidationError if gating_stage belongs to a different pipeline."""
    pipe_1 = _masterdataconfig_pipeline(tenant_a, name="Pipeline 1")
    pipe_2 = _masterdataconfig_pipeline(tenant_a, name="Pipeline 2")
    stage_2 = _masterdataconfig_stage(tenant_a, pipe_2, name="Stage Belonging to Pipe 2")

    methodology = SalesMethodology(
        tenant=tenant_a,
        name="Mismatched Stage Methodology",
        framework="spin",
        pipeline=pipe_1,
        gating_stage=stage_2,
    )
    with pytest.raises(ValidationError) as exc:
        methodology.full_clean()
    assert "gating_stage" in exc.value.message_dict
    assert "must belong to the selected pipeline" in exc.value.message_dict["gating_stage"][0]


# ==============================================================================
# 5. Mass Assignment & Privilege Escalation
# ==============================================================================

def test_masterdataconfig_mass_assignment_tenant_forgery_ignored_on_create(
    client_a,
    tenant_a,
    tenant_b,
):
    """Forged POST bodies specifying tenant or tenant_id of another tenant are ignored on create."""
    pb_a = _masterdataconfig_price_book(tenant_a)
    prod_a = _masterdataconfig_product(tenant_a)

    # 1. SalesPriceBookEntry create
    pbe_data = _masterdataconfig_pbe_payload(pb_a, prod_a)
    pbe_data.update({"tenant": str(tenant_b.pk), "tenant_id": str(tenant_b.pk)})
    resp_pbe = client_a.post(reverse("sales:pbe_create"), pbe_data)
    assert resp_pbe.status_code == 302
    pbe = SalesPriceBookEntry.objects.filter(sku_code=pbe_data["sku_code"]).first()
    assert pbe is not None
    assert pbe.tenant == tenant_a
    assert not SalesPriceBookEntry.objects.filter(tenant=tenant_b, sku_code=pbe_data["sku_code"]).exists()

    # 2. SalesCustomEntityDefinition create
    sco_data = _masterdataconfig_sco_payload(name="Tenant Isolation Entity", entity_code="tnt_iso_c")
    sco_data.update({"tenant": str(tenant_b.pk), "tenant_id": str(tenant_b.pk)})
    resp_sco = client_a.post(reverse("sales:sco_create"), sco_data)
    assert resp_sco.status_code == 302
    sco = SalesCustomEntityDefinition.objects.filter(entity_code="tnt_iso_c").first()
    assert sco is not None
    assert sco.tenant == tenant_a
    assert not SalesCustomEntityDefinition.objects.filter(tenant=tenant_b, entity_code="tnt_iso_c").exists()

    # 3. SalesMethodology create
    smd_data = _masterdataconfig_smd_payload(name="Tenant Isolation Methodology")
    smd_data.update({"tenant": str(tenant_b.pk), "tenant_id": str(tenant_b.pk)})
    resp_smd = client_a.post(reverse("sales:smd_create"), smd_data)
    assert resp_smd.status_code == 302
    smd = SalesMethodology.objects.filter(name="Tenant Isolation Methodology").first()
    assert smd is not None
    assert smd.tenant == tenant_a
    assert not SalesMethodology.objects.filter(tenant=tenant_b, name="Tenant Isolation Methodology").exists()

    # 4. SalesRegionalSetting create
    srg_data = _masterdataconfig_srg_payload(name="Tenant Isolation Regional", region_code="LATAM")
    srg_data.update({"tenant": str(tenant_b.pk), "tenant_id": str(tenant_b.pk)})
    resp_srg = client_a.post(reverse("sales:srg_create"), srg_data)
    assert resp_srg.status_code == 302
    srg = SalesRegionalSetting.objects.filter(name="Tenant Isolation Regional").first()
    assert srg is not None
    assert srg.tenant == tenant_a
    assert not SalesRegionalSetting.objects.filter(tenant=tenant_b, name="Tenant Isolation Regional").exists()


def test_masterdataconfig_mass_assignment_number_forgery_ignored_on_create(
    client_a,
    tenant_a,
):
    """Forged POST bodies containing arbitrary number values cannot override sequence numbering."""
    pb_a = _masterdataconfig_price_book(tenant_a)
    prod_a = _masterdataconfig_product(tenant_a)

    # 1. PBE
    pbe_data = _masterdataconfig_pbe_payload(pb_a, prod_a, sku_code="SKU-NUM-TEST-1")
    pbe_data["number"] = "PBE-FORGED-99999"
    resp_pbe = client_a.post(reverse("sales:pbe_create"), pbe_data)
    assert resp_pbe.status_code == 302
    pbe = SalesPriceBookEntry.objects.get(tenant=tenant_a, sku_code="SKU-NUM-TEST-1")
    assert pbe.number != "PBE-FORGED-99999"
    assert pbe.number.startswith("PBE-")

    # 2. SCO
    sco_data = _masterdataconfig_sco_payload(name="Number Probe Entity", entity_code="num_probe_c")
    sco_data["number"] = "SCO-FORGED-99999"
    resp_sco = client_a.post(reverse("sales:sco_create"), sco_data)
    assert resp_sco.status_code == 302
    sco = SalesCustomEntityDefinition.objects.get(tenant=tenant_a, entity_code="num_probe_c")
    assert sco.number != "SCO-FORGED-99999"
    assert sco.number.startswith("SCO-")

    # 3. SMD
    smd_data = _masterdataconfig_smd_payload(name="Number Probe Methodology")
    smd_data["number"] = "SMD-FORGED-99999"
    resp_smd = client_a.post(reverse("sales:smd_create"), smd_data)
    assert resp_smd.status_code == 302
    smd = SalesMethodology.objects.get(tenant=tenant_a, name="Number Probe Methodology")
    assert smd.number != "SMD-FORGED-99999"
    assert smd.number.startswith("SMD-")

    # 4. SRG
    srg_data = _masterdataconfig_srg_payload(name="Number Probe Regional", region_code="UK")
    srg_data["number"] = "SRG-FORGED-99999"
    resp_srg = client_a.post(reverse("sales:srg_create"), srg_data)
    assert resp_srg.status_code == 302
    srg = SalesRegionalSetting.objects.get(tenant=tenant_a, name="Number Probe Regional")
    assert srg.number != "SRG-FORGED-99999"
    assert srg.number.startswith("SRG-")


def test_masterdataconfig_mass_assignment_system_fields_cannot_be_overwritten_on_edit(
    client_a,
    tenant_a,
    tenant_b,
    mdc_price_book_entry_a,
    mdc_custom_entity_a,
    mdc_methodology_a,
    mdc_regional_setting_a,
):
    """Submitting edit forms with forged tenant, number, or created_at fields cannot overwrite database values."""
    orig_pbe_num = mdc_price_book_entry_a.number
    orig_pbe_created = mdc_price_book_entry_a.created_at

    pbe_payload = _masterdataconfig_pbe_payload(
        mdc_price_book_entry_a.price_book,
        mdc_price_book_entry_a.product,
    )
    pbe_payload.update({
        "tenant": str(tenant_b.pk),
        "number": "PBE-OVERWRITE-HACK",
        "created_at": "2020-01-01T00:00:00Z",
    })
    resp = client_a.post(reverse("sales:pbe_edit", args=[mdc_price_book_entry_a.pk]), pbe_payload)
    assert resp.status_code == 302

    mdc_price_book_entry_a.refresh_from_db()
    assert mdc_price_book_entry_a.tenant == tenant_a
    assert mdc_price_book_entry_a.number == orig_pbe_num
    assert mdc_price_book_entry_a.created_at == orig_pbe_created


# ==============================================================================
# 6. Adversarial & Input Chaos
# ==============================================================================

def test_masterdataconfig_adversarial_malformed_regex_in_custom_entity_rejected(
    client_a,
    tenant_a,
):
    """Submitting malformed regular expressions in custom entity definition validation rules is rejected with ValidationError."""
    malformed_patterns = [
        "(?P<unclosed_group",
        "[a-z(",
        "*starts_with_multiplier",
        "(?=",
    ]
    for pattern in malformed_patterns:
        payload = _masterdataconfig_sco_payload(
            name=f"Regex Test {pattern[:4]}",
            entity_code=f"reg_{uuid.uuid4().hex[:6]}",
            validation_rule=pattern,
        )
        resp = client_a.post(reverse("sales:sco_create"), payload)
        assert resp.status_code == 200, f"Expected form re-render for malformed regex '{pattern}', got {resp.status_code}"
        form = resp.context["form"]
        assert not form.is_valid()
        assert "validation_rule" in form.errors
        assert any("Invalid regular expression pattern" in err for err in form.errors["validation_rule"])


def test_masterdataconfig_adversarial_valid_regex_in_custom_entity_accepted(
    client_a,
    tenant_a,
):
    """Submitting a valid compiled regex pattern in custom entity definition succeeds cleanly."""
    valid_pattern = r"^[A-Z0-9_-]{3,20}$"
    code = f"val_reg_{uuid.uuid4().hex[:6]}"
    payload = _masterdataconfig_sco_payload(
        name="Valid Regex Entity",
        entity_code=code,
        validation_rule=valid_pattern,
    )
    resp = client_a.post(reverse("sales:sco_create"), payload)
    assert resp.status_code == 302
    entity = SalesCustomEntityDefinition.objects.get(tenant=tenant_a, entity_code=code)
    assert entity.validation_rule == valid_pattern


def test_masterdataconfig_adversarial_out_of_bounds_cooling_off_days_rejected(
    client_a,
    tenant_a,
):
    """Submitting cooling_off_days > 365 on SalesRegionalSetting is rejected by MaxValueValidator."""
    payload = _masterdataconfig_srg_payload(
        name="Excessive Cooling Off Regional",
        region_code="APAC",
        cooling_off_days=999,
    )
    resp = client_a.post(reverse("sales:srg_create"), payload)
    assert resp.status_code == 200
    form = resp.context["form"]
    assert not form.is_valid()
    assert "cooling_off_days" in form.errors


def test_masterdataconfig_adversarial_negative_cooling_off_days_rejected(
    client_a,
    tenant_a,
):
    """Submitting negative cooling_off_days on SalesRegionalSetting is rejected by form field validation."""
    payload = _masterdataconfig_srg_payload(
        name="Negative Cooling Off Regional",
        region_code="GLOBAL",
        cooling_off_days=-10,
    )
    resp = client_a.post(reverse("sales:srg_create"), payload)
    assert resp.status_code == 200
    form = resp.context["form"]
    assert not form.is_valid()
    assert "cooling_off_days" in form.errors


def test_masterdataconfig_adversarial_out_of_bounds_min_passing_score_rejected(
    client_a,
    tenant_a,
):
    """Submitting min_passing_score > 100 on SalesMethodology is rejected by MaxValueValidator."""
    payload = _masterdataconfig_smd_payload(
        name="Impossible Passing Score Methodology",
        min_passing_score=150,
    )
    resp = client_a.post(reverse("sales:smd_create"), payload)
    assert resp.status_code == 200
    form = resp.context["form"]
    assert not form.is_valid()
    assert "min_passing_score" in form.errors


def test_masterdataconfig_adversarial_negative_min_passing_score_rejected(
    client_a,
    tenant_a,
):
    """Submitting negative min_passing_score on SalesMethodology is rejected by form validation."""
    payload = _masterdataconfig_smd_payload(
        name="Negative Passing Score Methodology",
        min_passing_score=-5,
    )
    resp = client_a.post(reverse("sales:smd_create"), payload)
    assert resp.status_code == 200
    form = resp.context["form"]
    assert not form.is_valid()
    assert "min_passing_score" in form.errors


def test_masterdataconfig_adversarial_negative_prices_rejected(
    client_a,
    tenant_a,
):
    """Submitting negative list_price or floor_price is rejected by MinValueValidator(0.00)."""
    pb_a = _masterdataconfig_price_book(tenant_a)
    prod_a = _masterdataconfig_product(tenant_a)

    # Negative list price
    payload_neg_list = _masterdataconfig_pbe_payload(
        pb_a, prod_a, sku_code="SKU-NEG-1", list_price="-50.00"
    )
    resp_list = client_a.post(reverse("sales:pbe_create"), payload_neg_list)
    assert resp_list.status_code == 200
    assert "list_price" in resp_list.context["form"].errors

    # Negative floor price
    payload_neg_floor = _masterdataconfig_pbe_payload(
        pb_a, prod_a, sku_code="SKU-NEG-2", floor_price="-10.00"
    )
    resp_floor = client_a.post(reverse("sales:pbe_create"), payload_neg_floor)
    assert resp_floor.status_code == 200
    assert "floor_price" in resp_floor.context["form"].errors


def test_masterdataconfig_adversarial_floor_price_exceeding_list_price_rejected(
    client_a,
    tenant_a,
):
    """Submitting floor_price greater than list_price is rejected by model clean() validation."""
    pb_a = _masterdataconfig_price_book(tenant_a)
    prod_a = _masterdataconfig_product(tenant_a)

    payload = _masterdataconfig_pbe_payload(
        pb_a, prod_a, sku_code="SKU-FLOOR-GT-LIST", list_price="100.00", floor_price="150.00"
    )
    resp = client_a.post(reverse("sales:pbe_create"), payload)
    assert resp.status_code == 200
    form = resp.context["form"]
    assert not form.is_valid()
    assert "floor_price" in form.errors
    assert any("Floor price cannot exceed list price" in err for err in form.errors["floor_price"])


def test_masterdataconfig_adversarial_zero_or_negative_min_quantity_rejected(
    client_a,
    tenant_a,
):
    """Submitting min_quantity <= 0.00 is rejected by MinValueValidator(0.01)."""
    pb_a = _masterdataconfig_price_book(tenant_a)
    prod_a = _masterdataconfig_product(tenant_a)

    for bad_qty in ["0.00", "-1.00"]:
        payload = _masterdataconfig_pbe_payload(
            pb_a, prod_a, sku_code=f"SKU-QTY-{bad_qty}", min_quantity=bad_qty
        )
        resp = client_a.post(reverse("sales:pbe_create"), payload)
        assert resp.status_code == 200
        form = resp.context["form"]
        assert not form.is_valid()
        assert "min_quantity" in form.errors


def test_masterdataconfig_adversarial_extreme_string_lengths_in_charfields_rejected(
    client_a,
    tenant_a,
):
    """Submitting strings exceeding max_length (e.g. 10,000 chars) on bounded CharFields is rejected by form validation."""
    huge_string = "X" * 10000
    pb_a = _masterdataconfig_price_book(tenant_a)
    prod_a = _masterdataconfig_product(tenant_a)

    # 1. Custom entity name (max 150)
    sco_payload = _masterdataconfig_sco_payload(name=huge_string)
    resp_sco = client_a.post(reverse("sales:sco_create"), sco_payload)
    assert resp_sco.status_code == 200
    assert "name" in resp_sco.context["form"].errors

    # 2. Price book entry sku_code (max 64)
    pbe_payload = _masterdataconfig_pbe_payload(pb_a, prod_a, sku_code=huge_string)
    resp_pbe = client_a.post(reverse("sales:pbe_create"), pbe_payload)
    assert resp_pbe.status_code == 200
    assert "sku_code" in resp_pbe.context["form"].errors

    # 3. Methodology name (max 150)
    smd_payload = _masterdataconfig_smd_payload(name=huge_string)
    resp_smd = client_a.post(reverse("sales:smd_create"), smd_payload)
    assert resp_smd.status_code == 200
    assert "name" in resp_smd.context["form"].errors


def test_masterdataconfig_adversarial_extreme_string_lengths_in_textfields_accepted(
    client_a,
    tenant_a,
):
    """Submitting large text bodies (10,000+ chars) in unconstrained TextFields is handled gracefully without crash."""
    large_guideline = "Tactical Guidance:\n" + ("Verify commercial and technical sponsors. " * 300)  # ~14,000 chars
    smd_payload = _masterdataconfig_smd_payload(
        name="Large Text Coaching Methodology",
        coaching_guidelines=large_guideline,
    )
    resp = client_a.post(reverse("sales:smd_create"), smd_payload)
    assert resp.status_code == 302
    smd = SalesMethodology.objects.get(tenant=tenant_a, name="Large Text Coaching Methodology")
    assert len(smd.coaching_guidelines) > 10000


def test_masterdataconfig_adversarial_malformed_json_in_tier_breaks_rejected(
    client_a,
    tenant_a,
):
    """Submitting malformed or broken JSON in volume_tier_breaks_raw is rejected with a clean ValidationError."""
    pb_a = _masterdataconfig_price_book(tenant_a)
    prod_a = _masterdataconfig_product(tenant_a)

    payload = _masterdataconfig_pbe_payload(
        pb_a, prod_a, sku_code="SKU-JSON-ERR-1", volume_tier_breaks_raw="{broken_json: true"
    )
    resp = client_a.post(reverse("sales:pbe_create"), payload)
    assert resp.status_code == 200
    form = resp.context["form"]
    assert not form.is_valid()
    assert "volume_tier_breaks_raw" in form.errors
    assert any("Invalid JSON format" in err for err in form.errors["volume_tier_breaks_raw"])


def test_masterdataconfig_adversarial_non_list_json_in_tier_breaks_rejected(
    client_a,
    tenant_a,
):
    """Submitting a JSON object instead of an array in volume_tier_breaks_raw is rejected with ValidationError."""
    pb_a = _masterdataconfig_price_book(tenant_a)
    prod_a = _masterdataconfig_product(tenant_a)

    payload = _masterdataconfig_pbe_payload(
        pb_a, prod_a, sku_code="SKU-JSON-ERR-2", volume_tier_breaks_raw='{"min_qty": 10, "discount": 5}'
    )
    resp = client_a.post(reverse("sales:pbe_create"), payload)
    assert resp.status_code == 200
    form = resp.context["form"]
    assert not form.is_valid()
    assert "volume_tier_breaks_raw" in form.errors
    assert any("Must be a JSON array of tier objects" in err for err in form.errors["volume_tier_breaks_raw"])


def test_masterdataconfig_adversarial_malformed_json_in_qualification_criteria_fallback(
    client_a,
    tenant_a,
):
    """Submitting malformed JSON starting with '[' in qualification_criteria_raw is rejected with ValidationError."""
    payload = _masterdataconfig_smd_payload(
        name="Broken Criteria JSON Methodology",
        qualification_criteria_raw="[broken_json_array: 123",
    )
    resp = client_a.post(reverse("sales:smd_create"), payload)
    assert resp.status_code == 200
    form = resp.context["form"]
    assert not form.is_valid()
    assert "qualification_criteria_raw" in form.errors
    assert any("Invalid JSON format" in err for err in form.errors["qualification_criteria_raw"])


# ==============================================================================
# 7. CSRF Protection
# ==============================================================================

def test_masterdataconfig_csrf_protection_enforced_on_all_mutating_endpoints(
    admin_user,
    mdc_price_book_entry_a,
    mdc_custom_entity_a,
    mdc_methodology_a,
    mdc_regional_setting_a,
):
    """POST to all 12 mutating endpoints with Client(enforce_csrf_checks=True) returns 403 Forbidden without CSRF token."""
    csrf_client = _masterdataconfig_csrf_client(admin_user)

    mutating_post_urls = [
        # 4 Create POSTs
        reverse("sales:pbe_create"),
        reverse("sales:sco_create"),
        reverse("sales:smd_create"),
        reverse("sales:srg_create"),
        # 4 Edit POSTs
        reverse("sales:pbe_edit", args=[mdc_price_book_entry_a.pk]),
        reverse("sales:sco_edit", args=[mdc_custom_entity_a.pk]),
        reverse("sales:smd_edit", args=[mdc_methodology_a.pk]),
        reverse("sales:srg_edit", args=[mdc_regional_setting_a.pk]),
        # 4 Delete POSTs
        reverse("sales:pbe_delete", args=[mdc_price_book_entry_a.pk]),
        reverse("sales:sco_delete", args=[mdc_custom_entity_a.pk]),
        reverse("sales:smd_delete", args=[mdc_methodology_a.pk]),
        reverse("sales:srg_delete", args=[mdc_regional_setting_a.pk]),
    ]
    assert len(mutating_post_urls) == 12

    for url in mutating_post_urls:
        resp = csrf_client.post(url, {})
        assert resp.status_code == 403, (
            f"CSRF protection failed for POST {url}: expected 403 Forbidden, got {resp.status_code}"
        )
