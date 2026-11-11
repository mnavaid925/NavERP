"""
Security, Tenant-Isolation, RBAC, State-Guard, SSRF, Secret Hygiene, and
Adversarial Input Hardening Tests for Sub-module 11.15: Integration & API Hub.

Covers all 4 entities across all 25 routes:
1. AuthN, HTTP Method & CSRF Matrix (all 25 routes, 9 @require_POST, 17 POST routes).
2. Cross-Tenant IDOR Matrix (tenant_a <-> tenant_b -> strict 404, zero mutations,
   child & list isolation, ?connector= prefill guard, corrupted cross-tenant DB child filtering).
3. Fail-Closed request.tenant is None (superuser & tenant-none users on create/list/objects).
4. Role Authorization (@tenant_admin_required -> 403 for members) & Template Parity.
5. Adversarial Mass Assignment, Posted GL Batch Immutability, select_for_update() +
   Atomic Rollback, Cross-Tenant FK Injection via POST & Action Runtime Guards.
6. Obfuscated SSRF Corpus (13+ vectors), Secret Lifecycle & AuditLog Redaction,
   Stored XSS Escaping, Nested JSON RecursionError / NaN / >64KB Rejection,
   Extreme Decimal Ingest, and Unicode Chaos Query Resistance.
7. Multi-User Isolation & Role Matrix at Scale (100 heterogeneous bulk dummy users:
   60 in tenant_a, 40 in tenant_b across admin/manager/staff/auditor roles).
"""

from __future__ import annotations

import datetime
import hashlib
import socket
import urllib.request
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.contrib.messages import get_messages
from django.db import connection
from django.db.models.query import QuerySet
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape

from apps.accounts.models import Role
from apps.accounting.models import (
    FiscalPeriod,
    GLAccount,
    JournalEntry,
    JournalLine,
)
from apps.assets.forms import (
    AssetGisMappingForm,
    AssetGlSyncBatchForm,
    AssetIntegrationConnectorForm,
    AssetTelemetryStreamForm,
)
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

User = get_user_model()
pytestmark = pytest.mark.django_db


# =====================================================================
# Module-level Helpers (_integration_api_hub_*)
# =====================================================================


def _integration_api_hub_sec_msg_texts(response):
    """Return stringified Django flash messages queued on response.wsgi_request."""
    return [str(m) for m in get_messages(response.wsgi_request)]


def _integration_api_hub_sec_get_routes(connector, stream, batch, mapping):
    """Return the 16 GET-accessible routes (4x list/create/detail/edit)."""
    return [
        reverse("assets:asset_integration_connector_list"),
        reverse("assets:asset_integration_connector_create"),
        reverse(
            "assets:asset_integration_connector_detail", kwargs={"pk": connector.pk}
        ),
        reverse("assets:asset_integration_connector_edit", kwargs={"pk": connector.pk}),
        reverse("assets:asset_telemetry_stream_list"),
        reverse("assets:asset_telemetry_stream_create"),
        reverse("assets:asset_telemetry_stream_detail", kwargs={"pk": stream.pk}),
        reverse("assets:asset_telemetry_stream_edit", kwargs={"pk": stream.pk}),
        reverse("assets:asset_gl_sync_batch_list"),
        reverse("assets:asset_gl_sync_batch_create"),
        reverse("assets:asset_gl_sync_batch_detail", kwargs={"pk": batch.pk}),
        reverse("assets:asset_gl_sync_batch_edit", kwargs={"pk": batch.pk}),
        reverse("assets:asset_gis_mapping_list"),
        reverse("assets:asset_gis_mapping_create"),
        reverse("assets:asset_gis_mapping_detail", kwargs={"pk": mapping.pk}),
        reverse("assets:asset_gis_mapping_edit", kwargs={"pk": mapping.pk}),
    ]


def _integration_api_hub_sec_post_only_routes(connector, stream, batch, mapping):
    """Return all 9 @require_POST routes (4x delete + 5x custom actions)."""
    return [
        reverse(
            "assets:asset_integration_connector_delete", kwargs={"pk": connector.pk}
        ),
        reverse("assets:asset_integration_connector_test", kwargs={"pk": connector.pk}),
        reverse(
            "assets:asset_integration_connector_rotate_secret",
            kwargs={"pk": connector.pk},
        ),
        reverse("assets:asset_telemetry_stream_delete", kwargs={"pk": stream.pk}),
        reverse("assets:asset_telemetry_stream_ingest", kwargs={"pk": stream.pk}),
        reverse("assets:asset_gl_sync_batch_delete", kwargs={"pk": batch.pk}),
        reverse("assets:asset_gl_sync_batch_execute", kwargs={"pk": batch.pk}),
        reverse("assets:asset_gis_mapping_delete", kwargs={"pk": mapping.pk}),
        reverse("assets:asset_gis_mapping_verify_sync", kwargs={"pk": mapping.pk}),
    ]


def _integration_api_hub_sec_all_25_routes(connector, stream, batch, mapping):
    """Return all 25 URLs belonging to 11.15 Integration & API Hub."""
    return _integration_api_hub_sec_get_routes(
        connector, stream, batch, mapping
    ) + _integration_api_hub_sec_post_only_routes(connector, stream, batch, mapping)


def _integration_api_hub_sec_connector_payload(**overrides):
    """Minimal valid POST payload for AssetIntegrationConnector create/edit."""
    data = {
        "name": "Security Hardened Connector",
        "connector_category": "erp_procurement",
        "provider": "sap_s4hana",
        "protocol": "odata_v4",
        "sync_direction": "bidirectional",
        "environment": "production",
        "endpoint_url": "https://api-sec.example.com/odata/v4",
        "auth_method": "api_key",
        "rate_limit_rpm": "120",
        "timeout_seconds": "30",
        "retry_policy_max": "3",
        "polling_interval_minutes": "15",
        "status": "active",
        "webhook_verify_tls": True,
        "notes": "Security baseline connector",
    }
    data.update(overrides)
    return data


def _integration_api_hub_sec_stream_payload(
    connector, operational_asset=None, fixed_asset=None, **overrides
):
    """Minimal valid POST payload for AssetTelemetryStream create/edit."""
    data = {
        "connector": str(connector.pk),
        "operational_asset": str(operational_asset.pk) if operational_asset else "",
        "fixed_asset": str(fixed_asset.pk) if fixed_asset else "",
        "tag_address": "ns=2;s=Plant1.Sec.Temp01",
        "stream_name": "Security Hardened Bearing Stream",
        "stream_protocol": "opc_ua_node",
        "metric_type": "bearing_temperature",
        "metric_unit": "celsius",
        "ingestion_mode": "polling",
        "polling_interval_seconds": "60",
        "deadband_delta": "0.2500",
        "scale_factor": "1.000000",
        "offset_value": "0.0000",
        "baseline_value": "45.0000",
        "warning_threshold": "75.0000",
        "critical_threshold": "90.0000",
        "auto_trigger_maintenance": True,
        "stream_status": "active",
        "notes": "Security baseline stream",
    }
    data.update(overrides)
    return data


def _integration_api_hub_sec_batch_payload(connector, **overrides):
    """Minimal valid POST payload for AssetGlSyncBatch create/edit."""
    data = {
        "connector": str(connector.pk),
        "sync_domain": "depreciation_posting",
        "sync_direction": "outbound",
        "external_batch_ref": "SEC-BATCH-001",
        "batch_date": timezone.localdate().isoformat(),
        "source_amount": "1500.00",
        "target_gl_amount": "1500.00",
        "field_mapping_json": '{"asset_class": "ANLKL"}',
        "payload_summary": "Security baseline GL sync batch",
        "notes": "Security notes",
    }
    data.update(overrides)
    return data


def _integration_api_hub_sec_mapping_payload(connector, **overrides):
    """Minimal valid POST payload for AssetGisMapping create/edit."""
    data = {
        "connector": str(connector.pk),
        "external_feature_id": "GIS-SEC-001",
        "layer_name": "sec_assets_pt",
        "geometry_type": "point",
        "coordinate_system_srid": "4326",
        "latitude": "37.774900",
        "longitude": "-122.419400",
        "is_linear_asset": False,
        "lrs_measure_unit": "km",
        "geojson_payload": '{"type": "Point", "coordinates": [-122.4194, 37.7749]}',
        "system_of_record": "erp_authoritative",
        "sync_direction": "bidirectional",
        "status": "active",
        "notes": "Security baseline GIS mapping",
    }
    data.update(overrides)
    return data


def _integration_api_hub_sec_make_connector(tenant, index=1, **overrides):
    """Create a valid AssetIntegrationConnector directly in DB."""
    defaults = {
        "tenant": tenant,
        "name": f"Sec Connector #{index}",
        "connector_category": "iot_scada",
        "provider": "kepware_opcua",
        "protocol": "opc_ua",
        "sync_direction": "inbound",
        "environment": "production",
        "endpoint_url": f"https://gateway-sec-{index}.example.com/api/v1",
        "auth_method": "api_key",
        "rate_limit_rpm": 120,
        "timeout_seconds": 30,
        "retry_policy_max": 3,
        "polling_interval_minutes": 15,
        "status": "active",
        "health_status": "unverified",
        "webhook_verify_tls": True,
    }
    defaults.update(overrides)
    return AssetIntegrationConnector.objects.create(**defaults)


def _integration_api_hub_sec_make_stream(
    tenant, connector, operational_asset, index=1, **overrides
):
    """Create a valid AssetTelemetryStream directly in DB."""
    defaults = {
        "tenant": tenant,
        "connector": connector,
        "operational_asset": operational_asset,
        "tag_address": f"ns=2;s=Sec.Line1.Tag{index}",
        "stream_name": f"Sec Stream #{index}",
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


def _integration_api_hub_sec_make_batch(tenant, connector, index=1, **overrides):
    """Create a valid AssetGlSyncBatch directly in DB."""
    defaults = {
        "tenant": tenant,
        "connector": connector,
        "sync_domain": "depreciation_posting",
        "sync_direction": "outbound",
        "external_batch_ref": f"SEC-GL-{index:04d}",
        "batch_date": timezone.localdate(),
        "source_amount": Decimal("1200.00"),
        "target_gl_amount": Decimal("1200.00"),
        "status": "ready",
        "reconciliation_status": "pending",
        "field_mapping_json": '{"asset_class": "MACH"}',
    }
    defaults.update(overrides)
    return AssetGlSyncBatch.objects.create(**defaults)


def _integration_api_hub_sec_make_mapping(
    tenant, connector, operational_asset, index=1, **overrides
):
    """Create a valid AssetGisMapping directly in DB."""
    defaults = {
        "tenant": tenant,
        "connector": connector,
        "operational_asset": operational_asset,
        "external_feature_id": f"SEC-GIS-{index:04d}",
        "layer_name": "sec_corridor_pt",
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
        "drift_status": "unverified",
    }
    defaults.update(overrides)
    return AssetGisMapping.objects.create(**defaults)


def _integration_api_hub_sec_make_depreciation_schedule(
    tenant,
    fixed_asset,
    operational_asset,
    expense_account,
    accum_account,
    index=1,
):
    """Create AssetDepreciationSchedule without invoking broken legacy fixtures."""
    return AssetDepreciationSchedule.objects.create(
        tenant=tenant,
        fixed_asset=fixed_asset,
        operational_asset=operational_asset,
        fiscal_year=2026,
        period_number=((index - 1) % 12) + 1,
        period_frequency="monthly",
        schedule_date=datetime.date(2026, 6, 15),
        depreciation_method="straight_line",
        starting_book_value=Decimal("50000.00"),
        depreciation_amount=Decimal("800.00"),
        accumulated_depreciation_after=Decimal("10800.00"),
        ending_book_value=Decimal("49200.00"),
        expense_account=expense_account,
        accumulated_account=accum_account,
        status="draft",
    )


def _integration_api_hub_sec_make_maintenance_request(
    tenant, operational_asset, fixed_asset, requester, index=1
):
    """Create AssetMaintenanceRequest directly for cross-tenant FK injection checks."""
    return AssetMaintenanceRequest.objects.create(
        tenant=tenant,
        title=f"Sec Maintenance Req #{index}",
        fixed_asset=fixed_asset,
        operational_asset=operational_asset,
        requester=requester,
        request_type="breakdown_repair",
        urgency="high",
        is_breakdown=True,
        downtime_started_at=timezone.now(),
        symptom_description=f"Test symptom #{index}",
        status="submitted",
    )


def _integration_api_hub_sec_snapshot_counts():
    """Return tuple of DB row counts across Integration Hub and downstream tables."""
    return (
        AssetIntegrationConnector.objects.count(),
        AssetTelemetryStream.objects.count(),
        AssetGlSyncBatch.objects.count(),
        AssetGisMapping.objects.count(),
        AssetTelemetryReading.objects.count(),
        AssetMaintenanceRequest.objects.count(),
        JournalEntry.objects.count(),
        JournalLine.objects.count(),
        AuditLog.objects.count(),
    )


# =====================================================================
# 1. AuthN, Method & CSRF Matrix (All 25 Routes)
# =====================================================================


class TestIntegrationApiHubAuthMethodAndCsrf:
    """Enforce authentication, @require_POST, and CSRF checks across all 25 routes."""

    def test_integration_api_hub_anonymous_redirects_to_login_on_all_25_routes(
        self,
        client,
        integration_connector_a,
        integration_stream_a,
        integration_gl_batch_a,
        integration_gis_mapping_a,
    ):
        all_urls = _integration_api_hub_sec_all_25_routes(
            integration_connector_a,
            integration_stream_a,
            integration_gl_batch_a,
            integration_gis_mapping_a,
        )
        assert len(all_urls) == 25

        before_counts = _integration_api_hub_sec_snapshot_counts()
        for url in all_urls:
            resp_get = client.get(url)
            assert resp_get.status_code == 302, (
                f"Expected 302 login redirect on anonymous GET {url}, got {resp_get.status_code}"
            )
            assert "login" in resp_get["Location"].lower()

            resp_post = client.post(url, {})
            assert resp_post.status_code == 302, (
                f"Expected 302 login redirect on anonymous POST {url}, got {resp_post.status_code}"
            )
            assert "login" in resp_post["Location"].lower()

        assert _integration_api_hub_sec_snapshot_counts() == before_counts

    def test_integration_api_hub_require_post_routes_reject_get_with_405(
        self,
        client_a,
        integration_connector_a,
        integration_stream_a,
        integration_gl_batch_a,
        integration_gis_mapping_a,
    ):
        post_only_urls = _integration_api_hub_sec_post_only_routes(
            integration_connector_a,
            integration_stream_a,
            integration_gl_batch_a,
            integration_gis_mapping_a,
        )
        assert len(post_only_urls) == 9

        before_counts = _integration_api_hub_sec_snapshot_counts()
        prev_hash = integration_connector_a.api_key_hash
        prev_health = integration_connector_a.health_status
        prev_drift = integration_gis_mapping_a.drift_status

        for url in post_only_urls:
            resp_get = client_a.get(url)
            assert resp_get.status_code == 405, (
                f"Expected 405 on GET {url}, got {resp_get.status_code}"
            )
            resp_put = client_a.put(url, {})
            assert resp_put.status_code == 405, (
                f"Expected 405 on PUT {url}, got {resp_put.status_code}"
            )

        assert _integration_api_hub_sec_snapshot_counts() == before_counts
        integration_connector_a.refresh_from_db()
        integration_gis_mapping_a.refresh_from_db()
        assert integration_connector_a.api_key_hash == prev_hash
        assert integration_connector_a.health_status == prev_health
        assert integration_gis_mapping_a.drift_status == prev_drift

    def test_integration_api_hub_csrf_enforced_across_all_17_post_routes(
        self,
        admin_user,
        operational_asset_a,
        integration_connector_a,
        integration_stream_a,
        integration_gl_batch_a,
        integration_gis_mapping_a,
    ):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(admin_user)

        post_cases = [
            # 8 Create & Edit routes
            (
                reverse("assets:asset_integration_connector_create"),
                _integration_api_hub_sec_connector_payload(name="CSRF Blocked Conn"),
            ),
            (
                reverse(
                    "assets:asset_integration_connector_edit",
                    args=[integration_connector_a.pk],
                ),
                _integration_api_hub_sec_connector_payload(name="CSRF Blocked Conn Edit"),
            ),
            (
                reverse("assets:asset_telemetry_stream_create"),
                _integration_api_hub_sec_stream_payload(
                    integration_connector_a,
                    operational_asset_a,
                    stream_name="CSRF Blocked Stream",
                ),
            ),
            (
                reverse(
                    "assets:asset_telemetry_stream_edit",
                    args=[integration_stream_a.pk],
                ),
                _integration_api_hub_sec_stream_payload(
                    integration_connector_a,
                    operational_asset_a,
                    stream_name="CSRF Blocked Stream Edit",
                ),
            ),
            (
                reverse("assets:asset_gl_sync_batch_create"),
                _integration_api_hub_sec_batch_payload(
                    integration_connector_a, external_batch_ref="CSRF-BLOCKED-BATCH"
                ),
            ),
            (
                reverse(
                    "assets:asset_gl_sync_batch_edit",
                    args=[integration_gl_batch_a.pk],
                ),
                _integration_api_hub_sec_batch_payload(
                    integration_connector_a, external_batch_ref="CSRF-BLOCKED-EDIT"
                ),
            ),
            (
                reverse("assets:asset_gis_mapping_create"),
                _integration_api_hub_sec_mapping_payload(
                    integration_connector_a, external_feature_id="CSRF-BLOCKED-GIS"
                ),
            ),
            (
                reverse(
                    "assets:asset_gis_mapping_edit",
                    args=[integration_gis_mapping_a.pk],
                ),
                _integration_api_hub_sec_mapping_payload(
                    integration_connector_a, external_feature_id="CSRF-BLOCKED-GIS-EDIT"
                ),
            ),
            # 9 @require_POST routes
            (
                reverse(
                    "assets:asset_integration_connector_delete",
                    args=[integration_connector_a.pk],
                ),
                {},
            ),
            (
                reverse(
                    "assets:asset_integration_connector_test",
                    args=[integration_connector_a.pk],
                ),
                {},
            ),
            (
                reverse(
                    "assets:asset_integration_connector_rotate_secret",
                    args=[integration_connector_a.pk],
                ),
                {},
            ),
            (
                reverse(
                    "assets:asset_telemetry_stream_delete",
                    args=[integration_stream_a.pk],
                ),
                {},
            ),
            (
                reverse(
                    "assets:asset_telemetry_stream_ingest",
                    args=[integration_stream_a.pk],
                ),
                {"raw_value": "95.0000"},
            ),
            (
                reverse(
                    "assets:asset_gl_sync_batch_delete",
                    args=[integration_gl_batch_a.pk],
                ),
                {},
            ),
            (
                reverse(
                    "assets:asset_gl_sync_batch_execute",
                    args=[integration_gl_batch_a.pk],
                ),
                {},
            ),
            (
                reverse(
                    "assets:asset_gis_mapping_delete",
                    args=[integration_gis_mapping_a.pk],
                ),
                {},
            ),
            (
                reverse(
                    "assets:asset_gis_mapping_verify_sync",
                    args=[integration_gis_mapping_a.pk],
                ),
                {},
            ),
        ]
        assert len(post_cases) == 17

        before_counts = _integration_api_hub_sec_snapshot_counts()
        orig_hash = integration_connector_a.api_key_hash

        for url, payload in post_cases:
            resp = csrf_client.post(url, data=payload)
            assert resp.status_code == 403, (
                f"Expected 403 CSRF rejection on POST {url}, got {resp.status_code}"
            )

        assert _integration_api_hub_sec_snapshot_counts() == before_counts
        integration_connector_a.refresh_from_db()
        integration_stream_a.refresh_from_db()
        integration_gl_batch_a.refresh_from_db()
        integration_gis_mapping_a.refresh_from_db()
        assert integration_connector_a.api_key_hash == orig_hash
        assert integration_connector_a.name != "CSRF Blocked Conn Edit"
        assert integration_stream_a.stream_name != "CSRF Blocked Stream Edit"
        assert integration_gl_batch_a.external_batch_ref != "CSRF-BLOCKED-EDIT"
        assert integration_gis_mapping_a.external_feature_id != "CSRF-BLOCKED-GIS-EDIT"

    def test_integration_api_hub_csrf_passes_with_valid_token(self, admin_user):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(admin_user)

        create_url = reverse("assets:asset_integration_connector_create")
        get_resp = csrf_client.get(create_url)
        assert get_resp.status_code == 200
        csrf_token = get_resp.cookies["csrftoken"].value

        payload = _integration_api_hub_sec_connector_payload(
            name="Valid CSRF Token Connector",
            csrfmiddlewaretoken=csrf_token,
        )
        post_resp = csrf_client.post(create_url, data=payload)
        assert post_resp.status_code == 302
        assert AssetIntegrationConnector.objects.filter(
            tenant=admin_user.tenant, name="Valid CSRF Token Connector"
        ).exists()


# =====================================================================
# 2. Cross-Tenant IDOR & Child Isolation Matrix
# =====================================================================


class TestIntegrationApiHubCrossTenantIdor:
    """Strict 404 cross-tenant IDOR protection and list/child isolation."""

    def test_integration_api_hub_cross_tenant_idor_b_to_a_and_a_to_b_returns_404_zero_mutation(
        self,
        client_a,
        client_b,
        operational_asset_a,
        operational_asset_b,
        integration_connector_a,
        integration_connector_b,
        integration_stream_a,
        integration_stream_b,
        integration_gl_batch_a,
        integration_gl_batch_b,
        integration_gis_mapping_a,
        integration_gis_mapping_b,
    ):
        before_counts = _integration_api_hub_sec_snapshot_counts()
        orig_hash_a = integration_connector_a.api_key_hash
        orig_hash_b = integration_connector_b.api_key_hash

        pairs = [
            (
                client_b,
                integration_connector_a,
                integration_stream_a,
                integration_gl_batch_a,
                integration_gis_mapping_a,
                operational_asset_b,
            ),
            (
                client_a,
                integration_connector_b,
                integration_stream_b,
                integration_gl_batch_b,
                integration_gis_mapping_b,
                operational_asset_a,
            ),
        ]

        for attacker_client, conn, stream, batch, mapping, attacker_asset in pairs:
            get_404_urls = [
                reverse(
                    "assets:asset_integration_connector_detail", args=[conn.pk]
                ),
                reverse("assets:asset_integration_connector_edit", args=[conn.pk]),
                reverse("assets:asset_telemetry_stream_detail", args=[stream.pk]),
                reverse("assets:asset_telemetry_stream_edit", args=[stream.pk]),
                reverse("assets:asset_gl_sync_batch_detail", args=[batch.pk]),
                reverse("assets:asset_gl_sync_batch_edit", args=[batch.pk]),
                reverse("assets:asset_gis_mapping_detail", args=[mapping.pk]),
                reverse("assets:asset_gis_mapping_edit", args=[mapping.pk]),
            ]
            for url in get_404_urls:
                resp = attacker_client.get(url)
                assert resp.status_code == 404, (
                    f"Expected 404 IDOR block on GET {url}, got {resp.status_code}"
                )

            edit_post_cases = [
                (
                    reverse(
                        "assets:asset_integration_connector_edit", args=[conn.pk]
                    ),
                    _integration_api_hub_sec_connector_payload(name="IDOR Hijacked"),
                ),
                (
                    reverse("assets:asset_telemetry_stream_edit", args=[stream.pk]),
                    _integration_api_hub_sec_stream_payload(
                        conn, attacker_asset, stream_name="IDOR Hijacked Stream"
                    ),
                ),
                (
                    reverse("assets:asset_gl_sync_batch_edit", args=[batch.pk]),
                    _integration_api_hub_sec_batch_payload(
                        conn, external_batch_ref="IDOR-HIJACK"
                    ),
                ),
                (
                    reverse("assets:asset_gis_mapping_edit", args=[mapping.pk]),
                    _integration_api_hub_sec_mapping_payload(
                        conn, external_feature_id="IDOR-HIJACK-GIS"
                    ),
                ),
            ]
            for url, payload in edit_post_cases:
                resp = attacker_client.post(url, data=payload)
                assert resp.status_code == 404, (
                    f"Expected 404 IDOR block on edit POST {url}, got {resp.status_code}"
                )

            post_only_404_urls = _integration_api_hub_sec_post_only_routes(
                conn, stream, batch, mapping
            )
            for url in post_only_404_urls:
                resp = attacker_client.post(url, {"raw_value": "99.0000"})
                assert resp.status_code == 404, (
                    f"Expected 404 IDOR block on POST {url}, got {resp.status_code}"
                )

        assert _integration_api_hub_sec_snapshot_counts() == before_counts

        for obj in (
            integration_connector_a,
            integration_connector_b,
            integration_stream_a,
            integration_stream_b,
            integration_gl_batch_a,
            integration_gl_batch_b,
            integration_gis_mapping_a,
            integration_gis_mapping_b,
        ):
            obj.refresh_from_db()

        assert integration_connector_a.api_key_hash == orig_hash_a
        assert integration_connector_b.api_key_hash == orig_hash_b
        assert integration_connector_a.health_status == "unverified"
        assert integration_connector_b.health_status == "unverified"
        assert integration_stream_a.readings_ingested_count == 0
        assert integration_stream_b.readings_ingested_count == 0
        assert integration_gl_batch_a.status == "ready"
        assert integration_gl_batch_b.status == "ready"
        assert integration_gis_mapping_a.drift_status == "unverified"
        assert integration_gis_mapping_b.drift_status == "unverified"

    def test_integration_api_hub_list_views_and_create_prefill_isolate_tenants(
        self,
        client_a,
        client_b,
        operational_asset_a,
        operational_asset_b,
        integration_connector_a,
        integration_connector_b,
        integration_stream_a,
        integration_stream_b,
        integration_gl_batch_a,
        integration_gl_batch_b,
        integration_gis_mapping_a,
        integration_gis_mapping_b,
    ):
        checks = [
            (
                "assets:asset_integration_connector_list",
                "connectors",
                integration_connector_a,
                integration_connector_b,
                integration_connector_a.name,
                integration_connector_b.name,
            ),
            (
                "assets:asset_telemetry_stream_list",
                "streams",
                integration_stream_a,
                integration_stream_b,
                integration_stream_a.stream_name,
                integration_stream_b.stream_name,
            ),
            (
                "assets:asset_gl_sync_batch_list",
                "batches",
                integration_gl_batch_a,
                integration_gl_batch_b,
                integration_gl_batch_a.external_batch_ref,
                integration_gl_batch_b.external_batch_ref,
            ),
            (
                "assets:asset_gis_mapping_list",
                "mappings",
                integration_gis_mapping_a,
                integration_gis_mapping_b,
                integration_gis_mapping_a.external_feature_id,
                integration_gis_mapping_b.external_feature_id,
            ),
        ]
        for url_name, ctx_key, obj_a, obj_b, marker_a, marker_b in checks:
            url = reverse(url_name)
            resp_a = client_a.get(url)
            assert resp_a.status_code == 200
            html_a = resp_a.content.decode("utf-8")
            assert list(resp_a.context[ctx_key]) == [obj_a]
            assert resp_a.context["total_count"] == 1
            assert marker_a in html_a
            assert marker_b not in html_a
            if "connectors" in resp_a.context and ctx_key != "connectors":
                assert list(resp_a.context["connectors"]) == [integration_connector_a]
            if "assets_list" in resp_a.context:
                assert list(resp_a.context["assets_list"]) == [operational_asset_a]

            resp_b = client_b.get(url)
            assert resp_b.status_code == 200
            html_b = resp_b.content.decode("utf-8")
            assert list(resp_b.context[ctx_key]) == [obj_b]
            assert resp_b.context["total_count"] == 1
            assert marker_b in html_b
            assert marker_a not in html_b
            if "connectors" in resp_b.context and ctx_key != "connectors":
                assert list(resp_b.context["connectors"]) == [integration_connector_b]
            if "assets_list" in resp_b.context:
                assert list(resp_b.context["assets_list"]) == [operational_asset_b]

        # Foreign ?connector= query prefill on create routes must be ignored cleanly
        for create_url_name in (
            "assets:asset_telemetry_stream_create",
            "assets:asset_gl_sync_batch_create",
            "assets:asset_gis_mapping_create",
        ):
            resp = client_a.get(
                f"{reverse(create_url_name)}?connector={integration_connector_b.pk}"
            )
            assert resp.status_code == 200
            form = resp.context["form"]
            assert form.initial.get("connector") is None
            assert integration_connector_b.name not in resp.content.decode("utf-8")

    def test_integration_api_hub_detail_views_filter_out_corrupted_cross_tenant_children(
        self,
        client_a,
        tenant_b,
        operational_asset_a,
        integration_connector_a,
        integration_stream_a,
        integration_gl_batch_a,
        integration_gis_mapping_a,
    ):
        # Plant corrupted tenant_b child rows pointing to tenant_a parent FKs in DB
        foreign_stream = _integration_api_hub_sec_make_stream(
            tenant_b,
            integration_connector_a,
            operational_asset_a,
            index=77,
            stream_name="Leaked Foreign Stream Child",
        )
        foreign_batch = _integration_api_hub_sec_make_batch(
            tenant_b,
            integration_connector_a,
            index=77,
            external_batch_ref="LEAKED-FOREIGN-BATCH",
        )
        foreign_mapping = _integration_api_hub_sec_make_mapping(
            tenant_b,
            integration_connector_a,
            operational_asset_a,
            index=77,
            layer_name="leaked_foreign_layer",
            external_feature_id="LEAKED-GIS-077",
        )
        foreign_reading = AssetTelemetryReading.objects.create(
            tenant=tenant_b,
            operational_asset=operational_asset_a,
            sensor_identifier="FOREIGN-SENSOR-77",
            reading_value=Decimal("88.0000"),
            metric_type="bearing_temperature",
            metric_unit="celsius",
            threshold_status="warning",
        )

        conn_resp = client_a.get(
            reverse(
                "assets:asset_integration_connector_detail",
                args=[integration_connector_a.pk],
            )
        )
        assert conn_resp.status_code == 200
        conn_html = conn_resp.content.decode("utf-8")
        assert list(conn_resp.context["streams"]) == [integration_stream_a]
        assert list(conn_resp.context["gl_batches"]) == [integration_gl_batch_a]
        assert list(conn_resp.context["gis_mappings"]) == [integration_gis_mapping_a]
        assert foreign_stream.stream_name not in conn_html
        assert foreign_mapping.layer_name not in conn_html
        assert (
            reverse("assets:asset_gl_sync_batch_detail", args=[foreign_batch.pk])
            not in conn_html
        )

        stream_resp = client_a.get(
            reverse(
                "assets:asset_telemetry_stream_detail",
                args=[integration_stream_a.pk],
            )
        )
        assert stream_resp.status_code == 200
        assert list(stream_resp.context["recent_readings"]) == []
        stream_html = stream_resp.content.decode("utf-8")
        assert foreign_reading.sensor_identifier not in stream_html
        assert (
            reverse("assets:asset_telemetry_reading_detail", args=[foreign_reading.pk])
            not in stream_html
        )


# =====================================================================
# 3. Fail-Closed request.tenant is None
# =====================================================================


class TestIntegrationApiHubFailClosedTenantNone:
    """Superuser / tenant-less accounts fail closed on create, list, detail, and actions."""

    def test_integration_api_hub_tenant_none_superuser_fails_closed_on_create_list_and_objects(
        self,
        integration_connector_a,
        integration_connector_b,
        integration_stream_a,
        integration_gl_batch_a,
        integration_gis_mapping_a,
        operational_asset_a,
    ):
        superuser = User.objects.create_superuser(
            email="platform_super_hub@naverp.test",
            username="platform_super_hub",
            password="TestPass123!",
            tenant=None,
        )
        c = Client()
        c.force_login(superuser)

        before_counts = _integration_api_hub_sec_snapshot_counts()

        create_routes = [
            (
                "assets:asset_integration_connector_create",
                "assets:asset_integration_connector_list",
                _integration_api_hub_sec_connector_payload(name="Superuser Conn"),
            ),
            (
                "assets:asset_telemetry_stream_create",
                "assets:asset_telemetry_stream_list",
                _integration_api_hub_sec_stream_payload(
                    integration_connector_a,
                    operational_asset_a,
                    stream_name="Superuser Stream",
                ),
            ),
            (
                "assets:asset_gl_sync_batch_create",
                "assets:asset_gl_sync_batch_list",
                _integration_api_hub_sec_batch_payload(
                    integration_connector_a, external_batch_ref="SU-BATCH"
                ),
            ),
            (
                "assets:asset_gis_mapping_create",
                "assets:asset_gis_mapping_list",
                _integration_api_hub_sec_mapping_payload(
                    integration_connector_a, external_feature_id="SU-GIS"
                ),
            ),
        ]

        for create_name, list_name, post_data in create_routes:
            create_url = reverse(create_name)
            list_url = reverse(list_name)

            get_resp = c.get(create_url)
            assert get_resp.status_code == 302, (
                f"Expected 302 redirect for tenant=None GET {create_url}, got {get_resp.status_code}"
            )
            assert get_resp.url == list_url

            post_resp = c.post(create_url, data=post_data)
            assert post_resp.status_code == 302, (
                f"Expected 302 redirect for tenant=None POST {create_url}, got {post_resp.status_code}"
            )
            assert post_resp.url == list_url

        # List views render 200 with zero records and zero foreign <option> disclosure
        for list_name, ctx_key in (
            ("assets:asset_integration_connector_list", "connectors"),
            ("assets:asset_telemetry_stream_list", "streams"),
            ("assets:asset_gl_sync_batch_list", "batches"),
            ("assets:asset_gis_mapping_list", "mappings"),
        ):
            resp = c.get(reverse(list_name))
            assert resp.status_code == 200
            html = resp.content.decode("utf-8")
            assert resp.context["total_count"] == 0
            assert list(resp.context[ctx_key]) == []
            assert integration_connector_a.name not in html
            assert integration_connector_b.name not in html
            assert integration_stream_a.stream_name not in html
            assert integration_gl_batch_a.external_batch_ref not in html
            assert integration_gis_mapping_a.external_feature_id not in html
            if "connectors" in resp.context and ctx_key != "connectors":
                assert list(resp.context["connectors"]) == []
            if "assets_list" in resp.context:
                assert list(resp.context["assets_list"]) == []

        # Direct PK access returns 404 across detail, edit, delete, and actions
        for url in [
            reverse(
                "assets:asset_integration_connector_detail",
                args=[integration_connector_a.pk],
            ),
            reverse(
                "assets:asset_integration_connector_edit",
                args=[integration_connector_a.pk],
            ),
            reverse(
                "assets:asset_telemetry_stream_detail",
                args=[integration_stream_a.pk],
            ),
            reverse(
                "assets:asset_telemetry_stream_edit",
                args=[integration_stream_a.pk],
            ),
            reverse(
                "assets:asset_gl_sync_batch_detail",
                args=[integration_gl_batch_a.pk],
            ),
            reverse(
                "assets:asset_gl_sync_batch_edit",
                args=[integration_gl_batch_a.pk],
            ),
            reverse(
                "assets:asset_gis_mapping_detail",
                args=[integration_gis_mapping_a.pk],
            ),
            reverse(
                "assets:asset_gis_mapping_edit",
                args=[integration_gis_mapping_a.pk],
            ),
        ]:
            assert c.get(url).status_code == 404

        for url in _integration_api_hub_sec_post_only_routes(
            integration_connector_a,
            integration_stream_a,
            integration_gl_batch_a,
            integration_gis_mapping_a,
        ):
            assert c.post(url, {}).status_code == 404

        assert _integration_api_hub_sec_snapshot_counts() == before_counts

    def test_integration_api_hub_tenant_none_non_superuser_accounts_fail_closed(
        self, integration_connector_a, operational_asset_a
    ):
        tenantless_admin = User.objects.create_user(
            email="tenantless_admin_hub@naverp.test",
            username="tenantless_admin_hub",
            password="TestPass123!",
            tenant=None,
            is_tenant_admin=True,
        )
        tenantless_member = User.objects.create_user(
            email="tenantless_member_hub@naverp.test",
            username="tenantless_member_hub",
            password="TestPass123!",
            tenant=None,
            is_tenant_admin=False,
        )

        c_admin = Client()
        c_admin.force_login(tenantless_admin)
        for create_name, list_name in (
            (
                "assets:asset_integration_connector_create",
                "assets:asset_integration_connector_list",
            ),
            (
                "assets:asset_telemetry_stream_create",
                "assets:asset_telemetry_stream_list",
            ),
            (
                "assets:asset_gl_sync_batch_create",
                "assets:asset_gl_sync_batch_list",
            ),
            (
                "assets:asset_gis_mapping_create",
                "assets:asset_gis_mapping_list",
            ),
        ):
            r_get = c_admin.get(reverse(create_name))
            assert r_get.status_code == 302
            assert r_get.url == reverse(list_name)
            r_post = c_admin.post(reverse(create_name), {})
            assert r_post.status_code == 302
            assert r_post.url == reverse(list_name)

        c_member = Client()
        c_member.force_login(tenantless_member)
        assert (
            c_member.get(
                reverse("assets:asset_integration_connector_create")
            ).status_code
            == 403
        )
        assert (
            c_member.post(
                reverse("assets:asset_integration_connector_create"), {}
            ).status_code
            == 403
        )
        for create_name, list_name in (
            (
                "assets:asset_telemetry_stream_create",
                "assets:asset_telemetry_stream_list",
            ),
            (
                "assets:asset_gl_sync_batch_create",
                "assets:asset_gl_sync_batch_list",
            ),
            (
                "assets:asset_gis_mapping_create",
                "assets:asset_gis_mapping_list",
            ),
        ):
            assert c_member.get(reverse(create_name)).status_code == 302
            assert (
                c_member.post(
                    reverse(create_name),
                    {"connector": str(integration_connector_a.pk), "operational_asset": str(operational_asset_a.pk)},
                ).status_code
                == 302
            )

        assert AssetIntegrationConnector.objects.filter(tenant__isnull=True).count() == 0
        assert AssetTelemetryStream.objects.filter(tenant__isnull=True).count() == 0
        assert AssetGlSyncBatch.objects.filter(tenant__isnull=True).count() == 0
        assert AssetGisMapping.objects.filter(tenant__isnull=True).count() == 0


# =====================================================================
# 4. Role Authorization (@tenant_admin_required) & Template Parity
# =====================================================================


class TestIntegrationApiHubRoleAuthorizationAndTemplateParity:
    """Enforce @tenant_admin_required on 8 privileged routes and UI template parity."""

    def test_integration_api_hub_member_denied_all_8_admin_routes_with_403(
        self,
        member_client,
        integration_connector_a,
        integration_stream_a,
        integration_gl_batch_a,
        integration_gis_mapping_a,
    ):
        before_counts = _integration_api_hub_sec_snapshot_counts()
        orig_hash = integration_connector_a.api_key_hash

        admin_form_urls = [
            reverse("assets:asset_integration_connector_create"),
            reverse(
                "assets:asset_integration_connector_edit",
                args=[integration_connector_a.pk],
            ),
        ]
        for url in admin_form_urls:
            assert member_client.get(url).status_code == 403
            assert (
                member_client.post(
                    url, _integration_api_hub_sec_connector_payload(name="Member Escalation")
                ).status_code
                == 403
            )

        admin_post_urls = [
            reverse(
                "assets:asset_integration_connector_delete",
                args=[integration_connector_a.pk],
            ),
            reverse(
                "assets:asset_integration_connector_rotate_secret",
                args=[integration_connector_a.pk],
            ),
            reverse(
                "assets:asset_telemetry_stream_delete",
                args=[integration_stream_a.pk],
            ),
            reverse(
                "assets:asset_gl_sync_batch_delete",
                args=[integration_gl_batch_a.pk],
            ),
            reverse(
                "assets:asset_gl_sync_batch_execute",
                args=[integration_gl_batch_a.pk],
            ),
            reverse(
                "assets:asset_gis_mapping_delete",
                args=[integration_gis_mapping_a.pk],
            ),
        ]
        for url in admin_post_urls:
            assert member_client.get(url).status_code == 403
            assert member_client.post(url, {}).status_code == 403

        assert _integration_api_hub_sec_snapshot_counts() == before_counts
        integration_connector_a.refresh_from_db()
        assert integration_connector_a.api_key_hash == orig_hash

    def test_integration_api_hub_member_allowed_operational_routes_and_workflows(
        self,
        member_client,
        tenant_a,
        operational_asset_a,
        integration_connector_a,
        integration_stream_a,
        integration_gl_batch_a,
        integration_gis_mapping_a,
    ):
        # Reads: all 4 lists and 4 details return 200
        for url in [
            reverse("assets:asset_integration_connector_list"),
            reverse(
                "assets:asset_integration_connector_detail",
                args=[integration_connector_a.pk],
            ),
            reverse("assets:asset_telemetry_stream_list"),
            reverse(
                "assets:asset_telemetry_stream_detail",
                args=[integration_stream_a.pk],
            ),
            reverse("assets:asset_gl_sync_batch_list"),
            reverse(
                "assets:asset_gl_sync_batch_detail",
                args=[integration_gl_batch_a.pk],
            ),
            reverse("assets:asset_gis_mapping_list"),
            reverse(
                "assets:asset_gis_mapping_detail",
                args=[integration_gis_mapping_a.pk],
            ),
        ]:
            assert member_client.get(url).status_code == 200

        # Non-admin create & edit for stream, batch, mapping
        assert (
            member_client.post(
                reverse("assets:asset_telemetry_stream_create"),
                _integration_api_hub_sec_stream_payload(
                    integration_connector_a,
                    operational_asset_a,
                    stream_name="Member Created Stream",
                ),
            ).status_code
            == 302
        )
        assert AssetTelemetryStream.objects.filter(
            tenant=tenant_a, stream_name="Member Created Stream"
        ).exists()

        assert (
            member_client.post(
                reverse(
                    "assets:asset_telemetry_stream_edit",
                    args=[integration_stream_a.pk],
                ),
                _integration_api_hub_sec_stream_payload(
                    integration_connector_a,
                    operational_asset_a,
                    stream_name="Member Edited Stream",
                ),
            ).status_code
            == 302
        )

        assert (
            member_client.post(
                reverse("assets:asset_gl_sync_batch_create"),
                _integration_api_hub_sec_batch_payload(
                    integration_connector_a, external_batch_ref="MEMBER-BATCH-01"
                ),
            ).status_code
            == 302
        )
        assert (
            member_client.post(
                reverse(
                    "assets:asset_gl_sync_batch_edit",
                    args=[integration_gl_batch_a.pk],
                ),
                _integration_api_hub_sec_batch_payload(
                    integration_connector_a, external_batch_ref="MEMBER-EDITED-BATCH"
                ),
            ).status_code
            == 302
        )

        assert (
            member_client.post(
                reverse("assets:asset_gis_mapping_create"),
                _integration_api_hub_sec_mapping_payload(
                    integration_connector_a, external_feature_id="MEMBER-GIS-01"
                ),
            ).status_code
            == 302
        )
        assert (
            member_client.post(
                reverse(
                    "assets:asset_gis_mapping_edit",
                    args=[integration_gis_mapping_a.pk],
                ),
                _integration_api_hub_sec_mapping_payload(
                    integration_connector_a, external_feature_id="MEMBER-EDITED-GIS"
                ),
            ).status_code
            == 302
        )

        # Non-admin operational actions: test_connection, ingest, verify_spatial_sync
        assert (
            member_client.post(
                reverse(
                    "assets:asset_integration_connector_test",
                    args=[integration_connector_a.pk],
                )
            ).status_code
            == 302
        )
        integration_connector_a.refresh_from_db()
        assert integration_connector_a.health_status == "healthy"

        assert (
            member_client.post(
                reverse(
                    "assets:asset_telemetry_stream_ingest",
                    args=[integration_stream_a.pk],
                ),
                {"raw_value": "60.0000"},
            ).status_code
            == 302
        )
        integration_stream_a.refresh_from_db()
        assert integration_stream_a.readings_ingested_count == 1

        assert (
            member_client.post(
                reverse(
                    "assets:asset_gis_mapping_verify_sync",
                    args=[integration_gis_mapping_a.pk],
                )
            ).status_code
            == 302
        )
        integration_gis_mapping_a.refresh_from_db()
        assert integration_gis_mapping_a.drift_status == "attribute_drift"

    def test_integration_api_hub_template_hides_admin_controls_from_member_and_shows_to_admin(
        self,
        client_a,
        member_client,
        integration_connector_a,
        integration_stream_a,
        integration_gl_batch_a,
        integration_gis_mapping_a,
    ):
        conn_create_url = reverse("assets:asset_integration_connector_create")
        conn_edit_url = reverse(
            "assets:asset_integration_connector_edit", args=[integration_connector_a.pk]
        )
        conn_del_url = reverse(
            "assets:asset_integration_connector_delete", args=[integration_connector_a.pk]
        )
        conn_rot_url = reverse(
            "assets:asset_integration_connector_rotate_secret",
            args=[integration_connector_a.pk],
        )
        conn_test_url = reverse(
            "assets:asset_integration_connector_test", args=[integration_connector_a.pk]
        )

        stream_edit_url = reverse(
            "assets:asset_telemetry_stream_edit", args=[integration_stream_a.pk]
        )
        stream_del_url = reverse(
            "assets:asset_telemetry_stream_delete", args=[integration_stream_a.pk]
        )
        stream_ingest_url = reverse(
            "assets:asset_telemetry_stream_ingest", args=[integration_stream_a.pk]
        )

        batch_edit_url = reverse(
            "assets:asset_gl_sync_batch_edit", args=[integration_gl_batch_a.pk]
        )
        batch_del_url = reverse(
            "assets:asset_gl_sync_batch_delete", args=[integration_gl_batch_a.pk]
        )
        batch_exec_url = reverse(
            "assets:asset_gl_sync_batch_execute", args=[integration_gl_batch_a.pk]
        )

        map_edit_url = reverse(
            "assets:asset_gis_mapping_edit", args=[integration_gis_mapping_a.pk]
        )
        map_del_url = reverse(
            "assets:asset_gis_mapping_delete", args=[integration_gis_mapping_a.pk]
        )
        map_verify_url = reverse(
            "assets:asset_gis_mapping_verify_sync", args=[integration_gis_mapping_a.pk]
        )

        # 1) connector_list
        m_conn_list = member_client.get(
            reverse("assets:asset_integration_connector_list")
        ).content.decode("utf-8")
        a_conn_list = client_a.get(
            reverse("assets:asset_integration_connector_list")
        ).content.decode("utf-8")
        assert conn_create_url not in m_conn_list
        assert "New Connector" not in m_conn_list
        assert conn_edit_url not in m_conn_list
        assert conn_create_url in a_conn_list
        assert conn_edit_url in a_conn_list

        # 2) connector_detail
        m_conn_detail = member_client.get(
            reverse(
                "assets:asset_integration_connector_detail",
                args=[integration_connector_a.pk],
            )
        ).content.decode("utf-8")
        a_conn_detail = client_a.get(
            reverse(
                "assets:asset_integration_connector_detail",
                args=[integration_connector_a.pk],
            )
        ).content.decode("utf-8")
        assert "Rotate Secret" not in m_conn_detail
        assert conn_rot_url not in m_conn_detail
        assert conn_edit_url not in m_conn_detail
        assert conn_del_url not in m_conn_detail
        assert conn_test_url in m_conn_detail
        assert "Rotate Secret" in a_conn_detail
        assert conn_rot_url in a_conn_detail
        assert conn_edit_url in a_conn_detail
        assert conn_del_url in a_conn_detail

        # 3) batch_detail
        m_batch_detail = member_client.get(
            reverse(
                "assets:asset_gl_sync_batch_detail",
                args=[integration_gl_batch_a.pk],
            )
        ).content.decode("utf-8")
        a_batch_detail = client_a.get(
            reverse(
                "assets:asset_gl_sync_batch_detail",
                args=[integration_gl_batch_a.pk],
            )
        ).content.decode("utf-8")
        assert "Execute &amp; Reconcile GL Batch" not in m_batch_detail
        assert batch_exec_url not in m_batch_detail
        assert batch_del_url not in m_batch_detail
        assert batch_edit_url in m_batch_detail
        assert "Execute &amp; Reconcile GL Batch" in a_batch_detail
        assert batch_exec_url in a_batch_detail
        assert batch_del_url in a_batch_detail

        # 4) stream_detail
        m_stream_detail = member_client.get(
            reverse(
                "assets:asset_telemetry_stream_detail",
                args=[integration_stream_a.pk],
            )
        ).content.decode("utf-8")
        a_stream_detail = client_a.get(
            reverse(
                "assets:asset_telemetry_stream_detail",
                args=[integration_stream_a.pk],
            )
        ).content.decode("utf-8")
        assert stream_del_url not in m_stream_detail
        assert stream_edit_url in m_stream_detail
        assert stream_ingest_url in m_stream_detail
        assert stream_del_url in a_stream_detail

        # 5) mapping_detail
        m_map_detail = member_client.get(
            reverse(
                "assets:asset_gis_mapping_detail",
                args=[integration_gis_mapping_a.pk],
            )
        ).content.decode("utf-8")
        a_map_detail = client_a.get(
            reverse(
                "assets:asset_gis_mapping_detail",
                args=[integration_gis_mapping_a.pk],
            )
        ).content.decode("utf-8")
        assert map_del_url not in m_map_detail
        assert map_edit_url in m_map_detail
        assert map_verify_url in m_map_detail
        assert map_del_url in a_map_detail


# =====================================================================
# 5. Mass Assignment, Posted GL Lock, Concurrency & FK Forgery
# =====================================================================


class TestIntegrationApiHubMassAssignmentStateAndFkForgery:
    """Block mass assignment, state-machine bypass, and cross-tenant FK injection."""

    def test_integration_api_hub_mass_assignment_smuggled_system_fields_ignored_on_create_and_edit(
        self,
        client_a,
        tenant_a,
        tenant_b,
        operational_asset_a,
        admin_user,
        integration_connector_a,
        integration_stream_a,
        integration_gl_batch_a,
        integration_gis_mapping_a,
    ):
        # Create foreign/dummy records to attempt smuggling into excluded FK fields
        foreign_reading = AssetTelemetryReading.objects.create(
            tenant=tenant_b,
            sensor_identifier="FORGED-READ",
            reading_value=Decimal("99.0000"),
            metric_type="bearing_temperature",
            metric_unit="celsius",
        )
        foreign_mr = _integration_api_hub_sec_make_maintenance_request(
            tenant_b, operational_asset_a, None, admin_user, index=99
        )
        foreign_je = JournalEntry.objects.create(
            tenant=tenant_b,
            entry_type="recurring",
            entry_date=timezone.localdate(),
            description="Foreign JE",
            status="posted",
        )

        # 1) Connector create + edit smuggling
        r_conn = client_a.post(
            reverse("assets:asset_integration_connector_create"),
            _integration_api_hub_sec_connector_payload(
                name="Mass Assign Safe Conn",
                tenant=str(tenant_b.pk),
                number="AICN-99999",
                health_status="healthy",
                api_key_prefix="aicn_forged",
                api_key_hash="f" * 64,
                consecutive_failures="99",
                last_error_message="forged error",
                last_heartbeat_at="2026-01-01T00:00:00Z",
                last_sync_at="2026-01-01T00:00:00Z",
            ),
        )
        assert r_conn.status_code == 302
        c_created = AssetIntegrationConnector.objects.get(
            tenant=tenant_a, name="Mass Assign Safe Conn"
        )
        assert c_created.tenant_id == tenant_a.pk
        assert c_created.number != "AICN-99999"
        assert c_created.health_status == "unverified"
        assert c_created.api_key_prefix == ""
        assert c_created.api_key_hash == ""
        assert c_created.consecutive_failures == 0
        assert c_created.last_error_message == ""
        assert c_created.last_heartbeat_at is None
        assert c_created.last_sync_at is None

        orig_hash = integration_connector_a.api_key_hash
        orig_prefix = integration_connector_a.api_key_prefix
        r_conn_ed = client_a.post(
            reverse(
                "assets:asset_integration_connector_edit",
                args=[integration_connector_a.pk],
            ),
            _integration_api_hub_sec_connector_payload(
                name="Mass Assign Safe Conn Edit",
                tenant=str(tenant_b.pk),
                number="AICN-88888",
                health_status="healthy",
                api_key_prefix="aicn_evil",
                api_key_hash="e" * 64,
                consecutive_failures="42",
                last_error_message="tampered",
            ),
        )
        assert r_conn_ed.status_code == 302
        integration_connector_a.refresh_from_db()
        assert integration_connector_a.tenant_id == tenant_a.pk
        assert integration_connector_a.number != "AICN-88888"
        assert integration_connector_a.health_status == "unverified"
        assert integration_connector_a.api_key_prefix == orig_prefix
        assert integration_connector_a.api_key_hash == orig_hash
        assert integration_connector_a.consecutive_failures == 0
        assert integration_connector_a.last_error_message == ""

        # 2) Telemetry stream create + edit smuggling
        r_stream = client_a.post(
            reverse("assets:asset_telemetry_stream_create"),
            _integration_api_hub_sec_stream_payload(
                integration_connector_a,
                operational_asset_a,
                stream_name="Mass Assign Safe Stream",
                tenant=str(tenant_b.pk),
                number="ATMS-99999",
                last_ingested_value="999.9999",
                readings_ingested_count="500",
                last_telemetry_reading=str(foreign_reading.pk),
                latest_maintenance_request=str(foreign_mr.pk),
                last_ingested_at="2026-01-01T00:00:00Z",
            ),
        )
        assert r_stream.status_code == 302
        s_created = AssetTelemetryStream.objects.get(
            tenant=tenant_a, stream_name="Mass Assign Safe Stream"
        )
        assert s_created.tenant_id == tenant_a.pk
        assert s_created.number != "ATMS-99999"
        assert s_created.last_ingested_value is None
        assert s_created.readings_ingested_count == 0
        assert s_created.last_telemetry_reading is None
        assert s_created.latest_maintenance_request is None
        assert s_created.last_ingested_at is None

        client_a.post(
            reverse(
                "assets:asset_telemetry_stream_edit",
                args=[integration_stream_a.pk],
            ),
            _integration_api_hub_sec_stream_payload(
                integration_connector_a,
                operational_asset_a,
                stream_name="Mass Assign Safe Stream Edit",
                tenant=str(tenant_b.pk),
                number="ATMS-88888",
                readings_ingested_count="777",
                last_telemetry_reading=str(foreign_reading.pk),
            ),
        )
        integration_stream_a.refresh_from_db()
        assert integration_stream_a.tenant_id == tenant_a.pk
        assert integration_stream_a.number != "ATMS-88888"
        assert integration_stream_a.readings_ingested_count == 0
        assert integration_stream_a.last_telemetry_reading is None

        # 3) GL sync batch create + edit smuggling
        r_batch = client_a.post(
            reverse("assets:asset_gl_sync_batch_create"),
            _integration_api_hub_sec_batch_payload(
                integration_connector_a,
                external_batch_ref="MASS-SAFE-BATCH",
                source_amount="1500.00",
                target_gl_amount="1200.00",
                tenant=str(tenant_b.pk),
                number="AGLS-99999",
                status="posted",
                reconciliation_status="reconciled",
                variance_amount="0.00",
                journal_entry=str(foreign_je.pk),
                executed_by=str(admin_user.pk),
                records_processed="10",
                records_succeeded="10",
                records_failed="0",
                synced_at="2026-01-01T00:00:00Z",
            ),
        )
        assert r_batch.status_code == 302
        b_created = AssetGlSyncBatch.objects.get(
            tenant=tenant_a, external_batch_ref="MASS-SAFE-BATCH"
        )
        assert b_created.tenant_id == tenant_a.pk
        assert b_created.number != "AGLS-99999"
        assert b_created.status == "draft"
        assert b_created.reconciliation_status == "pending"
        assert b_created.variance_amount == Decimal("300.00")
        assert b_created.journal_entry is None
        assert b_created.executed_by is None
        assert b_created.records_processed == 0
        assert b_created.synced_at is None

        client_a.post(
            reverse(
                "assets:asset_gl_sync_batch_edit",
                args=[integration_gl_batch_a.pk],
            ),
            _integration_api_hub_sec_batch_payload(
                integration_connector_a,
                external_batch_ref="MASS-SAFE-BATCH-EDIT",
                source_amount="2000.00",
                target_gl_amount="1900.00",
                tenant=str(tenant_b.pk),
                number="AGLS-88888",
                status="posted",
                reconciliation_status="reconciled",
                variance_amount="0.00",
                journal_entry=str(foreign_je.pk),
            ),
        )
        integration_gl_batch_a.refresh_from_db()
        assert integration_gl_batch_a.tenant_id == tenant_a.pk
        assert integration_gl_batch_a.number != "AGLS-88888"
        assert integration_gl_batch_a.status == "ready"
        assert integration_gl_batch_a.reconciliation_status == "pending"
        assert integration_gl_batch_a.variance_amount == Decimal("100.00")
        assert integration_gl_batch_a.journal_entry is None

        # 4) GIS mapping create + edit smuggling
        r_map = client_a.post(
            reverse("assets:asset_gis_mapping_create"),
            _integration_api_hub_sec_mapping_payload(
                integration_connector_a,
                external_feature_id="MASS-SAFE-GIS",
                tenant=str(tenant_b.pk),
                number="AGIS-99999",
                drift_status="in_sync",
                last_spatial_sync_at="2026-01-01T00:00:00Z",
            ),
        )
        assert r_map.status_code == 302
        m_created = AssetGisMapping.objects.get(
            tenant=tenant_a, external_feature_id="MASS-SAFE-GIS"
        )
        assert m_created.tenant_id == tenant_a.pk
        assert m_created.number != "AGIS-99999"
        assert m_created.drift_status == "unverified"
        assert m_created.last_spatial_sync_at is None

        client_a.post(
            reverse(
                "assets:asset_gis_mapping_edit",
                args=[integration_gis_mapping_a.pk],
            ),
            _integration_api_hub_sec_mapping_payload(
                integration_connector_a,
                external_feature_id="MASS-SAFE-GIS-EDIT",
                tenant=str(tenant_b.pk),
                number="AGIS-88888",
                drift_status="in_sync",
            ),
        )
        integration_gis_mapping_a.refresh_from_db()
        assert integration_gis_mapping_a.tenant_id == tenant_a.pk
        assert integration_gis_mapping_a.number != "AGIS-88888"
        assert integration_gis_mapping_a.drift_status == "unverified"

    def test_integration_api_hub_posted_batch_immutability_and_replay_guards(
        self,
        client_a,
        tenant_a,
        integration_connector_a,
        integration_open_fiscal_period_a,
        integration_closed_fiscal_period_a,
        expense_account_a,
        asset_account_a,
    ):
        batch = _integration_api_hub_sec_make_batch(
            tenant_a,
            integration_connector_a,
            index=201,
            sync_domain="capitalization_sync",
            fiscal_period=integration_open_fiscal_period_a,
            gl_account=expense_account_a,
            offset_gl_account=asset_account_a,
            batch_date=integration_open_fiscal_period_a.start_date,
            source_amount=Decimal("2450.00"),
            target_gl_amount=Decimal("2450.00"),
            status="ready",
        )
        exec_url = reverse("assets:asset_gl_sync_batch_execute", args=[batch.pk])
        edit_url = reverse("assets:asset_gl_sync_batch_edit", args=[batch.pk])
        del_url = reverse("assets:asset_gl_sync_batch_delete", args=[batch.pk])
        detail_url = reverse("assets:asset_gl_sync_batch_detail", args=[batch.pk])

        je_before = JournalEntry.objects.filter(tenant=tenant_a).count()
        assert client_a.post(exec_url).status_code == 302
        batch.refresh_from_db()
        assert batch.status == "posted"
        assert batch.journal_entry is not None
        assert JournalEntry.objects.filter(tenant=tenant_a).count() == je_before + 1

        audit_before = AuditLog.objects.count()
        orig_je_id = batch.journal_entry_id
        orig_synced_at = batch.synced_at

        # Edit GET/POST, Delete POST, and Replay Execute POST all blocked
        r_edit_get = client_a.get(edit_url)
        assert r_edit_get.status_code == 302
        assert r_edit_get.url == detail_url

        r_edit_post = client_a.post(
            edit_url,
            _integration_api_hub_sec_batch_payload(
                integration_connector_a, external_batch_ref="BYPASS-EDIT"
            ),
        )
        assert r_edit_post.status_code == 302
        assert r_edit_post.url == detail_url

        r_del_post = client_a.post(del_url)
        assert r_del_post.status_code == 302
        assert r_del_post.url == detail_url
        assert AssetGlSyncBatch.objects.filter(pk=batch.pk).exists()

        r_replay = client_a.post(exec_url)
        assert r_replay.status_code == 302
        assert any(
            "already posted" in m.lower()
            for m in _integration_api_hub_sec_msg_texts(r_replay)
        )

        batch.refresh_from_db()
        assert batch.external_batch_ref != "BYPASS-EDIT"
        assert batch.journal_entry_id == orig_je_id
        assert batch.synced_at == orig_synced_at
        assert JournalEntry.objects.filter(tenant=tenant_a).count() == je_before + 1
        assert JournalLine.objects.filter(entry_id=orig_je_id).count() == 2
        assert AuditLog.objects.count() == audit_before

        # Invariant guard: status="posted" even without JE still blocks edit/delete/execute
        b_status_only = _integration_api_hub_sec_make_batch(
            tenant_a, integration_connector_a, index=202, status="posted"
        )
        assert (
            client_a.get(
                reverse("assets:asset_gl_sync_batch_edit", args=[b_status_only.pk])
            ).status_code
            == 302
        )
        assert (
            client_a.post(
                reverse("assets:asset_gl_sync_batch_delete", args=[b_status_only.pk])
            ).status_code
            == 302
        )
        assert AssetGlSyncBatch.objects.filter(pk=b_status_only.pk).exists()
        assert (
            client_a.post(
                reverse("assets:asset_gl_sync_batch_execute", args=[b_status_only.pk])
            ).status_code
            == 302
        )

        # Invariant guard: failed batch rejected cleanly
        b_failed = _integration_api_hub_sec_make_batch(
            tenant_a,
            integration_connector_a,
            index=203,
            status="failed",
            fiscal_period=integration_open_fiscal_period_a,
            gl_account=expense_account_a,
            offset_gl_account=asset_account_a,
        )
        assert (
            client_a.post(
                reverse("assets:asset_gl_sync_batch_execute", args=[b_failed.pk])
            ).status_code
            == 302
        )
        b_failed.refresh_from_db()
        assert b_failed.status == "failed"
        assert b_failed.journal_entry is None

        # Closed AND Locked fiscal periods block execution cleanly without JE
        for period_status in ("closed", "locked"):
            fp = FiscalPeriod.objects.create(
                tenant=tenant_a,
                name=f"Sec {period_status.title()} Period",
                period_type="month",
                start_date=datetime.date(2025, 1, 1),
                end_date=datetime.date(2025, 1, 31),
                status=period_status,
            )
            b_fp = _integration_api_hub_sec_make_batch(
                tenant_a,
                integration_connector_a,
                index=204 if period_status == "closed" else 205,
                fiscal_period=fp,
                gl_account=expense_account_a,
                offset_gl_account=asset_account_a,
                batch_date=fp.start_date,
                status="ready",
            )
            r_fp = client_a.post(
                reverse("assets:asset_gl_sync_batch_execute", args=[b_fp.pk])
            )
            assert r_fp.status_code == 302
            assert any(
                "must be open" in m.lower()
                for m in _integration_api_hub_sec_msg_texts(r_fp)
            )
            b_fp.refresh_from_db()
            assert b_fp.status == "ready"
            assert b_fp.journal_entry is None

        assert JournalEntry.objects.filter(tenant=tenant_a).count() == je_before + 1

    def test_integration_api_hub_execute_and_ingest_use_select_for_update_and_atomic_rollback(
        self,
        client_a,
        tenant_a,
        integration_connector_a,
        integration_open_fiscal_period_a,
        integration_stream_a,
        expense_account_a,
        asset_account_a,
    ):
        batch = _integration_api_hub_sec_make_batch(
            tenant_a,
            integration_connector_a,
            index=210,
            sync_domain="depreciation_posting",
            fiscal_period=integration_open_fiscal_period_a,
            gl_account=expense_account_a,
            offset_gl_account=asset_account_a,
            batch_date=integration_open_fiscal_period_a.start_date,
            source_amount=Decimal("500.00"),
            target_gl_amount=Decimal("500.00"),
            status="ready",
        )

        # 1) Verify select_for_update() is invoked inside atomic block on both actions
        locked_models = []
        orig_sfu = QuerySet.select_for_update

        def _spy_select_for_update(qs_self, *args, **kwargs):
            if qs_self.model in (AssetGlSyncBatch, AssetTelemetryStream):
                assert connection.in_atomic_block is True
                locked_models.append(qs_self.model)
            return orig_sfu(qs_self, *args, **kwargs)

        with patch.object(
            QuerySet, "select_for_update", autospec=True, side_effect=_spy_select_for_update
        ):
            r_ingest = client_a.post(
                reverse(
                    "assets:asset_telemetry_stream_ingest",
                    args=[integration_stream_a.pk],
                ),
                {"raw_value": "55.0000"},
            )
            assert r_ingest.status_code == 302
            assert AssetTelemetryStream in locked_models

            # 2) Simulate mid-transaction failure on second JournalLine.save -> atomic rollback
            je_before = JournalEntry.objects.count()
            jl_before = JournalLine.objects.count()
            audit_before = AuditLog.objects.count()

            orig_jl_save = JournalLine.save
            save_calls = {"count": 0}

            def _failing_second_line_save(jl_self, *args, **kwargs):
                save_calls["count"] += 1
                if save_calls["count"] == 2:
                    raise RuntimeError("Simulated mid-posting DB fault")
                return orig_jl_save(jl_self, *args, **kwargs)

            with patch.object(
                JournalLine,
                "save",
                autospec=True,
                side_effect=_failing_second_line_save,
            ):
                with pytest.raises(RuntimeError, match="Simulated mid-posting DB fault"):
                    client_a.post(
                        reverse("assets:asset_gl_sync_batch_execute", args=[batch.pk])
                    )

            assert AssetGlSyncBatch in locked_models
            assert JournalEntry.objects.count() == je_before
            assert JournalLine.objects.count() == jl_before
            assert AuditLog.objects.count() == audit_before
            batch.refresh_from_db()
            assert batch.status == "ready"
            assert batch.journal_entry is None

    def test_integration_api_hub_cross_tenant_fk_injection_via_http_post_all_4_entities(
        self,
        client_a,
        tenant_a,
        tenant_b,
        admin_b,
        vendor_party_b,
        org_unit_b,
        location_b,
        po_b,
        operational_asset_a,
        operational_asset_b,
        fixed_asset_b,
        capitalization_b,
        expense_account_b,
        accum_account_b,
        integration_open_fiscal_period_b,
        integration_connector_a,
        integration_connector_b,
        integration_stream_a,
        integration_gl_batch_a,
        integration_gis_mapping_a,
    ):
        dep_sched_b = _integration_api_hub_sec_make_depreciation_schedule(
            tenant_b,
            fixed_asset_b,
            operational_asset_b,
            expense_account_b,
            accum_account_b,
            index=1,
        )
        maint_req_b = _integration_api_hub_sec_make_maintenance_request(
            tenant_b, operational_asset_b, fixed_asset_b, admin_b, index=1
        )
        inactive_gl_a = GLAccount.objects.create(
            tenant=tenant_a,
            code="9999-INACT",
            name="Inactive Clearing",
            account_type="expense",
            normal_balance="debit",
            is_active=False,
        )

        before_counts = _integration_api_hub_sec_snapshot_counts()

        # 1) Connector create & edit foreign FK injections
        for fk_name, fk_val in (
            ("vendor_partner", vendor_party_b.pk),
            ("default_org_unit", org_unit_b.pk),
            ("owner", admin_b.pk),
        ):
            r_c = client_a.post(
                reverse("assets:asset_integration_connector_create"),
                _integration_api_hub_sec_connector_payload(**{fk_name: str(fk_val)}),
            )
            assert r_c.status_code == 200
            assert fk_name in r_c.context["form"].errors

            r_e = client_a.post(
                reverse(
                    "assets:asset_integration_connector_edit",
                    args=[integration_connector_a.pk],
                ),
                _integration_api_hub_sec_connector_payload(**{fk_name: str(fk_val)}),
            )
            assert r_e.status_code == 200
            assert fk_name in r_e.context["form"].errors

        # 2) Stream create & edit foreign FK injections
        for fk_name, fk_val in (
            ("connector", integration_connector_b.pk),
            ("operational_asset", operational_asset_b.pk),
            ("fixed_asset", fixed_asset_b.pk),
            ("steward", admin_b.pk),
        ):
            overrides = {fk_name: str(fk_val)}
            if fk_name == "operational_asset":
                overrides["fixed_asset"] = ""
            stream_payload = _integration_api_hub_sec_stream_payload(
                integration_connector_a, operational_asset_a
            )
            stream_payload.update(overrides)
            r_c = client_a.post(
                reverse("assets:asset_telemetry_stream_create"),
                stream_payload,
            )
            assert r_c.status_code == 200
            assert fk_name in r_c.context["form"].errors

            r_e = client_a.post(
                reverse(
                    "assets:asset_telemetry_stream_edit",
                    args=[integration_stream_a.pk],
                ),
                dict(stream_payload),
            )
            assert r_e.status_code == 200
            assert fk_name in r_e.context["form"].errors

        # 3) GL Sync Batch create & edit across all 10 tenant FKs + inactive GL account
        batch_fk_cases = [
            ("connector", integration_connector_b.pk),
            ("fiscal_period", integration_open_fiscal_period_b.pk),
            ("gl_account", expense_account_b.pk),
            ("offset_gl_account", accum_account_b.pk),
            ("fixed_asset", fixed_asset_b.pk),
            ("purchase_order", po_b.pk),
            ("capitalization", capitalization_b.pk),
            ("depreciation_schedule", dep_sched_b.pk),
            ("maintenance_request", maint_req_b.pk),
            ("cost_center", org_unit_b.pk),
            ("gl_account", inactive_gl_a.pk),
        ]
        for fk_name, fk_val in batch_fk_cases:
            batch_payload = _integration_api_hub_sec_batch_payload(
                integration_connector_a
            )
            batch_payload[fk_name] = str(fk_val)
            r_c = client_a.post(
                reverse("assets:asset_gl_sync_batch_create"),
                batch_payload,
            )
            assert r_c.status_code == 200
            assert fk_name in r_c.context["form"].errors

            r_e = client_a.post(
                reverse(
                    "assets:asset_gl_sync_batch_edit",
                    args=[integration_gl_batch_a.pk],
                ),
                dict(batch_payload),
            )
            assert r_e.status_code == 200
            assert fk_name in r_e.context["form"].errors

        # 4) GIS Mapping create & edit foreign FK injections
        for fk_name, fk_val in (
            ("connector", integration_connector_b.pk),
            ("operational_asset", operational_asset_b.pk),
            ("location", location_b.pk),
            ("org_unit", org_unit_b.pk),
            ("gis_custodian", admin_b.pk),
        ):
            mapping_payload = _integration_api_hub_sec_mapping_payload(
                integration_connector_a
            )
            mapping_payload[fk_name] = str(fk_val)
            r_c = client_a.post(
                reverse("assets:asset_gis_mapping_create"),
                mapping_payload,
            )
            assert r_c.status_code == 200
            assert fk_name in r_c.context["form"].errors

            r_e = client_a.post(
                reverse(
                    "assets:asset_gis_mapping_edit",
                    args=[integration_gis_mapping_a.pk],
                ),
                dict(mapping_payload),
            )
            assert r_e.status_code == 200
            assert fk_name in r_e.context["form"].errors

        assert _integration_api_hub_sec_snapshot_counts() == before_counts

    def test_integration_api_hub_action_runtime_guards_block_foreign_fks_attached_in_db(
        self,
        client_a,
        tenant_a,
        org_unit_a,
        org_unit_b,
        operational_asset_a,
        operational_asset_b,
        fixed_asset_a,
        fixed_asset_b,
        expense_account_a,
        expense_account_b,
        asset_account_a,
        accum_account_b,
        integration_connector_a,
        integration_connector_b,
        integration_open_fiscal_period_a,
        integration_open_fiscal_period_b,
    ):
        # 1) execute_reconcile_batch guards across all 5 checked FKs
        batch_fk_cases = [
            ("connector_id", integration_connector_b.pk, "connector"),
            ("fiscal_period_id", integration_open_fiscal_period_b.pk, "fiscal period"),
            ("gl_account_id", expense_account_b.pk, "primary gl account"),
            ("offset_gl_account_id", accum_account_b.pk, "offset gl account"),
            ("cost_center_id", org_unit_b.pk, "cost center"),
        ]
        je_before = JournalEntry.objects.count()
        audit_before = AuditLog.objects.count()

        for idx, (col_name, foreign_pk, label_substr) in enumerate(batch_fk_cases, 1):
            batch = _integration_api_hub_sec_make_batch(
                tenant_a,
                integration_connector_a,
                index=300 + idx,
                fiscal_period=integration_open_fiscal_period_a,
                gl_account=expense_account_a,
                offset_gl_account=asset_account_a,
                cost_center=org_unit_a,
                batch_date=integration_open_fiscal_period_a.start_date,
                source_amount=Decimal("700.00"),
                target_gl_amount=Decimal("700.00"),
                status="ready",
            )
            AssetGlSyncBatch.objects.filter(pk=batch.pk).update(**{col_name: foreign_pk})
            resp = client_a.post(
                reverse("assets:asset_gl_sync_batch_execute", args=[batch.pk])
            )
            assert resp.status_code == 302
            msgs = [m.lower() for m in _integration_api_hub_sec_msg_texts(resp)]
            assert any(
                label_substr in m and "another workspace" in m for m in msgs
            ), f"Expected foreign FK guard for {col_name}, got {msgs}"
            batch.refresh_from_db()
            assert batch.status == "ready"
            assert batch.journal_entry is None

        assert JournalEntry.objects.count() == je_before
        assert AuditLog.objects.count() == audit_before

        # 2) ingest_sample_reading guards across all 3 checked FKs
        stream_fk_cases = [
            ("connector_id", integration_connector_b.pk, "connector"),
            ("operational_asset_id", operational_asset_b.pk, "operational asset"),
            ("fixed_asset_id", fixed_asset_b.pk, "fixed asset"),
        ]
        reading_before = AssetTelemetryReading.objects.count()
        mr_before = AssetMaintenanceRequest.objects.count()

        for idx, (col_name, foreign_pk, label_substr) in enumerate(stream_fk_cases, 1):
            stream = _integration_api_hub_sec_make_stream(
                tenant_a,
                integration_connector_a,
                operational_asset_a,
                index=300 + idx,
                fixed_asset=fixed_asset_a,
            )
            AssetTelemetryStream.objects.filter(pk=stream.pk).update(
                **{col_name: foreign_pk}
            )
            resp = client_a.post(
                reverse("assets:asset_telemetry_stream_ingest", args=[stream.pk]),
                {"raw_value": "95.0000"},
            )
            assert resp.status_code == 302
            msgs = [m.lower() for m in _integration_api_hub_sec_msg_texts(resp)]
            assert any(
                label_substr in m and "another workspace" in m for m in msgs
            ), f"Expected foreign FK guard for {col_name}, got {msgs}"
            stream.refresh_from_db()
            assert stream.readings_ingested_count == 0
            assert stream.last_telemetry_reading is None

        assert AssetTelemetryReading.objects.count() == reading_before
        assert AssetMaintenanceRequest.objects.count() == mr_before
        assert AuditLog.objects.count() == audit_before


# =====================================================================
# 6. SSRF, Secret Lifecycle, XSS, Audit Redaction & Chaos Hardening
# =====================================================================


class TestIntegrationApiHubSsrfSecretXssAndChaosHardening:
    """Block obfuscated SSRF, enforce secret hygiene, XSS escaping, and chaos resilience."""

    @pytest.mark.parametrize(
        "ssrf_url",
        [
            "http://2130706433/admin",
            "http://0x7f000001/admin",
            "http://0177.0.0.1/admin",
            "http://127.1/admin",
            "http://[::ffff:127.0.0.1]/admin",
            "http://[::ffff:169.254.169.254]/latest/meta-data/",
            "http://[2002:7f00:1::]/admin",
            "http://100.64.0.1/internal",
            "http://[::1%25eth0]/admin",
            "https://ok.com\\@127.0.0.1/",
            "https://user:pass@example.com/",
            "http://foo.local/",
            "ftp://example.com",
            "http://metadata.google.internal/computeMetadata/v1/",
            "http://169.254.169.254/latest/meta-data/",
            "https://api.example.com/\r\nX-Injected: 1",
        ],
    )
    def test_integration_api_hub_ssrf_corpus_blocked_via_connector_create_and_edit_http_post(
        self, client_a, integration_connector_a, ssrf_url
    ):
        before_count = AssetIntegrationConnector.objects.count()
        orig_url = integration_connector_a.endpoint_url

        r_create = client_a.post(
            reverse("assets:asset_integration_connector_create"),
            _integration_api_hub_sec_connector_payload(
                name="SSRF Attempt", endpoint_url=ssrf_url
            ),
        )
        assert r_create.status_code == 200
        assert "endpoint_url" in r_create.context["form"].errors
        assert AssetIntegrationConnector.objects.count() == before_count

        r_edit = client_a.post(
            reverse(
                "assets:asset_integration_connector_edit",
                args=[integration_connector_a.pk],
            ),
            _integration_api_hub_sec_connector_payload(
                name="SSRF Edit Attempt", endpoint_url=ssrf_url
            ),
        )
        assert r_edit.status_code == 200
        assert "endpoint_url" in r_edit.context["form"].errors
        integration_connector_a.refresh_from_db()
        assert integration_connector_a.endpoint_url == orig_url

    def test_integration_api_hub_test_connection_db_ssrf_zero_network_io(
        self, client_a, integration_connector_a
    ):
        AssetIntegrationConnector.objects.filter(pk=integration_connector_a.pk).update(
            endpoint_url="http://169.254.169.254/latest/meta-data/"
        )
        with patch.object(
            urllib.request,
            "urlopen",
            side_effect=AssertionError("Outbound HTTP forbidden"),
        ), patch.object(
            socket,
            "create_connection",
            side_effect=AssertionError("Outbound socket forbidden"),
        ):
            resp = client_a.post(
                reverse(
                    "assets:asset_integration_connector_test",
                    args=[integration_connector_a.pk],
                )
            )
        assert resp.status_code == 302
        integration_connector_a.refresh_from_db()
        assert integration_connector_a.health_status == "unreachable"
        assert integration_connector_a.consecutive_failures == 1

    def test_integration_api_hub_secret_hygiene_audit_redaction_and_cross_connector_pop(
        self, client_a, tenant_a
    ):
        # Create two connectors via HTTP POST
        r1 = client_a.post(
            reverse("assets:asset_integration_connector_create"),
            _integration_api_hub_sec_connector_payload(name="Secret Lifecycle A"),
        )
        assert r1.status_code == 302
        conn_a = AssetIntegrationConnector.objects.get(
            tenant=tenant_a, name="Secret Lifecycle A"
        )
        conn_b = _integration_api_hub_sec_make_connector(
            tenant_a, index=41, name="Secret Lifecycle B"
        )
        conn_c = _integration_api_hub_sec_make_connector(
            tenant_a, index=42, name="Secret Lifecycle C (Deletable)"
        )

        # Rotate conn_a
        rot_url = reverse(
            "assets:asset_integration_connector_rotate_secret", args=[conn_a.pk]
        )
        detail_a_url = reverse(
            "assets:asset_integration_connector_detail", args=[conn_a.pk]
        )
        detail_b_url = reverse(
            "assets:asset_integration_connector_detail", args=[conn_b.pk]
        )

        rot_resp = client_a.post(rot_url)
        assert rot_resp.status_code == 302
        conn_a.refresh_from_db()
        secret_hash_1 = conn_a.api_key_hash
        assert len(secret_hash_1) == 64

        plaintext_1 = client_a.session["_aicn_secret_reveal"]["secret"]
        assert (
            hashlib.sha256(plaintext_1.encode("utf-8")).hexdigest() == secret_hash_1
        )

        # Plaintext never flashed in messages
        msgs = _integration_api_hub_sec_msg_texts(rot_resp)
        assert all(plaintext_1 not in m for m in msgs)
        assert all(secret_hash_1 not in m for m in msgs)

        # Unconditional pop: visiting conn_b clears conn_a's reveal immediately
        visit_b = client_a.get(detail_b_url)
        assert visit_b.status_code == 200
        assert visit_b.context["plaintext_once"] is None
        assert plaintext_1 not in visit_b.content.decode("utf-8")
        assert "_aicn_secret_reveal" not in client_a.session

        visit_a_after_b = client_a.get(detail_a_url)
        assert visit_a_after_b.status_code == 200
        assert visit_a_after_b.context["plaintext_once"] is None
        assert plaintext_1 not in visit_a_after_b.content.decode("utf-8")

        # Rotate again, verify first detail reveals once, second hides, hash never in HTML
        client_a.post(rot_url)
        conn_a.refresh_from_db()
        secret_hash_2 = conn_a.api_key_hash
        plaintext_2 = client_a.session["_aicn_secret_reveal"]["secret"]

        first_a = client_a.get(detail_a_url)
        assert first_a.context["plaintext_once"] == plaintext_2
        first_html = first_a.content.decode("utf-8")
        assert plaintext_2 in first_html
        assert secret_hash_2 not in first_html
        assert "_aicn_secret_reveal" not in client_a.session

        second_a = client_a.get(detail_a_url)
        assert second_a.context["plaintext_once"] is None
        assert plaintext_2 not in second_a.content.decode("utf-8")
        assert secret_hash_2 not in second_a.content.decode("utf-8")

        # List and edit HTML also never leak api_key_hash or plaintext
        list_html = client_a.get(
            reverse("assets:asset_integration_connector_list")
        ).content.decode("utf-8")
        edit_html = client_a.get(
            reverse("assets:asset_integration_connector_edit", args=[conn_a.pk])
        ).content.decode("utf-8")
        assert secret_hash_1 not in list_html and secret_hash_2 not in list_html
        assert secret_hash_1 not in edit_html and secret_hash_2 not in edit_html
        assert plaintext_1 not in list_html and plaintext_2 not in list_html

        # Malformed session reveal value does not crash connector_detail
        session = client_a.session
        session["_aicn_secret_reveal"] = "corrupted-non-dict"
        session.save()
        corrupt_resp = client_a.get(detail_a_url)
        assert corrupt_resp.status_code == 200
        assert corrupt_resp.context["plaintext_once"] is None
        assert "_aicn_secret_reveal" not in client_a.session

        # Run test and delete on conn_c, then audit every AuditLog row
        client_a.post(
            reverse("assets:asset_integration_connector_test", args=[conn_a.pk])
        )
        client_a.post(
            reverse("assets:asset_integration_connector_edit", args=[conn_a.pk]),
            _integration_api_hub_sec_connector_payload(name="Secret Lifecycle A Updated"),
        )
        client_a.post(
            reverse("assets:asset_integration_connector_delete", args=[conn_c.pk])
        )

        for log in AuditLog.objects.filter(tenant=tenant_a):
            serialized = f"{log.target} {log.changes}"
            assert secret_hash_1 not in serialized
            assert secret_hash_2 not in serialized
            assert plaintext_1 not in serialized
            assert plaintext_2 not in serialized

    def test_integration_api_hub_stored_xss_escaped_across_all_4_entities(
        self,
        client_a,
        tenant_a,
        operational_asset_a,
        integration_connector_a,
    ):
        xss_script = "<script>alert('xss_hub')</script>"
        xss_img = '<img src=x onerror="alert(1)">'

        # Create connector with XSS payload
        assert (
            client_a.post(
                reverse("assets:asset_integration_connector_create"),
                _integration_api_hub_sec_connector_payload(
                    name=f"Conn {xss_script}", notes=xss_img
                ),
            ).status_code
            == 302
        )
        c_xss = AssetIntegrationConnector.objects.get(
            tenant=tenant_a, name__contains="xss_hub"
        )

        # Create stream with XSS payload
        assert (
            client_a.post(
                reverse("assets:asset_telemetry_stream_create"),
                _integration_api_hub_sec_stream_payload(
                    integration_connector_a,
                    operational_asset_a,
                    stream_name=f"Stream {xss_script}",
                    tag_address=f"ns=2;s={xss_img}",
                    notes=xss_script,
                ),
            ).status_code
            == 302
        )
        s_xss = AssetTelemetryStream.objects.get(
            tenant=tenant_a, stream_name__contains="xss_hub"
        )

        # Create batch with XSS payload
        assert (
            client_a.post(
                reverse("assets:asset_gl_sync_batch_create"),
                _integration_api_hub_sec_batch_payload(
                    integration_connector_a,
                    external_batch_ref=f"REF-{xss_script}",
                    payload_summary=xss_img,
                    notes=xss_script,
                ),
            ).status_code
            == 302
        )
        b_xss = AssetGlSyncBatch.objects.get(
            tenant=tenant_a, external_batch_ref__contains="xss_hub"
        )

        # Create GIS mapping with XSS payload
        assert (
            client_a.post(
                reverse("assets:asset_gis_mapping_create"),
                _integration_api_hub_sec_mapping_payload(
                    integration_connector_a,
                    layer_name=f"layer_{xss_script}",
                    external_feature_id=f"FEAT-{xss_img}",
                    notes=xss_script,
                ),
            ).status_code
            == 302
        )
        m_xss = AssetGisMapping.objects.get(
            tenant=tenant_a, layer_name__contains="xss_hub"
        )

        render_urls = [
            reverse("assets:asset_integration_connector_list"),
            reverse("assets:asset_integration_connector_detail", args=[c_xss.pk]),
            reverse("assets:asset_telemetry_stream_list"),
            reverse("assets:asset_telemetry_stream_detail", args=[s_xss.pk]),
            reverse("assets:asset_gl_sync_batch_list"),
            reverse("assets:asset_gl_sync_batch_detail", args=[b_xss.pk]),
            reverse("assets:asset_gis_mapping_list"),
            reverse("assets:asset_gis_mapping_detail", args=[m_xss.pk]),
        ]
        escaped_script = escape(xss_script)
        escaped_img = escape(xss_img)
        for url in render_urls:
            resp = client_a.get(url)
            assert resp.status_code == 200
            html = resp.content.decode("utf-8")
            assert xss_script not in html
            assert xss_img not in html
            assert escaped_script in html or escaped_img in html

    def test_integration_api_hub_json_recursion_nan_infinity_and_size_bounds_rejected(
        self, client_a, integration_connector_a
    ):
        before_batches = AssetGlSyncBatch.objects.count()
        before_mappings = AssetGisMapping.objects.count()

        deep_json = ('{"a":' * 2000) + "1" + ("}" * 2000)
        oversized_json = '{"k":"' + ("a" * 66000) + '"}'
        oversized_summary = "P" * 65600

        bad_json_cases = [
            deep_json,
            '{"v": NaN}',
            '{"v": Infinity}',
            '{"v": -Infinity}',
            '["not", "an", "object"]',
            '"scalar-string"',
            oversized_json,
        ]

        batch_create_url = reverse("assets:asset_gl_sync_batch_create")
        map_create_url = reverse("assets:asset_gis_mapping_create")

        for bad_json in bad_json_cases:
            r_b = client_a.post(
                batch_create_url,
                _integration_api_hub_sec_batch_payload(
                    integration_connector_a, field_mapping_json=bad_json
                ),
            )
            assert r_b.status_code == 200
            assert "field_mapping_json" in r_b.context["form"].errors

            r_m = client_a.post(
                map_create_url,
                _integration_api_hub_sec_mapping_payload(
                    integration_connector_a, geojson_payload=bad_json
                ),
            )
            assert r_m.status_code == 200
            assert "geojson_payload" in r_m.context["form"].errors

        r_sum = client_a.post(
            batch_create_url,
            _integration_api_hub_sec_batch_payload(
                integration_connector_a, payload_summary=oversized_summary
            ),
        )
        assert r_sum.status_code == 200
        assert "payload_summary" in r_sum.context["form"].errors

        assert AssetGlSyncBatch.objects.count() == before_batches
        assert AssetGisMapping.objects.count() == before_mappings

    def test_integration_api_hub_extreme_decimal_ingest_and_unicode_query_chaos_resistance(
        self, client_a, tenant_a, operational_asset_a, integration_connector_a
    ):
        scaled_stream = _integration_api_hub_sec_make_stream(
            tenant_a,
            integration_connector_a,
            operational_asset_a,
            index=501,
            scale_factor=Decimal("2.000000"),
            deadband_delta=Decimal("0.0000"),
        )
        ingest_url = reverse(
            "assets:asset_telemetry_stream_ingest", args=[scaled_stream.pk]
        )
        readings_before = AssetTelemetryReading.objects.count()

        for bad_raw in (
            "1e50",
            "-1e50",
            "9999999999999",
            "99999999.9999",  # overflows 99,999,999.9999 when * scale_factor=2
            "NaN",
            "Infinity",
            "-Infinity",
            "sNaN",
            "1" * 33,
            "not_a_decimal",
        ):
            r = client_a.post(ingest_url, {"raw_value": bad_raw})
            assert r.status_code == 302
            msgs = _integration_api_hub_sec_msg_texts(r)
            assert msgs, f"Expected error flash message for raw_value={bad_raw!r}"

        scaled_stream.refresh_from_db()
        assert scaled_stream.readings_ingested_count == 0
        assert AssetTelemetryReading.objects.count() == readings_before

        # Unicode superscript, Arabic-Indic digit, huge int, negative int, SQLi, XSS in GET params
        chaos_queries = [
            "\u00b2",
            "\u0662",
            "NaN",
            "-99",
            "9999999999999999999999999999",
            "' OR 1=1--",
            "<script>alert(1)</script>",
            "2026-99-99",
        ]
        for q_val in chaos_queries:
            for list_url_name in (
                "assets:asset_integration_connector_list",
                "assets:asset_telemetry_stream_list",
                "assets:asset_gl_sync_batch_list",
                "assets:asset_gis_mapping_list",
            ):
                resp = client_a.get(
                    reverse(list_url_name),
                    {
                        "q": q_val,
                        "connector": q_val,
                        "operational_asset": q_val,
                        "date_from": q_val,
                        "date_to": q_val,
                        "page": q_val,
                        "status": q_val,
                    },
                )
                assert resp.status_code == 200
                assert "<script>alert(1)</script>" not in resp.content.decode("utf-8")

            for create_url_name in (
                "assets:asset_telemetry_stream_create",
                "assets:asset_gl_sync_batch_create",
                "assets:asset_gis_mapping_create",
            ):
                resp_c = client_a.get(
                    reverse(create_url_name), {"connector": q_val}
                )
                assert resp_c.status_code == 200


# =====================================================================
# 7. Multi-User Isolation & Role Matrix at Scale (100 Dummy Users)
# =====================================================================


class TestIntegrationApiHubScaleUserIsolation:
    """Create 100 heterogeneous dummy users (60 tenant_a, 40 tenant_b) and verify isolation & RBAC."""

    def test_integration_api_hub_100_dummy_users_bulk_tenant_isolation_and_role_matrix(
        self,
        tenant_a,
        tenant_b,
        integration_connector_a,
        integration_connector_b,
        integration_stream_a,
        integration_stream_b,
        integration_gl_batch_a,
        integration_gl_batch_b,
        integration_gis_mapping_a,
        integration_gis_mapping_b,
    ):
        role_names = ("Admin", "Manager", "Staff", "Auditor")
        roles_a = {
            name: Role.objects.get_or_create(tenant=tenant_a, name=name)[0]
            for name in role_names
        }
        roles_b = {
            name: Role.objects.get_or_create(tenant=tenant_b, name=name)[0]
            for name in role_names
        }

        fast_hash = make_password("password")
        bulk_users = []

        # 60 heterogeneous users in tenant_a: 15 Admin, 15 Manager, 15 Staff, 15 Auditor
        for idx in range(60):
            role_name = role_names[idx % 4]
            bulk_users.append(
                User(
                    email=f"bulk_hub_a_{idx:02d}@acme.test",
                    username=f"bulk_hub_a_{idx:02d}",
                    first_name="BulkA",
                    last_name=f"{role_name}{idx:02d}",
                    tenant=tenant_a,
                    role=roles_a[role_name],
                    is_tenant_admin=(role_name == "Admin"),
                    status="active",
                    is_active=True,
                    is_staff=False,
                    is_superuser=False,
                    password=fast_hash,
                )
            )

        # 40 heterogeneous users in tenant_b: 10 Admin, 10 Manager, 10 Staff, 10 Auditor
        for idx in range(40):
            role_name = role_names[idx % 4]
            bulk_users.append(
                User(
                    email=f"bulk_hub_b_{idx:02d}@globex.test",
                    username=f"bulk_hub_b_{idx:02d}",
                    first_name="BulkB",
                    last_name=f"{role_name}{idx:02d}",
                    tenant=tenant_b,
                    role=roles_b[role_name],
                    is_tenant_admin=(role_name == "Admin"),
                    status="active",
                    is_active=True,
                    is_staff=False,
                    is_superuser=False,
                    password=fast_hash,
                )
            )

        assert len(bulk_users) == 100
        User.objects.bulk_create(bulk_users)

        users_a = list(
            User.objects.filter(username__startswith="bulk_hub_a_").select_related(
                "tenant", "role"
            )
        )
        users_b = list(
            User.objects.filter(username__startswith="bulk_hub_b_").select_related(
                "tenant", "role"
            )
        )
        assert len(users_a) == 60
        assert len(users_b) == 40

        # Form owner/steward/custodian queryset isolation across all 100 bulk users
        form_a = AssetIntegrationConnectorForm(tenant=tenant_a)
        form_b = AssetIntegrationConnectorForm(tenant=tenant_b)
        owner_ids_a = set(form_a.fields["owner"].queryset.values_list("pk", flat=True))
        owner_ids_b = set(form_b.fields["owner"].queryset.values_list("pk", flat=True))
        bulk_ids_a = {u.pk for u in users_a}
        bulk_ids_b = {u.pk for u in users_b}
        assert bulk_ids_a.issubset(owner_ids_a)
        assert bulk_ids_a.isdisjoint(owner_ids_b)
        assert bulk_ids_b.issubset(owner_ids_b)
        assert bulk_ids_b.isdisjoint(owner_ids_a)

        list_urls = [
            (reverse("assets:asset_integration_connector_list"), integration_connector_a.name, integration_connector_b.name),
            (reverse("assets:asset_telemetry_stream_list"), integration_stream_a.stream_name, integration_stream_b.stream_name),
            (reverse("assets:asset_gl_sync_batch_list"), integration_gl_batch_a.external_batch_ref, integration_gl_batch_b.external_batch_ref),
            (reverse("assets:asset_gis_mapping_list"), integration_gis_mapping_a.external_feature_id, integration_gis_mapping_b.external_feature_id),
        ]

        conn_detail_a = reverse(
            "assets:asset_integration_connector_detail", args=[integration_connector_a.pk]
        )
        conn_detail_b = reverse(
            "assets:asset_integration_connector_detail", args=[integration_connector_b.pk]
        )
        rot_a = reverse(
            "assets:asset_integration_connector_rotate_secret",
            args=[integration_connector_a.pk],
        )
        rot_b = reverse(
            "assets:asset_integration_connector_rotate_secret",
            args=[integration_connector_b.pk],
        )
        exec_a = reverse(
            "assets:asset_gl_sync_batch_execute", args=[integration_gl_batch_a.pk]
        )
        exec_b = reverse(
            "assets:asset_gl_sync_batch_execute", args=[integration_gl_batch_b.pk]
        )
        conn_create_url = reverse("assets:asset_integration_connector_create")

        client = Client()
        admin_count_checked = 0
        non_admin_count_checked = 0

        # Verify all 100 users across list isolation, foreign detail 404, and RBAC gates
        for idx, user in enumerate(users_a + users_b):
            client.force_login(user)
            is_a = user.tenant_id == tenant_a.pk
            l_url, num_a, num_b = list_urls[idx % len(list_urls)]

            # 1) List isolation across all 4 entities
            r_list = client.get(l_url)
            assert r_list.status_code == 200
            list_html = r_list.content.decode("utf-8")
            if is_a:
                assert num_a in list_html
                assert num_b not in list_html
                # 2) Foreign detail IDOR -> 404
                assert client.get(conn_detail_b).status_code == 404
            else:
                assert num_b in list_html
                assert num_a not in list_html
                assert client.get(conn_detail_a).status_code == 404

            # 3) Role authorization matrix (Admin vs Manager/Staff/Auditor)
            own_rot = rot_a if is_a else rot_b
            foreign_rot = rot_b if is_a else rot_a
            foreign_exec = exec_b if is_a else exec_a

            if user.is_tenant_admin:
                admin_count_checked += 1
                assert client.get(conn_create_url).status_code == 200
                assert client.post(own_rot).status_code == 302
                assert client.post(foreign_rot).status_code == 404
                assert client.post(foreign_exec).status_code == 404
            else:
                non_admin_count_checked += 1
                assert client.get(conn_create_url).status_code == 403
                assert client.post(own_rot).status_code == 403
                assert client.post(foreign_rot).status_code == 403
                assert client.post(foreign_exec).status_code == 403

        assert admin_count_checked == 25  # 15 in tenant_a + 10 in tenant_b
        assert non_admin_count_checked == 75  # 45 in tenant_a + 30 in tenant_b
