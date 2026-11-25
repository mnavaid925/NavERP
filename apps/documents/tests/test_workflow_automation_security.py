"""Security, IDOR, RBAC, SSRF, HMAC, CSRF, and legal-hold tests for Sub-module 13.11 (Workflow Automation & BPM)."""
import json
import time
import pytest

from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import Client
from django.urls import reverse

from apps.documents.models.RecordsManagement.DocumentLegalHolds import DocumentLegalHold
from apps.documents.models.RecordsManagement.RecordDeclarations import RecordDeclaration
from apps.documents.models.RecordsManagement.RetentionSchedules import RetentionSchedule
from apps.documents.models.WorkflowAutomation.DocumentProcessDefinitions import (
    DocumentProcessDefinition,
)
from apps.documents.models.WorkflowAutomation.DocumentProcessInstances import (
    DocumentProcessInstance,
)
from apps.documents.models.WorkflowAutomation.DocumentRoutingRules import DocumentRoutingRule
from apps.documents.models.WorkflowAutomation.DocumentWebhookTriggers import (
    DocumentWebhookTrigger,
)
from apps.documents.services.workflow_automation import (
    dispatch_simulated_webhook,
    evaluate_routing_rules,
    validate_dms_webhook_url,
    validate_flat_headers,
    validate_safe_regex,
)

pytestmark = pytest.mark.django_db


def _workflow_automation_valid_webhook_post(**overrides):
    data = {
        "name": "Sec Check Hook",
        "direction": "outbound_webhook",
        "trigger_event": "process.completed",
        "target_url": "https://hooks.partner-erp.example/sec",
        "http_method": "post",
        "payload_format": "json",
        "custom_headers": "{}",
        "payload_template_json": "{}",
        "retry_policy_max": "3",
        "is_active": "on",
    }
    data.update(overrides)
    return data


# ---------------------------------------------------------------------------
# 1. Authentication & Superuser tenant=None Isolation
# ---------------------------------------------------------------------------


def test_workflow_automation_unauthenticated_redirects_to_login(
    client,
    process_definition,
    routing_rule,
    process_instance,
    webhook_trigger,
):
    get_urls = [
        reverse("documents:process_definition_list"),
        reverse("documents:process_definition_create"),
        reverse("documents:process_definition_detail", args=[process_definition.pk]),
        reverse("documents:process_definition_edit", args=[process_definition.pk]),
        reverse("documents:process_definition_designer", args=[process_definition.pk]),
        reverse("documents:routing_rule_list"),
        reverse("documents:routing_rule_create"),
        reverse("documents:routing_rule_simulator"),
        reverse("documents:routing_rule_detail", args=[routing_rule.pk]),
        reverse("documents:routing_rule_edit", args=[routing_rule.pk]),
        reverse("documents:process_instance_list"),
        reverse("documents:process_instance_create"),
        reverse("documents:process_instance_detail", args=[process_instance.pk]),
        reverse("documents:process_instance_edit", args=[process_instance.pk]),
        reverse("documents:webhook_trigger_list"),
        reverse("documents:webhook_trigger_create"),
        reverse("documents:webhook_trigger_detail", args=[webhook_trigger.pk]),
        reverse("documents:webhook_trigger_edit", args=[webhook_trigger.pk]),
        reverse("documents:process_analytics_dashboard"),
    ]
    for url in get_urls:
        res = client.get(url)
        assert res.status_code == 302, f"Expected 302 login redirect for unauth GET {url}, got {res.status_code}"
        assert "login" in res.url.lower()

    post_urls = [
        reverse("documents:process_definition_publish", args=[process_definition.pk]),
        reverse("documents:routing_rule_toggle", args=[routing_rule.pk]),
        reverse("documents:process_instance_cancel", args=[process_instance.pk]),
        reverse("documents:webhook_trigger_rotate_secret", args=[webhook_trigger.pk]),
        reverse("documents:webhook_trigger_test_ping", args=[webhook_trigger.pk]),
    ]
    for url in post_urls:
        res = client.post(url)
        assert res.status_code == 302
        assert "login" in res.url.lower()


def test_workflow_automation_superuser_without_tenant_sees_empty_scoped_data(
    tenant_a,
    process_definition,
    routing_rule,
    process_instance,
    webhook_trigger,
):
    User = get_user_model()
    su = User.objects.create_user(
        username="root_no_tenant_bpm",
        email="root_no_tenant_bpm@naverp.test",
        password="Password123!",
        tenant=None,
        is_superuser=True,
        is_staff=True,
    )
    c_su = Client(HTTP_HOST="localhost")
    c_su.force_login(su)

    for url_name, ctx_list_key, leaked_name in (
        ("documents:process_definition_list", "process_definitions", process_definition.number),
        ("documents:routing_rule_list", "routing_rules", routing_rule.number),
        ("documents:process_instance_list", "instances", process_instance.number),
        ("documents:webhook_trigger_list", "webhooks", webhook_trigger.number),
    ):
        res = c_su.get(reverse(url_name))
        assert res.status_code == 200
        assert len(res.context[ctx_list_key]) == 0
        assert res.context["total_count"] == 0
        assert leaked_name not in res.content.decode("utf-8")

    # Analytics dashboard returns 0 instances for tenant=None
    res_ana = c_su.get(reverse("documents:process_analytics_dashboard"))
    assert res_ana.status_code == 200
    assert res_ana.context["analytics"]["total_instances"] == 0
    assert res_ana.context["process_definitions"].count() == 0

    # Create & simulator forms reset all tenant-scoped FK querysets to .none()
    for url_name, form_key, fk_fields in (
        ("documents:process_definition_create", "form", ("target_folder", "department", "core_workflow_ref")),
        ("documents:routing_rule_create", "form", ("process_definition", "source_folder", "route_to_user")),
        ("documents:routing_rule_simulator", "form", ("document", "rule")),
        ("documents:process_instance_create", "form", ("process_definition", "document", "version", "current_assignee")),
        ("documents:webhook_trigger_create", "form", ("process_definition", "connector_ref")),
    ):
        res = c_su.get(reverse(url_name))
        assert res.status_code == 200
        form = res.context[form_key]
        for fname in fk_fields:
            assert form.fields[fname].queryset.count() == 0


# ---------------------------------------------------------------------------
# 2. Cross-Tenant IDOR Isolation (client_b targeting tenant_a PKs -> 404)
# ---------------------------------------------------------------------------


def test_workflow_automation_cross_tenant_idor_returns_404_across_all_endpoints(
    client_b,
    tenant_b,
    admin_b,
    process_definition,
    draft_process_definition,
    routing_rule,
    process_instance,
    webhook_trigger,
    document,
):
    get_idor_urls = [
        (reverse("documents:process_definition_detail", args=[process_definition.pk]), process_definition.number),
        (reverse("documents:process_definition_edit", args=[draft_process_definition.pk]), draft_process_definition.number),
        (reverse("documents:process_definition_designer", args=[process_definition.pk]), process_definition.number),
        (reverse("documents:routing_rule_detail", args=[routing_rule.pk]), routing_rule.number),
        (reverse("documents:routing_rule_edit", args=[routing_rule.pk]), routing_rule.number),
        (reverse("documents:process_instance_detail", args=[process_instance.pk]), process_instance.number),
        (reverse("documents:process_instance_edit", args=[process_instance.pk]), process_instance.number),
        (reverse("documents:webhook_trigger_detail", args=[webhook_trigger.pk]), webhook_trigger.number),
        (reverse("documents:webhook_trigger_edit", args=[webhook_trigger.pk]), webhook_trigger.number),
    ]
    for url, secret_marker in get_idor_urls:
        res = client_b.get(url)
        assert res.status_code == 404, f"IDOR leak on GET {url}: got {res.status_code}"
        assert secret_marker not in res.content.decode("utf-8")

    post_idor_cases = [
        (reverse("documents:process_definition_edit", args=[draft_process_definition.pk]), {"name": "Hijacked"}),
        (reverse("documents:process_definition_designer", args=[draft_process_definition.pk]), {"nodes_json": "[]"}),
        (reverse("documents:process_definition_delete", args=[draft_process_definition.pk]), {}),
        (reverse("documents:process_definition_publish", args=[draft_process_definition.pk]), {}),
        (reverse("documents:process_definition_deprecate", args=[process_definition.pk]), {}),
        (reverse("documents:routing_rule_edit", args=[routing_rule.pk]), {"name": "Hijacked"}),
        (reverse("documents:routing_rule_delete", args=[routing_rule.pk]), {}),
        (reverse("documents:routing_rule_toggle", args=[routing_rule.pk]), {}),
        (reverse("documents:process_instance_edit", args=[process_instance.pk]), {}),
        (reverse("documents:process_instance_delete", args=[process_instance.pk]), {}),
        (reverse("documents:process_instance_advance", args=[process_instance.pk]), {"outcome": "completed"}),
        (reverse("documents:process_instance_cancel", args=[process_instance.pk]), {}),
        (reverse("documents:webhook_trigger_edit", args=[webhook_trigger.pk]), _workflow_automation_valid_webhook_post()),
        (reverse("documents:webhook_trigger_delete", args=[webhook_trigger.pk]), {}),
        (reverse("documents:webhook_trigger_rotate_secret", args=[webhook_trigger.pk]), {}),
        (reverse("documents:webhook_trigger_test_ping", args=[webhook_trigger.pk]), {"event_override": "hijack"}),
        (reverse("documents:webhook_trigger_simulate_inbound", args=[webhook_trigger.pk]), {"document_id": str(document.pk)}),
    ]
    for url, payload in post_idor_cases:
        res = client_b.post(url, data=payload)
        assert res.status_code == 404, f"IDOR mutation permitted on POST {url}: got {res.status_code}"

    # Verify tenant_a objects remain completely untouched
    draft_process_definition.refresh_from_db()
    assert draft_process_definition.status == "draft"
    process_definition.refresh_from_db()
    assert process_definition.status == "published"
    routing_rule.refresh_from_db()
    assert routing_rule.is_active is True
    process_instance.refresh_from_db()
    assert process_instance.status == "running"
    webhook_trigger.refresh_from_db()
    assert webhook_trigger.fire_count == 0

    # Cross-tenant simulator / ping / simulate_inbound / analytics filtering with foreign PKs
    wh_b = DocumentWebhookTrigger.objects.create(
        tenant=tenant_b,
        name="Tenant B Inbound",
        direction="inbound_webhook",
        trigger_event="inbound.trigger",
        is_active=True,
        owner=admin_b,
    )
    res_b_sim = client_b.post(
        reverse("documents:routing_rule_simulator"),
        data={"document": str(document.pk), "rule": str(routing_rule.pk), "apply_mutations": "on"},
    )
    assert res_b_sim.status_code == 200
    assert res_b_sim.context["form"].errors
    assert res_b_sim.context["selected_document"] is None

    res_b_ping = client_b.post(
        reverse("documents:webhook_trigger_test_ping", args=[wh_b.pk]),
        data={"document": str(document.pk)},
    )
    assert res_b_ping.status_code == 302
    wh_b.refresh_from_db()
    assert wh_b.fire_count == 0

    res_b_in = client_b.post(
        reverse("documents:webhook_trigger_simulate_inbound", args=[wh_b.pk]),
        data={"document_id": str(document.pk)},
    )
    assert res_b_in.status_code == 302
    wh_b.refresh_from_db()
    assert wh_b.fire_count == 0

    res_b_ana = client_b.get(
        reverse("documents:process_analytics_dashboard"),
        {"process_definition": str(process_definition.pk)},
    )
    assert res_b_ana.status_code == 200
    assert res_b_ana.context["analytics"]["total_instances"] == 0


# ---------------------------------------------------------------------------
# 3. RBAC / Admin Enforcement, Instance Step Authorization & HTTP 405
# ---------------------------------------------------------------------------


def test_workflow_automation_non_admin_rbac_and_published_blueprint_guards(
    member_client,
    tenant_a,
    admin_user,
    process_definition,
    draft_process_definition,
    routing_rule,
    webhook_trigger,
    document,
):
    forbidden_gets = [
        reverse("documents:routing_rule_create"),
        reverse("documents:routing_rule_edit", args=[routing_rule.pk]),
        reverse("documents:webhook_trigger_create"),
        reverse("documents:webhook_trigger_edit", args=[webhook_trigger.pk]),
        reverse("documents:process_definition_edit", args=[process_definition.pk]),
    ]
    for url in forbidden_gets:
        res = member_client.get(url)
        assert res.status_code == 403, f"Expected 403 for member GET {url}, got {res.status_code}"

    forbidden_posts = [
        (reverse("documents:process_definition_publish", args=[draft_process_definition.pk]), {}),
        (reverse("documents:process_definition_deprecate", args=[process_definition.pk]), {}),
        (reverse("documents:process_definition_delete", args=[draft_process_definition.pk]), {}),
        (reverse("documents:process_definition_edit", args=[process_definition.pk]), {"name": "Hacked"}),
        (reverse("documents:process_definition_designer", args=[process_definition.pk]), {"nodes_json": "[]"}),
        (reverse("documents:routing_rule_create"), {"name": "Member Rule"}),
        (reverse("documents:routing_rule_edit", args=[routing_rule.pk]), {"name": "Member Edit"}),
        (reverse("documents:routing_rule_toggle", args=[routing_rule.pk]), {}),
        (reverse("documents:routing_rule_delete", args=[routing_rule.pk]), {}),
        (reverse("documents:webhook_trigger_create"), _workflow_automation_valid_webhook_post()),
        (reverse("documents:webhook_trigger_edit", args=[webhook_trigger.pk]), _workflow_automation_valid_webhook_post()),
        (reverse("documents:webhook_trigger_delete", args=[webhook_trigger.pk]), {}),
        (reverse("documents:webhook_trigger_rotate_secret", args=[webhook_trigger.pk]), {}),
    ]
    for url, payload in forbidden_posts:
        res = member_client.post(url, data=payload)
        assert res.status_code == 403, f"Expected 403 for member POST {url}, got {res.status_code}"

    queued_inst = DocumentProcessInstance.objects.create(
        tenant=tenant_a,
        process_definition=process_definition,
        document=document,
        status="queued",
        initiated_by=admin_user,
    )
    assert member_client.post(reverse("documents:process_instance_delete", args=[queued_inst.pk])).status_code == 403

    # Non-admin simulator cannot apply live mutations
    orig_tags = document.tags
    res_sim = member_client.post(
        reverse("documents:routing_rule_simulator"),
        data={"document": str(document.pk), "rule": str(routing_rule.pk), "apply_mutations": "on"},
    )
    assert res_sim.status_code == 200
    document.refresh_from_db()
    assert document.tags == orig_tags
    assert any("administrator privileges" in str(m) for m in get_messages(res_sim.wsgi_request))


def test_workflow_automation_instance_step_and_cancel_authorization(
    member_client, member_user, tenant_a, admin_user, process_definition, document
):
    from apps.documents.services.workflow_automation import start_process_instance

    # Instance assigned to admin_user, initiated by admin_user
    inst_admin_owned = start_process_instance(
        tenant=tenant_a,
        process_definition=process_definition,
        document=document,
        actor=admin_user,
        assignee=admin_user,
    )
    assert member_client.post(
        reverse("documents:process_instance_advance", args=[inst_admin_owned.pk]),
        {"outcome": "approved"},
    ).status_code == 403
    assert member_client.post(
        reverse("documents:process_instance_cancel", args=[inst_admin_owned.pk]),
    ).status_code == 403

    # Instance assigned to member_user, initiated by admin_user: member can advance step, NOT force-complete or cancel
    inst_member_assigned = start_process_instance(
        tenant=tenant_a,
        process_definition=process_definition,
        document=document,
        actor=admin_user,
        assignee=member_user,
    )
    assert member_client.post(
        reverse("documents:process_instance_advance", args=[inst_member_assigned.pk]),
        {"outcome": "completed"},
    ).status_code == 403
    assert member_client.post(
        reverse("documents:process_instance_cancel", args=[inst_member_assigned.pk]),
    ).status_code == 403

    # Regular step advance by assigned member_user succeeds
    res_ok = member_client.post(
        reverse("documents:process_instance_advance", args=[inst_member_assigned.pk]),
        {"outcome": "approved", "notes": "Assignee sign-off"},
    )
    assert res_ok.status_code == 302
    inst_member_assigned.refresh_from_db()
    assert inst_member_assigned.current_node_id == "n_gw"


def test_workflow_automation_post_only_endpoints_reject_get_with_405(
    client_a, process_definition, routing_rule, process_instance, webhook_trigger
):
    post_only_urls = [
        reverse("documents:process_definition_delete", args=[process_definition.pk]),
        reverse("documents:process_definition_publish", args=[process_definition.pk]),
        reverse("documents:process_definition_deprecate", args=[process_definition.pk]),
        reverse("documents:routing_rule_delete", args=[routing_rule.pk]),
        reverse("documents:routing_rule_toggle", args=[routing_rule.pk]),
        reverse("documents:process_instance_delete", args=[process_instance.pk]),
        reverse("documents:process_instance_advance", args=[process_instance.pk]),
        reverse("documents:process_instance_cancel", args=[process_instance.pk]),
        reverse("documents:webhook_trigger_delete", args=[webhook_trigger.pk]),
        reverse("documents:webhook_trigger_rotate_secret", args=[webhook_trigger.pk]),
        reverse("documents:webhook_trigger_test_ping", args=[webhook_trigger.pk]),
        reverse("documents:webhook_trigger_simulate_inbound", args=[webhook_trigger.pk]),
    ]
    for url in post_only_urls:
        res = client_a.get(url)
        assert res.status_code == 405, f"Expected 405 Method Not Allowed on GET {url}, got {res.status_code}"


# ---------------------------------------------------------------------------
# 4. HMAC Secret Security, Fail-Closed Decrypt & Pop-Once TTL Cleanup
# ---------------------------------------------------------------------------


def test_workflow_automation_hmac_secret_never_leaks_and_clears_expired_session(
    client_a, tenant_a, webhook_trigger
):
    raw = webhook_trigger.get_signing_secret()
    assert raw
    assert webhook_trigger.signing_secret.startswith("fernet.v1:")
    assert raw not in webhook_trigger.signing_secret

    # List, detail, and edit HTML must never expose raw secret or ciphertext
    for url in (
        reverse("documents:webhook_trigger_list"),
        reverse("documents:webhook_trigger_detail", args=[webhook_trigger.pk]),
        reverse("documents:webhook_trigger_edit", args=[webhook_trigger.pk]),
    ):
        html = client_a.get(url).content.decode("utf-8")
        assert raw not in html
        assert webhook_trigger.signing_secret not in html

    # Django flash messages after rotate_secret do not leak the secret either
    rot_res = client_a.post(reverse("documents:webhook_trigger_rotate_secret", args=[webhook_trigger.pk]))
    assert rot_res.status_code == 302
    webhook_trigger.refresh_from_db()
    rotated_raw = webhook_trigger.get_signing_secret()
    for msg in get_messages(rot_res.wsgi_request):
        assert rotated_raw not in str(msg)
        assert webhook_trigger.signing_secret not in str(msg)

    # Pop-once consumes valid reveal immediately
    detail_url = reverse("documents:webhook_trigger_detail", args=[webhook_trigger.pk])
    assert rotated_raw in client_a.get(detail_url).content.decode("utf-8")
    assert rotated_raw not in client_a.get(detail_url).content.decode("utf-8")

    # Expired reveal (> 120s TTL) & malformed non-dict session entries are purged cleanly without rendering secret
    sess = client_a.session
    sess["_dwhk_secret_reveal"] = {
        "pk": webhook_trigger.pk,
        "secret": "EXPIRED_LEAK_TOKEN_987",
        "created_ts": time.time() - 300,
    }
    sess.save()
    res_exp = client_a.get(detail_url)
    assert "EXPIRED_LEAK_TOKEN_987" not in res_exp.content.decode("utf-8")
    assert "_dwhk_secret_reveal" not in client_a.session

    sess = client_a.session
    sess["_dwhk_secret_reveal"] = "corrupted-non-dict-entry"
    sess.save()
    res_mal = client_a.get(detail_url)
    assert res_mal.status_code == 200
    assert "_dwhk_secret_reveal" not in client_a.session

    # Fail-closed decrypt on tampered ciphertext
    bad_wh = DocumentWebhookTrigger(
        tenant=tenant_a,
        name="Corrupt Secret",
        signing_secret="fernet.v1:not-valid-token",
    )
    with pytest.raises(Exception):
        bad_wh.get_signing_secret()


# ---------------------------------------------------------------------------
# 5. SSRF, Headers, ReDoS, JSON Caps, CSRF, Mass Assignment & Legal Holds
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ssrf_url",
    [
        "http://127.0.0.1/hook",
        "http://[::ffff:127.0.0.1]/hook",
        "http://[64:ff9b::169.254.169.254]/latest",
        "http://169.254.169.254/latest/meta-data/",
        "http://metadata/compute",
        "http://instance-data/",
        "https://10.0.0.1/internal",
        "https://100.64.0.1/cgnat",
        "https://user:pass@hooks.partner-erp.example/cb",
        "ftp://hooks.partner-erp.example/cb",
    ],
)
def test_workflow_automation_ssrf_blocked_in_http_post_and_dispatch(
    client_a, tenant_a, admin_user, ssrf_url
):
    res = client_a.post(
        reverse("documents:webhook_trigger_create"),
        data=_workflow_automation_valid_webhook_post(target_url=ssrf_url),
    )
    assert res.status_code == 200
    assert "target_url" in res.context["form"].errors

    with pytest.raises(Exception):
        validate_dms_webhook_url(ssrf_url)

    # Even if pre-existing DB row holds unsafe target_url, dispatch re-checks at runtime
    persisted_bad = DocumentWebhookTrigger.objects.create(
        tenant=tenant_a,
        name="Bypass DB Row",
        direction="outbound_webhook",
        trigger_event="process.completed",
        target_url=ssrf_url,
        owner=admin_user,
    )
    with pytest.raises(Exception):
        dispatch_simulated_webhook(persisted_bad, "process.completed", {"x": 1}, actor=admin_user)


def test_workflow_automation_header_spoofing_redos_json_caps_and_mass_assignment(
    client_a, tenant_a, draft_process_definition
):
    # CRLF and forbidden headers rejected in webhook create POST
    for bad_headers in (
        json.dumps({"Authorization": "Bearer leak"}),
        json.dumps({"Host": "evil.internal"}),
        json.dumps({"X-NavERP-Signature-256": "forged"}),
        json.dumps({"X-Test": "ok\r\nX-Injected: 1"}),
    ):
        res = client_a.post(
            reverse("documents:webhook_trigger_create"),
            data=_workflow_automation_valid_webhook_post(custom_headers=bad_headers),
        )
        assert res.status_code == 200
        assert "custom_headers" in res.context["form"].errors
        with pytest.raises(Exception):
            validate_flat_headers(json.loads(bad_headers))

    # ReDoS nested quantifier rejected in HTTP POST & service validator
    res_redos = client_a.post(
        reverse("documents:routing_rule_create"),
        data={
            "name": "ReDoS Rule",
            "rule_type": "routing_distribution",
            "trigger_event": "on_upload",
            "priority": "1",
            "condition_logic_mode": "all_and",
            "conditions_json": json.dumps(
                [{"source": "document", "field": "title", "op": "regex_match", "value": "(a+)+"}]
            ),
            "else_action_json": "{}",
            "validation_rules_json": "[]",
            "auto_populate_json": "{}",
            "route_action": "move_to_folder",
        },
    )
    assert res_redos.status_code == 200
    assert "conditions_json" in res_redos.context["form"].errors
    with pytest.raises(Exception):
        validate_safe_regex("(a+)+")

    # >65536 byte JSON rejected cleanly without 500
    oversized_json = "[" + "1," * 35000 + "1]"
    res_big = client_a.post(
        reverse("documents:process_definition_designer", args=[draft_process_definition.pk]),
        data={"swimlanes_json": "[]", "nodes_json": oversized_json, "transitions_json": "[]"},
    )
    assert res_big.status_code == 200
    assert "nodes_json" in res_big.context["designer_form"].errors

    # Mass assignment via HTTP POST cannot publish draft or forge instance_count/number
    res_ma = client_a.post(
        reverse("documents:process_definition_edit", args=[draft_process_definition.pk]),
        data={
            "name": "Mass Assign Check",
            "code": draft_process_definition.code,
            "process_category": "intake_triage",
            "trigger_event": "document_created",
            "target_document_type": "all",
            "version_number": "1",
            "sla_target_hours": "24",
            "status": "published",
            "number": "DBPM-99999",
            "instance_count": "500",
        },
    )
    assert res_ma.status_code == 302
    draft_process_definition.refresh_from_db()
    assert draft_process_definition.status == "draft"
    assert draft_process_definition.instance_count == 0
    assert draft_process_definition.number != "DBPM-99999"


def test_workflow_automation_csrf_enforced_on_mutations(admin_user, draft_process_definition):
    csrf_client = Client(HTTP_HOST="localhost", enforce_csrf_checks=True)
    csrf_client.force_login(admin_user)
    for url in (
        reverse("documents:process_definition_publish", args=[draft_process_definition.pk]),
        reverse("documents:process_definition_delete", args=[draft_process_definition.pk]),
        reverse("documents:routing_rule_create"),
        reverse("documents:webhook_trigger_create"),
    ):
        res = csrf_client.post(url, data={})
        assert res.status_code == 403, f"Expected 403 CSRF rejection on {url}, got {res.status_code}"


def test_workflow_automation_legal_hold_and_locked_record_block_live_routing(
    tenant_a, admin_user, document, target_document, document_folder
):
    DocumentLegalHold.objects.create(
        tenant=tenant_a,
        matter_name="SEC Matter",
        matter_number="SEC-HOLD-1",
        hold_reason="litigation",
        document=document,
        placed_by=admin_user,
        is_active=True,
    )
    sched = RetentionSchedule.objects.create(tenant=tenant_a, name="Locked Schedule", code="LOCK-7Y")
    RecordDeclaration.objects.create(
        tenant=tenant_a,
        document=target_document,
        retention_schedule=sched,
        declared_by=admin_user,
        is_locked=True,
    )

    rule = DocumentRoutingRule.objects.create(
        tenant=tenant_a,
        name="Security Hold Gate Rule",
        rule_type="routing_distribution",
        trigger_event="on_manual_eval",
        priority=1,
        conditions_json=[],
        auto_populate_json={"document_fields": {"tags": "mutated-by-rule"}},
        route_action="move_to_folder",
        destination_folder=document_folder,
        is_active=True,
        owner=admin_user,
    )

    for protected_doc in (document, target_document):
        orig_status = protected_doc.status
        orig_tags = protected_doc.tags
        results = evaluate_routing_rules(
            tenant=tenant_a,
            document=protected_doc,
            rules=[rule],
            apply_mutations=True,
            actor=admin_user,
        )
        protected_doc.refresh_from_db()
        assert protected_doc.status == orig_status
        assert protected_doc.tags == orig_tags
        assert (document_folder.slug or "") not in (protected_doc.tags or "")
        assert "mutated-by-rule" not in (protected_doc.tags or "")
        assert results[0]["applied_actions"] == []
        assert any("legal hold or locked record" in err for err in results[0]["validation_errors"])
