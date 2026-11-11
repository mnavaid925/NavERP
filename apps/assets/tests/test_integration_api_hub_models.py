"""
Unit tests for Sub-module 11.15: Integration & API Hub Models.

Covers AssetIntegrationConnector, AssetTelemetryStream, AssetGlSyncBatch,
and AssetGisMapping — auto-numbering, __str__, unique constraints, ProtectedError,
semantic color badges, credential issuance, SSRF URL validation, telemetry mapping
and boundary evaluation, GL variance calculation and strict JSON checks, GIS/LRS
validation and spatial drift evaluation, and programmatic cross-tenant FK guards.
"""

import hashlib
from datetime import timedelta
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.utils import timezone

from apps.accounting.models import JournalEntry
from apps.assets.models import (
    AssetDepreciationSchedule,
    AssetGisMapping,
    AssetGlSyncBatch,
    AssetIntegrationConnector,
    AssetTelemetryReading,
    AssetTelemetryStream,
)
from apps.assets.models.IntegrationApiHub.AssetIntegrationConnectors import (
    validate_connector_endpoint_url,
)

pytestmark = pytest.mark.django_db

_INTEGRATION_API_HUB_VALID_BADGES = frozenset(
    {
        "badge-green",
        "badge-amber",
        "badge-red",
        "badge-slate",
        "badge-muted",
        "badge-info",
    }
)


# =====================================================================
# Module-level Helpers (Must start with _integration_api_hub_*)
# =====================================================================


def _integration_api_hub_make_connector(
    tenant, name="ERP Connector", endpoint_url="https://api.example.com/v1", **kwargs
):
    data = {
        "tenant": tenant,
        "name": name,
        "connector_category": "erp_procurement",
        "provider": "sap_s4hana",
        "protocol": "rest_json",
        "sync_direction": "bidirectional",
        "environment": "sandbox",
        "endpoint_url": endpoint_url,
        "auth_method": "api_key",
        "rate_limit_rpm": 120,
        "timeout_seconds": 30,
        "retry_policy_max": 3,
        "polling_interval_minutes": 15,
        "status": "active",
    }
    data.update(kwargs)
    return AssetIntegrationConnector.objects.create(**data)


def _integration_api_hub_make_stream(
    tenant,
    connector,
    operational_asset=None,
    fixed_asset=None,
    stream_name="Bearing Temp Feed",
    tag_address="ns=2;s=Plant1.Pump01.Temp",
    **kwargs,
):
    data = {
        "tenant": tenant,
        "connector": connector,
        "operational_asset": operational_asset,
        "fixed_asset": fixed_asset,
        "tag_address": tag_address,
        "stream_name": stream_name,
        "stream_protocol": "opc_ua_node",
        "metric_type": "bearing_temperature",
        "metric_unit": "celsius",
        "ingestion_mode": "polling",
        "polling_interval_seconds": 60,
        "deadband_delta": Decimal("0.5000"),
        "scale_factor": Decimal("1.000000"),
        "offset_value": Decimal("0.0000"),
        "stream_status": "active",
    }
    data.update(kwargs)
    return AssetTelemetryStream.objects.create(**data)


def _integration_api_hub_make_batch(tenant, connector, **kwargs):
    data = {
        "tenant": tenant,
        "connector": connector,
        "sync_domain": "depreciation_posting",
        "sync_direction": "outbound",
        "batch_date": timezone.localdate(),
        "source_amount": Decimal("1000.00"),
        "target_gl_amount": Decimal("1000.00"),
        "field_mapping_json": '{"book": "CORP"}',
    }
    data.update(kwargs)
    return AssetGlSyncBatch.objects.create(**data)


def _integration_api_hub_make_mapping(
    tenant,
    connector,
    external_feature_id="FEAT-100",
    layer_name="plant_assets_pt",
    **kwargs,
):
    data = {
        "tenant": tenant,
        "connector": connector,
        "external_feature_id": external_feature_id,
        "layer_name": layer_name,
        "geometry_type": "point",
        "coordinate_system_srid": 4326,
        "system_of_record": "erp_authoritative",
        "sync_direction": "bidirectional",
        "status": "active",
    }
    data.update(kwargs)
    return AssetGisMapping.objects.create(**data)


# =====================================================================
# 1. Auto-numbering, __str__, Unique Constraints & ProtectedError
# =====================================================================


class TestIntegrationApiHubCoreMechanics:
    """Tests auto-numbering, string representation, unique constraints, and PROTECT cascades."""

    def test_integration_api_hub_autonumber_prefixes_and_tenant_isolation(
        self, tenant_a, tenant_b, operational_asset_a, operational_asset_b
    ):
        c_a1 = _integration_api_hub_make_connector(tenant_a, name="A1")
        c_a2 = _integration_api_hub_make_connector(tenant_a, name="A2")
        c_b1 = _integration_api_hub_make_connector(tenant_b, name="B1")

        assert c_a1.number == "AICN-00001"
        assert c_a2.number == "AICN-00002"
        assert c_b1.number == "AICN-00001"

        s_a1 = _integration_api_hub_make_stream(
            tenant_a, c_a1, operational_asset=operational_asset_a, stream_name="S-A1"
        )
        s_a2 = _integration_api_hub_make_stream(
            tenant_a, c_a1, operational_asset=operational_asset_a, stream_name="S-A2"
        )
        s_b1 = _integration_api_hub_make_stream(
            tenant_b, c_b1, operational_asset=operational_asset_b, stream_name="S-B1"
        )

        assert s_a1.number == "ATMS-00001"
        assert s_a2.number == "ATMS-00002"
        assert s_b1.number == "ATMS-00001"

        b_a1 = _integration_api_hub_make_batch(tenant_a, c_a1)
        b_a2 = _integration_api_hub_make_batch(tenant_a, c_a1)
        b_b1 = _integration_api_hub_make_batch(tenant_b, c_b1)

        assert b_a1.number == "AGLS-00001"
        assert b_a2.number == "AGLS-00002"
        assert b_b1.number == "AGLS-00001"

        m_a1 = _integration_api_hub_make_mapping(tenant_a, c_a1, external_feature_id="F1")
        m_a2 = _integration_api_hub_make_mapping(tenant_a, c_a1, external_feature_id="F2")
        m_b1 = _integration_api_hub_make_mapping(tenant_b, c_b1, external_feature_id="F1")

        assert m_a1.number == "AGIS-00001"
        assert m_a2.number == "AGIS-00002"
        assert m_b1.number == "AGIS-00001"

    def test_integration_api_hub_str_representations(
        self,
        integration_connector_a,
        integration_stream_a,
        integration_gl_batch_a,
        integration_gis_mapping_a,
    ):
        assert str(integration_connector_a) == (
            f"{integration_connector_a.number} · {integration_connector_a.name}"
        )
        assert str(integration_stream_a) == (
            f"{integration_stream_a.number} · {integration_stream_a.stream_name}"
        )
        assert str(integration_gl_batch_a) == (
            f"{integration_gl_batch_a.number} · "
            f"{integration_gl_batch_a.get_sync_domain_display()} "
            f"({integration_gl_batch_a.batch_date})"
        )
        assert str(integration_gis_mapping_a) == (
            f"{integration_gis_mapping_a.number} · "
            f"{integration_gis_mapping_a.layer_name} / "
            f"{integration_gis_mapping_a.external_feature_id}"
        )

    def test_integration_api_hub_tenant_number_unique_constraints(
        self,
        tenant_a,
        tenant_b,
        operational_asset_a,
        operational_asset_b,
    ):
        c_a = _integration_api_hub_make_connector(tenant_a, name="Conn A")
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                AssetIntegrationConnector.objects.create(
                    tenant=tenant_a,
                    number=c_a.number,
                    name="Dup Conn A",
                    endpoint_url="https://api2.example.com/v1",
                )
        c_b = AssetIntegrationConnector.objects.create(
            tenant=tenant_b,
            number=c_a.number,
            name="Conn B",
            endpoint_url="https://api-b.example.com/v1",
        )
        assert c_b.number == c_a.number

        s_a = _integration_api_hub_make_stream(
            tenant_a, c_a, operational_asset=operational_asset_a
        )
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                AssetTelemetryStream.objects.create(
                    tenant=tenant_a,
                    number=s_a.number,
                    connector=c_a,
                    operational_asset=operational_asset_a,
                    tag_address="tag/dup",
                    stream_name="Dup Stream",
                )
        s_b = AssetTelemetryStream.objects.create(
            tenant=tenant_b,
            number=s_a.number,
            connector=c_b,
            operational_asset=operational_asset_b,
            tag_address="tag/b",
            stream_name="Stream B",
        )
        assert s_b.number == s_a.number

        b_a = _integration_api_hub_make_batch(tenant_a, c_a)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                AssetGlSyncBatch.objects.create(
                    tenant=tenant_a,
                    number=b_a.number,
                    connector=c_a,
                )
        b_b = AssetGlSyncBatch.objects.create(
            tenant=tenant_b,
            number=b_a.number,
            connector=c_b,
        )
        assert b_b.number == b_a.number

        m_a = _integration_api_hub_make_mapping(tenant_a, c_a)
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                AssetGisMapping.objects.create(
                    tenant=tenant_a,
                    number=m_a.number,
                    connector=c_a,
                    external_feature_id="DUP-FEAT",
                    layer_name="layer_a",
                )
        m_b = AssetGisMapping.objects.create(
            tenant=tenant_b,
            number=m_a.number,
            connector=c_b,
            external_feature_id="FEAT-B",
            layer_name="layer_b",
        )
        assert m_b.number == m_a.number

    def test_integration_api_hub_connector_delete_protected_by_children(
        self,
        tenant_a,
        operational_asset_a,
    ):
        conn_stream = _integration_api_hub_make_connector(tenant_a, name="With Stream")
        stream = _integration_api_hub_make_stream(
            tenant_a, conn_stream, operational_asset=operational_asset_a
        )
        with pytest.raises(ProtectedError):
            conn_stream.delete()
        stream.delete()
        conn_stream.delete()

        conn_batch = _integration_api_hub_make_connector(tenant_a, name="With Batch")
        batch = _integration_api_hub_make_batch(tenant_a, conn_batch)
        with pytest.raises(ProtectedError):
            conn_batch.delete()
        batch.delete()
        conn_batch.delete()

        conn_gis = _integration_api_hub_make_connector(tenant_a, name="With GIS")
        mapping = _integration_api_hub_make_mapping(tenant_a, conn_gis)
        with pytest.raises(ProtectedError):
            conn_gis.delete()
        mapping.delete()
        conn_gis.delete()

    def test_integration_api_hub_gl_batch_protect_and_optional_set_null_deletes(
        self,
        tenant_a,
        integration_connector_a,
        integration_open_fiscal_period_a,
        expense_account_a,
        asset_account_a,
        operational_asset_a,
        location_a,
    ):
        batch = _integration_api_hub_make_batch(
            tenant_a,
            integration_connector_a,
            fiscal_period=integration_open_fiscal_period_a,
            gl_account=expense_account_a,
            offset_gl_account=asset_account_a,
        )
        with pytest.raises(ProtectedError):
            integration_open_fiscal_period_a.delete()
        with pytest.raises(ProtectedError):
            expense_account_a.delete()
        with pytest.raises(ProtectedError):
            asset_account_a.delete()
        batch.delete()

        mapping = _integration_api_hub_make_mapping(
            tenant_a,
            integration_connector_a,
            operational_asset=operational_asset_a,
            location=location_a,
        )
        operational_asset_a.delete()
        location_a.delete()
        mapping.refresh_from_db()
        assert mapping.operational_asset is None
        assert mapping.location is None

    def test_integration_api_hub_default_ordering(self, tenant_a):
        c1 = _integration_api_hub_make_connector(tenant_a, name="First")
        c2 = _integration_api_hub_make_connector(tenant_a, name="Second")
        assert list(AssetIntegrationConnector.objects.filter(tenant=tenant_a)) == [
            c1,
            c2,
        ]

        today = timezone.localdate()
        older_batch = _integration_api_hub_make_batch(
            tenant_a, c1, batch_date=today - timedelta(days=5)
        )
        newer_batch_1 = _integration_api_hub_make_batch(tenant_a, c1, batch_date=today)
        newer_batch_2 = _integration_api_hub_make_batch(tenant_a, c1, batch_date=today)
        # Ordering is ["-batch_date", "-number"]
        assert list(AssetGlSyncBatch.objects.filter(tenant=tenant_a)) == [
            newer_batch_2,
            newer_batch_1,
            older_batch,
        ]


# =====================================================================
# 2. Semantic Color Badge CSS Properties
# =====================================================================


class TestIntegrationApiHubBadgeProperties:
    """Verifies all badge CSS properties across all 4 models return valid theme.css classes."""

    def test_integration_api_hub_connector_badge_classes(self, integration_connector_a):
        for status_val, _ in AssetIntegrationConnector.STATUS_CHOICES:
            integration_connector_a.status = status_val
            css = integration_connector_a.status_badge_class
            assert css == AssetIntegrationConnector.STATUS_BADGE_MAP[status_val]
            assert css in _INTEGRATION_API_HUB_VALID_BADGES

        integration_connector_a.status = "nonexistent"
        assert integration_connector_a.status_badge_class == "badge-slate"

        for health_val, _ in AssetIntegrationConnector.HEALTH_STATUS_CHOICES:
            integration_connector_a.health_status = health_val
            css = integration_connector_a.health_badge_class
            assert css == AssetIntegrationConnector.HEALTH_BADGE_MAP[health_val]
            assert css in _INTEGRATION_API_HUB_VALID_BADGES

        integration_connector_a.health_status = "nonexistent"
        assert integration_connector_a.health_badge_class == "badge-slate"

    def test_integration_api_hub_stream_badge_classes(self, integration_stream_a):
        for status_val, _ in AssetTelemetryStream.STREAM_STATUS_CHOICES:
            integration_stream_a.stream_status = status_val
            css = integration_stream_a.status_badge_class
            assert css == AssetTelemetryStream.STREAM_STATUS_BADGE_MAP[status_val]
            assert css in _INTEGRATION_API_HUB_VALID_BADGES

        integration_stream_a.stream_status = "nonexistent"
        assert integration_stream_a.status_badge_class == "badge-slate"

    def test_integration_api_hub_gl_batch_badge_classes(self, integration_gl_batch_a):
        for status_val, _ in AssetGlSyncBatch.STATUS_CHOICES:
            integration_gl_batch_a.status = status_val
            css = integration_gl_batch_a.status_badge_class
            assert css == AssetGlSyncBatch.STATUS_BADGE_MAP[status_val]
            assert css in _INTEGRATION_API_HUB_VALID_BADGES

        integration_gl_batch_a.status = "nonexistent"
        assert integration_gl_batch_a.status_badge_class == "badge-slate"

        for recon_val, _ in AssetGlSyncBatch.RECONCILIATION_STATUS_CHOICES:
            integration_gl_batch_a.reconciliation_status = recon_val
            css = integration_gl_batch_a.reconciliation_badge_class
            assert css == AssetGlSyncBatch.RECON_BADGE_MAP[recon_val]
            assert css in _INTEGRATION_API_HUB_VALID_BADGES

        integration_gl_batch_a.reconciliation_status = "nonexistent"
        assert integration_gl_batch_a.reconciliation_badge_class == "badge-slate"

    def test_integration_api_hub_gis_mapping_badge_classes(
        self, integration_gis_mapping_a
    ):
        for status_val, _ in AssetGisMapping.STATUS_CHOICES:
            integration_gis_mapping_a.status = status_val
            css = integration_gis_mapping_a.status_badge_class
            assert css == AssetGisMapping.STATUS_BADGE_MAP[status_val]
            assert css in _INTEGRATION_API_HUB_VALID_BADGES

        integration_gis_mapping_a.status = "nonexistent"
        assert integration_gis_mapping_a.status_badge_class == "badge-slate"

        for drift_val, _ in AssetGisMapping.DRIFT_STATUS_CHOICES:
            integration_gis_mapping_a.drift_status = drift_val
            css = integration_gis_mapping_a.drift_badge_class
            assert css == AssetGisMapping.DRIFT_BADGE_MAP[drift_val]
            assert css in _INTEGRATION_API_HUB_VALID_BADGES

        integration_gis_mapping_a.drift_status = "nonexistent"
        assert integration_gis_mapping_a.drift_badge_class == "badge-slate"


# =====================================================================
# 3. AssetIntegrationConnector Secrets, Numerics & SSRF Hardening
# =====================================================================


class TestIntegrationApiHubConnectorModel:
    """Tests AssetIntegrationConnector credential minting, numeric rules, and SSRF validation."""

    def test_integration_api_hub_issue_new_secret_prefix_and_sha256_only(
        self, tenant_a
    ):
        connector = _integration_api_hub_make_connector(tenant_a, name="Secret Hub")
        assert connector.api_key_prefix == ""
        assert connector.api_key_hash == ""

        plaintext_1 = connector.issue_new_secret()
        assert plaintext_1.startswith("aicn_")
        assert len(plaintext_1) >= 25
        expected_hash_1 = hashlib.sha256(plaintext_1.encode("utf-8")).hexdigest()
        assert connector.api_key_prefix == plaintext_1[:8]
        assert len(connector.api_key_prefix) == 8
        assert connector.api_key_hash == expected_hash_1
        assert connector.api_key_hash != plaintext_1

        connector.save()
        connector.refresh_from_db()
        assert connector.api_key_prefix == plaintext_1[:8]
        assert connector.api_key_hash == expected_hash_1
        # Verify plaintext is not persisted anywhere on DB fields
        for field in AssetIntegrationConnector._meta.fields:
            val = getattr(connector, field.name)
            if isinstance(val, str):
                assert plaintext_1 not in val

        plaintext_2 = connector.issue_new_secret()
        assert plaintext_2 != plaintext_1
        assert connector.api_key_hash == hashlib.sha256(
            plaintext_2.encode("utf-8")
        ).hexdigest()

    def test_integration_api_hub_connector_positive_numeric_validations(
        self, tenant_a
    ):
        base_kwargs = {
            "tenant": tenant_a,
            "name": "Numeric Test",
            "endpoint_url": "https://api.example.com/v1",
        }
        valid = AssetIntegrationConnector(
            rate_limit_rpm=1,
            timeout_seconds=1,
            polling_interval_minutes=1,
            **base_kwargs,
        )
        valid.full_clean()

        for field_name in (
            "rate_limit_rpm",
            "timeout_seconds",
            "polling_interval_minutes",
        ):
            bad_kwargs = dict(base_kwargs)
            bad_kwargs[field_name] = 0
            bad = AssetIntegrationConnector(**bad_kwargs)
            with pytest.raises(ValidationError) as exc_info:
                bad.full_clean()
            assert field_name in exc_info.value.message_dict

    @pytest.mark.parametrize(
        "allowed_url",
        [
            "https://api.example.com/sap/opu/odata4",
            "http://erp-gateway.example.com/rest",
            "opc.tcp://scada.example.com:4840/UA/Server",
            "mqtts://broker.example.com:8883/plant/line1",
            "mqtt://telemetry.example.com:1883/sensors",
            "tcps://plc-gw.example.com:8443",
            "sftp://files.example.com:22/assets/exports",
            "wss://events.example.com/stream",
            "HTTPS://UPPER.example.com/v1",
            "https://93.184.216.34/api/v1",
            "  https://trimmed.example.com/api  ",
        ],
    )
    def test_integration_api_hub_connector_accepts_allowed_endpoint_urls(
        self, tenant_a, allowed_url
    ):
        connector = AssetIntegrationConnector(
            tenant=tenant_a,
            name="Allowed URL",
            endpoint_url=allowed_url,
        )
        connector.full_clean()
        assert connector.endpoint_url == allowed_url.strip()

    @pytest.mark.parametrize(
        "blocked_url",
        [
            "",
            "   ",
            "https://api.example.com/with space",
            "https://api.example.com/\nheader",
            "https://api.example.com/\tpath",
            "https://allowed.com\\@127.0.0.1/",
            "https://api.example.com\\path",
            "ftp://files.example.com/assets.csv",
            "file:///etc/passwd",
            "gopher://93.184.216.34:70/",
            "javascript:alert(1)",
            "dict://93.184.216.34:2628/",
            "api.example.com/no-scheme",
            "https:///missing-host",
            "https://user:secret@api.example.com/v1",
            "https://user@api.example.com/v1",
            "https://api.example.com@127.0.0.1/",
            "https://api.example.com:99999/bad-port",
            "https://api.example.com:abc/bad-port",
            "http://[::1%25eth0]/",
            "http://[fe80::1%eth0]/",
            "https://api%2eexample.com/v1",
            "https://localhost/api",
            "https://LOCALHOST/api",
            "https://localhost.localdomain/api",
            "https://app.localhost/api",
            "https://metadata.google.internal/computeMetadata/v1/",
            "https://plc-gw.local/opc",
            "https://erp.internal/odata",
            "https://127.0.0.1/api",
            "https://127.0.1.1/api",
            "https://0.0.0.0/api",
            "https://10.0.0.1/api",
            "https://172.16.0.1/api",
            "https://192.168.1.50/api",
            "https://169.254.169.254/latest/meta-data/",
            "https://100.64.0.1/api",
            "https://100.127.255.254/api",
            "https://224.0.0.1/multicast",
            "https://240.0.0.1/reserved",
            "http://2130706433/",
            "http://167772161/",
            "http://2852039166/",
            "http://0x7f000001/",
            "http://0x7f.0.0.1/",
            "http://0177.0.0.1/",
            "http://0177.0000.0000.0001/",
            "http://127.1/",
            "http://10.1/",
            "http://[::1]/",
            "http://[::]/",
            "http://[fc00::1]/",
            "http://[fe80::1]/",
            "http://[::ffff:127.0.0.1]/",
            "http://[::ffff:169.254.169.254]/",
            "http://[::ffff:10.0.0.1]/",
            "http://[::ffff:7f00:1]/",
            "http://[2002:7f00:1::]/",
            "http://[2002:a9fe:a9fe::]/",
            "http://[2001:0:7f00:1::]/",
            "http://[2001:0:0808:0808::80ff:fffe]/",
            "https://" + ("a" * 64) + ".example.com/too-long-idna-label",
        ],
        ids=lambda val: val[:40] if len(val) > 40 else (val or "empty"),
    )
    def test_integration_api_hub_connector_rejects_ssrf_and_invalid_urls(
        self, tenant_a, blocked_url
    ):
        with pytest.raises(ValidationError):
            validate_connector_endpoint_url(blocked_url)

        if blocked_url:
            connector = AssetIntegrationConnector(
                tenant=tenant_a,
                name="Blocked SSRF",
                endpoint_url=blocked_url,
            )
            with pytest.raises(ValidationError) as exc_info:
                connector.full_clean()
            assert "endpoint_url" in exc_info.value.message_dict


# =====================================================================
# 4. AssetTelemetryStream Validations, Mapping & Threshold Evaluation
# =====================================================================


class TestIntegrationApiHubTelemetryStreamModel:
    """Tests AssetTelemetryStream numeric rules, asset link, metric mapping, and thresholds."""

    def test_integration_api_hub_stream_numeric_and_threshold_validations(
        self, tenant_a, integration_connector_a, operational_asset_a
    ):
        base = {
            "tenant": tenant_a,
            "connector": integration_connector_a,
            "operational_asset": operational_asset_a,
            "tag_address": "ns=2;s=Line1.Test",
            "stream_name": "Validation Stream",
        }

        # Valid boundary values: polling=1, deadband=0, warning==critical, negative non-zero scale
        valid = AssetTelemetryStream(
            polling_interval_seconds=1,
            deadband_delta=Decimal("0.0000"),
            scale_factor=Decimal("-2.500000"),
            warning_threshold=Decimal("50.0000"),
            critical_threshold=Decimal("50.0000"),
            **base,
        )
        valid.full_clean()

        bad_polling = AssetTelemetryStream(polling_interval_seconds=0, **base)
        with pytest.raises(ValidationError) as exc_poll:
            bad_polling.full_clean()
        assert "polling_interval_seconds" in exc_poll.value.message_dict

        bad_scale = AssetTelemetryStream(scale_factor=Decimal("0.000000"), **base)
        with pytest.raises(ValidationError) as exc_scale:
            bad_scale.full_clean()
        assert "scale_factor" in exc_scale.value.message_dict

        bad_deadband = AssetTelemetryStream(deadband_delta=Decimal("-0.0001"), **base)
        with pytest.raises(ValidationError) as exc_db:
            bad_deadband.full_clean()
        assert "deadband_delta" in exc_db.value.message_dict

        bad_thresh = AssetTelemetryStream(
            warning_threshold=Decimal("80.0000"),
            critical_threshold=Decimal("79.9999"),
            **base,
        )
        with pytest.raises(ValidationError) as exc_th:
            bad_thresh.full_clean()
        assert "critical_threshold" in exc_th.value.message_dict

    def test_integration_api_hub_stream_requires_operational_or_fixed_asset(
        self, tenant_a, integration_connector_a, operational_asset_a, fixed_asset_a
    ):
        no_asset = AssetTelemetryStream(
            tenant=tenant_a,
            connector=integration_connector_a,
            tag_address="ns=2;s=OrphanTag",
            stream_name="Orphan Stream",
        )
        with pytest.raises(ValidationError) as exc_info:
            no_asset.full_clean()
        assert "operational_asset" in exc_info.value.message_dict

        only_op = AssetTelemetryStream(
            tenant=tenant_a,
            connector=integration_connector_a,
            operational_asset=operational_asset_a,
            tag_address="ns=2;s=OpOnly",
            stream_name="Op Only",
        )
        only_op.full_clean()

        only_fixed = AssetTelemetryStream(
            tenant=tenant_a,
            connector=integration_connector_a,
            fixed_asset=fixed_asset_a,
            tag_address="ns=2;s=FixedOnly",
            stream_name="Fixed Only",
        )
        only_fixed.full_clean()

    @pytest.mark.parametrize(
        "stream_metric,stream_unit,expected_metric,expected_unit",
        [
            # Shared 11.7 metric types + compatible units
            (
                "vibration_velocity_rms",
                "mm_per_s",
                "vibration_velocity_rms",
                "mm_per_s",
            ),
            ("vibration_peak_accel", "g_force", "vibration_peak_accel", "g_force"),
            ("bearing_temperature", "celsius", "bearing_temperature", "celsius"),
            ("ambient_temperature", "fahrenheit", "ambient_temperature", "fahrenheit"),
            ("acoustic_ultrasound", "decibel_uv", "acoustic_ultrasound", "decibel_uv"),
            ("operating_pressure", "bar", "operating_pressure", "bar"),
            ("operating_pressure", "psi", "operating_pressure", "psi"),
            (
                "oil_dielectric_viscosity",
                "viscosity_cst",
                "oil_dielectric_viscosity",
                "viscosity_cst",
            ),
            ("motor_current_amperage", "amperes", "motor_current_amperage", "amperes"),
            # Telemetry-only metrics mapped to 11.7 equivalents
            ("runtime_hours", "hours", "motor_current_amperage", "amperes"),
            ("cycle_count", "cycles", "vibration_peak_accel", "g_force"),
            ("energy_kwh", "kwh", "motor_current_amperage", "amperes"),
            # Shared metrics paired with telemetry-only units -> unit fallbacks
            ("bearing_temperature", "hours", "bearing_temperature", "celsius"),
            ("vibration_peak_accel", "cycles", "vibration_peak_accel", "g_force"),
            ("motor_current_amperage", "kwh", "motor_current_amperage", "amperes"),
        ],
    )
    def test_integration_api_hub_resolve_telemetry_metric_and_unit(
        self,
        tenant_a,
        integration_connector_a,
        operational_asset_a,
        stream_metric,
        stream_unit,
        expected_metric,
        expected_unit,
    ):
        stream = _integration_api_hub_make_stream(
            tenant_a,
            integration_connector_a,
            operational_asset=operational_asset_a,
            metric_type=stream_metric,
            metric_unit=stream_unit,
        )
        valid_reading_types = {k for k, _ in AssetTelemetryReading.METRIC_TYPE_CHOICES}
        valid_reading_units = {k for k, _ in AssetTelemetryReading.METRIC_UNIT_CHOICES}

        mapped_type, mapped_unit, note = stream.resolve_telemetry_metric_and_unit()
        assert mapped_type == expected_metric
        assert mapped_unit == expected_unit
        assert mapped_type in valid_reading_types
        assert mapped_unit in valid_reading_units
        assert stream.number in note
        assert stream.tag_address in note

    def test_integration_api_hub_resolve_telemetry_metric_and_unit_unknown_fallback(
        self, integration_stream_a
    ):
        integration_stream_a.metric_type = "unmapped_custom_metric"
        integration_stream_a.metric_unit = "unmapped_custom_unit"
        mapped_type, mapped_unit, note = (
            integration_stream_a.resolve_telemetry_metric_and_unit()
        )
        assert mapped_type == "bearing_temperature"
        assert mapped_unit == "celsius"
        assert integration_stream_a.number in note

    def test_integration_api_hub_evaluate_reading_status_including_zero_thresholds(
        self, integration_stream_a
    ):
        # Standard thresholds from fixture: warning=75.0000, critical=90.0000
        assert integration_stream_a.evaluate_reading_status(Decimal("74.9999")) == "normal"
        assert integration_stream_a.evaluate_reading_status(Decimal("75.0000")) == "warning"
        assert integration_stream_a.evaluate_reading_status(Decimal("89.9999")) == "warning"
        assert integration_stream_a.evaluate_reading_status(Decimal("90.0000")) == "critical"
        assert integration_stream_a.evaluate_reading_status(Decimal("120.0000")) == "critical"

        # Zero warning threshold boundary
        integration_stream_a.warning_threshold = Decimal("0.0000")
        integration_stream_a.critical_threshold = Decimal("5.0000")
        assert integration_stream_a.evaluate_reading_status(Decimal("-0.0001")) == "normal"
        assert integration_stream_a.evaluate_reading_status(Decimal("0.0000")) == "warning"
        assert integration_stream_a.evaluate_reading_status(Decimal("4.9999")) == "warning"
        assert integration_stream_a.evaluate_reading_status(Decimal("5.0000")) == "critical"

        # Zero warning AND zero critical threshold boundary (critical precedence)
        integration_stream_a.warning_threshold = Decimal("0.0000")
        integration_stream_a.critical_threshold = Decimal("0.0000")
        assert integration_stream_a.evaluate_reading_status(Decimal("-1.0000")) == "normal"
        assert integration_stream_a.evaluate_reading_status(Decimal("0.0000")) == "critical"

        # Zero critical only (warning None)
        integration_stream_a.warning_threshold = None
        integration_stream_a.critical_threshold = Decimal("0.0000")
        assert integration_stream_a.evaluate_reading_status(Decimal("-0.0001")) == "normal"
        assert integration_stream_a.evaluate_reading_status(Decimal("0.0000")) == "critical"

        # Unconfigured thresholds
        integration_stream_a.warning_threshold = None
        integration_stream_a.critical_threshold = None
        assert integration_stream_a.evaluate_reading_status(Decimal("999.0000")) == "normal"


# =====================================================================
# 5. AssetGlSyncBatch Variance, GL Accounts & Strict JSON Validation
# =====================================================================


class TestIntegrationApiHubGlSyncBatchModel:
    """Tests AssetGlSyncBatch variance computation, GL account guards, and JSON limits."""

    def test_integration_api_hub_batch_variance_computed_in_clean_and_save(
        self, tenant_a, integration_connector_a
    ):
        # 1. Computed in clean() BEFORE save
        unsaved = AssetGlSyncBatch(
            tenant=tenant_a,
            connector=integration_connector_a,
            source_amount=Decimal("2500.50"),
            target_gl_amount=Decimal("2400.25"),
        )
        assert unsaved.variance_amount == Decimal("0.00")
        unsaved.clean()
        assert unsaved.variance_amount == Decimal("100.25")

        # Null handling in clean()
        unsaved.source_amount = None
        unsaved.target_gl_amount = Decimal("50.00")
        unsaved.clean()
        assert unsaved.variance_amount == Decimal("-50.00")

        # 2. Computed on save() directly without clean()
        created = AssetGlSyncBatch.objects.create(
            tenant=tenant_a,
            connector=integration_connector_a,
            source_amount=Decimal("1000.00"),
            target_gl_amount=Decimal("1250.00"),
        )
        created.refresh_from_db()
        assert created.variance_amount == Decimal("-250.00")

        # 3. Computed and persisted when using update_fields on source_amount or target_gl_amount
        created.source_amount = Decimal("1500.00")
        created.save(update_fields=["source_amount"])
        created.refresh_from_db()
        assert created.variance_amount == Decimal("250.00")

        created.target_gl_amount = Decimal("1500.00")
        created.save(update_fields=["target_gl_amount"])
        created.refresh_from_db()
        assert created.variance_amount == Decimal("0.00")

    def test_integration_api_hub_batch_amount_and_distinct_account_validations(
        self,
        tenant_a,
        integration_connector_a,
        expense_account_a,
        asset_account_a,
    ):
        neg_src = AssetGlSyncBatch(
            tenant=tenant_a,
            connector=integration_connector_a,
            source_amount=Decimal("-0.01"),
            target_gl_amount=Decimal("0.00"),
        )
        with pytest.raises(ValidationError) as exc_src:
            neg_src.full_clean()
        assert "source_amount" in exc_src.value.message_dict

        neg_tgt = AssetGlSyncBatch(
            tenant=tenant_a,
            connector=integration_connector_a,
            source_amount=Decimal("0.00"),
            target_gl_amount=Decimal("-0.01"),
        )
        with pytest.raises(ValidationError) as exc_tgt:
            neg_tgt.full_clean()
        assert "target_gl_amount" in exc_tgt.value.message_dict

        same_acct = AssetGlSyncBatch(
            tenant=tenant_a,
            connector=integration_connector_a,
            gl_account=expense_account_a,
            offset_gl_account=expense_account_a,
        )
        with pytest.raises(ValidationError) as exc_acct:
            same_acct.full_clean()
        assert "offset_gl_account" in exc_acct.value.message_dict

        valid = AssetGlSyncBatch(
            tenant=tenant_a,
            connector=integration_connector_a,
            gl_account=expense_account_a,
            offset_gl_account=asset_account_a,
            source_amount=Decimal("0.00"),
            target_gl_amount=Decimal("0.00"),
        )
        valid.full_clean()

    @pytest.mark.parametrize(
        "bad_json",
        [
            "{not valid json",
            '{"v": NaN}',
            '{"v": Infinity}',
            '{"v": -Infinity}',
            '["not", "a", "dict"]',
            "123",
            '"plain string"',
            "true",
            "null",
            '{"k": "' + ("x" * 65540) + '"}',
            ('{"a":' * 2000) + "1" + ("}" * 2000),
        ],
        ids=[
            "syntax_error",
            "nan",
            "infinity",
            "neg_infinity",
            "list_root",
            "number_root",
            "string_root",
            "bool_root",
            "null_root",
            "oversize_64kb",
            "deep_nesting",
        ],
    )
    def test_integration_api_hub_batch_rejects_invalid_field_mapping_json(
        self, tenant_a, integration_connector_a, bad_json
    ):
        batch = AssetGlSyncBatch(
            tenant=tenant_a,
            connector=integration_connector_a,
            field_mapping_json=bad_json,
        )
        with pytest.raises(ValidationError) as exc_info:
            batch.full_clean()
        assert "field_mapping_json" in exc_info.value.message_dict

    def test_integration_api_hub_batch_payload_summary_and_json_size_boundaries(
        self, tenant_a, integration_connector_a
    ):
        # Exact 65536-byte boundary accepted on both field_mapping_json and payload_summary
        prefix = '{"k":"'
        suffix = '"}'
        exact_json = prefix + ("a" * (65536 - len(prefix) - len(suffix))) + suffix
        assert len(exact_json.encode("utf-8")) == 65536

        exact_summary = "s" * 65536
        assert len(exact_summary.encode("utf-8")) == 65536

        ok_batch = AssetGlSyncBatch(
            tenant=tenant_a,
            connector=integration_connector_a,
            field_mapping_json=exact_json,
            payload_summary=exact_summary,
        )
        ok_batch.full_clean()

        # 65537 UTF-8 bytes rejected on payload_summary (including multi-byte UTF-8)
        too_big_ascii = AssetGlSyncBatch(
            tenant=tenant_a,
            connector=integration_connector_a,
            payload_summary="s" * 65537,
        )
        with pytest.raises(ValidationError) as exc_ascii:
            too_big_ascii.full_clean()
        assert "payload_summary" in exc_ascii.value.message_dict

        # 22000 3-byte characters = 66000 bytes > 65536 bytes even though char len < 65536
        too_big_utf8 = AssetGlSyncBatch(
            tenant=tenant_a,
            connector=integration_connector_a,
            payload_summary="\u20ac" * 22000,
        )
        with pytest.raises(ValidationError) as exc_utf8:
            too_big_utf8.full_clean()
        assert "payload_summary" in exc_utf8.value.message_dict


# =====================================================================
# 6. AssetGisMapping Coordinate, LRS, GeoJSON & Drift Status Evaluation
# =====================================================================


class TestIntegrationApiHubGisMappingModel:
    """Tests AssetGisMapping spatial constraints, GeoJSON rules, and drift computation."""

    def test_integration_api_hub_gis_coordinate_srid_and_lrs_validations(
        self, tenant_a, integration_connector_a
    ):
        base = {
            "tenant": tenant_a,
            "connector": integration_connector_a,
            "external_feature_id": "GIS-BOUND-1",
            "layer_name": "transmission_lines",
        }

        # Valid boundaries
        valid = AssetGisMapping(
            latitude=Decimal("-90.000000"),
            longitude=Decimal("180.000000"),
            coordinate_system_srid=1,
            is_linear_asset=True,
            lrs_route_id="RT-1",
            lrs_from_measure=Decimal("12.500"),
            lrs_to_measure=Decimal("12.500"),
            **base,
        )
        valid.full_clean()

        for bad_lat in (Decimal("-90.000001"), Decimal("90.000001")):
            m = AssetGisMapping(latitude=bad_lat, **base)
            with pytest.raises(ValidationError) as exc_lat:
                m.full_clean()
            assert "latitude" in exc_lat.value.message_dict

        for bad_lon in (Decimal("-180.000001"), Decimal("180.000001")):
            m = AssetGisMapping(longitude=bad_lon, **base)
            with pytest.raises(ValidationError) as exc_lon:
                m.full_clean()
            assert "longitude" in exc_lon.value.message_dict

        bad_srid = AssetGisMapping(coordinate_system_srid=0, **base)
        with pytest.raises(ValidationError) as exc_srid:
            bad_srid.full_clean()
        assert "coordinate_system_srid" in exc_srid.value.message_dict

        bad_lrs = AssetGisMapping(
            is_linear_asset=True,
            lrs_route_id="RT-1",
            lrs_from_measure=Decimal("10.000"),
            lrs_to_measure=Decimal("9.999"),
            **base,
        )
        with pytest.raises(ValidationError) as exc_lrs:
            bad_lrs.full_clean()
        assert "lrs_to_measure" in exc_lrs.value.message_dict

    @pytest.mark.parametrize(
        "bad_geojson",
        [
            "{bad-json",
            '["Point", 0, 0]',
            '"Point"',
            "42",
            '{"type": "Point", "coordinates": [NaN, 0]}',
            '{"type": "Point", "coordinates": [Infinity, 0]}',
            '{"blob": "' + ("g" * 65540) + '"}',
            ('{"a":' * 2000) + "1" + ("}" * 2000),
        ],
        ids=[
            "syntax_error",
            "list_root",
            "string_root",
            "number_root",
            "nan",
            "infinity",
            "oversize_64kb",
            "deep_nesting",
        ],
    )
    def test_integration_api_hub_gis_rejects_invalid_geojson_payload(
        self, tenant_a, integration_connector_a, bad_geojson
    ):
        mapping = AssetGisMapping(
            tenant=tenant_a,
            connector=integration_connector_a,
            external_feature_id="GIS-BAD-JSON",
            layer_name="bad_layer",
            geojson_payload=bad_geojson,
        )
        with pytest.raises(ValidationError) as exc_info:
            mapping.full_clean()
        assert "geojson_payload" in exc_info.value.message_dict

    def test_integration_api_hub_compute_spatial_drift_status_all_branches(
        self, tenant_a, integration_connector_a, operational_asset_a, location_a
    ):
        base = {
            "tenant": tenant_a,
            "connector": integration_connector_a,
            "external_feature_id": "DRIFT-01",
            "layer_name": "spatial_layer",
        }

        # 1. No geometry at all -> location_drift
        no_geom = AssetGisMapping(operational_asset=operational_asset_a, **base)
        assert no_geom.compute_spatial_drift_status() == "location_drift"
        # Verify compute_spatial_drift_status does not mutate drift_status
        assert no_geom.drift_status == "unverified"

        # Partial point coordinates alone -> location_drift
        lat_only = AssetGisMapping(
            latitude=Decimal("40.700000"),
            operational_asset=operational_asset_a,
            **base,
        )
        assert lat_only.compute_spatial_drift_status() == "location_drift"

        lon_only = AssetGisMapping(
            longitude=Decimal("-73.900000"),
            location=location_a,
            **base,
        )
        assert lon_only.compute_spatial_drift_status() == "location_drift"

        # Linear asset flag without route_id (or whitespace route_id) -> location_drift
        lrs_blank = AssetGisMapping(
            is_linear_asset=True,
            lrs_route_id="   ",
            operational_asset=operational_asset_a,
            **base,
        )
        assert lrs_blank.compute_spatial_drift_status() == "location_drift"

        # Non-linear asset with lrs_route_id only -> location_drift
        non_linear_route = AssetGisMapping(
            is_linear_asset=False,
            lrs_route_id="ROUTE-1",
            operational_asset=operational_asset_a,
            **base,
        )
        assert non_linear_route.compute_spatial_drift_status() == "location_drift"

        # Whitespace geojson only -> location_drift
        ws_geojson = AssetGisMapping(
            geojson_payload="   ",
            operational_asset=operational_asset_a,
            **base,
        )
        assert ws_geojson.compute_spatial_drift_status() == "location_drift"

        # 2. Spatial geometry present WITHOUT operational_asset or location -> attribute_drift
        point_no_erp = AssetGisMapping(
            latitude=Decimal("40.748400"),
            longitude=Decimal("-73.985700"),
            **base,
        )
        assert point_no_erp.compute_spatial_drift_status() == "attribute_drift"

        lrs_no_erp = AssetGisMapping(
            is_linear_asset=True,
            lrs_route_id="PIPE-LINE-04",
            **base,
        )
        assert lrs_no_erp.compute_spatial_drift_status() == "attribute_drift"

        geojson_no_erp = AssetGisMapping(
            geojson_payload='{"type": "Polygon", "coordinates": []}',
            **base,
        )
        assert geojson_no_erp.compute_spatial_drift_status() == "attribute_drift"

        # 3. Spatial geometry + at least one ERP link -> in_sync
        point_with_asset = AssetGisMapping(
            latitude=Decimal("40.748400"),
            longitude=Decimal("-73.985700"),
            operational_asset=operational_asset_a,
            **base,
        )
        assert point_with_asset.compute_spatial_drift_status() == "in_sync"

        lrs_with_location = AssetGisMapping(
            is_linear_asset=True,
            lrs_route_id="PIPE-LINE-04",
            location=location_a,
            **base,
        )
        assert lrs_with_location.compute_spatial_drift_status() == "in_sync"

        geojson_with_asset = AssetGisMapping(
            geojson_payload='{"type": "Point", "coordinates": [1.0, 2.0]}',
            operational_asset=operational_asset_a,
            **base,
        )
        assert geojson_with_asset.compute_spatial_drift_status() == "in_sync"


# =====================================================================
# 7. Cross-Tenant FK Rejection (validate_tenant_fks via .full_clean())
# =====================================================================


class TestIntegrationApiHubCrossTenantFks:
    """Verifies programmatic .full_clean() rejects cross-tenant FKs across all 4 models."""

    def test_integration_api_hub_connector_rejects_foreign_fks_allows_global_currency(
        self,
        tenant_a,
        vendor_party_b,
        org_unit_b,
        admin_b,
        currency_usd,
    ):
        for field_name, foreign_obj in (
            ("vendor_partner", vendor_party_b),
            ("default_org_unit", org_unit_b),
            ("owner", admin_b),
        ):
            conn = AssetIntegrationConnector(
                tenant=tenant_a,
                name="Cross-Tenant FK",
                endpoint_url="https://api.example.com/v1",
                **{field_name: foreign_obj},
            )
            with pytest.raises(ValidationError) as exc_info:
                conn.full_clean()
            assert field_name in exc_info.value.message_dict

        # Global Currency (no tenant attribute) must pass cleanly
        conn_global = AssetIntegrationConnector(
            tenant=tenant_a,
            name="Global Currency OK",
            endpoint_url="https://api.example.com/v1",
            default_currency=currency_usd,
        )
        conn_global.full_clean()

    def test_integration_api_hub_stream_rejects_foreign_fks(
        self,
        tenant_a,
        integration_connector_a,
        integration_connector_b,
        operational_asset_a,
        operational_asset_b,
        fixed_asset_b,
        admin_b,
        telemetry_reading_b,
        maintenance_request_b,
    ):
        # Note: ensure at least one asset link is present when testing non-asset FKs
        cases = [
            ("connector", integration_connector_b, {"operational_asset": operational_asset_a}),
            ("operational_asset", operational_asset_b, {"connector": integration_connector_a}),
            ("fixed_asset", fixed_asset_b, {"connector": integration_connector_a}),
            (
                "steward",
                admin_b,
                {"connector": integration_connector_a, "operational_asset": operational_asset_a},
            ),
            (
                "last_telemetry_reading",
                telemetry_reading_b,
                {"connector": integration_connector_a, "operational_asset": operational_asset_a},
            ),
            (
                "latest_maintenance_request",
                maintenance_request_b,
                {"connector": integration_connector_a, "operational_asset": operational_asset_a},
            ),
        ]
        for field_name, foreign_obj, base_overrides in cases:
            stream_kwargs = {
                "tenant": tenant_a,
                "tag_address": "ns=2;s=ForeignTest",
                "stream_name": "Foreign FK Stream",
                **base_overrides,
                field_name: foreign_obj,
            }
            stream = AssetTelemetryStream(**stream_kwargs)
            with pytest.raises(ValidationError) as exc_info:
                stream.full_clean()
            assert field_name in exc_info.value.message_dict

    def test_integration_api_hub_gl_batch_rejects_foreign_fks_allows_global_currency(
        self,
        tenant_a,
        tenant_b,
        integration_connector_a,
        integration_connector_b,
        integration_open_fiscal_period_b,
        expense_account_b,
        accum_account_b,
        fixed_asset_b,
        operational_asset_b,
        po_b,
        capitalization_b,
        maintenance_request_b,
        org_unit_b,
        admin_b,
        currency_usd,
    ):
        dep_sched_b = AssetDepreciationSchedule.objects.create(
            tenant=tenant_b,
            fixed_asset=fixed_asset_b,
            operational_asset=operational_asset_b,
            fiscal_year=2026,
            period_number=1,
            period_frequency="monthly",
            schedule_date=timezone.localdate(),
            depreciation_method="straight_line",
            starting_book_value=Decimal("45000.00"),
            depreciation_amount=Decimal("833.33"),
            accumulated_depreciation_after=Decimal("833.33"),
            ending_book_value=Decimal("44166.67"),
            expense_account=expense_account_b,
            accumulated_account=accum_account_b,
            status="draft",
        )
        je_b = JournalEntry.objects.create(
            tenant=tenant_b,
            entry_type="recurring",
            entry_date=timezone.localdate(),
            status="draft",
        )
        cases = [
            ("connector", integration_connector_b),
            ("fiscal_period", integration_open_fiscal_period_b),
            ("gl_account", expense_account_b),
            ("offset_gl_account", accum_account_b),
            ("fixed_asset", fixed_asset_b),
            ("purchase_order", po_b),
            ("capitalization", capitalization_b),
            ("depreciation_schedule", dep_sched_b),
            ("maintenance_request", maintenance_request_b),
            ("cost_center", org_unit_b),
            ("journal_entry", je_b),
            ("executed_by", admin_b),
        ]
        for field_name, foreign_obj in cases:
            kwargs = {
                "tenant": tenant_a,
                "connector": integration_connector_a,
                field_name: foreign_obj,
            }
            batch = AssetGlSyncBatch(**kwargs)
            with pytest.raises(ValidationError) as exc_info:
                batch.full_clean()
            assert field_name in exc_info.value.message_dict

        # Global Currency must be accepted on tenant_a batch
        batch_global = AssetGlSyncBatch(
            tenant=tenant_a,
            connector=integration_connector_a,
            currency=currency_usd,
        )
        batch_global.full_clean()

    def test_integration_api_hub_gis_mapping_rejects_foreign_fks(
        self,
        tenant_a,
        integration_connector_a,
        integration_connector_b,
        operational_asset_b,
        location_b,
        org_unit_b,
        admin_b,
    ):
        cases = [
            ("connector", integration_connector_b),
            ("operational_asset", operational_asset_b),
            ("location", location_b),
            ("org_unit", org_unit_b),
            ("gis_custodian", admin_b),
        ]
        for field_name, foreign_obj in cases:
            kwargs = {
                "tenant": tenant_a,
                "connector": integration_connector_a,
                "external_feature_id": "GIS-FOREIGN",
                "layer_name": "foreign_layer",
                field_name: foreign_obj,
            }
            mapping = AssetGisMapping(**kwargs)
            with pytest.raises(ValidationError) as exc_info:
                mapping.full_clean()
            assert field_name in exc_info.value.message_dict

    def test_integration_api_hub_missing_fk_caught_cleanly_in_clean(self, tenant_a):
        conn = AssetIntegrationConnector(
            tenant=tenant_a,
            name="Stale FK",
            endpoint_url="https://api.example.com/v1",
            vendor_partner_id=999999999,
        )
        with pytest.raises(ValidationError) as exc_info:
            conn.clean()
        assert "vendor_partner" in exc_info.value.message_dict
