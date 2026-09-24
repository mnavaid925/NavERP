import json
import socket
import urllib.request

import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages import get_messages
from django.core.exceptions import ValidationError
from django.urls import reverse

from apps.core.crypto import is_encrypted
from apps.core.models import AuditLog
from apps.projects.forms import (
    ConnectorFieldMappingForm,
    ProjectIntegrationConnectorForm,
    ProjectSyncJobForm,
)
from apps.projects.models import (
    ConnectorFieldMapping,
    ProjectIntegrationConnector,
    ProjectSyncJob,
    ProjectSyncRun,
)

pytestmark = pytest.mark.django_db
User = get_user_model()

_INTEGRATIONAPIHUB_ROUTES = (
    ("ixc_list", (), "/projects/integration/connectors/"),
    ("ixc_create", (), "/projects/integration/connectors/add/"),
    ("ixc_erp_list", (), "/projects/integration/connectors/erp/"),
    ("ixc_crm_list", (), "/projects/integration/connectors/crm/"),
    ("ixc_hris_list", (), "/projects/integration/connectors/hris/"),
    ("ixc_devops_list", (), "/projects/integration/connectors/devops/"),
    ("ixc_storage_list", (), "/projects/integration/connectors/storage/"),
    ("ixc_detail", (7,), "/projects/integration/connectors/7/"),
    ("ixc_edit", (7,), "/projects/integration/connectors/7/edit/"),
    ("ixc_delete", (7,), "/projects/integration/connectors/7/delete/"),
    ("ixc_rotate_credential", (7,), "/projects/integration/connectors/7/rotate-credential/"),
    ("ixc_test", (7,), "/projects/integration/connectors/7/test/"),
    ("ixc_toggle_active", (7,), "/projects/integration/connectors/7/toggle/"),
    ("connector_health", (7,), "/projects/integration/connectors/7/health/"),
    ("ixm_list", (), "/projects/integration/mappings/"),
    ("ixm_create", (), "/projects/integration/mappings/add/"),
    ("ixm_detail", (7,), "/projects/integration/mappings/7/"),
    ("ixm_edit", (7,), "/projects/integration/mappings/7/edit/"),
    ("ixm_delete", (7,), "/projects/integration/mappings/7/delete/"),
    ("syj_list", (), "/projects/integration/sync-jobs/"),
    ("syj_create", (), "/projects/integration/sync-jobs/add/"),
    ("syj_detail", (7,), "/projects/integration/sync-jobs/7/"),
    ("syj_edit", (7,), "/projects/integration/sync-jobs/7/edit/"),
    ("syj_delete", (7,), "/projects/integration/sync-jobs/7/delete/"),
    ("syj_run", (7,), "/projects/integration/sync-jobs/7/run/"),
    ("syj_toggle_active", (7,), "/projects/integration/sync-jobs/7/toggle/"),
    ("syr_list", (), "/projects/integration/runs/"),
    ("syr_detail", (7,), "/projects/integration/runs/7/"),
    ("syr_retry", (7,), "/projects/integration/runs/7/retry/"),
    ("integration_hub", (), "/projects/integration/hub/"),
    ("sync_monitor", (), "/projects/integration/monitor/"),
)

_INTEGRATIONAPIHUB_POST_ONLY = (
    ("ixc_delete", "integrationapihub_connector_a"),
    ("ixc_rotate_credential", "integrationapihub_connector_a"),
    ("ixc_test", "integrationapihub_connector_a"),
    ("ixc_toggle_active", "integrationapihub_connector_a"),
    ("ixm_delete", "integrationapihub_mapping_a"),
    ("syj_delete", "integrationapihub_job_a"),
    ("syj_run", "integrationapihub_job_a"),
    ("syj_toggle_active", "integrationapihub_job_a"),
    ("syr_retry", "integrationapihub_run_failed_a"),
)

_INTEGRATIONAPIHUB_ADMIN_POST_ONLY = (
    ("ixc_delete", "integrationapihub_connector_a"),
    ("ixc_rotate_credential", "integrationapihub_connector_a"),
    ("ixm_delete", "integrationapihub_mapping_a"),
    ("syj_delete", "integrationapihub_job_a"),
    ("syr_retry", "integrationapihub_run_failed_a"),
)

_INTEGRATIONAPIHUB_LOGIN_POST_ONLY = (
    ("ixc_test", "integrationapihub_connector_a"),
    ("ixc_toggle_active", "integrationapihub_connector_a"),
    ("syj_run", "integrationapihub_job_a"),
    ("syj_toggle_active", "integrationapihub_job_a"),
)

_INTEGRATIONAPIHUB_CSRF_ROUTES = (
    ("ixc_create", None),
    ("ixc_edit", "integrationapihub_connector_a"),
    ("ixm_create", None),
    ("ixm_edit", "integrationapihub_mapping_a"),
    ("syj_create", None),
    ("syj_edit", "integrationapihub_job_a"),
    ("ixc_delete", "integrationapihub_connector_a"),
    ("ixc_rotate_credential", "integrationapihub_connector_a"),
    ("ixc_test", "integrationapihub_connector_a"),
    ("ixc_toggle_active", "integrationapihub_connector_a"),
    ("ixm_delete", "integrationapihub_mapping_a"),
    ("syj_delete", "integrationapihub_job_a"),
    ("syj_run", "integrationapihub_job_a"),
    ("syj_toggle_active", "integrationapihub_job_a"),
    ("syr_retry", "integrationapihub_run_failed_a"),
)

_INTEGRATIONAPIHUB_CONNECTOR_FOREIGN_GET = (
    ("ixc_detail", "integrationapihub_connector_b"),
    ("ixc_edit", "integrationapihub_connector_b"),
    ("connector_health", "integrationapihub_connector_b"),
)

_INTEGRATIONAPIHUB_CONNECTOR_FOREIGN_POST = (
    ("ixc_edit", "integrationapihub_connector_b"),
    ("ixc_delete", "integrationapihub_connector_b"),
    ("ixc_rotate_credential", "integrationapihub_connector_b"),
    ("ixc_test", "integrationapihub_connector_b"),
    ("ixc_toggle_active", "integrationapihub_connector_b"),
)

_INTEGRATIONAPIHUB_MAPPING_FOREIGN_GET = (
    ("ixm_detail", "integrationapihub_mapping_b"),
    ("ixm_edit", "integrationapihub_mapping_b"),
)

_INTEGRATIONAPIHUB_MAPPING_FOREIGN_POST = (
    ("ixm_edit", "integrationapihub_mapping_b"),
    ("ixm_delete", "integrationapihub_mapping_b"),
)

_INTEGRATIONAPIHUB_JOB_FOREIGN_GET = (
    ("syj_detail", "integrationapihub_job_b"),
    ("syj_edit", "integrationapihub_job_b"),
)

_INTEGRATIONAPIHUB_JOB_FOREIGN_POST = (
    ("syj_edit", "integrationapihub_job_b"),
    ("syj_delete", "integrationapihub_job_b"),
    ("syj_run", "integrationapihub_job_b"),
    ("syj_toggle_active", "integrationapihub_job_b"),
)

_INTEGRATIONAPIHUB_RUN_FOREIGN_GET = (
    ("syr_detail", "integrationapihub_run_b"),
)

_INTEGRATIONAPIHUB_RUN_FOREIGN_POST = (
    ("syr_retry", "integrationapihub_run_b"),
)


def _integrationapihub_url(name, *args):
    return reverse(f"projects:{name}", args=args)


def _integrationapihub_fixture(request, fixture_name):
    return None if fixture_name is None else request.getfixturevalue(fixture_name)


def _integrationapihub_target_url(request, route, fixture_name):
    target = _integrationapihub_fixture(request, fixture_name)
    args = () if target is None else (target.pk,)
    return _integrationapihub_url(route, *args), target


def _integrationapihub_snapshot(obj):
    if obj is None:
        return None
    return type(obj)._default_manager.filter(pk=obj.pk).values().first()


def _integrationapihub_assert_unchanged(obj, before):
    assert _integrationapihub_snapshot(obj) == before


def _integrationapihub_chain_snapshot(objects):
    return [(type(obj), obj.pk, _integrationapihub_snapshot(obj)) for obj in objects]


def _integrationapihub_assert_chain_unchanged(chain):
    for model, pk, before in chain:
        after = model._default_manager.filter(pk=pk).values().first()
        assert after == before


def _integrationapihub_audits(model, object_pk, action=None):
    queryset = AuditLog.objects.filter(
        content_type=ContentType.objects.get_for_model(model),
        object_id=object_pk,
    )
    if action is not None:
        queryset = queryset.filter(action=action)
    return list(queryset.order_by("id"))


def _integrationapihub_messages(response):
    return [str(message) for message in get_messages(response.wsgi_request)]


def _integrationapihub_body(response):
    return response.content.decode()


def _integrationapihub_context_pks(response, key):
    return [row.pk for row in list(response.context[key])]


def _integrationapihub_assert_no_tokens(response, tokens):
    body = _integrationapihub_body(response)
    for token in tokens:
        assert token not in body, token


def _integrationapihub_assert_no_tokens_ignoring_values(response, tokens, values):
    body = _integrationapihub_body(response)
    for value in values:
        body = body.replace(value, "")
    for token in tokens:
        assert token not in body, token


def _integrationapihub_widen(form, *field_names):
    for field_name in field_names:
        field = form.fields[field_name]
        field.queryset = field.queryset.model._default_manager.all()
    return form


def _integrationapihub_inactive_user(tenant):
    count = User.objects.filter(username__startswith="integrationapihub_inactive").count()
    return User.objects.create_user(
        email=f"integrationapihub_inactive_{count}@example.com",
        username=f"integrationapihub_inactive_{count}",
        password="TestPass123!",
        tenant=tenant,
        is_active=False,
    )


def _integrationapihub_connector_payload(project=None, owner=None, **overrides):
    payload = {
        "project": "" if project is None else str(project.pk),
        "name": "Security connector payload",
        "domain": "erp",
        "provider": "sap",
        "direction": "bidirectional",
        "auth_method": "api_key",
        "base_url": "http://127.0.0.1:9/internal",
        "remote_scope_ref": "SECURITY-SCOPE",
        "trigger_mode": "manual",
        "schedule_note": "Recorded intent only.",
        "environment": "sandbox",
        "status": "unverified",
        "is_active": "on",
        "notify_webhook": "",
        "owner": "" if owner is None else str(owner.pk),
        "notes": "No outbound request is made.",
        "credential": "",
    }
    payload.update(overrides)
    return payload


def _integrationapihub_mapping_payload(connector, **overrides):
    payload = {
        "connector": str(connector.pk),
        "local_field": "task.security_field",
        "remote_field": "fields.SecurityField",
        "direction": "both",
        "transform": "none",
        "value_map": "{}",
        "default_value": "",
        "is_key": "",
        "is_required": "",
        "notes": "",
    }
    payload.update(overrides)
    return payload


def _integrationapihub_job_payload(connector, **overrides):
    payload = {
        "connector": str(connector.pk),
        "name": "Security sync job payload",
        "entity_scope": "tasks",
        "direction": "bidirectional",
        "trigger_mode": "manual",
        "interval_minutes": "",
        "schedule_note": "",
        "filter_expression": "",
        "conflict_policy": "manual",
        "batch_size": "100",
        "is_active": "on",
    }
    payload.update(overrides)
    return payload


def _integrationapihub_tokenize_tenant_b(
    project_b,
    connector_b,
    mapping_b,
    job_b,
    run_b,
    webhook_b,
):
    project_b.name = "B_ONLY_PROJECT_TOKEN"
    project_b.save(update_fields=["name", "updated_at"])
    connector_b.name = "B_ONLY_CONNECTOR_TOKEN"
    connector_b.remote_scope_ref = "B_ONLY_SCOPE_TOKEN"
    connector_b.save(update_fields=["name", "remote_scope_ref", "updated_at"])
    mapping_b.local_field = "B_ONLY_MAPPING_TOKEN"
    mapping_b.remote_field = "B_ONLY_REMOTE_TOKEN"
    mapping_b.save(update_fields=["local_field", "remote_field", "updated_at"])
    job_b.name = "B_ONLY_JOB_TOKEN"
    job_b.filter_expression = "B_ONLY_FILTER_TOKEN"
    job_b.save(update_fields=["name", "filter_expression", "updated_at"])
    run_b.error_code = "B_ONLY_ERROR_CODE"
    run_b.error_message = "B_ONLY_ERROR_MESSAGE"
    run_b.payload_excerpt = "B_ONLY_PAYLOAD_TOKEN"
    run_b.save(update_fields=["error_code", "error_message", "payload_excerpt", "updated_at"])
    webhook_b.name = "B_ONLY_WEBHOOK_TOKEN"
    webhook_b.save(update_fields=["name", "updated_at"])
    return (
        project_b.name,
        connector_b.name,
        connector_b.remote_scope_ref,
        mapping_b.local_field,
        mapping_b.remote_field,
        job_b.name,
        job_b.filter_expression,
        run_b.error_code,
        run_b.error_message,
        run_b.payload_excerpt,
        webhook_b.name,
    )


def _integrationapihub_assert_empty_filter(response, key, tokens, ignored_values=()):
    assert response.status_code == 200
    assert list(response.context[key]) == []
    if ignored_values:
        _integrationapihub_assert_no_tokens_ignoring_values(response, tokens, ignored_values)
    else:
        _integrationapihub_assert_no_tokens(response, tokens)


def _integrationapihub_forbid_network(monkeypatch):
    def _integrationapihub_network_failure(*args, **kwargs):
        raise AssertionError("7.18 attempted outbound network I/O")

    monkeypatch.setattr(socket.socket, "connect", _integrationapihub_network_failure)
    monkeypatch.setattr(socket, "create_connection", _integrationapihub_network_failure)
    monkeypatch.setattr(urllib.request, "urlopen", _integrationapihub_network_failure)
    try:
        import requests
    except ImportError:
        return
    monkeypatch.setattr(requests.sessions.Session, "request", _integrationapihub_network_failure)


def test_integrationapihub_anonymous_get_and_post_redirect_for_all_31_routes(
    projectinitiation_anon_client,
):
    assert len(_INTEGRATIONAPIHUB_ROUTES) == 31
    for route, args, expected_path in _INTEGRATIONAPIHUB_ROUTES:
        url = _integrationapihub_url(route, *args)
        assert url == expected_path
        for method in ("get", "post"):
            response = getattr(projectinitiation_anon_client, method)(url, {}) if method == "post" else getattr(projectinitiation_anon_client, method)(url)
            assert response.status_code == 302, (route, method, response.status_code)
            assert "/login/" in response.url, (route, method, response.url)


@pytest.mark.parametrize("route,fixture_name", _INTEGRATIONAPIHUB_POST_ONLY)
def test_integrationapihub_post_only_routes_return_405_for_member_and_admin(
    client_a,
    member_client,
    request,
    route,
    fixture_name,
):
    url, target = _integrationapihub_target_url(request, route, fixture_name)
    before = _integrationapihub_snapshot(target)
    assert client_a.get(url).status_code == 405
    assert member_client.get(url).status_code == 405
    _integrationapihub_assert_unchanged(target, before)


@pytest.mark.parametrize("route,fixture_name", _INTEGRATIONAPIHUB_ADMIN_POST_ONLY)
def test_integrationapihub_member_post_to_admin_only_actions_is_403(
    member_client,
    request,
    route,
    fixture_name,
):
    url, target = _integrationapihub_target_url(request, route, fixture_name)
    before = _integrationapihub_snapshot(target)
    response = member_client.post(url, {})
    assert response.status_code == 403
    _integrationapihub_assert_unchanged(target, before)


@pytest.mark.parametrize("route,fixture_name", _INTEGRATIONAPIHUB_ADMIN_POST_ONLY)
def test_integrationapihub_admin_post_controls_all_five_admin_only_actions(
    client_a,
    request,
    route,
    fixture_name,
):
    url, target = _integrationapihub_target_url(request, route, fixture_name)
    response = client_a.post(url, {})
    assert response.status_code == 302
    if route == "ixc_delete":
        assert not ProjectIntegrationConnector.objects.filter(pk=target.pk).exists()
    elif route == "ixc_rotate_credential":
        target.refresh_from_db()
        assert len(target.get_credential()) == 64
        assert client_a.session["_ixc_cred_reveal"]["pk"] == target.pk
    elif route == "ixm_delete":
        assert not ConnectorFieldMapping.objects.filter(pk=target.pk).exists()
    elif route == "syj_delete":
        assert not ProjectSyncJob.objects.filter(pk=target.pk).exists()
    elif route == "syr_retry":
        target.refresh_from_db()
        assert target.status == "pending"
        assert target.attempt_no == 2
        assert target.next_retry_at is not None


def test_integrationapihub_csrf_is_enforced_on_every_post_form_and_action(
    projectinitiation_csrf_client,
    request,
):
    for route, fixture_name in _INTEGRATIONAPIHUB_CSRF_ROUTES:
        url, target = _integrationapihub_target_url(request, route, fixture_name)
        before = _integrationapihub_snapshot(target)
        response = projectinitiation_csrf_client.post(url, {})
        assert response.status_code == 403, route
        _integrationapihub_assert_unchanged(target, before)


def test_integrationapihub_tenant_a_admin_gets_404_for_every_foreign_connector_route(
    client_a,
    request,
    tenant_b,
    integrationapihub_connector_b,
    integrationapihub_mapping_b,
    integrationapihub_job_b,
    integrationapihub_run_b,
):
    chain = _integrationapihub_chain_snapshot(
        (integrationapihub_connector_b, integrationapihub_mapping_b, integrationapihub_job_b, integrationapihub_run_b)
    )
    audit_count = AuditLog.objects.filter(tenant=tenant_b).count()
    for route, fixture_name in _INTEGRATIONAPIHUB_CONNECTOR_FOREIGN_GET:
        target = request.getfixturevalue(fixture_name)
        response = client_a.get(_integrationapihub_url(route, target.pk))
        assert response.status_code == 404
        assert target.name not in _integrationapihub_body(response)
    for route, fixture_name in _INTEGRATIONAPIHUB_CONNECTOR_FOREIGN_POST:
        target = request.getfixturevalue(fixture_name)
        data = {"name": "foreign edit", "note": "foreign test"}
        response = client_a.post(_integrationapihub_url(route, target.pk), data)
        assert response.status_code == 404, route
    _integrationapihub_assert_chain_unchanged(chain)
    assert AuditLog.objects.filter(tenant=tenant_b).count() == audit_count


def test_integrationapihub_tenant_a_admin_gets_404_for_every_foreign_mapping_route(
    client_a,
    request,
    tenant_b,
    integrationapihub_mapping_b,
):
    chain = _integrationapihub_chain_snapshot((integrationapihub_mapping_b,))
    audit_count = AuditLog.objects.filter(tenant=tenant_b).count()
    for route, fixture_name in _INTEGRATIONAPIHUB_MAPPING_FOREIGN_GET:
        target = request.getfixturevalue(fixture_name)
        response = client_a.get(_integrationapihub_url(route, target.pk))
        assert response.status_code == 404
    for route, fixture_name in _INTEGRATIONAPIHUB_MAPPING_FOREIGN_POST:
        target = request.getfixturevalue(fixture_name)
        response = client_a.post(
            _integrationapihub_url(route, target.pk),
            {"local_field": "foreign mapping"},
        )
        assert response.status_code == 404
    _integrationapihub_assert_chain_unchanged(chain)
    assert AuditLog.objects.filter(tenant=tenant_b).count() == audit_count


def test_integrationapihub_tenant_a_admin_gets_404_for_every_foreign_job_route(
    client_a,
    request,
    tenant_b,
    integrationapihub_connector_b,
    integrationapihub_job_b,
    integrationapihub_run_b,
):
    chain = _integrationapihub_chain_snapshot(
        (integrationapihub_connector_b, integrationapihub_job_b, integrationapihub_run_b)
    )
    audit_count = AuditLog.objects.filter(tenant=tenant_b).count()
    for route, fixture_name in _INTEGRATIONAPIHUB_JOB_FOREIGN_GET:
        target = request.getfixturevalue(fixture_name)
        response = client_a.get(_integrationapihub_url(route, target.pk))
        assert response.status_code == 404
    for route, fixture_name in _INTEGRATIONAPIHUB_JOB_FOREIGN_POST:
        target = request.getfixturevalue(fixture_name)
        response = client_a.post(
            _integrationapihub_url(route, target.pk),
            {"name": "foreign job"},
        )
        assert response.status_code == 404, route
    _integrationapihub_assert_chain_unchanged(chain)
    assert AuditLog.objects.filter(tenant=tenant_b).count() == audit_count


def test_integrationapihub_tenant_a_admin_gets_404_for_every_foreign_run_route(
    client_a,
    request,
    tenant_b,
    integrationapihub_run_b,
    integrationapihub_job_b,
):
    chain = _integrationapihub_chain_snapshot((integrationapihub_run_b, integrationapihub_job_b))
    audit_count = AuditLog.objects.filter(tenant=tenant_b).count()
    for route, fixture_name in _INTEGRATIONAPIHUB_RUN_FOREIGN_GET:
        target = request.getfixturevalue(fixture_name)
        response = client_a.get(_integrationapihub_url(route, target.pk))
        assert response.status_code == 404
    for route, fixture_name in _INTEGRATIONAPIHUB_RUN_FOREIGN_POST:
        target = request.getfixturevalue(fixture_name)
        response = client_a.post(_integrationapihub_url(route, target.pk), {})
        assert response.status_code == 404
    _integrationapihub_assert_chain_unchanged(chain)
    assert AuditLog.objects.filter(tenant=tenant_b).count() == audit_count


def test_integrationapihub_member_role_gate_precedes_scope_on_foreign_admin_actions(
    member_client,
    tenant_b,
    integrationapihub_connector_b,
    integrationapihub_mapping_b,
    integrationapihub_job_b,
    integrationapihub_run_b,
):
    targets = {
        "integrationapihub_connector_b": integrationapihub_connector_b,
        "integrationapihub_mapping_b": integrationapihub_mapping_b,
        "integrationapihub_job_b": integrationapihub_job_b,
        "integrationapihub_run_b": integrationapihub_run_b,
    }
    chain = _integrationapihub_chain_snapshot(targets.values())
    for route, fixture_name in _INTEGRATIONAPIHUB_ADMIN_POST_ONLY:
        foreign_fixture = {
            "integrationapihub_connector_a": "integrationapihub_connector_b",
            "integrationapihub_mapping_a": "integrationapihub_mapping_b",
            "integrationapihub_job_a": "integrationapihub_job_b",
            "integrationapihub_run_failed_a": "integrationapihub_run_b",
        }[fixture_name]
        target = targets[foreign_fixture]
        response = member_client.post(_integrationapihub_url(route, target.pk), {})
        assert response.status_code == 403, route
    _integrationapihub_assert_chain_unchanged(chain)
    assert AuditLog.objects.filter(tenant=tenant_b).count() == 0


def test_integrationapihub_member_gets_404_for_foreign_login_only_actions(
    member_client,
    tenant_b,
    integrationapihub_connector_b,
    integrationapihub_job_b,
):
    chain = _integrationapihub_chain_snapshot((integrationapihub_connector_b, integrationapihub_job_b))
    for route, fixture_name in _INTEGRATIONAPIHUB_LOGIN_POST_ONLY:
        target = integrationapihub_connector_b if fixture_name == "integrationapihub_connector_a" else integrationapihub_job_b
        response = member_client.post(_integrationapihub_url(route, target.pk), {})
        assert response.status_code == 404, route
    _integrationapihub_assert_chain_unchanged(chain)
    assert AuditLog.objects.filter(tenant=tenant_b).count() == 0


def test_integrationapihub_member_gets_404_for_foreign_read_and_edit_routes(
    member_client,
    integrationapihub_connector_b,
    integrationapihub_mapping_b,
    integrationapihub_job_b,
    integrationapihub_run_b,
):
    routes = (
        ("ixc_detail", integrationapihub_connector_b),
        ("ixc_edit", integrationapihub_connector_b),
        ("connector_health", integrationapihub_connector_b),
        ("ixm_detail", integrationapihub_mapping_b),
        ("ixm_edit", integrationapihub_mapping_b),
        ("syj_detail", integrationapihub_job_b),
        ("syj_edit", integrationapihub_job_b),
        ("syr_detail", integrationapihub_run_b),
    )
    for route, target in routes:
        response = member_client.get(_integrationapihub_url(route, target.pk))
        assert response.status_code == 404, route


def test_integrationapihub_all_registers_boards_and_aggregates_are_tenant_scoped(
    client_a,
    integrationapihub_project_a,
    integrationapihub_project_b,
    integrationapihub_connector_a,
    integrationapihub_connector_b,
    integrationapihub_mapping_a,
    integrationapihub_mapping_b,
    integrationapihub_job_a,
    integrationapihub_job_b,
    integrationapihub_run_a,
    integrationapihub_run_failed_a,
    integrationapihub_run_b,
    workflowautomation_webhook_b,
):
    tokens = _integrationapihub_tokenize_tenant_b(
        integrationapihub_project_b,
        integrationapihub_connector_b,
        integrationapihub_mapping_b,
        integrationapihub_job_b,
        integrationapihub_run_b,
        workflowautomation_webhook_b,
    )
    connector_list = client_a.get(_integrationapihub_url("ixc_list"))
    assert connector_list.status_code == 200
    assert set(_integrationapihub_context_pks(connector_list, "connectors")) == {integrationapihub_connector_a.pk}
    assert set(_integrationapihub_context_pks(connector_list, "projects")) == {integrationapihub_project_a.pk}
    assert connector_list.context["stats"] == {
        "total": 1,
        "active": 1,
        "connected": 1,
        "error": 0,
        "unverified": 0,
    }
    _integrationapihub_assert_no_tokens(connector_list, tokens)

    for route, domain in (
        ("ixc_erp_list", "erp"),
        ("ixc_crm_list", "crm"),
        ("ixc_hris_list", "hris"),
        ("ixc_devops_list", "devops"),
        ("ixc_storage_list", "storage"),
    ):
        response = client_a.get(_integrationapihub_url(route))
        assert response.status_code == 200
        assert response.context["domain"] == domain
        assert set(_integrationapihub_context_pks(response, "connectors")) == ({integrationapihub_connector_a.pk} if domain == "erp" else set())
        _integrationapihub_assert_no_tokens(response, tokens)

    mapping_list = client_a.get(_integrationapihub_url("ixm_list"))
    assert mapping_list.status_code == 200
    assert set(_integrationapihub_context_pks(mapping_list, "mappings")) == {integrationapihub_mapping_a.pk}
    assert set(_integrationapihub_context_pks(mapping_list, "connectors")) == {integrationapihub_connector_a.pk}
    _integrationapihub_assert_no_tokens(mapping_list, tokens)

    job_list = client_a.get(_integrationapihub_url("syj_list"))
    assert job_list.status_code == 200
    assert set(_integrationapihub_context_pks(job_list, "jobs")) == {integrationapihub_job_a.pk}
    assert set(_integrationapihub_context_pks(job_list, "connectors")) == {integrationapihub_connector_a.pk}
    assert job_list.context["stats"] == {"total": 1, "active": 1, "inactive": 0, "runs_total": 2}
    _integrationapihub_assert_no_tokens(job_list, tokens)

    run_list = client_a.get(_integrationapihub_url("syr_list"))
    assert run_list.status_code == 200
    assert set(_integrationapihub_context_pks(run_list, "runs")) == {integrationapihub_run_a.pk, integrationapihub_run_failed_a.pk}
    assert set(_integrationapihub_context_pks(run_list, "jobs")) == {integrationapihub_job_a.pk}
    assert set(_integrationapihub_context_pks(run_list, "connectors")) == {integrationapihub_connector_a.pk}
    assert run_list.context["stats"] == {
        "pending": 0,
        "running": 0,
        "failed": 1,
        "partial": 0,
        "simulated": 1,
        "failed_today": 1,
    }
    _integrationapihub_assert_no_tokens(run_list, tokens)

    monitor = client_a.get(_integrationapihub_url("sync_monitor"))
    assert monitor.status_code == 200
    assert set(_integrationapihub_context_pks(monitor, "runs")) == {integrationapihub_run_a.pk, integrationapihub_run_failed_a.pk}
    assert set(_integrationapihub_context_pks(monitor, "jobs")) == {integrationapihub_job_a.pk}
    assert set(_integrationapihub_context_pks(monitor, "connectors")) == {integrationapihub_connector_a.pk}
    assert monitor.context["stats"] == {"total": 2, "failed": 1, "success": 0, "simulated": 1, "failed_today": 1}
    _integrationapihub_assert_no_tokens(monitor, tokens)

    hub = client_a.get(_integrationapihub_url("integration_hub"))
    assert hub.status_code == 200
    assert set(_integrationapihub_context_pks(hub, "connectors")) == {integrationapihub_connector_a.pk}
    assert set(_integrationapihub_context_pks(hub, "recent_runs")) == {integrationapihub_run_a.pk, integrationapihub_run_failed_a.pk}
    assert set(_integrationapihub_context_pks(hub, "projects")) == {integrationapihub_project_a.pk}
    assert hub.context["stats"]["connectors_total"] == 1
    assert hub.context["stats"]["jobs_active"] == 1
    assert hub.context["stats"]["mappings_total"] == 1
    assert hub.context["stats"]["failed_today"] == 1
    assert hub.context["stats"]["runs_today"] == 2
    assert hub.context["stats"]["by_domain"] == {"erp": 1}
    assert hub.context["stats"]["by_status"] == {"connected": 1}
    domain_rows = {row["value"]: row for row in hub.context["domains"]}
    assert domain_rows["erp"]["total"] == 1
    assert domain_rows["erp"]["connected"] == 1
    assert all(domain_rows[value]["total"] == 0 for value in ("crm", "hris", "devops", "storage", "custom"))
    _integrationapihub_assert_no_tokens(hub, tokens)

    health = client_a.get(_integrationapihub_url("connector_health", integrationapihub_connector_a.pk))
    assert health.status_code == 200
    assert health.context["connector"] == integrationapihub_connector_a
    assert set(_integrationapihub_context_pks(health, "recent_runs")) == {integrationapihub_run_a.pk, integrationapihub_run_failed_a.pk}
    assert health.context["jobs_count"] == 1
    assert health.context["mappings_count"] == 1
    assert health.context["stats"] == {
        "total_runs": 2,
        "failed_runs": 1,
        "success_rate": 0,
        "last_success_at": None,
    }
    _integrationapihub_assert_no_tokens(health, tokens)


def test_integrationapihub_detail_child_chains_are_tenant_scoped(
    client_a,
    integrationapihub_connector_a,
    integrationapihub_connector_b,
    integrationapihub_mapping_a,
    integrationapihub_mapping_b,
    integrationapihub_job_a,
    integrationapihub_job_b,
    integrationapihub_run_a,
    integrationapihub_run_failed_a,
    integrationapihub_run_b,
):
    connector_detail = client_a.get(_integrationapihub_url("ixc_detail", integrationapihub_connector_a.pk))
    assert connector_detail.status_code == 200
    assert connector_detail.context["connector"] == integrationapihub_connector_a
    assert set(_integrationapihub_context_pks(connector_detail, "mappings")) == {integrationapihub_mapping_a.pk}
    assert set(_integrationapihub_context_pks(connector_detail, "jobs")) == {integrationapihub_job_a.pk}
    assert set(_integrationapihub_context_pks(connector_detail, "recent_runs")) == {integrationapihub_run_a.pk, integrationapihub_run_failed_a.pk}
    assert connector_detail.context["mappings_total"] == 1
    assert integrationapihub_connector_b.pk not in {row.pk for row in connector_detail.context["mappings"]}
    assert integrationapihub_job_b.pk not in {row.pk for row in connector_detail.context["jobs"]}
    assert integrationapihub_run_b.pk not in {row.pk for row in connector_detail.context["recent_runs"]}

    mapping_detail = client_a.get(_integrationapihub_url("ixm_detail", integrationapihub_mapping_a.pk))
    assert mapping_detail.status_code == 200
    assert mapping_detail.context["mapping"] == integrationapihub_mapping_a
    assert mapping_detail.context["mapping"].connector == integrationapihub_connector_a

    job_detail = client_a.get(_integrationapihub_url("syj_detail", integrationapihub_job_a.pk))
    assert job_detail.status_code == 200
    assert job_detail.context["job"] == integrationapihub_job_a
    assert job_detail.context["connector"] == integrationapihub_connector_a
    assert set(_integrationapihub_context_pks(job_detail, "runs")) == {integrationapihub_run_a.pk, integrationapihub_run_failed_a.pk}
    assert integrationapihub_run_b.pk not in {row.pk for row in job_detail.context["runs"]}

    run_detail = client_a.get(_integrationapihub_url("syr_detail", integrationapihub_run_a.pk))
    assert run_detail.status_code == 200
    assert run_detail.context["run"] == integrationapihub_run_a
    assert run_detail.context["run"].job == integrationapihub_job_a
    assert run_detail.context["run"].job.connector == integrationapihub_connector_a


def test_integrationapihub_filters_cannot_cross_tenant_boundaries(
    client_a,
    integrationapihub_project_b,
    integrationapihub_connector_a,
    integrationapihub_connector_b,
    integrationapihub_mapping_a,
    integrationapihub_mapping_b,
    integrationapihub_job_a,
    integrationapihub_job_b,
    integrationapihub_run_a,
    integrationapihub_run_failed_a,
    integrationapihub_run_b,
    workflowautomation_webhook_b,
):
    tokens = _integrationapihub_tokenize_tenant_b(
        integrationapihub_project_b,
        integrationapihub_connector_b,
        integrationapihub_mapping_b,
        integrationapihub_job_b,
        integrationapihub_run_b,
        workflowautomation_webhook_b,
    )
    empty_cases = (
        ("ixc_list", "connectors", {"project": str(integrationapihub_project_b.pk)}),
        ("ixc_list", "connectors", {"q": "B_ONLY_CONNECTOR_TOKEN"}),
        ("ixm_list", "mappings", {"connector": str(integrationapihub_connector_b.pk)}),
        ("ixm_list", "mappings", {"q": "B_ONLY_MAPPING_TOKEN"}),
        ("syj_list", "jobs", {"connector": str(integrationapihub_connector_b.pk)}),
        ("syj_list", "jobs", {"q": "B_ONLY_JOB_TOKEN"}),
        ("syr_list", "runs", {"job": str(integrationapihub_job_b.pk)}),
        ("syr_list", "runs", {"connector": str(integrationapihub_connector_b.pk)}),
        ("syr_list", "runs", {"status": "success"}),
        ("syr_list", "runs", {"trigger_source": "schedule"}),
        ("syr_list", "runs", {"q": "B_ONLY_ERROR_MESSAGE"}),
        ("sync_monitor", "runs", {"job": str(integrationapihub_job_b.pk)}),
        ("sync_monitor", "runs", {"connector": str(integrationapihub_connector_b.pk)}),
        ("sync_monitor", "runs", {"status": "success"}),
        ("sync_monitor", "runs", {"trigger_source": "schedule"}),
        ("sync_monitor", "runs", {"q": "B_ONLY_ERROR_MESSAGE"}),
    )
    for route, key, params in empty_cases:
        response = client_a.get(_integrationapihub_url(route), params)
        ignored_values = params.values() if "q" in params else ()
        _integrationapihub_assert_empty_filter(response, key, tokens, ignored_values)
        if route == "syr_list":
            expected = {
                "pending": 0,
                "running": 0,
                "failed": 1,
                "partial": 0,
                "simulated": 1,
                "failed_today": 1,
            }
            assert response.context["stats"] == expected
        elif route == "sync_monitor":
            expected = {"total": 2, "failed": 1, "success": 0, "simulated": 1, "failed_today": 1}
            assert response.context["stats"] == expected

    connector = client_a.get(
        _integrationapihub_url("ixc_list"),
        {"q": "Acme ERP connector", "status": "connected", "provider": "sap", "is_active": "active"},
    )
    assert connector.status_code == 200
    assert set(_integrationapihub_context_pks(connector, "connectors")) == {integrationapihub_connector_a.pk}

    mapping = client_a.get(
        _integrationapihub_url("ixm_list"),
        {"connector": str(integrationapihub_connector_a.pk), "direction": "to_remote", "transform": "upper"},
    )
    assert mapping.status_code == 200
    assert set(_integrationapihub_context_pks(mapping, "mappings")) == {integrationapihub_mapping_a.pk}

    job = client_a.get(
        _integrationapihub_url("syj_list"),
        {"connector": str(integrationapihub_connector_a.pk), "entity_scope": "tasks", "trigger_mode": "scheduled", "is_active": "active"},
    )
    assert job.status_code == 200
    assert set(_integrationapihub_context_pks(job, "jobs")) == {integrationapihub_job_a.pk}

    for route in ("syr_list", "sync_monitor"):
        response = client_a.get(
            _integrationapihub_url(route),
            {"job": str(integrationapihub_job_a.pk), "connector": str(integrationapihub_connector_a.pk), "status": "simulated", "trigger_source": "manual"},
        )
        assert response.status_code == 200
        assert set(_integrationapihub_context_pks(response, "runs")) == {integrationapihub_run_a.pk}
        response = client_a.get(
            _integrationapihub_url(route),
            {"job": str(integrationapihub_job_a.pk), "status": "failed", "trigger_source": "event"},
        )
        assert response.status_code == 200
        assert set(_integrationapihub_context_pks(response, "runs")) == {integrationapihub_run_failed_a.pk}
        _integrationapihub_assert_no_tokens(response, tokens)


def test_integrationapihub_widened_foreign_form_querysets_are_rejected(
    tenant_a,
    integrationapihub_project_a,
    integrationapihub_project_b,
    integrationapihub_connector_b,
    workflowautomation_webhook_b,
):
    project_form = ProjectIntegrationConnectorForm(
        _integrationapihub_connector_payload(
            project=integrationapihub_project_b,
            name="Widened foreign project",
        ),
        tenant=tenant_a,
    )
    _integrationapihub_widen(project_form, "project")
    assert not project_form.is_valid()
    assert project_form.errors["project"] == ["That record belongs to another workspace."]

    webhook_form = ProjectIntegrationConnectorForm(
        _integrationapihub_connector_payload(
            project=integrationapihub_project_a,
            notify_webhook=str(workflowautomation_webhook_b.pk),
            name="Widened foreign webhook",
        ),
        tenant=tenant_a,
    )
    _integrationapihub_widen(webhook_form, "notify_webhook")
    assert not webhook_form.is_valid()
    assert webhook_form.errors["notify_webhook"] == ["That record belongs to another workspace."]

    mapping_form = ConnectorFieldMappingForm(
        _integrationapihub_mapping_payload(
            integrationapihub_connector_b,
            local_field="task.widened.foreign.connector",
        ),
        tenant=tenant_a,
    )
    _integrationapihub_widen(mapping_form, "connector")
    assert not mapping_form.is_valid()
    assert mapping_form.errors["connector"] == ["That record belongs to another workspace."]

    job_form = ProjectSyncJobForm(
        _integrationapihub_job_payload(
            integrationapihub_connector_b,
            name="Widened foreign job connector",
        ),
        tenant=tenant_a,
    )
    _integrationapihub_widen(job_form, "connector")
    assert not job_form.is_valid()
    assert job_form.errors["connector"] == ["That record belongs to another workspace."]


def test_integrationapihub_model_clean_rejects_every_cross_tenant_fk(
    tenant_a,
    integrationapihub_project_a,
    integrationapihub_project_b,
    integrationapihub_connector_b,
    integrationapihub_job_b,
    workflowautomation_webhook_b,
):
    cases = (
        (ProjectIntegrationConnector(tenant=tenant_a, project=integrationapihub_project_b, name="Model foreign project"), "project"),
        (ProjectIntegrationConnector(tenant=tenant_a, project=integrationapihub_project_a, notify_webhook=workflowautomation_webhook_b, name="Model foreign webhook"), "notify_webhook"),
        (ConnectorFieldMapping(tenant=tenant_a, connector=integrationapihub_connector_b, local_field="model.foreign", remote_field="model.remote"), "connector"),
        (ProjectSyncJob(tenant=tenant_a, connector=integrationapihub_connector_b, name="Model foreign job"), "connector"),
        (ProjectSyncRun(tenant=tenant_a, job=integrationapihub_job_b), "job"),
    )
    for obj, field_name in cases:
        with pytest.raises(ValidationError) as error:
            obj.clean()
        assert field_name in error.value.message_dict


def test_integrationapihub_connector_owner_scoping_and_tenantless_owner_queryset(
    tenant_a,
    admin_user,
    member_user,
    admin_b,
):
    inactive = _integrationapihub_inactive_user(tenant_a)
    form = ProjectIntegrationConnectorForm(tenant=tenant_a)
    owner_pks = set(form.fields["owner"].queryset.values_list("pk", flat=True))
    assert admin_user.pk in owner_pks
    assert member_user.pk in owner_pks
    assert inactive.pk not in owner_pks
    assert admin_b.pk not in owner_pks
    assert admin_b.email not in str(form["owner"])

    foreign_owner_form = ProjectIntegrationConnectorForm(
        _integrationapihub_connector_payload(owner=admin_b, name="Foreign owner form"),
        tenant=tenant_a,
    )
    assert not foreign_owner_form.is_valid()
    assert "owner" in foreign_owner_form.errors

    inactive_owner_form = ProjectIntegrationConnectorForm(
        _integrationapihub_connector_payload(owner=inactive, name="Inactive owner form"),
        tenant=tenant_a,
    )
    assert not inactive_owner_form.is_valid()
    assert "owner" in inactive_owner_form.errors

    tenantless_form = ProjectIntegrationConnectorForm(tenant=None)
    assert list(tenantless_form.fields["owner"].queryset) == []


def test_integrationapihub_tenantless_reads_are_empty_and_foreign_pks_are_404(
    projectinitiation_tenantless_client,
    integrationapihub_connector_a,
    integrationapihub_connector_b,
    integrationapihub_mapping_a,
    integrationapihub_mapping_b,
    integrationapihub_job_a,
    integrationapihub_job_b,
    integrationapihub_run_b,
):
    list_cases = (
        ("ixc_list", "connectors"),
        ("ixc_erp_list", "connectors"),
        ("ixc_crm_list", "connectors"),
        ("ixm_list", "mappings"),
        ("syj_list", "jobs"),
        ("syr_list", "runs"),
        ("sync_monitor", "runs"),
    )
    for route, key in list_cases:
        response = projectinitiation_tenantless_client.get(_integrationapihub_url(route))
        assert response.status_code == 200
        assert list(response.context[key]) == []
        assert integrationapihub_connector_a.name not in _integrationapihub_body(response)
        assert integrationapihub_connector_b.name not in _integrationapihub_body(response)
        assert integrationapihub_job_b.name not in _integrationapihub_body(response)
        assert integrationapihub_run_b.number not in _integrationapihub_body(response)

    hub = projectinitiation_tenantless_client.get(_integrationapihub_url("integration_hub"))
    assert hub.status_code == 200
    assert hub.context["stats"]["connectors_total"] == 0
    assert hub.context["stats"]["jobs_active"] == 0
    assert hub.context["stats"]["mappings_total"] == 0
    assert list(hub.context["connectors"]) == []
    assert list(hub.context["recent_runs"]) == []

    monitor = projectinitiation_tenantless_client.get(_integrationapihub_url("sync_monitor"))
    assert monitor.status_code == 200
    assert monitor.context["stats"] == {"total": 0, "failed": 0, "success": 0, "simulated": 0, "failed_today": 0}
    assert list(monitor.context["runs"]) == []

    read_targets = (
        ("ixc_detail", integrationapihub_connector_b),
        ("ixc_edit", integrationapihub_connector_b),
        ("connector_health", integrationapihub_connector_b),
        ("ixm_detail", integrationapihub_mapping_b),
        ("ixm_edit", integrationapihub_mapping_b),
        ("syj_detail", integrationapihub_job_b),
        ("syj_edit", integrationapihub_job_b),
        ("syr_detail", integrationapihub_run_b),
    )
    for route, target in read_targets:
        response = projectinitiation_tenantless_client.get(_integrationapihub_url(route, target.pk))
        assert response.status_code == 404, route


def test_integrationapihub_tenantless_action_gates_match_decorator_order(
    projectinitiation_tenantless_client,
    integrationapihub_connector_a,
    integrationapihub_mapping_a,
    integrationapihub_job_a,
    integrationapihub_run_failed_a,
):
    for route, target in (
        ("ixc_delete", integrationapihub_connector_a),
        ("ixc_rotate_credential", integrationapihub_connector_a),
        ("ixm_delete", integrationapihub_mapping_a),
        ("syj_delete", integrationapihub_job_a),
        ("syr_retry", integrationapihub_run_failed_a),
    ):
        assert projectinitiation_tenantless_client.get(_integrationapihub_url(route, target.pk)).status_code == 405
        assert projectinitiation_tenantless_client.post(_integrationapihub_url(route, target.pk), {}).status_code == 403
    for route, target in (
        ("ixc_test", integrationapihub_connector_a),
        ("ixc_toggle_active", integrationapihub_connector_a),
        ("syj_run", integrationapihub_job_a),
        ("syj_toggle_active", integrationapihub_job_a),
    ):
        assert projectinitiation_tenantless_client.post(_integrationapihub_url(route, target.pk), {}).status_code == 404


@pytest.mark.parametrize(
    "route,field_names",
    (
        ("ixc_create", ("project", "notify_webhook", "owner")),
        ("ixm_create", ("connector",)),
        ("syj_create", ("connector",)),
    ),
)
def test_integrationapihub_tenantless_create_forms_do_not_disclose_foreign_options(
    projectinitiation_tenantless_client,
    integrationapihub_project_a,
    integrationapihub_project_b,
    integrationapihub_connector_a,
    integrationapihub_connector_b,
    workflowautomation_webhook_b,
    route,
    field_names,
):
    response = projectinitiation_tenantless_client.get(_integrationapihub_url(route))
    assert response.status_code in (200, 302)
    tokens = (
        integrationapihub_project_a.name,
        integrationapihub_project_b.name,
        integrationapihub_connector_a.name,
        integrationapihub_connector_b.name,
        workflowautomation_webhook_b.name,
    )
    _integrationapihub_assert_no_tokens(response, tokens)
    if response.status_code == 200:
        form = response.context["form"]
        for field_name in field_names:
            assert list(form.fields[field_name].queryset) == [], (route, field_name)


def test_integrationapihub_credential_plaintext_is_absent_from_pages_audit_and_flash(
    client_a,
    tenant_a,
    admin_user,
    integrationapihub_project_a,
    integrationapihub_connector_credential_a,
):
    raw = "provider-secret-1234"
    connector = integrationapihub_connector_credential_a
    assert connector.credential != raw
    assert is_encrypted(connector.credential)
    assert connector.get_credential() == raw

    for route, target in (
        ("ixc_list", None),
        ("ixc_detail", connector),
        ("ixc_edit", connector),
    ):
        url = _integrationapihub_url(route) if target is None else _integrationapihub_url(route, target.pk)
        response = client_a.get(url)
        assert response.status_code == 200
        assert raw not in _integrationapihub_body(response)
        if route == "ixc_edit":
            assert raw not in str(response.context["form"]["credential"])

    new_raw = "provider-secret-created-9876"
    response = client_a.post(
        _integrationapihub_url("ixc_create"),
        _integrationapihub_connector_payload(
            project=integrationapihub_project_a,
            owner=admin_user,
            name="Security credential create",
            credential=new_raw,
        ),
    )
    assert response.status_code == 302
    created = ProjectIntegrationConnector.objects.get(tenant=tenant_a, name="Security credential create")
    assert created.get_credential() == new_raw
    assert is_encrypted(created.credential)
    assert new_raw not in created.credential
    assert new_raw not in _integrationapihub_body(response)
    for message in _integrationapihub_messages(response):
        assert new_raw not in message
    for audit in _integrationapihub_audits(ProjectIntegrationConnector, created.pk, "create"):
        serialized = json.dumps({"target": audit.target, "changes": audit.changes}, default=str)
        assert new_raw not in serialized


def test_integrationapihub_credential_rotation_reveals_once_without_audit_or_flash_leak(
    client_a,
    integrationapihub_connector_credential_a,
):
    connector = integrationapihub_connector_credential_a
    old_raw = connector.get_credential()
    response = client_a.post(_integrationapihub_url("ixc_rotate_credential", connector.pk), {})
    assert response.status_code == 302
    connector.refresh_from_db()
    new_raw = connector.get_credential()
    assert new_raw != old_raw
    assert len(new_raw) == 64
    assert is_encrypted(connector.credential)
    assert new_raw not in connector.credential
    assert new_raw not in _integrationapihub_body(response)
    for message in _integrationapihub_messages(response):
        assert new_raw not in message
    for audit in _integrationapihub_audits(ProjectIntegrationConnector, connector.pk, "rotate"):
        serialized = json.dumps({"target": audit.target, "changes": audit.changes}, default=str)
        assert new_raw not in serialized
    assert client_a.session["_ixc_cred_reveal"] == {"pk": connector.pk, "credential": new_raw}

    first = client_a.get(_integrationapihub_url("ixc_detail", connector.pk))
    assert first.status_code == 200
    assert first.context["revealed_credential"] == new_raw
    assert new_raw in _integrationapihub_body(first)
    assert "_ixc_cred_reveal" not in client_a.session

    second = client_a.get(_integrationapihub_url("ixc_detail", connector.pk))
    assert second.status_code == 200
    assert second.context["revealed_credential"] is None
    assert new_raw not in _integrationapihub_body(second)


def test_integrationapihub_simulated_actions_perform_no_network_io(
    monkeypatch,
    client_a,
    integrationapihub_connector_a,
    integrationapihub_job_a,
    integrationapihub_run_failed_a,
):
    _integrationapihub_forbid_network(monkeypatch)
    actions = (
        ("ixc_test", integrationapihub_connector_a, {"note": "simulated security check"}),
        ("syj_run", integrationapihub_job_a, {}),
        ("syr_retry", integrationapihub_run_failed_a, {}),
    )
    for route, target, data in actions:
        response = client_a.post(_integrationapihub_url(route, target.pk), data)
        assert response.status_code == 302, route
