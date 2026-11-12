"""Shared filter, CSV export, and CMDB BFS impact helpers for Module 11.18 ITAM."""

from collections import deque
import csv
from itertools import islice

from django.http import HttpResponse

PAGE_SIZE = 15

CMDB_REL_SELECT_RELATED = (
    "source_hardware",
    "source_software",
    "source_cloud",
    "source_service",
    "source_asset",
    "target_hardware",
    "target_software",
    "target_cloud",
    "target_service",
    "target_asset",
    "owner",
    "verified_by",
)


def is_tenant_admin_user(user):
    """Return True if user holds tenant admin or superuser privileges."""
    return bool(getattr(user, "is_superuser", False) or getattr(user, "is_tenant_admin", False))


def parse_pos_int(raw_value):
    """Parse a bounded ASCII positive 32-bit integer query parameter, returning None when invalid."""
    raw = (str(raw_value) if raw_value is not None else "").strip()
    if not raw or len(raw) > 10 or not raw.isascii() or not raw.isdigit():
        return None
    val = int(raw)
    return val if 0 < val <= 2_147_483_647 else None


def apply_choice_filter(qs, request, param_name, field_name=None, allowed_values=None):
    """Apply an exact GET choice filter cleanly while ignoring unrecognized choice values."""
    val = request.GET.get(param_name, "").strip()
    if not val:
        return qs
    if allowed_values is not None and val not in allowed_values:
        return qs
    return qs.filter(**{field_name or param_name: val})


def apply_fk_filter(qs, request, param_name, field_name=None):
    """Apply an integer ForeignKey filter cleanly while ignoring malformed query values."""
    val = parse_pos_int(request.GET.get(param_name))
    if val is None:
        return qs
    target = field_name or f"{param_name}_id"
    return qs.filter(**{target: val})


def csv_safe(value):
    """Neutralize spreadsheet formula-injection prefixes before writing CSV cells."""
    if value is None:
        return ""
    text = str(value)
    if text.startswith(("\t", "\r", "\n")) or text.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def csv_export_response(*, filename, headers, rows):
    """Stream up to 10,000 rows as a hardened attachment CSV download."""
    safe_name = "".join(c for c in filename if c.isalnum() or c in ("-", "_", ".")) or "export.csv"
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{safe_name}"'
    response["X-Content-Type-Options"] = "nosniff"
    writer = csv.writer(response)
    writer.writerow([csv_safe(h) for h in headers])
    for row in islice(rows, 10000):
        writer.writerow([csv_safe(c) for c in row])
    return response


def build_ci_label_map(tenant):
    """Build deterministic ``(ci_type, pk) -> label`` and option list in 5 bounded queries."""
    from apps.assets.models.ItAssetManagement.CloudAssetSubscriptions import CloudAssetSubscription
    from apps.assets.models.ItAssetManagement.ItHardwareAssets import ItHardwareAsset
    from apps.assets.models.ItAssetManagement.SoftwareLicenses import SoftwareLicense
    from apps.core.models.Monitoring import ServiceComponent
    from apps.scm.models.AssetManagement.Assets import Asset

    label_map = {}
    options = []

    for hw in ItHardwareAsset.objects.filter(tenant=tenant).order_by("hostname", "number"):
        key = ("it_hardware", hw.pk)
        label = f"[HW] {hw.number} — {hw.hostname}"
        label_map[key] = label
        options.append({"token": f"it_hardware:{hw.pk}", "label": label, "ci_type": "it_hardware", "pk": hw.pk})

    for sw in SoftwareLicense.objects.filter(tenant=tenant).order_by("software_name", "number"):
        key = ("software_license", sw.pk)
        label = f"[SW] {sw.number} — {sw.software_name}"
        label_map[key] = label
        options.append({"token": f"software_license:{sw.pk}", "label": label, "ci_type": "software_license", "pk": sw.pk})

    for cl in CloudAssetSubscription.objects.filter(tenant=tenant).order_by("name", "number"):
        key = ("cloud_asset", cl.pk)
        label = f"[Cloud] {cl.number} — {cl.name}"
        label_map[key] = label
        options.append({"token": f"cloud_asset:{cl.pk}", "label": label, "ci_type": "cloud_asset", "pk": cl.pk})

    for svc in ServiceComponent.objects.filter(tenant=tenant).order_by("display_order", "name"):
        key = ("service_component", svc.pk)
        label = f"[Service] {svc.name}"
        label_map[key] = label
        options.append({"token": f"service_component:{svc.pk}", "label": label, "ci_type": "service_component", "pk": svc.pk})

    for ast in Asset.objects.filter(tenant=tenant).order_by("code", "name"):
        key = ("operational_asset", ast.pk)
        label = f"[SCM Asset] {ast.code} — {ast.name}"
        label_map[key] = label
        options.append({"token": f"operational_asset:{ast.pk}", "label": label, "ci_type": "operational_asset", "pk": ast.pk})

    return label_map, options


def parse_ci_token(token):
    """Parse ``<ci_type>:<int_pk>`` into ``(ci_type, pk)`` or return ``(None, None)``."""
    raw = (token or "").strip()
    if ":" not in raw:
        return None, None
    ci_type, raw_id = raw.split(":", 1)
    pk = parse_pos_int(raw_id)
    if not ci_type or pk is None:
        return None, None
    return ci_type.strip(), pk


def compute_cmdb_impact(edges, start_key, label_map):
    """Compute cycle-safe BFS upstream dependencies and downstream blast radius from ``start_key``.

    Edge direction is ``source -> relationship_type -> target`` (source depends on / runs on target).
    Therefore:
    - Upstream dependencies (what ``start_key`` relies upon): follow ``source -> target`` edges.
    - Downstream blast radius (what breaks if ``start_key`` fails): follow ``target -> source`` edges.
    """
    outbound = {}
    inbound = {}
    for edge in edges:
        s_key = edge.source_ci_key
        t_key = edge.target_ci_key
        if not s_key or not t_key:
            continue
        outbound.setdefault(s_key, []).append(edge)
        inbound.setdefault(t_key, []).append(edge)

    def _bfs(adj, get_next_key, get_label):
        visited = {start_key}
        queue = deque([(start_key, 0)])
        results = []
        while queue:
            cur_key, dist = queue.popleft()
            if dist >= 8:
                continue
            for edge in adj.get(cur_key, ()):
                nxt_key = get_next_key(edge)
                if not nxt_key or nxt_key in visited:
                    continue
                visited.add(nxt_key)
                results.append(
                    {
                        "hop": dist + 1,
                        "ci_type": nxt_key[0],
                        "ci_pk": nxt_key[1],
                        "ci_token": f"{nxt_key[0]}:{nxt_key[1]}",
                        "ci_label": label_map.get(nxt_key) or get_label(edge),
                        "edge": edge,
                        "relationship_label": edge.get_relationship_type_display(),
                        "criticality_label": edge.get_criticality_display(),
                        "criticality_badge_class": edge.criticality_badge_class,
                        "impact_label": edge.get_impact_severity_display(),
                        "is_spof": edge.is_single_point_of_failure,
                    }
                )
                queue.append((nxt_key, dist + 1))
        return results

    upstream = _bfs(outbound, lambda e: e.target_ci_key, lambda e: e.target_label)
    downstream = _bfs(inbound, lambda e: e.source_ci_key, lambda e: e.source_label)
    return upstream, downstream
