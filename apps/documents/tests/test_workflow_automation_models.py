"""Model and service unit tests for Sub-module 13.11: Workflow Automation & BPM.

Covers all four models and apps/documents/services/workflow_automation.py:
1. DocumentProcessDefinition: DBPM- numbering, tenant isolation, code uppercase
   normalization, (tenant, code, version_number) uniqueness, badge/count properties,
   clean() bounds & None safety, validate_graph(), and simulate_process_path().
2. DocumentRoutingRule: DRUL- numbering, badge/rate properties, clean() validations
   (priority, operators, invalid regex, nested-quantifier ReDoS, min_confidence,
   empty block_validation, else_action), and evaluate_routing_rules() (False/0, raw
   DocumentMetadataValue fields, all_and/any_or, else_branch_enabled fallback & audit,
   route actions, legal-hold/locked-record guards, cross-tenant boundary guards).
3. DocumentProcessInstance & analytics: DPIN- numbering, sla_badge, duration_display,
   start_process_instance() status/tenant guards, gateway conditional branching,
   automatic 13.3 DocumentApprovalWorkflow spawn on approval_subprocess advance,
   rejected rework & escalated sla_breached trace/audit/webhook dispatch,
   cancel_process_instance(), and compute_process_analytics() KPIs & filters.
4. DocumentWebhookTrigger: DWHK- numbering, Fernet encryption + prefix masking,
   fail-closed get_signing_secret(), HMAC-SHA256 sign/verify, SSRF URL validation,
   flat header CR/LF/NUL & denylist validation, 25-entry delivery history cap,
   and filter_document_type / direction event webhook filtering.
"""
from datetime import date, timedelta
from decimal import Decimal
import json
import pytest

from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db import IntegrityError
from django.utils import timezone

from apps.documents.models import (
    Document,
    DocumentApprovalWorkflow,
    DocumentAuditTrail,
    DocumentLegalHold,
    DocumentMetadataValue,
    DocumentProcessDefinition,
    DocumentProcessInstance,
    DocumentRoutingRule,
    DocumentTask,
    DocumentWebhookTrigger,
    RecordDeclaration,
    RetentionSchedule,
)
from apps.documents.services.workflow_automation import (
    advance_process_instance,
    build_document_context,
    cancel_process_instance,
    compute_process_analytics,
    dispatch_simulated_webhook,
    evaluate_condition_clause,
    evaluate_routing_rules,
    simulate_process_path,
    start_process_instance,
    validate_dms_webhook_url,
    validate_flat_headers,
    validate_process_graph,
)


pytestmark = pytest.mark.django_db


# ---------------------------------------------------------------------------
# Module-level helpers (prefix _workflow_automation_*)
# ---------------------------------------------------------------------------

def _workflow_automation_create_process(
    tenant,
    owner,
    name="Standard BPM Flow",
    code="WF-STD",
    version_number=1,
    status="published",
    is_active=True,
    sla_target_hours=48,
    nodes_json=None,
    transitions_json=None,
    swimlanes_json=None,
):
    """Create a DocumentProcessDefinition with sensible graph defaults."""
    default_lanes = [{"id": "lane_ops", "name": "Operations"}]
    default_nodes = [
        {"id": "s1", "type": "start_event", "label": "Start", "lane_id": "lane_ops"},
        {"id": "t1", "type": "user_task", "label": "Review", "lane_id": "lane_ops"},
        {"id": "e1", "type": "end_event", "label": "Done", "lane_id": "lane_ops"},
    ]
    default_edges = [
        {"from_node": "s1", "to_node": "t1", "label": "Start"},
        {"from_node": "t1", "to_node": "e1", "label": "Finish"},
    ]
    return DocumentProcessDefinition.objects.create(
        tenant=tenant,
        name=name,
        code=code,
        version_number=version_number,
        status=status,
        is_active=is_active,
        sla_target_hours=sla_target_hours,
        owner=owner,
        swimlanes_json=default_lanes if swimlanes_json is None else swimlanes_json,
        nodes_json=default_nodes if nodes_json is None else nodes_json,
        transitions_json=default_edges if transitions_json is None else transitions_json,
    )


def _workflow_automation_create_rule(
    tenant,
    owner,
    name="Test Routing Rule",
    priority=20,
    rule_type="routing_distribution",
    trigger_event="on_upload",
    condition_logic_mode="all_and",
    conditions_json=None,
    validation_rules_json=None,
    auto_populate_json=None,
    route_action="populate_metadata",
    else_branch_enabled=False,
    else_action_json=None,
    is_active=True,
    **extra,
):
    """Create a DocumentRoutingRule."""
    return DocumentRoutingRule.objects.create(
        tenant=tenant,
        name=name,
        owner=owner,
        priority=priority,
        rule_type=rule_type,
        trigger_event=trigger_event,
        condition_logic_mode=condition_logic_mode,
        conditions_json=[] if conditions_json is None else conditions_json,
        validation_rules_json=[] if validation_rules_json is None else validation_rules_json,
        auto_populate_json={} if auto_populate_json is None else auto_populate_json,
        route_action=route_action,
        else_branch_enabled=else_branch_enabled,
        else_action_json={} if else_action_json is None else else_action_json,
        is_active=is_active,
        **extra,
    )


def _workflow_automation_create_webhook(
    tenant,
    owner,
    name="Test Webhook",
    direction="outbound_webhook",
    trigger_event="process.completed",
    target_url="https://hooks.partner-erp.example/events",
    payload_format="json",
    process_definition=None,
    filter_document_type="",
    is_active=True,
    custom_headers=None,
):
    """Create a DocumentWebhookTrigger with a generated Fernet-encrypted secret."""
    wh = DocumentWebhookTrigger(
        tenant=tenant,
        name=name,
        owner=owner,
        direction=direction,
        trigger_event=trigger_event,
        target_url=target_url,
        payload_format=payload_format,
        process_definition=process_definition,
        filter_document_type=filter_document_type,
        is_active=is_active,
        custom_headers=custom_headers if custom_headers is not None else {},
    )
    wh.generate_signing_secret()
    wh.save()
    return wh


# ---------------------------------------------------------------------------
# 1. DocumentProcessDefinition Tests
# ---------------------------------------------------------------------------

def test_workflow_automation_process_definition_numbering_and_isolation(
    tenant_a, tenant_b, admin_user, admin_b, process_definition
):
    """Verify DBPM- auto-numbering, __str__, and per-tenant sequence isolation."""
    assert process_definition.number.startswith("DBPM-")
    assert str(process_definition) == (
        f"{process_definition.number} — {process_definition.name} (v{process_definition.version_number})"
    )

    proc_b = _workflow_automation_create_process(tenant_b, admin_b, name="Globex Intake", code="GLX-01")
    assert proc_b.number == "DBPM-00001"
    assert process_definition in DocumentProcessDefinition.objects.filter(tenant=tenant_a)
    assert process_definition not in DocumentProcessDefinition.objects.filter(tenant=tenant_b)
    assert proc_b in DocumentProcessDefinition.objects.filter(tenant=tenant_b)


def test_workflow_automation_process_definition_code_normalization_and_uniqueness(
    tenant_a, tenant_b, admin_user, admin_b
):
    """Verify code uppercase normalization and (tenant, code, version_number) unique constraint."""
    proc = DocumentProcessDefinition(
        tenant=tenant_a,
        name="Normalized Code Flow",
        code="  contract-review  ",
        version_number=1,
        owner=admin_user,
    )
    proc.clean()
    assert proc.code == "CONTRACT-REVIEW"
    proc.save()
    assert proc.code == "CONTRACT-REVIEW"

    # Duplicate (tenant, code, version_number) violates unique constraint
    with pytest.raises(IntegrityError):
        DocumentProcessDefinition.objects.create(
            tenant=tenant_a,
            name="Duplicate Code Version",
            code="CONTRACT-REVIEW",
            version_number=1,
            owner=admin_user,
        )

    # Same code with version_number=2 in tenant_a or version_number=1 in tenant_b succeeds
    proc_v2 = _workflow_automation_create_process(
        tenant_a, admin_user, name="Normalized v2", code="contract-review", version_number=2
    )
    proc_b = _workflow_automation_create_process(
        tenant_b, admin_b, name="Globex Copy", code="contract-review", version_number=1
    )
    assert proc_v2.version_number == 2
    assert proc_b.code == "CONTRACT-REVIEW"


def test_workflow_automation_process_definition_badges_counts_and_clean_bounds(tenant_a, admin_user):
    """Verify CSS badges, structural counts, and clean() lower bounds + None safety."""
    proc = _workflow_automation_create_process(tenant_a, admin_user, status="deprecated")
    assert proc.status_badge == "badge-amber"
    assert proc.category_badge == "badge-info"
    assert proc.swimlane_count == 1
    assert proc.node_count == 3
    assert proc.transition_count == 2

    proc.status = "unknown_status"
    assert proc.status_badge == "badge-slate"
    proc.nodes_json = {"not": "a list"}
    assert proc.node_count == 0

    # clean() bounds checks
    bad_sla = DocumentProcessDefinition(
        tenant=tenant_a, name="Bad SLA", code="BAD-SLA", sla_target_hours=0, owner=admin_user
    )
    with pytest.raises(ValidationError) as exc_sla:
        bad_sla.clean()
    assert "sla_target_hours" in exc_sla.value.message_dict

    bad_ver = DocumentProcessDefinition(
        tenant=tenant_a, name="Bad Ver", code="BAD-VER", version_number=0, owner=admin_user
    )
    with pytest.raises(ValidationError) as exc_ver:
        bad_ver.clean()
    assert "version_number" in exc_ver.value.message_dict

    # None values do not raise TypeError in clean()
    none_bounds = DocumentProcessDefinition(
        tenant=tenant_a,
        name="None Bounds",
        code="NONE-OK",
        sla_target_hours=None,
        version_number=None,
        owner=admin_user,
    )
    none_bounds.clean()


def test_workflow_automation_validate_graph_and_simulate_process_path(process_definition):
    """Verify validate_graph() valid/invalid/warning diagnostics and gateway path simulation."""
    vg_ok = process_definition.validate_graph()
    assert vg_ok["is_valid"] is True
    assert vg_ok["errors"] == []
    assert vg_ok["warnings"] == []
    assert vg_ok["node_count"] == 6
    assert vg_ok["transition_count"] == 6

    # Gateway simulation branches deterministically on context
    steps_conf = simulate_process_path(process_definition, context={"classification": "confidential"})
    assert [s["node_id"] for s in steps_conf] == ["n_start", "n_task", "n_gw", "n_app", "n_end"]

    steps_std = simulate_process_path(process_definition, context={"classification": "internal"})
    assert [s["node_id"] for s in steps_std] == ["n_start", "n_task", "n_gw", "n_std", "n_end"]

    # Invalid graphs
    empty_res = validate_process_graph([], [], [])
    assert empty_res["is_valid"] is False
    assert "at least one node" in empty_res["errors"][0]

    bad_res = validate_process_graph(
        "not-a-list",
        [
            {"id": "s", "type": "user_task"},
            {"id": "s", "type": "user_task"},  # duplicate
            {"id": "x", "type": "bogus_node_type"},  # unsupported type, no start/end
        ],
        [{"from_node": "s", "to_node": "missing_target"}],
    )
    assert bad_res["is_valid"] is False
    joined_errors = " ".join(bad_res["errors"])
    assert "Swimlanes must be a JSON array" in joined_errors
    assert "Duplicate node id 's'" in joined_errors
    assert "unsupported type 'bogus_node_type'" in joined_errors
    assert "requires at least one 'start_event'" in joined_errors
    assert "requires at least one 'end_event'" in joined_errors
    assert "unknown target node 'missing_target'" in joined_errors

    # Valid graph with structural warnings
    warn_res = validate_process_graph(
        [],
        [
            {"id": "s", "type": "start_event"},
            {"id": "gw", "type": "exclusive_gateway"},
            {"id": "b1", "type": "user_task"},
            {"id": "b2", "type": "user_task"},
            {"id": "orphan", "type": "user_task"},
            {"id": "e", "type": "end_event"},
        ],
        [
            {"from_node": "s", "to_node": "gw"},
            {"from_node": "gw", "to_node": "b1"},
            {"from_node": "gw", "to_node": "b2"},
            {"from_node": "b1", "to_node": "b1"},  # self-loop
            {"from_node": "b1", "to_node": "e"},
        ],
    )
    assert warn_res["is_valid"] is True
    joined_warns = " ".join(warn_res["warnings"])
    assert "self-loop" in joined_warns
    assert "without a default edge" in joined_warns
    assert "no outgoing transitions" in joined_warns
    assert "Unreachable nodes" in joined_warns


# ---------------------------------------------------------------------------
# 2. DocumentRoutingRule & Evaluator Tests
# ---------------------------------------------------------------------------

def test_workflow_automation_routing_rule_numbering_badges_and_rates(tenant_a, admin_user, routing_rule):
    """Verify DRUL- prefix, __str__, CSS badges, and match_rate_pct calculation."""
    assert routing_rule.number.startswith("DRUL-")
    assert str(routing_rule) == f"{routing_rule.number} — {routing_rule.name} (P{routing_rule.priority})"
    assert routing_rule.rule_type_badge == "badge-info"
    assert routing_rule.route_action_badge == "badge-info"
    assert routing_rule.active_badge == "badge-green"
    assert routing_rule.condition_count == 1
    assert routing_rule.match_rate_pct == 0.0

    routing_rule.execution_count = 8
    routing_rule.match_count = 3
    assert routing_rule.match_rate_pct == 37.5

    routing_rule.is_active = False
    assert routing_rule.active_badge == "badge-slate"


def test_workflow_automation_routing_rule_clean_validations(tenant_a, admin_user):
    """Verify clean() enforces priority, operators, safe regex/ReDoS, min_confidence, and block_validation."""
    bad_pri = DocumentRoutingRule(tenant=tenant_a, name="Bad Pri", priority=0, owner=admin_user)
    with pytest.raises(ValidationError) as exc:
        bad_pri.clean()
    assert "priority" in exc.value.message_dict

    # Unsupported operator
    bad_op = DocumentRoutingRule(
        tenant=tenant_a,
        name="Bad Op",
        owner=admin_user,
        conditions_json=[{"source": "document", "field": "title", "op": "like", "value": "x"}],
    )
    with pytest.raises(ValidationError) as exc:
        bad_op.clean()
    assert "conditions_json" in exc.value.message_dict

    # Invalid regex syntax
    bad_rx = DocumentRoutingRule(
        tenant=tenant_a,
        name="Bad Regex",
        owner=admin_user,
        conditions_json=[{"source": "document", "field": "title", "op": "regex_match", "value": "["}],
    )
    with pytest.raises(ValidationError) as exc:
        bad_rx.clean()
    assert "conditions_json" in exc.value.message_dict

    # Nested-quantifier ReDoS pattern
    for redos in ("(a+)+", "(a*)*", "(a{1,5})+"):
        bad_redos = DocumentRoutingRule(
            tenant=tenant_a,
            name="ReDoS",
            owner=admin_user,
            conditions_json=[{"source": "document", "field": "title", "op": "regex_match", "value": redos}],
        )
        with pytest.raises(ValidationError) as exc:
            bad_redos.clean()
        assert "conditions_json" in exc.value.message_dict

    # Invalid min_confidence
    bad_conf = DocumentRoutingRule(
        tenant=tenant_a,
        name="Bad Conf",
        owner=admin_user,
        validation_rules_json=[{"check": "min_ocr_confidence", "min_confidence": "NaN"}],
    )
    with pytest.raises(ValidationError) as exc:
        bad_conf.clean()
    assert "validation_rules_json" in exc.value.message_dict

    # block_validation without checks
    empty_block = DocumentRoutingRule(
        tenant=tenant_a,
        name="Empty Block",
        owner=admin_user,
        route_action="block_validation",
        validation_rules_json=[],
    )
    with pytest.raises(ValidationError) as exc:
        empty_block.clean()
    assert "validation_rules_json" in exc.value.message_dict

    # Unsupported else_action route_action
    bad_else = DocumentRoutingRule(
        tenant=tenant_a,
        name="Bad Else",
        owner=admin_user,
        else_branch_enabled=True,
        else_action_json={"route_action": "delete_everything"},
    )
    with pytest.raises(ValidationError) as exc:
        bad_else.clean()
    assert "else_action_json" in exc.value.message_dict


def test_workflow_automation_rule_evaluator_false_zero_and_raw_metadata(tenant_a, admin_user):
    """Verify False, 0, and raw DocumentMetadataValue types evaluate without truthiness bugs."""
    doc = Document.objects.create(
        tenant=tenant_a,
        title="NDA-2026 Zero-Version",
        document_type="contract",
        classification="confidential",
        status="draft",
        current_version_no=0,
        is_locked=False,
        owner=admin_user,
    )
    DocumentMetadataValue.objects.create(
        tenant=tenant_a,
        document=doc,
        version=None,
        field_name="empty_code",
        data_type="text",
        value_text="",
        updated_by=admin_user,
    )
    DocumentMetadataValue.objects.create(
        tenant=tenant_a,
        document=doc,
        version=None,
        field_name="text_code",
        data_type="text",
        value_text="REG-042",
        updated_by=admin_user,
    )
    DocumentMetadataValue.objects.create(
        tenant=tenant_a,
        document=doc,
        version=None,
        field_name="requires_board",
        data_type="boolean",
        value_boolean=False,
        updated_by=admin_user,
    )
    DocumentMetadataValue.objects.create(
        tenant=tenant_a,
        document=doc,
        version=None,
        field_name="risk_score",
        data_type="integer",
        value_number=Decimal("0"),
        updated_by=admin_user,
    )
    DocumentMetadataValue.objects.create(
        tenant=tenant_a,
        document=doc,
        version=None,
        field_name="effective_on",
        data_type="date",
        value_date=date(2026, 6, 15),
        updated_by=admin_user,
    )

    ctx = build_document_context(tenant_a, doc)
    assert ctx["metadata"]["empty_code"] == ""
    assert ctx["metadata"]["text_code"] == "REG-042"
    assert ctx["metadata"]["requires_board"] is False
    assert ctx["metadata"]["risk_score"] == Decimal("0")
    assert ctx["metadata"]["effective_on"] == "2026-06-15"

    # False equality / membership
    assert evaluate_condition_clause({"source": "document", "field": "is_locked", "op": "eq", "value": "false"}, ctx)["matched"] is True
    assert evaluate_condition_clause({"source": "document", "field": "is_locked", "op": "eq", "value": ""}, ctx)["matched"] is False
    assert evaluate_condition_clause({"source": "document", "field": "is_locked", "op": "ne", "value": "false"}, ctx)["matched"] is False
    assert evaluate_condition_clause({"source": "document", "field": "is_locked", "op": "in", "value": "false, true"}, ctx)["matched"] is True
    assert evaluate_condition_clause({"source": "metadata", "field": "requires_board", "op": "eq", "value": "false"}, ctx)["matched"] is True

    # 0 numeric comparisons & string operators
    assert evaluate_condition_clause({"source": "document", "field": "current_version_no", "op": "eq", "value": "0"}, ctx)["matched"] is True
    assert evaluate_condition_clause({"source": "document", "field": "current_version_no", "op": "gt", "value": "-1"}, ctx)["matched"] is True
    assert evaluate_condition_clause({"source": "document", "field": "current_version_no", "op": "lt", "value": "1"}, ctx)["matched"] is True
    assert evaluate_condition_clause({"source": "document", "field": "current_version_no", "op": "in", "value": "0, 1"}, ctx)["matched"] is True
    assert evaluate_condition_clause({"source": "document", "field": "current_version_no", "op": "not_in", "value": "0, 1"}, ctx)["matched"] is False
    assert evaluate_condition_clause({"source": "document", "field": "current_version_no", "op": "contains", "value": "0"}, ctx)["matched"] is True
    assert evaluate_condition_clause({"source": "document", "field": "current_version_no", "op": "regex_match", "value": "^0$"}, ctx)["matched"] is True
    assert evaluate_condition_clause({"source": "metadata", "field": "risk_score", "op": "lte", "value": "0"}, ctx)["matched"] is True

    # Empty metadata row: is_empty=True, required_metadata fails
    assert evaluate_condition_clause({"source": "metadata", "field": "empty_code", "op": "is_empty"}, ctx)["matched"] is True
    assert evaluate_condition_clause({"source": "metadata", "field": "empty_code", "op": "is_set"}, ctx)["matched"] is False
    assert evaluate_condition_clause({"source": "metadata", "field": "text_code", "op": "regex_match", "value": r"^REG-\d+$"}, ctx)["matched"] is True

    gate_rule = _workflow_automation_create_rule(
        tenant_a,
        admin_user,
        name="Empty Metadata Gate",
        rule_type="data_validation",
        route_action="block_validation",
        validation_rules_json=[{"check": "required_metadata", "field": "empty_code", "message": "empty_code required"}],
    )
    gate_res = evaluate_routing_rules(tenant_a, doc, rules=[gate_rule], apply_mutations=False)
    assert gate_res[0]["validation_errors"] == ["empty_code required"]
    assert gate_res[0]["effective_action"] is None

    # all_and vs any_or
    and_rule = _workflow_automation_create_rule(
        tenant_a,
        admin_user,
        name="AND Rule",
        condition_logic_mode="all_and",
        conditions_json=[
            {"source": "document", "field": "is_locked", "op": "eq", "value": "false"},
            {"source": "metadata", "field": "text_code", "op": "eq", "value": "NOPE"},
        ],
    )
    or_rule = _workflow_automation_create_rule(
        tenant_a,
        admin_user,
        name="OR Rule",
        condition_logic_mode="any_or",
        conditions_json=and_rule.conditions_json,
    )
    combo = evaluate_routing_rules(tenant_a, doc, rules=[and_rule, or_rule], apply_mutations=False)
    assert combo[0]["matched"] is False
    assert combo[1]["matched"] is True


def test_workflow_automation_evaluate_routing_rules_actions_and_else_fallback(
    tenant_a,
    admin_user,
    member_user,
    document,
    target_document,
    document_folder,
    org_unit_a,
    process_definition,
    draft_process_definition,
):
    """Verify dry-run vs live apply across move_to_folder, populate_metadata, assign_user, trigger_process, spawn_approval_workflow, and else_branch."""
    # Exact tag token matching for source_folder (substring should NOT match)
    document.tags = "corporate-policies-archive"
    document.save(update_fields=["tags"])
    src_rule = _workflow_automation_create_rule(
        tenant_a, admin_user, name="Source Folder Check", source_folder=document_folder
    )
    src_res = evaluate_routing_rules(tenant_a, document, rules=[src_rule], apply_mutations=False)
    assert src_res[0]["scope_ok"] is False

    # 1. Dry-run move_to_folder + populate_metadata
    rule_move = _workflow_automation_create_rule(
        tenant_a,
        admin_user,
        name="Move + Populate",
        priority=1,
        conditions_json=[{"source": "document", "field": "document_type", "op": "eq", "value": "sop"}],
        auto_populate_json={"document_fields": {"tags": "validated"}, "metadata_fields": {"tier": "Gold"}},
        route_action="move_to_folder",
        destination_folder=document_folder,
    )
    dry = evaluate_routing_rules(tenant_a, document, rules=[rule_move], apply_mutations=False, actor=admin_user)
    assert dry[0]["matched"] is True
    assert dry[0]["applied_actions"] == []
    rule_move.refresh_from_db()
    assert rule_move.execution_count == 0

    # Live apply move_to_folder + populate_metadata
    live = evaluate_routing_rules(tenant_a, document, rules=[rule_move], apply_mutations=True, actor=admin_user)
    document.refresh_from_db()
    rule_move.refresh_from_db()
    assert rule_move.execution_count == 1
    assert rule_move.match_count == 1
    assert "corporate-policies" in document.tags
    assert "validated" in document.tags
    assert DocumentMetadataValue.objects.filter(
        tenant=tenant_a, document=document, version=None, field_name="routed_folder_path", value_text=document_folder.path
    ).exists()
    assert DocumentMetadataValue.objects.filter(
        tenant=tenant_a, document=document, version=None, field_name="tier", value_text="Gold"
    ).exists()
    assert DocumentAuditTrail.objects.filter(
        tenant=tenant_a, document=document, action_type="moved", details_json__bpm_event="routing.matched"
    ).exists()
    assert live[0]["applied_actions"]

    # 2. assign_user
    rule_assign = _workflow_automation_create_rule(
        tenant_a, admin_user, name="Assign Member", route_action="assign_user", route_to_user=member_user
    )
    evaluate_routing_rules(tenant_a, document, rules=[rule_assign], apply_mutations=True, actor=admin_user)
    document.refresh_from_db()
    assert document.owner == member_user

    # 3. trigger_process (published launches DPIN; draft is skipped)
    rule_proc_pub = _workflow_automation_create_rule(
        tenant_a, admin_user, name="Launch Pub", route_action="trigger_process", process_definition=process_definition
    )
    rule_proc_draft = _workflow_automation_create_rule(
        tenant_a, admin_user, name="Skip Draft", route_action="trigger_process", process_definition=draft_process_definition
    )
    proc_res = evaluate_routing_rules(
        tenant_a, target_document, rules=[rule_proc_pub, rule_proc_draft], apply_mutations=True, actor=admin_user
    )
    assert any(item.startswith("started_dpin->DPIN-") for item in proc_res[0]["applied_actions"])
    assert any("not_published" in item for item in proc_res[1]["applied_actions"])
    assert DocumentProcessInstance.objects.filter(tenant=tenant_a, document=target_document, triggered_by_rule=rule_proc_pub).exists()

    # 4. spawn_approval_workflow
    rule_dwf = _workflow_automation_create_rule(
        tenant_a, admin_user, name="Spawn Approval", route_action="spawn_approval_workflow", route_to_org_unit=org_unit_a
    )
    dwf_res = evaluate_routing_rules(tenant_a, target_document, rules=[rule_dwf], apply_mutations=True, actor=admin_user)
    assert any(item.startswith("spawned_dwf->DWF-") for item in dwf_res[0]["applied_actions"])
    assert DocumentApprovalWorkflow.objects.filter(tenant=tenant_a, document=target_document).exists()

    # 5. else_branch_enabled fallback with route_action="move_to_folder" + metadata + audit
    rule_else = _workflow_automation_create_rule(
        tenant_a,
        admin_user,
        name="Else Fallback Move",
        conditions_json=[{"source": "document", "field": "title", "op": "eq", "value": "DOES_NOT_MATCH"}],
        else_branch_enabled=True,
        else_action_json={
            "route_action": "move_to_folder",
            "destination_folder_id": document_folder.pk,
            "metadata_fields": {"fallback_queue": "Triage-Queue"},
        },
        route_action="assign_user",
        route_to_user=admin_user,
    )
    else_res = evaluate_routing_rules(tenant_a, target_document, rules=[rule_else], apply_mutations=True, actor=admin_user)
    target_document.refresh_from_db()
    rule_else.refresh_from_db()
    assert else_res[0]["used_else"] is True
    assert else_res[0]["effective_action"] == "move_to_folder"
    assert "corporate-policies" in target_document.tags
    assert DocumentMetadataValue.objects.filter(
        tenant=tenant_a, document=target_document, field_name="fallback_queue", value_text="Triage-Queue"
    ).exists()
    assert DocumentAuditTrail.objects.filter(
        tenant=tenant_a, document=target_document, details_json__bpm_event="routing.else_fallback"
    ).exists()
    assert rule_else.execution_count == 1
    assert rule_else.match_count == 0


def test_workflow_automation_rule_evaluator_legal_hold_locked_and_cross_tenant_guards(
    tenant_a, tenant_b, admin_user, admin_b, document, target_document, document_folder
):
    """Verify active legal holds, locked RecordDeclarations, and cross-tenant FK isolation block mutations."""
    # Active Legal Hold blocks live mutations
    DocumentLegalHold.objects.create(
        tenant=tenant_a,
        matter_name="Litigation Hold",
        matter_number="LIT-2026-01",
        hold_reason="litigation",
        document=document,
        placed_by=admin_user,
        is_active=True,
    )
    rule_hold = _workflow_automation_create_rule(
        tenant_a,
        admin_user,
        name="Blocked By Hold",
        route_action="move_to_folder",
        destination_folder=document_folder,
    )
    hold_res = evaluate_routing_rules(tenant_a, document, rules=[rule_hold], apply_mutations=True, actor=admin_user)
    document.refresh_from_db()
    assert any("legal hold or locked record" in err for err in hold_res[0]["validation_errors"])
    assert hold_res[0]["applied_actions"] == []
    assert "corporate-policies" not in (document.tags or "")
    assert DocumentAuditTrail.objects.filter(
        tenant=tenant_a, document=document, action_type="workflow_rejected", failure_reason="routing_validation_failed"
    ).exists()

    # Locked RecordDeclaration blocks live mutations including else_branch
    sched = RetentionSchedule.objects.create(tenant=tenant_a, name="WORM 7Y", code="WORM-7Y")
    RecordDeclaration.objects.create(
        tenant=tenant_a,
        document=target_document,
        retention_schedule=sched,
        declared_by=admin_user,
        is_locked=True,
    )
    rule_locked_else = _workflow_automation_create_rule(
        tenant_a,
        admin_user,
        name="Locked Else",
        conditions_json=[{"source": "document", "field": "title", "op": "eq", "value": "NO_MATCH"}],
        else_branch_enabled=True,
        else_action_json={"metadata_fields": {"blocked_key": "should_not_write"}},
    )
    locked_res = evaluate_routing_rules(
        tenant_a, target_document, rules=[rule_locked_else], apply_mutations=True, actor=admin_user
    )
    assert any("legal hold or locked record" in err for err in locked_res[0]["validation_errors"])
    assert locked_res[0]["effective_action"] is None
    assert not DocumentMetadataValue.objects.filter(
        tenant=tenant_a, document=target_document, field_name="blocked_key"
    ).exists()

    # Cross-tenant boundary checks
    doc_b = Document.objects.create(tenant=tenant_b, title="Globex Doc", owner=admin_b)
    with pytest.raises(ValidationError):
        evaluate_routing_rules(tenant_a, doc_b, apply_mutations=False)

    rule_b = _workflow_automation_create_rule(tenant_b, admin_b, name="Globex Rule")
    with pytest.raises(ValidationError):
        evaluate_routing_rules(tenant_a, document, rules=[rule_b], apply_mutations=False)


# ---------------------------------------------------------------------------
# 3. DocumentProcessInstance, Execution & Analytics Tests
# ---------------------------------------------------------------------------

def test_workflow_automation_process_instance_numbering_badges_and_duration(
    tenant_a, admin_user, process_definition, process_instance
):
    """Verify DPIN- numbering, __str__, sla_badge, conformance_badge, and duration_display."""
    assert process_instance.number.startswith("DPIN-")
    assert process_definition.code in str(process_instance)
    assert process_instance.status_badge == "badge-info"
    assert process_instance.sla_badge == "badge-green"
    assert process_instance.conformance_badge == "badge-green"
    assert process_instance.step_count == 2
    assert process_instance.duration_display == "In Progress"

    process_instance.cycle_time_minutes = 45
    assert process_instance.duration_display == "45m"
    process_instance.cycle_time_minutes = 135
    assert process_instance.duration_display == "2h 15m"

    # sla_badge reflects either is_sla_breached or status=='sla_breached'
    process_instance.is_sla_breached = False
    process_instance.status = "sla_breached"
    assert process_instance.sla_badge == "badge-red"
    assert process_instance.status_badge == "badge-red"

    process_instance.status = "running"
    process_instance.is_sla_breached = True
    assert process_instance.sla_badge == "badge-red"


def test_workflow_automation_start_process_instance_status_and_tenant_guards(
    tenant_a, tenant_b, admin_user, admin_b, document, target_document, document_version, process_definition, draft_process_definition
):
    """Verify start_process_instance rejects draft/deprecated/archived/inactive blueprints and cross-tenant links."""
    deprecated_proc = _workflow_automation_create_process(
        tenant_a, admin_user, name="Deprecated", code="DEP-01", status="deprecated", is_active=False
    )
    archived_proc = _workflow_automation_create_process(
        tenant_a, admin_user, name="Archived", code="ARC-01", status="archived", is_active=False
    )
    inactive_pub = _workflow_automation_create_process(
        tenant_a, admin_user, name="Inactive Pub", code="INACT-01", status="published", is_active=False
    )
    for bad_proc in (draft_process_definition, deprecated_proc, archived_proc, inactive_pub):
        with pytest.raises(ValidationError):
            start_process_instance(tenant_a, bad_proc, document, actor=admin_user)

    # Cross-tenant document or version mismatch
    doc_b = Document.objects.create(tenant=tenant_b, title="Globex Doc", owner=admin_b)
    with pytest.raises(ValidationError):
        start_process_instance(tenant_a, process_definition, doc_b, actor=admin_user)

    with pytest.raises(ValidationError):
        # document_version belongs to `document`, not `target_document`
        start_process_instance(tenant_a, process_definition, target_document, actor=admin_user, version=document_version)


def test_workflow_automation_advance_gateway_branching_and_approval_spawn(
    tenant_a, admin_user, process_definition, document
):
    """Verify gateway condition routing and automatic 13.3 DocumentApprovalWorkflow spawn on approval_subprocess."""
    conf_doc = Document.objects.create(
        tenant=tenant_a,
        title="Confidential M&A Contract",
        document_type="contract",
        classification="confidential",
        owner=admin_user,
    )
    inst_conf = start_process_instance(tenant_a, process_definition, conf_doc, actor=admin_user)
    assert inst_conf.current_node_id == "n_task"
    assert inst_conf.approval_workflow is None

    # n_task -> n_gw
    inst_conf = advance_process_instance(inst_conf, outcome="approved", actor=admin_user)
    assert inst_conf.current_node_id == "n_gw"

    # n_gw -> n_app (approval_subprocess) because classification == "confidential"
    inst_conf = advance_process_instance(inst_conf, outcome="approved", actor=admin_user)
    assert inst_conf.current_node_id == "n_app"
    assert inst_conf.status == "waiting_approval"
    assert inst_conf.approval_workflow is not None
    assert inst_conf.approval_workflow.number.startswith("DWF-")
    assert inst_conf.approval_workflow.document == conf_doc
    assert inst_conf.approval_workflow.due_date is not None

    # Standard (internal) document takes default n_std edge and completes at n_end
    inst_std = start_process_instance(tenant_a, process_definition, document, actor=admin_user)
    inst_std = advance_process_instance(inst_std, outcome="approved", actor=admin_user)  # n_task -> n_gw
    inst_std = advance_process_instance(inst_std, outcome="approved", actor=admin_user)  # n_gw -> n_std
    assert inst_std.current_node_id == "n_std"
    assert inst_std.approval_workflow is None
    inst_std = advance_process_instance(inst_std, outcome="approved", actor=admin_user)  # n_std -> n_end
    assert inst_std.status == "completed"
    assert inst_std.completed_at is not None
    assert inst_std.cycle_time_minutes >= 1


def test_workflow_automation_advance_rejected_escalated_and_cancel(
    tenant_a, admin_user, process_definition, document
):
    """Verify rejected rework, escalated open sla_breached step + audit + webhook, and cancel_process_instance."""
    wh_sla = _workflow_automation_create_webhook(
        tenant_a,
        admin_user,
        name="SLA Breach Notifier",
        direction="outbound_webhook",
        trigger_event="process.sla_breached",
        process_definition=process_definition,
    )
    inst = start_process_instance(tenant_a, process_definition, document, actor=admin_user)

    # Reject -> rework
    inst = advance_process_instance(inst, outcome="rejected", actor=admin_user, notes="Missing exhibit")
    assert inst.status == "running"
    assert inst.rework_count == 1
    assert inst.is_conformant is False
    assert inst.step_trace_json[-1]["outcome"] == "rework"
    assert inst.step_trace_json[-1]["exited_at"] is None
    assert DocumentAuditTrail.objects.filter(
        tenant=tenant_a, document=document, action_type="workflow_rejected", failure_reason="step_rejected"
    ).exists()

    # Escalate -> sla_breached + open trace step + audit + process.sla_breached webhook
    inst = advance_process_instance(inst, outcome="escalated", actor=admin_user, notes="Overdue 48h")
    wh_sla.refresh_from_db()
    assert inst.status == "sla_breached"
    assert inst.is_sla_breached is True
    assert inst.step_trace_json[-1]["node_type"] == "sla_event"
    assert inst.step_trace_json[-1]["outcome"] == "sla_breached"
    assert inst.step_trace_json[-1]["exited_at"] is None
    assert DocumentAuditTrail.objects.filter(
        tenant=tenant_a, document=document, failure_reason="sla_breached"
    ).exists()
    assert wh_sla.fire_count == 1
    assert wh_sla.delivery_history_json[-1]["event"] == "process.sla_breached"

    # Cancel active instance closes trailing open step and is idempotent
    inst_cancel = start_process_instance(tenant_a, process_definition, document, actor=admin_user)
    inst_cancel = cancel_process_instance(inst_cancel, actor=admin_user, notes="Superseded")
    assert inst_cancel.status == "cancelled"
    assert inst_cancel.completed_at is not None
    assert inst_cancel.step_trace_json[-1]["exited_at"] is not None
    assert inst_cancel.step_trace_json[-1]["outcome"] == "cancelled"
    assert DocumentAuditTrail.objects.filter(
        tenant=tenant_a, document=document, details_json__bpm_event="process.cancelled"
    ).exists()
    # Second cancel is a no-op
    same = cancel_process_instance(inst_cancel, actor=admin_user)
    assert same.status == "cancelled"


def test_workflow_automation_compute_process_analytics_kpis_and_filters(
    tenant_a, tenant_b, admin_user, admin_b, process_definition, document, target_document
):
    """Verify analytics KPIs (active_wip incl. sla_breached, median/p95, bottlenecks, date range, isolation)."""
    now = timezone.now()
    # 4 completed instances with distinct cycle times for avg/median/p95
    for idx, mins in enumerate((10, 20, 30, 100)):
        DocumentProcessInstance.objects.create(
            tenant=tenant_a,
            process_definition=process_definition,
            document=document,
            status="completed",
            current_node_id="n_end",
            started_at=now - timedelta(days=idx),
            completed_at=now - timedelta(days=idx) + timedelta(minutes=mins),
            cycle_time_minutes=mins,
            rework_count=1 if mins == 100 else 0,
            is_conformant=(mins != 100),
            variant_signature="n_start -> n_task -> n_end",
            step_trace_json=[
                {"node_id": "n_task", "label": "Initial Triage", "lane": "lane_intake", "duration_minutes": mins, "exited_at": now.isoformat()}
            ],
        )

    # 1 escalated (sla_breached) instance with open trace step -> counts in active_wip & active_waiting
    esc_inst = start_process_instance(tenant_a, process_definition, target_document, actor=admin_user)
    advance_process_instance(esc_inst, outcome="escalated", actor=admin_user)

    # 1 cancelled instance with open trace step (manually simulated legacy open trace) -> excluded from active_wip & active_waiting
    DocumentProcessInstance.objects.create(
        tenant=tenant_a,
        process_definition=process_definition,
        document=document,
        status="cancelled",
        current_node_id="n_task",
        started_at=now,
        completed_at=now,
        variant_signature="n_start -> n_task",
        step_trace_json=[
            {"node_id": "n_task", "label": "Initial Triage", "lane": "lane_intake", "duration_minutes": 5, "exited_at": None}
        ],
    )

    # Noise instance in tenant_b must not leak into tenant_a analytics
    proc_b = _workflow_automation_create_process(tenant_b, admin_b, name="Globex Proc", code="GLX-A")
    doc_b = Document.objects.create(tenant=tenant_b, title="Globex Doc", owner=admin_b)
    start_process_instance(tenant_b, proc_b, doc_b, actor=admin_b)

    analytics = compute_process_analytics(tenant_a, process_def_id=process_definition.pk)
    assert analytics["total_instances"] == 6
    assert analytics["completed_count"] == 4
    assert analytics["active_wip"] == 1  # the sla_breached instance
    assert analytics["sla_breached_count"] == 1
    assert analytics["avg_cycle_minutes"] == 40.0  # (10+20+30+100)/4
    assert analytics["median_cycle_minutes"] == 25.0  # (20+30)/2
    assert analytics["p95_cycle_minutes"] == 100.0

    # Bottlenecks count open steps on non-terminal runs only (1 from sla_breached, 0 from cancelled)
    triage_bn = [b for b in analytics["bottlenecks"] if b["node_id"] == "n_task"][0]
    assert triage_bn["active_waiting"] == 1

    # Date range filter restricting to today only excludes idx=1,2,3 completed runs
    today = timezone.localdate()
    filtered = compute_process_analytics(
        tenant_a, process_def_id=process_definition.pk, date_from=today, date_to=today
    )
    assert filtered["total_instances"] == 3  # cycle=10 + escalated + cancelled


# ---------------------------------------------------------------------------
# 4. DocumentWebhookTrigger Security, Crypto & Dispatch Tests
# ---------------------------------------------------------------------------

def test_workflow_automation_webhook_crypto_hmac_and_fail_closed(tenant_a, admin_user, webhook_trigger, settings):
    """Verify DWHK- numbering, Fernet encryption, prefix masking, HMAC verification, and fail-closed decrypt."""
    assert webhook_trigger.number.startswith("DWHK-")
    assert webhook_trigger.signing_secret.startswith("fernet.v1:")
    assert len(webhook_trigger.signing_secret_prefix) == 8
    assert webhook_trigger.masked_secret.startswith(webhook_trigger.signing_secret_prefix)
    assert "••••" in webhook_trigger.masked_secret

    raw_secret = webhook_trigger.get_signing_secret()
    assert len(raw_secret) == 64
    assert raw_secret.startswith(webhook_trigger.signing_secret_prefix)

    payload = json.dumps({"event": "process.completed"}, sort_keys=True, separators=(",", ":")).encode("utf-8")
    sig = webhook_trigger.compute_signature(payload)
    assert webhook_trigger.verify_signature(payload, sig) is True
    assert webhook_trigger.verify_signature(payload, "deadbeef") is False
    assert webhook_trigger.verify_signature(payload, "") is False

    # Fail-closed when ciphertext is corrupted or key changes
    webhook_trigger.signing_secret = "fernet.v1:not-valid-fernet-token"
    with pytest.raises(ImproperlyConfigured):
        webhook_trigger.get_signing_secret()


def test_workflow_automation_webhook_ssrf_and_flat_header_validations(tenant_a, admin_user):
    """Verify SSRF IP/hostname protections and flat RFC 7230 header validations."""
    blocked_urls = [
        "",
        "ftp://hooks.example.com/hook",
        "https://user:pass@hooks.example.com/hook",
        "https://hooks.example.com/bad path",
        "https://hooks.example.com/bad\\path",
        "http://localhost/hook",
        "http://sub.localhost/hook",
        "http://metadata.google.internal/computeMetadata/v1/",
        "http://service.local/hook",
        "http://127.0.0.1/hook",
        "http://[::1]/hook",
        "http://[fe80::1%eth0]/hook",
        "http://10.0.0.1/hook",
        "http://172.16.0.1/hook",
        "http://192.168.1.1/hook",
        "http://169.254.169.254/latest/meta-data/",
        "http://100.64.0.1/hook",
        "https://[::ffff:127.0.0.1]/hook",
        "http://[64:ff9b::10.0.0.1]/hook",
        "http://[64:ff9b::127.0.0.1]/hook",
        "http://0177.0.0.1/hook",
        "http://2130706433/hook",
    ]
    for bad_url in blocked_urls:
        with pytest.raises(ValidationError):
            validate_dms_webhook_url(bad_url)

    assert validate_dms_webhook_url("https://hooks.partner-erp.example/dms") == "https://hooks.partner-erp.example/dms"

    # Model clean requires target_url for outbound/middleware, permits blank for inbound
    wh_out = DocumentWebhookTrigger(
        tenant=tenant_a, name="Missing URL", direction="outbound_webhook", target_url="", owner=admin_user
    )
    with pytest.raises(ValidationError) as exc_out:
        wh_out.clean()
    assert "target_url" in exc_out.value.message_dict

    wh_in = DocumentWebhookTrigger(
        tenant=tenant_a, name="Inbound Blank URL OK", direction="inbound_webhook", target_url="", owner=admin_user
    )
    wh_in.clean()

    # Header validations: CR/LF/NUL, forbidden denylist, duplicates, count/length
    bad_headers_list = [
        ["not-a-dict"],
        {"": "val"},
        {"X-Test": 123},
        {"X-Bad\r\nInject": "val"},
        {"X-Test": "val\ninjected"},
        {"X-Test": "val\x00null"},
        {"Host": "evil.com"},
        {"Authorization": "Bearer leak"},
        {"X-NavERP-Signature-256": "forged"},
        {"X-Dup": "1", "x-dup": "2"},
        {"X-Big": "A" * 2049},
        {f"X-H-{i}": "v" for i in range(26)},
    ]
    for bad_hdr in bad_headers_list:
        with pytest.raises(ValidationError):
            validate_flat_headers(bad_hdr)

    assert validate_flat_headers({"  X-NavERP-Channel  ": "dms"}) == {"X-NavERP-Channel": "dms"}


def test_workflow_automation_webhook_delivery_cap_and_event_filtering(
    tenant_a, admin_user, document, process_definition, webhook_trigger
):
    """Verify 25-entry delivery ring buffer, atomic fire_count, CloudEvents envelope, and doc_type/direction filtering."""
    # Cap delivery_history_json at 25 entries across 30 deliveries
    for i in range(30):
        entry = dispatch_simulated_webhook(
            webhook_trigger,
            "process.completed",
            {"seq": i},
            document=document if i == 0 else None,
            actor=admin_user,
        )
        assert entry["status"] == "simulated"
        assert entry["payload"]["specversion"] == "1.0"
        assert entry["payload"]["data"]["seq"] == i

    webhook_trigger.refresh_from_db()
    assert webhook_trigger.fire_count == 30
    assert webhook_trigger.last_status == "simulated"
    assert len(webhook_trigger.delivery_history_json) == 25
    assert webhook_trigger.delivery_history_json[0]["payload"]["data"]["seq"] == 5
    assert webhook_trigger.delivery_history_json[-1]["payload"]["data"]["seq"] == 29

    # Direction & filter_document_type filtering during process start/completion
    wh_inbound = _workflow_automation_create_webhook(
        tenant_a,
        admin_user,
        name="Inbound Ignored On Event",
        direction="inbound_webhook",
        trigger_event="process.started",
        target_url="",
        process_definition=process_definition,
    )
    wh_contract_only = _workflow_automation_create_webhook(
        tenant_a,
        admin_user,
        name="Contract Start Only",
        direction="middleware_callback",
        trigger_event="process.started",
        process_definition=process_definition,
        filter_document_type="contract",
    )
    wh_all_starts = _workflow_automation_create_webhook(
        tenant_a,
        admin_user,
        name="All Doc Start",
        direction="outbound_webhook",
        trigger_event="process.started",
        process_definition=process_definition,
        filter_document_type="",
    )

    # `document` fixture has document_type="sop" -> contract-only & inbound triggers must NOT fire
    start_process_instance(tenant_a, process_definition, document, actor=admin_user)
    wh_inbound.refresh_from_db()
    wh_contract_only.refresh_from_db()
    wh_all_starts.refresh_from_db()
    assert wh_inbound.fire_count == 0
    assert wh_contract_only.fire_count == 0
    assert wh_all_starts.fire_count == 1

    # Contract document fires wh_contract_only and wh_all_starts
    contract_doc = Document.objects.create(
        tenant=tenant_a, title="Vendor MSA", document_type="contract", owner=admin_user
    )
    start_process_instance(tenant_a, process_definition, contract_doc, actor=admin_user)
    wh_contract_only.refresh_from_db()
    wh_all_starts.refresh_from_db()
    assert wh_contract_only.fire_count == 1
    assert wh_all_starts.fire_count == 2
