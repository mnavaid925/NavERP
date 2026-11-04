"""Security, Multi-Tenancy, Authorization, and Hardening Tests for Sub-module 10.3 (Data Warehouse & Storage).

Covers:
1. Authentication & Authorization gates:
   - Unauthenticated GET and POST requests across all 10.3 endpoints redirect to login.
   - Non-admin member users (is_tenant_admin=False) attempting state-changing actions
     (create, edit, delete, analyze) receive 403 Forbidden.
   - Non-admin member users retain read-only access to lists, detail views, overview, and DDL preview.
   - POST-only mutation endpoints enforce HTTP method restrictions (405 on GET).
2. Cross-Tenant Data Isolation (IDOR) — 100% strict 404 assertions:
   - Detail routes: DataMart, LakehouseZone, WarehouseStoragePolicy, WarehouseTable with tenant_b PK requested by Client A -> 404
   - Edit routes (GET & POST): DataMart, LakehouseZone, WarehouseStoragePolicy, WarehouseTable with tenant_b PK requested by Client A -> 404
   - Delete routes (POST): DataMart, LakehouseZone, WarehouseStoragePolicy, WarehouseTable with tenant_b PK requested by Client A -> 404
   - DDL preview route: WarehouseTable with tenant_b PK requested by Client A -> 404
   - Analyze route (POST): WarehouseTable with tenant_b PK requested by Client A -> 404
   - Bidirectional symmetry: Client B attempting access to Tenant A's objects -> 404
   - No cross-tenant data leakage in list queries or CSV exports.
3. Cross-Tenant Foreign Key Tampering & Injection:
   - DataMartForm rejects org_unit, owner, or steward belonging to tenant_b via field queryset and clean() reject_foreign.
   - WarehouseTableForm rejects lakehouse_zone, data_mart, or storage_policy belonging to tenant_b via field queryset and clean() reject_foreign.
   - HTTP POST submission with foreign FK IDs fails validation and does not persist records.
4. Mass Assignment Hardening:
   - Submitting tenant, number, row_count, compressed_bytes, compression_ratio, last_analyzed_at in POST payloads
     never overwrites tenant boundaries or system telemetry fields.
5. Audit Trail Verification:
   - LakehouseZone deletion blocked by ProtectedError inside transaction.atomic() does NOT emit a phantom delete AuditLog row.
   - Successful create, edit, delete, and analyze actions record proper AuditLog rows with tenant=request.tenant and correct action verb.
6. SQL Injection Prevention & Identifier Sanitization:
   - SQL injection vectors in table_name, primary_key_column, and schema_definition JSON (column names & types)
     are strictly rejected by regex and whitelisting in WarehouseTableForm.
"""
import json
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from apps.bi.forms import (
    DataMartForm,
    LakehouseZoneForm,
    WarehouseStoragePolicyForm,
    WarehouseTableForm,
)
from apps.bi.models import (
    DataMart,
    LakehouseZone,
    WarehouseStoragePolicy,
    WarehouseTable,
)
from apps.core.models import AuditLog
from apps.core.models.OrgUnit import OrgUnit

pytestmark = pytest.mark.django_db
User = get_user_model()


# ---------------------------------------------------------------------------
# Module Helpers (must be prefixed with _datawarehouse_)
# ---------------------------------------------------------------------------


def _datawarehouse_create_user(tenant, username, is_admin=False):
    """Helper to create a tenant-scoped user."""
    return User.objects.create_user(
        email=f"{username}@example.com",
        username=username,
        password="TestPass123!",
        tenant=tenant,
        is_tenant_admin=is_admin,
    )


def _datawarehouse_create_org_unit(tenant, name="Engineering Org"):
    """Helper to create a tenant-scoped OrgUnit."""
    return OrgUnit.objects.create(tenant=tenant, name=name)


def _datawarehouse_create_unreferenced_zone(tenant, name="Temp Zone", code="temp_zone"):
    """Helper to create an unreferenced LakehouseZone safe for deletion tests."""
    return LakehouseZone.objects.create(
        tenant=tenant,
        name=name,
        code=code,
        zone_type="bronze",
        storage_backend="internal_db",
        base_uri_path=f"/warehouse/{code}",
        default_format="relational_table",
        is_active=True,
    )


def _datawarehouse_create_unreferenced_policy(tenant, name="Temp Retention Policy"):
    """Helper to create an unreferenced WarehouseStoragePolicy safe for deletion tests."""
    return WarehouseStoragePolicy.objects.create(
        tenant=tenant,
        name=name,
        partition_strategy="none",
        compression_codec="none",
        vacuum_cadence="weekly",
        is_active=True,
    )


def _datawarehouse_create_unreferenced_mart(tenant, name="Temp Mart", code="temp_mart"):
    """Helper to create an unreferenced DataMart safe for deletion tests."""
    return DataMart.objects.create(
        tenant=tenant,
        name=name,
        code=code,
        subject_area="finance",
        access_tier="department",
        is_active=True,
    )


def _datawarehouse_create_unreferenced_table(tenant, zone, name="Temp Fact", table_name="fact_temp_metric"):
    """Helper to create a standalone WarehouseTable safe for deletion tests."""
    return WarehouseTable.objects.create(
        tenant=tenant,
        lakehouse_zone=zone,
        name=name,
        table_name=table_name,
        table_type="fact",
        schema_type="star",
        grain="transaction",
        primary_key_column="id",
        schema_definition=[{"name": "id", "type": "BIGINT", "nullable": False}],
        is_active=True,
    )


# ===========================================================================
# 1. Authentication & Authorization Gates
# ===========================================================================


def test_datawarehouse_security_unauthenticated_get_requests_redirect_to_login(
    anon_client,
    lakehouse_zone_a,
    storage_policy_a,
    data_mart_a,
    warehouse_table_a,
):
    """Anonymous user accessing any Sub-module 10.3 GET route is redirected to login."""
    get_routes = [
        # Overview
        reverse("bi:warehouse_overview"),
        # Lakehouse Zones
        reverse("bi:lakehouse_zone_list"),
        reverse("bi:lakehouse_zone_create"),
        reverse("bi:lakehouse_zone_detail", kwargs={"pk": lakehouse_zone_a.pk}),
        reverse("bi:lakehouse_zone_edit", kwargs={"pk": lakehouse_zone_a.pk}),
        # Storage Policies
        reverse("bi:warehouse_storage_policy_list"),
        reverse("bi:warehouse_storage_policy_create"),
        reverse("bi:warehouse_storage_policy_detail", kwargs={"pk": storage_policy_a.pk}),
        reverse("bi:warehouse_storage_policy_edit", kwargs={"pk": storage_policy_a.pk}),
        # Data Marts
        reverse("bi:data_mart_list"),
        reverse("bi:data_mart_create"),
        reverse("bi:data_mart_detail", kwargs={"pk": data_mart_a.pk}),
        reverse("bi:data_mart_edit", kwargs={"pk": data_mart_a.pk}),
        # Warehouse Tables
        reverse("bi:warehouse_table_list"),
        reverse("bi:warehouse_table_create"),
        reverse("bi:warehouse_table_detail", kwargs={"pk": warehouse_table_a.pk}),
        reverse("bi:warehouse_table_edit", kwargs={"pk": warehouse_table_a.pk}),
        reverse("bi:warehouse_table_ddl_preview", kwargs={"pk": warehouse_table_a.pk}),
    ]

    for url in get_routes:
        res = anon_client.get(url)
        assert res.status_code == 302, f"Expected 302 redirect for anon GET {url}, got {res.status_code}"
        assert "/accounts/login" in res.url or "login" in res.url


def test_datawarehouse_security_unauthenticated_post_requests_redirect_to_login(
    anon_client,
    lakehouse_zone_a,
    storage_policy_a,
    data_mart_a,
    warehouse_table_a,
):
    """Anonymous user submitting POST to any Sub-module 10.3 mutation route is redirected to login."""
    post_routes = [
        # Creates
        (reverse("bi:lakehouse_zone_create"), {"name": "Anon Zone"}),
        (reverse("bi:warehouse_storage_policy_create"), {"name": "Anon Policy"}),
        (reverse("bi:data_mart_create"), {"name": "Anon Mart"}),
        (reverse("bi:warehouse_table_create"), {"name": "Anon Table"}),
        # Edits
        (reverse("bi:lakehouse_zone_edit", kwargs={"pk": lakehouse_zone_a.pk}), {"name": "Hacked Zone"}),
        (reverse("bi:warehouse_storage_policy_edit", kwargs={"pk": storage_policy_a.pk}), {"name": "Hacked Policy"}),
        (reverse("bi:data_mart_edit", kwargs={"pk": data_mart_a.pk}), {"name": "Hacked Mart"}),
        (reverse("bi:warehouse_table_edit", kwargs={"pk": warehouse_table_a.pk}), {"name": "Hacked Table"}),
        # Deletes
        (reverse("bi:lakehouse_zone_delete", kwargs={"pk": lakehouse_zone_a.pk}), {}),
        (reverse("bi:warehouse_storage_policy_delete", kwargs={"pk": storage_policy_a.pk}), {}),
        (reverse("bi:data_mart_delete", kwargs={"pk": data_mart_a.pk}), {}),
        (reverse("bi:warehouse_table_delete", kwargs={"pk": warehouse_table_a.pk}), {}),
        # Analyze action
        (reverse("bi:warehouse_table_analyze", kwargs={"pk": warehouse_table_a.pk}), {}),
    ]

    for url, data in post_routes:
        res = anon_client.post(url, data)
        assert res.status_code == 302, f"Expected 302 redirect for anon POST {url}, got {res.status_code}"
        assert "/accounts/login" in res.url or "login" in res.url


def test_datawarehouse_security_non_admin_forbidden_on_state_changing_actions(
    member_client,
    lakehouse_zone_a,
    storage_policy_a,
    data_mart_a,
    warehouse_table_a,
):
    """Non-admin workspace members (is_tenant_admin=False) attempting state mutations return 403 Forbidden."""
    privileged_routes = [
        # Create routes (GET and POST)
        (reverse("bi:lakehouse_zone_create"), "GET", {}),
        (reverse("bi:lakehouse_zone_create"), "POST", {"name": "Unauthorized Zone"}),
        (reverse("bi:warehouse_storage_policy_create"), "GET", {}),
        (reverse("bi:warehouse_storage_policy_create"), "POST", {"name": "Unauthorized Policy"}),
        (reverse("bi:data_mart_create"), "GET", {}),
        (reverse("bi:data_mart_create"), "POST", {"name": "Unauthorized Mart"}),
        (reverse("bi:warehouse_table_create"), "GET", {}),
        (reverse("bi:warehouse_table_create"), "POST", {"name": "Unauthorized Table"}),
        # Edit routes (GET and POST)
        (reverse("bi:lakehouse_zone_edit", kwargs={"pk": lakehouse_zone_a.pk}), "GET", {}),
        (reverse("bi:lakehouse_zone_edit", kwargs={"pk": lakehouse_zone_a.pk}), "POST", {"name": "Mutated"}),
        (reverse("bi:warehouse_storage_policy_edit", kwargs={"pk": storage_policy_a.pk}), "GET", {}),
        (reverse("bi:warehouse_storage_policy_edit", kwargs={"pk": storage_policy_a.pk}), "POST", {"name": "Mutated"}),
        (reverse("bi:data_mart_edit", kwargs={"pk": data_mart_a.pk}), "GET", {}),
        (reverse("bi:data_mart_edit", kwargs={"pk": data_mart_a.pk}), "POST", {"name": "Mutated"}),
        (reverse("bi:warehouse_table_edit", kwargs={"pk": warehouse_table_a.pk}), "GET", {}),
        (reverse("bi:warehouse_table_edit", kwargs={"pk": warehouse_table_a.pk}), "POST", {"name": "Mutated"}),
        # Delete routes (POST)
        (reverse("bi:lakehouse_zone_delete", kwargs={"pk": lakehouse_zone_a.pk}), "POST", {}),
        (reverse("bi:warehouse_storage_policy_delete", kwargs={"pk": storage_policy_a.pk}), "POST", {}),
        (reverse("bi:data_mart_delete", kwargs={"pk": data_mart_a.pk}), "POST", {}),
        (reverse("bi:warehouse_table_delete", kwargs={"pk": warehouse_table_a.pk}), "POST", {}),
        # Analyze route (POST)
        (reverse("bi:warehouse_table_analyze", kwargs={"pk": warehouse_table_a.pk}), "POST", {}),
    ]

    for url, method, data in privileged_routes:
        if method == "GET":
            res = member_client.get(url)
        else:
            res = member_client.post(url, data)
        assert res.status_code == 403, (
            f"Expected 403 Forbidden for non-admin on {method} {url}, got {res.status_code}"
        )

    # Confirm objects remain unchanged in the database
    lakehouse_zone_a.refresh_from_db()
    storage_policy_a.refresh_from_db()
    data_mart_a.refresh_from_db()
    warehouse_table_a.refresh_from_db()
    assert lakehouse_zone_a.name == "Gold Marts Zone"
    assert storage_policy_a.name == "Daily Range Snappy Policy"
    assert data_mart_a.name == "Revenue Finance Mart"
    assert warehouse_table_a.name == "Daily Invoiced Revenue Fact"


def test_datawarehouse_security_non_admin_allowed_read_only_access(
    member_client,
    lakehouse_zone_a,
    storage_policy_a,
    data_mart_a,
    warehouse_table_a,
):
    """Non-admin workspace members can view list, detail, overview, and DDL preview views (HTTP 200)."""
    read_only_routes = [
        reverse("bi:warehouse_overview"),
        reverse("bi:lakehouse_zone_list"),
        reverse("bi:lakehouse_zone_detail", kwargs={"pk": lakehouse_zone_a.pk}),
        reverse("bi:warehouse_storage_policy_list"),
        reverse("bi:warehouse_storage_policy_detail", kwargs={"pk": storage_policy_a.pk}),
        reverse("bi:data_mart_list"),
        reverse("bi:data_mart_detail", kwargs={"pk": data_mart_a.pk}),
        reverse("bi:warehouse_table_list"),
        reverse("bi:warehouse_table_detail", kwargs={"pk": warehouse_table_a.pk}),
        reverse("bi:warehouse_table_ddl_preview", kwargs={"pk": warehouse_table_a.pk}),
    ]

    for url in read_only_routes:
        res = member_client.get(url)
        assert res.status_code == 200, f"Expected 200 OK for non-admin on read-only {url}, got {res.status_code}"


def test_datawarehouse_security_post_only_method_enforcement(
    client_a,
    lakehouse_zone_a,
    storage_policy_a,
    data_mart_a,
    warehouse_table_a,
):
    """GET requests to delete and analyze routes return 405 Method Not Allowed."""
    post_only_routes = [
        reverse("bi:lakehouse_zone_delete", kwargs={"pk": lakehouse_zone_a.pk}),
        reverse("bi:warehouse_storage_policy_delete", kwargs={"pk": storage_policy_a.pk}),
        reverse("bi:data_mart_delete", kwargs={"pk": data_mart_a.pk}),
        reverse("bi:warehouse_table_delete", kwargs={"pk": warehouse_table_a.pk}),
        reverse("bi:warehouse_table_analyze", kwargs={"pk": warehouse_table_a.pk}),
    ]

    for url in post_only_routes:
        res = client_a.get(url)
        assert res.status_code == 405, f"Expected 405 Method Not Allowed on GET {url}, got {res.status_code}"


# ===========================================================================
# 2. Cross-Tenant Data Isolation (IDOR) — 100% Strict 404 Assertions
# ===========================================================================


def test_datawarehouse_security_idor_lakehouse_zone_routes_strict_404(
    client_a,
    lakehouse_zone_b,
):
    """Client A cannot access or mutate Tenant B's LakehouseZone via IDOR (returns 404)."""
    # Detail: Client A -> Zone B
    assert client_a.get(reverse("bi:lakehouse_zone_detail", kwargs={"pk": lakehouse_zone_b.pk})).status_code == 404

    # Edit GET: Client A -> Zone B
    assert client_a.get(reverse("bi:lakehouse_zone_edit", kwargs={"pk": lakehouse_zone_b.pk})).status_code == 404

    # Edit POST: Client A -> Zone B
    res_a = client_a.post(
        reverse("bi:lakehouse_zone_edit", kwargs={"pk": lakehouse_zone_b.pk}),
        data={"name": "Attacked Zone"},
    )
    assert res_a.status_code == 404

    # Delete POST: Client A -> Zone B
    assert client_a.post(reverse("bi:lakehouse_zone_delete", kwargs={"pk": lakehouse_zone_b.pk})).status_code == 404

    # Confirm object exists and was not altered
    lakehouse_zone_b.refresh_from_db()
    assert lakehouse_zone_b.name == "Globex Bronze Ingestion Zone"


def test_datawarehouse_security_idor_storage_policy_routes_strict_404(
    client_a,
    storage_policy_b,
):
    """Client A cannot access or mutate Tenant B's WarehouseStoragePolicy via IDOR (returns 404)."""
    # Detail: Client A -> Policy B
    assert client_a.get(reverse("bi:warehouse_storage_policy_detail", kwargs={"pk": storage_policy_b.pk})).status_code == 404

    # Edit GET: Client A -> Policy B
    assert client_a.get(reverse("bi:warehouse_storage_policy_edit", kwargs={"pk": storage_policy_b.pk})).status_code == 404

    # Edit POST: Client A -> Policy B
    res_a = client_a.post(
        reverse("bi:warehouse_storage_policy_edit", kwargs={"pk": storage_policy_b.pk}),
        data={"name": "Attacked Policy"},
    )
    assert res_a.status_code == 404

    # Delete POST: Client A -> Policy B
    assert client_a.post(reverse("bi:warehouse_storage_policy_delete", kwargs={"pk": storage_policy_b.pk})).status_code == 404

    # Confirm object exists and was not altered
    storage_policy_b.refresh_from_db()
    assert storage_policy_b.name == "Globex Monthly Policy"


def test_datawarehouse_security_idor_data_mart_routes_strict_404(
    client_a,
    data_mart_b,
):
    """Client A cannot access or mutate Tenant B's DataMart via IDOR (returns 404)."""
    # Detail: Client A -> Mart B
    assert client_a.get(reverse("bi:data_mart_detail", kwargs={"pk": data_mart_b.pk})).status_code == 404

    # Edit GET: Client A -> Mart B
    assert client_a.get(reverse("bi:data_mart_edit", kwargs={"pk": data_mart_b.pk})).status_code == 404

    # Edit POST: Client A -> Mart B
    res_a = client_a.post(
        reverse("bi:data_mart_edit", kwargs={"pk": data_mart_b.pk}),
        data={"name": "Attacked Mart"},
    )
    assert res_a.status_code == 404

    # Delete POST: Client A -> Mart B
    assert client_a.post(reverse("bi:data_mart_delete", kwargs={"pk": data_mart_b.pk})).status_code == 404

    # Confirm object exists and was not altered
    data_mart_b.refresh_from_db()
    assert data_mart_b.name == "Globex Sales Mart"


def test_datawarehouse_security_idor_warehouse_table_routes_strict_404(
    client_a,
    warehouse_table_b,
):
    """Client A cannot access or mutate Tenant B's WarehouseTable detail, edit, delete (returns 404)."""
    # Detail: Client A -> Table B
    assert client_a.get(reverse("bi:warehouse_table_detail", kwargs={"pk": warehouse_table_b.pk})).status_code == 404

    # Edit GET: Client A -> Table B
    assert client_a.get(reverse("bi:warehouse_table_edit", kwargs={"pk": warehouse_table_b.pk})).status_code == 404

    # Edit POST: Client A -> Table B
    res_a = client_a.post(
        reverse("bi:warehouse_table_edit", kwargs={"pk": warehouse_table_b.pk}),
        data={"name": "Attacked Table"},
    )
    assert res_a.status_code == 404

    # Delete POST: Client A -> Table B
    assert client_a.post(reverse("bi:warehouse_table_delete", kwargs={"pk": warehouse_table_b.pk})).status_code == 404

    # Confirm object exists and was not altered
    warehouse_table_b.refresh_from_db()
    assert warehouse_table_b.name == "Globex Orders Fact"


def test_datawarehouse_security_idor_warehouse_table_ddl_preview_strict_404(
    client_a,
    warehouse_table_b,
):
    """Client A cannot preview Tenant B's WarehouseTable DDL (returns 404)."""
    url_b = reverse("bi:warehouse_table_ddl_preview", kwargs={"pk": warehouse_table_b.pk})
    res_a = client_a.get(url_b)
    assert res_a.status_code == 404


def test_datawarehouse_security_idor_warehouse_table_analyze_strict_404(
    client_a,
    warehouse_table_b,
):
    """Client A cannot execute analyze action on Tenant B's WarehouseTable (returns 404)."""
    initial_analyzed_b = warehouse_table_b.last_analyzed_at
    url_b = reverse("bi:warehouse_table_analyze", kwargs={"pk": warehouse_table_b.pk})
    res_a = client_a.post(url_b)
    assert res_a.status_code == 404

    # Confirm telemetry was not modified by foreign request
    warehouse_table_b.refresh_from_db()
    assert warehouse_table_b.last_analyzed_at == initial_analyzed_b


def test_datawarehouse_security_idor_reverse_tenant_b_access_denied_strict_404(
    client_b,
    lakehouse_zone_a,
    storage_policy_a,
    data_mart_a,
    warehouse_table_a,
):
    """Tenant B admin cannot access or mutate any of Tenant A's objects (100% strict 404s)."""
    routes = [
        # Lakehouse Zone A
        (reverse("bi:lakehouse_zone_detail", kwargs={"pk": lakehouse_zone_a.pk}), "GET", {}),
        (reverse("bi:lakehouse_zone_edit", kwargs={"pk": lakehouse_zone_a.pk}), "GET", {}),
        (reverse("bi:lakehouse_zone_edit", kwargs={"pk": lakehouse_zone_a.pk}), "POST", {"name": "Hacked"}),
        (reverse("bi:lakehouse_zone_delete", kwargs={"pk": lakehouse_zone_a.pk}), "POST", {}),
        # Storage Policy A
        (reverse("bi:warehouse_storage_policy_detail", kwargs={"pk": storage_policy_a.pk}), "GET", {}),
        (reverse("bi:warehouse_storage_policy_edit", kwargs={"pk": storage_policy_a.pk}), "GET", {}),
        (reverse("bi:warehouse_storage_policy_edit", kwargs={"pk": storage_policy_a.pk}), "POST", {"name": "Hacked"}),
        (reverse("bi:warehouse_storage_policy_delete", kwargs={"pk": storage_policy_a.pk}), "POST", {}),
        # Data Mart A
        (reverse("bi:data_mart_detail", kwargs={"pk": data_mart_a.pk}), "GET", {}),
        (reverse("bi:data_mart_edit", kwargs={"pk": data_mart_a.pk}), "GET", {}),
        (reverse("bi:data_mart_edit", kwargs={"pk": data_mart_a.pk}), "POST", {"name": "Hacked"}),
        (reverse("bi:data_mart_delete", kwargs={"pk": data_mart_a.pk}), "POST", {}),
        # Warehouse Table A
        (reverse("bi:warehouse_table_detail", kwargs={"pk": warehouse_table_a.pk}), "GET", {}),
        (reverse("bi:warehouse_table_edit", kwargs={"pk": warehouse_table_a.pk}), "GET", {}),
        (reverse("bi:warehouse_table_edit", kwargs={"pk": warehouse_table_a.pk}), "POST", {"name": "Hacked"}),
        (reverse("bi:warehouse_table_delete", kwargs={"pk": warehouse_table_a.pk}), "POST", {}),
        (reverse("bi:warehouse_table_ddl_preview", kwargs={"pk": warehouse_table_a.pk}), "GET", {}),
        (reverse("bi:warehouse_table_analyze", kwargs={"pk": warehouse_table_a.pk}), "POST", {}),
    ]

    for url, method, data in routes:
        if method == "GET":
            res = client_b.get(url)
        else:
            res = client_b.post(url, data)
        assert res.status_code == 404, f"Tenant B accessed Tenant A via {method} {url} (expected 404, got {res.status_code})"

    # Confirm Tenant A objects remain untouched
    lakehouse_zone_a.refresh_from_db()
    storage_policy_a.refresh_from_db()
    data_mart_a.refresh_from_db()
    warehouse_table_a.refresh_from_db()
    assert lakehouse_zone_a.name == "Gold Marts Zone"
    assert storage_policy_a.name == "Daily Range Snappy Policy"
    assert data_mart_a.name == "Revenue Finance Mart"
    assert warehouse_table_a.name == "Daily Invoiced Revenue Fact"


def test_datawarehouse_security_data_leakage_in_lists_and_exports_prevented(
    client_a,
    lakehouse_zone_a,
    lakehouse_zone_b,
    storage_policy_a,
    storage_policy_b,
    data_mart_a,
    data_mart_b,
    warehouse_table_a,
    warehouse_table_b,
):
    """Verify list views and CSV exports strictly isolate tenant data and prevent cross-tenant leakage."""
    # 1. Lakehouse Zones List & CSV
    res_zone_a = client_a.get(reverse("bi:lakehouse_zone_list"))
    content_a = res_zone_a.content.decode("utf-8")
    assert lakehouse_zone_a.name in content_a
    assert lakehouse_zone_b.name not in content_a

    csv_zone_a = client_a.get(reverse("bi:lakehouse_zone_list") + "?export=csv")
    csv_text_zone_a = csv_zone_a.content.decode("utf-8")
    assert lakehouse_zone_a.name in csv_text_zone_a
    assert lakehouse_zone_b.name not in csv_text_zone_a

    # 2. Storage Policies List & CSV
    res_policy_a = client_a.get(reverse("bi:warehouse_storage_policy_list"))
    content_policy_a = res_policy_a.content.decode("utf-8")
    assert storage_policy_a.name in content_policy_a
    assert storage_policy_b.name not in content_policy_a

    csv_policy_a = client_a.get(reverse("bi:warehouse_storage_policy_list") + "?export=csv")
    csv_text_policy_a = csv_policy_a.content.decode("utf-8")
    assert storage_policy_a.name in csv_text_policy_a
    assert storage_policy_b.name not in csv_text_policy_a

    # 3. Data Marts List & CSV
    res_mart_a = client_a.get(reverse("bi:data_mart_list"))
    content_mart_a = res_mart_a.content.decode("utf-8")
    assert data_mart_a.name in content_mart_a
    assert data_mart_b.name not in content_mart_a

    csv_mart_a = client_a.get(reverse("bi:data_mart_list") + "?export=csv")
    csv_text_mart_a = csv_mart_a.content.decode("utf-8")
    assert data_mart_a.name in csv_text_mart_a
    assert data_mart_b.name not in csv_text_mart_a

    # 4. Warehouse Tables List & CSV
    res_table_a = client_a.get(reverse("bi:warehouse_table_list"))
    content_table_a = res_table_a.content.decode("utf-8")
    assert warehouse_table_a.name in content_table_a
    assert warehouse_table_b.name not in content_table_a

    csv_table_a = client_a.get(reverse("bi:warehouse_table_list") + "?export=csv")
    csv_text_table_a = csv_table_a.content.decode("utf-8")
    assert warehouse_table_a.name in csv_text_table_a
    assert warehouse_table_b.name not in csv_text_table_a

    # 5. Warehouse Overview context
    res_overview = client_a.get(reverse("bi:warehouse_overview"))
    overview_text = res_overview.content.decode("utf-8")
    assert warehouse_table_a.name in overview_text
    assert warehouse_table_b.name not in overview_text


def test_datawarehouse_security_data_leakage_reverse_tenant_b_list_isolation(
    client_b,
    lakehouse_zone_a,
    storage_policy_a,
    data_mart_a,
    warehouse_table_a,
):
    """Verify Tenant B lists and exports never leak any of Tenant A's objects."""
    routes = [
        reverse("bi:warehouse_overview"),
        reverse("bi:lakehouse_zone_list"),
        reverse("bi:lakehouse_zone_list") + "?export=csv",
        reverse("bi:warehouse_storage_policy_list"),
        reverse("bi:warehouse_storage_policy_list") + "?export=csv",
        reverse("bi:data_mart_list"),
        reverse("bi:data_mart_list") + "?export=csv",
        reverse("bi:warehouse_table_list"),
        reverse("bi:warehouse_table_list") + "?export=csv",
    ]

    for url in routes:
        res = client_b.get(url)
        assert res.status_code == 200
        text = res.content.decode("utf-8")
        assert lakehouse_zone_a.name not in text
        assert storage_policy_a.name not in text
        assert data_mart_a.name not in text
        assert warehouse_table_a.name not in text


# ===========================================================================
# 3. Cross-Tenant FK Injection & Validation in Forms
# ===========================================================================


def test_datawarehouse_security_fk_injection_datamart_form_clean_rejects_foreign_relations(
    tenant_a,
    tenant_b,
    admin_user_b,
):
    """DataMartForm clean() and scoped querysets reject foreign org_unit, owner, and steward."""
    foreign_ou = _datawarehouse_create_org_unit(tenant_b, "Globex Engineering")

    base_payload = {
        "name": "Acme Marketing Mart",
        "code": "acme_marketing",
        "subject_area": "marketing",
        "access_tier": "department",
        "certification_status": "draft",
        "refresh_cadence": "weekly",
        "is_active": True,
    }

    # 1. Scoped queryset rejects at field level
    form_scoped = DataMartForm(
        data={**base_payload, "org_unit": foreign_ou.pk, "owner": admin_user_b.pk, "steward": admin_user_b.pk},
        tenant=tenant_a,
    )
    assert not form_scoped.is_valid()
    assert "org_unit" in form_scoped.errors
    assert "owner" in form_scoped.errors
    assert "steward" in form_scoped.errors

    # 2. Defense-in-depth: clean() reject_foreign rejects even when querysets are widened
    form_wide = DataMartForm(
        data={**base_payload, "org_unit": foreign_ou.pk, "owner": admin_user_b.pk, "steward": admin_user_b.pk},
        tenant=tenant_a,
    )
    form_wide.fields["org_unit"].queryset = OrgUnit.objects.all()
    form_wide.fields["owner"].queryset = User.objects.all()
    form_wide.fields["steward"].queryset = User.objects.all()

    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors.get("org_unit", [])
    assert "That record belongs to another workspace." in form_wide.errors.get("owner", [])
    assert "That record belongs to another workspace." in form_wide.errors.get("steward", [])


def test_datawarehouse_security_fk_injection_warehousetable_form_clean_rejects_foreign_relations(
    tenant_a,
    tenant_b,
    lakehouse_zone_b,
    storage_policy_b,
    data_mart_b,
):
    """WarehouseTableForm clean() and scoped querysets reject foreign lakehouse_zone, data_mart, storage_policy."""
    base_payload = {
        "name": "Injected Foreign FK Table",
        "table_name": "fact_foreign_injected",
        "table_type": "fact",
        "schema_type": "star",
        "grain": "transaction",
        "primary_key_column": "id",
        "is_active": True,
        "lakehouse_zone": lakehouse_zone_b.pk,
        "data_mart": data_mart_b.pk,
        "storage_policy": storage_policy_b.pk,
    }

    # 1. Scoped queryset rejects at field level
    form_scoped = WarehouseTableForm(data=base_payload, tenant=tenant_a)
    assert not form_scoped.is_valid()
    assert "lakehouse_zone" in form_scoped.errors
    assert "data_mart" in form_scoped.errors
    assert "storage_policy" in form_scoped.errors

    # 2. Defense-in-depth: clean() reject_foreign rejects even when querysets are widened
    form_wide = WarehouseTableForm(data=base_payload, tenant=tenant_a)
    form_wide.fields["lakehouse_zone"].queryset = LakehouseZone.objects.all()
    form_wide.fields["data_mart"].queryset = DataMart.objects.all()
    form_wide.fields["storage_policy"].queryset = WarehouseStoragePolicy.objects.all()

    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors.get("lakehouse_zone", [])
    assert "That record belongs to another workspace." in form_wide.errors.get("data_mart", [])
    assert "That record belongs to another workspace." in form_wide.errors.get("storage_policy", [])


def test_datawarehouse_security_post_injection_foreign_fk_rejected_via_http(
    client_a,
    tenant_b,
    lakehouse_zone_b,
    storage_policy_b,
    data_mart_b,
    admin_user_b,
):
    """HTTP POST attempting to inject foreign tenant FKs is rejected and does not persist rows."""
    foreign_ou = _datawarehouse_create_org_unit(tenant_b, "Globex R&D")

    # 1. DataMart POST injection
    mart_payload = {
        "name": "Hostile Injected Mart",
        "code": "hostile_injected_mart",
        "subject_area": "finance",
        "access_tier": "department",
        "certification_status": "draft",
        "refresh_cadence": "daily",
        "org_unit": foreign_ou.pk,
        "owner": admin_user_b.pk,
        "steward": admin_user_b.pk,
        "is_active": "on",
    }
    res_mart = client_a.post(reverse("bi:data_mart_create"), data=mart_payload)
    assert res_mart.status_code == 200  # Re-renders form with error
    assert not DataMart.objects.filter(code="hostile_injected_mart").exists()

    # 2. WarehouseTable POST injection
    table_payload = {
        "name": "Hostile Injected Table",
        "table_name": "fact_hostile_injected",
        "table_type": "fact",
        "schema_type": "star",
        "grain": "transaction",
        "lakehouse_zone": lakehouse_zone_b.pk,
        "data_mart": data_mart_b.pk,
        "storage_policy": storage_policy_b.pk,
        "primary_key_column": "id",
        "is_active": "on",
    }
    res_table = client_a.post(reverse("bi:warehouse_table_create"), data=table_payload)
    assert res_table.status_code == 200  # Re-renders form with error
    assert not WarehouseTable.objects.filter(table_name="fact_hostile_injected").exists()


# ===========================================================================
# 4. Mass Assignment Hardening
# ===========================================================================


def test_datawarehouse_security_mass_assignment_table_create_ignores_system_fields(
    client_a,
    tenant_a,
    tenant_b,
    lakehouse_zone_a,
):
    """Submitting tenant and telemetry system fields during table creation does not overwrite values."""
    payload = {
        "name": "Safe Ledger Fact",
        "table_name": "fact_safe_ledger",
        "table_type": "fact",
        "schema_type": "star",
        "grain": "transaction",
        "lakehouse_zone": lakehouse_zone_a.pk,
        "primary_key_column": "id",
        "is_active": "on",
        # Malicious mass-assignment payload
        "tenant": tenant_b.pk,
        "tenant_id": tenant_b.pk,
        "number": "BDWT-99999",
        "row_count": 99999999,
        "compressed_bytes": 88888888,
        "compression_ratio": "99.99",
        "last_analyzed_at": "2030-01-01T00:00:00Z",
    }

    res = client_a.post(reverse("bi:warehouse_table_create"), data=payload)
    assert res.status_code == 302

    created = WarehouseTable.objects.get(table_name="fact_safe_ledger")
    # Must belong to tenant_a
    assert created.tenant == tenant_a
    # Number prefix generated deterministically, not overridden to BDWT-99999
    assert created.number != "BDWT-99999"
    assert created.number.startswith("BDWT-")
    # System fields remain at defaults
    assert created.row_count == 0
    assert created.compressed_bytes == 0
    assert created.compression_ratio == Decimal("1.00")
    assert created.last_analyzed_at is None


def test_datawarehouse_security_mass_assignment_table_edit_ignores_system_fields(
    client_a,
    tenant_a,
    tenant_b,
    warehouse_table_a,
    lakehouse_zone_a,
):
    """Submitting tenant and telemetry system fields during table edit does not overwrite values."""
    orig_number = warehouse_table_a.number
    orig_rows = warehouse_table_a.row_count
    orig_bytes = warehouse_table_a.compressed_bytes
    orig_ratio = warehouse_table_a.compression_ratio
    orig_analyzed = warehouse_table_a.last_analyzed_at

    payload = {
        "name": "Updated Table Name",
        "table_name": warehouse_table_a.table_name,
        "table_type": warehouse_table_a.table_type,
        "schema_type": warehouse_table_a.schema_type,
        "grain": warehouse_table_a.grain,
        "lakehouse_zone": lakehouse_zone_a.pk,
        "primary_key_column": "id",
        "is_active": "on",
        # Tampered system values
        "tenant": tenant_b.pk,
        "tenant_id": tenant_b.pk,
        "number": "BDWT-TAMPERED",
        "row_count": 77777777,
        "compressed_bytes": 66666666,
        "compression_ratio": "55.55",
        "last_analyzed_at": "2035-12-31T23:59:59Z",
    }

    res = client_a.post(
        reverse("bi:warehouse_table_edit", kwargs={"pk": warehouse_table_a.pk}),
        data=payload,
    )
    assert res.status_code == 302

    warehouse_table_a.refresh_from_db()
    assert warehouse_table_a.name == "Updated Table Name"
    assert warehouse_table_a.tenant == tenant_a
    assert warehouse_table_a.number == orig_number
    assert warehouse_table_a.row_count == orig_rows
    assert warehouse_table_a.compressed_bytes == orig_bytes
    assert warehouse_table_a.compression_ratio == orig_ratio
    assert warehouse_table_a.last_analyzed_at == orig_analyzed


def test_datawarehouse_security_mass_assignment_lakehouse_zone_and_data_mart_hardening(
    client_a,
    tenant_a,
    tenant_b,
):
    """Submitting tenant or number on LakehouseZone and DataMart ignores mass assignment injection."""
    # 1. LakehouseZone
    zone_payload = {
        "name": "Hardened Zone",
        "code": "hardened_zone",
        "zone_type": "silver",
        "storage_backend": "internal_db",
        "base_uri_path": "/warehouse/hardened",
        "default_format": "relational_table",
        "is_active": "on",
        "tenant": tenant_b.pk,
        "number": "BLHZ-99999",
    }
    res_zone = client_a.post(reverse("bi:lakehouse_zone_create"), data=zone_payload)
    assert res_zone.status_code == 302
    created_zone = LakehouseZone.objects.get(code="hardened_zone")
    assert created_zone.tenant == tenant_a
    assert created_zone.number != "BLHZ-99999"
    assert created_zone.number.startswith("BLHZ-")

    # 2. DataMart
    mart_payload = {
        "name": "Hardened Mart",
        "code": "hardened_mart",
        "subject_area": "sales",
        "access_tier": "department",
        "certification_status": "draft",
        "refresh_cadence": "daily",
        "is_active": "on",
        "tenant": tenant_b.pk,
        "number": "BDMT-99999",
    }
    res_mart = client_a.post(reverse("bi:data_mart_create"), data=mart_payload)
    assert res_mart.status_code == 302
    created_mart = DataMart.objects.get(code="hardened_mart")
    assert created_mart.tenant == tenant_a
    assert created_mart.number != "BDMT-99999"
    assert created_mart.number.startswith("BDMT-")


# ===========================================================================
# 5. Audit Trail Verification
# ===========================================================================


def test_datawarehouse_security_audit_lakehouse_zone_protected_error_no_phantom_delete_log(
    client_a,
    tenant_a,
    admin_user,
    lakehouse_zone_a,
    warehouse_table_a,
):
    """LakehouseZone deletion blocked by ProtectedError rolls back and emits NO phantom delete AuditLog."""
    # Ensure warehouse_table_a references lakehouse_zone_a
    assert warehouse_table_a.lakehouse_zone == lakehouse_zone_a

    delete_url = reverse("bi:lakehouse_zone_delete", kwargs={"pk": lakehouse_zone_a.pk})
    res = client_a.post(delete_url)
    assert res.status_code == 302
    assert res.url == reverse("bi:lakehouse_zone_detail", kwargs={"pk": lakehouse_zone_a.pk})

    # Zone still exists
    assert LakehouseZone.objects.filter(pk=lakehouse_zone_a.pk).exists()

    # Verify NO delete audit log exists for this zone
    phantom_logs = AuditLog.objects.filter(
        tenant=tenant_a,
        action="delete",
        object_id=lakehouse_zone_a.pk,
    )
    assert not phantom_logs.exists()


def test_datawarehouse_security_audit_trail_recorded_on_table_lifecycle(
    client_a,
    tenant_a,
    admin_user,
    lakehouse_zone_a,
):
    """Successful table create, update, analyze, and delete actions record proper AuditLog entries."""
    # 1. Create table
    create_payload = {
        "name": "Audit Tracked Table",
        "table_name": "fact_audit_tracked",
        "table_type": "fact",
        "schema_type": "star",
        "grain": "transaction",
        "lakehouse_zone": lakehouse_zone_a.pk,
        "primary_key_column": "id",
        "is_active": "on",
    }
    res_create = client_a.post(reverse("bi:warehouse_table_create"), data=create_payload)
    assert res_create.status_code == 302
    tbl = WarehouseTable.objects.get(table_name="fact_audit_tracked")

    create_log = AuditLog.objects.filter(
        tenant=tenant_a,
        object_id=tbl.pk,
        action="create",
    ).first()
    assert create_log is not None
    assert create_log.user == admin_user

    # 2. Edit table
    edit_payload = {
        "name": "Audit Tracked Table Renamed",
        "table_name": tbl.table_name,
        "table_type": tbl.table_type,
        "schema_type": tbl.schema_type,
        "grain": tbl.grain,
        "lakehouse_zone": lakehouse_zone_a.pk,
        "primary_key_column": "id",
        "is_active": "on",
    }
    res_edit = client_a.post(reverse("bi:warehouse_table_edit", kwargs={"pk": tbl.pk}), data=edit_payload)
    assert res_edit.status_code == 302

    update_log = AuditLog.objects.filter(
        tenant=tenant_a,
        object_id=tbl.pk,
        action="update",
    ).first()
    assert update_log is not None
    assert update_log.user == admin_user

    # 3. Analyze table
    res_analyze = client_a.post(reverse("bi:warehouse_table_analyze", kwargs={"pk": tbl.pk}))
    assert res_analyze.status_code == 302

    analyze_log = AuditLog.objects.filter(
        tenant=tenant_a,
        object_id=tbl.pk,
        action="analyze",
    ).first()
    assert analyze_log is not None
    assert analyze_log.user == admin_user

    # 4. Delete table
    tbl_pk = tbl.pk
    res_delete = client_a.post(reverse("bi:warehouse_table_delete", kwargs={"pk": tbl_pk}))
    assert res_delete.status_code == 302
    assert not WarehouseTable.objects.filter(pk=tbl_pk).exists()

    delete_log = AuditLog.objects.filter(
        tenant=tenant_a,
        object_id=tbl_pk,
        action="delete",
    ).first()
    assert delete_log is not None
    assert delete_log.user == admin_user


def test_datawarehouse_security_audit_trail_recorded_on_lakehouse_zone_policy_mart(
    client_a,
    tenant_a,
    admin_user,
):
    """LakehouseZone, DataMart, and WarehouseStoragePolicy CRUD actions emit AuditLog rows."""
    # 1. Unreferenced LakehouseZone
    zone = _datawarehouse_create_unreferenced_zone(tenant_a, "Zone for Audit", "audit_zone")
    res_edit_zone = client_a.post(
        reverse("bi:lakehouse_zone_edit", kwargs={"pk": zone.pk}),
        data={
            "name": "Zone for Audit Updated",
            "code": zone.code,
            "zone_type": zone.zone_type,
            "storage_backend": zone.storage_backend,
            "base_uri_path": zone.base_uri_path,
            "default_format": zone.default_format,
            "is_active": "on",
        },
    )
    assert res_edit_zone.status_code == 302
    assert AuditLog.objects.filter(tenant=tenant_a, object_id=zone.pk, action="update").exists()

    zone_pk = zone.pk
    res_del_zone = client_a.post(reverse("bi:lakehouse_zone_delete", kwargs={"pk": zone_pk}))
    assert res_del_zone.status_code == 302
    assert AuditLog.objects.filter(tenant=tenant_a, object_id=zone_pk, action="delete").exists()

    # 2. Unreferenced DataMart
    mart = _datawarehouse_create_unreferenced_mart(tenant_a, "Mart for Audit", "audit_mart")
    res_edit_mart = client_a.post(
        reverse("bi:data_mart_edit", kwargs={"pk": mart.pk}),
        data={
            "name": "Mart for Audit Updated",
            "code": mart.code,
            "subject_area": mart.subject_area,
            "access_tier": mart.access_tier,
            "certification_status": "draft",
            "refresh_cadence": "daily",
            "is_active": "on",
        },
    )
    assert res_edit_mart.status_code == 302
    assert AuditLog.objects.filter(tenant=tenant_a, object_id=mart.pk, action="update").exists()

    mart_pk = mart.pk
    res_del_mart = client_a.post(reverse("bi:data_mart_delete", kwargs={"pk": mart_pk}))
    assert res_del_mart.status_code == 302
    assert AuditLog.objects.filter(tenant=tenant_a, object_id=mart_pk, action="delete").exists()

    # 3. Unreferenced WarehouseStoragePolicy
    policy = _datawarehouse_create_unreferenced_policy(tenant_a, "Policy for Audit")
    res_edit_policy = client_a.post(
        reverse("bi:warehouse_storage_policy_edit", kwargs={"pk": policy.pk}),
        data={
            "name": "Policy for Audit Updated",
            "partition_strategy": "range_time",
            "partition_key": "posting_date",
            "partition_granularity": "month",
            "compression_codec": "zstd",
            "vacuum_cadence": "weekly",
            "hot_tier_days": 90,
            "warm_tier_days": 365,
            "cold_tier_days": 2555,
            "time_travel_days": 7,
            "is_active": "on",
        },
    )
    assert res_edit_policy.status_code == 302
    assert AuditLog.objects.filter(tenant=tenant_a, object_id=policy.pk, action="update").exists()

    policy_pk = policy.pk
    res_del_policy = client_a.post(reverse("bi:warehouse_storage_policy_delete", kwargs={"pk": policy_pk}))
    assert res_del_policy.status_code == 302
    assert AuditLog.objects.filter(tenant=tenant_a, object_id=policy_pk, action="delete").exists()


# ===========================================================================
# 6. SQL Injection Prevention & Identifier Sanitization
# ===========================================================================


def test_datawarehouse_security_sql_injection_table_name_rejected_by_form(
    tenant_a,
    lakehouse_zone_a,
):
    """WarehouseTableForm clean_table_name strictly rejects SQL injection payloads."""
    malicious_table_names = [
        "fact_orders; DROP TABLE bi_warehouse_table;--",
        "orders' OR '1'='1",
        'orders" OR ""="',
        "fact_orders; DELETE FROM auth_user;",
        "1starts_with_digit",
        "has spaces in identifier",
        "fact-dashes-not-allowed",
        "fact$dollar",
        "fact_orders/*inline comment*/",
        "a" * 64,  # Exceeds max 63 characters
    ]

    base_data = {
        "name": "SQL Injection Test",
        "table_type": "fact",
        "schema_type": "star",
        "grain": "transaction",
        "lakehouse_zone": lakehouse_zone_a.pk,
        "primary_key_column": "id",
        "is_active": True,
    }

    for bad_name in malicious_table_names:
        form = WarehouseTableForm(data={**base_data, "table_name": bad_name}, tenant=tenant_a)
        assert not form.is_valid(), f"Expected validation error for SQL injection payload in table_name: {bad_name}"
        assert "table_name" in form.errors


def test_datawarehouse_security_sql_injection_primary_key_column_rejected_by_form(
    tenant_a,
    lakehouse_zone_a,
):
    """WarehouseTableForm clean_primary_key_column strictly rejects SQL injection payloads."""
    malicious_pk_cols = [
        'col_name" OR 1=1--',
        "id; DROP TABLE users--",
        "id' OR '1'='1",
        "1digit_first",
        "id with space",
        "id; SELECT 1;",
        "id, another_col",
        "id/*comment*/",
    ]

    base_data = {
        "name": "SQL Injection PK Test",
        "table_name": "fact_pk_test",
        "table_type": "fact",
        "schema_type": "star",
        "grain": "transaction",
        "lakehouse_zone": lakehouse_zone_a.pk,
        "is_active": True,
    }

    for bad_pk in malicious_pk_cols:
        form = WarehouseTableForm(data={**base_data, "primary_key_column": bad_pk}, tenant=tenant_a)
        assert not form.is_valid(), f"Expected validation error for SQL injection payload in primary_key_column: {bad_pk}"
        assert "primary_key_column" in form.errors


def test_datawarehouse_security_sql_injection_schema_definition_column_name_rejected(
    tenant_a,
    lakehouse_zone_a,
):
    """WarehouseTableForm clean_schema_definition_raw rejects injection payloads in column names."""
    malicious_column_names = [
        'col_name" OR 1=1--',
        "col; DROP TABLE users--",
        "col' OR '1'='1",
        "1bad_col",
        "col with spaces",
        "col, second_col",
    ]

    base_data = {
        "name": "Schema Injection Column Test",
        "table_name": "fact_schema_col_test",
        "table_type": "fact",
        "schema_type": "star",
        "grain": "transaction",
        "lakehouse_zone": lakehouse_zone_a.pk,
        "primary_key_column": "id",
        "is_active": True,
    }

    for bad_col in malicious_column_names:
        schema_json = json.dumps([{"name": bad_col, "type": "INTEGER", "nullable": False}])
        form = WarehouseTableForm(data={**base_data, "schema_definition_raw": schema_json}, tenant=tenant_a)
        assert not form.is_valid(), f"Expected schema validation error for malicious column name: {bad_col}"
        assert "schema_definition_raw" in form.errors


def test_datawarehouse_security_sql_injection_schema_definition_sql_type_rejected(
    tenant_a,
    lakehouse_zone_a,
):
    """WarehouseTableForm clean_schema_definition_raw rejects unwhitelisted/injected SQL types."""
    malicious_types = [
        "INTEGER; DROP TABLE users--",
        "VARCHAR(100); SHUTDOWN;--",
        "UNION SELECT 1",
        "UNKNOWN_TYPE",
        "EXEC xp_cmdshell('dir')",
        "INTEGER/**/AND/**/1=1",
    ]

    base_data = {
        "name": "Schema Injection Type Test",
        "table_name": "fact_schema_type_test",
        "table_type": "fact",
        "schema_type": "star",
        "grain": "transaction",
        "lakehouse_zone": lakehouse_zone_a.pk,
        "primary_key_column": "id",
        "is_active": True,
    }

    for bad_type in malicious_types:
        schema_json = json.dumps([{"name": "test_col", "type": bad_type, "nullable": True}])
        form = WarehouseTableForm(data={**base_data, "schema_definition_raw": schema_json}, tenant=tenant_a)
        assert not form.is_valid(), f"Expected schema validation error for malicious column type: {bad_type}"
        assert "schema_definition_raw" in form.errors


def test_datawarehouse_security_sql_injection_http_post_fails_and_no_record_created(
    client_a,
    lakehouse_zone_a,
):
    """HTTP POST with SQL injection in table_name fails form validation and creates no database record."""
    injected_table_name = "fact_orders; DROP TABLE bi_warehouse_table;--"
    payload = {
        "name": "Hostile SQL Injection Table",
        "table_name": injected_table_name,
        "table_type": "fact",
        "schema_type": "star",
        "grain": "transaction",
        "lakehouse_zone": lakehouse_zone_a.pk,
        "primary_key_column": "id",
        "is_active": "on",
    }

    res = client_a.post(reverse("bi:warehouse_table_create"), data=payload)
    # Re-renders form template (200 OK) with validation errors
    assert res.status_code == 200
    assert not WarehouseTable.objects.filter(table_name=injected_table_name).exists()
    assert not WarehouseTable.objects.filter(name="Hostile SQL Injection Table").exists()
