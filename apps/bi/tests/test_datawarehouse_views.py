"""View test suite for Sub-module 10.3 (Data Warehouse & Storage).

Covers all routes under apps/bi for Sub-module 10.3:
1. Warehouse Overview:
   - bi:warehouse_overview (HTTP 200, context metrics, empty tenant, unauthenticated redirect)
2. DataMart views:
   - bi:data_mart_list (HTTP 200, context, search, filters, CSV export, pagination & fallback)
   - bi:data_mart_create (GET 200, POST valid 302 + AuditLog, POST invalid 200)
   - bi:data_mart_detail (GET 200, 404 for non-existent pk)
   - bi:data_mart_edit (GET 200, POST valid 302 + AuditLog)
   - bi:data_mart_delete (POST 302 + AuditLog, GET 405 Method Not Allowed)
3. LakehouseZone views:
   - bi:lakehouse_zone_list (HTTP 200, context, filters, CSV export)
   - bi:lakehouse_zone_create (GET 200, POST valid 302 + AuditLog)
   - bi:lakehouse_zone_detail (GET 200, tables context)
   - bi:lakehouse_zone_edit (GET 200, POST valid 302 + AuditLog)
   - bi:lakehouse_zone_delete (POST 302 unreferenced, POST protected handling with tables, GET 405)
4. WarehouseStoragePolicy views:
   - bi:warehouse_storage_policy_list (HTTP 200, context, filters, CSV export)
   - bi:warehouse_storage_policy_create (GET 200, POST valid 302 + AuditLog, is_default exclusivity)
   - bi:warehouse_storage_policy_detail (GET 200, tables context)
   - bi:warehouse_storage_policy_edit (GET 200, POST valid 302 + AuditLog)
   - bi:warehouse_storage_policy_delete (POST 302 + AuditLog, GET 405)
5. WarehouseTable views:
   - bi:warehouse_table_list (HTTP 200, context, filters, CSV export)
   - bi:warehouse_table_create (GET 200 prefill, POST valid 302 + AuditLog)
   - bi:warehouse_table_detail (GET 200, ddl_sql)
   - bi:warehouse_table_edit (GET 200, POST valid 302 + AuditLog)
   - bi:warehouse_table_ddl_preview (GET 200, ddl_sql)
   - bi:warehouse_table_analyze (POST 302 telemetry update + AuditLog, GET 405)
   - bi:warehouse_table_delete (POST 302 + AuditLog, GET 405)
6. Tenant Isolation / IDOR cross-tenant access assertions
"""
import json
from decimal import Decimal

import pytest
from django.urls import reverse

from apps.bi.models import (
    DataMart,
    LakehouseZone,
    WarehouseStoragePolicy,
    WarehouseTable,
)
from apps.core.models import AuditLog


# ---------------------------------------------------------------------------
# Module-level test helpers
# ---------------------------------------------------------------------------


def _datawarehouse_create_extra_mart(tenant, name="Auxiliary Mart", code="aux_mart", **kwargs):
    """Helper to create a DataMart with defaults."""
    defaults = {
        "tenant": tenant,
        "name": name,
        "code": code,
        "subject_area": "sales",
        "access_tier": "department",
        "certification_status": "draft",
        "refresh_cadence": "daily",
        "is_active": True,
    }
    defaults.update(kwargs)
    return DataMart.objects.create(**defaults)


def _datawarehouse_create_extra_zone(tenant, name="Auxiliary Zone", code="aux_zone", **kwargs):
    """Helper to create a LakehouseZone with defaults."""
    defaults = {
        "tenant": tenant,
        "name": name,
        "code": code,
        "zone_type": "silver",
        "storage_backend": "internal_db",
        "base_uri_path": "/warehouse/aux",
        "default_format": "relational_table",
        "is_active": True,
    }
    defaults.update(kwargs)
    return LakehouseZone.objects.create(**defaults)


def _datawarehouse_create_extra_policy(tenant, name="Auxiliary Policy", **kwargs):
    """Helper to create a WarehouseStoragePolicy with defaults."""
    defaults = {
        "tenant": tenant,
        "name": name,
        "partition_strategy": "range_time",
        "partition_key": "created_at",
        "partition_granularity": "month",
        "compression_codec": "zstd",
        "vacuum_cadence": "weekly",
        "hot_tier_days": 30,
        "warm_tier_days": 90,
        "cold_tier_days": 365,
        "time_travel_days": 14,
        "is_active": True,
    }
    defaults.update(kwargs)
    return WarehouseStoragePolicy.objects.create(**defaults)


def _datawarehouse_create_extra_table(
    tenant, zone, policy, mart, name="Auxiliary Table", table_name="dim_aux_table", **kwargs
):
    """Helper to create a WarehouseTable with defaults."""
    defaults = {
        "tenant": tenant,
        "lakehouse_zone": zone,
        "storage_policy": policy,
        "data_mart": mart,
        "name": name,
        "table_name": table_name,
        "table_type": "dimension",
        "schema_type": "star",
        "grain": "type_1_dimension",
        "primary_key_column": "id",
        "schema_definition": [
            {"name": "id", "type": "INTEGER", "nullable": False},
            {"name": "code", "type": "VARCHAR(50)", "nullable": False},
        ],
        "row_count": 500,
        "compressed_bytes": 10240,
        "compression_ratio": Decimal("1.50"),
        "is_conformed_dimension": False,
        "is_active": True,
    }
    defaults.update(kwargs)
    return WarehouseTable.objects.create(**defaults)


# ===========================================================================
# 1. Warehouse Overview View Tests
# ===========================================================================


@pytest.mark.django_db
def test_datawarehouse_views_overview_unauthenticated_redirects_to_login(anon_client):
    """Verify unauthenticated requests redirect to the login page."""
    url = reverse("bi:warehouse_overview")
    resp = anon_client.get(url)
    assert resp.status_code == 302
    assert "/accounts/login/" in resp.url or "login" in resp.url


@pytest.mark.django_db
def test_datawarehouse_views_overview_renders_200_and_context_metrics(
    auth_client, warehouse_table_a, data_mart_a, lakehouse_zone_a, storage_policy_a
):
    """Verify bi:warehouse_overview returns HTTP 200 with all expected dashboard metric keys."""
    url = reverse("bi:warehouse_overview")
    resp = auth_client.get(url)

    assert resp.status_code == 200
    expected_keys = [
        "total_tables",
        "total_rows",
        "total_compressed_bytes",
        "total_marts",
        "certified_marts",
        "total_zones",
        "total_policies",
        "fact_count",
        "dim_count",
        "recent_tables",
        "marts",
        "zones",
    ]
    for key in expected_keys:
        assert key in resp.context, f"Context key '{key}' missing from warehouse_overview"

    assert resp.context["total_tables"] >= 1
    assert resp.context["fact_count"] >= 1
    assert resp.context["total_rows"] >= 100000
    assert resp.context["total_compressed_bytes"] >= 10485760
    assert resp.context["total_marts"] >= 1
    assert resp.context["certified_marts"] >= 1
    assert resp.context["total_zones"] >= 1
    assert resp.context["total_policies"] >= 1
    assert warehouse_table_a in resp.context["recent_tables"]


@pytest.mark.django_db
def test_datawarehouse_views_overview_empty_tenant(client_b, tenant_b):
    """Verify warehouse overview renders gracefully with 0 metrics when tenant has no records."""
    # Ensure tenant_b has zero records by removing any existing ones
    WarehouseTable.objects.filter(tenant=tenant_b).delete()
    DataMart.objects.filter(tenant=tenant_b).delete()
    LakehouseZone.objects.filter(tenant=tenant_b).delete()
    WarehouseStoragePolicy.objects.filter(tenant=tenant_b).delete()

    url = reverse("bi:warehouse_overview")
    resp = client_b.get(url)

    assert resp.status_code == 200
    assert resp.context["total_tables"] == 0
    assert resp.context["total_rows"] == 0
    assert resp.context["total_compressed_bytes"] == 0
    assert resp.context["total_marts"] == 0
    assert resp.context["total_zones"] == 0
    assert resp.context["total_policies"] == 0


# ===========================================================================
# 2. DataMart View Tests
# ===========================================================================


@pytest.mark.django_db
def test_datawarehouse_views_datamart_list_renders_200_and_context(auth_client, data_mart_a):
    """Verify bi:data_mart_list returns HTTP 200 and all filter/stats context keys."""
    url = reverse("bi:data_mart_list")
    resp = auth_client.get(url)

    assert resp.status_code == 200
    expected_keys = [
        "page_obj",
        "data_marts",
        "subject_area_choices",
        "certification_status_choices",
        "access_tier_choices",
        "active_choices",
        "total_count",
        "certified_count",
        "draft_count",
        "search_query",
    ]
    for key in expected_keys:
        assert key in resp.context, f"Context key '{key}' missing from data_mart_list"

    assert data_mart_a in resp.context["data_marts"]
    assert resp.context["total_count"] >= 1


@pytest.mark.django_db
def test_datawarehouse_views_datamart_list_search(auth_client, tenant_a, data_mart_a):
    """Verify search filter ?q= matches name, code, or description."""
    mart_b = _datawarehouse_create_extra_mart(
        tenant_a,
        name="Customer 360 Analytics",
        code="customer_360",
        description="Comprehensive customer lifetime value",
    )
    url = reverse("bi:data_mart_list")

    # Match mart_b
    resp = auth_client.get(f"{url}?q=Customer 360")
    assert resp.status_code == 200
    listed_ids = [m.id for m in resp.context["data_marts"]]
    assert mart_b.id in listed_ids
    assert data_mart_a.id not in listed_ids

    # Non-existent search
    resp_empty = auth_client.get(f"{url}?q=NonExistentQueryXYZ")
    assert resp_empty.status_code == 200
    assert len(resp_empty.context["data_marts"]) == 0


@pytest.mark.django_db
def test_datawarehouse_views_datamart_list_filters(auth_client, tenant_a, data_mart_a):
    """Verify filters ?subject_area=, ?access_tier=, ?certification_status=, and ?is_active=."""
    mart_sales = _datawarehouse_create_extra_mart(
        tenant_a,
        name="Sales Operations Mart",
        code="sales_ops",
        subject_area="sales",
        access_tier="restricted",
        certification_status="draft",
        is_active=False,
    )
    url = reverse("bi:data_mart_list")

    # Subject area filter
    resp = auth_client.get(f"{url}?subject_area=sales")
    assert resp.status_code == 200
    ids = [m.id for m in resp.context["data_marts"]]
    assert mart_sales.id in ids
    assert data_mart_a.id not in ids

    # Access tier filter
    resp = auth_client.get(f"{url}?access_tier=restricted")
    assert resp.status_code == 200
    ids = [m.id for m in resp.context["data_marts"]]
    assert mart_sales.id in ids
    assert data_mart_a.id not in ids

    # Certification status filter
    resp = auth_client.get(f"{url}?certification_status=certified")
    assert resp.status_code == 200
    ids = [m.id for m in resp.context["data_marts"]]
    assert data_mart_a.id in ids
    assert mart_sales.id not in ids

    # Active filter (active=0 vs active=1)
    resp_inactive = auth_client.get(f"{url}?is_active=0")
    assert resp_inactive.status_code == 200
    ids = [m.id for m in resp_inactive.context["data_marts"]]
    assert mart_sales.id in ids
    assert data_mart_a.id not in ids

    resp_active = auth_client.get(f"{url}?is_active=1")
    assert resp_active.status_code == 200
    ids = [m.id for m in resp_active.context["data_marts"]]
    assert data_mart_a.id in ids
    assert mart_sales.id not in ids


@pytest.mark.django_db
def test_datawarehouse_views_datamart_list_csv_export(auth_client, data_mart_a):
    """Verify ?export=csv generates valid CSV attachment with headers and row data."""
    url = reverse("bi:data_mart_list")
    resp = auth_client.get(f"{url}?export=csv")

    assert resp.status_code == 200
    assert resp["Content-Type"] == "text/csv"
    assert 'attachment; filename="data_marts.csv"' in resp["Content-Disposition"]
    content = resp.content.decode("utf-8")
    assert "Number,Name,Code,Subject Area,Org Unit,Owner,Steward,Access Tier" in content
    assert data_mart_a.name in content
    assert data_mart_a.code in content


@pytest.mark.django_db
def test_datawarehouse_views_datamart_list_pagination_and_fallback(auth_client, tenant_a):
    """Verify pagination splits 20 per page, renders page 2, and handles invalid page fallback."""
    # Create 22 extra marts (total > 20)
    for i in range(22):
        _datawarehouse_create_extra_mart(
            tenant_a,
            name=f"Paginated Mart {i:02d}",
            code=f"pag_mart_{i:02d}",
        )

    url = reverse("bi:data_mart_list")

    # Page 1
    resp_p1 = auth_client.get(f"{url}?page=1")
    assert resp_p1.status_code == 200
    assert len(resp_p1.context["data_marts"]) == 20

    # Page 2
    resp_p2 = auth_client.get(f"{url}?page=2")
    assert resp_p2.status_code == 200
    assert len(resp_p2.context["data_marts"]) > 0

    # Invalid page number falls back to page 1
    resp_invalid = auth_client.get(f"{url}?page=notanumber")
    assert resp_invalid.status_code == 200
    assert resp_invalid.context["page_obj"].number == 1

    # Out of range page falls back to last page
    resp_out_of_range = auth_client.get(f"{url}?page=99999")
    assert resp_out_of_range.status_code == 200
    assert resp_out_of_range.context["page_obj"].number == resp_p2.context["page_obj"].paginator.num_pages


@pytest.mark.django_db
def test_datawarehouse_views_datamart_create_get_and_post_valid(auth_client, tenant_a, admin_user):
    """Verify bi:data_mart_create renders GET form, and POST creates record with AuditLog."""
    url = reverse("bi:data_mart_create")

    # GET
    resp_get = auth_client.get(url)
    assert resp_get.status_code == 200
    assert "form" in resp_get.context
    assert resp_get.context["is_edit"] is False
    assert resp_get.context["data_mart"] is None

    # POST valid
    payload = {
        "name": "Supply Chain Analytics Mart",
        "code": "supply_chain_analytics",
        "subject_area": "procurement",
        "access_tier": "department",
        "certification_status": "certified",
        "refresh_cadence": "hourly",
        "owner": admin_user.pk,
        "steward": admin_user.pk,
        "description": "Procurement and supply chain metrics",
        "is_active": True,
    }
    resp_post = auth_client.post(url, data=payload)
    assert resp_post.status_code == 302

    created_mart = DataMart.objects.filter(tenant=tenant_a, code="supply_chain_analytics").first()
    assert created_mart is not None
    assert created_mart.name == "Supply Chain Analytics Mart"
    assert created_mart.tenant == tenant_a
    assert resp_post.url == reverse("bi:data_mart_detail", kwargs={"pk": created_mart.pk})

    # Verify AuditLog created
    assert AuditLog.objects.filter(tenant=tenant_a, action="create", object_id=created_mart.pk).exists()


@pytest.mark.django_db
def test_datawarehouse_views_datamart_create_post_invalid(auth_client, tenant_a):
    """Verify invalid POST re-renders form with errors and does not create record."""
    url = reverse("bi:data_mart_create")
    initial_count = DataMart.objects.filter(tenant=tenant_a).count()

    # Empty name violates required constraint
    payload = {
        "name": "",
        "code": "invalid_mart",
        "subject_area": "finance",
        "access_tier": "department",
        "certification_status": "draft",
        "refresh_cadence": "daily",
    }
    resp = auth_client.post(url, data=payload)
    assert resp.status_code == 200
    assert "form" in resp.context
    assert resp.context["form"].errors
    assert DataMart.objects.filter(tenant=tenant_a).count() == initial_count


@pytest.mark.django_db
def test_datawarehouse_views_datamart_detail_get_and_404(auth_client, data_mart_a, warehouse_table_a):
    """Verify bi:data_mart_detail renders 200 with tables context, and 404 for missing pk."""
    url = reverse("bi:data_mart_detail", kwargs={"pk": data_mart_a.pk})
    resp = auth_client.get(url)

    assert resp.status_code == 200
    assert resp.context["data_mart"] == data_mart_a
    assert warehouse_table_a in resp.context["tables"]

    # 404 for nonexistent pk
    resp_404 = auth_client.get(reverse("bi:data_mart_detail", kwargs={"pk": 999999}))
    assert resp_404.status_code == 404


@pytest.mark.django_db
def test_datawarehouse_views_datamart_edit_get_and_post_valid(auth_client, tenant_a, data_mart_a):
    """Verify bi:data_mart_edit renders GET form, and POST updates record with AuditLog."""
    url = reverse("bi:data_mart_edit", kwargs={"pk": data_mart_a.pk})

    # GET
    resp_get = auth_client.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True
    assert resp_get.context["data_mart"] == data_mart_a

    # POST update
    payload = {
        "name": "Updated Revenue Finance Mart",
        "code": data_mart_a.code,
        "subject_area": data_mart_a.subject_area,
        "access_tier": "restricted",
        "certification_status": "certified",
        "refresh_cadence": "daily",
        "description": "Updated SLA notes",
        "is_active": True,
    }
    resp_post = auth_client.post(url, data=payload)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("bi:data_mart_detail", kwargs={"pk": data_mart_a.pk})

    data_mart_a.refresh_from_db()
    assert data_mart_a.name == "Updated Revenue Finance Mart"
    assert data_mart_a.access_tier == "restricted"

    # Verify AuditLog update entry
    assert AuditLog.objects.filter(tenant=tenant_a, action="update", object_id=data_mart_a.pk).exists()


@pytest.mark.django_db
def test_datawarehouse_views_datamart_delete_post_and_method_not_allowed(auth_client, tenant_a):
    """Verify DELETE requires POST (GET returns 405), deletes record and creates AuditLog."""
    mart = _datawarehouse_create_extra_mart(tenant_a, name="Mart To Delete", code="delete_me_mart")
    url = reverse("bi:data_mart_delete", kwargs={"pk": mart.pk})

    # GET method not allowed
    resp_get = auth_client.get(url)
    assert resp_get.status_code == 405

    # POST deletes
    resp_post = auth_client.post(url)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("bi:data_mart_list")

    assert not DataMart.objects.filter(pk=mart.pk).exists()
    assert AuditLog.objects.filter(tenant=tenant_a, action="delete", object_id=mart.pk).exists()


# ===========================================================================
# 3. LakehouseZone View Tests
# ===========================================================================


@pytest.mark.django_db
def test_datawarehouse_views_lakehouse_zone_list_renders_200_and_context(auth_client, lakehouse_zone_a):
    """Verify bi:lakehouse_zone_list returns HTTP 200 and passes all zone context keys."""
    url = reverse("bi:lakehouse_zone_list")
    resp = auth_client.get(url)

    assert resp.status_code == 200
    expected_keys = [
        "page_obj",
        "lakehouse_zones",
        "zone_type_choices",
        "storage_backend_choices",
        "default_format_choices",
        "active_choices",
        "total_count",
        "bronze_count",
        "silver_count",
        "gold_count",
        "search_query",
    ]
    for key in expected_keys:
        assert key in resp.context, f"Context key '{key}' missing from lakehouse_zone_list"

    assert lakehouse_zone_a in resp.context["lakehouse_zones"]
    assert resp.context["total_count"] >= 1


@pytest.mark.django_db
def test_datawarehouse_views_lakehouse_zone_list_filters_and_export(auth_client, tenant_a, lakehouse_zone_a):
    """Verify filters ?zone_type=, ?storage_backend=, ?default_format=, ?is_active=, and ?export=csv."""
    zone_bronze = _datawarehouse_create_extra_zone(
        tenant_a,
        name="Bronze Raw Landing",
        code="bronze_landing",
        zone_type="bronze",
        storage_backend="s3_compatible",
        default_format="delta_lake",
        is_active=False,
    )
    url = reverse("bi:lakehouse_zone_list")

    # Zone type filter
    resp = auth_client.get(f"{url}?zone_type=bronze")
    assert resp.status_code == 200
    ids = [z.id for z in resp.context["lakehouse_zones"]]
    assert zone_bronze.id in ids
    assert lakehouse_zone_a.id not in ids

    # Storage backend filter
    resp = auth_client.get(f"{url}?storage_backend=s3_compatible")
    assert resp.status_code == 200
    ids = [z.id for z in resp.context["lakehouse_zones"]]
    assert zone_bronze.id in ids
    assert lakehouse_zone_a.id not in ids

    # Default format filter
    resp = auth_client.get(f"{url}?default_format=delta_lake")
    assert resp.status_code == 200
    ids = [z.id for z in resp.context["lakehouse_zones"]]
    assert zone_bronze.id in ids
    assert lakehouse_zone_a.id not in ids

    # Active filter
    resp = auth_client.get(f"{url}?is_active=0")
    assert resp.status_code == 200
    ids = [z.id for z in resp.context["lakehouse_zones"]]
    assert zone_bronze.id in ids
    assert lakehouse_zone_a.id not in ids

    # CSV Export
    resp_csv = auth_client.get(f"{url}?export=csv")
    assert resp_csv.status_code == 200
    assert resp_csv["Content-Type"] == "text/csv"
    assert 'attachment; filename="lakehouse_zones.csv"' in resp_csv["Content-Disposition"]
    content = resp_csv.content.decode("utf-8")
    assert "Number,Name,Code,Zone Type,Storage Backend,Default Format" in content
    assert lakehouse_zone_a.name in content


@pytest.mark.django_db
def test_datawarehouse_views_lakehouse_zone_create_get_and_post(auth_client, tenant_a):
    """Verify bi:lakehouse_zone_create renders form and POST creates zone with AuditLog."""
    url = reverse("bi:lakehouse_zone_create")

    # GET
    resp_get = auth_client.get(url)
    assert resp_get.status_code == 200
    assert "form" in resp_get.context
    assert resp_get.context["is_edit"] is False

    # POST valid
    payload = {
        "name": "Silver Standardized Clean Zone",
        "code": "silver_standardized",
        "zone_type": "silver",
        "storage_backend": "internal_db",
        "default_format": "relational_table",
        "base_uri_path": "/warehouse/silver",
        "is_read_only": False,
        "description": "Cleansed and validated models",
        "is_active": True,
    }
    resp_post = auth_client.post(url, data=payload)
    assert resp_post.status_code == 302

    created_zone = LakehouseZone.objects.filter(tenant=tenant_a, code="silver_standardized").first()
    assert created_zone is not None
    assert resp_post.url == reverse("bi:lakehouse_zone_detail", kwargs={"pk": created_zone.pk})
    assert AuditLog.objects.filter(tenant=tenant_a, action="create", object_id=created_zone.pk).exists()


@pytest.mark.django_db
def test_datawarehouse_views_lakehouse_zone_detail(auth_client, lakehouse_zone_a, warehouse_table_a):
    """Verify bi:lakehouse_zone_detail renders 200 with zone and tables context."""
    url = reverse("bi:lakehouse_zone_detail", kwargs={"pk": lakehouse_zone_a.pk})
    resp = auth_client.get(url)

    assert resp.status_code == 200
    assert resp.context["lakehouse_zone"] == lakehouse_zone_a
    assert warehouse_table_a in resp.context["tables"]


@pytest.mark.django_db
def test_datawarehouse_views_lakehouse_zone_edit_get_and_post(auth_client, tenant_a, lakehouse_zone_a):
    """Verify bi:lakehouse_zone_edit renders GET form and POST updates zone with AuditLog."""
    url = reverse("bi:lakehouse_zone_edit", kwargs={"pk": lakehouse_zone_a.pk})

    # GET
    resp_get = auth_client.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True
    assert resp_get.context["lakehouse_zone"] == lakehouse_zone_a

    # POST
    payload = {
        "name": "Updated Gold Marts Zone",
        "code": lakehouse_zone_a.code,
        "zone_type": lakehouse_zone_a.zone_type,
        "storage_backend": lakehouse_zone_a.storage_backend,
        "default_format": lakehouse_zone_a.default_format,
        "base_uri_path": "/warehouse/gold/v2",
        "is_read_only": True,
        "description": "Updated zone governance notes",
        "is_active": True,
    }
    resp_post = auth_client.post(url, data=payload)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("bi:lakehouse_zone_detail", kwargs={"pk": lakehouse_zone_a.pk})

    lakehouse_zone_a.refresh_from_db()
    assert lakehouse_zone_a.name == "Updated Gold Marts Zone"
    assert lakehouse_zone_a.is_read_only is True
    assert AuditLog.objects.filter(tenant=tenant_a, action="update", object_id=lakehouse_zone_a.pk).exists()


@pytest.mark.django_db
def test_datawarehouse_views_lakehouse_zone_delete_success_when_unreferenced(auth_client, tenant_a):
    """Verify unreferenced zone is deleted and redirects to zone list."""
    zone = _datawarehouse_create_extra_zone(tenant_a, name="Unreferenced Zone", code="unref_zone")
    url = reverse("bi:lakehouse_zone_delete", kwargs={"pk": zone.pk})

    resp = auth_client.post(url)
    assert resp.status_code == 302
    assert resp.url == reverse("bi:lakehouse_zone_list")

    assert not LakehouseZone.objects.filter(pk=zone.pk).exists()
    assert AuditLog.objects.filter(tenant=tenant_a, action="delete", object_id=zone.pk).exists()


@pytest.mark.django_db
def test_datawarehouse_views_lakehouse_zone_delete_protected_when_tables_exist(
    auth_client, lakehouse_zone_a, warehouse_table_a
):
    """Verify delete handles ProtectedError when tables exist, flashes warning, and does NOT delete."""
    url = reverse("bi:lakehouse_zone_delete", kwargs={"pk": lakehouse_zone_a.pk})

    resp = auth_client.post(url)
    assert resp.status_code == 302
    # Redirects back to detail page on ProtectedError
    assert resp.url == reverse("bi:lakehouse_zone_detail", kwargs={"pk": lakehouse_zone_a.pk})

    # Zone must still exist
    assert LakehouseZone.objects.filter(pk=lakehouse_zone_a.pk).exists()


@pytest.mark.django_db
def test_datawarehouse_views_lakehouse_zone_delete_get_method_not_allowed(auth_client, lakehouse_zone_a):
    """Verify GET method is not allowed on delete endpoint."""
    url = reverse("bi:lakehouse_zone_delete", kwargs={"pk": lakehouse_zone_a.pk})
    resp = auth_client.get(url)
    assert resp.status_code == 405


# ===========================================================================
# 4. WarehouseStoragePolicy View Tests
# ===========================================================================


@pytest.mark.django_db
def test_datawarehouse_views_storage_policy_list_renders_200_and_context(auth_client, storage_policy_a):
    """Verify bi:warehouse_storage_policy_list returns HTTP 200 and context keys."""
    url = reverse("bi:warehouse_storage_policy_list")
    resp = auth_client.get(url)

    assert resp.status_code == 200
    expected_keys = [
        "page_obj",
        "storage_policies",
        "partition_strategy_choices",
        "compression_codec_choices",
        "vacuum_cadence_choices",
        "active_choices",
        "total_count",
        "default_policy",
        "search_query",
    ]
    for key in expected_keys:
        assert key in resp.context, f"Context key '{key}' missing from warehouse_storage_policy_list"

    assert storage_policy_a in resp.context["storage_policies"]
    assert resp.context["total_count"] >= 1


@pytest.mark.django_db
def test_datawarehouse_views_storage_policy_list_filters_and_export(auth_client, tenant_a, storage_policy_a):
    """Verify filters ?partition_strategy=, ?compression_codec=, ?vacuum_cadence=, ?is_active=, and ?export=csv."""
    policy_hash = _datawarehouse_create_extra_policy(
        tenant_a,
        name="Hash Partitioned Zstd Policy",
        partition_strategy="hash_bucket",
        partition_key="account_id",
        compression_codec="zstd",
        vacuum_cadence="monthly",
        is_active=False,
    )
    url = reverse("bi:warehouse_storage_policy_list")

    # Partition strategy filter
    resp = auth_client.get(f"{url}?partition_strategy=hash_bucket")
    assert resp.status_code == 200
    ids = [p.id for p in resp.context["storage_policies"]]
    assert policy_hash.id in ids
    assert storage_policy_a.id not in ids

    # Compression codec filter
    resp = auth_client.get(f"{url}?compression_codec=zstd")
    assert resp.status_code == 200
    ids = [p.id for p in resp.context["storage_policies"]]
    assert policy_hash.id in ids
    assert storage_policy_a.id not in ids

    # Vacuum cadence filter
    resp = auth_client.get(f"{url}?vacuum_cadence=monthly")
    assert resp.status_code == 200
    ids = [p.id for p in resp.context["storage_policies"]]
    assert policy_hash.id in ids
    assert storage_policy_a.id not in ids

    # Active filter
    resp = auth_client.get(f"{url}?is_active=0")
    assert resp.status_code == 200
    ids = [p.id for p in resp.context["storage_policies"]]
    assert policy_hash.id in ids
    assert storage_policy_a.id not in ids

    # CSV export
    resp_csv = auth_client.get(f"{url}?export=csv")
    assert resp_csv.status_code == 200
    assert resp_csv["Content-Type"] == "text/csv"
    assert 'attachment; filename="warehouse_storage_policies.csv"' in resp_csv["Content-Disposition"]
    content = resp_csv.content.decode("utf-8")
    assert "Number,Name,Partition Strategy,Partition Key,Granularity,Compression" in content
    assert storage_policy_a.name in content


@pytest.mark.django_db
def test_datawarehouse_views_storage_policy_create_get_and_post(auth_client, tenant_a):
    """Verify bi:warehouse_storage_policy_create renders form, and POST creates policy with AuditLog."""
    url = reverse("bi:warehouse_storage_policy_create")

    # GET
    resp_get = auth_client.get(url)
    assert resp_get.status_code == 200
    assert "form" in resp_get.context
    assert resp_get.context["is_edit"] is False

    # POST valid with is_default=True
    payload = {
        "name": "Default Analytical Tiering Policy",
        "partition_strategy": "range_time",
        "partition_key": "event_date",
        "partition_granularity": "day",
        "compression_codec": "snappy",
        "enable_zone_maps": True,
        "hot_tier_days": 15,
        "warm_tier_days": 60,
        "cold_tier_days": 180,
        "time_travel_days": 7,
        "auto_purge_enabled": True,
        "vacuum_cadence": "weekly",
        "is_default": True,
        "description": "Standard corporate data retention SLA",
        "is_active": True,
    }
    resp_post = auth_client.post(url, data=payload)
    assert resp_post.status_code == 302

    created_policy = WarehouseStoragePolicy.objects.filter(tenant=tenant_a, name="Default Analytical Tiering Policy").first()
    assert created_policy is not None
    assert created_policy.is_default is True
    assert resp_post.url == reverse("bi:warehouse_storage_policy_detail", kwargs={"pk": created_policy.pk})
    assert AuditLog.objects.filter(tenant=tenant_a, action="create", object_id=created_policy.pk).exists()


@pytest.mark.django_db
def test_datawarehouse_views_storage_policy_detail(auth_client, storage_policy_a, warehouse_table_a):
    """Verify bi:warehouse_storage_policy_detail renders 200 with policy and tables context."""
    url = reverse("bi:warehouse_storage_policy_detail", kwargs={"pk": storage_policy_a.pk})
    resp = auth_client.get(url)

    assert resp.status_code == 200
    assert resp.context["storage_policy"] == storage_policy_a
    assert warehouse_table_a in resp.context["tables"]


@pytest.mark.django_db
def test_datawarehouse_views_storage_policy_edit_get_and_post(auth_client, tenant_a, storage_policy_a):
    """Verify bi:warehouse_storage_policy_edit renders GET form and POST updates policy with AuditLog."""
    url = reverse("bi:warehouse_storage_policy_edit", kwargs={"pk": storage_policy_a.pk})

    # GET
    resp_get = auth_client.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True
    assert resp_get.context["storage_policy"] == storage_policy_a

    # POST
    payload = {
        "name": "Updated Snappy Daily Policy",
        "partition_strategy": storage_policy_a.partition_strategy,
        "partition_key": "invoice_date",
        "partition_granularity": storage_policy_a.partition_granularity,
        "compression_codec": storage_policy_a.compression_codec,
        "enable_zone_maps": False,
        "hot_tier_days": 45,
        "warm_tier_days": 120,
        "cold_tier_days": 400,
        "time_travel_days": 15,
        "auto_purge_enabled": False,
        "vacuum_cadence": "monthly",
        "is_default": False,
        "description": "Updated description",
        "is_active": True,
    }
    resp_post = auth_client.post(url, data=payload)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("bi:warehouse_storage_policy_detail", kwargs={"pk": storage_policy_a.pk})

    storage_policy_a.refresh_from_db()
    assert storage_policy_a.name == "Updated Snappy Daily Policy"
    assert storage_policy_a.vacuum_cadence == "monthly"
    assert AuditLog.objects.filter(tenant=tenant_a, action="update", object_id=storage_policy_a.pk).exists()


@pytest.mark.django_db
def test_datawarehouse_views_storage_policy_delete_post_and_method_not_allowed(auth_client, tenant_a):
    """Verify storage policy delete requires POST (GET 405), deletes record and creates AuditLog."""
    policy = _datawarehouse_create_extra_policy(tenant_a, name="Temporary Policy For Delete")
    url = reverse("bi:warehouse_storage_policy_delete", kwargs={"pk": policy.pk})

    # GET 405
    resp_get = auth_client.get(url)
    assert resp_get.status_code == 405

    # POST deletes
    resp_post = auth_client.post(url)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("bi:warehouse_storage_policy_list")

    assert not WarehouseStoragePolicy.objects.filter(pk=policy.pk).exists()
    assert AuditLog.objects.filter(tenant=tenant_a, action="delete", object_id=policy.pk).exists()


# ===========================================================================
# 5. WarehouseTable View Tests
# ===========================================================================


@pytest.mark.django_db
def test_datawarehouse_views_warehouse_table_list_renders_200_and_context(auth_client, warehouse_table_a):
    """Verify bi:warehouse_table_list returns HTTP 200 and passes all table filter/stats keys."""
    url = reverse("bi:warehouse_table_list")
    resp = auth_client.get(url)

    assert resp.status_code == 200
    expected_keys = [
        "page_obj",
        "warehouse_tables",
        "table_type_choices",
        "schema_type_choices",
        "grain_choices",
        "lakehouse_zones",
        "data_marts",
        "active_choices",
        "total_count",
        "fact_count",
        "dimension_count",
        "total_rows",
        "search_query",
    ]
    for key in expected_keys:
        assert key in resp.context, f"Context key '{key}' missing from warehouse_table_list"

    assert warehouse_table_a in resp.context["warehouse_tables"]
    assert resp.context["total_count"] >= 1


@pytest.mark.django_db
def test_datawarehouse_views_warehouse_table_list_filters_and_export(
    auth_client, tenant_a, warehouse_table_a, lakehouse_zone_a, storage_policy_a, data_mart_a
):
    """Verify filters ?table_type=, ?schema_type=, ?grain=, ?lakehouse_zone=, ?data_mart=, ?is_conformed=, and export."""
    other_zone = _datawarehouse_create_extra_zone(tenant_a, name="Table Test Zone", code="tbl_test_zone")
    other_mart = _datawarehouse_create_extra_mart(tenant_a, name="Table Test Mart", code="tbl_test_mart")

    dim_table = _datawarehouse_create_extra_table(
        tenant_a,
        zone=other_zone,
        policy=storage_policy_a,
        mart=other_mart,
        name="Customer Dimension Table",
        table_name="dim_customers",
        table_type="dimension",
        schema_type="snowflake",
        grain="type_2_scd",
        is_conformed_dimension=False,
        is_active=False,
    )
    url = reverse("bi:warehouse_table_list")

    # Table type filter
    resp = auth_client.get(f"{url}?table_type=dimension")
    assert resp.status_code == 200
    ids = [t.id for t in resp.context["warehouse_tables"]]
    assert dim_table.id in ids
    assert warehouse_table_a.id not in ids

    # Schema type filter
    resp = auth_client.get(f"{url}?schema_type=snowflake")
    assert resp.status_code == 200
    ids = [t.id for t in resp.context["warehouse_tables"]]
    assert dim_table.id in ids
    assert warehouse_table_a.id not in ids

    # Grain filter
    resp = auth_client.get(f"{url}?grain=type_2_scd")
    assert resp.status_code == 200
    ids = [t.id for t in resp.context["warehouse_tables"]]
    assert dim_table.id in ids
    assert warehouse_table_a.id not in ids

    # Lakehouse zone filter
    resp = auth_client.get(f"{url}?lakehouse_zone={other_zone.pk}")
    assert resp.status_code == 200
    ids = [t.id for t in resp.context["warehouse_tables"]]
    assert dim_table.id in ids
    assert warehouse_table_a.id not in ids

    # Data mart filter
    resp = auth_client.get(f"{url}?data_mart={other_mart.pk}")
    assert resp.status_code == 200
    ids = [t.id for t in resp.context["warehouse_tables"]]
    assert dim_table.id in ids
    assert warehouse_table_a.id not in ids

    # Conformed dimension filter (conformed=0 vs conformed=1)
    resp = auth_client.get(f"{url}?is_conformed=0")
    assert resp.status_code == 200
    ids = [t.id for t in resp.context["warehouse_tables"]]
    assert dim_table.id in ids
    assert warehouse_table_a.id not in ids

    # Active filter
    resp = auth_client.get(f"{url}?is_active=0")
    assert resp.status_code == 200
    ids = [t.id for t in resp.context["warehouse_tables"]]
    assert dim_table.id in ids
    assert warehouse_table_a.id not in ids

    # Export CSV
    resp_csv = auth_client.get(f"{url}?export=csv")
    assert resp_csv.status_code == 200
    assert resp_csv["Content-Type"] == "text/csv"
    assert 'attachment; filename="warehouse_tables.csv"' in resp_csv["Content-Disposition"]
    content = resp_csv.content.decode("utf-8")
    assert "Number,Name,Physical Table,Table Type,Schema Type,Grain" in content
    assert warehouse_table_a.table_name in content


@pytest.mark.django_db
def test_datawarehouse_views_warehouse_table_create_get_prefill_and_post(
    auth_client, tenant_a, lakehouse_zone_a, storage_policy_a, data_mart_a
):
    """Verify bi:warehouse_table_create GET supports query param prefill, and POST creates record."""
    url = reverse("bi:warehouse_table_create")

    # GET with prefill parameters
    resp_get = auth_client.get(f"{url}?lakehouse_zone={lakehouse_zone_a.pk}&data_mart={data_mart_a.pk}")
    assert resp_get.status_code == 200
    assert "form" in resp_get.context
    assert resp_get.context["is_edit"] is False
    assert resp_get.context["form"].initial.get("lakehouse_zone") == str(lakehouse_zone_a.pk)
    assert resp_get.context["form"].initial.get("data_mart") == str(data_mart_a.pk)

    # POST valid table
    schema_json = json.dumps([
        {"name": "order_id", "type": "BIGINT", "nullable": False},
        {"name": "order_number", "type": "VARCHAR(64)", "nullable": False},
        {"name": "total_amount", "type": "NUMERIC(14,2)", "nullable": False},
    ])
    payload = {
        "name": "Fact Sales Orders Table",
        "table_name": "fact_sales_orders",
        "table_type": "fact",
        "schema_type": "star",
        "grain": "transaction",
        "lakehouse_zone": lakehouse_zone_a.pk,
        "data_mart": data_mart_a.pk,
        "storage_policy": storage_policy_a.pk,
        "primary_key_column": "order_id",
        "natural_key_column": "order_number",
        "is_conformed_dimension": False,
        "schema_definition_raw": schema_json,
        "description": "Granular customer sales orders",
        "is_active": True,
    }
    resp_post = auth_client.post(url, data=payload)
    assert resp_post.status_code == 302

    created_table = WarehouseTable.objects.filter(tenant=tenant_a, table_name="fact_sales_orders").first()
    assert created_table is not None
    assert len(created_table.schema_definition) == 3
    assert resp_post.url == reverse("bi:warehouse_table_detail", kwargs={"pk": created_table.pk})
    assert AuditLog.objects.filter(tenant=tenant_a, action="create", object_id=created_table.pk).exists()


@pytest.mark.django_db
def test_datawarehouse_views_warehouse_table_detail(auth_client, warehouse_table_a):
    """Verify bi:warehouse_table_detail renders 200 with warehouse_table and generated ddl_sql."""
    url = reverse("bi:warehouse_table_detail", kwargs={"pk": warehouse_table_a.pk})
    resp = auth_client.get(url)

    assert resp.status_code == 200
    assert resp.context["warehouse_table"] == warehouse_table_a
    assert "ddl_sql" in resp.context
    assert "CREATE TABLE IF NOT EXISTS fact_daily_revenue" in resp.context["ddl_sql"]


@pytest.mark.django_db
def test_datawarehouse_views_warehouse_table_edit_get_and_post(auth_client, tenant_a, warehouse_table_a):
    """Verify bi:warehouse_table_edit renders GET form and POST updates table with AuditLog."""
    url = reverse("bi:warehouse_table_edit", kwargs={"pk": warehouse_table_a.pk})

    # GET
    resp_get = auth_client.get(url)
    assert resp_get.status_code == 200
    assert resp_get.context["is_edit"] is True
    assert resp_get.context["warehouse_table"] == warehouse_table_a

    # POST update
    payload = {
        "name": "Updated Daily Invoiced Revenue Fact",
        "table_name": warehouse_table_a.table_name,
        "table_type": warehouse_table_a.table_type,
        "schema_type": warehouse_table_a.schema_type,
        "grain": warehouse_table_a.grain,
        "lakehouse_zone": warehouse_table_a.lakehouse_zone_id,
        "data_mart": warehouse_table_a.data_mart_id,
        "storage_policy": warehouse_table_a.storage_policy_id,
        "primary_key_column": warehouse_table_a.primary_key_column,
        "is_conformed_dimension": True,
        "description": "Updated revenue fact description",
        "is_active": True,
    }
    resp_post = auth_client.post(url, data=payload)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("bi:warehouse_table_detail", kwargs={"pk": warehouse_table_a.pk})

    warehouse_table_a.refresh_from_db()
    assert warehouse_table_a.name == "Updated Daily Invoiced Revenue Fact"
    assert AuditLog.objects.filter(tenant=tenant_a, action="update", object_id=warehouse_table_a.pk).exists()


@pytest.mark.django_db
def test_datawarehouse_views_warehouse_table_ddl_preview(auth_client, warehouse_table_a):
    """Verify bi:warehouse_table_ddl_preview returns HTTP 200 with generated DDL SQL."""
    url = reverse("bi:warehouse_table_ddl_preview", kwargs={"pk": warehouse_table_a.pk})
    resp = auth_client.get(url)

    assert resp.status_code == 200
    assert "ddl_sql" in resp.context
    assert "CREATE TABLE IF NOT EXISTS fact_daily_revenue" in resp.context["ddl_sql"]
    assert "invoice_date DATE NOT NULL" in resp.context["ddl_sql"]


@pytest.mark.django_db
def test_datawarehouse_views_warehouse_table_analyze_post_and_method_not_allowed(
    auth_client, tenant_a, lakehouse_zone_a, storage_policy_a, data_mart_a
):
    """Verify table analyze requires POST (GET 405), updates last_analyzed_at, and writes AuditLog."""
    table = _datawarehouse_create_extra_table(
        tenant_a,
        zone=lakehouse_zone_a,
        policy=storage_policy_a,
        mart=data_mart_a,
        name="Table For Analysis",
        table_name="fact_unanalyzed",
        row_count=0,
        compressed_bytes=0,
    )
    url = reverse("bi:warehouse_table_analyze", kwargs={"pk": table.pk})

    # GET 405
    resp_get = auth_client.get(url)
    assert resp_get.status_code == 405

    # POST analyzes telemetry
    resp_post = auth_client.post(url)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("bi:warehouse_table_detail", kwargs={"pk": table.pk})

    table.refresh_from_db()
    assert table.last_analyzed_at is not None
    assert table.row_count == 100000
    assert table.compressed_bytes == 25000000
    assert table.compression_ratio == Decimal("3.40")
    assert AuditLog.objects.filter(tenant=tenant_a, action="analyze", object_id=table.pk).exists()


@pytest.mark.django_db
def test_datawarehouse_views_warehouse_table_delete_post_and_method_not_allowed(
    auth_client, tenant_a, lakehouse_zone_a, storage_policy_a, data_mart_a
):
    """Verify warehouse table delete requires POST (GET 405), removes table, and writes AuditLog."""
    table = _datawarehouse_create_extra_table(
        tenant_a,
        zone=lakehouse_zone_a,
        policy=storage_policy_a,
        mart=data_mart_a,
        name="Table To Delete",
        table_name="dim_temporary_table",
    )
    url = reverse("bi:warehouse_table_delete", kwargs={"pk": table.pk})

    # GET 405
    resp_get = auth_client.get(url)
    assert resp_get.status_code == 405

    # POST deletes
    resp_post = auth_client.post(url)
    assert resp_post.status_code == 302
    assert resp_post.url == reverse("bi:warehouse_table_list")

    assert not WarehouseTable.objects.filter(pk=table.pk).exists()
    assert AuditLog.objects.filter(tenant=tenant_a, action="delete", object_id=table.pk).exists()


# ===========================================================================
# 6. Tenant Isolation / IDOR Cross-Tenant Assertions
# ===========================================================================


@pytest.mark.django_db
def test_datawarehouse_views_tenant_isolation_datamart_detail_cross_tenant_404(auth_client, data_mart_b):
    """Verify tenant_a user accessing tenant_b DataMart receives HTTP 404."""
    url = reverse("bi:data_mart_detail", kwargs={"pk": data_mart_b.pk})
    resp = auth_client.get(url)
    assert resp.status_code == 404


@pytest.mark.django_db
def test_datawarehouse_views_tenant_isolation_lakehouse_zone_detail_cross_tenant_404(
    auth_client, lakehouse_zone_b
):
    """Verify tenant_a user accessing tenant_b LakehouseZone receives HTTP 404."""
    url = reverse("bi:lakehouse_zone_detail", kwargs={"pk": lakehouse_zone_b.pk})
    resp = auth_client.get(url)
    assert resp.status_code == 404


@pytest.mark.django_db
def test_datawarehouse_views_tenant_isolation_storage_policy_detail_cross_tenant_404(
    auth_client, storage_policy_b
):
    """Verify tenant_a user accessing tenant_b WarehouseStoragePolicy receives HTTP 404."""
    url = reverse("bi:warehouse_storage_policy_detail", kwargs={"pk": storage_policy_b.pk})
    resp = auth_client.get(url)
    assert resp.status_code == 404


@pytest.mark.django_db
def test_datawarehouse_views_tenant_isolation_warehouse_table_detail_cross_tenant_404(
    auth_client, warehouse_table_b
):
    """Verify tenant_a user accessing tenant_b WarehouseTable receives HTTP 404."""
    url = reverse("bi:warehouse_table_detail", kwargs={"pk": warehouse_table_b.pk})
    resp = auth_client.get(url)
    assert resp.status_code == 404


@pytest.mark.django_db
def test_datawarehouse_views_tenant_isolation_warehouse_table_analyze_cross_tenant_404(
    auth_client, warehouse_table_b
):
    """Verify tenant_a user attempting to analyze tenant_b WarehouseTable receives HTTP 404."""
    url = reverse("bi:warehouse_table_analyze", kwargs={"pk": warehouse_table_b.pk})
    resp = auth_client.post(url)
    assert resp.status_code == 404
