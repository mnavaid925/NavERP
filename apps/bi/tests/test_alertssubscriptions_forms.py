"""Unit tests for Sub-module 10.16 Alerts, Subscriptions & Distribution forms.

Forms covered:
- BiAlertRuleForm (BiAlertRule)
- ReportSubscriptionForm (ReportSubscription)
- DistributionBurstRunForm (DistributionBurstRun)
- BiNotificationItemForm (BiNotificationItem)
"""
from decimal import Decimal

import pytest
from django import forms
from django.contrib.auth import get_user_model

from apps.bi.forms import (
    BiAlertRuleForm,
    BiNotificationItemForm,
    DistributionBurstRunForm,
    ReportSubscriptionForm,
)
from apps.bi.models import (
    BiAlertRule,
    BiDashboard,
    BiNotificationItem,
    DistributionBurstRun,
    KpiDefinition,
    ReportDefinition,
    ReportSubscription,
    StatisticalAnomaly,
)
from apps.core.models.OrgUnit import OrgUnit

User = get_user_model()


# ---------------------------------------------------------------------------
# Module Helpers (strictly prefixed with _alertssubscriptions_)
# ---------------------------------------------------------------------------


def _alertssubscriptions_forms_create_org_unit(tenant, name="Analytics Unit"):
    """Helper to create a tenant-scoped OrgUnit record."""
    return OrgUnit.objects.create(tenant=tenant, name=name, kind="department")


def _alertssubscriptions_forms_create_report(
    tenant, name="Executive Operational Report", slug="exec-op-report"
):
    """Helper to create a tenant-scoped ReportDefinition record."""
    return ReportDefinition.objects.create(
        tenant=tenant,
        name=name,
        slug=slug,
        category="finance",
        report_type="standard_tabular",
        status="published",
    )


def _alertssubscriptions_forms_valid_alert_rule_data(
    kpi_definition=None, anomaly_detection=None, recipient_users=None, **kwargs
):
    """Helper returning a valid data payload for BiAlertRuleForm."""
    data = {
        "name": "Operating Margin Threshold Alert",
        "description": "Trigger alert if operating margin dips below target floor.",
        "alert_type": "kpi_threshold",
        "condition_operator": "lt",
        "threshold_value": "0.1500",
        "secondary_threshold_value": "0.2500",
        "severity": "critical",
        "evaluation_cadence": "hourly",
        "trigger_frequency": "once_until_resolved",
        "delivery_channel": "in_app_email",
        "notification_email_list": "ops@acme.com, alerts@acme.com",
        "webhook_url": "https://hooks.slack.com/services/T00/B00/X00",
        "downstream_workflow": "create_task",
        "status": "active",
    }
    if kpi_definition:
        data["kpi_definition"] = kpi_definition.pk
    if anomaly_detection:
        data["anomaly_detection"] = anomaly_detection.pk
    if recipient_users:
        data["recipient_users"] = [u.pk for u in recipient_users]
    data.update(kwargs)
    return data


def _alertssubscriptions_forms_valid_subscription_data(
    dashboard=None,
    report=None,
    subscriber_users=None,
    subscriber_org_units=None,
    **kwargs,
):
    """Helper returning a valid data payload for ReportSubscriptionForm."""
    data = {
        "name": "Weekly Monday Executive Digest",
        "target_asset_type": "dashboard",
        "export_format": "pdf",
        "cadence": "weekly",
        "scheduled_time": "08:00",
        "cron_expression": "0 8 * * 1",
        "burst_mode": "broadcast",
        "external_recipient_emails": "execs@acme.com, board@acme.com",
        "include_cover_page": True,
        "skip_if_empty": True,
        "status": "active",
    }
    if dashboard:
        data["dashboard"] = dashboard.pk
    if report:
        data["report"] = report.pk
    if subscriber_users:
        data["subscriber_users"] = [u.pk for u in subscriber_users]
    if subscriber_org_units:
        data["subscriber_org_units"] = [ou.pk for ou in subscriber_org_units]
    data.update(kwargs)
    return data


def _alertssubscriptions_forms_valid_burst_run_data(
    subscription=None, alert_rule=None, **kwargs
):
    """Helper returning a valid data payload for DistributionBurstRunForm."""
    data = {
        "run_trigger": "scheduled_subscription",
        "delivery_channel": "email",
        "status": "completed",
        "recipient_count": 12,
        "generated_file_name": "Weekly_Exec_Digest_20261108.pdf",
        "file_size_bytes": 1048576,
        "error_summary": "All 12 recipients dispatched with zero delivery failures.",
    }
    if subscription:
        data["subscription"] = subscription.pk
    if alert_rule:
        data["alert_rule"] = alert_rule.pk
    data.update(kwargs)
    return data


def _alertssubscriptions_forms_valid_notification_data(
    recipient, alert_rule=None, burst_run=None, **kwargs
):
    """Helper returning a valid data payload for BiNotificationItemForm."""
    data = {
        "recipient": recipient.pk,
        "title": "Operating Margin Threshold Tripped",
        "message": "Current margin 12.4% fell below target 15.0%.",
        "severity": "critical",
        "category": "kpi_alert",
        "status": "unread",
        "action_url": "/bi/dashboards/1/",
        "acknowledgment_notes": "Reviewed by on-call ops engineer.",
        "snoozed_until": "2026-11-10T12:00:00",
    }
    if alert_rule:
        data["alert_rule"] = alert_rule.pk
    if burst_run:
        data["burst_run"] = burst_run.pk
    data.update(kwargs)
    return data


# ===========================================================================
# 1. BiAlertRuleForm Tests
# ===========================================================================


@pytest.mark.django_db
def test_alertssubscriptions_forms_alert_rule_system_field_exclusions():
    """Verify system-managed fields are excluded from BiAlertRuleForm Meta.fields."""
    form = BiAlertRuleForm()
    system_fields = [
        "tenant",
        "number",
        "last_evaluated_at",
        "last_triggered_at",
        "trigger_count",
        "last_trigger_value",
        "created_at",
        "updated_at",
        "created_by",
    ]
    for field in system_fields:
        assert field not in form.fields, (
            f"Security violation: {field} exposed in BiAlertRuleForm"
        )


@pytest.mark.django_db
def test_alertssubscriptions_forms_alert_rule_valid_creation(tenant_a):
    """Verify valid form data creates a BiAlertRule bound to tenant."""
    data = _alertssubscriptions_forms_valid_alert_rule_data()
    form = BiAlertRuleForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    rule = form.save()
    assert rule.pk is not None
    assert rule.tenant == tenant_a
    assert rule.name == "Operating Margin Threshold Alert"
    assert rule.alert_type == "kpi_threshold"
    assert rule.condition_operator == "lt"
    assert rule.threshold_value == Decimal("0.1500")
    assert rule.secondary_threshold_value == Decimal("0.2500")
    assert rule.severity == "critical"
    assert rule.evaluation_cadence == "hourly"
    assert rule.trigger_frequency == "once_until_resolved"
    assert rule.delivery_channel == "in_app_email"
    assert rule.status == "active"


@pytest.mark.django_db
def test_alertssubscriptions_forms_alert_rule_with_all_relations(
    tenant_a, kpi_definition_a, statistical_anomaly_a, admin_user
):
    """Verify form saves with foreign keys and M2M recipient_users bound to tenant."""
    data = _alertssubscriptions_forms_valid_alert_rule_data(
        kpi_definition=kpi_definition_a,
        anomaly_detection=statistical_anomaly_a,
        recipient_users=[admin_user],
    )
    form = BiAlertRuleForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    rule = form.save()
    assert rule.kpi_definition == kpi_definition_a
    assert rule.anomaly_detection == statistical_anomaly_a
    assert admin_user in rule.recipient_users.all()


@pytest.mark.django_db
def test_alertssubscriptions_forms_alert_rule_required_fields(tenant_a):
    """Verify required fields fail validation when empty payload submitted."""
    form = BiAlertRuleForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "name" in form.errors


@pytest.mark.django_db
def test_alertssubscriptions_forms_alert_rule_unscoped_initialization():
    """Verify form initializes safely with tenant=None without raising exceptions."""
    form = BiAlertRuleForm(tenant=None)
    assert form.fields["name"].required is True
    assert "kpi_definition" in form.fields
    assert "anomaly_detection" in form.fields
    assert "recipient_users" in form.fields


@pytest.mark.django_db
def test_alertssubscriptions_forms_alert_rule_tenant_scoping_foreign_keys(
    tenant_a,
    kpi_definition_a,
    kpi_definition_b,
    statistical_anomaly_a,
    statistical_anomaly_b,
):
    """Verify FK querysets are filtered by tenant in __init__."""
    form = BiAlertRuleForm(tenant=tenant_a)

    kpi_qs = form.fields["kpi_definition"].queryset
    assert kpi_definition_a in kpi_qs
    assert kpi_definition_b not in kpi_qs

    anomaly_qs = form.fields["anomaly_detection"].queryset
    assert statistical_anomaly_a in anomaly_qs
    assert statistical_anomaly_b not in anomaly_qs


@pytest.mark.django_db
def test_alertssubscriptions_forms_alert_rule_tenant_scoping_m2m_recipients(
    tenant_a, admin_user, admin_user_b
):
    """Verify recipient_users M2M queryset is filtered to tenant users."""
    form = BiAlertRuleForm(tenant=tenant_a)
    recipient_qs = form.fields["recipient_users"].queryset
    assert admin_user in recipient_qs
    assert admin_user_b not in recipient_qs


@pytest.mark.django_db
def test_alertssubscriptions_forms_alert_rule_reject_foreign_kpi_definition(
    tenant_a, kpi_definition_b
):
    """Verify cross-tenant KPI definition is rejected by choices and reject_foreign."""
    data = _alertssubscriptions_forms_valid_alert_rule_data(
        kpi_definition=kpi_definition_b
    )
    # 1. Standard tenant-filtered form rejects at field validation
    form = BiAlertRuleForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "kpi_definition" in form.errors

    # 2. Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = BiAlertRuleForm(data=data, tenant=tenant_a)
    form_wide.fields["kpi_definition"].queryset = KpiDefinition.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors[
        "kpi_definition"
    ]


@pytest.mark.django_db
def test_alertssubscriptions_forms_alert_rule_reject_foreign_anomaly_detection(
    tenant_a, statistical_anomaly_b
):
    """Verify cross-tenant anomaly detection is rejected by choices and reject_foreign."""
    data = _alertssubscriptions_forms_valid_alert_rule_data(
        anomaly_detection=statistical_anomaly_b
    )
    # 1. Standard tenant-filtered form rejects at field validation
    form = BiAlertRuleForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "anomaly_detection" in form.errors

    # 2. Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = BiAlertRuleForm(data=data, tenant=tenant_a)
    form_wide.fields["anomaly_detection"].queryset = (
        StatisticalAnomaly.objects.all()
    )
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors[
        "anomaly_detection"
    ]


@pytest.mark.django_db
def test_alertssubscriptions_forms_alert_rule_reject_foreign_recipient_users(
    tenant_a, admin_user_b
):
    """Verify cross-tenant user recipient is rejected by choices and reject_foreign."""
    data = _alertssubscriptions_forms_valid_alert_rule_data(
        recipient_users=[admin_user_b]
    )
    # 1. Standard tenant-filtered form rejects at field validation
    form = BiAlertRuleForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "recipient_users" in form.errors

    # 2. Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = BiAlertRuleForm(data=data, tenant=tenant_a)
    form_wide.fields["recipient_users"].queryset = User.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors[
        "recipient_users"
    ]


@pytest.mark.django_db
def test_alertssubscriptions_forms_alert_rule_condition_operator_choices(tenant_a):
    """Verify valid condition operators accept and invalid operators fail."""
    valid_ops = ["gt", "gte", "lt", "lte", "eq", "outside_range", "pct_change_gt"]
    for op in valid_ops:
        data = _alertssubscriptions_forms_valid_alert_rule_data(
            name=f"Rule Op {op}", condition_operator=op
        )
        form = BiAlertRuleForm(data=data, tenant=tenant_a)
        assert form.is_valid(), f"Failed for valid operator {op}: {form.errors}"

    data_bad = _alertssubscriptions_forms_valid_alert_rule_data(
        condition_operator="invalid_op"
    )
    form_bad = BiAlertRuleForm(data=data_bad, tenant=tenant_a)
    assert not form_bad.is_valid()
    assert "condition_operator" in form_bad.errors


@pytest.mark.django_db
def test_alertssubscriptions_forms_alert_rule_severity_and_cadence_choices(tenant_a):
    """Verify severity and cadence choices validation."""
    for sev in ["info", "warning", "critical"]:
        data = _alertssubscriptions_forms_valid_alert_rule_data(
            name=f"Rule Sev {sev}", severity=sev
        )
        form = BiAlertRuleForm(data=data, tenant=tenant_a)
        assert form.is_valid()

    for cadence in ["on_data_refresh", "every_15_mins", "hourly", "daily", "weekly"]:
        data = _alertssubscriptions_forms_valid_alert_rule_data(
            name=f"Rule Cadence {cadence}", evaluation_cadence=cadence
        )
        form = BiAlertRuleForm(data=data, tenant=tenant_a)
        assert form.is_valid()


@pytest.mark.django_db
def test_alertssubscriptions_forms_alert_rule_delivery_and_workflow_choices(tenant_a):
    """Verify delivery_channel and downstream_workflow choices validation."""
    for channel in ["in_app_only", "in_app_email", "slack_webhook", "multi_channel"]:
        data = _alertssubscriptions_forms_valid_alert_rule_data(
            name=f"Rule Channel {channel}", delivery_channel=channel
        )
        form = BiAlertRuleForm(data=data, tenant=tenant_a)
        assert form.is_valid()

    for wf in ["none", "create_task", "request_approval", "trigger_webhook"]:
        data = _alertssubscriptions_forms_valid_alert_rule_data(
            name=f"Rule WF {wf}", downstream_workflow=wf
        )
        form = BiAlertRuleForm(data=data, tenant=tenant_a)
        assert form.is_valid()


@pytest.mark.django_db
def test_alertssubscriptions_forms_alert_rule_edit_existing_instance(
    tenant_a, bi_alert_rule_a
):
    """Verify editing an existing alert rule via form updates fields."""
    data = _alertssubscriptions_forms_valid_alert_rule_data(
        name="Updated Alert Rule Name",
        description="Updated description text",
        threshold_value="9999.5000",
        severity="info",
        status="paused",
    )
    form = BiAlertRuleForm(data=data, instance=bi_alert_rule_a, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    updated = form.save()
    assert updated.pk == bi_alert_rule_a.pk
    assert updated.name == "Updated Alert Rule Name"
    assert updated.threshold_value == Decimal("9999.5000")
    assert updated.severity == "info"
    assert updated.status == "paused"


@pytest.mark.django_db
def test_alertssubscriptions_forms_alert_rule_invalid_webhook_url(tenant_a):
    """Verify malformed webhook_url fails URL field validation."""
    data = _alertssubscriptions_forms_valid_alert_rule_data(
        webhook_url="not-a-valid-url"
    )
    form = BiAlertRuleForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "webhook_url" in form.errors


@pytest.mark.django_db
def test_alertssubscriptions_forms_alert_rule_optional_fields_blank(tenant_a):
    """Verify optional fields can be left blank."""
    data = {
        "name": "Minimal Alert Rule",
        "alert_type": "kpi_threshold",
        "condition_operator": "gt",
        "threshold_value": "100.0000",
        "severity": "warning",
        "evaluation_cadence": "daily",
        "trigger_frequency": "every_time",
        "delivery_channel": "in_app_only",
        "downstream_workflow": "none",
        "status": "active",
        "description": "",
        "notification_email_list": "",
        "webhook_url": "",
    }
    form = BiAlertRuleForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    rule = form.save()
    assert rule.description == ""
    assert rule.webhook_url == ""
    assert rule.kpi_definition is None
    assert rule.anomaly_detection is None


# ===========================================================================
# 2. ReportSubscriptionForm Tests
# ===========================================================================


@pytest.mark.django_db
def test_alertssubscriptions_forms_subscription_system_field_exclusions():
    """Verify system-managed and runtime override fields are excluded from Meta.fields."""
    form = ReportSubscriptionForm()
    system_fields = [
        "tenant",
        "number",
        "last_run_at",
        "next_run_at",
        "run_count",
        "created_at",
        "updated_at",
        "created_by",
        "filter_overrides",
    ]
    for field in system_fields:
        assert field not in form.fields, (
            f"Security violation: {field} exposed in ReportSubscriptionForm"
        )


@pytest.mark.django_db
def test_alertssubscriptions_forms_subscription_valid_creation(tenant_a):
    """Verify valid form data creates a ReportSubscription bound to tenant."""
    data = _alertssubscriptions_forms_valid_subscription_data()
    form = ReportSubscriptionForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    sub = form.save()
    assert sub.pk is not None
    assert sub.tenant == tenant_a
    assert sub.name == "Weekly Monday Executive Digest"
    assert sub.target_asset_type == "dashboard"
    assert sub.export_format == "pdf"
    assert sub.cadence == "weekly"
    assert sub.burst_mode == "broadcast"
    assert sub.include_cover_page is True
    assert sub.skip_if_empty is True
    assert sub.status == "active"


@pytest.mark.django_db
def test_alertssubscriptions_forms_subscription_with_all_relations(
    tenant_a, bi_dashboard_a, admin_user
):
    """Verify form saves with foreign keys and M2M subscriber relations."""
    rep = _alertssubscriptions_forms_create_report(tenant_a, slug="exec-report-a")
    ou = _alertssubscriptions_forms_create_org_unit(tenant_a, "Executive Group")
    data = _alertssubscriptions_forms_valid_subscription_data(
        dashboard=bi_dashboard_a,
        report=rep,
        subscriber_users=[admin_user],
        subscriber_org_units=[ou],
    )
    form = ReportSubscriptionForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    sub = form.save()
    assert sub.dashboard == bi_dashboard_a
    assert sub.report == rep
    assert admin_user in sub.subscriber_users.all()
    assert ou in sub.subscriber_org_units.all()


@pytest.mark.django_db
def test_alertssubscriptions_forms_subscription_required_fields(tenant_a):
    """Verify required fields fail validation when empty payload submitted."""
    form = ReportSubscriptionForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "name" in form.errors


@pytest.mark.django_db
def test_alertssubscriptions_forms_subscription_unscoped_initialization():
    """Verify form initializes safely with tenant=None without raising exceptions."""
    form = ReportSubscriptionForm(tenant=None)
    assert form.fields["name"].required is True
    assert "dashboard" in form.fields
    assert "report" in form.fields
    assert "subscriber_users" in form.fields
    assert "subscriber_org_units" in form.fields


@pytest.mark.django_db
def test_alertssubscriptions_forms_subscription_tenant_scoping_foreign_keys(
    tenant_a,
    tenant_b,
    bi_dashboard_a,
    bi_dashboard_b,
):
    """Verify dashboard and report FK querysets are filtered by tenant in __init__."""
    rep_a = _alertssubscriptions_forms_create_report(tenant_a, slug="rep-a")
    rep_b = _alertssubscriptions_forms_create_report(tenant_b, slug="rep-b")

    form = ReportSubscriptionForm(tenant=tenant_a)

    dash_qs = form.fields["dashboard"].queryset
    assert bi_dashboard_a in dash_qs
    assert bi_dashboard_b not in dash_qs

    rep_qs = form.fields["report"].queryset
    assert rep_a in rep_qs
    assert rep_b not in rep_qs


@pytest.mark.django_db
def test_alertssubscriptions_forms_subscription_tenant_scoping_m2m(
    tenant_a, tenant_b, admin_user, admin_user_b
):
    """Verify subscriber_users and subscriber_org_units M2M querysets are scoped to tenant."""
    ou_a = _alertssubscriptions_forms_create_org_unit(tenant_a, "Dept A")
    ou_b = _alertssubscriptions_forms_create_org_unit(tenant_b, "Dept B")

    form = ReportSubscriptionForm(tenant=tenant_a)

    user_qs = form.fields["subscriber_users"].queryset
    assert admin_user in user_qs
    assert admin_user_b not in user_qs

    ou_qs = form.fields["subscriber_org_units"].queryset
    assert ou_a in ou_qs
    assert ou_b not in ou_qs


@pytest.mark.django_db
def test_alertssubscriptions_forms_subscription_reject_foreign_dashboard(
    tenant_a, bi_dashboard_b
):
    """Verify cross-tenant dashboard assignment is rejected."""
    data = _alertssubscriptions_forms_valid_subscription_data(dashboard=bi_dashboard_b)
    # 1. Standard tenant-filtered form rejects at field validation
    form = ReportSubscriptionForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "dashboard" in form.errors

    # 2. Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = ReportSubscriptionForm(data=data, tenant=tenant_a)
    form_wide.fields["dashboard"].queryset = BiDashboard.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["dashboard"]


@pytest.mark.django_db
def test_alertssubscriptions_forms_subscription_reject_foreign_report(
    tenant_a, tenant_b
):
    """Verify cross-tenant report assignment is rejected."""
    rep_b = _alertssubscriptions_forms_create_report(tenant_b, slug="foreign-rep-b")
    data = _alertssubscriptions_forms_valid_subscription_data(report=rep_b)
    # 1. Standard tenant-filtered form rejects at field validation
    form = ReportSubscriptionForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "report" in form.errors

    # 2. Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = ReportSubscriptionForm(data=data, tenant=tenant_a)
    form_wide.fields["report"].queryset = ReportDefinition.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["report"]


@pytest.mark.django_db
def test_alertssubscriptions_forms_subscription_reject_foreign_subscriber_users(
    tenant_a, admin_user_b
):
    """Verify cross-tenant subscriber user is rejected."""
    data = _alertssubscriptions_forms_valid_subscription_data(
        subscriber_users=[admin_user_b]
    )
    # 1. Standard tenant-filtered form rejects at field validation
    form = ReportSubscriptionForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "subscriber_users" in form.errors

    # 2. Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = ReportSubscriptionForm(data=data, tenant=tenant_a)
    form_wide.fields["subscriber_users"].queryset = User.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors[
        "subscriber_users"
    ]


@pytest.mark.django_db
def test_alertssubscriptions_forms_subscription_reject_foreign_subscriber_org_units(
    tenant_a, tenant_b
):
    """Verify cross-tenant subscriber org unit is rejected."""
    ou_b = _alertssubscriptions_forms_create_org_unit(tenant_b, "Globex Finance")
    data = _alertssubscriptions_forms_valid_subscription_data(
        subscriber_org_units=[ou_b]
    )
    # 1. Standard tenant-filtered form rejects at field validation
    form = ReportSubscriptionForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "subscriber_org_units" in form.errors

    # 2. Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = ReportSubscriptionForm(data=data, tenant=tenant_a)
    form_wide.fields["subscriber_org_units"].queryset = OrgUnit.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors[
        "subscriber_org_units"
    ]


@pytest.mark.django_db
def test_alertssubscriptions_forms_subscription_export_format_choices(tenant_a):
    """Verify export format choices validation."""
    for fmt in ["pdf", "xlsx", "csv", "html_inline"]:
        data = _alertssubscriptions_forms_valid_subscription_data(
            name=f"Sub Format {fmt}", export_format=fmt
        )
        form = ReportSubscriptionForm(data=data, tenant=tenant_a)
        assert form.is_valid(), f"Failed for format {fmt}: {form.errors}"

    data_bad = _alertssubscriptions_forms_valid_subscription_data(
        export_format="invalid_doc"
    )
    form_bad = ReportSubscriptionForm(data=data_bad, tenant=tenant_a)
    assert not form_bad.is_valid()
    assert "export_format" in form_bad.errors


@pytest.mark.django_db
def test_alertssubscriptions_forms_subscription_burst_mode_choices(tenant_a):
    """Verify burst_mode choices validation."""
    for mode in ["broadcast", "slice_by_user", "slice_by_org_unit"]:
        data = _alertssubscriptions_forms_valid_subscription_data(
            name=f"Sub Mode {mode}", burst_mode=mode
        )
        form = ReportSubscriptionForm(data=data, tenant=tenant_a)
        assert form.is_valid(), f"Failed for burst mode {mode}: {form.errors}"


@pytest.mark.django_db
def test_alertssubscriptions_forms_subscription_cadence_and_cron(tenant_a):
    """Verify cadence and cron_expression handling."""
    for cad in ["daily", "weekly", "monthly", "quarterly", "cron"]:
        data = _alertssubscriptions_forms_valid_subscription_data(
            name=f"Sub Cadence {cad}", cadence=cad, cron_expression="30 7 * * 1-5"
        )
        form = ReportSubscriptionForm(data=data, tenant=tenant_a)
        assert form.is_valid(), f"Failed for cadence {cad}: {form.errors}"


@pytest.mark.django_db
def test_alertssubscriptions_forms_subscription_edit_existing_instance(
    tenant_a, report_subscription_a
):
    """Verify updating existing subscription via form."""
    data = _alertssubscriptions_forms_valid_subscription_data(
        name="Updated Subscription Schedule",
        cadence="monthly",
        scheduled_time="09:30",
        export_format="xlsx",
        status="paused",
    )
    form = ReportSubscriptionForm(
        data=data, instance=report_subscription_a, tenant=tenant_a
    )
    assert form.is_valid(), f"Form errors: {form.errors}"
    updated = form.save()
    assert updated.pk == report_subscription_a.pk
    assert updated.name == "Updated Subscription Schedule"
    assert updated.cadence == "monthly"
    assert updated.export_format == "xlsx"
    assert updated.status == "paused"


@pytest.mark.django_db
def test_alertssubscriptions_forms_subscription_boolean_flags_defaults(tenant_a):
    """Verify include_cover_page and skip_if_empty checkboxes behavior."""
    data = _alertssubscriptions_forms_valid_subscription_data()
    data["include_cover_page"] = False
    data["skip_if_empty"] = False
    form = ReportSubscriptionForm(data=data, tenant=tenant_a)
    assert form.is_valid()
    sub = form.save()
    assert sub.include_cover_page is False
    assert sub.skip_if_empty is False


# ===========================================================================
# 3. DistributionBurstRunForm Tests
# ===========================================================================


@pytest.mark.django_db
def test_alertssubscriptions_forms_burst_run_system_field_exclusions():
    """Verify system-managed burst run fields are excluded from Meta.fields."""
    form = DistributionBurstRunForm()
    system_fields = [
        "tenant",
        "number",
        "created_at",
        "updated_at",
        "executed_by",
        "burst_slicing_metadata",
        "started_at",
        "completed_at",
        "delivered_count",
        "failed_count",
        "execution_duration_ms",
    ]
    for field in system_fields:
        assert field not in form.fields, (
            f"Security violation: {field} exposed in DistributionBurstRunForm"
        )


@pytest.mark.django_db
def test_alertssubscriptions_forms_burst_run_valid_creation(tenant_a):
    """Verify valid form data creates a DistributionBurstRun bound to tenant."""
    data = _alertssubscriptions_forms_valid_burst_run_data()
    form = DistributionBurstRunForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    run = form.save()
    assert run.pk is not None
    assert run.tenant == tenant_a
    assert run.run_trigger == "scheduled_subscription"
    assert run.delivery_channel == "email"
    assert run.status == "completed"
    assert run.recipient_count == 12
    assert run.generated_file_name == "Weekly_Exec_Digest_20261108.pdf"
    assert run.file_size_bytes == 1048576


@pytest.mark.django_db
def test_alertssubscriptions_forms_burst_run_with_relations(
    tenant_a, report_subscription_a, bi_alert_rule_a
):
    """Verify form saves with subscription and alert_rule FKs."""
    data = _alertssubscriptions_forms_valid_burst_run_data(
        subscription=report_subscription_a,
        alert_rule=bi_alert_rule_a,
    )
    form = DistributionBurstRunForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    run = form.save()
    assert run.subscription == report_subscription_a
    assert run.alert_rule == bi_alert_rule_a


@pytest.mark.django_db
def test_alertssubscriptions_forms_burst_run_unscoped_initialization():
    """Verify form initializes safely with tenant=None without raising exceptions."""
    form = DistributionBurstRunForm(tenant=None)
    assert "subscription" in form.fields
    assert "alert_rule" in form.fields
    assert "run_trigger" in form.fields


@pytest.mark.django_db
def test_alertssubscriptions_forms_burst_run_tenant_scoping_foreign_keys(
    tenant_a,
    report_subscription_a,
    report_subscription_b,
    bi_alert_rule_a,
    bi_alert_rule_b,
):
    """Verify subscription and alert_rule FK querysets are filtered by tenant."""
    form = DistributionBurstRunForm(tenant=tenant_a)

    sub_qs = form.fields["subscription"].queryset
    assert report_subscription_a in sub_qs
    assert report_subscription_b not in sub_qs

    rule_qs = form.fields["alert_rule"].queryset
    assert bi_alert_rule_a in rule_qs
    assert bi_alert_rule_b not in rule_qs


@pytest.mark.django_db
def test_alertssubscriptions_forms_burst_run_reject_foreign_subscription(
    tenant_a, report_subscription_b
):
    """Verify cross-tenant subscription is rejected."""
    data = _alertssubscriptions_forms_valid_burst_run_data(
        subscription=report_subscription_b
    )
    # 1. Standard tenant-filtered form rejects at field validation
    form = DistributionBurstRunForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "subscription" in form.errors

    # 2. Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = DistributionBurstRunForm(data=data, tenant=tenant_a)
    form_wide.fields["subscription"].queryset = ReportSubscription.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors[
        "subscription"
    ]


@pytest.mark.django_db
def test_alertssubscriptions_forms_burst_run_reject_foreign_alert_rule(
    tenant_a, bi_alert_rule_b
):
    """Verify cross-tenant alert_rule is rejected."""
    data = _alertssubscriptions_forms_valid_burst_run_data(alert_rule=bi_alert_rule_b)
    # 1. Standard tenant-filtered form rejects at field validation
    form = DistributionBurstRunForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "alert_rule" in form.errors

    # 2. Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = DistributionBurstRunForm(data=data, tenant=tenant_a)
    form_wide.fields["alert_rule"].queryset = BiAlertRule.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors[
        "alert_rule"
    ]


@pytest.mark.django_db
def test_alertssubscriptions_forms_burst_run_run_trigger_choices(tenant_a):
    """Verify run_trigger choices validation."""
    for trig in ["scheduled_subscription", "ad_hoc_manual", "alert_triggered"]:
        data = _alertssubscriptions_forms_valid_burst_run_data(run_trigger=trig)
        form = DistributionBurstRunForm(data=data, tenant=tenant_a)
        assert form.is_valid(), f"Failed for trigger {trig}: {form.errors}"

    bad_data = _alertssubscriptions_forms_valid_burst_run_data(
        run_trigger="unsupported_trigger"
    )
    form_bad = DistributionBurstRunForm(data=bad_data, tenant=tenant_a)
    assert not form_bad.is_valid()
    assert "run_trigger" in form_bad.errors


@pytest.mark.django_db
def test_alertssubscriptions_forms_burst_run_delivery_channel_choices(tenant_a):
    """Verify delivery_channel choices validation."""
    for channel in ["email", "sftp", "portal_inbox", "webhook"]:
        data = _alertssubscriptions_forms_valid_burst_run_data(delivery_channel=channel)
        form = DistributionBurstRunForm(data=data, tenant=tenant_a)
        assert form.is_valid(), f"Failed for channel {channel}: {form.errors}"


@pytest.mark.django_db
def test_alertssubscriptions_forms_burst_run_status_choices(tenant_a):
    """Verify status choices validation."""
    for st in ["queued", "processing", "completed", "partial_failure", "failed"]:
        data = _alertssubscriptions_forms_valid_burst_run_data(status=st)
        form = DistributionBurstRunForm(data=data, tenant=tenant_a)
        assert form.is_valid(), f"Failed for status {st}: {form.errors}"


@pytest.mark.django_db
def test_alertssubscriptions_forms_burst_run_optional_foreign_keys(tenant_a):
    """Verify burst run form is valid with both FKs None (optional fields)."""
    data = _alertssubscriptions_forms_valid_burst_run_data(
        subscription=None, alert_rule=None
    )
    form = DistributionBurstRunForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    run = form.save()
    assert run.subscription is None
    assert run.alert_rule is None


@pytest.mark.django_db
def test_alertssubscriptions_forms_burst_run_edit_existing_instance(
    tenant_a, distribution_burst_run_a
):
    """Verify editing existing burst run via form."""
    data = _alertssubscriptions_forms_valid_burst_run_data(
        recipient_count=25,
        status="partial_failure",
        error_summary="3 of 25 mailboxes bounced with recipient not found.",
    )
    form = DistributionBurstRunForm(
        data=data, instance=distribution_burst_run_a, tenant=tenant_a
    )
    assert form.is_valid(), f"Form errors: {form.errors}"
    updated = form.save()
    assert updated.pk == distribution_burst_run_a.pk
    assert updated.recipient_count == 25
    assert updated.status == "partial_failure"
    assert "bounced" in updated.error_summary


# ===========================================================================
# 4. BiNotificationItemForm Tests
# ===========================================================================


@pytest.mark.django_db
def test_alertssubscriptions_forms_notification_system_field_exclusions():
    """Verify system-managed lifecycle fields are excluded from Meta.fields."""
    form = BiNotificationItemForm()
    system_fields = [
        "tenant",
        "number",
        "read_at",
        "acknowledged_at",
        "acknowledged_by",
        "escalation_level",
        "escalated_to",
        "workflow_converted",
        "workflow_reference",
        "created_at",
        "updated_at",
    ]
    for field in system_fields:
        assert field not in form.fields, (
            f"Security violation: {field} exposed in BiNotificationItemForm"
        )


@pytest.mark.django_db
def test_alertssubscriptions_forms_notification_valid_creation(tenant_a, admin_user):
    """Verify valid form data creates a BiNotificationItem bound to tenant."""
    data = _alertssubscriptions_forms_valid_notification_data(recipient=admin_user)
    form = BiNotificationItemForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    item = form.save()
    assert item.pk is not None
    assert item.tenant == tenant_a
    assert item.recipient == admin_user
    assert item.title == "Operating Margin Threshold Tripped"
    assert item.message == "Current margin 12.4% fell below target 15.0%."
    assert item.severity == "critical"
    assert item.category == "kpi_alert"
    assert item.status == "unread"
    assert item.action_url == "/bi/dashboards/1/"


@pytest.mark.django_db
def test_alertssubscriptions_forms_notification_with_relations(
    tenant_a, admin_user, bi_alert_rule_a, distribution_burst_run_a
):
    """Verify form saves with alert_rule and burst_run FK relations."""
    data = _alertssubscriptions_forms_valid_notification_data(
        recipient=admin_user,
        alert_rule=bi_alert_rule_a,
        burst_run=distribution_burst_run_a,
    )
    form = BiNotificationItemForm(data=data, tenant=tenant_a)
    assert form.is_valid(), f"Form errors: {form.errors}"
    item = form.save()
    assert item.alert_rule == bi_alert_rule_a
    assert item.burst_run == distribution_burst_run_a


@pytest.mark.django_db
def test_alertssubscriptions_forms_notification_required_fields(tenant_a):
    """Verify required fields fail validation when empty payload submitted."""
    form = BiNotificationItemForm(data={}, tenant=tenant_a)
    assert not form.is_valid()
    assert "recipient" in form.errors
    assert "title" in form.errors
    assert "message" in form.errors


@pytest.mark.django_db
def test_alertssubscriptions_forms_notification_unscoped_initialization():
    """Verify form initializes safely with tenant=None without raising exceptions."""
    form = BiNotificationItemForm(tenant=None)
    assert form.fields["recipient"].required is True
    assert form.fields["title"].required is True
    assert form.fields["message"].required is True
    assert "alert_rule" in form.fields
    assert "burst_run" in form.fields


@pytest.mark.django_db
def test_alertssubscriptions_forms_notification_tenant_scoping_recipient(
    tenant_a, admin_user, admin_user_b
):
    """Verify recipient user queryset is filtered to tenant users."""
    form = BiNotificationItemForm(tenant=tenant_a)
    recip_qs = form.fields["recipient"].queryset
    assert admin_user in recip_qs
    assert admin_user_b not in recip_qs


@pytest.mark.django_db
def test_alertssubscriptions_forms_notification_tenant_scoping_relations(
    tenant_a,
    bi_alert_rule_a,
    bi_alert_rule_b,
    distribution_burst_run_a,
    distribution_burst_run_b,
):
    """Verify alert_rule and burst_run FK querysets are filtered to tenant records."""
    form = BiNotificationItemForm(tenant=tenant_a)

    rule_qs = form.fields["alert_rule"].queryset
    assert bi_alert_rule_a in rule_qs
    assert bi_alert_rule_b not in rule_qs

    burst_qs = form.fields["burst_run"].queryset
    assert distribution_burst_run_a in burst_qs
    assert distribution_burst_run_b not in burst_qs


@pytest.mark.django_db
def test_alertssubscriptions_forms_notification_reject_foreign_recipient(
    tenant_a, admin_user_b
):
    """Verify cross-tenant recipient user is rejected."""
    data = _alertssubscriptions_forms_valid_notification_data(recipient=admin_user_b)
    # 1. Standard tenant-filtered form rejects at field validation
    form = BiNotificationItemForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "recipient" in form.errors

    # 2. Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = BiNotificationItemForm(data=data, tenant=tenant_a)
    form_wide.fields["recipient"].queryset = User.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["recipient"]


@pytest.mark.django_db
def test_alertssubscriptions_forms_notification_reject_foreign_alert_rule(
    tenant_a, admin_user, bi_alert_rule_b
):
    """Verify cross-tenant alert_rule is rejected."""
    data = _alertssubscriptions_forms_valid_notification_data(
        recipient=admin_user, alert_rule=bi_alert_rule_b
    )
    # 1. Standard tenant-filtered form rejects at field validation
    form = BiNotificationItemForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "alert_rule" in form.errors

    # 2. Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = BiNotificationItemForm(data=data, tenant=tenant_a)
    form_wide.fields["alert_rule"].queryset = BiAlertRule.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors[
        "alert_rule"
    ]


@pytest.mark.django_db
def test_alertssubscriptions_forms_notification_reject_foreign_burst_run(
    tenant_a, admin_user, distribution_burst_run_b
):
    """Verify cross-tenant burst_run is rejected."""
    data = _alertssubscriptions_forms_valid_notification_data(
        recipient=admin_user, burst_run=distribution_burst_run_b
    )
    # 1. Standard tenant-filtered form rejects at field validation
    form = BiNotificationItemForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "burst_run" in form.errors

    # 2. Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = BiNotificationItemForm(data=data, tenant=tenant_a)
    form_wide.fields["burst_run"].queryset = DistributionBurstRun.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors[
        "burst_run"
    ]


@pytest.mark.django_db
def test_alertssubscriptions_forms_notification_clean_action_url_valid_relative(
    tenant_a, admin_user
):
    """Verify clean_action_url accepts valid relative URLs starting with /."""
    valid_paths = [
        "/bi/dashboards/1/",
        "/bi/reports/monthly-close/",
        "/bi/scorecards/kpi/25/",
        "/core/notifications/",
    ]
    for path in valid_paths:
        data = _alertssubscriptions_forms_valid_notification_data(
            recipient=admin_user, action_url=path
        )
        form = BiNotificationItemForm(data=data, tenant=tenant_a)
        assert form.is_valid(), f"Failed for valid path {path}: {form.errors}"
        assert form.cleaned_data["action_url"] == path


@pytest.mark.django_db
def test_alertssubscriptions_forms_notification_clean_action_url_valid_http_https(
    tenant_a, admin_user
):
    """Verify clean_action_url accepts absolute HTTP and HTTPS URLs."""
    valid_urls = [
        "https://bi.example.com/reports/42",
        "http://internal-analytics.local/dashboards/exec",
        "https://analytics.enterprise.org:8443/view?id=123",
    ]
    for url in valid_urls:
        data = _alertssubscriptions_forms_valid_notification_data(
            recipient=admin_user, action_url=url
        )
        form = BiNotificationItemForm(data=data, tenant=tenant_a)
        assert form.is_valid(), f"Failed for valid URL {url}: {form.errors}"
        assert form.cleaned_data["action_url"] == url


@pytest.mark.django_db
def test_alertssubscriptions_forms_notification_clean_action_url_empty_or_whitespace(
    tenant_a, admin_user
):
    """Verify clean_action_url returns empty string for blank or whitespace inputs."""
    for empty_val in ["", "   ", None]:
        data = _alertssubscriptions_forms_valid_notification_data(
            recipient=admin_user, action_url=empty_val
        )
        form = BiNotificationItemForm(data=data, tenant=tenant_a)
        assert form.is_valid(), f"Failed for empty value {empty_val}: {form.errors}"
        assert form.cleaned_data["action_url"] == ""


@pytest.mark.django_db
def test_alertssubscriptions_forms_notification_clean_action_url_reject_javascript_schemes(
    tenant_a, admin_user
):
    """Verify clean_action_url rejects javascript: scheme payloads."""
    xss_payloads = [
        "javascript:alert(1)",
        "javascript:alert(document.cookie)",
        "javascript:void(0)",
    ]
    for payload in xss_payloads:
        data = _alertssubscriptions_forms_valid_notification_data(
            recipient=admin_user, action_url=payload
        )
        form = BiNotificationItemForm(data=data, tenant=tenant_a)
        assert not form.is_valid(), f"Did not reject javascript payload: {payload}"
        assert "action_url" in form.errors
        assert (
            "Action URL must be a relative path" in form.errors["action_url"][0]
        )


@pytest.mark.django_db
def test_alertssubscriptions_forms_notification_clean_action_url_reject_data_schemes(
    tenant_a, admin_user
):
    """Verify clean_action_url rejects data: URI schemes."""
    data_payloads = [
        "data:text/html,<script>alert(1)</script>",
        "data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==",
    ]
    for payload in data_payloads:
        data = _alertssubscriptions_forms_valid_notification_data(
            recipient=admin_user, action_url=payload
        )
        form = BiNotificationItemForm(data=data, tenant=tenant_a)
        assert not form.is_valid(), f"Did not reject data URI payload: {payload}"
        assert "action_url" in form.errors


@pytest.mark.django_db
def test_alertssubscriptions_forms_notification_clean_action_url_reject_vbscript_schemes(
    tenant_a, admin_user
):
    """Verify clean_action_url rejects vbscript: schemes."""
    vb_payload = "vbscript:msgbox(1)"
    data = _alertssubscriptions_forms_valid_notification_data(
        recipient=admin_user, action_url=vb_payload
    )
    form = BiNotificationItemForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "action_url" in form.errors


@pytest.mark.django_db
def test_alertssubscriptions_forms_notification_clean_action_url_reject_other_schemes(
    tenant_a, admin_user
):
    """Verify clean_action_url rejects other non-HTTP schemes (ftp, file)."""
    bad_urls = [
        "ftp://ftp.example.com/file.pdf",
        "file:///etc/passwd",
        "gopher://gopher.example.com",
    ]
    for url in bad_urls:
        data = _alertssubscriptions_forms_valid_notification_data(
            recipient=admin_user, action_url=url
        )
        form = BiNotificationItemForm(data=data, tenant=tenant_a)
        assert not form.is_valid(), f"Did not reject scheme: {url}"
        assert "action_url" in form.errors


@pytest.mark.django_db
def test_alertssubscriptions_forms_notification_clean_action_url_reject_relative_without_leading_slash(
    tenant_a, admin_user
):
    """Verify clean_action_url rejects relative paths that do not start with /."""
    invalid_relative = [
        "bi/dashboards/1/",
        "reports/monthly-close",
        "view?id=10",
    ]
    for url in invalid_relative:
        data = _alertssubscriptions_forms_valid_notification_data(
            recipient=admin_user, action_url=url
        )
        form = BiNotificationItemForm(data=data, tenant=tenant_a)
        assert not form.is_valid(), (
            f"Did not reject relative path without slash: {url}"
        )
        assert "action_url" in form.errors


@pytest.mark.django_db
def test_alertssubscriptions_forms_notification_severity_and_category_choices(
    tenant_a, admin_user
):
    """Verify severity and category choices validation."""
    for sev in ["info", "warning", "critical"]:
        data = _alertssubscriptions_forms_valid_notification_data(
            recipient=admin_user, title=f"Notif {sev}", severity=sev
        )
        form = BiNotificationItemForm(data=data, tenant=tenant_a)
        assert form.is_valid()

    for cat in [
        "kpi_alert",
        "anomaly_alert",
        "subscription_digest",
        "workflow_task",
        "system_bulletin",
    ]:
        data = _alertssubscriptions_forms_valid_notification_data(
            recipient=admin_user, title=f"Notif {cat}", category=cat
        )
        form = BiNotificationItemForm(data=data, tenant=tenant_a)
        assert form.is_valid()


@pytest.mark.django_db
def test_alertssubscriptions_forms_notification_status_choices(
    tenant_a, admin_user
):
    """Verify status choices validation."""
    for st in [
        "unread",
        "read",
        "acknowledged",
        "snoozed",
        "escalated",
        "dismissed",
    ]:
        data = _alertssubscriptions_forms_valid_notification_data(
            recipient=admin_user, title=f"Notif Status {st}", status=st
        )
        form = BiNotificationItemForm(data=data, tenant=tenant_a)
        assert form.is_valid(), f"Failed for status {st}: {form.errors}"


@pytest.mark.django_db
def test_alertssubscriptions_forms_notification_edit_existing_instance(
    tenant_a, bi_notification_item_a, admin_user
):
    """Verify editing existing notification via form."""
    data = _alertssubscriptions_forms_valid_notification_data(
        recipient=admin_user,
        title="Updated Notification Title",
        status="acknowledged",
        acknowledgment_notes="Resolved in incident post-mortem #412.",
    )
    form = BiNotificationItemForm(
        data=data, instance=bi_notification_item_a, tenant=tenant_a
    )
    assert form.is_valid(), f"Form errors: {form.errors}"
    updated = form.save()
    assert updated.pk == bi_notification_item_a.pk
    assert updated.title == "Updated Notification Title"
    assert updated.status == "acknowledged"
    assert "post-mortem" in updated.acknowledgment_notes
