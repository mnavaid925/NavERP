"""Security, Multi-Tenancy, Authorization, and RBAC Test Suite for Sub-module 10.16:
Alerts, Subscriptions & Distribution (apps/bi).

Covers:
1. Multi-Tenant Isolation (IDOR):
   - Tenant A client accessing Tenant B's objects across all object endpoints returns 404:
     - BiAlertRule: detail, edit (GET/POST), delete (POST), test_evaluate (POST)
     - ReportSubscription: detail, edit (GET/POST), delete (POST), run_now (POST)
     - DistributionBurstRun: detail, edit (GET/POST), delete (POST)
     - BiNotificationItem: detail, edit (GET/POST), delete (POST), mark_read (POST), acknowledge (POST), snooze (POST), escalate (POST)
   - Reverse IDOR: Tenant B client accessing Tenant A's objects returns 404 across all endpoints.
   - List views and workspaces strictly filter by tenant (no data leakage):
     - bi_alert_rule_list
     - report_subscription_list
     - distribution_burst_run_list
     - bi_notification_item_list
     - notification_center workspace

2. Cross-Tenant Injection in Forms:
   - BiAlertRuleForm rejects Tenant B foreign keys & M2Ms (kpi_definition, anomaly_detection, recipient_users).
   - ReportSubscriptionForm rejects Tenant B foreign keys & M2Ms (dashboard, report, subscriber_org_units, subscriber_users).
   - DistributionBurstRunForm rejects Tenant B foreign keys (subscription, alert_rule).
   - BiNotificationItemForm rejects Tenant B foreign keys (recipient, alert_rule, burst_run).
   - Defense-in-depth: widened queryset triggers reject_foreign.

3. Open Redirect Defense:
   - Malicious next URLs (https://malicious.com, //evil.com, javascript:alert(1), \\evil.com) submitted to:
     - notification_mark_read
     - notification_acknowledge
     - notification_snooze
     - notification_escalate
     safely fall back to the internal default (bi:notification_center).
   - Safe internal relative next parameters are honored.

4. Stored XSS Defense on action_url:
   - Malicious payloads (javascript:alert(document.cookie), data:text/html,..., vbscript:..., ftp://...) in BiNotificationItemForm action_url are rejected by clean_action_url.
   - Valid relative and http/https URLs are accepted.

5. Hand-Parsed Numeric/Integer Hardening:
   - notification_snooze handles non-numeric, negative, huge/overflowing, empty, and out-of-range hours gracefully without 500 errors.

6. Privilege Separation & AuthN/AuthZ:
   - All endpoints require authentication (@login_required) and redirect anonymous users to login (302).
   - Deletions require tenant admin (@tenant_admin_required): non-admin member_client receives 403 Forbidden.
   - Mutation actions enforce @require_POST (GET returns 405 Method Not Allowed).

7. Audit Log Verification:
   - Verified that AuditLog records are generated with correct tenant, user, action, and object metadata on creation, update, deletion, evaluation, execution, acknowledgment, snooze, and escalation.
"""

from datetime import timedelta
from decimal import Decimal
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from django.utils import timezone

from apps.bi.forms.AlertsSubscriptions.BiAlertRules import BiAlertRuleForm
from apps.bi.forms.AlertsSubscriptions.BiNotificationItems import (
    BiNotificationItemForm,
)
from apps.bi.forms.AlertsSubscriptions.DistributionBurstRuns import (
    DistributionBurstRunForm,
)
from apps.bi.forms.AlertsSubscriptions.ReportSubscriptions import (
    ReportSubscriptionForm,
)
from apps.bi.models.AlertsSubscriptions.BiAlertRules import BiAlertRule
from apps.bi.models.AlertsSubscriptions.BiNotificationItems import (
    BiNotificationItem,
)
from apps.bi.models.AlertsSubscriptions.DistributionBurstRuns import (
    DistributionBurstRun,
)
from apps.bi.models.AlertsSubscriptions.ReportSubscriptions import (
    ReportSubscription,
)
from apps.bi.models.Dashboards.BiDashboards import BiDashboard
from apps.bi.models.OperationalReporting.ReportDefinitions import ReportDefinition
from apps.bi.models.PerformanceScorecards.KpiDefinitions import KpiDefinition
from apps.bi.models.PredictiveAnalytics.StatisticalAnomalies import (
    StatisticalAnomaly,
)
from apps.core.models import AuditLog, OrgUnit

User = get_user_model()
pytestmark = pytest.mark.django_db


# ==============================================================================
# Module Helpers (strictly prefixed with _alertssubscriptions_)
# ==============================================================================


def _alertssubscriptions_security_create_alert_rule(tenant, user=None, **kwargs):
    """Helper to create a tenant-scoped BiAlertRule."""
    uid = uuid.uuid4().hex[:6].upper()
    defaults = {
        "tenant": tenant,
        "number": f"BALR-SEC-{uid}",
        "name": f"Security Alert Rule {uid}",
        "alert_type": "kpi_threshold",
        "condition_operator": "gt",
        "threshold_value": Decimal("100.0000"),
        "severity": "critical",
        "evaluation_cadence": "hourly",
        "trigger_frequency": "every_time",
        "delivery_channel": "in_app_email",
        "status": "active",
        "created_by": user,
    }
    defaults.update(kwargs)
    rule = BiAlertRule.objects.create(**defaults)
    if user:
        rule.recipient_users.add(user)
    return rule


def _alertssubscriptions_security_create_subscription(
    tenant, dashboard=None, report=None, user=None, **kwargs
):
    """Helper to create a tenant-scoped ReportSubscription."""
    uid = uuid.uuid4().hex[:6].upper()
    defaults = {
        "tenant": tenant,
        "number": f"BSUB-SEC-{uid}",
        "name": f"Security Subscription {uid}",
        "target_asset_type": "dashboard" if dashboard else ("report" if report else "dashboard"),
        "dashboard": dashboard,
        "report": report,
        "export_format": "pdf",
        "cadence": "weekly",
        "burst_mode": "broadcast",
        "status": "active",
        "created_by": user,
    }
    defaults.update(kwargs)
    sub = ReportSubscription.objects.create(**defaults)
    if user:
        sub.subscriber_users.add(user)
    return sub


def _alertssubscriptions_security_create_burst_run(
    tenant, subscription=None, alert_rule=None, user=None, **kwargs
):
    """Helper to create a tenant-scoped DistributionBurstRun."""
    uid = uuid.uuid4().hex[:6].upper()
    defaults = {
        "tenant": tenant,
        "number": f"BBRS-SEC-{uid}",
        "subscription": subscription,
        "alert_rule": alert_rule,
        "run_trigger": "scheduled_subscription" if subscription else "alert_event",
        "delivery_channel": "email",
        "recipient_count": 5,
        "delivered_count": 5,
        "failed_count": 0,
        "status": "completed",
        "executed_by": user,
    }
    defaults.update(kwargs)
    return DistributionBurstRun.objects.create(**defaults)


def _alertssubscriptions_security_create_notification(
    tenant, user=None, alert_rule=None, burst_run=None, **kwargs
):
    """Helper to create a tenant-scoped BiNotificationItem."""
    uid = uuid.uuid4().hex[:6].upper()
    defaults = {
        "tenant": tenant,
        "number": f"BNTF-SEC-{uid}",
        "title": f"Security Notification {uid}",
        "message": "Automated security alert message.",
        "severity": "critical",
        "category": "kpi_alert",
        "alert_rule": alert_rule,
        "burst_run": burst_run,
        "recipient": user,
        "status": "unread",
    }
    defaults.update(kwargs)
    return BiNotificationItem.objects.create(**defaults)


def _alertssubscriptions_security_create_org_unit(tenant, name="Security Department"):
    """Helper to create a tenant-scoped OrgUnit."""
    return OrgUnit.objects.create(tenant=tenant, name=name, kind="department")


def _alertssubscriptions_security_create_report(
    tenant, name="Security Operational Report", slug=None
):
    """Helper to create a tenant-scoped ReportDefinition record."""
    slug_val = slug or f"sec-rep-{uuid.uuid4().hex[:6]}"
    return ReportDefinition.objects.create(
        tenant=tenant,
        name=name,
        slug=slug_val,
        category="finance",
        report_type="standard_tabular",
        status="published",
    )


# ==============================================================================
# 1. Multi-Tenant Isolation (IDOR) Tests
# ==============================================================================


def test_alertssubscriptions_security_alert_rule_idor_returns_404(
    client_a, bi_alert_rule_b
):
    """Assert Tenant A client receives 404 for all Tenant B BiAlertRule endpoints."""
    pk = bi_alert_rule_b.pk
    urls_and_methods = [
        ("GET", reverse("bi:bi_alert_rule_detail", kwargs={"pk": pk}), {}),
        ("GET", reverse("bi:bi_alert_rule_edit", kwargs={"pk": pk}), {}),
        (
            "POST",
            reverse("bi:bi_alert_rule_edit", kwargs={"pk": pk}),
            {"name": "Tampered Alert Rule Name"},
        ),
        ("POST", reverse("bi:bi_alert_rule_delete", kwargs={"pk": pk}), {}),
        ("POST", reverse("bi:bi_alert_rule_test_evaluate", kwargs={"pk": pk}), {}),
        # Also test short aliases
        ("GET", reverse("bi:alert_rule_detail", kwargs={"pk": pk}), {}),
        ("GET", reverse("bi:alert_rule_edit", kwargs={"pk": pk}), {}),
        ("POST", reverse("bi:alert_rule_delete", kwargs={"pk": pk}), {}),
        ("POST", reverse("bi:alert_rule_test_evaluate", kwargs={"pk": pk}), {}),
    ]

    for method, url, data in urls_and_methods:
        resp = client_a.get(url) if method == "GET" else client_a.post(url, data=data)
        assert resp.status_code == 404, f"Expected 404 for {method} {url}, got {resp.status_code}"


def test_alertssubscriptions_security_subscription_idor_returns_404(
    client_a, report_subscription_b
):
    """Assert Tenant A client receives 404 for all Tenant B ReportSubscription endpoints."""
    pk = report_subscription_b.pk
    urls_and_methods = [
        ("GET", reverse("bi:report_subscription_detail", kwargs={"pk": pk}), {}),
        ("GET", reverse("bi:report_subscription_edit", kwargs={"pk": pk}), {}),
        (
            "POST",
            reverse("bi:report_subscription_edit", kwargs={"pk": pk}),
            {"name": "Tampered Subscription Name"},
        ),
        ("POST", reverse("bi:report_subscription_delete", kwargs={"pk": pk}), {}),
        ("POST", reverse("bi:report_subscription_run_now", kwargs={"pk": pk}), {}),
    ]

    for method, url, data in urls_and_methods:
        resp = client_a.get(url) if method == "GET" else client_a.post(url, data=data)
        assert resp.status_code == 404, f"Expected 404 for {method} {url}, got {resp.status_code}"


def test_alertssubscriptions_security_burst_run_idor_returns_404(
    client_a, distribution_burst_run_b
):
    """Assert Tenant A client receives 404 for all Tenant B DistributionBurstRun endpoints."""
    pk = distribution_burst_run_b.pk
    urls_and_methods = [
        ("GET", reverse("bi:distribution_burst_run_detail", kwargs={"pk": pk}), {}),
        ("GET", reverse("bi:distribution_burst_run_edit", kwargs={"pk": pk}), {}),
        (
            "POST",
            reverse("bi:distribution_burst_run_edit", kwargs={"pk": pk}),
            {"generated_file_name": "tampered.pdf"},
        ),
        ("POST", reverse("bi:distribution_burst_run_delete", kwargs={"pk": pk}), {}),
    ]

    for method, url, data in urls_and_methods:
        resp = client_a.get(url) if method == "GET" else client_a.post(url, data=data)
        assert resp.status_code == 404, f"Expected 404 for {method} {url}, got {resp.status_code}"


def test_alertssubscriptions_security_notification_idor_returns_404(
    client_a, bi_notification_item_b
):
    """Assert Tenant A client receives 404 for all Tenant B BiNotificationItem endpoints."""
    pk = bi_notification_item_b.pk
    urls_and_methods = [
        ("GET", reverse("bi:bi_notification_item_detail", kwargs={"pk": pk}), {}),
        ("GET", reverse("bi:bi_notification_item_edit", kwargs={"pk": pk}), {}),
        (
            "POST",
            reverse("bi:bi_notification_item_edit", kwargs={"pk": pk}),
            {"title": "Tampered Notification Title"},
        ),
        ("POST", reverse("bi:bi_notification_item_delete", kwargs={"pk": pk}), {}),
        ("POST", reverse("bi:notification_mark_read", kwargs={"pk": pk}), {}),
        (
            "POST",
            reverse("bi:notification_acknowledge", kwargs={"pk": pk}),
            {"notes": "Malicious ack"},
        ),
        ("POST", reverse("bi:notification_snooze", kwargs={"pk": pk}), {"hours": 4}),
        ("POST", reverse("bi:notification_escalate", kwargs={"pk": pk}), {}),
        # Also test short aliases
        ("GET", reverse("bi:notification_item_detail", kwargs={"pk": pk}), {}),
        ("GET", reverse("bi:notification_item_edit", kwargs={"pk": pk}), {}),
        ("POST", reverse("bi:notification_item_delete", kwargs={"pk": pk}), {}),
    ]

    for method, url, data in urls_and_methods:
        resp = client_a.get(url) if method == "GET" else client_a.post(url, data=data)
        assert resp.status_code == 404, f"Expected 404 for {method} {url}, got {resp.status_code}"


def test_alertssubscriptions_security_reverse_idor_tenant_b_on_tenant_a_returns_404(
    client_b,
    bi_alert_rule_a,
    report_subscription_a,
    distribution_burst_run_a,
    bi_notification_item_a,
):
    """Assert Tenant B client receives 404 for all Tenant A endpoints (reverse IDOR)."""
    reverse_targets = [
        # BiAlertRule
        ("GET", reverse("bi:bi_alert_rule_detail", kwargs={"pk": bi_alert_rule_a.pk}), {}),
        ("GET", reverse("bi:bi_alert_rule_edit", kwargs={"pk": bi_alert_rule_a.pk}), {}),
        ("POST", reverse("bi:bi_alert_rule_delete", kwargs={"pk": bi_alert_rule_a.pk}), {}),
        ("POST", reverse("bi:bi_alert_rule_test_evaluate", kwargs={"pk": bi_alert_rule_a.pk}), {}),
        # ReportSubscription
        ("GET", reverse("bi:report_subscription_detail", kwargs={"pk": report_subscription_a.pk}), {}),
        ("GET", reverse("bi:report_subscription_edit", kwargs={"pk": report_subscription_a.pk}), {}),
        ("POST", reverse("bi:report_subscription_delete", kwargs={"pk": report_subscription_a.pk}), {}),
        ("POST", reverse("bi:report_subscription_run_now", kwargs={"pk": report_subscription_a.pk}), {}),
        # DistributionBurstRun
        ("GET", reverse("bi:distribution_burst_run_detail", kwargs={"pk": distribution_burst_run_a.pk}), {}),
        ("GET", reverse("bi:distribution_burst_run_edit", kwargs={"pk": distribution_burst_run_a.pk}), {}),
        ("POST", reverse("bi:distribution_burst_run_delete", kwargs={"pk": distribution_burst_run_a.pk}), {}),
        # BiNotificationItem
        ("GET", reverse("bi:bi_notification_item_detail", kwargs={"pk": bi_notification_item_a.pk}), {}),
        ("GET", reverse("bi:bi_notification_item_edit", kwargs={"pk": bi_notification_item_a.pk}), {}),
        ("POST", reverse("bi:bi_notification_item_delete", kwargs={"pk": bi_notification_item_a.pk}), {}),
        ("POST", reverse("bi:notification_mark_read", kwargs={"pk": bi_notification_item_a.pk}), {}),
        ("POST", reverse("bi:notification_acknowledge", kwargs={"pk": bi_notification_item_a.pk}), {"notes": "x"}),
        ("POST", reverse("bi:notification_snooze", kwargs={"pk": bi_notification_item_a.pk}), {"hours": 4}),
        ("POST", reverse("bi:notification_escalate", kwargs={"pk": bi_notification_item_a.pk}), {}),
    ]

    for method, url, data in reverse_targets:
        resp = client_b.get(url) if method == "GET" else client_b.post(url, data=data)
        assert resp.status_code == 404, f"Reverse IDOR vulnerability: Client B {method} {url} returned {resp.status_code}"


def test_alertssubscriptions_security_list_views_tenant_isolation(
    client_a,
    client_b,
    bi_alert_rule_a,
    bi_alert_rule_b,
    report_subscription_a,
    report_subscription_b,
    distribution_burst_run_a,
    distribution_burst_run_b,
    bi_notification_item_a,
    bi_notification_item_b,
):
    """Assert list views and notification center only display records belonging to active tenant."""
    # 1. BiAlertRule list
    resp_a = client_a.get(reverse("bi:bi_alert_rule_list"))
    assert resp_a.status_code == 200
    assert bi_alert_rule_a.name.encode() in resp_a.content
    assert bi_alert_rule_b.name.encode() not in resp_a.content

    resp_b = client_b.get(reverse("bi:bi_alert_rule_list"))
    assert resp_b.status_code == 200
    assert bi_alert_rule_b.name.encode() in resp_b.content
    assert bi_alert_rule_a.name.encode() not in resp_b.content

    # 2. ReportSubscription list
    resp_sub_a = client_a.get(reverse("bi:report_subscription_list"))
    assert resp_sub_a.status_code == 200
    assert report_subscription_a.name.encode() in resp_sub_a.content
    assert report_subscription_b.name.encode() not in resp_sub_a.content

    resp_sub_b = client_b.get(reverse("bi:report_subscription_list"))
    assert resp_sub_b.status_code == 200
    assert report_subscription_b.name.encode() in resp_sub_b.content
    assert report_subscription_a.name.encode() not in resp_sub_b.content

    # 3. DistributionBurstRun list
    resp_run_a = client_a.get(reverse("bi:distribution_burst_run_list"))
    assert resp_run_a.status_code == 200
    assert distribution_burst_run_a.number.encode() in resp_run_a.content
    assert distribution_burst_run_b.number.encode() not in resp_run_a.content

    resp_run_b = client_b.get(reverse("bi:distribution_burst_run_list"))
    assert resp_run_b.status_code == 200
    assert distribution_burst_run_b.number.encode() in resp_run_b.content
    assert distribution_burst_run_a.number.encode() not in resp_run_b.content

    # 4. BiNotificationItem list
    resp_notif_a = client_a.get(reverse("bi:bi_notification_item_list"))
    assert resp_notif_a.status_code == 200
    assert bi_notification_item_a.title.encode() in resp_notif_a.content
    assert bi_notification_item_b.title.encode() not in resp_notif_a.content

    resp_notif_b = client_b.get(reverse("bi:bi_notification_item_list"))
    assert resp_notif_b.status_code == 200
    assert bi_notification_item_b.title.encode() in resp_notif_b.content
    assert bi_notification_item_a.title.encode() not in resp_notif_b.content

    # 5. Notification center workspace
    resp_center_a = client_a.get(reverse("bi:notification_center"))
    assert resp_center_a.status_code == 200
    assert bi_notification_item_a.title.encode() in resp_center_a.content
    assert bi_notification_item_b.title.encode() not in resp_center_a.content


# ==============================================================================
# 2. Cross-Tenant Injection in Forms
# ==============================================================================


def test_alertssubscriptions_security_form_alert_rule_reject_cross_tenant_kpi(
    tenant_a, kpi_definition_b
):
    """Verify BiAlertRuleForm rejects a KPI definition belonging to Tenant B."""
    data = {
        "name": "Sec Rule Invalid KPI",
        "alert_type": "kpi_threshold",
        "condition_operator": "gt",
        "threshold_value": "100.0000",
        "severity": "critical",
        "evaluation_cadence": "hourly",
        "trigger_frequency": "every_time",
        "delivery_channel": "in_app_only",
        "downstream_workflow": "none",
        "status": "active",
        "kpi_definition": kpi_definition_b.pk,
    }
    # Form with tenant_a
    form = BiAlertRuleForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "kpi_definition" in form.errors

    # Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = BiAlertRuleForm(data=data, tenant=tenant_a)
    form_wide.fields["kpi_definition"].queryset = KpiDefinition.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["kpi_definition"]


def test_alertssubscriptions_security_form_alert_rule_reject_cross_tenant_anomaly(
    tenant_a, statistical_anomaly_b
):
    """Verify BiAlertRuleForm rejects an anomaly detection belonging to Tenant B."""
    data = {
        "name": "Sec Rule Invalid Anomaly",
        "alert_type": "statistical_anomaly",
        "condition_operator": "anomaly_flagged",
        "threshold_value": "0.0000",
        "severity": "high",
        "evaluation_cadence": "hourly",
        "trigger_frequency": "every_time",
        "delivery_channel": "in_app_only",
        "downstream_workflow": "none",
        "status": "active",
        "anomaly_detection": statistical_anomaly_b.pk,
    }
    form = BiAlertRuleForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "anomaly_detection" in form.errors

    # Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = BiAlertRuleForm(data=data, tenant=tenant_a)
    form_wide.fields["anomaly_detection"].queryset = StatisticalAnomaly.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["anomaly_detection"]


def test_alertssubscriptions_security_form_alert_rule_reject_cross_tenant_recipient_users(
    tenant_a, admin_user_b
):
    """Verify BiAlertRuleForm rejects recipient users belonging to Tenant B."""
    data = {
        "name": "Sec Rule Invalid Users",
        "alert_type": "kpi_threshold",
        "condition_operator": "gt",
        "threshold_value": "50.0000",
        "severity": "medium",
        "evaluation_cadence": "daily",
        "trigger_frequency": "every_time",
        "delivery_channel": "in_app_only",
        "downstream_workflow": "none",
        "status": "active",
        "recipient_users": [admin_user_b.pk],
    }
    form = BiAlertRuleForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "recipient_users" in form.errors

    # Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = BiAlertRuleForm(data=data, tenant=tenant_a)
    form_wide.fields["recipient_users"].queryset = User.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["recipient_users"]


def test_alertssubscriptions_security_form_subscription_reject_cross_tenant_dashboard(
    tenant_a, bi_dashboard_b
):
    """Verify ReportSubscriptionForm rejects a dashboard from Tenant B."""
    data = {
        "name": "Sec Sub Invalid Dashboard",
        "target_asset_type": "dashboard",
        "dashboard": bi_dashboard_b.pk,
        "cadence": "weekly",
        "scheduled_time": "08:00",
        "export_format": "pdf",
        "burst_mode": "broadcast",
        "status": "active",
    }
    form = ReportSubscriptionForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "dashboard" in form.errors

    # Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = ReportSubscriptionForm(data=data, tenant=tenant_a)
    form_wide.fields["dashboard"].queryset = BiDashboard.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["dashboard"]


def test_alertssubscriptions_security_form_subscription_reject_cross_tenant_report(
    tenant_a, tenant_b
):
    """Verify ReportSubscriptionForm rejects a report from Tenant B."""
    report_b = _alertssubscriptions_security_create_report(tenant_b, slug="sec-rep-b")
    data = {
        "name": "Sec Sub Invalid Report",
        "target_asset_type": "report",
        "report": report_b.pk,
        "cadence": "monthly",
        "export_format": "xlsx",
        "burst_mode": "broadcast",
        "status": "active",
    }
    form = ReportSubscriptionForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "report" in form.errors

    # Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = ReportSubscriptionForm(data=data, tenant=tenant_a)
    form_wide.fields["report"].queryset = ReportDefinition.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["report"]


def test_alertssubscriptions_security_form_subscription_reject_cross_tenant_org_units(
    tenant_a, tenant_b, bi_dashboard_a
):
    """Verify ReportSubscriptionForm rejects subscriber org units from Tenant B."""
    foreign_org = _alertssubscriptions_security_create_org_unit(
        tenant_b, name="Foreign Branch"
    )
    data = {
        "name": "Sec Sub Invalid Org Unit",
        "target_asset_type": "dashboard",
        "dashboard": bi_dashboard_a.pk,
        "cadence": "daily",
        "export_format": "pdf",
        "burst_mode": "broadcast",
        "status": "active",
        "subscriber_org_units": [foreign_org.pk],
    }
    form = ReportSubscriptionForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "subscriber_org_units" in form.errors

    # Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = ReportSubscriptionForm(data=data, tenant=tenant_a)
    form_wide.fields["subscriber_org_units"].queryset = OrgUnit.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["subscriber_org_units"]


def test_alertssubscriptions_security_form_subscription_reject_cross_tenant_users(
    tenant_a, admin_user_b, bi_dashboard_a
):
    """Verify ReportSubscriptionForm rejects subscriber users from Tenant B."""
    data = {
        "name": "Sec Sub Invalid User",
        "target_asset_type": "dashboard",
        "dashboard": bi_dashboard_a.pk,
        "cadence": "daily",
        "export_format": "pdf",
        "burst_mode": "broadcast",
        "status": "active",
        "subscriber_users": [admin_user_b.pk],
    }
    form = ReportSubscriptionForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "subscriber_users" in form.errors

    # Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = ReportSubscriptionForm(data=data, tenant=tenant_a)
    form_wide.fields["subscriber_users"].queryset = User.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["subscriber_users"]


def test_alertssubscriptions_security_form_burst_run_reject_cross_tenant_subscription(
    tenant_a, report_subscription_b
):
    """Verify DistributionBurstRunForm rejects a subscription from Tenant B."""
    data = {
        "subscription": report_subscription_b.pk,
        "run_trigger": "scheduled_subscription",
        "delivery_channel": "email",
        "status": "completed",
        "recipient_count": 5,
    }
    form = DistributionBurstRunForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "subscription" in form.errors

    # Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = DistributionBurstRunForm(data=data, tenant=tenant_a)
    form_wide.fields["subscription"].queryset = ReportSubscription.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["subscription"]


def test_alertssubscriptions_security_form_burst_run_reject_cross_tenant_alert_rule(
    tenant_a, bi_alert_rule_b
):
    """Verify DistributionBurstRunForm rejects an alert rule from Tenant B."""
    data = {
        "alert_rule": bi_alert_rule_b.pk,
        "run_trigger": "alert_event",
        "delivery_channel": "email",
        "status": "completed",
        "recipient_count": 3,
    }
    form = DistributionBurstRunForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "alert_rule" in form.errors

    # Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = DistributionBurstRunForm(data=data, tenant=tenant_a)
    form_wide.fields["alert_rule"].queryset = BiAlertRule.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["alert_rule"]


def test_alertssubscriptions_security_form_notification_reject_cross_tenant_recipient(
    tenant_a, admin_user_b
):
    """Verify BiNotificationItemForm rejects a recipient user from Tenant B."""
    data = {
        "recipient": admin_user_b.pk,
        "title": "Sec Notification Invalid Recipient",
        "message": "Testing cross-tenant recipient rejection.",
        "severity": "info",
        "category": "system_bulletin",
        "status": "unread",
    }
    form = BiNotificationItemForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "recipient" in form.errors

    # Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = BiNotificationItemForm(data=data, tenant=tenant_a)
    form_wide.fields["recipient"].queryset = User.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["recipient"]


def test_alertssubscriptions_security_form_notification_reject_cross_tenant_alert_rule(
    tenant_a, admin_user, bi_alert_rule_b
):
    """Verify BiNotificationItemForm rejects an alert rule from Tenant B."""
    data = {
        "recipient": admin_user.pk,
        "title": "Sec Notification Invalid Alert Rule",
        "message": "Testing cross-tenant alert_rule rejection.",
        "severity": "critical",
        "category": "kpi_alert",
        "status": "unread",
        "alert_rule": bi_alert_rule_b.pk,
    }
    form = BiNotificationItemForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "alert_rule" in form.errors

    # Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = BiNotificationItemForm(data=data, tenant=tenant_a)
    form_wide.fields["alert_rule"].queryset = BiAlertRule.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["alert_rule"]


def test_alertssubscriptions_security_form_notification_reject_cross_tenant_burst_run(
    tenant_a, admin_user, distribution_burst_run_b
):
    """Verify BiNotificationItemForm rejects a burst run from Tenant B."""
    data = {
        "recipient": admin_user.pk,
        "title": "Sec Notification Invalid Burst Run",
        "message": "Testing cross-tenant burst_run rejection.",
        "severity": "info",
        "category": "subscription_digest",
        "status": "unread",
        "burst_run": distribution_burst_run_b.pk,
    }
    form = BiNotificationItemForm(data=data, tenant=tenant_a)
    assert not form.is_valid()
    assert "burst_run" in form.errors

    # Defense-in-depth: widened queryset triggers reject_foreign
    form_wide = BiNotificationItemForm(data=data, tenant=tenant_a)
    form_wide.fields["burst_run"].queryset = DistributionBurstRun.objects.all()
    assert not form_wide.is_valid()
    assert "That record belongs to another workspace." in form_wide.errors["burst_run"]


# ==============================================================================
# 3. Open Redirect Defense Tests
# ==============================================================================


@pytest.mark.parametrize(
    "malicious_next",
    [
        "https://malicious-site.com/exploit",
        "http://attacker.example.org",
        "//evil.com/phishing",
        "\\\\evil.com\\share",
        "javascript:alert(document.cookie)",
        "data:text/html,<script>alert(1)</script>",
    ],
)
def test_alertssubscriptions_security_open_redirect_defense(
    client_a, bi_notification_item_a, malicious_next
):
    """Assert mutating notification actions reject external/malicious next redirects."""
    actions = [
        ("notification_mark_read", {}),
        ("notification_acknowledge", {"notes": "Security note"}),
        ("notification_snooze", {"hours": 4}),
        ("notification_escalate", {}),
    ]

    fallback_path = reverse("bi:notification_center")

    for action_name, extra_data in actions:
        url = reverse(f"bi:{action_name}", kwargs={"pk": bi_notification_item_a.pk})
        payload = {"next": malicious_next}
        payload.update(extra_data)

        resp = client_a.post(url, data=payload)
        assert resp.status_code == 302
        assert resp["Location"] == fallback_path, (
            f"Action {action_name} allowed unsafe redirect: {resp['Location']}"
        )


def test_alertssubscriptions_security_safe_internal_redirect_accepted(
    client_a, bi_notification_item_a
):
    """Assert mutating notification actions respect valid relative internal next parameters."""
    safe_targets = [
        reverse("bi:bi_notification_item_list"),
        reverse("bi:notification_center") + "?tab=unread",
        f"/bi/notifications/{bi_notification_item_a.pk}/",
    ]

    for target in safe_targets:
        url = reverse(
            "bi:notification_mark_read", kwargs={"pk": bi_notification_item_a.pk}
        )
        resp = client_a.post(url, data={"next": target})
        assert resp.status_code == 302
        assert resp["Location"] == target


# ==============================================================================
# 4. Stored XSS Defense on action_url
# ==============================================================================


@pytest.mark.parametrize(
    "xss_payload",
    [
        "javascript:alert(document.cookie)",
        "JAVASCRIPT:alert(1)",
        "javascript:void(0)",
        "data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==",
        "data:text/javascript,alert(1)",
        "vbscript:msgbox(1)",
        "VBSCRIPT:msgbox('XSS')",
        "ftp://malicious.org/payload.exe",
        "file:///etc/passwd",
        "relative/without/leading/slash",
        "kpi/10/no-slash",
    ],
)
def test_alertssubscriptions_security_action_url_xss_rejected(
    tenant_a, admin_user, xss_payload
):
    """Assert BiNotificationItemForm rejects unsafe or non-http/non-relative action_url payloads."""
    form = BiNotificationItemForm(
        data={
            "recipient": admin_user.pk,
            "title": "XSS Test Notification",
            "message": "Testing action_url validation against XSS payloads.",
            "severity": "warning",
            "category": "system_bulletin",
            "status": "unread",
            "action_url": xss_payload,
        },
        tenant=tenant_a,
    )
    assert not form.is_valid()
    assert "action_url" in form.errors
    assert "Action URL must be a relative path" in form.errors["action_url"][0]


@pytest.mark.parametrize(
    "valid_url",
    [
        "/bi/dashboards/1/",
        "/bi/kpis/5/",
        "/bi/notification-center/?tab=unread",
        "https://analytics.example.com/reports/exec",
        "http://intranet.local/reports/view",
        "",  # optional field
    ],
)
def test_alertssubscriptions_security_action_url_valid_accepted(
    tenant_a, admin_user, valid_url
):
    """Assert BiNotificationItemForm accepts legitimate relative and http/https action_url paths."""
    form = BiNotificationItemForm(
        data={
            "recipient": admin_user.pk,
            "title": "Valid URL Notification",
            "message": "Testing valid action_url.",
            "severity": "info",
            "category": "system_bulletin",
            "status": "unread",
            "action_url": valid_url,
        },
        tenant=tenant_a,
    )
    assert form.is_valid(), f"Form unexpectedly invalid for action_url={valid_url}: {form.errors}"
    assert form.cleaned_data["action_url"] == valid_url


# ==============================================================================
# 5. Hand-Parsed Numeric/Integer Hardening
# ==============================================================================


@pytest.mark.parametrize(
    "malformed_hours",
    [
        "not_a_number",
        "-5",
        "0",
        "9999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999999",
        "NaN",
        "Infinity",
        "-Infinity",
        "3.14159",
        "",
        "100",  # positive int but not in allowed set (1, 4, 24, 72)
        "12",
    ],
)
def test_alertssubscriptions_security_notification_snooze_hours_hardening(
    client_a, bi_notification_item_a, malformed_hours
):
    """Assert notification_snooze safely falls back to 4 hours on malformed or out-of-range inputs without 500 error."""
    url = reverse("bi:notification_snooze", kwargs={"pk": bi_notification_item_a.pk})
    before = timezone.now()

    resp = client_a.post(url, data={"hours": malformed_hours})
    assert resp.status_code == 302

    bi_notification_item_a.refresh_from_db()
    assert bi_notification_item_a.status == "snoozed"
    assert bi_notification_item_a.snoozed_until is not None

    expected_snooze = before + timedelta(hours=4)
    # Allow 5 seconds tolerance
    assert abs((bi_notification_item_a.snoozed_until - expected_snooze).total_seconds()) < 5


@pytest.mark.parametrize("valid_hours", [1, 4, 24, 72])
def test_alertssubscriptions_security_notification_snooze_valid_hours(
    client_a, bi_notification_item_a, valid_hours
):
    """Assert notification_snooze sets accurate snoozed_until timestamp for valid hour options."""
    url = reverse("bi:notification_snooze", kwargs={"pk": bi_notification_item_a.pk})
    before = timezone.now()

    resp = client_a.post(url, data={"hours": str(valid_hours)})
    assert resp.status_code == 302

    bi_notification_item_a.refresh_from_db()
    assert bi_notification_item_a.status == "snoozed"
    expected_snooze = before + timedelta(hours=valid_hours)
    assert abs((bi_notification_item_a.snoozed_until - expected_snooze).total_seconds()) < 5


# ==============================================================================
# 6. Privilege Separation & AuthN/AuthZ
# ==============================================================================


def test_alertssubscriptions_security_unauthenticated_access_redirects_to_login(
    client,
    bi_alert_rule_a,
    report_subscription_a,
    distribution_burst_run_a,
    bi_notification_item_a,
):
    """Assert all 10.16 views redirect anonymous users to the login page (HTTP 302)."""
    endpoints = [
        # Lists and Workspaces
        ("GET", reverse("bi:bi_alert_rule_list")),
        ("GET", reverse("bi:report_subscription_list")),
        ("GET", reverse("bi:distribution_burst_run_list")),
        ("GET", reverse("bi:bi_notification_item_list")),
        ("GET", reverse("bi:notification_center")),
        # Create
        ("GET", reverse("bi:bi_alert_rule_create")),
        ("GET", reverse("bi:report_subscription_create")),
        ("GET", reverse("bi:distribution_burst_run_create")),
        ("GET", reverse("bi:bi_notification_item_create")),
        ("POST", reverse("bi:bi_alert_rule_create")),
        ("POST", reverse("bi:report_subscription_create")),
        ("POST", reverse("bi:distribution_burst_run_create")),
        ("POST", reverse("bi:bi_notification_item_create")),
        # Detail
        ("GET", reverse("bi:bi_alert_rule_detail", kwargs={"pk": bi_alert_rule_a.pk})),
        ("GET", reverse("bi:report_subscription_detail", kwargs={"pk": report_subscription_a.pk})),
        ("GET", reverse("bi:distribution_burst_run_detail", kwargs={"pk": distribution_burst_run_a.pk})),
        ("GET", reverse("bi:bi_notification_item_detail", kwargs={"pk": bi_notification_item_a.pk})),
        # Edit
        ("GET", reverse("bi:bi_alert_rule_edit", kwargs={"pk": bi_alert_rule_a.pk})),
        ("GET", reverse("bi:report_subscription_edit", kwargs={"pk": report_subscription_a.pk})),
        ("GET", reverse("bi:distribution_burst_run_edit", kwargs={"pk": distribution_burst_run_a.pk})),
        ("GET", reverse("bi:bi_notification_item_edit", kwargs={"pk": bi_notification_item_a.pk})),
        # Delete
        ("POST", reverse("bi:bi_alert_rule_delete", kwargs={"pk": bi_alert_rule_a.pk})),
        ("POST", reverse("bi:report_subscription_delete", kwargs={"pk": report_subscription_a.pk})),
        ("POST", reverse("bi:distribution_burst_run_delete", kwargs={"pk": distribution_burst_run_a.pk})),
        ("POST", reverse("bi:bi_notification_item_delete", kwargs={"pk": bi_notification_item_a.pk})),
        # Custom Actions
        ("POST", reverse("bi:bi_alert_rule_test_evaluate", kwargs={"pk": bi_alert_rule_a.pk})),
        ("POST", reverse("bi:report_subscription_run_now", kwargs={"pk": report_subscription_a.pk})),
        ("POST", reverse("bi:notification_mark_read", kwargs={"pk": bi_notification_item_a.pk})),
        ("POST", reverse("bi:notification_acknowledge", kwargs={"pk": bi_notification_item_a.pk})),
        ("POST", reverse("bi:notification_snooze", kwargs={"pk": bi_notification_item_a.pk})),
        ("POST", reverse("bi:notification_escalate", kwargs={"pk": bi_notification_item_a.pk})),
    ]

    for method, url in endpoints:
        resp = client.get(url) if method == "GET" else client.post(url)
        assert resp.status_code == 302, f"Expected 302 redirect to login for {method} {url}, got {resp.status_code}"
        assert "/login/" in resp["Location"], f"URL {url} did not redirect to login page"


def test_alertssubscriptions_security_tenant_admin_required_for_deletions(
    member_client,
    client_a,
    tenant_a,
    admin_user,
    bi_dashboard_a,
):
    """Assert non-admin tenant member receives 403 Forbidden for deletion endpoints protected by @tenant_admin_required."""
    # 1. BiAlertRule delete
    rule = _alertssubscriptions_security_create_alert_rule(tenant_a, user=admin_user)
    rule_url = reverse("bi:bi_alert_rule_delete", kwargs={"pk": rule.pk})
    resp_member = member_client.post(rule_url)
    assert resp_member.status_code == 403
    assert BiAlertRule.objects.filter(pk=rule.pk).exists()

    resp_admin = client_a.post(rule_url)
    assert resp_admin.status_code == 302
    assert not BiAlertRule.objects.filter(pk=rule.pk).exists()

    # 2. ReportSubscription delete
    sub = _alertssubscriptions_security_create_subscription(
        tenant_a, dashboard=bi_dashboard_a, user=admin_user
    )
    sub_url = reverse("bi:report_subscription_delete", kwargs={"pk": sub.pk})
    resp_member = member_client.post(sub_url)
    assert resp_member.status_code == 403
    assert ReportSubscription.objects.filter(pk=sub.pk).exists()

    resp_admin = client_a.post(sub_url)
    assert resp_admin.status_code == 302
    assert not ReportSubscription.objects.filter(pk=sub.pk).exists()

    # 3. DistributionBurstRun delete
    run = _alertssubscriptions_security_create_burst_run(tenant_a, user=admin_user)
    run_url = reverse("bi:distribution_burst_run_delete", kwargs={"pk": run.pk})
    resp_member = member_client.post(run_url)
    assert resp_member.status_code == 403
    assert DistributionBurstRun.objects.filter(pk=run.pk).exists()

    resp_admin = client_a.post(run_url)
    assert resp_admin.status_code == 302
    assert not DistributionBurstRun.objects.filter(pk=run.pk).exists()


def test_alertssubscriptions_security_require_post_enforced(
    client_a,
    bi_alert_rule_a,
    report_subscription_a,
    distribution_burst_run_a,
    bi_notification_item_a,
):
    """Assert mutating/action endpoints reject GET requests with HTTP 405 Method Not Allowed."""
    mutation_get_endpoints = [
        reverse("bi:bi_alert_rule_delete", kwargs={"pk": bi_alert_rule_a.pk}),
        reverse("bi:bi_alert_rule_test_evaluate", kwargs={"pk": bi_alert_rule_a.pk}),
        reverse("bi:report_subscription_delete", kwargs={"pk": report_subscription_a.pk}),
        reverse("bi:report_subscription_run_now", kwargs={"pk": report_subscription_a.pk}),
        reverse("bi:distribution_burst_run_delete", kwargs={"pk": distribution_burst_run_a.pk}),
        reverse("bi:bi_notification_item_delete", kwargs={"pk": bi_notification_item_a.pk}),
        reverse("bi:notification_mark_read", kwargs={"pk": bi_notification_item_a.pk}),
        reverse("bi:notification_acknowledge", kwargs={"pk": bi_notification_item_a.pk}),
        reverse("bi:notification_snooze", kwargs={"pk": bi_notification_item_a.pk}),
        reverse("bi:notification_escalate", kwargs={"pk": bi_notification_item_a.pk}),
    ]

    for url in mutation_get_endpoints:
        resp = client_a.get(url)
        assert resp.status_code == 405, f"Expected 405 for GET {url}, got {resp.status_code}"


# ==============================================================================
# 7. Audit Log Verification Tests
# ==============================================================================


def test_alertssubscriptions_security_audit_log_alert_rule_lifecycle(
    client_a, tenant_a, admin_user
):
    """Assert AuditLog records are generated for BiAlertRule create, update, evaluate, and delete."""
    # 1. Create
    create_url = reverse("bi:bi_alert_rule_create")
    create_data = {
        "name": "Audit Tracked Alert Rule",
        "description": "Rule for audit log testing.",
        "alert_type": "kpi_threshold",
        "condition_operator": "gt",
        "threshold_value": "150.0000",
        "severity": "critical",
        "evaluation_cadence": "daily",
        "trigger_frequency": "every_time",
        "delivery_channel": "in_app_only",
        "downstream_workflow": "none",
        "status": "active",
    }
    resp = client_a.post(create_url, data=create_data)
    assert resp.status_code == 302
    created_rule = BiAlertRule.objects.get(name="Audit Tracked Alert Rule")

    log_create = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="create",
        object_id=created_rule.pk,
    ).first()
    assert log_create is not None
    assert created_rule.number in log_create.target

    # 2. Update
    edit_url = reverse("bi:bi_alert_rule_edit", kwargs={"pk": created_rule.pk})
    edit_data = dict(create_data, name="Audit Tracked Alert Rule Updated")
    resp = client_a.post(edit_url, data=edit_data)
    assert resp.status_code == 302

    log_update = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="update",
        object_id=created_rule.pk,
    ).first()
    assert log_update is not None

    # 3. Evaluate
    eval_url = reverse(
        "bi:bi_alert_rule_test_evaluate", kwargs={"pk": created_rule.pk}
    )
    resp = client_a.post(eval_url)
    assert resp.status_code == 302

    log_eval = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="update",
        object_id=created_rule.pk,
    ).exclude(pk=log_update.pk).first()
    assert log_eval is not None
    assert "Evaluate" in log_eval.changes.get("details", "")

    # 4. Delete
    del_url = reverse("bi:bi_alert_rule_delete", kwargs={"pk": created_rule.pk})
    resp = client_a.post(del_url)
    assert resp.status_code == 302

    log_delete = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="delete",
        object_id=created_rule.pk,
    ).first()
    assert log_delete is not None


def test_alertssubscriptions_security_audit_log_subscription_and_burst_run(
    client_a, tenant_a, admin_user, bi_dashboard_a
):
    """Assert AuditLog records are created for ReportSubscription and DistributionBurstRun actions."""
    # 1. Create Subscription
    create_url = reverse("bi:report_subscription_create")
    create_data = {
        "name": "Audit Tracked Subscription",
        "target_asset_type": "dashboard",
        "dashboard": bi_dashboard_a.pk,
        "cadence": "weekly",
        "scheduled_time": "08:00",
        "export_format": "pdf",
        "burst_mode": "broadcast",
        "status": "active",
    }
    resp = client_a.post(create_url, data=create_data)
    assert resp.status_code == 302
    created_sub = ReportSubscription.objects.get(name="Audit Tracked Subscription")

    log_sub_create = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="create",
        object_id=created_sub.pk,
    ).first()
    assert log_sub_create is not None
    assert created_sub.number in log_sub_create.target

    # 2. Run now (triggers burst run creation and log)
    run_now_url = reverse(
        "bi:report_subscription_run_now", kwargs={"pk": created_sub.pk}
    )
    resp = client_a.post(run_now_url)
    assert resp.status_code == 302

    latest_burst = DistributionBurstRun.objects.filter(
        subscription=created_sub
    ).latest("id")
    log_run_now = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="create",
        object_id=latest_burst.pk,
    ).first()
    assert log_run_now is not None
    assert "Manual Run" in log_run_now.changes.get("details", "")

    # 3. Update Burst Run
    burst_edit_url = reverse(
        "bi:distribution_burst_run_edit", kwargs={"pk": latest_burst.pk}
    )
    burst_edit_data = {
        "subscription": created_sub.pk,
        "run_trigger": "ad_hoc_manual",
        "delivery_channel": "email",
        "status": "completed",
        "recipient_count": 5,
        "file_size_bytes": 1024,
        "error_summary": "No errors detected.",
    }
    resp = client_a.post(burst_edit_url, data=burst_edit_data)
    assert resp.status_code == 302

    log_burst_update = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="update",
        object_id=latest_burst.pk,
    ).first()
    assert log_burst_update is not None

    # 4. Delete Burst Run
    burst_del_url = reverse(
        "bi:distribution_burst_run_delete", kwargs={"pk": latest_burst.pk}
    )
    resp = client_a.post(burst_del_url)
    assert resp.status_code == 302

    log_burst_del = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="delete",
        object_id=latest_burst.pk,
    ).first()
    assert log_burst_del is not None

    # 5. Delete Subscription
    sub_del_url = reverse(
        "bi:report_subscription_delete", kwargs={"pk": created_sub.pk}
    )
    resp = client_a.post(sub_del_url)
    assert resp.status_code == 302

    log_sub_del = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="delete",
        object_id=created_sub.pk,
    ).first()
    assert log_sub_del is not None


def test_alertssubscriptions_security_audit_log_notification_actions(
    client_a, tenant_a, admin_user, bi_alert_rule_a
):
    """Assert AuditLog records are created for Notification create, update, acknowledge, snooze, escalate, and delete."""
    # 1. Create Notification
    create_url = reverse("bi:bi_notification_item_create")
    create_data = {
        "recipient": admin_user.pk,
        "title": "Audit Tracked Notification",
        "message": "Testing notification audit trail.",
        "severity": "critical",
        "category": "kpi_alert",
        "status": "unread",
        "alert_rule": bi_alert_rule_a.pk,
    }
    resp = client_a.post(create_url, data=create_data)
    assert resp.status_code == 302
    created_item = BiNotificationItem.objects.get(title="Audit Tracked Notification")

    log_create = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="create",
        object_id=created_item.pk,
    ).first()
    assert log_create is not None
    assert created_item.number in log_create.target

    # 2. Acknowledge
    ack_url = reverse("bi:notification_acknowledge", kwargs={"pk": created_item.pk})
    resp = client_a.post(ack_url, data={"notes": "Investigating anomaly."})
    assert resp.status_code == 302

    log_ack = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="update",
        object_id=created_item.pk,
    ).filter(changes__details__icontains="Acknowledged").first()
    assert log_ack is not None

    # 3. Snooze
    snooze_url = reverse("bi:notification_snooze", kwargs={"pk": created_item.pk})
    resp = client_a.post(snooze_url, data={"hours": "24"})
    assert resp.status_code == 302

    log_snooze = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="update",
        object_id=created_item.pk,
    ).filter(changes__details__icontains="Snoozed").first()
    assert log_snooze is not None
    assert "24 hours" in log_snooze.changes.get("details", "")

    # 4. Escalate
    esc_url = reverse("bi:notification_escalate", kwargs={"pk": created_item.pk})
    resp = client_a.post(esc_url)
    assert resp.status_code == 302

    log_esc = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="update",
        object_id=created_item.pk,
    ).filter(changes__details__icontains="Escalated").first()
    assert log_esc is not None

    # 5. Delete
    del_url = reverse("bi:bi_notification_item_delete", kwargs={"pk": created_item.pk})
    resp = client_a.post(del_url)
    assert resp.status_code == 302

    log_del = AuditLog.objects.filter(
        tenant=tenant_a,
        user=admin_user,
        action="delete",
        object_id=created_item.pk,
    ).first()
    assert log_del is not None
