"""View, workflow, navigation, template-contract, and query-budget tests for Asset 11.15 Integration & API Hub."""

from __future__ import annotations

import datetime
import hashlib
import re
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.contrib.messages import get_messages
from django.urls import reverse
from django.utils import timezone

from apps.accounting.models import FiscalPeriod, GLAccount, JournalEntry, JournalLine
from apps.assets.models import (
    AssetDepreciationSchedule,
    AssetGisMapping,
    AssetGlSyncBatch,
    AssetIntegrationConnector,
    AssetMaintenanceRequest,
    AssetTelemetryReading,
    AssetTelemetryStream,
)
from apps.core.models import AuditLog
from apps.core.navigation import LIVE_LINKS, resolve_nav


pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Module-level helpers (all prefixed with _integration_api_hub_*)
# ---------------------------------------------------------------------------


def _integration_api_hub_msg_texts(response):
    """Return rendered or queued Django flash message strings for a response."""
    return [str(m) for m in get_messages(response.wsgi_request)]


def _integration_api_hub_make_connector(tenant, index=1, **overrides):
    """Create a valid AssetIntegrationConnector for tenant without touching conftest."""
    defaults = {
        "tenant": tenant,
        "name": f"Integration Connector #{index}",
        "connector_category": "iot_scada",
        "provider": "kepware_opcua",
        "protocol": "opc_ua",
        "sync_direction": "inbound",
        "environment": "production",
        "endpoint_url": f"https://gateway-{index}.example.com/api/v1",
        "auth_method": "api_key",
        "rate_limit_rpm": 120,
        "timeout_seconds": 30,
        "retry_policy_max": 3,
        "polling_interval_minutes": 15,
        "status": "active",
        "health_status": "healthy",
        "webhook_verify_tls": True,
    }
    defaults.update(overrides)
    return AssetIntegrationConnector.objects.create(**defaults)


def _integration_api_hub_make_stream(
    tenant, connector, operational_asset, index=1, **overrides
):
    """Create a valid AssetTelemetryStream for tenant."""
    defaults = {
        "tenant": tenant,
        "connector": connector,
        "operational_asset": operational_asset,
        "tag_address": f"ns=2;s=Plant.Line1.Tag{index}",
        "stream_name": f"Telemetry Stream #{index}",
        "stream_protocol": "opc_ua_node",
        "metric_type": "bearing_temperature",
        "metric_unit": "celsius",
        "ingestion_mode": "polling",
        "polling_interval_seconds": 30,
        "deadband_delta": Decimal("0.0000"),
        "scale_factor": Decimal("1.000000"),
        "offset_value": Decimal("0.0000"),
        "baseline_value": Decimal("40.0000"),
        "warning_threshold": Decimal("75.0000"),
        "critical_threshold": Decimal("90.0000"),
        "auto_trigger_maintenance": True,
        "stream_status": "active",
    }
    defaults.update(overrides)
    return AssetTelemetryStream.objects.create(**defaults)


def _integration_api_hub_make_batch(tenant, connector, index=1, **overrides):
    """Create a valid AssetGlSyncBatch for tenant."""
    defaults = {
        "tenant": tenant,
        "connector": connector,
        "sync_domain": "depreciation_posting",
        "sync_direction": "outbound",
        "external_batch_ref": f"EXT-GL-{index:04d}",
        "batch_date": datetime.date(2026, 6, 15),
        "source_amount": Decimal("1500.00"),
        "target_gl_amount": Decimal("1500.00"),
        "status": "ready",
        "reconciliation_status": "pending",
        "field_mapping_json": '{"asset_class": "MACH"}',
    }
    defaults.update(overrides)
    return AssetGlSyncBatch.objects.create(**defaults)


def _integration_api_hub_make_mapping(
    tenant, connector, operational_asset, index=1, **overrides
):
    """Create a valid AssetGisMapping for tenant."""
    defaults = {
        "tenant": tenant,
        "connector": connector,
        "operational_asset": operational_asset,
        "external_feature_id": f"GIS-FEAT-{index:04d}",
        "layer_name": "plant_assets_pt",
        "geometry_type": "point",
        "coordinate_system_srid": 4326,
        "latitude": Decimal("40.748400"),
        "longitude": Decimal("-73.985700"),
        "is_linear_asset": False,
        "lrs_measure_unit": "km",
        "geojson_payload": '{"type": "Point", "coordinates": [-73.9857, 40.7484]}',
        "system_of_record": "erp_authoritative",
        "sync_direction": "bidirectional",
        "status": "active",
        "drift_status": "in_sync",
    }
    defaults.update(overrides)
    return AssetGisMapping.objects.create(**defaults)


def _integration_api_hub_make_depreciation_schedule(
    tenant,
    fixed_asset,
    operational_asset,
    expense_account,
    accum_account,
    index=1,
    **overrides,
):
    """Create AssetDepreciationSchedule directly without calling broken conftest fixture."""
    defaults = {
        "tenant": tenant,
        "fixed_asset": fixed_asset,
        "operational_asset": operational_asset,
        "fiscal_year": 2026,
        "period_number": ((index - 1) % 12) + 1,
        "period_frequency": "monthly",
        "schedule_date": datetime.date(2026, 6, 15),
        "depreciation_method": "straight_line",
        "starting_book_value": Decimal("100000.00"),
        "depreciation_amount": Decimal("1800.00"),
        "accumulated_depreciation_after": Decimal("21800.00"),
        "ending_book_value": Decimal("98200.00"),
        "expense_account": expense_account,
        "accumulated_account": accum_account,
        "status": "draft",
    }
    defaults.update(overrides)
    return AssetDepreciationSchedule.objects.create(**defaults)


def _integration_api_hub_make_maintenance_request(
    tenant,
    operational_asset,
    fixed_asset,
    requester,
    index=1,
    **overrides,
):
    """Create AssetMaintenanceRequest with valid schema fields."""
    defaults = {
        "tenant": tenant,
        "title": f"CBM Breakdown Alert #{index}",
        "fixed_asset": fixed_asset,
        "operational_asset": operational_asset,
        "requester": requester,
        "request_type": "breakdown_repair",
        "urgency": "critical",
        "is_breakdown": True,
        "downtime_started_at": timezone.now(),
        "symptom_description": f"Telemetry critical breach #{index}",
        "status": "submitted",
    }
    defaults.update(overrides)
    return AssetMaintenanceRequest.objects.create(**defaults)


def _integration_api_hub_reverse_live_link(url_spec):
    """Reverse an entry from LIVE_LINKS['11.15'], preserving ?query suffixes."""
    if "?" in url_spec:
        route_name, query = url_spec.split("?", 1)
        return f"{reverse(route_name)}?{query}"
    return reverse(url_spec)


def _integration_api_hub_extract_11_15_sidebar_active(html):
    """Extract active link labels inside the 11.15 sidebar subgroup."""
    pattern = re.compile(
        r'<div class="nav-subgroup([^"]*)"[^>]*data-nav-key="11\.15[^"]*"[^>]*>(.*?)</div>\s*</div>',
        re.DOTALL,
    )
    match = pattern.search(html)
    if not match:
        return [], False
    subgroup_classes, body = match.group(1), match.group(2)
    is_open = "open" in subgroup_classes.split()
    active_links = re.findall(
        r'<a href="[^"]*"\s+class="active">([^<]+)</a>',
        body,
    )
    return [lbl.strip() for lbl in active_links], is_open


def _integration_api_hub_assert_list_template_contract(html):
    """Verify UI/a11y contracts on an 11.15 list page."""
    assert 'class="table-wrap"' in html
    assert "btn-sm" in html
    assert 'aria-label="Reset filters"' in html
    assert "text-end" in html
    assert "table-responsive" not in html
    assert "btn-xs" not in html
    assert "form-checkbox" not in html
    assert "text-right" not in html

    filter_ids = set(re.findall(r'id="(id_filter_[^"]+)"', html))
    assert filter_ids, "Expected accessible id_filter_* controls in list template"
    for fid in filter_ids:
        assert f'for="{fid}"' in html, f"Missing <label for='{fid}'>"


# ---------------------------------------------------------------------------
# 1. Overview & Navigation Parity
# ---------------------------------------------------------------------------


class TestIntegrationApiHubOverviewAndNavViews:
    def test_integration_api_hub_overview_displays_kpis_and_quick_links(
        self,
        client_a,
        integration_connector_a,
        integration_stream_a,
        integration_gl_batch_a,
        integration_gis_mapping_a,
    ):
        response = client_a.get(reverse("assets:overview"))
        assert response.status_code == 200
        kpis = response.context["kpis"]
        assert kpis["total_connectors"] == 1
        assert kpis["active_connectors"] == 1
        assert kpis["total_streams"] == 1
        assert kpis["active_streams"] == 1
        assert kpis["total_gl_batches"] == 1
        assert kpis["posted_gl_batches"] == 0
        assert kpis["total_gis_mappings"] == 1
        assert kpis["drifted_gis_mappings"] == 0

        html = response.content.decode("utf-8")
        assert "API Connectors" in html
        assert "IoT &amp; SCADA Streams" in html or "IoT & SCADA Streams" in html
        assert "GL Sync &amp; Recon" in html or "GL Sync & Recon" in html
        assert "GIS Spatial Mappings" in html
        assert reverse("assets:asset_integration_connector_list") in html
        assert reverse("assets:asset_telemetry_stream_list") in html
        assert reverse("assets:asset_gl_sync_batch_list") in html
        assert reverse("assets:asset_gis_mapping_list") in html

    def test_integration_api_hub_overview_kpis_are_tenant_isolated(
        self,
        client_a,
        tenant_a,
        operational_asset_a,
        integration_connector_a,
        integration_connector_b,
        integration_stream_b,
        integration_gl_batch_b,
        integration_gis_mapping_b,
    ):
        _integration_api_hub_make_mapping(
            tenant_a,
            integration_connector_a,
            operational_asset_a,
            index=91,
            drift_status="location_drift",
        )
        _integration_api_hub_make_batch(
            tenant_a,
            integration_connector_a,
            index=92,
            status="posted",
            reconciliation_status="reconciled",
        )
        response = client_a.get(reverse("assets:overview"))
        assert response.status_code == 200
        kpis = response.context["kpis"]
        assert kpis["total_connectors"] == 1
        assert kpis["total_streams"] == 0
        assert kpis["total_gl_batches"] == 1
        assert kpis["posted_gl_batches"] == 1
        assert kpis["total_gis_mappings"] == 1
        assert kpis["drifted_gis_mappings"] == 1

    @pytest.mark.parametrize(
        "label,expected_spec",
        [
            (
                "ERP Integration",
                "assets:asset_integration_connector_list?connector_category=erp_procurement",
            ),
            (
                "IoT & SCADA Systems",
                "assets:asset_telemetry_stream_list",
            ),
            (
                "CMMS/EAM Connectivity",
                "assets:asset_integration_connector_list?connector_category=cmms_eam",
            ),
            (
                "Financial Systems & General Ledger",
                "assets:asset_gl_sync_batch_list",
            ),
            (
                "GIS & Mapping Tools",
                "assets:asset_gis_mapping_list",
            ),
            (
                "Integration Connectors",
                "assets:asset_integration_connector_list",
            ),
        ],
    )
    def test_integration_api_hub_live_links_reverse_return_200_and_single_active_sidebar(
        self,
        client_a,
        label,
        expected_spec,
    ):
        assert LIVE_LINKS["11.15"][label] == expected_spec
        href = _integration_api_hub_reverse_live_link(expected_spec)

        response = client_a.get(href)
        assert response.status_code == 200
        html = response.content.decode("utf-8")
        active_labels, is_open = _integration_api_hub_extract_11_15_sidebar_active(html)
        assert is_open is True
        expected_html_label = label.replace("&", "&amp;")
        assert active_labels == [expected_html_label] or active_labels == [label]

        # Direct resolve_nav parity check
        if "?" in expected_spec:
            view_name, qs = expected_spec.split("?", 1)
            k, v = qs.split("=", 1)
            req = SimpleNamespace(
                resolver_match=SimpleNamespace(view_name=view_name),
                GET={k: v},
            )
        else:
            req = SimpleNamespace(
                resolver_match=SimpleNamespace(view_name=expected_spec),
                GET={},
            )
        sections = resolve_nav(req)
        assets_mod = next(
            s for s in sections if s.get("label") == "11. Asset Management System"
        )
        sub_11_15 = next(
            sub for sub in assets_mod["submodules"] if sub["label"].startswith("11.15")
        )
        assert sub_11_15["open"] is True
        active_feats = [f["label"] for f in sub_11_15["features"] if f["is_active"]]
        assert active_feats == [label]

    def test_integration_api_hub_subroutes_highlight_parent_sidebar_bullet_cleanly(
        self,
        client_a,
        integration_connector_a,
        integration_stream_a,
        integration_gl_batch_a,
        integration_gis_mapping_a,
    ):
        cases = [
            (
                reverse(
                    "assets:asset_integration_connector_detail",
                    args=[integration_connector_a.pk],
                ),
                "Integration Connectors",
            ),
            (
                reverse(
                    "assets:asset_telemetry_stream_detail",
                    args=[integration_stream_a.pk],
                ),
                "IoT & SCADA Systems",
            ),
            (
                reverse(
                    "assets:asset_gl_sync_batch_detail",
                    args=[integration_gl_batch_a.pk],
                ),
                "Financial Systems & General Ledger",
            ),
            (
                reverse(
                    "assets:asset_gis_mapping_detail",
                    args=[integration_gis_mapping_a.pk],
                ),
                "GIS & Mapping Tools",
            ),
        ]
        for url, expected_label in cases:
            resp = client_a.get(url)
            assert resp.status_code == 200
            active_labels, is_open = _integration_api_hub_extract_11_15_sidebar_active(
                resp.content.decode("utf-8")
            )
            assert is_open is True
            assert len(active_labels) == 1
            assert active_labels[0].replace("&amp;", "&") == expected_label


# ---------------------------------------------------------------------------
# 2. Connectors Views & Actions
# ---------------------------------------------------------------------------


class TestIntegrationApiHubConnectorViews:
    def test_integration_api_hub_connector_list_filters_kpis_empty_and_isolation(
        self,
        client_a,
        tenant_a,
        integration_connector_a,
        integration_connector_b,
    ):
        c_healthy = _integration_api_hub_make_connector(
            tenant_a,
            index=1,
            name="Kepware Healthy OPC-UA",
            connector_category="iot_scada",
            provider="kepware_opcua",
            status="active",
            health_status="healthy",
        )
        c_err = _integration_api_hub_make_connector(
            tenant_a,
            index=2,
            name="Maximo CMMS Gateway",
            connector_category="cmms_eam",
            provider="maximo_eam",
            status="error",
            health_status="unreachable",
            endpoint_url="https://maximo-sync.example.com/oslc",
        )
        c_paused = _integration_api_hub_make_connector(
            tenant_a,
            index=3,
            name="SAP S4 Production Feed",
            connector_category="erp_procurement",
            provider="sap_s4hana",
            status="paused",
            health_status="degraded",
            endpoint_url="https://sap-odata.example.com/v4",
        )

        # Unfiltered list + KPI counts scoped to tenant A only (integration_connector_a is active/unverified)
        resp = client_a.get(reverse("assets:asset_integration_connector_list"))
        assert resp.status_code == 200
        assert resp.context["total_count"] == 4
        assert resp.context["active_count"] == 2
        assert resp.context["healthy_count"] == 1
        assert resp.context["error_count"] == 1
        listed_pks = {c.pk for c in resp.context["connectors"]}
        assert listed_pks == {integration_connector_a.pk, c_healthy.pk, c_err.pk, c_paused.pk}
        assert integration_connector_b.pk not in listed_pks
        assert integration_connector_b.name not in resp.content.decode("utf-8")

        # Search query q matching endpoint_url
        resp_q = client_a.get(
            reverse("assets:asset_integration_connector_list"),
            {"q": "sap-odata.example.com"},
        )
        assert [c.pk for c in resp_q.context["connectors"]] == [c_paused.pk]
        assert resp_q.context["search_query"] == "sap-odata.example.com"

        # Individual and combined dropdown filters
        resp_cat = client_a.get(
            reverse("assets:asset_integration_connector_list"),
            {"connector_category": "cmms_eam", "provider": "maximo_eam"},
        )
        assert [c.pk for c in resp_cat.context["connectors"]] == [c_err.pk]

        resp_health = client_a.get(
            reverse("assets:asset_integration_connector_list"),
            {"status": "paused", "health_status": "degraded"},
        )
        assert [c.pk for c in resp_health.context["connectors"]] == [c_paused.pk]

        # Empty state when filter matches nothing
        resp_empty = client_a.get(
            reverse("assets:asset_integration_connector_list"),
            {"q": "nonexistent-connector-xyz"},
        )
        assert resp_empty.status_code == 200
        assert len(resp_empty.context["connectors"]) == 0
        assert "No asset integration connectors found" in resp_empty.content.decode("utf-8")

    def test_integration_api_hub_connector_list_pagination_and_query_preservation(
        self,
        client_a,
        tenant_a,
    ):
        for i in range(1, 28):
            _integration_api_hub_make_connector(
                tenant_a,
                index=100 + i,
                name=f"Paged Connector {i:02d}",
                status="active",
            )

        url = reverse("assets:asset_integration_connector_list")
        resp_p1 = client_a.get(url, {"status": "active"})
        assert resp_p1.status_code == 200
        assert resp_p1.context["is_paginated"] is True
        assert len(resp_p1.context["connectors"]) == 25

        resp_p2 = client_a.get(url, {"status": "active", "page": "2"})
        assert resp_p2.status_code == 200
        assert resp_p2.context["page_obj"].number == 2
        assert len(resp_p2.context["connectors"]) == 2
        html_p2 = resp_p2.content.decode("utf-8")
        assert "status=active" in html_p2

        # Out-of-bounds page clamps cleanly to last page (2)
        resp_p999 = client_a.get(url, {"status": "active", "page": "999"})
        assert resp_p999.status_code == 200
        assert resp_p999.context["page_obj"].number == 2

    def test_integration_api_hub_connector_create_edit_detail_and_no_initial_secret(
        self,
        client_a,
        tenant_a,
        admin_user,
        vendor_party_a,
        org_unit_a,
        currency_usd,
    ):
        create_url = reverse("assets:asset_integration_connector_create")
        get_resp = client_a.get(create_url)
        assert get_resp.status_code == 200
        assert get_resp.context["title"] == "New Integration Connector"
        assert get_resp.context["is_edit"] is False
        assert get_resp.context["connector"] is None

        # Invalid SSRF URL stays on form with 200 and does not save
        bad_payload = {
            "name": "Local Metadata Leak",
            "connector_category": "erp_procurement",
            "provider": "sap_s4hana",
            "protocol": "rest_json",
            "sync_direction": "bidirectional",
            "environment": "production",
            "endpoint_url": "http://127.0.0.1:8080/internal",
            "auth_method": "oauth2_client",
            "rate_limit_rpm": 60,
            "timeout_seconds": 30,
            "retry_policy_max": 3,
            "polling_interval_minutes": 15,
            "status": "active",
            "webhook_verify_tls": "on",
        }
        bad_resp = client_a.post(create_url, bad_payload)
        assert bad_resp.status_code == 200
        assert bad_resp.context["form"].errors.get("endpoint_url")
        assert not AssetIntegrationConnector.objects.filter(
            tenant=tenant_a, name="Local Metadata Leak"
        ).exists()

        # Valid create
        good_payload = dict(bad_payload)
        good_payload.update(
            {
                "name": "Oracle Fusion Cloud Asset Hub",
                "endpoint_url": "https://fusion-erp.example.com/fscmRestApi",
                "vendor_partner": vendor_party_a.pk,
                "default_org_unit": org_unit_a.pk,
                "default_currency": currency_usd.pk,
                "owner": admin_user.pk,
            }
        )
        post_resp = client_a.post(create_url, good_payload)
        assert post_resp.status_code == 302
        created = AssetIntegrationConnector.objects.get(
            tenant=tenant_a, name="Oracle Fusion Cloud Asset Hub"
        )
        detail_url = reverse(
            "assets:asset_integration_connector_detail", args=[created.pk]
        )
        assert post_resp.url == detail_url

        # Connector create intentionally does NOT mint or reveal a secret yet
        assert created.api_key_prefix == ""
        assert created.api_key_hash == ""
        assert "_aicn_secret_reveal" not in client_a.session
        msgs = _integration_api_hub_msg_texts(post_resp)
        assert all("aicn_" not in m for m in msgs)

        detail_resp = client_a.get(detail_url)
        assert detail_resp.status_code == 200
        assert detail_resp.context["plaintext_once"] is None
        detail_html = detail_resp.content.decode("utf-8")
        assert "Not rotated" in detail_html
        assert "revealed-secret-code" not in detail_html

        create_log = AuditLog.objects.filter(
            tenant=tenant_a, object_id=created.pk, action="create"
        ).first()
        assert create_log is not None
        assert len(create_log.action) <= 10

        # Edit connector
        edit_url = reverse(
            "assets:asset_integration_connector_edit", args=[created.pk]
        )
        assert client_a.get(edit_url).status_code == 200
        edit_payload = dict(good_payload)
        edit_payload["name"] = "Oracle Fusion Cloud Updated"
        edit_payload["status"] = "paused"
        edit_resp = client_a.post(edit_url, edit_payload)
        assert edit_resp.status_code == 302
        created.refresh_from_db()
        assert created.name == "Oracle Fusion Cloud Updated"
        assert created.status == "paused"
        assert AuditLog.objects.filter(
            tenant=tenant_a, object_id=created.pk, action="update"
        ).exists()

    def test_integration_api_hub_connector_delete_protected_and_clean(
        self,
        client_a,
        tenant_a,
        operational_asset_a,
    ):
        protected_conn = _integration_api_hub_make_connector(
            tenant_a, index=21, name="Protected Connector"
        )
        _integration_api_hub_make_stream(
            tenant_a, protected_conn, operational_asset_a, index=21
        )
        delete_url = reverse(
            "assets:asset_integration_connector_delete", args=[protected_conn.pk]
        )

        # GET rejected with 405
        assert client_a.get(delete_url).status_code == 405

        # ProtectedError preserves record AND rolls back delete AuditLog atomically
        resp_protected = client_a.post(delete_url)
        assert resp_protected.status_code == 302
        assert resp_protected.url == reverse(
            "assets:asset_integration_connector_detail", args=[protected_conn.pk]
        )
        assert AssetIntegrationConnector.objects.filter(pk=protected_conn.pk).exists()
        assert not AuditLog.objects.filter(
            tenant=tenant_a, object_id=protected_conn.pk, action="delete"
        ).exists()
        assert any("Cannot delete" in m for m in _integration_api_hub_msg_texts(resp_protected))

        # Unreferenced connector deletes cleanly and writes <=10 char AuditLog
        unreferenced = _integration_api_hub_make_connector(
            tenant_a, index=22, name="Disposable Connector"
        )
        unreferenced_pk = unreferenced.pk
        resp_deleted = client_a.post(
            reverse("assets:asset_integration_connector_delete", args=[unreferenced_pk])
        )
        assert resp_deleted.status_code == 302
        assert resp_deleted.url == reverse("assets:asset_integration_connector_list")
        assert not AssetIntegrationConnector.objects.filter(pk=unreferenced_pk).exists()
        del_log = AuditLog.objects.filter(
            tenant=tenant_a, object_id=unreferenced_pk, action="delete"
        ).first()
        assert del_log is not None
        assert len(del_log.action) <= 10

    def test_integration_api_hub_connector_test_connection_states_and_zero_http_calls(
        self,
        client_a,
        tenant_a,
        integration_connector_a,
    ):
        test_url = reverse(
            "assets:asset_integration_connector_test", args=[integration_connector_a.pk]
        )
        assert client_a.get(test_url).status_code == 405

        def _forbid_network(*args, **kwargs):
            raise AssertionError("test_connection must never perform outbound HTTP/socket calls")

        with (
            patch("urllib.request.urlopen", side_effect=_forbid_network),
            patch("urllib.request.Request", side_effect=_forbid_network),
            patch("socket.create_connection", side_effect=_forbid_network),
            patch("socket.socket", side_effect=_forbid_network),
        ):
            # 1) Active connector -> healthy
            integration_connector_a.consecutive_failures = 2
            integration_connector_a.last_error_message = "Old transient error"
            integration_connector_a.save(
                update_fields=["consecutive_failures", "last_error_message"]
            )
            r_active = client_a.post(test_url)
            assert r_active.status_code == 302
            integration_connector_a.refresh_from_db()
            assert integration_connector_a.health_status == "healthy"
            assert integration_connector_a.consecutive_failures == 0
            assert integration_connector_a.last_error_message == ""
            assert integration_connector_a.last_heartbeat_at is not None

            # 2) Paused connector -> degraded
            integration_connector_a.status = "paused"
            integration_connector_a.save(update_fields=["status"])
            r_paused = client_a.post(test_url)
            assert r_paused.status_code == 302
            integration_connector_a.refresh_from_db()
            assert integration_connector_a.health_status == "degraded"

            # 3) Legacy/invalid endpoint in DB -> unreachable + consecutive_failures += 1
            AssetIntegrationConnector.objects.filter(
                pk=integration_connector_a.pk
            ).update(
                endpoint_url="http://169.254.169.254/latest/meta-data",
                status="active",
                consecutive_failures=1,
            )
            r_bad = client_a.post(test_url)
            assert r_bad.status_code == 302
            integration_connector_a.refresh_from_db()
            assert integration_connector_a.health_status == "unreachable"
            assert integration_connector_a.consecutive_failures == 2
            assert integration_connector_a.last_error_message != ""

        assert AuditLog.objects.filter(
            tenant=tenant_a,
            object_id=integration_connector_a.pk,
            action="test",
        ).count() == 3

    def test_integration_api_hub_connector_rotate_secret_one_time_pop_and_role_gate(
        self,
        client_a,
        member_client,
        tenant_a,
        integration_connector_a,
    ):
        other_connector = _integration_api_hub_make_connector(
            tenant_a, index=31, name="Second Connector"
        )
        rotate_url = reverse(
            "assets:asset_integration_connector_rotate_secret",
            args=[integration_connector_a.pk],
        )
        detail_a_url = reverse(
            "assets:asset_integration_connector_detail",
            args=[integration_connector_a.pk],
        )
        detail_b_url = reverse(
            "assets:asset_integration_connector_detail",
            args=[other_connector.pk],
        )

        # GET rejected with 405
        assert client_a.get(rotate_url).status_code == 405

        # Non-admin member cannot rotate secret
        prev_hash = integration_connector_a.api_key_hash
        member_resp = member_client.post(rotate_url)
        assert member_resp.status_code in (302, 403)
        integration_connector_a.refresh_from_db()
        assert integration_connector_a.api_key_hash == prev_hash

        # Admin rotates secret: stored as SHA-256 hex, displayed once in banner
        rot_resp = client_a.post(rotate_url)
        assert rot_resp.status_code == 302
        integration_connector_a.refresh_from_db()
        assert integration_connector_a.api_key_prefix.startswith("aicn_")
        assert len(integration_connector_a.api_key_hash) == 64

        reveal_data = client_a.session.get("_aicn_secret_reveal")
        assert isinstance(reveal_data, dict)
        assert reveal_data["pk"] == integration_connector_a.pk
        plaintext = reveal_data["secret"]
        assert plaintext.startswith(integration_connector_a.api_key_prefix)
        assert (
            hashlib.sha256(plaintext.encode("utf-8")).hexdigest()
            == integration_connector_a.api_key_hash
        )

        # Plaintext must NEVER appear in flash messages
        msgs = _integration_api_hub_msg_texts(rot_resp)
        assert any(integration_connector_a.api_key_prefix in m for m in msgs)
        assert all(plaintext not in m for m in msgs)

        assert AuditLog.objects.filter(
            tenant=tenant_a, object_id=integration_connector_a.pk, action="rotate"
        ).exists()

        # First detail view reveals secret once with Copy button and clears session key
        first_detail = client_a.get(detail_a_url)
        assert first_detail.status_code == 200
        assert first_detail.context["plaintext_once"] == plaintext
        first_html = first_detail.content.decode("utf-8")
        assert re.search(
            rf'<code[^>]*id="revealed-secret-code"[^>]*>{re.escape(plaintext)}</code>',
            first_html,
        )
        assert 'id="copy-secret-btn"' in first_html
        assert "_aicn_secret_reveal" not in client_a.session

        # Second detail view does NOT reveal secret
        second_detail = client_a.get(detail_a_url)
        assert second_detail.context["plaintext_once"] is None
        assert plaintext not in second_detail.content.decode("utf-8")
        assert "revealed-secret-code" not in second_detail.content.decode("utf-8")

        # Unconditional pop edge case: rotating A then visiting B pops A's reveal cleanly
        client_a.post(rotate_url)
        plaintext_2 = client_a.session["_aicn_secret_reveal"]["secret"]
        visit_other = client_a.get(detail_b_url)
        assert visit_other.status_code == 200
        assert visit_other.context["plaintext_once"] is None
        assert plaintext_2 not in visit_other.content.decode("utf-8")
        assert "_aicn_secret_reveal" not in client_a.session
        visit_a_after = client_a.get(detail_a_url)
        assert visit_a_after.context["plaintext_once"] is None
        assert plaintext_2 not in visit_a_after.content.decode("utf-8")


# ---------------------------------------------------------------------------
# 3. Telemetry Streams Views & 11.7 / 11.5 Cross-Module Ingestion
# ---------------------------------------------------------------------------


class TestIntegrationApiHubTelemetryStreamViews:
    def test_integration_api_hub_stream_list_filters_unicode_bigint_and_create_prefill(
        self,
        client_a,
        tenant_a,
        operational_asset_a,
        integration_connector_a,
        integration_connector_b,
        integration_stream_a,
        integration_stream_b,
    ):
        faulted = _integration_api_hub_make_stream(
            tenant_a,
            integration_connector_a,
            operational_asset_a,
            index=2,
            stream_name="Hydraulic Fault Tag",
            tag_address="mqtt/line2/press",
            stream_protocol="mqtt_topic",
            stream_status="faulted",
            auto_trigger_maintenance=False,
        )

        list_url = reverse("assets:asset_telemetry_stream_list")
        resp = client_a.get(list_url)
        assert resp.status_code == 200
        assert resp.context["total_count"] == 2
        assert resp.context["active_count"] == 1
        assert resp.context["faulted_count"] == 1
        assert resp.context["auto_cbm_count"] == 1
        pks = {s.pk for s in resp.context["streams"]}
        assert pks == {integration_stream_a.pk, faulted.pk}
        assert integration_stream_b.pk not in pks

        # Filters: q, connector, operational_asset, stream_protocol, stream_status
        resp_filtered = client_a.get(
            list_url,
            {
                "q": "mqtt/line2",
                "connector": str(integration_connector_a.pk),
                "operational_asset": str(operational_asset_a.pk),
                "stream_protocol": "mqtt_topic",
                "stream_status": "faulted",
            },
        )
        assert [s.pk for s in resp_filtered.context["streams"]] == [faulted.pk]

        # Empty state
        resp_empty = client_a.get(list_url, {"q": "missing-stream-xyz"})
        assert resp_empty.status_code == 200
        assert len(resp_empty.context["streams"]) == 0

        # Safe handling of Unicode superscript, zero, negative, and huge bigint
        for bad_param in ("\u00b2", "99999999999999999999999", "0", "-5"):
            r1 = client_a.get(list_url, {"connector": bad_param})
            assert r1.status_code == 200
            r2 = client_a.get(list_url, {"operational_asset": bad_param})
            assert r2.status_code == 200

        # Verified ?connector= prefill on stream_create (ignores foreign tenant & junk)
        create_url = reverse("assets:asset_telemetry_stream_create")
        r_prefill = client_a.get(create_url, {"connector": str(integration_connector_a.pk)})
        assert r_prefill.status_code == 200
        assert r_prefill.context["form"].initial.get("connector") == integration_connector_a.pk

        r_foreign = client_a.get(create_url, {"connector": str(integration_connector_b.pk)})
        assert r_foreign.status_code == 200
        assert "connector" not in r_foreign.context["form"].initial

        r_unicode = client_a.get(create_url, {"connector": "\u00b2"})
        assert r_unicode.status_code == 200
        assert "connector" not in r_unicode.context["form"].initial

    def test_integration_api_hub_stream_list_pagination_and_query_preservation(
        self,
        client_a,
        tenant_a,
        integration_connector_a,
        operational_asset_a,
    ):
        for i in range(1, 28):
            _integration_api_hub_make_stream(
                tenant_a,
                integration_connector_a,
                operational_asset_a,
                index=200 + i,
                stream_status="active",
            )
        url = reverse("assets:asset_telemetry_stream_list")
        resp_p2 = client_a.get(url, {"stream_status": "active", "page": "2"})
        assert resp_p2.status_code == 200
        assert resp_p2.context["page_obj"].number == 2
        assert len(resp_p2.context["streams"]) == 2
        assert "stream_status=active" in resp_p2.content.decode("utf-8")

        resp_p999 = client_a.get(url, {"page": "999"})
        assert resp_p999.status_code == 200
        assert resp_p999.context["page_obj"].number == 2

    def test_integration_api_hub_stream_create_edit_delete_and_zero_threshold_detail(
        self,
        client_a,
        tenant_a,
        integration_connector_a,
        operational_asset_a,
        fixed_asset_a,
        admin_user,
    ):
        create_url = reverse("assets:asset_telemetry_stream_create")
        payload = {
            "connector": integration_connector_a.pk,
            "operational_asset": operational_asset_a.pk,
            "fixed_asset": fixed_asset_a.pk,
            "tag_address": "ns=2;s=SubZero.Chamber.Temp",
            "stream_name": "Cryo Chamber Zero Threshold",
            "stream_protocol": "opc_ua_node",
            "metric_type": "bearing_temperature",
            "metric_unit": "celsius",
            "ingestion_mode": "polling",
            "polling_interval_seconds": 15,
            "deadband_delta": "0.0000",
            "scale_factor": "1.000000",
            "offset_value": "0.0000",
            "baseline_value": "0.0000",
            "warning_threshold": "0.0000",
            "critical_threshold": "0.0000",
            "auto_trigger_maintenance": "on",
            "stream_status": "active",
            "steward": admin_user.pk,
        }
        create_resp = client_a.post(create_url, payload)
        assert create_resp.status_code == 302
        stream = AssetTelemetryStream.objects.get(
            tenant=tenant_a, stream_name="Cryo Chamber Zero Threshold"
        )
        detail_url = reverse("assets:asset_telemetry_stream_detail", args=[stream.pk])
        assert create_resp.url == detail_url
        assert AuditLog.objects.filter(
            tenant=tenant_a, object_id=stream.pk, action="create"
        ).exists()

        # Verify 0.0000 thresholds render explicitly (not "—" or "25.0000") and asset links work
        detail_resp = client_a.get(detail_url)
        assert detail_resp.status_code == 200
        html = detail_resp.content.decode("utf-8")
        assert html.count("0.0000") >= 4
        assert "0.0000 / 0.0000 / 0.0000" in html
        assert 'placeholder="0.0000"' in html
        assert 'placeholder="25.0000"' not in html
        assert reverse("scm:asset_detail", args=[operational_asset_a.pk]) in html
        assert reverse("accounting:fixed_asset_detail", args=[fixed_asset_a.pk]) in html

        # Edit stream
        edit_url = reverse("assets:asset_telemetry_stream_edit", args=[stream.pk])
        assert client_a.get(edit_url).status_code == 200
        edit_payload = dict(payload)
        edit_payload["stream_name"] = "Cryo Chamber Renamed"
        edit_resp = client_a.post(edit_url, edit_payload)
        assert edit_resp.status_code == 302
        stream.refresh_from_db()
        assert stream.stream_name == "Cryo Chamber Renamed"
        assert AuditLog.objects.filter(
            tenant=tenant_a, object_id=stream.pk, action="update"
        ).exists()

        # Delete stream
        del_url = reverse("assets:asset_telemetry_stream_delete", args=[stream.pk])
        assert client_a.get(del_url).status_code == 405
        del_resp = client_a.post(del_url)
        assert del_resp.status_code == 302
        assert not AssetTelemetryStream.objects.filter(pk=stream.pk).exists()
        assert AuditLog.objects.filter(
            tenant=tenant_a, object_id=stream.pk, action="delete"
        ).exists()

    def test_integration_api_hub_ingest_sample_reading_sources_fallbacks_math_and_mapping(
        self,
        client_a,
        tenant_a,
        operational_asset_a,
        fixed_asset_a,
    ):
        scada_conn = _integration_api_hub_make_connector(
            tenant_a, index=41, connector_category="iot_scada"
        )
        erp_conn = _integration_api_hub_make_connector(
            tenant_a,
            index=42,
            connector_category="cmms_eam",
            provider="maximo_eam",
            protocol="rest_json",
        )

        # 1) Blank raw_value -> warning_threshold (0.0000 beats baseline_value) -> scada_historian + math
        s1 = _integration_api_hub_make_stream(
            tenant_a,
            scada_conn,
            operational_asset_a,
            index=41,
            fixed_asset=fixed_asset_a,
            metric_type="runtime_hours",
            metric_unit="hours",
            scale_factor=Decimal("2.000000"),
            offset_value=Decimal("10.5000"),
            baseline_value=Decimal("5.0000"),
            warning_threshold=Decimal("0.0000"),
            critical_threshold=Decimal("20.0000"),
        )
        ingest_url_1 = reverse("assets:asset_telemetry_stream_ingest", args=[s1.pk])
        assert client_a.get(ingest_url_1).status_code == 405

        r1 = client_a.post(ingest_url_1, {"raw_value": ""})
        assert r1.status_code == 302
        s1.refresh_from_db()
        rd1 = s1.last_telemetry_reading
        assert rd1 is not None
        # Blank fell back to warning_threshold=0.0000 -> (0 * 2) + 10.5 = 10.5000
        assert rd1.reading_value == Decimal("10.5000")
        assert rd1.source == "scada_historian"
        # resolve_telemetry_metric_and_unit: runtime_hours maps to motor_current_amperage / amperes in 11.7
        assert rd1.metric_type == "motor_current_amperage"
        assert rd1.metric_unit == "amperes"
        assert AuditLog.objects.filter(
            tenant=tenant_a, object_id=s1.pk, action="ingest"
        ).exists()

        # 2) Blank raw_value -> baseline_value fallback + bearing_temperature + hours -> celsius fallback + iot_sensor
        s2 = _integration_api_hub_make_stream(
            tenant_a,
            erp_conn,
            operational_asset_a,
            index=42,
            metric_type="bearing_temperature",
            metric_unit="hours",
            scale_factor=Decimal("1.500000"),
            offset_value=Decimal("-5.0000"),
            baseline_value=Decimal("20.0000"),
            warning_threshold=None,
            critical_threshold=None,
        )
        r2 = client_a.post(
            reverse("assets:asset_telemetry_stream_ingest", args=[s2.pk]),
            {"raw_value": ""},
        )
        assert r2.status_code == 302
        s2.refresh_from_db()
        rd2 = s2.last_telemetry_reading
        assert rd2.reading_value == Decimal("25.0000")  # (20 * 1.5) - 5
        assert rd2.source == "iot_sensor"
        assert rd2.metric_type == "bearing_temperature"
        assert rd2.metric_unit == "celsius"

        # 3) Blank raw_value -> default Decimal("25.0000") when both thresholds & baseline are None
        s3 = _integration_api_hub_make_stream(
            tenant_a,
            erp_conn,
            operational_asset_a,
            index=43,
            baseline_value=None,
            warning_threshold=None,
            critical_threshold=None,
        )
        r3 = client_a.post(
            reverse("assets:asset_telemetry_stream_ingest", args=[s3.pk]),
            {"raw_value": "   "},
        )
        assert r3.status_code == 302
        s3.refresh_from_db()
        assert s3.last_telemetry_reading.reading_value == Decimal("25.0000")

    def test_integration_api_hub_ingest_sample_reading_deadband_and_zero_threshold_normal(
        self,
        client_a,
        tenant_a,
        integration_connector_a,
        operational_asset_a,
    ):
        # warning_threshold=0.0000, critical=10.0000, baseline=5.0000, deadband=2.0000
        stream = _integration_api_hub_make_stream(
            tenant_a,
            integration_connector_a,
            operational_asset_a,
            index=51,
            deadband_delta=Decimal("2.0000"),
            baseline_value=Decimal("5.0000"),
            warning_threshold=Decimal("0.0000"),
            critical_threshold=Decimal("10.0000"),
        )
        ingest_url = reverse("assets:asset_telemetry_stream_ingest", args=[stream.pk])

        # First reading -1.0000 < warning_threshold (0.0000) -> MUST preserve "normal" even though diff from baseline 5.0000 is 120%
        resp_normal = client_a.post(ingest_url, {"raw_value": "-1.0000"})
        assert resp_normal.status_code == 302
        stream.refresh_from_db()
        rd_normal = stream.last_telemetry_reading
        assert rd_normal.reading_value == Decimal("-1.0000")
        assert rd_normal.threshold_status == "normal"
        assert stream.readings_ingested_count == 1

        # Second reading -0.5000 is within deadband_delta 2.0000 (|-0.5 - (-1.0)| = 0.5 < 2.0) -> skipped!
        prev_count = AssetTelemetryReading.objects.filter(tenant=tenant_a).count()
        resp_deadband = client_a.post(ingest_url, {"raw_value": "-0.5000"})
        assert resp_deadband.status_code == 302
        assert AssetTelemetryReading.objects.filter(tenant=tenant_a).count() == prev_count
        stream.refresh_from_db()
        assert stream.readings_ingested_count == 1
        assert stream.last_ingested_value == Decimal("-1.0000")
        assert any("deadband" in m.lower() for m in _integration_api_hub_msg_texts(resp_deadband))

    def test_integration_api_hub_ingest_sample_reading_critical_cbm_creates_and_reuses_open_mr(
        self,
        client_a,
        tenant_a,
        integration_connector_a,
        operational_asset_a,
        fixed_asset_a,
    ):
        stream = _integration_api_hub_make_stream(
            tenant_a,
            integration_connector_a,
            operational_asset_a,
            index=61,
            fixed_asset=fixed_asset_a,
            warning_threshold=Decimal("70.0000"),
            critical_threshold=Decimal("90.0000"),
            auto_trigger_maintenance=True,
        )
        ingest_url = reverse("assets:asset_telemetry_stream_ingest", args=[stream.pk])

        # First critical reading creates one breakdown AssetMaintenanceRequest
        resp1 = client_a.post(ingest_url, {"raw_value": "95.0000"})
        assert resp1.status_code == 302
        stream.refresh_from_db()
        mr1 = stream.latest_maintenance_request
        assert mr1 is not None
        assert mr1.request_type == "breakdown_repair"
        assert mr1.urgency == "critical"
        assert mr1.is_breakdown is True
        assert mr1.status == "submitted"
        assert stream.last_telemetry_reading.threshold_status == "critical"
        assert stream.last_telemetry_reading.triggered_maintenance_request == mr1
        mr_count_after_first = AssetMaintenanceRequest.objects.filter(tenant=tenant_a).count()

        # Second critical reading while mr1 is open reuses mr1 without creating a duplicate
        resp2 = client_a.post(ingest_url, {"raw_value": "99.0000"})
        assert resp2.status_code == 302
        assert AssetMaintenanceRequest.objects.filter(tenant=tenant_a).count() == mr_count_after_first
        assert any(mr1.number in m for m in _integration_api_hub_msg_texts(resp2))
        stream.refresh_from_db()
        assert stream.latest_maintenance_request == mr1

        # Once prior MR is closed, another critical reading creates a new MR
        mr1.status = "closed"
        mr1.save(update_fields=["status"])
        resp3 = client_a.post(ingest_url, {"raw_value": "102.0000"})
        assert resp3.status_code == 302
        assert AssetMaintenanceRequest.objects.filter(tenant=tenant_a).count() == mr_count_after_first + 1
        stream.refresh_from_db()
        assert stream.latest_maintenance_request != mr1

    def test_integration_api_hub_ingest_sample_reading_rejects_inactive_and_malformed_inputs(
        self,
        client_a,
        tenant_a,
        integration_connector_a,
        operational_asset_a,
    ):
        for inactive_status in ("paused", "faulted", "decommissioned"):
            inactive_stream = _integration_api_hub_make_stream(
                tenant_a,
                integration_connector_a,
                operational_asset_a,
                index=70 + hash(inactive_status) % 20,
                tag_address=f"ns=2;s=Inactive.{inactive_status}",
                stream_status=inactive_status,
            )
            before = AssetTelemetryReading.objects.filter(tenant=tenant_a).count()
            resp = client_a.post(
                reverse("assets:asset_telemetry_stream_ingest", args=[inactive_stream.pk]),
                {"raw_value": "50.0000"},
            )
            assert resp.status_code == 302
            assert AssetTelemetryReading.objects.filter(tenant=tenant_a).count() == before
            assert any(
                "must be active" in m.lower() for m in _integration_api_hub_msg_texts(resp)
            )

        active_stream = _integration_api_hub_make_stream(
            tenant_a,
            integration_connector_a,
            operational_asset_a,
            index=79,
            scale_factor=Decimal("1000.000000"),
        )
        ingest_url = reverse("assets:asset_telemetry_stream_ingest", args=[active_stream.pk])
        bad_inputs = [
            "1e50",
            "9999999999.0",
            "NaN",
            "Infinity",
            "-Infinity",
            "abc",
            "1" * 40,
            "1000000",  # exceeds 99,999,999.9999 once multiplied by scale_factor 1000
        ]
        before = AssetTelemetryReading.objects.filter(tenant=tenant_a).count()
        for bad_raw in bad_inputs:
            resp = client_a.post(ingest_url, {"raw_value": bad_raw})
            assert resp.status_code == 302
            assert resp.url == reverse(
                "assets:asset_telemetry_stream_detail", args=[active_stream.pk]
            )
            assert AssetTelemetryReading.objects.filter(tenant=tenant_a).count() == before
            msgs = _integration_api_hub_msg_texts(resp)
            assert len(msgs) >= 1


# ---------------------------------------------------------------------------
# 4. GL Sync Batches Views & 2.1 GL Posting
# ---------------------------------------------------------------------------


class TestIntegrationApiHubGlSyncBatchViews:
    def test_integration_api_hub_batch_list_filters_dates_unicode_pagination_and_prefill(
        self,
        client_a,
        tenant_a,
        integration_connector_a,
        integration_connector_b,
        integration_gl_batch_a,
        integration_gl_batch_b,
    ):
        b_draft = _integration_api_hub_make_batch(
            tenant_a,
            integration_connector_a,
            index=1,
            external_batch_ref="DRAFT-CHECK-01",
            batch_date=datetime.date(2026, 6, 15),
            status="draft",
            reconciliation_status="pending",
        )
        b_posted = _integration_api_hub_make_batch(
            tenant_a,
            integration_connector_a,
            index=2,
            sync_domain="capitalization_sync",
            external_batch_ref="SAP-CAP-2026-09",
            batch_date=datetime.date(2026, 7, 20),
            status="posted",
            reconciliation_status="reconciled",
        )
        b_var = _integration_api_hub_make_batch(
            tenant_a,
            integration_connector_a,
            index=3,
            sync_domain="work_order_cost_rollup",
            external_batch_ref="VAR-CHECK-01",
            batch_date=datetime.date(2026, 8, 5),
            source_amount=Decimal("500.00"),
            target_gl_amount=Decimal("450.00"),
            status="simulated",
            reconciliation_status="variance_flagged",
        )

        list_url = reverse("assets:asset_gl_sync_batch_list")
        resp = client_a.get(list_url)
        assert resp.status_code == 200
        assert resp.context["total_count"] == 4
        assert resp.context["posted_count"] == 1
        assert resp.context["variance_count"] == 1
        assert resp.context["draft_count"] == 1
        pks = {b.pk for b in resp.context["batches"]}
        assert {integration_gl_batch_a.pk, b_draft.pk, b_posted.pk, b_var.pk} == pks
        assert integration_gl_batch_b.pk not in pks

        # Search + domain + status + reconciliation + date_from/date_to
        r_filtered = client_a.get(
            list_url,
            {
                "q": "SAP-CAP",
                "connector": str(integration_connector_a.pk),
                "sync_domain": "capitalization_sync",
                "status": "posted",
                "reconciliation_status": "reconciled",
                "date_from": "2026-07-01",
                "date_to": "2026-07-31",
            },
        )
        assert [b.pk for b in r_filtered.context["batches"]] == [b_posted.pk]

        # Bounded August range isolates b_var strictly regardless of today's date; invalid date_to ignored cleanly
        r_aug = client_a.get(
            list_url, {"date_from": "2026-08-01", "date_to": "2026-08-31"}
        )
        assert r_aug.status_code == 200
        assert [b.pk for b in r_aug.context["batches"]] == [b_var.pk]

        r_bad_date = client_a.get(
            list_url, {"date_from": "2026-08-01", "date_to": "not-a-date"}
        )
        assert r_bad_date.status_code == 200
        bad_date_pks = {b.pk for b in r_bad_date.context["batches"]}
        assert b_var.pk in bad_date_pks
        assert b_draft.pk not in bad_date_pks
        assert b_posted.pk not in bad_date_pks

        # Empty state & Unicode/bigint safety
        assert len(client_a.get(list_url, {"q": "no-batch-xyz"}).context["batches"]) == 0
        for bad_conn in ("\u00b2", "99999999999999999999999"):
            assert client_a.get(list_url, {"connector": bad_conn}).status_code == 200

        # Verified ?connector= prefill
        create_url = reverse("assets:asset_gl_sync_batch_create")
        assert (
            client_a.get(create_url, {"connector": str(integration_connector_a.pk)})
            .context["form"]
            .initial.get("connector")
            == integration_connector_a.pk
        )
        assert (
            "connector"
            not in client_a.get(
                create_url, {"connector": str(integration_connector_b.pk)}
            )
            .context["form"]
            .initial
        )

        # Pagination (?page=2, ?page=999, query preservation)
        for i in range(10, 36):
            _integration_api_hub_make_batch(
                tenant_a, integration_connector_a, index=i, status="draft"
            )
        r_p2 = client_a.get(list_url, {"status": "draft", "page": "2"})
        assert r_p2.status_code == 200
        assert r_p2.context["page_obj"].number == 2
        assert "status=draft" in r_p2.content.decode("utf-8")
        assert client_a.get(list_url, {"page": "999"}).status_code == 200

    def test_integration_api_hub_batch_create_edit_delete_and_detail_cross_module_links(
        self,
        client_a,
        tenant_a,
        integration_connector_a,
        integration_open_fiscal_period_a,
        asset_account_a,
        expense_account_a,
        accum_account_a,
        fixed_asset_a,
        operational_asset_a,
        po_a,
        capitalization_a,
        maintenance_request_a,
        org_unit_a,
        currency_usd,
    ):
        dep_sched = _integration_api_hub_make_depreciation_schedule(
            tenant_a,
            fixed_asset_a,
            operational_asset_a,
            expense_account_a,
            accum_account_a,
            index=1,
        )
        create_url = reverse("assets:asset_gl_sync_batch_create")
        payload = {
            "connector": integration_connector_a.pk,
            "sync_domain": "depreciation_posting",
            "sync_direction": "outbound",
            "external_batch_ref": "SAP-BELNR-881",
            "fiscal_period": integration_open_fiscal_period_a.pk,
            "gl_account": expense_account_a.pk,
            "offset_gl_account": asset_account_a.pk,
            "fixed_asset": fixed_asset_a.pk,
            "purchase_order": po_a.pk,
            "capitalization": capitalization_a.pk,
            "depreciation_schedule": dep_sched.pk,
            "maintenance_request": maintenance_request_a.pk,
            "cost_center": org_unit_a.pk,
            "currency": currency_usd.pk,
            "batch_date": integration_open_fiscal_period_a.start_date.isoformat(),
            "source_amount": "2400.00",
            "target_gl_amount": "2400.00",
            "field_mapping_json": '{"account": "6100-A"}',
            "payload_summary": "Cross-module linked GL sync batch",
        }
        c_resp = client_a.post(create_url, payload)
        assert c_resp.status_code == 302
        batch = AssetGlSyncBatch.objects.get(
            tenant=tenant_a, external_batch_ref="SAP-BELNR-881"
        )
        assert AuditLog.objects.filter(
            tenant=tenant_a, object_id=batch.pk, action="create"
        ).exists()

        # Attach a posted JE temporarily or execute reconcile? First check edit happy path while still draft
        edit_url = reverse("assets:asset_gl_sync_batch_edit", args=[batch.pk])
        assert client_a.get(edit_url).status_code == 200
        edit_payload = dict(payload)
        edit_payload["payload_summary"] = "Updated cross-module summary"
        assert client_a.post(edit_url, edit_payload).status_code == 302
        batch.refresh_from_db()
        assert batch.payload_summary == "Updated cross-module summary"
        assert AuditLog.objects.filter(
            tenant=tenant_a, object_id=batch.pk, action="update"
        ).exists()

        # Post via reconcile so journal_entry link is also rendered alongside all 5 other FKs
        client_a.post(reverse("assets:asset_gl_sync_batch_execute", args=[batch.pk]))
        batch.refresh_from_db()
        assert batch.journal_entry is not None

        detail_html = client_a.get(
            reverse("assets:asset_gl_sync_batch_detail", args=[batch.pk])
        ).content.decode("utf-8")
        assert reverse("scm:purchaseorder_detail", args=[po_a.pk]) in detail_html
        assert reverse("accounting:journal_entry_detail", args=[batch.journal_entry.pk]) in detail_html
        assert reverse("accounting:fixed_asset_detail", args=[fixed_asset_a.pk]) in detail_html
        assert reverse("assets:asset_capitalization_detail", args=[capitalization_a.pk]) in detail_html
        assert reverse("assets:depreciation_schedule_detail", args=[dep_sched.pk]) in detail_html
        assert reverse("assets:asset_maintenance_request_detail", args=[maintenance_request_a.pk]) in detail_html

        # Delete happy path on separate unposted batch
        disposable = _integration_api_hub_make_batch(tenant_a, integration_connector_a, index=88)
        del_url = reverse("assets:asset_gl_sync_batch_delete", args=[disposable.pk])
        assert client_a.get(del_url).status_code == 405
        assert client_a.post(del_url).status_code == 302
        assert not AssetGlSyncBatch.objects.filter(pk=disposable.pk).exists()
        assert AuditLog.objects.filter(
            tenant=tenant_a, object_id=disposable.pk, action="delete"
        ).exists()

    def test_integration_api_hub_execute_reconcile_batch_creates_balanced_je_and_idempotent(
        self,
        client_a,
        tenant_a,
        integration_connector_a,
        integration_open_fiscal_period_a,
        expense_account_a,
        asset_account_a,
        org_unit_a,
        currency_usd,
    ):
        batch = _integration_api_hub_make_batch(
            tenant_a,
            integration_connector_a,
            index=101,
            sync_domain="depreciation_posting",
            fiscal_period=integration_open_fiscal_period_a,
            gl_account=expense_account_a,
            offset_gl_account=asset_account_a,
            cost_center=org_unit_a,
            currency=currency_usd,
            batch_date=integration_open_fiscal_period_a.start_date,
            source_amount=Decimal("3250.75"),
            target_gl_amount=Decimal("3250.75"),
            status="ready",
        )
        exec_url = reverse("assets:asset_gl_sync_batch_execute", args=[batch.pk])

        je_before = JournalEntry.objects.filter(tenant=tenant_a).count()
        r1 = client_a.post(exec_url)
        assert r1.status_code == 302
        assert JournalEntry.objects.filter(tenant=tenant_a).count() == je_before + 1

        batch.refresh_from_db()
        assert batch.status == "posted"
        assert batch.reconciliation_status == "reconciled"
        assert batch.synced_at is not None
        assert batch.executed_by is not None

        je = batch.journal_entry
        assert je is not None
        assert je.entry_type == "recurring"
        assert je.status == "posted"
        assert je.fiscal_period == integration_open_fiscal_period_a
        assert je.entry_date == batch.batch_date
        assert je.is_balanced() is True

        lines = list(JournalLine.objects.filter(entry=je).order_by("id"))
        assert len(lines) == 2
        assert lines[0].gl_account == expense_account_a
        assert lines[0].debit == Decimal("3250.75")
        assert lines[0].credit == Decimal("0.00")
        assert lines[1].gl_account == asset_account_a
        assert lines[1].debit == Decimal("0.00")
        assert lines[1].credit == Decimal("3250.75")
        assert AuditLog.objects.filter(
            tenant=tenant_a, object_id=batch.pk, action="reconcile"
        ).exists()

        # Idempotent second POST creates zero duplicate JEs or lines
        r2 = client_a.post(exec_url)
        assert r2.status_code == 302
        assert JournalEntry.objects.filter(tenant=tenant_a).count() == je_before + 1
        assert JournalLine.objects.filter(entry=je).count() == 2
        assert any("already posted" in m.lower() for m in _integration_api_hub_msg_texts(r2))

    def test_integration_api_hub_posted_batch_locks_edit_delete_and_hides_controls(
        self,
        client_a,
        tenant_a,
        integration_connector_a,
        integration_open_fiscal_period_a,
        expense_account_a,
        asset_account_a,
    ):
        batch = _integration_api_hub_make_batch(
            tenant_a,
            integration_connector_a,
            index=102,
            sync_domain="work_order_cost_rollup",
            fiscal_period=integration_open_fiscal_period_a,
            gl_account=expense_account_a,
            offset_gl_account=asset_account_a,
            batch_date=integration_open_fiscal_period_a.start_date,
            source_amount=Decimal("900.00"),
            target_gl_amount=Decimal("900.00"),
            status="draft",
        )
        client_a.post(reverse("assets:asset_gl_sync_batch_execute", args=[batch.pk]))
        batch.refresh_from_db()
        assert batch.status == "posted"

        detail_url = reverse("assets:asset_gl_sync_batch_detail", args=[batch.pk])
        edit_url = reverse("assets:asset_gl_sync_batch_edit", args=[batch.pk])
        del_url = reverse("assets:asset_gl_sync_batch_delete", args=[batch.pk])
        exec_url = reverse("assets:asset_gl_sync_batch_execute", args=[batch.pk])

        # Edit GET & POST blocked
        r_edit_get = client_a.get(edit_url)
        assert r_edit_get.status_code == 302
        assert r_edit_get.url == detail_url
        assert any("cannot edit" in m.lower() and "posted" in m.lower() for m in _integration_api_hub_msg_texts(r_edit_get))

        r_edit_post = client_a.post(edit_url, {"external_batch_ref": "TAMPERED"})
        assert r_edit_post.status_code == 302
        assert r_edit_post.url == detail_url
        batch.refresh_from_db()
        assert batch.external_batch_ref != "TAMPERED"

        # Delete POST blocked
        r_del_post = client_a.post(del_url)
        assert r_del_post.status_code == 302
        assert r_del_post.url == detail_url
        assert AssetGlSyncBatch.objects.filter(pk=batch.pk).exists()
        assert any("cannot delete" in m.lower() and "posted" in m.lower() for m in _integration_api_hub_msg_texts(r_del_post))

        # Detail HTML hides Edit link, Delete action, and Execute button
        detail_html = client_a.get(detail_url).content.decode("utf-8")
        assert edit_url not in detail_html
        assert f'action="{del_url}"' not in detail_html
        assert f'action="{exec_url}"' not in detail_html

    def test_integration_api_hub_execute_reconcile_guards_failed_closed_variance_non_posting(
        self,
        client_a,
        member_client,
        tenant_a,
        integration_connector_a,
        integration_open_fiscal_period_a,
        integration_closed_fiscal_period_a,
        expense_account_a,
        asset_account_a,
    ):
        je_initial = JournalEntry.objects.filter(tenant=tenant_a).count()

        # Member client rejected by @tenant_admin_required
        b_perm = _integration_api_hub_make_batch(
            tenant_a,
            integration_connector_a,
            index=110,
            fiscal_period=integration_open_fiscal_period_a,
            gl_account=expense_account_a,
            offset_gl_account=asset_account_a,
        )
        assert client_a.get(reverse("assets:asset_gl_sync_batch_execute", args=[b_perm.pk])).status_code == 405
        assert member_client.post(reverse("assets:asset_gl_sync_batch_execute", args=[b_perm.pk])).status_code in (302, 403)
        assert JournalEntry.objects.filter(tenant=tenant_a).count() == je_initial

        # 1) Failed batch rejected
        b_failed = _integration_api_hub_make_batch(
            tenant_a,
            integration_connector_a,
            index=111,
            status="failed",
            gl_account=expense_account_a,
            offset_gl_account=asset_account_a,
        )
        r_failed = client_a.post(
            reverse("assets:asset_gl_sync_batch_execute", args=[b_failed.pk])
        )
        assert r_failed.status_code == 302
        b_failed.refresh_from_db()
        assert b_failed.status == "failed"
        assert JournalEntry.objects.filter(tenant=tenant_a).count() == je_initial

        # 2) Closed fiscal period blocked
        b_closed = _integration_api_hub_make_batch(
            tenant_a,
            integration_connector_a,
            index=112,
            fiscal_period=integration_closed_fiscal_period_a,
            gl_account=expense_account_a,
            offset_gl_account=asset_account_a,
            batch_date=integration_closed_fiscal_period_a.start_date,
            status="ready",
        )
        r_closed = client_a.post(
            reverse("assets:asset_gl_sync_batch_execute", args=[b_closed.pk])
        )
        assert r_closed.status_code == 302
        b_closed.refresh_from_db()
        assert b_closed.status == "ready"
        assert b_closed.journal_entry is None
        assert any("closed" in m.lower() for m in _integration_api_hub_msg_texts(r_closed))
        assert JournalEntry.objects.filter(tenant=tenant_a).count() == je_initial

        # 3) Non-zero variance -> simulated / variance_flagged without JE
        b_var = _integration_api_hub_make_batch(
            tenant_a,
            integration_connector_a,
            index=113,
            fiscal_period=integration_open_fiscal_period_a,
            gl_account=expense_account_a,
            offset_gl_account=asset_account_a,
            source_amount=Decimal("1000.00"),
            target_gl_amount=Decimal("925.00"),
            status="ready",
        )
        r_var = client_a.post(
            reverse("assets:asset_gl_sync_batch_execute", args=[b_var.pk])
        )
        assert r_var.status_code == 302
        b_var.refresh_from_db()
        assert b_var.status == "simulated"
        assert b_var.reconciliation_status == "variance_flagged"
        assert b_var.journal_entry is None
        assert JournalEntry.objects.filter(tenant=tenant_a).count() == je_initial

        # 4) Non-posting domain (asset_subledger_sync) with zero variance -> reconciled without JE
        b_nonpost = _integration_api_hub_make_batch(
            tenant_a,
            integration_connector_a,
            index=114,
            sync_domain="asset_subledger_sync",
            fiscal_period=integration_open_fiscal_period_a,
            gl_account=expense_account_a,
            offset_gl_account=asset_account_a,
            source_amount=Decimal("500.00"),
            target_gl_amount=Decimal("500.00"),
            status="draft",
        )
        r_nonpost = client_a.post(
            reverse("assets:asset_gl_sync_batch_execute", args=[b_nonpost.pk])
        )
        assert r_nonpost.status_code == 302
        b_nonpost.refresh_from_db()
        assert b_nonpost.status == "reconciled"
        assert b_nonpost.reconciliation_status == "reconciled"
        assert b_nonpost.journal_entry is None
        assert JournalEntry.objects.filter(tenant=tenant_a).count() == je_initial


# ---------------------------------------------------------------------------
# 5. GIS Mappings Views, verify_spatial_sync & Template/CSS Contracts
# ---------------------------------------------------------------------------


class TestIntegrationApiHubGisMappingViewsAndTemplates:
    def test_integration_api_hub_mapping_list_filters_unicode_pagination_prefill_and_crud(
        self,
        client_a,
        tenant_a,
        operational_asset_a,
        location_a,
        org_unit_a,
        admin_user,
        integration_connector_a,
        integration_connector_b,
        integration_gis_mapping_a,
        integration_gis_mapping_b,
    ):
        in_sync_row = _integration_api_hub_make_mapping(
            tenant_a,
            integration_connector_a,
            operational_asset_a,
            index=1,
            external_feature_id="ARCGIS-SYNC-01",
            drift_status="in_sync",
            status="active",
        )
        drifted = _integration_api_hub_make_mapping(
            tenant_a,
            integration_connector_a,
            operational_asset_a,
            index=2,
            external_feature_id="ESRI-PIPE-77",
            layer_name="corridor_polyline",
            geometry_type="linestring",
            is_linear_asset=True,
            lrs_route_id="I-95-N",
            lrs_from_measure=Decimal("0.000"),
            lrs_to_measure=Decimal("12.500"),
            drift_status="location_drift",
            status="paused",
        )
        list_url = reverse("assets:asset_gis_mapping_list")
        resp = client_a.get(list_url)
        assert resp.status_code == 200
        assert resp.context["total_count"] == 3
        assert resp.context["in_sync_count"] == 1
        assert resp.context["drift_count"] == 1
        assert resp.context["linear_count"] == 1
        listed = {m.pk for m in resp.context["mappings"]}
        assert listed == {integration_gis_mapping_a.pk, in_sync_row.pk, drifted.pk}
        assert integration_gis_mapping_b.pk not in listed

        # Combined filters
        r_flt = client_a.get(
            list_url,
            {
                "q": "ESRI-PIPE",
                "connector": str(integration_connector_a.pk),
                "operational_asset": str(operational_asset_a.pk),
                "geometry_type": "linestring",
                "drift_status": "location_drift",
                "status": "paused",
            },
        )
        assert [m.pk for m in r_flt.context["mappings"]] == [drifted.pk]

        # Empty state & Unicode/bigint
        assert len(client_a.get(list_url, {"q": "missing-gis-xyz"}).context["mappings"]) == 0
        for bad in ("\u00b2", "99999999999999999999999"):
            assert client_a.get(list_url, {"connector": bad}).status_code == 200
            assert client_a.get(list_url, {"operational_asset": bad}).status_code == 200

        # Verified ?connector= prefill
        create_url = reverse("assets:asset_gis_mapping_create")
        assert (
            client_a.get(create_url, {"connector": str(integration_connector_a.pk)})
            .context["form"]
            .initial.get("connector")
            == integration_connector_a.pk
        )
        assert (
            "connector"
            not in client_a.get(create_url, {"connector": str(integration_connector_b.pk)})
            .context["form"]
            .initial
        )

        # Create / Edit / Delete happy path
        payload = {
            "connector": integration_connector_a.pk,
            "operational_asset": operational_asset_a.pk,
            "location": location_a.pk,
            "org_unit": org_unit_a.pk,
            "external_feature_id": "QGIS-VALVE-900",
            "layer_name": "distribution_valves",
            "geometry_type": "point",
            "coordinate_system_srid": 4326,
            "latitude": "34.052235",
            "longitude": "-118.243683",
            "elevation_meters": "89.50",
            "lrs_measure_unit": "km",
            "geojson_payload": '{"type": "Point", "coordinates": [-118.243683, 34.052235]}',
            "system_of_record": "erp_authoritative",
            "sync_direction": "bidirectional",
            "status": "active",
            "gis_custodian": admin_user.pk,
        }
        assert client_a.post(create_url, payload).status_code == 302
        created = AssetGisMapping.objects.get(
            tenant=tenant_a, external_feature_id="QGIS-VALVE-900"
        )
        assert AuditLog.objects.filter(
            tenant=tenant_a, object_id=created.pk, action="create"
        ).exists()

        edit_url = reverse("assets:asset_gis_mapping_edit", args=[created.pk])
        assert client_a.get(edit_url).status_code == 200
        edit_payload = dict(payload)
        edit_payload["layer_name"] = "distribution_valves_v2"
        assert client_a.post(edit_url, edit_payload).status_code == 302
        created.refresh_from_db()
        assert created.layer_name == "distribution_valves_v2"
        assert AuditLog.objects.filter(
            tenant=tenant_a, object_id=created.pk, action="update"
        ).exists()

        del_url = reverse("assets:asset_gis_mapping_delete", args=[created.pk])
        assert client_a.get(del_url).status_code == 405
        assert client_a.post(del_url).status_code == 302
        assert not AssetGisMapping.objects.filter(pk=created.pk).exists()
        assert AuditLog.objects.filter(
            tenant=tenant_a, object_id=created.pk, action="delete"
        ).exists()

    def test_integration_api_hub_mapping_list_pagination_and_query_preservation(
        self,
        client_a,
        tenant_a,
        integration_connector_a,
        operational_asset_a,
    ):
        for i in range(1, 28):
            _integration_api_hub_make_mapping(
                tenant_a,
                integration_connector_a,
                operational_asset_a,
                index=300 + i,
                status="active",
            )
        url = reverse("assets:asset_gis_mapping_list")
        resp_p2 = client_a.get(url, {"status": "active", "page": "2"})
        assert resp_p2.status_code == 200
        assert resp_p2.context["page_obj"].number == 2
        assert "status=active" in resp_p2.content.decode("utf-8")
        assert client_a.get(url, {"page": "999"}).status_code == 200

    def test_integration_api_hub_mapping_coordinate_partial_zero_lrs_and_unrouted_rendering(
        self,
        client_a,
        tenant_a,
        integration_connector_a,
        operational_asset_a,
    ):
        zero_lrs = _integration_api_hub_make_mapping(
            tenant_a,
            integration_connector_a,
            operational_asset_a,
            index=81,
            is_linear_asset=True,
            geometry_type="linestring",
            lrs_route_id="PIPE-ZERO-0",
            lrs_from_measure=Decimal("0.000"),
            lrs_to_measure=Decimal("5.250"),
            latitude=None,
            longitude=None,
        )
        partial_lat = _integration_api_hub_make_mapping(
            tenant_a,
            integration_connector_a,
            operational_asset_a,
            index=82,
            latitude=Decimal("40.712800"),
            longitude=None,
        )
        unrouted = _integration_api_hub_make_mapping(
            tenant_a,
            integration_connector_a,
            operational_asset_a,
            index=83,
            latitude=None,
            longitude=None,
            is_linear_asset=False,
            lrs_route_id="",
            lrs_from_measure=None,
            lrs_to_measure=None,
            geojson_payload="",
        )

        list_html = client_a.get(reverse("assets:asset_gis_mapping_list")).content.decode("utf-8")
        assert "0.000" in list_html
        assert "5.250" in list_html
        assert "Lat 40.712800, Lon —" in list_html
        assert '<span class="text-muted">—</span>' in list_html

        zero_detail = client_a.get(
            reverse("assets:asset_gis_mapping_detail", args=[zero_lrs.pk])
        ).content.decode("utf-8")
        assert "0.000" in zero_detail
        assert "5.250" in zero_detail

        partial_detail = client_a.get(
            reverse("assets:asset_gis_mapping_detail", args=[partial_lat.pk])
        ).content.decode("utf-8")
        assert "Lat 40.712800, Lon —" in partial_detail

        unrouted_detail = client_a.get(
            reverse("assets:asset_gis_mapping_detail", args=[unrouted.pk])
        ).content.decode("utf-8")
        assert "Not specified" in unrouted_detail

    def test_integration_api_hub_verify_spatial_sync_updates_drift_statuses_and_audit_log(
        self,
        client_a,
        tenant_a,
        integration_connector_a,
        operational_asset_a,
    ):
        mapping = _integration_api_hub_make_mapping(
            tenant_a,
            integration_connector_a,
            operational_asset_a,
            index=91,
            drift_status="unverified",
            last_spatial_sync_at=None,
        )
        verify_url = reverse("assets:asset_gis_mapping_verify_sync", args=[mapping.pk])
        assert client_a.get(verify_url).status_code == 405

        # 1) Complete coords + operational asset -> in_sync
        r1 = client_a.post(verify_url)
        assert r1.status_code == 302
        mapping.refresh_from_db()
        assert mapping.drift_status == "in_sync"
        assert mapping.last_spatial_sync_at is not None

        # 2) Valid spatial data with missing operational_asset & location -> attribute_drift
        mapping.operational_asset = None
        mapping.location = None
        mapping.save(update_fields=["operational_asset", "location"])
        r2 = client_a.post(verify_url)
        assert r2.status_code == 302
        mapping.refresh_from_db()
        assert mapping.drift_status == "attribute_drift"

        # 3) Missing point coordinates, LRS, and GeoJSON -> location_drift
        mapping.latitude = None
        mapping.longitude = None
        mapping.geojson_payload = ""
        mapping.save(update_fields=["latitude", "longitude", "geojson_payload"])
        r3 = client_a.post(verify_url)
        assert r3.status_code == 302
        mapping.refresh_from_db()
        assert mapping.drift_status == "location_drift"

        assert (
            AuditLog.objects.filter(
                tenant=tenant_a, object_id=mapping.pk, action="verify"
            ).count()
            == 3
        )

    def test_integration_api_hub_templates_enforce_css_table_wrap_btn_sm_and_a11y_contracts(
        self,
        client_a,
        integration_connector_a,
        integration_stream_a,
        integration_gl_batch_a,
        integration_gis_mapping_a,
    ):
        list_urls = [
            reverse("assets:asset_integration_connector_list"),
            reverse("assets:asset_telemetry_stream_list"),
            reverse("assets:asset_gl_sync_batch_list"),
            reverse("assets:asset_gis_mapping_list"),
        ]
        for url in list_urls:
            resp = client_a.get(url)
            assert resp.status_code == 200
            _integration_api_hub_assert_list_template_contract(resp.content.decode("utf-8"))

        detail_and_form_urls = [
            reverse(
                "assets:asset_integration_connector_detail",
                args=[integration_connector_a.pk],
            ),
            reverse(
                "assets:asset_telemetry_stream_detail",
                args=[integration_stream_a.pk],
            ),
            reverse(
                "assets:asset_gl_sync_batch_detail",
                args=[integration_gl_batch_a.pk],
            ),
            reverse(
                "assets:asset_gis_mapping_detail",
                args=[integration_gis_mapping_a.pk],
            ),
            reverse("assets:asset_integration_connector_create"),
            reverse("assets:asset_telemetry_stream_create"),
            reverse("assets:asset_gl_sync_batch_create"),
            reverse("assets:asset_gis_mapping_create"),
        ]
        for url in detail_and_form_urls:
            resp = client_a.get(url)
            assert resp.status_code == 200
            html = resp.content.decode("utf-8")
            assert "table-responsive" not in html
            assert "btn-xs" not in html
            assert "form-checkbox" not in html
            assert "text-right" not in html

        # Detail pages use btn-sm styling on action controls; stream detail wraps readings table in .table-wrap
        conn_detail_html = client_a.get(
            reverse(
                "assets:asset_integration_connector_detail",
                args=[integration_connector_a.pk],
            )
        ).content.decode("utf-8")
        assert "btn-sm" in conn_detail_html

        stream_detail_html = client_a.get(
            reverse(
                "assets:asset_telemetry_stream_detail",
                args=[integration_stream_a.pk],
            )
        ).content.decode("utf-8")
        assert "btn-sm" in stream_detail_html
        assert 'class="table-wrap"' in stream_detail_html


# ---------------------------------------------------------------------------
# 6. O(1) Query Counts (django_assert_max_num_queries)
# ---------------------------------------------------------------------------


class TestIntegrationApiHubQueryPerformance:
    def test_integration_api_hub_stream_detail_o1_queries_with_10_linked_readings(
        self,
        client_a,
        django_assert_max_num_queries,
        tenant_a,
        integration_connector_a,
        operational_asset_a,
        fixed_asset_a,
        admin_user,
    ):
        stream = _integration_api_hub_make_stream(
            tenant_a,
            integration_connector_a,
            operational_asset_a,
            index=501,
            fixed_asset=fixed_asset_a,
        )
        base_time = timezone.now()
        for i in range(1, 11):
            mr = _integration_api_hub_make_maintenance_request(
                tenant_a,
                operational_asset_a,
                fixed_asset_a,
                admin_user,
                index=500 + i,
            )
            AssetTelemetryReading.objects.create(
                tenant=tenant_a,
                operational_asset=operational_asset_a,
                fixed_asset=fixed_asset_a,
                sensor_identifier=stream.tag_address,
                recorded_by=admin_user,
                recorded_at=base_time - datetime.timedelta(minutes=i),
                source="iot_sensor",
                metric_type="bearing_temperature",
                metric_unit="celsius",
                reading_value=Decimal("92.0000") + Decimal(i),
                baseline_value=Decimal("40.0000"),
                threshold_status="critical",
                triggered_maintenance_request=mr,
            )

        detail_url = reverse("assets:asset_telemetry_stream_detail", args=[stream.pk])
        with django_assert_max_num_queries(12):
            resp = client_a.get(detail_url)
        assert resp.status_code == 200
        assert len(list(resp.context["recent_readings"])) == 10

    def test_integration_api_hub_batch_detail_o1_queries(
        self,
        client_a,
        django_assert_max_num_queries,
        tenant_a,
        integration_connector_a,
        integration_open_fiscal_period_a,
        expense_account_a,
        asset_account_a,
        accum_account_a,
        fixed_asset_a,
        operational_asset_a,
        po_a,
        capitalization_a,
        maintenance_request_a,
        org_unit_a,
        currency_usd,
    ):
        dep_sched = _integration_api_hub_make_depreciation_schedule(
            tenant_a,
            fixed_asset_a,
            operational_asset_a,
            expense_account_a,
            accum_account_a,
            index=51,
        )
        batch = _integration_api_hub_make_batch(
            tenant_a,
            integration_connector_a,
            index=502,
            fiscal_period=integration_open_fiscal_period_a,
            gl_account=expense_account_a,
            offset_gl_account=asset_account_a,
            fixed_asset=fixed_asset_a,
            purchase_order=po_a,
            capitalization=capitalization_a,
            depreciation_schedule=dep_sched,
            maintenance_request=maintenance_request_a,
            cost_center=org_unit_a,
            currency=currency_usd,
            batch_date=integration_open_fiscal_period_a.start_date,
        )
        client_a.post(reverse("assets:asset_gl_sync_batch_execute", args=[batch.pk]))

        detail_url = reverse("assets:asset_gl_sync_batch_detail", args=[batch.pk])
        with django_assert_max_num_queries(12):
            resp = client_a.get(detail_url)
        assert resp.status_code == 200

    def test_integration_api_hub_list_views_o1_queries_bounded_across_12_records(
        self,
        client_a,
        django_assert_max_num_queries,
        tenant_a,
        operational_asset_a,
        fixed_asset_a,
        location_a,
        org_unit_a,
        expense_account_a,
        asset_account_a,
        integration_open_fiscal_period_a,
        currency_usd,
    ):
        for i in range(1, 13):
            conn = _integration_api_hub_make_connector(
                tenant_a,
                index=600 + i,
                default_org_unit=org_unit_a,
                default_currency=currency_usd,
            )
            _integration_api_hub_make_stream(
                tenant_a,
                conn,
                operational_asset_a,
                index=600 + i,
                fixed_asset=fixed_asset_a,
            )
            _integration_api_hub_make_batch(
                tenant_a,
                conn,
                index=600 + i,
                fiscal_period=integration_open_fiscal_period_a,
                gl_account=expense_account_a,
                offset_gl_account=asset_account_a,
                cost_center=org_unit_a,
                currency=currency_usd,
            )
            _integration_api_hub_make_mapping(
                tenant_a,
                conn,
                operational_asset_a,
                index=600 + i,
                location=location_a,
                org_unit=org_unit_a,
            )

        for url_name in (
            "assets:asset_integration_connector_list",
            "assets:asset_telemetry_stream_list",
            "assets:asset_gl_sync_batch_list",
            "assets:asset_gis_mapping_list",
        ):
            with django_assert_max_num_queries(14):
                resp = client_a.get(reverse(url_name))
            assert resp.status_code == 200
