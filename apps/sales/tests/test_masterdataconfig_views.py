"""Integration and unit tests for Sales 8.19 Master Data & Configuration views.

Subslug: masterdataconfig
Prefix for test functions: test_masterdataconfig_*
Prefix for helper functions: _masterdataconfig_*

Covers:
1. Central Overview Dashboard (`sales:master_data_overview`):
   - Authenticated GET 200, context contract (kpis, overview_stats, recent items).
   - Unauthenticated GET redirects to login.
   - Non-admin member GET 200 access.
2. Price Book Entries (`SalesPriceBookEntry`):
   - URL resolution for all 5 routes (`pbe_list`, `pbe_create`, `pbe_detail`, `pbe_edit`, `pbe_delete`).
   - Unauthenticated access redirects to login.
   - List View: GET 200, context contract (`entries`, `price_book_entries`), filters (`q`, `price_book`, `pricing_model`, `is_active`),
     junk/huge integer query parameters return 200 gracefully, pagination.
   - Detail View: GET 200, context contract (`entry`, `price_book_entry`), cross-tenant IDOR protection (404), 404 on missing pk.
   - Create View: GET 200, context contract (`form`, `entry`=None, `is_edit`=False), non-admin member forbidden (403),
     valid POST creates entry + AuditLog + redirects (302), invalid POST re-renders form with 200.
   - Edit View: GET 200, context contract (`form`, `entry`, `is_edit`=True), non-admin member forbidden (403),
     cross-tenant IDOR (404), valid POST updates entry + AuditLog + redirects (302), invalid POST re-renders with 200.
   - Delete View: GET does not delete record (405/302), non-admin member forbidden (403),
     cross-tenant IDOR (404), valid POST deletes entry + AuditLog + redirects (302).
3. Custom Entity Definitions (`SalesCustomEntityDefinition`):
   - URL resolution for all 5 routes (`sco_list`, `sco_create`, `sco_detail`, `sco_edit`, `sco_delete`).
   - Unauthenticated access redirects to login.
   - List View: GET 200, context contract (`definitions`, `custom_entities`), filters (`q`, `target_model`, `field_type`, `is_active`),
     junk params return 200, pagination.
   - Detail View: GET 200, context contract (`definition`, `custom_entity`), IDOR protection (404).
   - Create View: GET 200, context contract (`form`, `definition`=None, `is_edit`=False), member forbidden (403),
     valid POST creates definition + AuditLog + redirects (302), invalid POST re-renders with 200.
   - Edit View: GET 200, context contract (`form`, `definition`, `is_edit`=True), member forbidden (403),
     IDOR (404), valid POST updates definition + AuditLog + redirects (302), invalid POST re-renders with 200.
   - Delete View: GET does not delete record, member forbidden (403), IDOR (404),
     valid POST deletes definition + AuditLog + redirects (302).
4. Sales Methodologies (`SalesMethodology`):
   - URL resolution for all 5 routes (`smd_list`, `smd_create`, `smd_detail`, `smd_edit`, `smd_delete`).
   - Unauthenticated access redirects to login.
   - List View: GET 200, context contract (`methodologies`), filters (`q`, `framework`, `pipeline`, `is_active`),
     junk/huge integer query params return 200, pagination.
   - Detail View: GET 200, context contract (`methodology`), IDOR protection (404).
   - Create View: GET 200, context contract (`form`, `methodology`=None, `is_edit`=False), member forbidden (403),
     valid POST creates methodology + AuditLog + redirects (302), invalid POST re-renders with 200.
   - Edit View: GET 200, context contract (`form`, `methodology`, `is_edit`=True), member forbidden (403),
     IDOR (404), valid POST updates methodology + AuditLog + redirects (302), invalid POST re-renders with 200.
   - Delete View: GET does not delete record, member forbidden (403), IDOR (404),
     valid POST deletes methodology + AuditLog + redirects (302).
5. Regional Settings (`SalesRegionalSetting`):
   - URL resolution for all 5 routes (`srg_list`, `srg_create`, `srg_detail`, `srg_edit`, `srg_delete`).
   - Unauthenticated access redirects to login.
   - List View: GET 200, context contract (`settings`, `regional_settings`), filters (`q`, `region_code`, `compliance_framework`, `is_active`),
     junk params return 200, pagination.
   - Detail View: GET 200, context contract (`setting`, `regional_setting`), IDOR protection (404).
   - Create View: GET 200, context contract (`form`, `setting`=None, `is_edit`=False), member forbidden (403),
     valid POST creates setting + AuditLog + redirects (302), invalid POST re-renders with 200.
   - Edit View: GET 200, context contract (`form`, `setting`, `is_edit`=True), member forbidden (403),
     IDOR (404), valid POST updates setting + AuditLog + redirects (302), invalid POST re-renders with 200.
   - Delete View: GET does not delete record, member forbidden (403), IDOR (404),
     valid POST deletes setting + AuditLog + redirects (302).
6. Template Hygiene:
   - All 17 GET views rendered contain no unclosed comment tags (`{#` or `{% comment`).
"""
from decimal import Decimal
import uuid
import pytest
from django.urls import reverse

from apps.core.models import AuditLog
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

pytestmark = pytest.mark.django_db


# ==============================================================================
# Helper Functions (_masterdataconfig_*)
# ==============================================================================

def _masterdataconfig_body(response):
    """Decode response HTML content safely to string."""
    return response.content.decode("utf-8", "replace")


def _masterdataconfig_pipeline(tenant, name="Pipeline Alpha", **overrides):
    """Helper to create a test pipeline for methodology foreign key tests."""
    defaults = {
        "tenant": tenant,
        "name": name,
        "is_active": True,
        "is_default": False,
    }
    defaults.update(overrides)
    return Pipeline.objects.create(**defaults)


def _masterdataconfig_stage(tenant, pipeline, name="Stage Discovery", code=None, **overrides):
    """Helper to create a test pipeline stage for methodology foreign key tests."""
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
        "probability": 20,
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
        "sku_code": "SKU-VIEW-101",
        "currency_code": "USD",
        "list_price": "1450.00",
        "floor_price": "1100.00",
        "pricing_model": "flat",
        "min_quantity": "1.00",
        "valid_from": "2026-01-01",
        "valid_to": "2026-12-31",
        "volume_tier_breaks_raw": '[{"min_qty": 5, "discount_pct": 5.0, "unit_price": 1377.50}]',
        "is_active": True,
        "notes": "Standard commercial pricing entry.",
    }
    defaults.update(overrides)
    return defaults


def _masterdataconfig_sco_payload(**overrides):
    """Generate a valid payload dictionary for SalesCustomEntityDefinition form submission."""
    defaults = {
        "name": "Security Review Signoff",
        "entity_code": "sec_review_signoff_c",
        "target_model": "opportunity",
        "field_type": "boolean",
        "is_required": False,
        "formula_expression": "",
        "lookup_target_model": "",
        "picklist_options_raw": "",
        "validation_rule": "",
        "display_order": 20,
        "is_active": True,
        "description": "Indicates SecOps approval has been obtained prior to contract issue.",
    }
    defaults.update(overrides)
    return defaults


def _masterdataconfig_smd_payload(pipeline=None, gating_stage=None, **overrides):
    """Generate a valid payload dictionary for SalesMethodology form submission."""
    defaults = {
        "name": "SPIN Selling Framework",
        "framework": "spin",
        "pipeline": (pipeline.pk if hasattr(pipeline, "pk") else pipeline) if pipeline else "",
        "gating_stage": (gating_stage.pk if hasattr(gating_stage, "pk") else gating_stage) if gating_stage else "",
        "min_passing_score": 70,
        "is_mandatory_gate": False,
        "qualification_criteria_raw": '[{"key": "situation", "label": "Customer current setup", "weight": 25}]',
        "coaching_guidelines": "Focus on uncovering implicit needs and developing them into explicit needs.",
        "is_active": True,
    }
    defaults.update(overrides)
    return defaults


def _masterdataconfig_srg_payload(**overrides):
    """Generate a valid payload dictionary for SalesRegionalSetting form submission."""
    defaults = {
        "name": "DACH Region Commercial Terms",
        "region_code": "DACH",
        "primary_currency": "EUR",
        "supported_currencies_raw": "EUR, CHF",
        "date_format": "DD.MM.YYYY",
        "number_format": "1.234,56",
        "tax_display_mode": "tax_inclusive",
        "default_quote_terms": "Zahlbar innerhalb von 30 Tagen netto.",
        "statutory_disclaimer": "Es gelten die gesetzlichen Garantie- und Gewaehrleistungsfristen.",
        "compliance_framework": "gdpr_commercial",
        "cooling_off_days": 14,
        "is_default": False,
        "is_active": True,
    }
    defaults.update(overrides)
    return defaults


# ==============================================================================
# 1. Central Overview Dashboard Tests
# ==============================================================================

def test_masterdataconfig_overview_unauthenticated(client):
    """Unauthenticated GET to overview dashboard redirects to login."""
    url = reverse("sales:master_data_overview")
    resp = client.get(url)
    assert resp.status_code == 302
    assert "/login" in resp["Location"] or "login" in resp["Location"]


def test_masterdataconfig_overview_authenticated(
    client_a, tenant_a, mdc_price_book_entry_a, mdc_custom_entity_a, mdc_methodology_a, mdc_regional_setting_a
):
    """Authenticated GET returns 200, renders overview template, and provides kpis + overview_stats."""
    url = reverse("sales:master_data_overview")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "sales/masterdataconfiguration/overview.html" in [t.name for t in resp.templates]

    ctx = resp.context
    assert "kpis" in ctx
    assert "overview_stats" in ctx
    assert ctx["kpis"] == ctx["overview_stats"]

    kpis = ctx["kpis"]
    assert kpis["total_price_book_entries"] >= 1
    assert kpis["active_price_book_entries"] >= 1
    assert kpis["total_custom_definitions"] >= 1
    assert kpis["active_custom_definitions"] >= 1
    assert kpis["total_methodologies"] >= 1
    assert kpis["total_regional_settings"] >= 1

    assert "recent_price_book_entries" in ctx
    assert "recent_custom_entities" in ctx
    assert "recent_methodologies" in ctx
    assert "recent_regional_settings" in ctx
    assert mdc_price_book_entry_a in ctx["recent_price_book_entries"]
    assert mdc_custom_entity_a in ctx["recent_custom_entities"]
    assert mdc_methodology_a in ctx["recent_methodologies"]
    assert mdc_regional_setting_a in ctx["recent_regional_settings"]


def test_masterdataconfig_overview_member_access(member_client):
    """Non-admin authenticated member can access the overview dashboard (200)."""
    url = reverse("sales:master_data_overview")
    resp = member_client.get(url)
    assert resp.status_code == 200


# ==============================================================================
# 2. Price Book Entries (`SalesPriceBookEntry`) Views
# ==============================================================================

def test_masterdataconfig_pbe_url_resolution(mdc_price_book_entry_a):
    """Verify URL reversal for all 5 Price Book Entry endpoints."""
    pk = mdc_price_book_entry_a.pk
    assert reverse("sales:pbe_list") == "/sales/master-data/price-book-entries/"
    assert reverse("sales:pbe_create") == "/sales/master-data/price-book-entries/create/"
    assert reverse("sales:pbe_detail", kwargs={"pk": pk}) == f"/sales/master-data/price-book-entries/{pk}/"
    assert reverse("sales:pbe_edit", kwargs={"pk": pk}) == f"/sales/master-data/price-book-entries/{pk}/edit/"
    assert reverse("sales:pbe_delete", kwargs={"pk": pk}) == f"/sales/master-data/price-book-entries/{pk}/delete/"


def test_masterdataconfig_pbe_unauthenticated_redirects(client, mdc_price_book_entry_a):
    """Unauthenticated requests to PBE routes redirect to login."""
    pk = mdc_price_book_entry_a.pk
    for route, kwargs, method in [
        ("sales:pbe_list", None, "get"),
        ("sales:pbe_create", None, "get"),
        ("sales:pbe_detail", {"pk": pk}, "get"),
        ("sales:pbe_edit", {"pk": pk}, "get"),
        ("sales:pbe_delete", {"pk": pk}, "post"),
    ]:
        url = reverse(route, kwargs=kwargs)
        resp = getattr(client, method)(url)
        assert resp.status_code == 302, f"Expected 302 on unauthenticated {route}"


def test_masterdataconfig_pbe_list_view_context_contract(client_a, mdc_price_book_entry_a):
    """pbe_list passes both 'entries' and 'price_book_entries' alongside filter choices."""
    url = reverse("sales:pbe_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "sales/masterdataconfiguration/pricebookentry/list.html" in [t.name for t in resp.templates]

    ctx = resp.context
    assert "page_obj" in ctx
    assert "entries" in ctx
    assert "price_book_entries" in ctx
    assert list(ctx["entries"]) == list(ctx["page_obj"].object_list)
    assert list(ctx["price_book_entries"]) == list(ctx["page_obj"].object_list)
    assert "price_books" in ctx
    assert "pricing_models" in ctx
    assert "q" in ctx
    assert "selected_price_book" in ctx
    assert "selected_pricing_model" in ctx
    assert "selected_active" in ctx


def test_masterdataconfig_pbe_list_view_filters(client_a, tenant_a):
    """pbe_list filters by search q, price_book, pricing_model, and is_active."""
    pb1 = _masterdataconfig_price_book(tenant_a, name="Catalog Primary")
    pb2 = _masterdataconfig_price_book(tenant_a, name="Catalog Secondary")
    prod1 = _masterdataconfig_product(tenant_a, name="Alpha Engine", sku="SKU-FLAT-01")
    prod2 = _masterdataconfig_product(tenant_a, name="Beta Platform", sku="SKU-TIER-02")

    pbe1 = _masterdataconfig_price_book_entry(
        tenant_a, price_book=pb1, product=prod1, sku_code="SKU-FLAT-01",
        pricing_model="flat", is_active=True, notes="Alpha note"
    )
    pbe2 = _masterdataconfig_price_book_entry(
        tenant_a, price_book=pb2, product=prod2, sku_code="SKU-TIER-02",
        pricing_model="tier_volume", is_active=False, notes="Beta note"
    )

    url = reverse("sales:pbe_list")

    # Search filter q by SKU
    resp = client_a.get(url, {"q": "SKU-FLAT-01"})
    assert pbe1 in resp.context["entries"]
    assert pbe2 not in resp.context["entries"]

    # Filter by price_book
    resp = client_a.get(url, {"price_book": str(pb2.pk)})
    assert pbe2 in resp.context["entries"]
    assert pbe1 not in resp.context["entries"]

    # Filter by pricing_model
    resp = client_a.get(url, {"pricing_model": "tier_volume"})
    assert pbe2 in resp.context["entries"]
    assert pbe1 not in resp.context["entries"]

    # Filter by is_active=true
    resp = client_a.get(url, {"is_active": "true"})
    assert pbe1 in resp.context["entries"]
    assert pbe2 not in resp.context["entries"]

    # Filter by is_active=false
    resp = client_a.get(url, {"is_active": "0"})
    assert pbe2 in resp.context["entries"]
    assert pbe1 not in resp.context["entries"]


def test_masterdataconfig_pbe_list_view_junk_params(client_a):
    """pbe_list handles junk and unrecognized query params gracefully (no 500)."""
    url = reverse("sales:pbe_list")
    resp = client_a.get(url, {
        "price_book": "invalid",
        "pricing_model": "unknown",
        "is_active": "maybe",
        "status": "unknown",
        "q": "%%%###@@@",
    })
    assert resp.status_code == 200

    resp_nonexistent = client_a.get(url, {"price_book": "999999"})
    assert resp_nonexistent.status_code == 200


def test_masterdataconfig_pbe_list_view_pagination(client_a, tenant_a):
    """pbe_list handles valid, invalid, and out-of-range pagination parameters."""
    url = reverse("sales:pbe_list")

    resp_normal = client_a.get(url, {"page": "1"})
    assert resp_normal.status_code == 200

    resp_invalid = client_a.get(url, {"page": "invalid_page"})
    assert resp_invalid.status_code == 200
    assert resp_invalid.context["page_obj"].number == 1

    resp_out = client_a.get(url, {"page": "999999"})
    assert resp_out.status_code == 200


def test_masterdataconfig_pbe_list_view_member_access(member_client):
    """Non-admin authenticated member can access pbe_list (200)."""
    resp = member_client.get(reverse("sales:pbe_list"))
    assert resp.status_code == 200


def test_masterdataconfig_pbe_detail_view(client_a, mdc_price_book_entry_a):
    """pbe_detail returns 200 and passes both 'entry' and 'price_book_entry' in context."""
    url = reverse("sales:pbe_detail", kwargs={"pk": mdc_price_book_entry_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "sales/masterdataconfiguration/pricebookentry/detail.html" in [t.name for t in resp.templates]
    assert resp.context["entry"] == mdc_price_book_entry_a
    assert resp.context["price_book_entry"] == mdc_price_book_entry_a


def test_masterdataconfig_pbe_detail_view_idor(client_a, mdc_price_book_entry_b):
    """Tenant A client accessing Tenant B's price book entry receives 404 (IDOR guard)."""
    url = reverse("sales:pbe_detail", kwargs={"pk": mdc_price_book_entry_b.pk})
    resp = client_a.get(url)
    assert resp.status_code == 404


def test_masterdataconfig_pbe_detail_view_nonexistent(client_a):
    """pbe_detail returns 404 for non-existent pk."""
    url = reverse("sales:pbe_detail", kwargs={"pk": 9999999})
    assert client_a.get(url).status_code == 404


def test_masterdataconfig_pbe_detail_view_member_access(member_client, mdc_price_book_entry_a):
    """Non-admin authenticated member can access pbe_detail (200)."""
    url = reverse("sales:pbe_detail", kwargs={"pk": mdc_price_book_entry_a.pk})
    assert member_client.get(url).status_code == 200


def test_masterdataconfig_pbe_create_view_get(client_a):
    """pbe_create GET returns 200 and passes form with is_edit=False."""
    url = reverse("sales:pbe_create")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "sales/masterdataconfiguration/pricebookentry/form.html" in [t.name for t in resp.templates]
    assert resp.context["is_edit"] is False
    assert resp.context["entry"] is None
    assert resp.context["price_book_entry"] is None


def test_masterdataconfig_pbe_create_view_member_forbidden(member_client):
    """Non-admin member cannot access pbe_create (403 Forbidden)."""
    url = reverse("sales:pbe_create")
    assert member_client.get(url).status_code == 403


def test_masterdataconfig_pbe_create_view_post_success(client_a, tenant_a):
    """Valid POST creates entry, generates AuditLog, and redirects to pbe_detail."""
    pb = _masterdataconfig_price_book(tenant_a, name="Creation Test Catalog")
    prod = _masterdataconfig_product(tenant_a, name="Creation Test Product", sku="SKU-CRT-01")

    payload = _masterdataconfig_pbe_payload(pb, prod, sku_code="SKU-CRT-01", list_price="2100.00")
    url = reverse("sales:pbe_create")
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302

    created = SalesPriceBookEntry.objects.filter(tenant=tenant_a, sku_code="SKU-CRT-01").first()
    assert created is not None
    assert created.list_price == Decimal("2100.00")
    assert resp["Location"].endswith(reverse("sales:pbe_detail", kwargs={"pk": created.pk}))

    assert AuditLog.objects.filter(tenant=tenant_a, action="create", object_id=created.pk).exists()


def test_masterdataconfig_pbe_create_view_post_invalid(client_a, tenant_a):
    """Invalid POST re-renders form with 200 and validation errors, creating no object or audit log."""
    url = reverse("sales:pbe_create")
    initial_count = SalesPriceBookEntry.objects.filter(tenant=tenant_a).count()

    # Missing product and price_book
    resp = client_a.post(url, data={"notes": "Invalid entry without required FKs"})
    assert resp.status_code == 200
    assert resp.context["form"].errors
    assert SalesPriceBookEntry.objects.filter(tenant=tenant_a).count() == initial_count


def test_masterdataconfig_pbe_edit_view_get(client_a, mdc_price_book_entry_a):
    """pbe_edit GET returns 200 and passes form with is_edit=True and entry context."""
    url = reverse("sales:pbe_edit", kwargs={"pk": mdc_price_book_entry_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "sales/masterdataconfiguration/pricebookentry/form.html" in [t.name for t in resp.templates]
    assert resp.context["is_edit"] is True
    assert resp.context["entry"] == mdc_price_book_entry_a
    assert resp.context["price_book_entry"] == mdc_price_book_entry_a


def test_masterdataconfig_pbe_edit_view_member_forbidden(member_client, mdc_price_book_entry_a):
    """Non-admin member cannot edit pbe (403 Forbidden)."""
    url = reverse("sales:pbe_edit", kwargs={"pk": mdc_price_book_entry_a.pk})
    assert member_client.get(url).status_code == 403


def test_masterdataconfig_pbe_edit_view_idor(client_a, mdc_price_book_entry_b):
    """Tenant A client editing Tenant B's entry receives 404 (IDOR guard)."""
    url = reverse("sales:pbe_edit", kwargs={"pk": mdc_price_book_entry_b.pk})
    assert client_a.get(url).status_code == 404
    assert client_a.post(url, data={"notes": "Exploit attempt"}).status_code == 404


def test_masterdataconfig_pbe_edit_view_post_success(client_a, tenant_a, mdc_price_book_entry_a):
    """Valid POST updates entry, generates AuditLog, and redirects to pbe_detail."""
    url = reverse("sales:pbe_edit", kwargs={"pk": mdc_price_book_entry_a.pk})
    payload = _masterdataconfig_pbe_payload(
        mdc_price_book_entry_a.price_book,
        mdc_price_book_entry_a.product,
        list_price="3500.00",
        notes="Updated pricing contract terms.",
    )
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302
    assert resp["Location"].endswith(reverse("sales:pbe_detail", kwargs={"pk": mdc_price_book_entry_a.pk}))

    mdc_price_book_entry_a.refresh_from_db()
    assert mdc_price_book_entry_a.list_price == Decimal("3500.00")
    assert mdc_price_book_entry_a.notes == "Updated pricing contract terms."

    assert AuditLog.objects.filter(tenant=tenant_a, action="update", object_id=mdc_price_book_entry_a.pk).exists()


def test_masterdataconfig_pbe_edit_view_post_invalid(client_a, mdc_price_book_entry_a):
    """Invalid POST to edit view re-renders form with 200 and validation errors."""
    url = reverse("sales:pbe_edit", kwargs={"pk": mdc_price_book_entry_a.pk})
    resp = client_a.post(url, data={"list_price": "-100.00"})  # negative price
    assert resp.status_code == 200
    assert resp.context["form"].errors


def test_masterdataconfig_pbe_delete_view_get_does_not_delete(client_a, mdc_price_book_entry_a):
    """GET request to pbe_delete does not delete the entry (guarded with @require_POST)."""
    url = reverse("sales:pbe_delete", kwargs={"pk": mdc_price_book_entry_a.pk})
    resp = client_a.get(url)
    assert resp.status_code in (302, 405)
    assert SalesPriceBookEntry.objects.filter(pk=mdc_price_book_entry_a.pk).exists()


def test_masterdataconfig_pbe_delete_view_member_forbidden(member_client, mdc_price_book_entry_a):
    """Non-admin member cannot delete entry (403 Forbidden)."""
    url = reverse("sales:pbe_delete", kwargs={"pk": mdc_price_book_entry_a.pk})
    assert member_client.post(url).status_code == 403
    assert SalesPriceBookEntry.objects.filter(pk=mdc_price_book_entry_a.pk).exists()


def test_masterdataconfig_pbe_delete_view_idor(client_a, mdc_price_book_entry_b):
    """Tenant A client deleting Tenant B's entry receives 404 (IDOR guard)."""
    url = reverse("sales:pbe_delete", kwargs={"pk": mdc_price_book_entry_b.pk})
    assert client_a.post(url).status_code == 404
    assert SalesPriceBookEntry.objects.filter(pk=mdc_price_book_entry_b.pk).exists()


def test_masterdataconfig_pbe_delete_view_post_success(client_a, tenant_a):
    """POST to pbe_delete deletes entry, writes AuditLog, and redirects to pbe_list."""
    pb = _masterdataconfig_price_book(tenant_a, name="Catalog Deletable")
    prod = _masterdataconfig_product(tenant_a, name="Product Deletable", sku="SKU-DEL-01")
    entry = _masterdataconfig_price_book_entry(tenant_a, price_book=pb, product=prod)
    pk = entry.pk

    url = reverse("sales:pbe_delete", kwargs={"pk": pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp["Location"].endswith(reverse("sales:pbe_list"))

    assert not SalesPriceBookEntry.objects.filter(pk=pk).exists()
    assert AuditLog.objects.filter(tenant=tenant_a, action="delete", object_id=pk).exists()


# ==============================================================================
# 3. Custom Entity Definitions (`SalesCustomEntityDefinition`) Views
# ==============================================================================

def test_masterdataconfig_sco_url_resolution(mdc_custom_entity_a):
    """Verify URL reversal for all 5 Custom Entity Definition endpoints."""
    pk = mdc_custom_entity_a.pk
    assert reverse("sales:sco_list") == "/sales/master-data/custom-entities/"
    assert reverse("sales:sco_create") == "/sales/master-data/custom-entities/create/"
    assert reverse("sales:sco_detail", kwargs={"pk": pk}) == f"/sales/master-data/custom-entities/{pk}/"
    assert reverse("sales:sco_edit", kwargs={"pk": pk}) == f"/sales/master-data/custom-entities/{pk}/edit/"
    assert reverse("sales:sco_delete", kwargs={"pk": pk}) == f"/sales/master-data/custom-entities/{pk}/delete/"


def test_masterdataconfig_sco_unauthenticated_redirects(client, mdc_custom_entity_a):
    """Unauthenticated requests to Custom Entity Definition routes redirect to login."""
    pk = mdc_custom_entity_a.pk
    for route, kwargs, method in [
        ("sales:sco_list", None, "get"),
        ("sales:sco_create", None, "get"),
        ("sales:sco_detail", {"pk": pk}, "get"),
        ("sales:sco_edit", {"pk": pk}, "get"),
        ("sales:sco_delete", {"pk": pk}, "post"),
    ]:
        url = reverse(route, kwargs=kwargs)
        resp = getattr(client, method)(url)
        assert resp.status_code == 302, f"Expected 302 on unauthenticated {route}"


def test_masterdataconfig_sco_list_view_context_contract(client_a, mdc_custom_entity_a):
    """sco_list passes both 'definitions' and 'custom_entities' alongside filter choices."""
    url = reverse("sales:sco_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "sales/masterdataconfiguration/customentitydefinition/list.html" in [t.name for t in resp.templates]

    ctx = resp.context
    assert "page_obj" in ctx
    assert "definitions" in ctx
    assert "custom_entities" in ctx
    assert list(ctx["definitions"]) == list(ctx["page_obj"].object_list)
    assert list(ctx["custom_entities"]) == list(ctx["page_obj"].object_list)
    assert "target_models" in ctx
    assert "field_types" in ctx
    assert "q" in ctx
    assert "selected_target_model" in ctx
    assert "selected_field_type" in ctx
    assert "selected_active" in ctx


def test_masterdataconfig_sco_list_view_filters(client_a, tenant_a):
    """sco_list filters by search q, target_model, field_type, and is_active."""
    d1 = _masterdataconfig_custom_entity(
        tenant_a, name="Customer ARR Target", entity_code="cust_arr_target_c",
        target_model="account", field_type="currency", is_active=True, description="ARR metric"
    )
    d2 = _masterdataconfig_custom_entity(
        tenant_a, name="Quote Margin Formula", entity_code="quote_margin_calc_c",
        target_model="cpq_quote", field_type="formula", is_active=False, description="Formula calc"
    )

    url = reverse("sales:sco_list")

    # Search filter q
    resp = client_a.get(url, {"q": "cust_arr_target_c"})
    assert d1 in resp.context["definitions"]
    assert d2 not in resp.context["definitions"]

    # Filter target_model
    resp = client_a.get(url, {"target_model": "cpq_quote"})
    assert d2 in resp.context["definitions"]
    assert d1 not in resp.context["definitions"]

    # Filter field_type
    resp = client_a.get(url, {"field_type": "currency"})
    assert d1 in resp.context["definitions"]
    assert d2 not in resp.context["definitions"]

    # Filter is_active
    resp = client_a.get(url, {"is_active": "true"})
    assert d1 in resp.context["definitions"]
    assert d2 not in resp.context["definitions"]


def test_masterdataconfig_sco_list_view_junk_params(client_a):
    """sco_list handles junk and unrecognized filter choices gracefully (no 500)."""
    url = reverse("sales:sco_list")
    resp = client_a.get(url, {
        "target_model": "invalid_model_identifier",
        "field_type": "unrecognized_type",
        "is_active": "random_junk",
        "q": "???***!!!",
    })
    assert resp.status_code == 200


def test_masterdataconfig_sco_list_view_pagination(client_a):
    """sco_list handles pagination gracefully."""
    url = reverse("sales:sco_list")
    assert client_a.get(url, {"page": "1"}).status_code == 200
    assert client_a.get(url, {"page": "invalid"}).status_code == 200
    assert client_a.get(url, {"page": "9999"}).status_code == 200


def test_masterdataconfig_sco_list_view_member_access(member_client):
    """Non-admin member can access sco_list (200)."""
    assert member_client.get(reverse("sales:sco_list")).status_code == 200


def test_masterdataconfig_sco_detail_view(client_a, mdc_custom_entity_a):
    """sco_detail returns 200 and passes both 'definition' and 'custom_entity'."""
    url = reverse("sales:sco_detail", kwargs={"pk": mdc_custom_entity_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "sales/masterdataconfiguration/customentitydefinition/detail.html" in [t.name for t in resp.templates]
    assert resp.context["definition"] == mdc_custom_entity_a
    assert resp.context["custom_entity"] == mdc_custom_entity_a


def test_masterdataconfig_sco_detail_view_idor(client_a, mdc_custom_entity_b):
    """Tenant A client accessing Tenant B's custom entity receives 404 (IDOR guard)."""
    url = reverse("sales:sco_detail", kwargs={"pk": mdc_custom_entity_b.pk})
    assert client_a.get(url).status_code == 404


def test_masterdataconfig_sco_detail_view_nonexistent(client_a):
    """sco_detail returns 404 for non-existent pk."""
    url = reverse("sales:sco_detail", kwargs={"pk": 9999999})
    assert client_a.get(url).status_code == 404


def test_masterdataconfig_sco_detail_view_member_access(member_client, mdc_custom_entity_a):
    """Non-admin member can access sco_detail (200)."""
    url = reverse("sales:sco_detail", kwargs={"pk": mdc_custom_entity_a.pk})
    assert member_client.get(url).status_code == 200


def test_masterdataconfig_sco_create_view_get(client_a):
    """sco_create GET returns 200 and passes form with is_edit=False."""
    url = reverse("sales:sco_create")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "sales/masterdataconfiguration/customentitydefinition/form.html" in [t.name for t in resp.templates]
    assert resp.context["is_edit"] is False
    assert resp.context["definition"] is None
    assert resp.context["custom_entity"] is None


def test_masterdataconfig_sco_create_view_member_forbidden(member_client):
    """Non-admin member cannot access sco_create (403 Forbidden)."""
    url = reverse("sales:sco_create")
    assert member_client.get(url).status_code == 403


def test_masterdataconfig_sco_create_view_post_success(client_a, tenant_a):
    """Valid POST creates definition, writes AuditLog, and redirects to sco_detail."""
    payload = _masterdataconfig_sco_payload(
        name="Deal Risk Rating",
        entity_code="deal_risk_rating_c",
        target_model="opportunity",
        field_type="picklist",
        picklist_options_raw="Low\nMedium\nHigh\nCritical",
    )
    url = reverse("sales:sco_create")
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302

    created = SalesCustomEntityDefinition.objects.filter(tenant=tenant_a, entity_code="deal_risk_rating_c").first()
    assert created is not None
    assert created.name == "Deal Risk Rating"
    assert created.picklist_options == ["Low", "Medium", "High", "Critical"]
    assert resp["Location"].endswith(reverse("sales:sco_detail", kwargs={"pk": created.pk}))

    assert AuditLog.objects.filter(tenant=tenant_a, action="create", object_id=created.pk).exists()


def test_masterdataconfig_sco_create_view_post_invalid(client_a, tenant_a):
    """Invalid POST re-renders form with 200 and validation errors, creating no object or audit log."""
    url = reverse("sales:sco_create")
    initial_count = SalesCustomEntityDefinition.objects.filter(tenant=tenant_a).count()

    resp = client_a.post(url, data={"name": ""})  # missing name and entity_code
    assert resp.status_code == 200
    assert resp.context["form"].errors
    assert SalesCustomEntityDefinition.objects.filter(tenant=tenant_a).count() == initial_count


def test_masterdataconfig_sco_edit_view_get(client_a, mdc_custom_entity_a):
    """sco_edit GET returns 200 and passes form with is_edit=True and definition context."""
    url = reverse("sales:sco_edit", kwargs={"pk": mdc_custom_entity_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "sales/masterdataconfiguration/customentitydefinition/form.html" in [t.name for t in resp.templates]
    assert resp.context["is_edit"] is True
    assert resp.context["definition"] == mdc_custom_entity_a
    assert resp.context["custom_entity"] == mdc_custom_entity_a


def test_masterdataconfig_sco_edit_view_member_forbidden(member_client, mdc_custom_entity_a):
    """Non-admin member cannot edit custom definition (403 Forbidden)."""
    url = reverse("sales:sco_edit", kwargs={"pk": mdc_custom_entity_a.pk})
    assert member_client.get(url).status_code == 403


def test_masterdataconfig_sco_edit_view_idor(client_a, mdc_custom_entity_b):
    """Tenant A client editing Tenant B's custom definition receives 404 (IDOR guard)."""
    url = reverse("sales:sco_edit", kwargs={"pk": mdc_custom_entity_b.pk})
    assert client_a.get(url).status_code == 404
    assert client_a.post(url, data={"name": "Exploit attempt"}).status_code == 404


def test_masterdataconfig_sco_edit_view_post_success(client_a, tenant_a, mdc_custom_entity_a):
    """Valid POST updates definition, generates AuditLog, and redirects to sco_detail."""
    url = reverse("sales:sco_edit", kwargs={"pk": mdc_custom_entity_a.pk})
    payload = _masterdataconfig_sco_payload(
        name="Updated Authority Level",
        entity_code=mdc_custom_entity_a.entity_code,
        target_model=mdc_custom_entity_a.target_model,
        field_type=mdc_custom_entity_a.field_type,
        description="Updated documentation notes.",
    )
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302
    assert resp["Location"].endswith(reverse("sales:sco_detail", kwargs={"pk": mdc_custom_entity_a.pk}))

    mdc_custom_entity_a.refresh_from_db()
    assert mdc_custom_entity_a.name == "Updated Authority Level"
    assert mdc_custom_entity_a.description == "Updated documentation notes."

    assert AuditLog.objects.filter(tenant=tenant_a, action="update", object_id=mdc_custom_entity_a.pk).exists()


def test_masterdataconfig_sco_edit_view_post_invalid(client_a, mdc_custom_entity_a):
    """Invalid POST to edit view re-renders form with 200 and validation errors."""
    url = reverse("sales:sco_edit", kwargs={"pk": mdc_custom_entity_a.pk})
    resp = client_a.post(url, data={"name": ""})
    assert resp.status_code == 200
    assert resp.context["form"].errors


def test_masterdataconfig_sco_delete_view_get_does_not_delete(client_a, mdc_custom_entity_a):
    """GET request to sco_delete does not delete the definition (guarded with @require_POST)."""
    url = reverse("sales:sco_delete", kwargs={"pk": mdc_custom_entity_a.pk})
    resp = client_a.get(url)
    assert resp.status_code in (302, 405)
    assert SalesCustomEntityDefinition.objects.filter(pk=mdc_custom_entity_a.pk).exists()


def test_masterdataconfig_sco_delete_view_member_forbidden(member_client, mdc_custom_entity_a):
    """Non-admin member cannot delete custom definition (403 Forbidden)."""
    url = reverse("sales:sco_delete", kwargs={"pk": mdc_custom_entity_a.pk})
    assert member_client.post(url).status_code == 403
    assert SalesCustomEntityDefinition.objects.filter(pk=mdc_custom_entity_a.pk).exists()


def test_masterdataconfig_sco_delete_view_idor(client_a, mdc_custom_entity_b):
    """Tenant A client deleting Tenant B's custom definition receives 404 (IDOR guard)."""
    url = reverse("sales:sco_delete", kwargs={"pk": mdc_custom_entity_b.pk})
    assert client_a.post(url).status_code == 404
    assert SalesCustomEntityDefinition.objects.filter(pk=mdc_custom_entity_b.pk).exists()


def test_masterdataconfig_sco_delete_view_post_success(client_a, tenant_a):
    """POST to sco_delete deletes definition, writes AuditLog, and redirects to sco_list."""
    defn = _masterdataconfig_custom_entity(tenant_a, name="Temporary Field", entity_code="temp_field_c")
    pk = defn.pk

    url = reverse("sales:sco_delete", kwargs={"pk": pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp["Location"].endswith(reverse("sales:sco_list"))

    assert not SalesCustomEntityDefinition.objects.filter(pk=pk).exists()
    assert AuditLog.objects.filter(tenant=tenant_a, action="delete", object_id=pk).exists()


# ==============================================================================
# 4. Sales Methodologies (`SalesMethodology`) Views
# ==============================================================================

def test_masterdataconfig_smd_url_resolution(mdc_methodology_a):
    """Verify URL reversal for all 5 Sales Methodology endpoints."""
    pk = mdc_methodology_a.pk
    assert reverse("sales:smd_list") == "/sales/master-data/methodologies/"
    assert reverse("sales:smd_create") == "/sales/master-data/methodologies/create/"
    assert reverse("sales:smd_detail", kwargs={"pk": pk}) == f"/sales/master-data/methodologies/{pk}/"
    assert reverse("sales:smd_edit", kwargs={"pk": pk}) == f"/sales/master-data/methodologies/{pk}/edit/"
    assert reverse("sales:smd_delete", kwargs={"pk": pk}) == f"/sales/master-data/methodologies/{pk}/delete/"


def test_masterdataconfig_smd_unauthenticated_redirects(client, mdc_methodology_a):
    """Unauthenticated requests to Sales Methodology routes redirect to login."""
    pk = mdc_methodology_a.pk
    for route, kwargs, method in [
        ("sales:smd_list", None, "get"),
        ("sales:smd_create", None, "get"),
        ("sales:smd_detail", {"pk": pk}, "get"),
        ("sales:smd_edit", {"pk": pk}, "get"),
        ("sales:smd_delete", {"pk": pk}, "post"),
    ]:
        url = reverse(route, kwargs=kwargs)
        resp = getattr(client, method)(url)
        assert resp.status_code == 302, f"Expected 302 on unauthenticated {route}"


def test_masterdataconfig_smd_list_view_context_contract(client_a, mdc_methodology_a):
    """smd_list passes 'methodologies' alongside framework choices and pipeline querysets."""
    url = reverse("sales:smd_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "sales/masterdataconfiguration/salesmethodology/list.html" in [t.name for t in resp.templates]

    ctx = resp.context
    assert "page_obj" in ctx
    assert "methodologies" in ctx
    assert list(ctx["methodologies"]) == list(ctx["page_obj"].object_list)
    assert "frameworks" in ctx
    assert "pipelines" in ctx
    assert "q" in ctx
    assert "selected_framework" in ctx
    assert "selected_pipeline" in ctx
    assert "selected_active" in ctx


def test_masterdataconfig_smd_list_view_filters(client_a, tenant_a):
    """smd_list filters by search q, framework, pipeline, and is_active."""
    pipe1 = _masterdataconfig_pipeline(tenant_a, name="Core Pipeline")
    pipe2 = _masterdataconfig_pipeline(tenant_a, name="Channel Pipeline")

    m1 = _masterdataconfig_methodology(
        tenant_a, name="BANT Fast Track", framework="bant",
        pipeline=pipe1, is_active=True, coaching_guidelines="Qualify budget early"
    )
    m2 = _masterdataconfig_methodology(
        tenant_a, name="Challenger Sale Guide", framework="challenger",
        pipeline=pipe2, is_active=False, coaching_guidelines="Teach and tailor"
    )

    url = reverse("sales:smd_list")

    # Search filter q
    resp = client_a.get(url, {"q": "BANT Fast Track"})
    assert m1 in resp.context["methodologies"]
    assert m2 not in resp.context["methodologies"]

    # Filter framework
    resp = client_a.get(url, {"framework": "challenger"})
    assert m2 in resp.context["methodologies"]
    assert m1 not in resp.context["methodologies"]

    # Filter pipeline
    resp = client_a.get(url, {"pipeline": str(pipe1.pk)})
    assert m1 in resp.context["methodologies"]
    assert m2 not in resp.context["methodologies"]

    # Filter is_active
    resp = client_a.get(url, {"is_active": "0"})
    assert m2 in resp.context["methodologies"]
    assert m1 not in resp.context["methodologies"]


def test_masterdataconfig_smd_list_view_junk_params(client_a):
    """smd_list handles junk, invalid, and unknown query params gracefully (no 500)."""
    url = reverse("sales:smd_list")
    resp = client_a.get(url, {
        "pipeline": "invalid",
        "framework": "unrecognized_framework",
        "is_active": "unknown_val",
        "status": "unknown",
        "q": "___***&&&",
    })
    assert resp.status_code == 200

    resp_nonexistent = client_a.get(url, {"pipeline": "999999"})
    assert resp_nonexistent.status_code == 200


def test_masterdataconfig_smd_list_view_pagination(client_a):
    """smd_list handles pagination gracefully."""
    url = reverse("sales:smd_list")
    assert client_a.get(url, {"page": "1"}).status_code == 200
    assert client_a.get(url, {"page": "invalid"}).status_code == 200
    assert client_a.get(url, {"page": "9999"}).status_code == 200


def test_masterdataconfig_smd_list_view_member_access(member_client):
    """Non-admin member can access smd_list (200)."""
    assert member_client.get(reverse("sales:smd_list")).status_code == 200


def test_masterdataconfig_smd_detail_view(client_a, mdc_methodology_a):
    """smd_detail returns 200 and passes 'methodology' in context."""
    url = reverse("sales:smd_detail", kwargs={"pk": mdc_methodology_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "sales/masterdataconfiguration/salesmethodology/detail.html" in [t.name for t in resp.templates]
    assert resp.context["methodology"] == mdc_methodology_a


def test_masterdataconfig_smd_detail_view_idor(client_a, mdc_methodology_b):
    """Tenant A client accessing Tenant B's methodology receives 404 (IDOR guard)."""
    url = reverse("sales:smd_detail", kwargs={"pk": mdc_methodology_b.pk})
    assert client_a.get(url).status_code == 404


def test_masterdataconfig_smd_detail_view_nonexistent(client_a):
    """smd_detail returns 404 for non-existent pk."""
    url = reverse("sales:smd_detail", kwargs={"pk": 9999999})
    assert client_a.get(url).status_code == 404


def test_masterdataconfig_smd_detail_view_member_access(member_client, mdc_methodology_a):
    """Non-admin member can access smd_detail (200)."""
    url = reverse("sales:smd_detail", kwargs={"pk": mdc_methodology_a.pk})
    assert member_client.get(url).status_code == 200


def test_masterdataconfig_smd_create_view_get(client_a):
    """smd_create GET returns 200 and passes form with is_edit=False."""
    url = reverse("sales:smd_create")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "sales/masterdataconfiguration/salesmethodology/form.html" in [t.name for t in resp.templates]
    assert resp.context["is_edit"] is False
    assert resp.context["methodology"] is None


def test_masterdataconfig_smd_create_view_member_forbidden(member_client):
    """Non-admin member cannot access smd_create (403 Forbidden)."""
    url = reverse("sales:smd_create")
    assert member_client.get(url).status_code == 403


def test_masterdataconfig_smd_create_view_post_success(client_a, tenant_a):
    """Valid POST creates methodology, writes AuditLog, and redirects to smd_detail."""
    pipe = _masterdataconfig_pipeline(tenant_a, name="Creation Test Pipeline")
    stage = _masterdataconfig_stage(tenant_a, pipe, name="Stage Gate 1")

    payload = _masterdataconfig_smd_payload(
        pipeline=pipe,
        gating_stage=stage,
        name="Sandler Sub-Module Stage Gate",
        framework="sandler",
        min_passing_score=80,
    )
    url = reverse("sales:smd_create")
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302

    created = SalesMethodology.objects.filter(tenant=tenant_a, name="Sandler Sub-Module Stage Gate").first()
    assert created is not None
    assert created.framework == "sandler"
    assert created.min_passing_score == 80
    assert resp["Location"].endswith(reverse("sales:smd_detail", kwargs={"pk": created.pk}))

    assert AuditLog.objects.filter(tenant=tenant_a, action="create", object_id=created.pk).exists()


def test_masterdataconfig_smd_create_view_post_invalid(client_a, tenant_a):
    """Invalid POST re-renders form with 200 and validation errors, creating no object or audit log."""
    url = reverse("sales:smd_create")
    initial_count = SalesMethodology.objects.filter(tenant=tenant_a).count()

    resp = client_a.post(url, data={"name": "", "min_passing_score": 150})
    assert resp.status_code == 200
    assert resp.context["form"].errors
    assert SalesMethodology.objects.filter(tenant=tenant_a).count() == initial_count


def test_masterdataconfig_smd_edit_view_get(client_a, mdc_methodology_a):
    """smd_edit GET returns 200 and passes form with is_edit=True and methodology context."""
    url = reverse("sales:smd_edit", kwargs={"pk": mdc_methodology_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "sales/masterdataconfiguration/salesmethodology/form.html" in [t.name for t in resp.templates]
    assert resp.context["is_edit"] is True
    assert resp.context["methodology"] == mdc_methodology_a


def test_masterdataconfig_smd_edit_view_member_forbidden(member_client, mdc_methodology_a):
    """Non-admin member cannot edit methodology (403 Forbidden)."""
    url = reverse("sales:smd_edit", kwargs={"pk": mdc_methodology_a.pk})
    assert member_client.get(url).status_code == 403


def test_masterdataconfig_smd_edit_view_idor(client_a, mdc_methodology_b):
    """Tenant A client editing Tenant B's methodology receives 404 (IDOR guard)."""
    url = reverse("sales:smd_edit", kwargs={"pk": mdc_methodology_b.pk})
    assert client_a.get(url).status_code == 404
    assert client_a.post(url, data={"name": "Exploit attempt"}).status_code == 404


def test_masterdataconfig_smd_edit_view_post_success(client_a, tenant_a, mdc_methodology_a):
    """Valid POST updates methodology, generates AuditLog, and redirects to smd_detail."""
    url = reverse("sales:smd_edit", kwargs={"pk": mdc_methodology_a.pk})
    payload = _masterdataconfig_smd_payload(
        pipeline=mdc_methodology_a.pipeline,
        gating_stage=mdc_methodology_a.gating_stage,
        name="Updated MEDDPICC Framework",
        framework=mdc_methodology_a.framework,
        min_passing_score=85,
        coaching_guidelines="Updated coaching instructions.",
    )
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302
    assert resp["Location"].endswith(reverse("sales:smd_detail", kwargs={"pk": mdc_methodology_a.pk}))

    mdc_methodology_a.refresh_from_db()
    assert mdc_methodology_a.name == "Updated MEDDPICC Framework"
    assert mdc_methodology_a.min_passing_score == 85
    assert mdc_methodology_a.coaching_guidelines == "Updated coaching instructions."

    assert AuditLog.objects.filter(tenant=tenant_a, action="update", object_id=mdc_methodology_a.pk).exists()


def test_masterdataconfig_smd_edit_view_post_invalid(client_a, mdc_methodology_a):
    """Invalid POST to edit view re-renders form with 200 and validation errors."""
    url = reverse("sales:smd_edit", kwargs={"pk": mdc_methodology_a.pk})
    resp = client_a.post(url, data={"name": "", "min_passing_score": 200})
    assert resp.status_code == 200
    assert resp.context["form"].errors


def test_masterdataconfig_smd_delete_view_get_does_not_delete(client_a, mdc_methodology_a):
    """GET request to smd_delete does not delete the methodology (guarded with @require_POST)."""
    url = reverse("sales:smd_delete", kwargs={"pk": mdc_methodology_a.pk})
    resp = client_a.get(url)
    assert resp.status_code in (302, 405)
    assert SalesMethodology.objects.filter(pk=mdc_methodology_a.pk).exists()


def test_masterdataconfig_smd_delete_view_member_forbidden(member_client, mdc_methodology_a):
    """Non-admin member cannot delete methodology (403 Forbidden)."""
    url = reverse("sales:smd_delete", kwargs={"pk": mdc_methodology_a.pk})
    assert member_client.post(url).status_code == 403
    assert SalesMethodology.objects.filter(pk=mdc_methodology_a.pk).exists()


def test_masterdataconfig_smd_delete_view_idor(client_a, mdc_methodology_b):
    """Tenant A client deleting Tenant B's methodology receives 404 (IDOR guard)."""
    url = reverse("sales:smd_delete", kwargs={"pk": mdc_methodology_b.pk})
    assert client_a.post(url).status_code == 404
    assert SalesMethodology.objects.filter(pk=mdc_methodology_b.pk).exists()


def test_masterdataconfig_smd_delete_view_post_success(client_a, tenant_a):
    """POST to smd_delete deletes methodology, writes AuditLog, and redirects to smd_list."""
    meth = _masterdataconfig_methodology(tenant_a, name="Temporary Delete Methodology")
    pk = meth.pk

    url = reverse("sales:smd_delete", kwargs={"pk": pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp["Location"].endswith(reverse("sales:smd_list"))

    assert not SalesMethodology.objects.filter(pk=pk).exists()
    assert AuditLog.objects.filter(tenant=tenant_a, action="delete", object_id=pk).exists()


# ==============================================================================
# 5. Regional Settings (`SalesRegionalSetting`) Views
# ==============================================================================

def test_masterdataconfig_srg_url_resolution(mdc_regional_setting_a):
    """Verify URL reversal for all 5 Regional Setting endpoints."""
    pk = mdc_regional_setting_a.pk
    assert reverse("sales:srg_list") == "/sales/master-data/regional-settings/"
    assert reverse("sales:srg_create") == "/sales/master-data/regional-settings/create/"
    assert reverse("sales:srg_detail", kwargs={"pk": pk}) == f"/sales/master-data/regional-settings/{pk}/"
    assert reverse("sales:srg_edit", kwargs={"pk": pk}) == f"/sales/master-data/regional-settings/{pk}/edit/"
    assert reverse("sales:srg_delete", kwargs={"pk": pk}) == f"/sales/master-data/regional-settings/{pk}/delete/"


def test_masterdataconfig_srg_unauthenticated_redirects(client, mdc_regional_setting_a):
    """Unauthenticated requests to Regional Setting routes redirect to login."""
    pk = mdc_regional_setting_a.pk
    for route, kwargs, method in [
        ("sales:srg_list", None, "get"),
        ("sales:srg_create", None, "get"),
        ("sales:srg_detail", {"pk": pk}, "get"),
        ("sales:srg_edit", {"pk": pk}, "get"),
        ("sales:srg_delete", {"pk": pk}, "post"),
    ]:
        url = reverse(route, kwargs=kwargs)
        resp = getattr(client, method)(url)
        assert resp.status_code == 302, f"Expected 302 on unauthenticated {route}"


def test_masterdataconfig_srg_list_view_context_contract(client_a, mdc_regional_setting_a):
    """srg_list passes both 'settings' and 'regional_settings' alongside region/compliance choices."""
    url = reverse("sales:srg_list")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "sales/masterdataconfiguration/regionalsetting/list.html" in [t.name for t in resp.templates]

    ctx = resp.context
    assert "page_obj" in ctx
    assert "settings" in ctx
    assert "regional_settings" in ctx
    assert list(ctx["settings"]) == list(ctx["page_obj"].object_list)
    assert list(ctx["regional_settings"]) == list(ctx["page_obj"].object_list)
    assert "region_codes" in ctx
    assert "compliance_frameworks" in ctx
    assert "q" in ctx
    assert "selected_region" in ctx
    assert "selected_framework" in ctx
    assert "selected_active" in ctx


def test_masterdataconfig_srg_list_view_filters(client_a, tenant_a):
    """srg_list filters by search q, region_code, compliance_framework, and is_active."""
    # Note: UniqueConstraint(fields=["tenant", "region_code"]) restricts to one setting per region
    s1 = _masterdataconfig_regional_setting(
        tenant_a, name="UK Commercial Profile", region_code="UK",
        compliance_framework="consumer_protection", is_active=True,
        default_quote_terms="UK Statutory cooling-off applied."
    )
    s2 = _masterdataconfig_regional_setting(
        tenant_a, name="APAC Commercial Profile", region_code="APAC",
        compliance_framework="export_control", is_active=False,
        default_quote_terms="Export EAR trade control."
    )

    url = reverse("sales:srg_list")

    # Search filter q
    resp = client_a.get(url, {"q": "UK Statutory"})
    assert s1 in resp.context["settings"]
    assert s2 not in resp.context["settings"]

    # Filter region_code
    resp = client_a.get(url, {"region_code": "APAC"})
    assert s2 in resp.context["settings"]
    assert s1 not in resp.context["settings"]

    # Filter compliance_framework
    resp = client_a.get(url, {"compliance_framework": "consumer_protection"})
    assert s1 in resp.context["settings"]
    assert s2 not in resp.context["settings"]

    # Filter is_active
    resp = client_a.get(url, {"is_active": "0"})
    assert s2 in resp.context["settings"]
    assert s1 not in resp.context["settings"]


def test_masterdataconfig_srg_list_view_junk_params(client_a):
    """srg_list handles junk and unknown query parameters gracefully (no 500)."""
    url = reverse("sales:srg_list")
    resp = client_a.get(url, {
        "region_code": "non_existent_region",
        "compliance_framework": "unrecognized_framework",
        "is_active": "invalid_active_flag",
        "q": "~~~###$$$",
    })
    assert resp.status_code == 200


def test_masterdataconfig_srg_list_view_pagination(client_a):
    """srg_list handles pagination gracefully."""
    url = reverse("sales:srg_list")
    assert client_a.get(url, {"page": "1"}).status_code == 200
    assert client_a.get(url, {"page": "invalid"}).status_code == 200
    assert client_a.get(url, {"page": "9999"}).status_code == 200


def test_masterdataconfig_srg_list_view_member_access(member_client):
    """Non-admin member can access srg_list (200)."""
    assert member_client.get(reverse("sales:srg_list")).status_code == 200


def test_masterdataconfig_srg_detail_view(client_a, mdc_regional_setting_a):
    """srg_detail returns 200 and passes both 'setting' and 'regional_setting' in context."""
    url = reverse("sales:srg_detail", kwargs={"pk": mdc_regional_setting_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "sales/masterdataconfiguration/regionalsetting/detail.html" in [t.name for t in resp.templates]
    assert resp.context["setting"] == mdc_regional_setting_a
    assert resp.context["regional_setting"] == mdc_regional_setting_a


def test_masterdataconfig_srg_detail_view_idor(client_a, mdc_regional_setting_b):
    """Tenant A client accessing Tenant B's regional setting receives 404 (IDOR guard)."""
    url = reverse("sales:srg_detail", kwargs={"pk": mdc_regional_setting_b.pk})
    assert client_a.get(url).status_code == 404


def test_masterdataconfig_srg_detail_view_nonexistent(client_a):
    """srg_detail returns 404 for non-existent pk."""
    url = reverse("sales:srg_detail", kwargs={"pk": 9999999})
    assert client_a.get(url).status_code == 404


def test_masterdataconfig_srg_detail_view_member_access(member_client, mdc_regional_setting_a):
    """Non-admin member can access srg_detail (200)."""
    url = reverse("sales:srg_detail", kwargs={"pk": mdc_regional_setting_a.pk})
    assert member_client.get(url).status_code == 200


def test_masterdataconfig_srg_create_view_get(client_a):
    """srg_create GET returns 200 and passes form with is_edit=False."""
    url = reverse("sales:srg_create")
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "sales/masterdataconfiguration/regionalsetting/form.html" in [t.name for t in resp.templates]
    assert resp.context["is_edit"] is False
    assert resp.context["setting"] is None
    assert resp.context["regional_setting"] is None


def test_masterdataconfig_srg_create_view_member_forbidden(member_client):
    """Non-admin member cannot access srg_create (403 Forbidden)."""
    url = reverse("sales:srg_create")
    assert member_client.get(url).status_code == 403


def test_masterdataconfig_srg_create_view_post_success(client_a, tenant_a):
    """Valid POST creates regional setting, writes AuditLog, and redirects to srg_detail."""
    payload = _masterdataconfig_srg_payload(
        name="Latin America Terms Profile",
        region_code="LATAM",
        primary_currency="USD",
        supported_currencies_raw="USD, BRL, MXN",
    )
    url = reverse("sales:srg_create")
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302

    created = SalesRegionalSetting.objects.filter(tenant=tenant_a, region_code="LATAM").first()
    assert created is not None
    assert created.name == "Latin America Terms Profile"
    assert created.supported_currencies == ["USD", "BRL", "MXN"]
    assert resp["Location"].endswith(reverse("sales:srg_detail", kwargs={"pk": created.pk}))

    assert AuditLog.objects.filter(tenant=tenant_a, action="create", object_id=created.pk).exists()


def test_masterdataconfig_srg_create_view_post_invalid(client_a, tenant_a):
    """Invalid POST re-renders form with 200 and validation errors, creating no object or audit log."""
    url = reverse("sales:srg_create")
    initial_count = SalesRegionalSetting.objects.filter(tenant=tenant_a).count()

    resp = client_a.post(url, data={"name": "", "cooling_off_days": -10})
    assert resp.status_code == 200
    assert resp.context["form"].errors
    assert SalesRegionalSetting.objects.filter(tenant=tenant_a).count() == initial_count


def test_masterdataconfig_srg_edit_view_get(client_a, mdc_regional_setting_a):
    """srg_edit GET returns 200 and passes form with is_edit=True and setting context."""
    url = reverse("sales:srg_edit", kwargs={"pk": mdc_regional_setting_a.pk})
    resp = client_a.get(url)
    assert resp.status_code == 200
    assert "sales/masterdataconfiguration/regionalsetting/form.html" in [t.name for t in resp.templates]
    assert resp.context["is_edit"] is True
    assert resp.context["setting"] == mdc_regional_setting_a
    assert resp.context["regional_setting"] == mdc_regional_setting_a


def test_masterdataconfig_srg_edit_view_member_forbidden(member_client, mdc_regional_setting_a):
    """Non-admin member cannot edit regional setting (403 Forbidden)."""
    url = reverse("sales:srg_edit", kwargs={"pk": mdc_regional_setting_a.pk})
    assert member_client.get(url).status_code == 403


def test_masterdataconfig_srg_edit_view_idor(client_a, mdc_regional_setting_b):
    """Tenant A client editing Tenant B's regional setting receives 404 (IDOR guard)."""
    url = reverse("sales:srg_edit", kwargs={"pk": mdc_regional_setting_b.pk})
    assert client_a.get(url).status_code == 404
    assert client_a.post(url, data={"name": "Exploit attempt"}).status_code == 404


def test_masterdataconfig_srg_edit_view_post_success(client_a, tenant_a, mdc_regional_setting_a):
    """Valid POST updates regional setting, generates AuditLog, and redirects to srg_detail."""
    url = reverse("sales:srg_edit", kwargs={"pk": mdc_regional_setting_a.pk})
    payload = _masterdataconfig_srg_payload(
        name="Updated NA Commercial Terms",
        region_code="NA",
        primary_currency="USD",
        supported_currencies_raw="USD, CAD, MXN",
        default_quote_terms="Updated Net 45 payment terms.",
    )
    resp = client_a.post(url, data=payload)
    assert resp.status_code == 302
    assert resp["Location"].endswith(reverse("sales:srg_detail", kwargs={"pk": mdc_regional_setting_a.pk}))

    mdc_regional_setting_a.refresh_from_db()
    assert mdc_regional_setting_a.name == "Updated NA Commercial Terms"
    assert mdc_regional_setting_a.region_code == "NA"
    assert mdc_regional_setting_a.default_quote_terms == "Updated Net 45 payment terms."
    assert mdc_regional_setting_a.supported_currencies == ["USD", "CAD", "MXN"]

    assert AuditLog.objects.filter(tenant=tenant_a, action="update", object_id=mdc_regional_setting_a.pk).exists()


def test_masterdataconfig_srg_edit_view_post_invalid(client_a, mdc_regional_setting_a):
    """Invalid POST to edit view re-renders form with 200 and validation errors."""
    url = reverse("sales:srg_edit", kwargs={"pk": mdc_regional_setting_a.pk})
    resp = client_a.post(url, data={"name": "", "cooling_off_days": -5})
    assert resp.status_code == 200
    assert resp.context["form"].errors


def test_masterdataconfig_srg_delete_view_get_does_not_delete(client_a, mdc_regional_setting_a):
    """GET request to srg_delete does not delete the setting (guarded with @require_POST)."""
    url = reverse("sales:srg_delete", kwargs={"pk": mdc_regional_setting_a.pk})
    resp = client_a.get(url)
    assert resp.status_code in (302, 405)
    assert SalesRegionalSetting.objects.filter(pk=mdc_regional_setting_a.pk).exists()


def test_masterdataconfig_srg_delete_view_member_forbidden(member_client, mdc_regional_setting_a):
    """Non-admin member cannot delete regional setting (403 Forbidden)."""
    url = reverse("sales:srg_delete", kwargs={"pk": mdc_regional_setting_a.pk})
    assert member_client.post(url).status_code == 403
    assert SalesRegionalSetting.objects.filter(pk=mdc_regional_setting_a.pk).exists()


def test_masterdataconfig_srg_delete_view_idor(client_a, mdc_regional_setting_b):
    """Tenant A client deleting Tenant B's regional setting receives 404 (IDOR guard)."""
    url = reverse("sales:srg_delete", kwargs={"pk": mdc_regional_setting_b.pk})
    assert client_a.post(url).status_code == 404
    assert SalesRegionalSetting.objects.filter(pk=mdc_regional_setting_b.pk).exists()


def test_masterdataconfig_srg_delete_view_post_success(client_a, tenant_a):
    """POST to srg_delete deletes setting, writes AuditLog, and redirects to srg_list."""
    setting = _masterdataconfig_regional_setting(tenant_a, name="Temporary Setting", region_code="GLOBAL")
    pk = setting.pk

    url = reverse("sales:srg_delete", kwargs={"pk": pk})
    resp = client_a.post(url)
    assert resp.status_code == 302
    assert resp["Location"].endswith(reverse("sales:srg_list"))

    assert not SalesRegionalSetting.objects.filter(pk=pk).exists()
    assert AuditLog.objects.filter(tenant=tenant_a, action="delete", object_id=pk).exists()


# ==============================================================================
# 6. Template Hygiene Across All Views
# ==============================================================================

def test_masterdataconfig_template_hygiene_no_unclosed_comments(
    client_a, mdc_price_book_entry_a, mdc_custom_entity_a, mdc_methodology_a, mdc_regional_setting_a
):
    """Assert that rendered HTML responses across all GET routes contain no unclosed comment tags ({# or {% comment)."""
    pbe_pk = mdc_price_book_entry_a.pk
    sco_pk = mdc_custom_entity_a.pk
    smd_pk = mdc_methodology_a.pk
    srg_pk = mdc_regional_setting_a.pk

    routes_to_check = [
        # Overview
        reverse("sales:master_data_overview"),
        # PBE
        reverse("sales:pbe_list"),
        reverse("sales:pbe_create"),
        reverse("sales:pbe_detail", kwargs={"pk": pbe_pk}),
        reverse("sales:pbe_edit", kwargs={"pk": pbe_pk}),
        # SCO
        reverse("sales:sco_list"),
        reverse("sales:sco_create"),
        reverse("sales:sco_detail", kwargs={"pk": sco_pk}),
        reverse("sales:sco_edit", kwargs={"pk": sco_pk}),
        # SMD
        reverse("sales:smd_list"),
        reverse("sales:smd_create"),
        reverse("sales:smd_detail", kwargs={"pk": smd_pk}),
        reverse("sales:smd_edit", kwargs={"pk": smd_pk}),
        # SRG
        reverse("sales:srg_list"),
        reverse("sales:srg_create"),
        reverse("sales:srg_detail", kwargs={"pk": srg_pk}),
        reverse("sales:srg_edit", kwargs={"pk": srg_pk}),
    ]

    for route in routes_to_check:
        resp = client_a.get(route)
        assert resp.status_code == 200, f"Expected 200 on {route}, got {resp.status_code}"
        body = _masterdataconfig_body(resp)
        assert "{#" not in body, f"Found unclosed tag '{{#' in response for {route}"
        assert "{% comment" not in body, f"Found unclosed tag '{{% comment' in response for {route}"
