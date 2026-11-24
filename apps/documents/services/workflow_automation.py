"""Shared BPM, routing, webhook simulation, and process mining services for DMS 13.11."""
from collections import defaultdict, deque
from datetime import timedelta
from decimal import Decimal, InvalidOperation
import ipaddress
import json
import math
import re
import socket
from urllib.parse import urlparse

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

ALLOWED_WEBHOOK_SCHEMES = frozenset({"https", "http"})
BLOCKED_WEBHOOK_HOSTNAMES = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "127.0.0.1",
        "::1",
        "0.0.0.0",
        "metadata.google.internal",
        "169.254.169.254",
    }
)
BLOCKED_WEBHOOK_SUFFIXES = (".local", ".internal", ".localhost")
_CGNAT_NETWORK = ipaddress.ip_network("100.64.0.0/10")

BPMN_NODE_TYPES = frozenset(
    {
        "start_event",
        "user_task",
        "service_task",
        "approval_subprocess",
        "exclusive_gateway",
        "parallel_gateway",
        "inclusive_gateway",
        "timer_event",
        "webhook_task",
        "end_event",
    }
)

SUPPORTED_RULE_OPERATORS = frozenset(
    {
        "eq",
        "ne",
        "gt",
        "gte",
        "lt",
        "lte",
        "in",
        "not_in",
        "contains",
        "regex_match",
        "is_set",
        "is_empty",
    }
)


def _unwrap_ip_targets(ip_obj):
    seen = set()
    stack = [ip_obj]
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        yield cur
        if isinstance(cur, ipaddress.IPv6Address):
            if cur.ipv4_mapped is not None:
                stack.append(cur.ipv4_mapped)
            if cur.sixtofour is not None:
                stack.append(cur.sixtofour)
            if cur.teredo is not None:
                stack.extend(cur.teredo)


def _is_blocked_ip(ip_obj):
    for ip_check in _unwrap_ip_targets(ip_obj):
        if (
            not ip_check.is_global
            or ip_check.is_private
            or ip_check.is_loopback
            or ip_check.is_link_local
            or ip_check.is_multicast
            or ip_check.is_reserved
            or ip_check.is_unspecified
            or (isinstance(ip_check, ipaddress.IPv4Address) and ip_check in _CGNAT_NETWORK)
        ):
            return True
    return False


def validate_dms_webhook_url(value):
    """Validate webhook URL against SSRF vectors (loopback, RFC1918, metadata, CGNAT)."""
    raw = (value or "").strip()
    if not raw:
        raise ValidationError("Target URL is required.")
    if any(ch.isspace() or ord(ch) < 32 or ord(ch) == 127 for ch in raw):
        raise ValidationError("Webhook URL cannot contain whitespace or control characters.")
    if "\\" in raw:
        raise ValidationError("Webhook URL cannot contain backslash characters.")

    parsed = urlparse(raw)
    scheme = (parsed.scheme or "").lower()
    if scheme not in ALLOWED_WEBHOOK_SCHEMES:
        raise ValidationError("Only https:// or http:// webhook URLs are permitted.")
    if parsed.username is not None or parsed.password is not None or "@" in (parsed.netloc or ""):
        raise ValidationError("Webhook URL must not contain embedded user credentials.")

    try:
        _ = parsed.port
    except ValueError as exc:
        raise ValidationError("Webhook URL contains an invalid port number.") from exc

    raw_host = (parsed.hostname or "").strip().rstrip(".")
    if not raw_host:
        raise ValidationError("Webhook URL must include a valid hostname or IP address.")
    if "%" in raw_host:
        raise ValidationError("Percent-encoded hosts and IPv6 zone identifiers are not permitted.")

    try:
        hostname = raw_host.encode("idna").decode("ascii").rstrip(".").lower()
    except UnicodeError as exc:
        raise ValidationError("Webhook URL contains an invalid internationalized host name.") from exc

    if not hostname or hostname in BLOCKED_WEBHOOK_HOSTNAMES or hostname.endswith(BLOCKED_WEBHOOK_SUFFIXES):
        raise ValidationError("Localhost, link-local, and internal host targets are not permitted.")

    ip_candidates = []
    try:
        ip_candidates.append(ipaddress.ip_address(hostname))
    except ValueError:
        pass
    try:
        packed_ipv4 = socket.inet_aton(hostname)
    except OSError:
        packed_ipv4 = None
    if packed_ipv4 is not None:
        ip_candidates.append(ipaddress.IPv4Address(packed_ipv4))

    for ip_obj in ip_candidates:
        if _is_blocked_ip(ip_obj):
            raise ValidationError(
                "Private, loopback, link-local, CGNAT, multicast, or reserved IP addresses are not permitted."
            )
    return raw


def validate_flat_headers(headers):
    """Validate custom headers are a flat {str: str} mapping without CR/LF/NUL characters."""
    if headers is None or headers == "":
        return {}
    if not isinstance(headers, dict):
        raise ValidationError("Custom headers must be a JSON object of string key-value pairs.")
    cleaned = {}
    for key, val in headers.items():
        if not isinstance(key, str) or not isinstance(val, str):
            raise ValidationError("Every custom header key and value must be a flat string.")
        if not key.strip():
            raise ValidationError("Custom header names cannot be blank.")
        for text in (key, val):
            if "\r" in text or "\n" in text or "\x00" in text:
                raise ValidationError("Custom headers must not contain CR, LF, or null bytes.")
        cleaned[key.strip()] = val
    return cleaned


def validate_process_graph(swimlanes, nodes, transitions):
    """Validate BPMN process blueprint connectivity, start/end gates, and gateway defaults."""
    errors = []
    warnings = []

    if not isinstance(swimlanes, list):
        errors.append("Swimlanes must be a JSON array.")
        swimlanes = []
    if not isinstance(nodes, list):
        errors.append("Nodes must be a JSON array.")
        nodes = []
    if not isinstance(transitions, list):
        errors.append("Transitions must be a JSON array.")
        transitions = []

    if not nodes:
        errors.append("Process blueprint must define at least one node.")
        return {
            "is_valid": False,
            "errors": errors,
            "warnings": warnings,
            "node_count": 0,
            "transition_count": len(transitions),
        }

    node_map = {}
    start_ids = []
    end_ids = []
    for idx, node in enumerate(nodes):
        if not isinstance(node, dict):
            errors.append(f"Node at index {idx} must be an object.")
            continue
        nid = str(node.get("id") or "").strip()
        ntype = str(node.get("type") or "").strip()
        if not nid:
            errors.append(f"Node at index {idx} is missing an 'id'.")
            continue
        if nid in node_map:
            errors.append(f"Duplicate node id '{nid}'.")
            continue
        if ntype not in BPMN_NODE_TYPES:
            errors.append(f"Node '{nid}' uses unsupported type '{ntype}'.")
        node_map[nid] = node
        if ntype == "start_event":
            start_ids.append(nid)
        elif ntype == "end_event":
            end_ids.append(nid)

    if not start_ids:
        errors.append("Process blueprint requires at least one 'start_event' node.")
    if not end_ids:
        errors.append("Process blueprint requires at least one 'end_event' node.")

    outgoing = defaultdict(list)
    for idx, edge in enumerate(transitions):
        if not isinstance(edge, dict):
            errors.append(f"Transition at index {idx} must be an object.")
            continue
        src = str(edge.get("from_node") or "").strip()
        dst = str(edge.get("to_node") or "").strip()
        if src not in node_map:
            errors.append(f"Transition #{idx + 1} references unknown source node '{src}'.")
            continue
        if dst not in node_map:
            errors.append(f"Transition #{idx + 1} references unknown target node '{dst}'.")
            continue
        if src == dst:
            warnings.append(f"Transition on node '{src}' forms a direct self-loop.")
        outgoing[src].append(edge)

    for nid, node in node_map.items():
        ntype = node.get("type")
        edges = outgoing.get(nid, [])
        if ntype != "end_event" and len(nodes) > 1 and not edges:
            warnings.append(f"Non-terminal node '{nid}' has no outgoing transitions.")
        if ntype in ("exclusive_gateway", "inclusive_gateway"):
            if len(edges) > 1 and not any(bool(e.get("is_default")) for e in edges):
                warnings.append(f"Gateway '{nid}' has multiple branches without a default edge.")

    if start_ids and node_map:
        visited = set(start_ids)
        queue = deque(start_ids)
        while queue:
            cur = queue.popleft()
            for edge in outgoing.get(cur, []):
                nxt = str(edge.get("to_node") or "").strip()
                if nxt in node_map and nxt not in visited:
                    visited.add(nxt)
                    queue.append(nxt)
        unreachable = [nid for nid in node_map if nid not in visited]
        if unreachable and transitions:
            warnings.append(f"Unreachable nodes from start_event: {', '.join(unreachable)}.")

    return {
        "is_valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "node_count": len(node_map),
        "transition_count": len(transitions),
    }


def _to_finite_decimal(val):
    if val is None or isinstance(val, bool):
        return None
    try:
        dec = Decimal(str(val).strip())
        if not dec.is_finite():
            return None
        return dec
    except (InvalidOperation, ValueError, TypeError):
        return None


def _resolve_doc_field(doc_ctx, source, field):
    source_key = (source or "document").strip().lower()
    if source_key == "metadata":
        return doc_ctx.get("metadata", {}).get(field)
    if source_key == "ocr":
        return doc_ctx.get("ocr", {}).get(field)
    if source_key == "context":
        return doc_ctx.get("context", {}).get(field)
    return doc_ctx.get("document", {}).get(field)


def evaluate_condition_clause(clause, doc_ctx):
    """Evaluate a single structured rule clause against normalized document context."""
    if not isinstance(clause, dict):
        return {"matched": False, "actual": None, "reason": "Invalid clause object"}

    source = clause.get("source", "document")
    field = str(clause.get("field") or "").strip()
    op = str(clause.get("op") or "eq").strip().lower()
    expected = clause.get("value")
    actual = _resolve_doc_field(doc_ctx, source, field)

    if op not in SUPPORTED_RULE_OPERATORS:
        return {"matched": False, "actual": actual, "reason": f"Unsupported operator '{op}'"}

    matched = False
    if op == "is_set":
        matched = actual is not None and str(actual).strip() != ""
    elif op == "is_empty":
        matched = actual is None or str(actual).strip() == ""
    elif op == "eq":
        d_act, d_exp = _to_finite_decimal(actual), _to_finite_decimal(expected)
        if d_act is not None and d_exp is not None:
            matched = d_act == d_exp
        else:
            matched = str(actual or "").strip().lower() == str(expected or "").strip().lower()
    elif op == "ne":
        d_act, d_exp = _to_finite_decimal(actual), _to_finite_decimal(expected)
        if d_act is not None and d_exp is not None:
            matched = d_act != d_exp
        else:
            matched = str(actual or "").strip().lower() != str(expected or "").strip().lower()
    elif op in ("gt", "gte", "lt", "lte"):
        d_act, d_exp = _to_finite_decimal(actual), _to_finite_decimal(expected)
        if d_act is not None and d_exp is not None:
            if op == "gt":
                matched = d_act > d_exp
            elif op == "gte":
                matched = d_act >= d_exp
            elif op == "lt":
                matched = d_act < d_exp
            else:
                matched = d_act <= d_exp
    elif op in ("in", "not_in"):
        items = expected if isinstance(expected, (list, tuple, set)) else [
            part.strip() for part in str(expected or "").split(",") if part.strip()
        ]
        norm_items = {str(item).strip().lower() for item in items}
        in_set = str(actual or "").strip().lower() in norm_items
        matched = in_set if op == "in" else not in_set
    elif op == "contains":
        matched = str(expected or "").strip().lower() in str(actual or "").strip().lower()
    elif op == "regex_match":
        pattern = str(expected or "")
        if len(pattern) <= 200:
            try:
                matched = bool(re.search(pattern, str(actual or ""), re.IGNORECASE))
            except re.error:
                matched = False

    return {
        "source": source,
        "field": field,
        "op": op,
        "expected": expected,
        "actual": actual,
        "matched": matched,
    }


def simulate_process_path(process_def, context=None):
    """Run a deterministic dry-run path walk from start_event across BPMN nodes."""
    nodes = process_def.nodes_json or []
    transitions = process_def.transitions_json or []
    node_map = {str(n.get("id")): n for n in nodes if isinstance(n, dict) and n.get("id")}
    if not node_map:
        return []

    outgoing = defaultdict(list)
    for edge in transitions:
        if isinstance(edge, dict) and edge.get("from_node") and edge.get("to_node"):
            outgoing[str(edge["from_node"])].append(edge)

    starts = [nid for nid, n in node_map.items() if n.get("type") == "start_event"]
    current_id = starts[0] if starts else next(iter(node_map.keys()))
    doc_ctx = {"document": context or {}, "metadata": {}, "ocr": {}, "context": context or {}}

    steps = []
    visited_guard = defaultdict(int)
    max_steps = max(20, len(node_map) * 2)

    while current_id and current_id in node_map and len(steps) < max_steps:
        visited_guard[current_id] += 1
        if visited_guard[current_id] > 3:
            break
        node = node_map[current_id]
        edges = outgoing.get(current_id, [])
        chosen_edge = None
        for edge in edges:
            cond = edge.get("condition")
            if isinstance(cond, dict) and cond.get("field"):
                res = evaluate_condition_clause(cond, doc_ctx)
                if res["matched"]:
                    chosen_edge = edge
                    break
        if chosen_edge is None:
            for edge in edges:
                if edge.get("is_default"):
                    chosen_edge = edge
                    break
        if chosen_edge is None and edges:
            chosen_edge = edges[0]

        steps.append(
            {
                "node_id": current_id,
                "type": node.get("type", "user_task"),
                "label": node.get("label", current_id),
                "lane": node.get("lane_id", ""),
                "selected_transition": chosen_edge.get("label", "") if chosen_edge else "",
                "next_node": chosen_edge.get("to_node", "") if chosen_edge else "",
            }
        )
        if node.get("type") == "end_event" or not chosen_edge:
            break
        current_id = str(chosen_edge.get("to_node") or "")

    return steps


def build_document_context(tenant, document):
    """Build unified attribute, metadata, and OCR context dictionary for rule evaluation."""
    from apps.documents.models.MetadataIndexing.DocumentMetadataValues import DocumentMetadataValue
    from apps.documents.models.MetadataIndexing.DocumentOcrJobs import DocumentOcrJob

    latest_ver = document.versions.filter(tenant=tenant).order_by("-created_at", "-id").first()
    meta_qs = DocumentMetadataValue.objects.filter(
        tenant=tenant, document=document, version__isnull=True
    ).order_by("field_name")
    metadata = {}
    for mv in meta_qs:
        metadata[mv.field_name] = mv.display_value

    ocr_job = (
        DocumentOcrJob.objects.filter(tenant=tenant, document=document, status="completed")
        .order_by("-created_at", "-id")
        .first()
    )
    ocr_ctx = {
        "confidence_score": float(ocr_job.confidence_score) if ocr_job and ocr_job.confidence_score is not None else None,
        "suggested_category": ocr_job.suggested_category if ocr_job else "",
        "has_handwriting": ocr_job.has_handwriting if ocr_job else False,
        "has_barcode": ocr_job.has_barcode if ocr_job else False,
    }

    doc_ctx = {
        "number": document.number,
        "title": document.title,
        "document_type": document.document_type,
        "classification": document.classification,
        "status": document.status,
        "tags": document.tags,
        "current_version_label": document.current_version_label,
        "current_version_no": document.current_version_no,
        "department": document.department.name if document.department_id else "",
        "department_id": document.department_id,
        "owner": document.owner.username if document.owner_id else "",
        "is_locked": document.is_locked,
        "file_size": latest_ver.file_size if latest_ver else 0,
        "file_name": latest_ver.file_name if latest_ver else "",
    }
    return {"document": doc_ctx, "metadata": metadata, "ocr": ocr_ctx, "context": doc_ctx}


def _resolve_org_unit_manager_user(tenant, org_unit):
    """Resolve active manager User for an OrgUnit via core.Employment (L61 deterministic order)."""
    if not org_unit:
        return None
    from apps.core.models.Employment import Employment

    User = get_user_model()
    emp = (
        Employment.objects.filter(
            tenant=tenant, org_unit=org_unit, status="active", manager__isnull=False
        )
        .select_related("manager")
        .order_by("pk")
        .first()
    )
    if emp and emp.manager_id:
        mgr_user = User.objects.filter(
            tenant=tenant, party_id=emp.manager_id, is_active=True
        ).order_by("pk").first()
        if mgr_user:
            return mgr_user
    return None


def _apply_folder_routing(tenant, document, folder, actor=None):
    """Apply DocumentFolder routing using tags, optional department, and DocumentMetadataValue."""
    from apps.documents.models.MetadataIndexing.DocumentMetadataValues import DocumentMetadataValue

    existing_tags = [t.strip() for t in (document.tags or "").split(",") if t.strip()]
    if folder.slug and folder.slug not in existing_tags:
        existing_tags.append(folder.slug)
    new_tags = ", ".join(existing_tags)[:500]
    update_fields = ["tags", "updated_at"]
    document.tags = new_tags
    if folder.department_id and not document.department_id:
        document.department = folder.department
        update_fields.append("department")
    document.save(update_fields=update_fields)

    DocumentMetadataValue.objects.update_or_create(
        tenant=tenant,
        document=document,
        version=None,
        field_name="routed_folder_path",
        defaults={
            "field_label": "Routed Folder Path",
            "data_type": "text",
            "value_text": folder.path or f"/{folder.slug}/",
            "source": "bulk_updated",
            "updated_by": actor,
        },
    )


def _apply_auto_populate(tenant, document, auto_populate, actor=None):
    """Apply safe document field & metadata upserts defined in rule.auto_populate_json."""
    from apps.documents.models.MetadataIndexing.DocumentMetadataValues import DocumentMetadataValue

    if not isinstance(auto_populate, dict):
        return []
    changes = []

    doc_fields = auto_populate.get("document_fields") or {}
    if isinstance(doc_fields, dict):
        allowed_doc_fields = {"classification", "status", "tags"}
        valid_classifications = {c[0] for c in document.CLASSIFICATION_CHOICES}
        valid_statuses = {s[0] for s in document.STATUS_CHOICES}
        dirty = []
        for field_name, val in doc_fields.items():
            if field_name not in allowed_doc_fields:
                continue
            if field_name == "classification" and val not in valid_classifications:
                continue
            if field_name == "status" and val not in valid_statuses:
                continue
            if field_name == "tags":
                existing = [t.strip() for t in (document.tags or "").split(",") if t.strip()]
                for t in str(val).split(","):
                    ts = t.strip()
                    if ts and ts not in existing:
                        existing.append(ts)
                document.tags = ", ".join(existing)[:500]
            else:
                setattr(document, field_name, val)
            dirty.append(field_name)
            changes.append(f"document.{field_name}={val}")
        if dirty:
            dirty.append("updated_at")
            document.save(update_fields=dirty)

    meta_fields = auto_populate.get("metadata_fields") or {}
    if isinstance(meta_fields, dict):
        for m_key, m_val in meta_fields.items():
            key_clean = str(m_key).strip()[:100]
            if not key_clean:
                continue
            DocumentMetadataValue.objects.update_or_create(
                tenant=tenant,
                document=document,
                version=None,
                field_name=key_clean,
                defaults={
                    "field_label": key_clean.replace("_", " ").title()[:150],
                    "data_type": "text",
                    "value_text": str(m_val),
                    "source": "bulk_updated",
                    "updated_by": actor,
                },
            )
            changes.append(f"metadata.{key_clean}={m_val}")
    return changes


def evaluate_routing_rules(
    tenant,
    document,
    rules=None,
    trigger_event=None,
    apply_mutations=False,
    actor=None,
    request=None,
):
    """Evaluate active routing/business rules against a document (dry-run or live apply)."""
    from apps.documents.models.ApprovalWorkflow.DocumentApprovalWorkflows import DocumentApprovalWorkflow
    from apps.documents.models.CollaborationSharing.DocumentTasks import DocumentTask
    from apps.documents.models.WorkflowAutomation.DocumentRoutingRules import DocumentRoutingRule
    from apps.documents.services.audit import log_document_event

    if rules is None:
        qs = DocumentRoutingRule.objects.filter(tenant=tenant, is_active=True).select_related(
            "process_definition",
            "source_folder",
            "destination_folder",
            "route_to_org_unit",
            "route_to_role",
            "route_to_user",
        )
        if trigger_event:
            qs = qs.filter(trigger_event=trigger_event)
        rules = list(qs.order_by("priority", "pk"))

    doc_ctx = build_document_context(tenant, document)
    User = get_user_model()
    results = []

    for rule in rules:
        # Scope checks
        scope_ok = True
        scope_reasons = []
        if rule.target_document_type and rule.target_document_type != document.document_type:
            scope_ok = False
            scope_reasons.append(f"document_type '{document.document_type}' != '{rule.target_document_type}'")
        if rule.target_classification and rule.target_classification != document.classification:
            scope_ok = False
            scope_reasons.append(f"classification '{document.classification}' != '{rule.target_classification}'")
        if rule.source_folder_id:
            folder_slug = rule.source_folder.slug
            tags_lower = (document.tags or "").lower()
            routed_path = doc_ctx["metadata"].get("routed_folder_path", "")
            if folder_slug not in tags_lower and rule.source_folder.path != routed_path:
                scope_ok = False
                scope_reasons.append(f"document not filed in source folder '{rule.source_folder.name}'")

        clause_traces = []
        conditions = rule.conditions_json or []
        if not scope_ok:
            cond_matched = False
        elif not conditions:
            cond_matched = True
        else:
            clause_traces = [evaluate_condition_clause(c, doc_ctx) for c in conditions]
            if rule.condition_logic_mode == "any_or":
                cond_matched = any(t["matched"] for t in clause_traces)
            else:
                cond_matched = all(t["matched"] for t in clause_traces)

        validation_errors = []
        if scope_ok and cond_matched:
            for vrule in rule.validation_rules_json or []:
                if not isinstance(vrule, dict):
                    continue
                check_kind = vrule.get("check", "required_metadata")
                vfield = str(vrule.get("field") or "").strip()
                msg = vrule.get("message") or f"Validation check '{check_kind}' failed."
                if check_kind == "required_metadata" and vfield:
                    val = doc_ctx["metadata"].get(vfield)
                    if val is None or str(val).strip() == "":
                        validation_errors.append(msg)
                elif check_kind == "min_ocr_confidence":
                    min_conf = _to_finite_decimal(vrule.get("min_confidence", 0.7))
                    actual_conf = _to_finite_decimal(doc_ctx["ocr"].get("confidence_score"))
                    if min_conf is not None and (actual_conf is None or actual_conf < min_conf):
                        validation_errors.append(msg)
                elif check_kind == "not_status" and vfield:
                    if document.status == vfield:
                        validation_errors.append(msg)

        used_else = False
        effective_action = None
        if scope_ok and cond_matched and not validation_errors:
            effective_action = rule.route_action
        elif scope_ok and not cond_matched and rule.else_branch_enabled:
            used_else = True
            else_cfg = rule.else_action_json or {}
            effective_action = else_cfg.get("route_action") or "else_fallback"

        applied_actions = []
        if apply_mutations:
            with transaction.atomic():
                now = timezone.now()
                update_kwargs = {"execution_count": F("execution_count") + 1, "last_evaluated_at": now}
                if scope_ok and cond_matched:
                    update_kwargs["match_count"] = F("match_count") + 1
                DocumentRoutingRule.objects.filter(pk=rule.pk).update(**update_kwargs)

                if scope_ok and cond_matched and not validation_errors:
                    pop_changes = _apply_auto_populate(tenant, document, rule.auto_populate_json, actor=actor)
                    applied_actions.extend(pop_changes)

                    if rule.route_action == "move_to_folder" and rule.destination_folder_id:
                        _apply_folder_routing(tenant, document, rule.destination_folder, actor=actor)
                        applied_actions.append(f"filed->{rule.destination_folder.path}")
                        log_document_event(
                            tenant=tenant,
                            action_type="moved",
                            document=document,
                            actor=actor,
                            request=request,
                            details={"bpm_event": "routing.moved_to_folder", "rule": rule.number, "folder": rule.destination_folder.path},
                        )
                    elif rule.route_action == "assign_user" and rule.route_to_user_id:
                        document.owner = rule.route_to_user
                        document.save(update_fields=["owner", "updated_at"])
                        applied_actions.append(f"owner->{rule.route_to_user.username}")
                    elif rule.route_action == "assign_org_unit_head" and rule.route_to_org_unit_id:
                        document.department = rule.route_to_org_unit
                        mgr_user = _resolve_org_unit_manager_user(tenant, rule.route_to_org_unit)
                        if mgr_user:
                            document.owner = mgr_user
                            document.save(update_fields=["department", "owner", "updated_at"])
                            applied_actions.append(f"org_head->{mgr_user.username}")
                        else:
                            document.save(update_fields=["department", "updated_at"])
                            applied_actions.append(f"department->{rule.route_to_org_unit.name}")
                    elif rule.route_action == "assign_role" and rule.route_to_role_id:
                        assignee = User.objects.filter(
                            tenant=tenant, role_id=rule.route_to_role_id, is_active=True
                        ).order_by("pk").first()
                        DocumentTask.objects.create(
                            tenant=tenant,
                            document=document,
                            title=f"Rule {rule.number}: {rule.name}"[:255],
                            description=f"Auto-assigned to role '{rule.route_to_role.name}'.",
                            task_type="review",
                            priority="medium",
                            assigned_to=assignee,
                            assigned_by=actor or document.owner,
                        )
                        applied_actions.append(f"role_task->{rule.route_to_role.name}")
                    elif rule.route_action == "create_document_task":
                        DocumentTask.objects.create(
                            tenant=tenant,
                            document=document,
                            title=f"Routing Task: {rule.name}"[:255],
                            description=rule.description or f"Dispatched by routing rule {rule.number}.",
                            task_type="general_todo",
                            priority="medium",
                            assigned_to=rule.route_to_user,
                            assigned_org_unit=rule.route_to_org_unit,
                            assigned_by=actor or document.owner,
                        )
                        applied_actions.append("task_created")
                    elif rule.route_action == "spawn_approval_workflow":
                        wf = DocumentApprovalWorkflow.objects.create(
                            tenant=tenant,
                            document=document,
                            title=f"{rule.name} — {document.title}"[:255],
                            workflow_type="sequential",
                            status="draft",
                            initiator=actor or document.owner,
                            department=rule.route_to_org_unit or document.department,
                        )
                        applied_actions.append(f"spawned_dwf->{wf.number}")
                    elif rule.route_action == "trigger_process" and rule.process_definition_id:
                        inst = start_process_instance(
                            tenant=tenant,
                            process_definition=rule.process_definition,
                            document=document,
                            actor=actor,
                            department=rule.route_to_org_unit or document.department,
                            assignee=rule.route_to_user,
                            triggered_by_rule=rule,
                            request=request,
                        )
                        applied_actions.append(f"started_dpin->{inst.number}")

                    if pop_changes or applied_actions:
                        log_document_event(
                            tenant=tenant,
                            action_type="edited",
                            document=document,
                            actor=actor,
                            request=request,
                            details={
                                "bpm_event": "routing.matched",
                                "rule": rule.number,
                                "action": rule.route_action,
                                "changes": applied_actions,
                            },
                        )
                elif scope_ok and cond_matched and validation_errors:
                    log_document_event(
                        tenant=tenant,
                        action_type="workflow_rejected",
                        document=document,
                        actor=actor,
                        request=request,
                        is_success=False,
                        failure_reason="routing_validation_failed",
                        details={"bpm_event": "routing.validation_blocked", "rule": rule.number, "errors": validation_errors},
                    )
                elif used_else:
                    else_cfg = rule.else_action_json or {}
                    else_meta = else_cfg.get("metadata_fields") or {}
                    if else_meta:
                        pop_changes = _apply_auto_populate(tenant, document, {"metadata_fields": else_meta}, actor=actor)
                        applied_actions.extend(pop_changes)

        results.append(
            {
                "rule": rule,
                "scope_ok": scope_ok,
                "scope_reasons": scope_reasons,
                "matched": scope_ok and cond_matched,
                "used_else": used_else,
                "clause_traces": clause_traces,
                "validation_errors": validation_errors,
                "effective_action": effective_action,
                "applied_actions": applied_actions,
            }
        )

    return results


def _build_variant_signature(trace):
    parts = []
    for item in trace:
        nid = str(item.get("node_id") or "").strip()
        if nid:
            parts.append(nid)
    return " -> ".join(parts)[:500]


def start_process_instance(
    tenant,
    process_definition,
    document,
    actor=None,
    version=None,
    department=None,
    assignee=None,
    triggered_by_rule=None,
    context_variables=None,
    request=None,
):
    """Initialize and launch a live DocumentProcessInstance for a document."""
    from apps.documents.models.ApprovalWorkflow.DocumentApprovalWorkflows import DocumentApprovalWorkflow
    from apps.documents.models.WorkflowAutomation.DocumentProcessDefinitions import DocumentProcessDefinition
    from apps.documents.models.WorkflowAutomation.DocumentProcessInstances import DocumentProcessInstance
    from apps.documents.models.WorkflowAutomation.DocumentWebhookTriggers import DocumentWebhookTrigger
    from apps.documents.services.audit import log_document_event

    now = timezone.now()
    nodes = process_definition.nodes_json or []
    transitions = process_definition.transitions_json or []
    node_map = {str(n.get("id")): n for n in nodes if isinstance(n, dict) and n.get("id")}

    start_nodes = [n for n in nodes if isinstance(n, dict) and n.get("type") == "start_event"]
    first_node = start_nodes[0] if start_nodes else (nodes[0] if nodes else {"id": "start", "type": "start_event", "label": "Start"})
    first_id = str(first_node.get("id") or "start")

    trace = [
        {
            "node_id": first_id,
            "node_type": first_node.get("type", "start_event"),
            "label": first_node.get("label", "Start"),
            "lane": first_node.get("lane_id", ""),
            "entered_at": now.isoformat(),
            "exited_at": now.isoformat(),
            "duration_minutes": 0,
            "outcome": "started",
            "actor": actor.username if actor else "system",
        }
    ]

    # Advance from start_event to first active node if outgoing transition exists
    next_id = first_id
    for edge in transitions:
        if isinstance(edge, dict) and str(edge.get("from_node")) == first_id:
            candidate = str(edge.get("to_node") or "")
            if candidate in node_map:
                next_id = candidate
                break

    active_node = node_map.get(next_id, first_node)
    status = "running"
    approval_wf = None

    with transaction.atomic():
        if next_id != first_id:
            trace.append(
                {
                    "node_id": next_id,
                    "node_type": active_node.get("type", "user_task"),
                    "label": active_node.get("label", next_id),
                    "lane": active_node.get("lane_id", ""),
                    "entered_at": now.isoformat(),
                    "exited_at": None,
                    "duration_minutes": 0,
                    "outcome": "pending",
                    "actor": assignee.username if assignee else (actor.username if actor else "system"),
                }
            )
            ntype = active_node.get("type")
            if ntype == "approval_subprocess":
                status = "waiting_approval"
                approval_wf = DocumentApprovalWorkflow.objects.create(
                    tenant=tenant,
                    document=document,
                    version=version,
                    title=f"BPM: {process_definition.name} — {document.title}"[:255],
                    workflow_type="sequential",
                    status="draft",
                    target_turnaround_hours=process_definition.sla_target_hours or 48,
                    initiator=actor or document.owner,
                    department=department or document.department,
                )
            elif ntype == "timer_event":
                status = "waiting_timer"
            elif ntype == "end_event":
                status = "completed"
                trace[-1]["exited_at"] = now.isoformat()
                trace[-1]["outcome"] = "completed"

        due_at = now + timedelta(hours=process_definition.sla_target_hours or 48)
        instance = DocumentProcessInstance.objects.create(
            tenant=tenant,
            process_definition=process_definition,
            document=document,
            version=version,
            triggered_by_rule=triggered_by_rule,
            approval_workflow=approval_wf,
            department=department or process_definition.department or document.department,
            initiated_by=actor,
            current_assignee=assignee,
            status=status,
            current_node_id=str(active_node.get("id") or next_id),
            current_node_label=str(active_node.get("label") or next_id)[:160],
            started_at=now,
            due_at=due_at,
            completed_at=now if status == "completed" else None,
            cycle_time_minutes=0 if status == "completed" else None,
            variant_signature=_build_variant_signature(trace),
            step_trace_json=trace,
            context_variables_json=context_variables or {},
        )
        DocumentProcessDefinition.objects.filter(pk=process_definition.pk).update(
            instance_count=F("instance_count") + 1
        )
        log_document_event(
            tenant=tenant,
            action_type="created",
            document=document,
            version=version,
            actor=actor,
            request=request,
            details={"bpm_event": "process.started", "instance": instance.number, "process": process_definition.number},
        )
        webhooks = DocumentWebhookTrigger.objects.filter(
            tenant=tenant,
            is_active=True,
            trigger_event="process.started",
        )
        for wh in webhooks:
            if wh.process_definition_id and wh.process_definition_id != process_definition.id:
                continue
            dispatch_simulated_webhook(
                wh,
                "process.started",
                {"instance": instance.number, "document": document.number, "process": process_definition.number},
                document=document,
                actor=actor,
                request=request,
            )
    return instance


def advance_process_instance(instance, outcome="approved", actor=None, notes="", request=None):
    """Advance an active DocumentProcessInstance along its BPMN blueprint or record rework."""
    from apps.documents.models.WorkflowAutomation.DocumentWebhookTriggers import DocumentWebhookTrigger
    from apps.documents.services.audit import log_document_event

    if instance.status in ("completed", "cancelled"):
        return instance

    now = timezone.now()
    nodes = instance.process_definition.nodes_json or []
    transitions = instance.process_definition.transitions_json or []
    node_map = {str(n.get("id")): n for n in nodes if isinstance(n, dict) and n.get("id")}
    trace = list(instance.step_trace_json or [])

    # Close out active trace entry
    if trace and trace[-1].get("exited_at") is None:
        entered_raw = trace[-1].get("entered_at")
        dur_mins = 1
        if entered_raw:
            try:
                from django.utils.dateparse import parse_datetime

                entered_dt = parse_datetime(entered_raw)
                if entered_dt:
                    dur_mins = max(1, int((now - entered_dt).total_seconds() // 60))
            except Exception:
                dur_mins = 1
        trace[-1]["exited_at"] = now.isoformat()
        trace[-1]["duration_minutes"] = dur_mins
        trace[-1]["outcome"] = outcome
        if notes:
            trace[-1]["notes"] = notes[:200]

    with transaction.atomic():
        if outcome == "escalated":
            instance.is_sla_breached = True
            instance.status = "sla_breached"
            instance.step_trace_json = trace
            instance.variant_signature = _build_variant_signature(trace)
            instance.save(update_fields=["is_sla_breached", "status", "step_trace_json", "variant_signature", "updated_at"])
            return instance

        if outcome == "rejected":
            instance.rework_count = (instance.rework_count or 0) + 1
            instance.is_conformant = False
            instance.status = "running"
            trace.append(
                {
                    "node_id": instance.current_node_id or "rework",
                    "node_type": "user_task",
                    "label": f"Rework: {instance.current_node_label or 'Task'}"[:160],
                    "lane": "",
                    "entered_at": now.isoformat(),
                    "exited_at": None,
                    "duration_minutes": 0,
                    "outcome": "rework",
                    "actor": actor.username if actor else "system",
                }
            )
            instance.step_trace_json = trace
            instance.variant_signature = _build_variant_signature(trace)
            instance.save(update_fields=["rework_count", "is_conformant", "status", "step_trace_json", "variant_signature", "updated_at"])
            return instance

        if outcome == "completed":
            next_node = None
            for n in nodes:
                if isinstance(n, dict) and n.get("type") == "end_event":
                    next_node = n
                    break
        else:
            outgoing = [
                e for e in transitions if isinstance(e, dict) and str(e.get("from_node")) == str(instance.current_node_id)
            ]
            chosen = next((e for e in outgoing if e.get("is_default")), outgoing[0] if outgoing else None)
            next_id = str(chosen.get("to_node")) if chosen else ""
            next_node = node_map.get(next_id)
            if not next_node and nodes:
                # Fallback to sequential order in nodes_json
                ids = [str(n.get("id")) for n in nodes if isinstance(n, dict) and n.get("id")]
                if instance.current_node_id in ids:
                    idx = ids.index(instance.current_node_id)
                    if idx + 1 < len(ids):
                        next_node = node_map.get(ids[idx + 1])

        if not next_node or next_node.get("type") == "end_event":
            end_id = str(next_node.get("id")) if next_node else "end"
            end_label = str(next_node.get("label") or "Completed") if next_node else "Completed"
            trace.append(
                {
                    "node_id": end_id,
                    "node_type": "end_event",
                    "label": end_label,
                    "lane": next_node.get("lane_id", "") if next_node else "",
                    "entered_at": now.isoformat(),
                    "exited_at": now.isoformat(),
                    "duration_minutes": 0,
                    "outcome": "completed",
                    "actor": actor.username if actor else "system",
                }
            )
            instance.status = "completed"
            instance.current_node_id = end_id
            instance.current_node_label = end_label[:160]
            instance.completed_at = now
            if instance.started_at:
                instance.cycle_time_minutes = max(1, int((now - instance.started_at).total_seconds() // 60))
            if instance.due_at and now > instance.due_at:
                instance.is_sla_breached = True
            instance.step_trace_json = trace
            instance.variant_signature = _build_variant_signature(trace)
            instance.save()

            log_document_event(
                tenant=instance.tenant,
                action_type="workflow_approved",
                document=instance.document,
                version=instance.version,
                actor=actor,
                request=request,
                details={"bpm_event": "process.completed", "instance": instance.number},
            )
            for wh in DocumentWebhookTrigger.objects.filter(
                tenant=instance.tenant, is_active=True, trigger_event="process.completed"
            ):
                if wh.process_definition_id and wh.process_definition_id != instance.process_definition_id:
                    continue
                dispatch_simulated_webhook(
                    wh,
                    "process.completed",
                    {"instance": instance.number, "document": instance.document.number, "cycle_time_minutes": instance.cycle_time_minutes},
                    document=instance.document,
                    actor=actor,
                    request=request,
                )
        else:
            nid = str(next_node.get("id"))
            nlabel = str(next_node.get("label") or nid)[:160]
            ntype = next_node.get("type", "user_task")
            trace.append(
                {
                    "node_id": nid,
                    "node_type": ntype,
                    "label": nlabel,
                    "lane": next_node.get("lane_id", ""),
                    "entered_at": now.isoformat(),
                    "exited_at": None,
                    "duration_minutes": 0,
                    "outcome": "pending",
                    "actor": actor.username if actor else "system",
                }
            )
            instance.current_node_id = nid
            instance.current_node_label = nlabel
            instance.status = "waiting_approval" if ntype == "approval_subprocess" else (
                "waiting_timer" if ntype == "timer_event" else "running"
            )
            if instance.due_at and now > instance.due_at:
                instance.is_sla_breached = True
            instance.step_trace_json = trace
            instance.variant_signature = _build_variant_signature(trace)
            instance.save()
            log_document_event(
                tenant=instance.tenant,
                action_type="edited",
                document=instance.document,
                version=instance.version,
                actor=actor,
                request=request,
                details={"bpm_event": "process.advanced", "instance": instance.number, "node": nid},
            )
    return instance


def dispatch_simulated_webhook(trigger, event_name, payload_data, document=None, actor=None, request=None):
    """Build signed CloudEvents/JSON envelope and record honest local simulated delivery (L55)."""
    from apps.documents.services.audit import log_document_event

    now = timezone.now()
    base_payload = dict(trigger.payload_template_json or {})
    base_payload.update(payload_data or {})

    if trigger.payload_format == "cloudevents_json":
        envelope = {
            "specversion": "1.0",
            "type": f"com.naverp.documents.{event_name}",
            "source": f"/documents/bpm/webhooks/{trigger.number}",
            "id": f"{trigger.number}-{int(now.timestamp())}",
            "time": now.isoformat(),
            "datacontenttype": "application/json",
            "data": base_payload,
        }
    else:
        envelope = {
            "event": event_name,
            "trigger": trigger.number,
            "timestamp": now.isoformat(),
            "payload": base_payload,
        }

    body_bytes = json.dumps(envelope, sort_keys=True, separators=(",", ":")).encode("utf-8")
    signature = trigger.compute_signature(body_bytes)
    entry = trigger.record_simulated_delivery(event_name, envelope, signature)

    if document is not None:
        log_document_event(
            tenant=trigger.tenant,
            action_type="edited",
            document=document,
            actor=actor,
            request=request,
            details={"bpm_event": "webhook.simulated", "webhook": trigger.number, "event": event_name},
        )
    return entry


def compute_process_analytics(tenant, process_def_id=None, department_id=None, date_from=None, date_to=None):
    """Compute cycle times, SLA breach rates, node bottlenecks, and process mining variants."""
    from apps.documents.models.WorkflowAutomation.DocumentProcessInstances import DocumentProcessInstance
    from apps.documents.models.WorkflowAutomation.DocumentRoutingRules import DocumentRoutingRule

    qs = DocumentProcessInstance.objects.filter(tenant=tenant).select_related(
        "process_definition", "department", "document"
    )
    if process_def_id and str(process_def_id).isdigit():
        qs = qs.filter(process_definition_id=int(process_def_id))
    if department_id and str(department_id).isdigit():
        qs = qs.filter(department_id=int(department_id))
    if date_from:
        qs = qs.filter(started_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(started_at__date__lte=date_to)

    instances = list(qs)
    total = len(instances)
    completed = [i for i in instances if i.status == "completed"]
    active_wip = [i for i in instances if i.status in ("queued", "running", "waiting_approval", "waiting_timer")]
    breached = [i for i in instances if i.is_sla_breached or i.status == "sla_breached"]
    rework_instances = [i for i in instances if (i.rework_count or 0) > 0]
    conformant = [i for i in instances if i.is_conformant]

    cycles = sorted([i.cycle_time_minutes for i in completed if i.cycle_time_minutes is not None])
    avg_cycle = round(sum(cycles) / len(cycles), 1) if cycles else 0.0
    if cycles:
        mid = len(cycles) // 2
        median_cycle = float(cycles[mid]) if len(cycles) % 2 == 1 else round((cycles[mid - 1] + cycles[mid]) / 2, 1)
        p95_idx = min(len(cycles) - 1, math.ceil(len(cycles) * 0.95) - 1)
        p95_cycle = float(cycles[p95_idx])
    else:
        median_cycle = 0.0
        p95_cycle = 0.0

    # Node & Lane bottlenecks
    node_stats = defaultdict(lambda: {"label": "", "lane": "", "executions": 0, "total_minutes": 0, "max_minutes": 0, "active_waiting": 0})
    variant_stats = defaultdict(lambda: {"count": 0, "cycles": [], "rework": 0, "conformant": 0})

    for inst in instances:
        sig = inst.variant_signature or inst.current_node_id or "start"
        v = variant_stats[sig]
        v["count"] += 1
        if inst.cycle_time_minutes is not None:
            v["cycles"].append(inst.cycle_time_minutes)
        if inst.rework_count:
            v["rework"] += 1
        if inst.is_conformant:
            v["conformant"] += 1

        for step in inst.step_trace_json or []:
            if not isinstance(step, dict):
                continue
            nid = str(step.get("node_id") or "").strip()
            if not nid:
                continue
            st = node_stats[nid]
            st["label"] = step.get("label") or nid
            st["lane"] = step.get("lane") or "Unassigned"
            st["executions"] += 1
            dur = int(step.get("duration_minutes") or 0)
            st["total_minutes"] += dur
            if dur > st["max_minutes"]:
                st["max_minutes"] = dur
            if step.get("exited_at") is None:
                st["active_waiting"] += 1

    bottlenecks = []
    for nid, st in node_stats.items():
        avg_m = round(st["total_minutes"] / st["executions"], 1) if st["executions"] else 0.0
        bottlenecks.append(
            {
                "node_id": nid,
                "label": st["label"],
                "lane": st["lane"],
                "executions": st["executions"],
                "avg_minutes": avg_m,
                "max_minutes": st["max_minutes"],
                "active_waiting": st["active_waiting"],
            }
        )
    bottlenecks.sort(key=lambda r: (r["avg_minutes"], r["active_waiting"], r["executions"]), reverse=True)

    variants = []
    for sig, v in variant_stats.items():
        v_avg = round(sum(v["cycles"]) / len(v["cycles"]), 1) if v["cycles"] else 0.0
        variants.append(
            {
                "signature": sig,
                "count": v["count"],
                "pct": round((v["count"] / total) * 100, 1) if total else 0.0,
                "avg_cycle_minutes": v_avg,
                "rework_count": v["rework"],
                "conformance_pct": round((v["conformant"] / v["count"]) * 100, 1) if v["count"] else 100.0,
            }
        )
    variants.sort(key=lambda r: r["count"], reverse=True)

    rules_qs = DocumentRoutingRule.objects.filter(tenant=tenant).order_by("-match_count", "priority")[:10]

    return {
        "total_instances": total,
        "completed_count": len(completed),
        "active_wip": len(active_wip),
        "sla_breached_count": len(breached),
        "sla_breach_rate": round((len(breached) / total) * 100, 1) if total else 0.0,
        "avg_cycle_minutes": avg_cycle,
        "median_cycle_minutes": median_cycle,
        "p95_cycle_minutes": p95_cycle,
        "rework_rate": round((len(rework_instances) / total) * 100, 1) if total else 0.0,
        "conformance_rate": round((len(conformant) / total) * 100, 1) if total else 100.0,
        "bottlenecks": bottlenecks[:15],
        "variants": variants[:12],
        "top_rules": list(rules_qs),
        "recent_instances": instances[:10],
    }
