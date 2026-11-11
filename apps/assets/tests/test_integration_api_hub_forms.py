"""
Unit, validation, tenant-isolation, widget, and query-bound tests for
Sub-module 11.15: Integration & API Hub Forms.

Covers AssetIntegrationConnectorForm, AssetTelemetryStreamForm,
AssetGlSyncBatchForm, and AssetGisMappingForm:
1. Exact Meta.fields whitelists & system/managed field exclusions (+ mass-assignment checks).
2. Fail-closed tenant=None queryset scoping & tenant_a / tenant_b isolation
   (including inactive GLAccount filtering on create vs linked-edit preservation).
3. Cross-tenant FK rejection via form POST and direct reject_foreign() helper coverage.
4. Widget class & input type assertions (form-check vs form-checkbox, TextInput endpoint_url).
5. Comprehensive domain validation & edge cases (SSRF/URI checks, telemetry thresholds
   & non-finite decimals, GL distinct accounts & strict JSON/size bounds, GIS bounds/LRS/GeoJSON).
6. O(1) bounded-query dropdown evaluation on AssetGlSyncBatchForm via django_assert_max_num_queries.
"""

from decimal import Decimal

import pytest
from django import forms
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.accounting.models import Currency, FixedAsset, GLAccount
from apps.assets.forms import (
    AssetGisMappingForm,
    AssetGlSyncBatchForm,
    AssetIntegrationConnectorForm,
    AssetTelemetryStreamForm,
    reject_foreign,
)
from apps.assets.models import (
    AssetDepreciationSchedule,
    AssetGisMapping,
    AssetGlSyncBatch,
    AssetIntegrationConnector,
    AssetTelemetryStream,
)
from apps.core.models import OrgUnit, Party
from apps.scm.models import PurchaseOrder

User = get_user_model()
pytestmark = pytest.mark.django_db


# =====================================================================
# Module-level Helpers (_integration_api_hub_*)
# =====================================================================


def _integration_api_hub_connector_minimal_payload(**overrides):
    """Build a minimal valid payload for AssetIntegrationConnectorForm."""
    data = {
        "name": "SAP S/4HANA Production Connector",
        "connector_category": "erp_procurement",
        "provider": "sap_s4hana",
        "protocol": "odata_v4",
        "sync_direction": "bidirectional",
        "environment": "production",
        "endpoint_url": "https://api-erp.example.com/odata/v4",
        "auth_method": "api_key",
        "rate_limit_rpm": "120",
        "timeout_seconds": "30",
        "retry_policy_max": "3",
        "polling_interval_minutes": "15",
        "status": "draft",
        "webhook_verify_tls": True,
    }
    data.update(overrides)
    return data


def _integration_api_hub_stream_minimal_payload(
    connector, operational_asset=None, fixed_asset=None, **overrides
):
    """Build a minimal valid payload for AssetTelemetryStreamForm."""
    data = {
        "connector": str(connector.pk),
        "operational_asset": str(operational_asset.pk) if operational_asset else "",
        "fixed_asset": str(fixed_asset.pk) if fixed_asset else "",
        "tag_address": "ns=2;s=Plant1.Line1.Pump01.BearingTemp",
        "stream_name": "Line 1 Pump Bearing Temperature",
        "stream_protocol": "opc_ua_node",
        "metric_type": "bearing_temperature",
        "metric_unit": "celsius",
        "ingestion_mode": "polling",
        "polling_interval_seconds": "60",
        "deadband_delta": "0.5000",
        "scale_factor": "1.000000",
        "offset_value": "0.0000",
        "auto_trigger_maintenance": True,
        "stream_status": "active",
    }
    data.update(overrides)
    return data


def _integration_api_hub_gl_batch_minimal_payload(connector, **overrides):
    """Build a minimal valid payload for AssetGlSyncBatchForm."""
    data = {
        "connector": str(connector.pk),
        "sync_domain": "depreciation_posting",
        "sync_direction": "outbound",
        "batch_date": timezone.localdate().isoformat(),
        "source_amount": "1500.00",
        "target_gl_amount": "1500.00",
        "field_mapping_json": '{"asset_class": "ANLKL"}',
    }
    data.update(overrides)
    return data


def _integration_api_hub_gis_mapping_minimal_payload(connector, **overrides):
    """Build a minimal valid payload for AssetGisMappingForm."""
    data = {
        "connector": str(connector.pk),
        "external_feature_id": "ARCGIS-SUB-10482",
        "layer_name": "transmission_substations_pt",
        "geometry_type": "point",
        "coordinate_system_srid": "4326",
        "lrs_measure_unit": "km",
        "system_of_record": "erp_authoritative",
        "sync_direction": "bidirectional",
        "status": "active",
    }
    data.update(overrides)
    return data


def _integration_api_hub_make_depreciation_schedule(
    tenant,
    fixed_asset,
    operational_asset=None,
    expense_account=None,
    accumulated_account=None,
    period_number=1,
):
    """Create a valid AssetDepreciationSchedule aligned with the 11.4 model schema."""
    return AssetDepreciationSchedule.objects.create(
        tenant=tenant,
        fixed_asset=fixed_asset,
        operational_asset=operational_asset,
        fiscal_year=2026,
        period_number=period_number,
        period_frequency="monthly",
        schedule_date=timezone.localdate(),
        depreciation_method="straight_line",
        starting_book_value=Decimal("120000.00"),
        depreciation_amount=Decimal("1800.00"),
        accumulated_depreciation_after=Decimal("1800.00"),
        ending_book_value=Decimal("118200.00"),
        expense_account=expense_account,
        accumulated_account=accumulated_account,
        status="draft",
    )


# =====================================================================
# 1. Exact Meta.fields & System/Managed Field Exclusions
# =====================================================================


class TestIntegrationApiHubFormMetadataAndExclusions:
    """Verify exact Meta.fields whitelists and mass-assignment exclusions."""

    def test_integration_api_hub_connector_form_exact_fields_and_exclusions(
        self, tenant_a
    ):
        form = AssetIntegrationConnectorForm(tenant=tenant_a)
        assert list(form.fields) == [
            "name",
            "connector_category",
            "provider",
            "protocol",
            "sync_direction",
            "environment",
            "endpoint_url",
            "auth_method",
            "rate_limit_rpm",
            "timeout_seconds",
            "retry_policy_max",
            "polling_interval_minutes",
            "status",
            "vendor_partner",
            "default_org_unit",
            "default_currency",
            "owner",
            "webhook_verify_tls",
            "notes",
        ]
        for excluded in (
            "tenant",
            "number",
            "created_at",
            "updated_at",
            "api_key_prefix",
            "api_key_hash",
            "health_status",
            "last_heartbeat_at",
            "last_sync_at",
            "consecutive_failures",
            "last_error_message",
        ):
            assert excluded not in form.fields

    def test_integration_api_hub_connector_form_ignores_mass_assigned_system_fields(
        self, tenant_a, tenant_b
    ):
        payload = _integration_api_hub_connector_minimal_payload(
            tenant=str(tenant_b.pk),
            number="AICN-99999",
            api_key_prefix="aicn_bad",
            api_key_hash="f" * 64,
            health_status="healthy",
            last_heartbeat_at=timezone.now().isoformat(),
            last_sync_at=timezone.now().isoformat(),
            consecutive_failures="99",
            last_error_message="Injected error",
        )
        form = AssetIntegrationConnectorForm(data=payload, tenant=tenant_a)
        assert form.is_valid(), form.errors
        obj = form.save()
        assert obj.tenant == tenant_a
        assert obj.number != "AICN-99999"
        assert obj.number.startswith("AICN-")
        assert obj.api_key_prefix == ""
        assert obj.api_key_hash == ""
        assert obj.health_status == "unverified"
        assert obj.last_heartbeat_at is None
        assert obj.last_sync_at is None
        assert obj.consecutive_failures == 0
        assert obj.last_error_message == ""

    def test_integration_api_hub_stream_form_exact_fields_and_exclusions(
        self, tenant_a
    ):
        form = AssetTelemetryStreamForm(tenant=tenant_a)
        assert list(form.fields) == [
            "connector",
            "operational_asset",
            "fixed_asset",
            "tag_address",
            "stream_name",
            "stream_protocol",
            "metric_type",
            "metric_unit",
            "ingestion_mode",
            "polling_interval_seconds",
            "deadband_delta",
            "scale_factor",
            "offset_value",
            "baseline_value",
            "warning_threshold",
            "critical_threshold",
            "auto_trigger_maintenance",
            "stream_status",
            "steward",
            "notes",
        ]
        for excluded in (
            "tenant",
            "number",
            "created_at",
            "updated_at",
            "last_ingested_value",
            "last_ingested_at",
            "readings_ingested_count",
            "last_telemetry_reading",
            "latest_maintenance_request",
        ):
            assert excluded not in form.fields

    def test_integration_api_hub_stream_form_ignores_mass_assigned_derived_fields(
        self, tenant_a, tenant_b, integration_connector_a, operational_asset_a
    ):
        payload = _integration_api_hub_stream_minimal_payload(
            integration_connector_a,
            operational_asset=operational_asset_a,
            tenant=str(tenant_b.pk),
            number="ATMS-99999",
            last_ingested_value="999.9900",
            last_ingested_at=timezone.now().isoformat(),
            readings_ingested_count="42",
            last_telemetry_reading="1",
            latest_maintenance_request="1",
        )
        form = AssetTelemetryStreamForm(data=payload, tenant=tenant_a)
        assert form.is_valid(), form.errors
        obj = form.save()
        assert obj.tenant == tenant_a
        assert obj.number != "ATMS-99999"
        assert obj.number.startswith("ATMS-")
        assert obj.last_ingested_value is None
        assert obj.last_ingested_at is None
        assert obj.readings_ingested_count == 0
        assert obj.last_telemetry_reading is None
        assert obj.latest_maintenance_request is None

    def test_integration_api_hub_gl_batch_form_exact_fields_and_exclusions(
        self, tenant_a
    ):
        form = AssetGlSyncBatchForm(tenant=tenant_a)
        assert list(form.fields) == [
            "connector",
            "sync_domain",
            "sync_direction",
            "external_batch_ref",
            "fiscal_period",
            "gl_account",
            "offset_gl_account",
            "fixed_asset",
            "purchase_order",
            "capitalization",
            "depreciation_schedule",
            "maintenance_request",
            "cost_center",
            "currency",
            "batch_date",
            "source_amount",
            "target_gl_amount",
            "field_mapping_json",
            "payload_summary",
            "notes",
        ]
        for excluded in (
            "tenant",
            "number",
            "created_at",
            "updated_at",
            "status",
            "reconciliation_status",
            "variance_amount",
            "journal_entry",
            "executed_by",
            "executed_at",
            "synced_at",
            "records_processed",
            "records_succeeded",
            "records_failed",
        ):
            assert excluded not in form.fields

    def test_integration_api_hub_gl_batch_form_ignores_mass_assigned_system_fields(
        self, tenant_a, tenant_b, integration_connector_a, admin_user
    ):
        payload = _integration_api_hub_gl_batch_minimal_payload(
            integration_connector_a,
            tenant=str(tenant_b.pk),
            number="AGLS-99999",
            status="posted",
            reconciliation_status="reconciled",
            variance_amount="9999.00",
            journal_entry="1",
            executed_by=str(admin_user.pk),
            executed_at=timezone.now().isoformat(),
            synced_at=timezone.now().isoformat(),
            records_processed="15",
            records_succeeded="15",
            records_failed="2",
            source_amount="1500.00",
            target_gl_amount="1400.00",
        )
        form = AssetGlSyncBatchForm(data=payload, tenant=tenant_a)
        assert form.is_valid(), form.errors
        obj = form.save()
        assert obj.tenant == tenant_a
        assert obj.number != "AGLS-99999"
        assert obj.number.startswith("AGLS-")
        assert obj.status == "draft"
        assert obj.reconciliation_status == "pending"
        assert obj.variance_amount == Decimal("100.00")
        assert obj.journal_entry is None
        assert obj.executed_by is None
        assert obj.synced_at is None
        assert obj.records_processed == 0
        assert obj.records_succeeded == 0
        assert obj.records_failed == 0

    def test_integration_api_hub_gis_mapping_form_exact_fields_and_exclusions(
        self, tenant_a
    ):
        form = AssetGisMappingForm(tenant=tenant_a)
        assert list(form.fields) == [
            "connector",
            "operational_asset",
            "location",
            "org_unit",
            "external_feature_id",
            "layer_name",
            "geometry_type",
            "coordinate_system_srid",
            "latitude",
            "longitude",
            "elevation_meters",
            "is_linear_asset",
            "lrs_route_id",
            "lrs_from_measure",
            "lrs_to_measure",
            "lrs_measure_unit",
            "geojson_payload",
            "system_of_record",
            "sync_direction",
            "status",
            "gis_custodian",
            "notes",
        ]
        for excluded in (
            "tenant",
            "number",
            "created_at",
            "updated_at",
            "drift_status",
            "last_spatial_sync_at",
        ):
            assert excluded not in form.fields

    def test_integration_api_hub_gis_mapping_form_ignores_mass_assigned_system_fields(
        self, tenant_a, tenant_b, integration_connector_a
    ):
        payload = _integration_api_hub_gis_mapping_minimal_payload(
            integration_connector_a,
            tenant=str(tenant_b.pk),
            number="AGIS-99999",
            drift_status="in_sync",
            last_spatial_sync_at=timezone.now().isoformat(),
        )
        form = AssetGisMappingForm(data=payload, tenant=tenant_a)
        assert form.is_valid(), form.errors
        obj = form.save()
        assert obj.tenant == tenant_a
        assert obj.number != "AGIS-99999"
        assert obj.number.startswith("AGIS-")
        assert obj.drift_status == "unverified"
        assert obj.last_spatial_sync_at is None


# =====================================================================
# 2. Widget Attributes
# =====================================================================


class TestIntegrationApiHubFormWidgets:
    """Verify checkbox CSS classes, endpoint_url TextInput, and key field widgets."""

    def test_integration_api_hub_checkbox_widgets_use_form_check_not_form_checkbox(
        self, tenant_a
    ):
        connector_widget = AssetIntegrationConnectorForm(tenant=tenant_a).fields[
            "webhook_verify_tls"
        ].widget
        stream_widget = AssetTelemetryStreamForm(tenant=tenant_a).fields[
            "auto_trigger_maintenance"
        ].widget
        gis_widget = AssetGisMappingForm(tenant=tenant_a).fields[
            "is_linear_asset"
        ].widget

        for widget in (connector_widget, stream_widget, gis_widget):
            assert isinstance(widget, forms.CheckboxInput)
            classes = widget.attrs.get("class", "").split()
            assert "form-check" in classes
            assert "form-checkbox" not in classes

    def test_integration_api_hub_connector_endpoint_url_uses_text_input_not_url_input(
        self, tenant_a
    ):
        widget = AssetIntegrationConnectorForm(tenant=tenant_a).fields[
            "endpoint_url"
        ].widget
        assert type(widget) is forms.TextInput
        assert not isinstance(widget, forms.URLInput)
        assert "form-input" in widget.attrs.get("class", "").split()

    def test_integration_api_hub_gl_batch_date_and_json_widgets(self, tenant_a):
        batch_form = AssetGlSyncBatchForm(tenant=tenant_a)
        date_widget = batch_form.fields["batch_date"].widget
        json_widget = batch_form.fields["field_mapping_json"].widget
        assert isinstance(date_widget, forms.DateInput)
        assert date_widget.input_type == "date"
        assert 'type="date"' in str(batch_form["batch_date"])
        assert "form-input" in date_widget.attrs.get("class", "").split()
        assert isinstance(json_widget, forms.Textarea)
        assert "form-textarea" in json_widget.attrs.get("class", "").split()


# =====================================================================
# 3. Fail-Closed tenant=None & Tenant-Scoped FK Querysets
# =====================================================================


class TestIntegrationApiHubFormTenantScoping:
    """Verify tenant=None fails closed to .none() and tenant=tenant_a isolates FKs."""

    def test_integration_api_hub_connector_form_fail_closed_tenant_none(
        self, tenant_a, vendor_party_a, org_unit_a, currency_usd, admin_user
    ):
        form = AssetIntegrationConnectorForm(tenant=None)
        for fk_field in ("vendor_partner", "default_org_unit", "owner"):
            qs = form.fields[fk_field].queryset
            assert qs.count() == 0
            assert list(qs) == []
        # Global Currency remains populated with active currencies
        assert currency_usd in form.fields["default_currency"].queryset

        # Submitting a tenant_a FK when tenant=None must fail cleanly
        payload = _integration_api_hub_connector_minimal_payload(
            vendor_partner=str(vendor_party_a.pk)
        )
        bound = AssetIntegrationConnectorForm(data=payload, tenant=None)
        assert not bound.is_valid()
        assert "vendor_partner" in bound.errors

    def test_integration_api_hub_stream_form_fail_closed_tenant_none(
        self, integration_connector_a, operational_asset_a, fixed_asset_a, admin_user
    ):
        form = AssetTelemetryStreamForm(tenant=None)
        for fk_field in ("connector", "operational_asset", "fixed_asset", "steward"):
            qs = form.fields[fk_field].queryset
            assert qs.count() == 0
            assert list(qs) == []

        payload = _integration_api_hub_stream_minimal_payload(
            integration_connector_a, operational_asset=operational_asset_a
        )
        bound = AssetTelemetryStreamForm(data=payload, tenant=None)
        assert not bound.is_valid()
        assert "connector" in bound.errors
        assert "operational_asset" in bound.errors

    def test_integration_api_hub_gl_batch_form_fail_closed_tenant_none(
        self,
        tenant_a,
        integration_connector_a,
        integration_open_fiscal_period_a,
        expense_account_a,
        asset_account_a,
        fixed_asset_a,
        operational_asset_a,
        po_a,
        capitalization_a,
        maintenance_request_a,
        org_unit_a,
        currency_usd,
    ):
        _integration_api_hub_make_depreciation_schedule(
            tenant_a,
            fixed_asset_a,
            operational_asset=operational_asset_a,
            expense_account=expense_account_a,
        )
        form = AssetGlSyncBatchForm(tenant=None)
        tenant_fk_fields = (
            "connector",
            "fiscal_period",
            "gl_account",
            "offset_gl_account",
            "fixed_asset",
            "purchase_order",
            "capitalization",
            "depreciation_schedule",
            "maintenance_request",
            "cost_center",
        )
        for fk_field in tenant_fk_fields:
            qs = form.fields[fk_field].queryset
            assert qs.count() == 0
            assert list(qs) == []
        # Global Currency remains populated with active currencies
        assert currency_usd in form.fields["currency"].queryset

        payload = _integration_api_hub_gl_batch_minimal_payload(integration_connector_a)
        bound = AssetGlSyncBatchForm(data=payload, tenant=None)
        assert not bound.is_valid()
        assert "connector" in bound.errors

    def test_integration_api_hub_gis_mapping_form_fail_closed_tenant_none(
        self,
        integration_connector_a,
        operational_asset_a,
        location_a,
        org_unit_a,
        admin_user,
    ):
        form = AssetGisMappingForm(tenant=None)
        for fk_field in (
            "connector",
            "operational_asset",
            "location",
            "org_unit",
            "gis_custodian",
        ):
            qs = form.fields[fk_field].queryset
            assert qs.count() == 0
            assert list(qs) == []

        payload = _integration_api_hub_gis_mapping_minimal_payload(
            integration_connector_a
        )
        bound = AssetGisMappingForm(data=payload, tenant=None)
        assert not bound.is_valid()
        assert "connector" in bound.errors

    def test_integration_api_hub_connector_form_scopes_querysets_to_tenant_a(
        self,
        tenant_a,
        vendor_party_a,
        vendor_party_b,
        org_unit_a,
        org_unit_b,
        admin_user,
        admin_b,
        currency_usd,
    ):
        form = AssetIntegrationConnectorForm(tenant=tenant_a)
        assert vendor_party_a in form.fields["vendor_partner"].queryset
        assert vendor_party_b not in form.fields["vendor_partner"].queryset
        assert org_unit_a in form.fields["default_org_unit"].queryset
        assert org_unit_b not in form.fields["default_org_unit"].queryset
        assert admin_user in form.fields["owner"].queryset
        assert admin_b not in form.fields["owner"].queryset
        assert currency_usd in form.fields["default_currency"].queryset

    def test_integration_api_hub_stream_form_scopes_querysets_to_tenant_a(
        self,
        tenant_a,
        integration_connector_a,
        integration_connector_b,
        operational_asset_a,
        operational_asset_b,
        fixed_asset_a,
        fixed_asset_b,
        admin_user,
        admin_b,
    ):
        form = AssetTelemetryStreamForm(tenant=tenant_a)
        assert integration_connector_a in form.fields["connector"].queryset
        assert integration_connector_b not in form.fields["connector"].queryset
        assert operational_asset_a in form.fields["operational_asset"].queryset
        assert operational_asset_b not in form.fields["operational_asset"].queryset
        assert fixed_asset_a in form.fields["fixed_asset"].queryset
        assert fixed_asset_b not in form.fields["fixed_asset"].queryset
        assert admin_user in form.fields["steward"].queryset
        assert admin_b not in form.fields["steward"].queryset

    def test_integration_api_hub_gl_batch_form_scopes_all_ten_tenant_fks_to_tenant_a(
        self,
        tenant_a,
        tenant_b,
        integration_connector_a,
        integration_connector_b,
        integration_open_fiscal_period_a,
        integration_open_fiscal_period_b,
        expense_account_a,
        expense_account_b,
        asset_account_a,
        accum_account_b,
        fixed_asset_a,
        fixed_asset_b,
        operational_asset_a,
        operational_asset_b,
        po_a,
        po_b,
        capitalization_a,
        capitalization_b,
        maintenance_request_a,
        maintenance_request_b,
        org_unit_a,
        org_unit_b,
        currency_usd,
    ):
        sched_a = _integration_api_hub_make_depreciation_schedule(
            tenant_a,
            fixed_asset_a,
            operational_asset=operational_asset_a,
            expense_account=expense_account_a,
        )
        sched_b = _integration_api_hub_make_depreciation_schedule(
            tenant_b,
            fixed_asset_b,
            operational_asset=operational_asset_b,
            expense_account=expense_account_b,
            accumulated_account=accum_account_b,
        )
        form = AssetGlSyncBatchForm(tenant=tenant_a)
        pairs = [
            ("connector", integration_connector_a, integration_connector_b),
            (
                "fiscal_period",
                integration_open_fiscal_period_a,
                integration_open_fiscal_period_b,
            ),
            ("gl_account", expense_account_a, expense_account_b),
            ("offset_gl_account", asset_account_a, accum_account_b),
            ("fixed_asset", fixed_asset_a, fixed_asset_b),
            ("purchase_order", po_a, po_b),
            ("capitalization", capitalization_a, capitalization_b),
            (
                "depreciation_schedule",
                sched_a,
                sched_b,
            ),
            ("maintenance_request", maintenance_request_a, maintenance_request_b),
            ("cost_center", org_unit_a, org_unit_b),
        ]
        for field_name, obj_a, obj_b in pairs:
            qs = form.fields[field_name].queryset
            assert obj_a in qs, f"{obj_a} missing from {field_name}"
            assert obj_b not in qs, f"Cross-tenant {obj_b} leaked into {field_name}"
        assert currency_usd in form.fields["currency"].queryset

    def test_integration_api_hub_gis_mapping_form_scopes_querysets_to_tenant_a(
        self,
        tenant_a,
        integration_connector_a,
        integration_connector_b,
        operational_asset_a,
        operational_asset_b,
        location_a,
        location_b,
        org_unit_a,
        org_unit_b,
        admin_user,
        admin_b,
    ):
        form = AssetGisMappingForm(tenant=tenant_a)
        pairs = [
            ("connector", integration_connector_a, integration_connector_b),
            ("operational_asset", operational_asset_a, operational_asset_b),
            ("location", location_a, location_b),
            ("org_unit", org_unit_a, org_unit_b),
            ("gis_custodian", admin_user, admin_b),
        ]
        for field_name, obj_a, obj_b in pairs:
            qs = form.fields[field_name].queryset
            assert obj_a in qs
            assert obj_b not in qs

    def test_integration_api_hub_gl_batch_form_filters_inactive_gl_accounts_create_vs_edit(
        self,
        tenant_a,
        tenant_b,
        integration_connector_a,
        expense_account_a,
        asset_account_a,
    ):
        inactive_gl_a = GLAccount.objects.create(
            tenant=tenant_a,
            code="6990-A-OLD",
            name="Legacy Inactive Expense",
            account_type="expense",
            is_active=False,
        )
        inactive_off_a = GLAccount.objects.create(
            tenant=tenant_a,
            code="1590-A-OLD",
            name="Legacy Inactive Offset",
            account_type="asset",
            is_active=False,
        )
        other_inactive_a = GLAccount.objects.create(
            tenant=tenant_a,
            code="9999-A-OLD",
            name="Unlinked Inactive Account",
            account_type="expense",
            is_active=False,
        )
        inactive_gl_b = GLAccount.objects.create(
            tenant=tenant_b,
            code="6990-B-OLD",
            name="Globex Inactive Account",
            account_type="expense",
            is_active=False,
        )

        # Create form: ALL inactive GLAccounts must be excluded
        create_form = AssetGlSyncBatchForm(tenant=tenant_a)
        for field_name in ("gl_account", "offset_gl_account"):
            qs = create_form.fields[field_name].queryset
            choice_pks = {pk for pk, _ in create_form.fields[field_name].choices if pk != ""}
            assert expense_account_a in qs
            assert asset_account_a in qs
            assert inactive_gl_a not in qs
            assert inactive_off_a not in qs
            assert other_inactive_a not in qs
            assert inactive_gl_b not in qs
            assert inactive_gl_a.pk not in choice_pks
            assert inactive_off_a.pk not in choice_pks
            assert other_inactive_a.pk not in choice_pks
            assert inactive_gl_b.pk not in choice_pks

        # Submitting an inactive GLAccount on create fails validation
        bad_create_payload = _integration_api_hub_gl_batch_minimal_payload(
            integration_connector_a,
            gl_account=str(inactive_gl_a.pk),
            offset_gl_account=str(asset_account_a.pk),
        )
        bad_create_form = AssetGlSyncBatchForm(data=bad_create_payload, tenant=tenant_a)
        assert not bad_create_form.is_valid()
        assert "gl_account" in bad_create_form.errors

        # Edit form: already-linked inactive accounts remain available ONLY on their own field
        batch = AssetGlSyncBatch.objects.create(
            tenant=tenant_a,
            connector=integration_connector_a,
            gl_account=inactive_gl_a,
            offset_gl_account=inactive_off_a,
            source_amount=Decimal("250.00"),
            target_gl_amount=Decimal("250.00"),
        )
        edit_form = AssetGlSyncBatchForm(instance=batch, tenant=tenant_a)

        gl_qs = edit_form.fields["gl_account"].queryset
        gl_choice_pks = {pk for pk, _ in edit_form.fields["gl_account"].choices if pk != ""}
        off_qs = edit_form.fields["offset_gl_account"].queryset
        off_choice_pks = {
            pk for pk, _ in edit_form.fields["offset_gl_account"].choices if pk != ""
        }

        assert inactive_gl_a in gl_qs
        assert inactive_gl_a.pk in gl_choice_pks
        assert inactive_off_a not in gl_qs
        assert inactive_off_a.pk not in gl_choice_pks
        assert other_inactive_a not in gl_qs
        assert inactive_gl_b not in gl_qs

        assert inactive_off_a in off_qs
        assert inactive_off_a.pk in off_choice_pks
        assert inactive_gl_a not in off_qs
        assert inactive_gl_a.pk not in off_choice_pks
        assert other_inactive_a not in off_qs
        assert inactive_gl_b not in off_qs

        # Saving edit form preserving the already-linked inactive accounts succeeds
        edit_payload = _integration_api_hub_gl_batch_minimal_payload(
            integration_connector_a,
            gl_account=str(inactive_gl_a.pk),
            offset_gl_account=str(inactive_off_a.pk),
        )
        bound_edit = AssetGlSyncBatchForm(
            data=edit_payload, instance=batch, tenant=tenant_a
        )
        assert bound_edit.is_valid(), bound_edit.errors

    def test_integration_api_hub_global_currency_filtering_active_vs_inactive_edit(
        self, tenant_a, integration_connector_a
    ):
        inactive_curr = Currency.objects.create(
            code="ZZZ", name="Legacy Inactive Currency", symbol="Z", is_active=False
        )

        # Create excludes inactive Currency
        conn_create = AssetIntegrationConnectorForm(tenant=tenant_a)
        batch_create = AssetGlSyncBatchForm(tenant=tenant_a)
        assert inactive_curr not in conn_create.fields["default_currency"].queryset
        assert inactive_curr not in batch_create.fields["currency"].queryset

        # Edit preserves an already-linked inactive Currency
        integration_connector_a.default_currency = inactive_curr
        integration_connector_a.save(update_fields=["default_currency", "updated_at"])
        conn_edit = AssetIntegrationConnectorForm(
            instance=integration_connector_a, tenant=tenant_a
        )
        assert inactive_curr in conn_edit.fields["default_currency"].queryset

        batch = AssetGlSyncBatch.objects.create(
            tenant=tenant_a,
            connector=integration_connector_a,
            currency=inactive_curr,
        )
        batch_edit = AssetGlSyncBatchForm(instance=batch, tenant=tenant_a)
        assert inactive_curr in batch_edit.fields["currency"].queryset


# =====================================================================
# 4. Cross-Tenant FK Rejection (POST + Direct reject_foreign)
# =====================================================================


class TestIntegrationApiHubFormCrossTenantRejection:
    """Verify tenant_b PKs are rejected across all tenant FKs and test reject_foreign directly."""

    @pytest.mark.parametrize(
        "field_name,fixture_name",
        [
            ("vendor_partner", "vendor_party_b"),
            ("default_org_unit", "org_unit_b"),
            ("owner", "admin_b"),
        ],
    )
    def test_integration_api_hub_connector_form_rejects_foreign_fks_via_post(
        self, request, tenant_a, field_name, fixture_name
    ):
        foreign_obj = request.getfixturevalue(fixture_name)
        payload = _integration_api_hub_connector_minimal_payload()
        payload[field_name] = str(foreign_obj.pk)
        form = AssetIntegrationConnectorForm(data=payload, tenant=tenant_a)
        assert not form.is_valid()
        assert field_name in form.errors

    @pytest.mark.parametrize(
        "field_name,fixture_name",
        [
            ("connector", "integration_connector_b"),
            ("operational_asset", "operational_asset_b"),
            ("fixed_asset", "fixed_asset_b"),
            ("steward", "admin_b"),
        ],
    )
    def test_integration_api_hub_stream_form_rejects_foreign_fks_via_post(
        self,
        request,
        tenant_a,
        integration_connector_a,
        operational_asset_a,
        field_name,
        fixture_name,
    ):
        foreign_obj = request.getfixturevalue(fixture_name)
        payload = _integration_api_hub_stream_minimal_payload(
            integration_connector_a,
            operational_asset=operational_asset_a,
        )
        payload[field_name] = str(foreign_obj.pk)
        form = AssetTelemetryStreamForm(data=payload, tenant=tenant_a)
        assert not form.is_valid()
        assert field_name in form.errors

    @pytest.mark.parametrize(
        "field_name,fixture_name",
        [
            ("connector", "integration_connector_b"),
            ("fiscal_period", "integration_open_fiscal_period_b"),
            ("gl_account", "expense_account_b"),
            ("offset_gl_account", "accum_account_b"),
            ("fixed_asset", "fixed_asset_b"),
            ("purchase_order", "po_b"),
            ("capitalization", "capitalization_b"),
            ("maintenance_request", "maintenance_request_b"),
            ("cost_center", "org_unit_b"),
        ],
    )
    def test_integration_api_hub_gl_batch_form_rejects_foreign_fks_via_post(
        self,
        request,
        tenant_a,
        integration_connector_a,
        field_name,
        fixture_name,
    ):
        foreign_obj = request.getfixturevalue(fixture_name)
        payload = _integration_api_hub_gl_batch_minimal_payload(
            integration_connector_a,
        )
        payload[field_name] = str(foreign_obj.pk)
        form = AssetGlSyncBatchForm(data=payload, tenant=tenant_a)
        assert not form.is_valid()
        assert field_name in form.errors

    def test_integration_api_hub_gl_batch_form_rejects_foreign_depreciation_schedule_via_post(
        self,
        tenant_a,
        tenant_b,
        integration_connector_a,
        fixed_asset_b,
        operational_asset_b,
        expense_account_b,
        accum_account_b,
    ):
        sched_b = _integration_api_hub_make_depreciation_schedule(
            tenant_b,
            fixed_asset_b,
            operational_asset=operational_asset_b,
            expense_account=expense_account_b,
            accumulated_account=accum_account_b,
        )
        payload = _integration_api_hub_gl_batch_minimal_payload(
            integration_connector_a,
            depreciation_schedule=str(sched_b.pk),
        )
        form = AssetGlSyncBatchForm(data=payload, tenant=tenant_a)
        assert not form.is_valid()
        assert "depreciation_schedule" in form.errors

    @pytest.mark.parametrize(
        "field_name,fixture_name",
        [
            ("connector", "integration_connector_b"),
            ("operational_asset", "operational_asset_b"),
            ("location", "location_b"),
            ("org_unit", "org_unit_b"),
            ("gis_custodian", "admin_b"),
        ],
    )
    def test_integration_api_hub_gis_mapping_form_rejects_foreign_fks_via_post(
        self,
        request,
        tenant_a,
        integration_connector_a,
        field_name,
        fixture_name,
    ):
        foreign_obj = request.getfixturevalue(fixture_name)
        payload = _integration_api_hub_gis_mapping_minimal_payload(
            integration_connector_a,
        )
        payload[field_name] = str(foreign_obj.pk)
        form = AssetGisMappingForm(data=payload, tenant=tenant_a)
        assert not form.is_valid()
        assert field_name in form.errors

    def test_integration_api_hub_reject_foreign_helper_direct_and_widened_clean(
        self,
        tenant_a,
        vendor_party_a,
        vendor_party_b,
        integration_connector_a,
        integration_connector_b,
        operational_asset_a,
        org_unit_b,
        currency_usd,
    ):
        # 1. Direct helper checks (single object, None, QuerySet, tenant=None)
        form = AssetIntegrationConnectorForm(tenant=tenant_a)
        form.cleaned_data = {"vendor_partner": vendor_party_a}
        reject_foreign(form, form.cleaned_data, ["vendor_partner"])
        assert "vendor_partner" not in form.errors

        form.cleaned_data = {"vendor_partner": None}
        reject_foreign(form, form.cleaned_data, ["vendor_partner"])
        assert "vendor_partner" not in form.errors

        foreign_form = AssetIntegrationConnectorForm(tenant=tenant_a)
        foreign_form.cleaned_data = {"vendor_partner": vendor_party_b}
        reject_foreign(foreign_form, foreign_form.cleaned_data, ["vendor_partner"])
        assert (
            "That record belongs to another workspace."
            in foreign_form.errors["vendor_partner"]
        )

        qs_form = AssetIntegrationConnectorForm(tenant=tenant_a)
        qs_form.cleaned_data = {
            "vendor_partner": Party.objects.filter(pk=vendor_party_b.pk)
        }
        reject_foreign(qs_form, qs_form.cleaned_data, ["vendor_partner"])
        assert (
            "That record belongs to another workspace."
            in qs_form.errors["vendor_partner"]
        )

        none_form = AssetIntegrationConnectorForm(tenant=None)
        none_form.cleaned_data = {"vendor_partner": vendor_party_a}
        reject_foreign(none_form, none_form.cleaned_data, ["vendor_partner"])
        assert (
            "That record belongs to another workspace."
            in none_form.errors["vendor_partner"]
        )

        # 2. Defense-in-depth inside each form's clean() even if queryset were widened
        widened_conn = AssetIntegrationConnectorForm(
            data=_integration_api_hub_connector_minimal_payload(
                vendor_partner=str(vendor_party_b.pk),
                default_currency=str(currency_usd.pk),
            ),
            tenant=tenant_a,
        )
        widened_conn.fields["vendor_partner"].queryset = Party.objects.all()
        assert not widened_conn.is_valid()
        assert (
            "That record belongs to another workspace."
            in widened_conn.errors["vendor_partner"]
        )
        assert "default_currency" not in widened_conn.errors

        widened_stream = AssetTelemetryStreamForm(
            data=_integration_api_hub_stream_minimal_payload(
                integration_connector_b, operational_asset=operational_asset_a
            ),
            tenant=tenant_a,
        )
        widened_stream.fields["connector"].queryset = (
            AssetIntegrationConnector.objects.all()
        )
        assert not widened_stream.is_valid()
        assert (
            "That record belongs to another workspace."
            in widened_stream.errors["connector"]
        )

        widened_batch = AssetGlSyncBatchForm(
            data=_integration_api_hub_gl_batch_minimal_payload(
                integration_connector_a,
                cost_center=str(org_unit_b.pk),
                currency=str(currency_usd.pk),
            ),
            tenant=tenant_a,
        )
        widened_batch.fields["cost_center"].queryset = OrgUnit.objects.all()
        assert not widened_batch.is_valid()
        assert (
            "That record belongs to another workspace."
            in widened_batch.errors["cost_center"]
        )
        assert "currency" not in widened_batch.errors

        widened_gis = AssetGisMappingForm(
            data=_integration_api_hub_gis_mapping_minimal_payload(
                integration_connector_b
            ),
            tenant=tenant_a,
        )
        widened_gis.fields["connector"].queryset = (
            AssetIntegrationConnector.objects.all()
        )
        assert not widened_gis.is_valid()
        assert (
            "That record belongs to another workspace."
            in widened_gis.errors["connector"]
        )


# =====================================================================
# 5. AssetIntegrationConnectorForm Domain Validation
# =====================================================================


class TestIntegrationApiHubConnectorFormValidation:
    """Tests valid creation/editing, SSRF URL rejection, and numeric bounds."""

    def test_integration_api_hub_connector_form_valid_minimal_full_and_edit(
        self,
        tenant_a,
        vendor_party_a,
        org_unit_a,
        currency_usd,
        admin_user,
        integration_connector_a,
    ):
        minimal_form = AssetIntegrationConnectorForm(
            data=_integration_api_hub_connector_minimal_payload(), tenant=tenant_a
        )
        assert minimal_form.is_valid(), minimal_form.errors
        created_min = minimal_form.save()
        assert created_min.tenant == tenant_a
        assert created_min.number.startswith("AICN-")

        full_payload = _integration_api_hub_connector_minimal_payload(
            name="Maximo EAM Full Bridge",
            connector_category="cmms_eam",
            provider="maximo_eam",
            protocol="rest_json",
            sync_direction="outbound",
            environment="staging",
            endpoint_url="https://maximo-api.example.com:8443/maxrest/oslc",
            auth_method="oauth2_client",
            rate_limit_rpm="600",
            timeout_seconds="45",
            retry_policy_max="0",
            polling_interval_minutes="5",
            status="active",
            vendor_partner=str(vendor_party_a.pk),
            default_org_unit=str(org_unit_a.pk),
            default_currency=str(currency_usd.pk),
            owner=str(admin_user.pk),
            webhook_verify_tls=False,
            notes="Full connector payload check.",
        )
        full_form = AssetIntegrationConnectorForm(data=full_payload, tenant=tenant_a)
        assert full_form.is_valid(), full_form.errors
        created_full = full_form.save()
        assert created_full.vendor_partner == vendor_party_a
        assert created_full.default_org_unit == org_unit_a
        assert created_full.default_currency == currency_usd
        assert created_full.owner == admin_user
        assert created_full.webhook_verify_tls is False

        edit_payload = _integration_api_hub_connector_minimal_payload(
            name="Acme SAP Hub Updated",
            rate_limit_rpm="300",
        )
        edit_form = AssetIntegrationConnectorForm(
            data=edit_payload, instance=integration_connector_a, tenant=tenant_a
        )
        assert edit_form.is_valid(), edit_form.errors
        updated = edit_form.save()
        assert updated.pk == integration_connector_a.pk
        assert updated.name == "Acme SAP Hub Updated"

    @pytest.mark.parametrize(
        "endpoint_url",
        [
            "https://api.example.com/v1/assets",
            "http://erp-gateway.example.com:8080/odata",
            "opc.tcp://scada.example.com:4840/UA/PlantServer",
            "mqtts://broker.example.com:8883/plant/telemetry",
            "mqtt://telemetry.example.com:1883/sensors",
            "tcps://modbus-proxy.example.com:5020",
            "sftp://files.example.com/exports/assets",
            "wss://realtime.example.com/ws/stream",
        ],
    )
    def test_integration_api_hub_connector_form_accepts_allowed_protocol_urls(
        self, tenant_a, endpoint_url
    ):
        payload = _integration_api_hub_connector_minimal_payload(
            endpoint_url=endpoint_url
        )
        form = AssetIntegrationConnectorForm(data=payload, tenant=tenant_a)
        assert form.is_valid(), form.errors

    @pytest.mark.parametrize(
        "bad_url",
        [
            "http://2130706433/",
            "http://0x7f000001/",
            "http://[::ffff:127.0.0.1]/",
            "ftp://bad.example.com/feed",
            "javascript:alert(1)",
            "file:///etc/passwd",
            "http://localhost/api",
            "http://127.0.0.1:8080/api",
            "http://[::1]/api",
            "http://0.0.0.0/api",
            "http://169.254.169.254/latest/meta-data/",
            "http://metadata.google.internal/computeMetadata/v1/",
            "https://10.0.0.1/api",
            "https://192.168.1.10/api",
            "https://172.16.0.1/api",
            "https://100.64.0.1/api",
            "https://service.internal/api",
            "https://plc.local/api",
            "https://gateway.localhost/api",
            "https://user:pass@api.example.com/v1",
            "https://api.example.com/has space",
            "https://api.example.com\\backslash",
            "https://[fe80::1%25eth0]/",
            "https://api.example.com:99999/v1",
            "",
        ],
    )
    def test_integration_api_hub_connector_form_rejects_ssrf_and_invalid_urls(
        self, tenant_a, bad_url
    ):
        payload = _integration_api_hub_connector_minimal_payload(endpoint_url=bad_url)
        form = AssetIntegrationConnectorForm(data=payload, tenant=tenant_a)
        assert not form.is_valid()
        assert "endpoint_url" in form.errors

    @pytest.mark.parametrize(
        "field_name,bad_value",
        [
            ("rate_limit_rpm", "0"),
            ("rate_limit_rpm", "-10"),
            ("timeout_seconds", "0"),
            ("timeout_seconds", "-1"),
            ("polling_interval_minutes", "0"),
            ("polling_interval_minutes", "-5"),
            ("retry_policy_max", "-1"),
        ],
    )
    def test_integration_api_hub_connector_form_rejects_invalid_numeric_limits(
        self, tenant_a, field_name, bad_value
    ):
        payload = _integration_api_hub_connector_minimal_payload(
            **{field_name: bad_value}
        )
        form = AssetIntegrationConnectorForm(data=payload, tenant=tenant_a)
        assert not form.is_valid()
        assert field_name in form.errors

    def test_integration_api_hub_connector_form_missing_required_name(self, tenant_a):
        payload = _integration_api_hub_connector_minimal_payload(name="")
        form = AssetIntegrationConnectorForm(data=payload, tenant=tenant_a)
        assert not form.is_valid()
        assert "name" in form.errors


# =====================================================================
# 6. AssetTelemetryStreamForm Domain Validation
# =====================================================================


class TestIntegrationApiHubTelemetryStreamFormValidation:
    """Tests asset requirement, scale/deadband/polling, threshold rules, and NaN/Inf safety."""

    def test_integration_api_hub_stream_form_valid_minimal_and_full_create_and_edit(
        self,
        tenant_a,
        integration_connector_a,
        operational_asset_a,
        fixed_asset_a,
        admin_user,
        integration_stream_a,
    ):
        # Operational asset only
        op_only_form = AssetTelemetryStreamForm(
            data=_integration_api_hub_stream_minimal_payload(
                integration_connector_a, operational_asset=operational_asset_a
            ),
            tenant=tenant_a,
        )
        assert op_only_form.is_valid(), op_only_form.errors
        s1 = op_only_form.save()
        assert s1.operational_asset == operational_asset_a
        assert s1.fixed_asset is None

        # Fixed asset only
        fa_only_form = AssetTelemetryStreamForm(
            data=_integration_api_hub_stream_minimal_payload(
                integration_connector_a, fixed_asset=fixed_asset_a
            ),
            tenant=tenant_a,
        )
        assert fa_only_form.is_valid(), fa_only_form.errors
        s2 = fa_only_form.save()
        assert s2.fixed_asset == fixed_asset_a
        assert s2.operational_asset is None

        # Full payload
        full_form = AssetTelemetryStreamForm(
            data=_integration_api_hub_stream_minimal_payload(
                integration_connector_a,
                operational_asset=operational_asset_a,
                fixed_asset=fixed_asset_a,
                baseline_value="45.0000",
                warning_threshold="75.0000",
                critical_threshold="92.5000",
                steward=str(admin_user.pk),
                notes="Full SCADA stream setup.",
            ),
            tenant=tenant_a,
        )
        assert full_form.is_valid(), full_form.errors
        s3 = full_form.save()
        assert s3.steward == admin_user

        # Edit existing
        edit_form = AssetTelemetryStreamForm(
            data=_integration_api_hub_stream_minimal_payload(
                integration_connector_a,
                operational_asset=operational_asset_a,
                stream_name="Updated Spindle Temp Feed",
            ),
            instance=integration_stream_a,
            tenant=tenant_a,
        )
        assert edit_form.is_valid(), edit_form.errors

    def test_integration_api_hub_stream_form_requires_at_least_one_asset(
        self, tenant_a, integration_connector_a
    ):
        payload = _integration_api_hub_stream_minimal_payload(
            integration_connector_a, operational_asset=None, fixed_asset=None
        )
        form = AssetTelemetryStreamForm(data=payload, tenant=tenant_a)
        assert not form.is_valid()
        assert "operational_asset" in form.errors

    def test_integration_api_hub_stream_form_scale_factor_nonzero_and_allows_negative(
        self, tenant_a, integration_connector_a, operational_asset_a
    ):
        for zero_val in ("0", "0.000000"):
            payload = _integration_api_hub_stream_minimal_payload(
                integration_connector_a,
                operational_asset=operational_asset_a,
                scale_factor=zero_val,
            )
            form = AssetTelemetryStreamForm(data=payload, tenant=tenant_a)
            assert not form.is_valid()
            assert "scale_factor" in form.errors

        neg_payload = _integration_api_hub_stream_minimal_payload(
            integration_connector_a,
            operational_asset=operational_asset_a,
            scale_factor="-0.500000",
        )
        neg_form = AssetTelemetryStreamForm(data=neg_payload, tenant=tenant_a)
        assert neg_form.is_valid(), neg_form.errors

    def test_integration_api_hub_stream_form_deadband_and_polling_bounds(
        self, tenant_a, integration_connector_a, operational_asset_a
    ):
        neg_deadband = AssetTelemetryStreamForm(
            data=_integration_api_hub_stream_minimal_payload(
                integration_connector_a,
                operational_asset=operational_asset_a,
                deadband_delta="-0.0001",
            ),
            tenant=tenant_a,
        )
        assert not neg_deadband.is_valid()
        assert "deadband_delta" in neg_deadband.errors

        zero_deadband = AssetTelemetryStreamForm(
            data=_integration_api_hub_stream_minimal_payload(
                integration_connector_a,
                operational_asset=operational_asset_a,
                deadband_delta="0.0000",
            ),
            tenant=tenant_a,
        )
        assert zero_deadband.is_valid(), zero_deadband.errors

        for bad_poll in ("0", "-1"):
            bad_poll_form = AssetTelemetryStreamForm(
                data=_integration_api_hub_stream_minimal_payload(
                    integration_connector_a,
                    operational_asset=operational_asset_a,
                    polling_interval_seconds=bad_poll,
                ),
                tenant=tenant_a,
            )
            assert not bad_poll_form.is_valid()
            assert "polling_interval_seconds" in bad_poll_form.errors

    def test_integration_api_hub_stream_form_threshold_ordering(
        self, tenant_a, integration_connector_a, operational_asset_a
    ):
        bad_thresholds = AssetTelemetryStreamForm(
            data=_integration_api_hub_stream_minimal_payload(
                integration_connector_a,
                operational_asset=operational_asset_a,
                warning_threshold="80.0000",
                critical_threshold="75.0000",
            ),
            tenant=tenant_a,
        )
        assert not bad_thresholds.is_valid()
        assert "critical_threshold" in bad_thresholds.errors

        equal_thresholds = AssetTelemetryStreamForm(
            data=_integration_api_hub_stream_minimal_payload(
                integration_connector_a,
                operational_asset=operational_asset_a,
                warning_threshold="80.0000",
                critical_threshold="80.0000",
            ),
            tenant=tenant_a,
        )
        assert equal_thresholds.is_valid(), equal_thresholds.errors

        warn_only = AssetTelemetryStreamForm(
            data=_integration_api_hub_stream_minimal_payload(
                integration_connector_a,
                operational_asset=operational_asset_a,
                warning_threshold="80.0000",
                critical_threshold="",
            ),
            tenant=tenant_a,
        )
        assert warn_only.is_valid(), warn_only.errors

    @pytest.mark.parametrize(
        "field_name",
        [
            "deadband_delta",
            "scale_factor",
            "offset_value",
            "baseline_value",
            "warning_threshold",
            "critical_threshold",
        ],
    )
    @pytest.mark.parametrize("bad_decimal", ["NaN", "Infinity", "-Infinity", "sNaN"])
    def test_integration_api_hub_stream_form_rejects_non_finite_decimals_cleanly(
        self,
        tenant_a,
        integration_connector_a,
        operational_asset_a,
        field_name,
        bad_decimal,
    ):
        payload = _integration_api_hub_stream_minimal_payload(
            integration_connector_a,
            operational_asset=operational_asset_a,
            **{field_name: bad_decimal},
        )
        form = AssetTelemetryStreamForm(data=payload, tenant=tenant_a)
        assert not form.is_valid()
        assert field_name in form.errors


# =====================================================================
# 7. AssetGlSyncBatchForm Domain Validation
# =====================================================================


class TestIntegrationApiHubGlSyncBatchFormValidation:
    """Tests account distinction, amounts, non-finite decimals, JSON, and payload size bounds."""

    def test_integration_api_hub_gl_batch_form_valid_minimal_full_and_edit(
        self,
        tenant_a,
        integration_connector_a,
        integration_open_fiscal_period_a,
        expense_account_a,
        asset_account_a,
        fixed_asset_a,
        operational_asset_a,
        po_a,
        capitalization_a,
        maintenance_request_a,
        org_unit_a,
        currency_usd,
        integration_gl_batch_a,
    ):
        sched_a = _integration_api_hub_make_depreciation_schedule(
            tenant_a,
            fixed_asset_a,
            operational_asset=operational_asset_a,
            expense_account=expense_account_a,
        )
        minimal_form = AssetGlSyncBatchForm(
            data=_integration_api_hub_gl_batch_minimal_payload(
                integration_connector_a
            ),
            tenant=tenant_a,
        )
        assert minimal_form.is_valid(), minimal_form.errors
        created_min = minimal_form.save()
        assert created_min.tenant == tenant_a
        assert created_min.variance_amount == Decimal("0.00")

        full_payload = _integration_api_hub_gl_batch_minimal_payload(
            integration_connector_a,
            sync_domain="capitalization_sync",
            sync_direction="bidirectional",
            external_batch_ref="SAP-CAP-2026-099",
            fiscal_period=str(integration_open_fiscal_period_a.pk),
            gl_account=str(expense_account_a.pk),
            offset_gl_account=str(asset_account_a.pk),
            fixed_asset=str(fixed_asset_a.pk),
            purchase_order=str(po_a.pk),
            capitalization=str(capitalization_a.pk),
            depreciation_schedule=str(sched_a.pk),
            maintenance_request=str(maintenance_request_a.pk),
            cost_center=str(org_unit_a.pk),
            currency=str(currency_usd.pk),
            source_amount="5000.00",
            target_gl_amount="4750.00",
            field_mapping_json='{"company": "1000", "cost_center": "KOSTL"}',
            payload_summary="Full capitalization subledger sync batch.",
            notes="Verified full payload.",
        )
        full_form = AssetGlSyncBatchForm(data=full_payload, tenant=tenant_a)
        assert full_form.is_valid(), full_form.errors
        created_full = full_form.save()
        assert created_full.variance_amount == Decimal("250.00")
        assert created_full.purchase_order == po_a
        assert created_full.depreciation_schedule == sched_a

        edit_form = AssetGlSyncBatchForm(
            data=_integration_api_hub_gl_batch_minimal_payload(
                integration_connector_a,
                gl_account=str(expense_account_a.pk),
                offset_gl_account=str(asset_account_a.pk),
                notes="Updated batch notes.",
            ),
            instance=integration_gl_batch_a,
            tenant=tenant_a,
        )
        assert edit_form.is_valid(), edit_form.errors

    def test_integration_api_hub_gl_batch_form_requires_distinct_gl_accounts(
        self, tenant_a, integration_connector_a, expense_account_a
    ):
        same_accounts = AssetGlSyncBatchForm(
            data=_integration_api_hub_gl_batch_minimal_payload(
                integration_connector_a,
                gl_account=str(expense_account_a.pk),
                offset_gl_account=str(expense_account_a.pk),
            ),
            tenant=tenant_a,
        )
        assert not same_accounts.is_valid()
        assert "offset_gl_account" in same_accounts.errors

        only_debit = AssetGlSyncBatchForm(
            data=_integration_api_hub_gl_batch_minimal_payload(
                integration_connector_a,
                gl_account=str(expense_account_a.pk),
                offset_gl_account="",
            ),
            tenant=tenant_a,
        )
        assert only_debit.is_valid(), only_debit.errors

    @pytest.mark.parametrize(
        "field_name,bad_value",
        [
            ("source_amount", "-0.01"),
            ("target_gl_amount", "-10.00"),
            ("source_amount", "NaN"),
            ("source_amount", "Infinity"),
            ("source_amount", "-Infinity"),
            ("target_gl_amount", "NaN"),
            ("target_gl_amount", "Infinity"),
            ("target_gl_amount", "-Infinity"),
        ],
    )
    def test_integration_api_hub_gl_batch_form_rejects_negative_and_non_finite_amounts(
        self, tenant_a, integration_connector_a, field_name, bad_value
    ):
        payload = _integration_api_hub_gl_batch_minimal_payload(
            integration_connector_a, **{field_name: bad_value}
        )
        form = AssetGlSyncBatchForm(data=payload, tenant=tenant_a)
        assert not form.is_valid()
        assert field_name in form.errors

    @pytest.mark.parametrize(
        "bad_json",
        [
            "{not valid json",
            '{"unclosed": 1',
            "[]",
            "[1, 2, 3]",
            '"a string"',
            "123",
            "true",
            "null",
            '{"val": NaN}',
            '{"val": Infinity}',
            '{"val": -Infinity}',
            '{"blob": "' + ("x" * 65536) + '"}',
        ],
        ids=[
            "bad-syntax",
            "unclosed-brace",
            "empty-list",
            "int-list",
            "json-string",
            "json-number",
            "json-bool",
            "json-null",
            "nan-constant",
            "inf-constant",
            "neg-inf-constant",
            "over-64kb",
        ],
    )
    def test_integration_api_hub_gl_batch_form_strict_field_mapping_json(
        self, tenant_a, integration_connector_a, bad_json
    ):
        payload = _integration_api_hub_gl_batch_minimal_payload(
            integration_connector_a, field_mapping_json=bad_json
        )
        form = AssetGlSyncBatchForm(data=payload, tenant=tenant_a)
        assert not form.is_valid()
        assert "field_mapping_json" in form.errors

    def test_integration_api_hub_gl_batch_form_accepts_blank_and_64kb_boundary_json(
        self, tenant_a, integration_connector_a
    ):
        for blank_val in ("", "   "):
            form = AssetGlSyncBatchForm(
                data=_integration_api_hub_gl_batch_minimal_payload(
                    integration_connector_a, field_mapping_json=blank_val
                ),
                tenant=tenant_a,
            )
            assert form.is_valid(), form.errors

        prefix = '{"k":"'
        suffix = '"}'
        exact_64kb_json = prefix + ("a" * (65536 - len(prefix) - len(suffix))) + suffix
        assert len(exact_64kb_json.encode("utf-8")) == 65536
        boundary_form = AssetGlSyncBatchForm(
            data=_integration_api_hub_gl_batch_minimal_payload(
                integration_connector_a, field_mapping_json=exact_64kb_json
            ),
            tenant=tenant_a,
        )
        assert boundary_form.is_valid(), boundary_form.errors

    def test_integration_api_hub_gl_batch_form_payload_summary_64kb_limit(
        self, tenant_a, integration_connector_a
    ):
        ok_summary = "x" * 65536
        ok_form = AssetGlSyncBatchForm(
            data=_integration_api_hub_gl_batch_minimal_payload(
                integration_connector_a, payload_summary=ok_summary
            ),
            tenant=tenant_a,
        )
        assert ok_form.is_valid(), ok_form.errors

        too_big_ascii = AssetGlSyncBatchForm(
            data=_integration_api_hub_gl_batch_minimal_payload(
                integration_connector_a, payload_summary="x" * 65537
            ),
            tenant=tenant_a,
        )
        assert not too_big_ascii.is_valid()
        assert "payload_summary" in too_big_ascii.errors

        # Multi-byte UTF-8: 33,000 chars (<65,536 chars) but 66,000 bytes (>65,536 bytes)
        too_big_utf8 = AssetGlSyncBatchForm(
            data=_integration_api_hub_gl_batch_minimal_payload(
                integration_connector_a, payload_summary="é" * 33000
            ),
            tenant=tenant_a,
        )
        assert not too_big_utf8.is_valid()
        assert "payload_summary" in too_big_utf8.errors


# =====================================================================
# 8. AssetGisMappingForm Domain Validation
# =====================================================================


class TestIntegrationApiHubGisMappingFormValidation:
    """Tests coordinate bounds, SRID, LRS measure ranges, non-finite decimals, and GeoJSON."""

    def test_integration_api_hub_gis_mapping_form_valid_minimal_full_and_edit(
        self,
        tenant_a,
        integration_connector_a,
        operational_asset_a,
        location_a,
        org_unit_a,
        admin_user,
        integration_gis_mapping_a,
    ):
        minimal_form = AssetGisMappingForm(
            data=_integration_api_hub_gis_mapping_minimal_payload(
                integration_connector_a
            ),
            tenant=tenant_a,
        )
        assert minimal_form.is_valid(), minimal_form.errors
        created_min = minimal_form.save()
        assert created_min.tenant == tenant_a
        assert created_min.number.startswith("AGIS-")

        full_form = AssetGisMappingForm(
            data=_integration_api_hub_gis_mapping_minimal_payload(
                integration_connector_a,
                operational_asset=str(operational_asset_a.pk),
                location=str(location_a.pk),
                org_unit=str(org_unit_a.pk),
                geometry_type="linestring",
                coordinate_system_srid="3857",
                latitude="40.748400",
                longitude="-73.985700",
                elevation_meters="125.50",
                is_linear_asset=True,
                lrs_route_id="CORRIDOR-WEST-09",
                lrs_from_measure="0.000",
                lrs_to_measure="14.750",
                lrs_measure_unit="km",
                geojson_payload='{"type": "LineString", "coordinates": [[-73.9857, 40.7484], [-73.98, 40.75]]}',
                system_of_record="gis_authoritative",
                sync_direction="inbound",
                status="active",
                gis_custodian=str(admin_user.pk),
                notes="Full LRS pipeline segment.",
            ),
            tenant=tenant_a,
        )
        assert full_form.is_valid(), full_form.errors
        created_full = full_form.save()
        assert created_full.is_linear_asset is True
        assert created_full.lrs_to_measure == Decimal("14.750")

        edit_form = AssetGisMappingForm(
            data=_integration_api_hub_gis_mapping_minimal_payload(
                integration_connector_a,
                layer_name="updated_machinery_pt",
            ),
            instance=integration_gis_mapping_a,
            tenant=tenant_a,
        )
        assert edit_form.is_valid(), edit_form.errors

    @pytest.mark.parametrize(
        "field_name,valid_values,invalid_values",
        [
            (
                "latitude",
                ["-90.000000", "0.000000", "90.000000"],
                ["-90.000001", "90.000001"],
            ),
            (
                "longitude",
                ["-180.000000", "0.000000", "180.000000"],
                ["-180.000001", "180.000001"],
            ),
        ],
    )
    def test_integration_api_hub_gis_mapping_form_coordinate_bounds(
        self,
        tenant_a,
        integration_connector_a,
        field_name,
        valid_values,
        invalid_values,
    ):
        for good in valid_values:
            form = AssetGisMappingForm(
                data=_integration_api_hub_gis_mapping_minimal_payload(
                    integration_connector_a, **{field_name: good}
                ),
                tenant=tenant_a,
            )
            assert form.is_valid(), f"{field_name}={good}: {form.errors}"

        for bad in invalid_values:
            form = AssetGisMappingForm(
                data=_integration_api_hub_gis_mapping_minimal_payload(
                    integration_connector_a, **{field_name: bad}
                ),
                tenant=tenant_a,
            )
            assert not form.is_valid()
            assert field_name in form.errors

    @pytest.mark.parametrize(
        "field_name",
        [
            "latitude",
            "longitude",
            "elevation_meters",
            "lrs_from_measure",
            "lrs_to_measure",
        ],
    )
    @pytest.mark.parametrize("bad_decimal", ["NaN", "Infinity", "-Infinity"])
    def test_integration_api_hub_gis_mapping_form_rejects_non_finite_decimals_cleanly(
        self, tenant_a, integration_connector_a, field_name, bad_decimal
    ):
        form = AssetGisMappingForm(
            data=_integration_api_hub_gis_mapping_minimal_payload(
                integration_connector_a, **{field_name: bad_decimal}
            ),
            tenant=tenant_a,
        )
        assert not form.is_valid()
        assert field_name in form.errors

    def test_integration_api_hub_gis_mapping_form_srid_and_lrs_range_validation(
        self, tenant_a, integration_connector_a
    ):
        for bad_srid in ("0", "-4326"):
            bad_srid_form = AssetGisMappingForm(
                data=_integration_api_hub_gis_mapping_minimal_payload(
                    integration_connector_a, coordinate_system_srid=bad_srid
                ),
                tenant=tenant_a,
            )
            assert not bad_srid_form.is_valid()
            assert "coordinate_system_srid" in bad_srid_form.errors

        min_srid_form = AssetGisMappingForm(
            data=_integration_api_hub_gis_mapping_minimal_payload(
                integration_connector_a, coordinate_system_srid="1"
            ),
            tenant=tenant_a,
        )
        assert min_srid_form.is_valid(), min_srid_form.errors

        bad_lrs = AssetGisMappingForm(
            data=_integration_api_hub_gis_mapping_minimal_payload(
                integration_connector_a,
                is_linear_asset=True,
                lrs_route_id="PIPE-1",
                lrs_from_measure="12.500",
                lrs_to_measure="12.499",
            ),
            tenant=tenant_a,
        )
        assert not bad_lrs.is_valid()
        assert "lrs_to_measure" in bad_lrs.errors

        equal_lrs = AssetGisMappingForm(
            data=_integration_api_hub_gis_mapping_minimal_payload(
                integration_connector_a,
                is_linear_asset=True,
                lrs_route_id="PIPE-1",
                lrs_from_measure="12.500",
                lrs_to_measure="12.500",
            ),
            tenant=tenant_a,
        )
        assert equal_lrs.is_valid(), equal_lrs.errors

    @pytest.mark.parametrize(
        "bad_geojson",
        [
            "{broken geojson",
            "[]",
            '"Point"',
            "42",
            '{"type": "Point", "coordinates": [NaN, 40.7]}',
            '{"type": "Point", "coordinates": [Infinity, 40.7]}',
            '{"type": "Point", "coordinates": [-Infinity, 40.7]}',
            '{"type": "Point", "note": "' + ("g" * 65536) + '"}',
        ],
        ids=[
            "bad-syntax",
            "empty-list",
            "json-string",
            "json-number",
            "nan-constant",
            "inf-constant",
            "neg-inf-constant",
            "over-64kb",
        ],
    )
    def test_integration_api_hub_gis_mapping_form_strict_geojson_validation(
        self, tenant_a, integration_connector_a, bad_geojson
    ):
        form = AssetGisMappingForm(
            data=_integration_api_hub_gis_mapping_minimal_payload(
                integration_connector_a, geojson_payload=bad_geojson
            ),
            tenant=tenant_a,
        )
        assert not form.is_valid()
        assert "geojson_payload" in form.errors


# =====================================================================
# 9. O(1) Query Bound on AssetGlSyncBatchForm Dropdown Evaluation
# =====================================================================


class TestIntegrationApiHubGlBatchQueryPerformance:
    """Verify O(1) bounded queries when instantiating & rendering GL Batch dropdowns."""

    def test_integration_api_hub_gl_batch_form_dropdown_evaluation_o1_queries(
        self,
        tenant_a,
        tenant_b,
        expense_account_a,
        expense_account_b,
        asset_account_a,
        accum_account_b,
        fixed_asset_a,
        fixed_asset_b,
        operational_asset_a,
        operational_asset_b,
        po_a,
        po_b,
        django_assert_max_num_queries,
    ):
        sched_a = _integration_api_hub_make_depreciation_schedule(
            tenant_a,
            fixed_asset_a,
            operational_asset=operational_asset_a,
            expense_account=expense_account_a,
        )
        sched_b = _integration_api_hub_make_depreciation_schedule(
            tenant_b,
            fixed_asset_b,
            operational_asset=operational_asset_b,
            expense_account=expense_account_b,
            accumulated_account=accum_account_b,
        )
        # Create N=6 distinct vendors + POs, distinct FixedAssets + Schedules, and GLAccounts
        created_gl_codes = []
        created_po_numbers = []
        created_sched_numbers = [sched_a.number]

        for idx in range(1, 7):
            gl = GLAccount.objects.create(
                tenant=tenant_a,
                code=f"7{idx:03d}-A",
                name=f"Scale Test GL Account {idx}",
                account_type="expense",
                is_active=True,
            )
            created_gl_codes.append(gl.code)

            vendor = Party.objects.create(
                tenant=tenant_a,
                name=f"Scale Vendor {idx}",
                kind="organization",
            )
            po = PurchaseOrder.objects.create(
                tenant=tenant_a,
                number=f"PO-O1-{idx:04d}",
                vendor=vendor,
                status="approved",
            )
            created_po_numbers.append(po.number)

            fa = FixedAsset.objects.create(
                tenant=tenant_a,
                name=f"Scale Asset {idx}",
                category="Machinery",
                acquisition_cost=Decimal("50000.00"),
                salvage_value=Decimal("5000.00"),
                useful_life_months=60,
                asset_account=asset_account_a,
                expense_account=expense_account_a,
            )
            sched = AssetDepreciationSchedule.objects.create(
                tenant=tenant_a,
                fixed_asset=fa,
                fiscal_year=2026,
                period_number=idx,
                period_frequency="monthly",
                schedule_date=timezone.localdate(),
                depreciation_method="straight_line",
                starting_book_value=Decimal("50000.00"),
                depreciation_amount=Decimal("750.00"),
                accumulated_depreciation_after=Decimal("750.00"),
                ending_book_value=Decimal("49250.00"),
                expense_account=expense_account_a,
                status="draft",
            )
            created_sched_numbers.append(sched.number)

        # Single GLAccount query in __init__ + 1 PO select_related(vendor) + 1 Schedule select_related(fixed_asset)
        with django_assert_max_num_queries(3):
            form = AssetGlSyncBatchForm(tenant=tenant_a)
            gl_html = str(form["gl_account"])
            offset_html = str(form["offset_gl_account"])
            po_html = str(form["purchase_order"])
            sched_html = str(form["depreciation_schedule"])

        for code in created_gl_codes:
            assert code in gl_html
            assert code in offset_html
        for po_num in created_po_numbers:
            assert po_num in po_html
        for idx in range(1, 7):
            assert f"Scale Vendor {idx}" in po_html
            assert f"Scale Asset {idx}" in sched_html
        for sched_num in created_sched_numbers:
            assert sched_num in sched_html

        assert str(po_a) in po_html
        assert str(sched_a) in sched_html
        assert po_b.number not in po_html
        assert str(po_b) not in po_html
        assert f'value="{po_b.pk}"' not in po_html
        assert str(sched_b) not in sched_html
        assert f'value="{sched_b.pk}"' not in sched_html

    def test_integration_api_hub_gl_batch_form_edit_dropdown_evaluation_o1_queries(
        self,
        tenant_a,
        integration_connector_a,
        expense_account_a,
        asset_account_a,
        fixed_asset_a,
        operational_asset_a,
        po_a,
        django_assert_max_num_queries,
    ):
        sched_a = _integration_api_hub_make_depreciation_schedule(
            tenant_a,
            fixed_asset_a,
            operational_asset=operational_asset_a,
            expense_account=expense_account_a,
        )
        inactive_gl = GLAccount.objects.create(
            tenant=tenant_a,
            code="6995-A-EDIT",
            name="Inactive Linked Edit Account",
            account_type="expense",
            is_active=False,
        )
        batch = AssetGlSyncBatch.objects.create(
            tenant=tenant_a,
            connector=integration_connector_a,
            gl_account=inactive_gl,
            offset_gl_account=asset_account_a,
            purchase_order=po_a,
            depreciation_schedule=sched_a,
            source_amount=Decimal("100.00"),
            target_gl_amount=Decimal("100.00"),
        )
        for idx in range(1, 5):
            vendor = Party.objects.create(
                tenant=tenant_a, name=f"Edit Vendor {idx}", kind="organization"
            )
            PurchaseOrder.objects.create(
                tenant=tenant_a,
                number=f"PO-ED-{idx:04d}",
                vendor=vendor,
                status="approved",
            )
            fa = FixedAsset.objects.create(
                tenant=tenant_a,
                name=f"Edit Asset {idx}",
                category="Equipment",
                acquisition_cost=Decimal("10000.00"),
                useful_life_months=24,
            )
            AssetDepreciationSchedule.objects.create(
                tenant=tenant_a,
                fixed_asset=fa,
                fiscal_year=2026,
                period_number=idx,
                schedule_date=timezone.localdate(),
                depreciation_amount=Decimal("400.00"),
            )

        with django_assert_max_num_queries(3):
            form = AssetGlSyncBatchForm(instance=batch, tenant=tenant_a)
            gl_html = str(form["gl_account"])
            offset_html = str(form["offset_gl_account"])
            po_html = str(form["purchase_order"])
            sched_html = str(form["depreciation_schedule"])

        assert inactive_gl.code in gl_html
        assert inactive_gl.code not in offset_html
        assert po_a.number in po_html
        assert sched_a.number in sched_html
