"""Computed CMDB Upstream/Downstream Blast-Radius Impact Analysis views (11.18)."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from apps.assets.models.ItAssetManagement.CmdbRelationships import CmdbRelationship
from apps.assets.views._common import assets_scope
from apps.assets.views.ItAssetManagement._helpers import (
    CMDB_REL_SELECT_RELATED,
    build_ci_label_map,
    compute_cmdb_impact,
    csv_export_response,
    parse_ci_token,
)

_VALID_ENVIRONMENTS = {val for val, _ in CmdbRelationship.ENVIRONMENT_CHOICES}


def _build_impact_context(request):
    """Compute cycle-safe CMDB BFS impact analysis & SPOF summary for ``request.tenant``."""
    label_map, ci_options = build_ci_label_map(request.tenant)

    raw_env = request.GET.get("environment", "").strip()
    selected_environment = raw_env if raw_env in _VALID_ENVIRONMENTS else ""

    edges_qs = assets_scope(
        CmdbRelationship.objects.filter(status="active"),
        request,
    ).select_related(*CMDB_REL_SELECT_RELATED)
    if selected_environment:
        edges_qs = edges_qs.filter(environment=selected_environment)
    edges = list(edges_qs)

    raw_ci_param = request.GET.get("ci", "").strip()
    selected_key = None
    selected_ci_token = ""
    selected_ci_label = ""

    if raw_ci_param:
        parsed_key = parse_ci_token(raw_ci_param)
        if parsed_key in label_map:
            selected_key = parsed_key
            selected_ci_token = f"{parsed_key[0]}:{parsed_key[1]}"
            selected_ci_label = label_map[parsed_key]
    elif ci_options:
        # Default to a CI that participates in an active edge if available, else first option.
        first_opt = ci_options[0]
        for edge in edges:
            key = edge.target_ci_key or edge.source_ci_key
            if key in label_map:
                selected_key = key
                selected_ci_token = f"{key[0]}:{key[1]}"
                selected_ci_label = label_map[key]
                break
        if selected_key is None:
            selected_key = (first_opt["ci_type"], first_opt["pk"])
            selected_ci_token = first_opt["token"]
            selected_ci_label = first_opt["label"]

    if selected_key is not None:
        upstream_nodes, downstream_nodes = compute_cmdb_impact(edges, selected_key, label_map)
    else:
        upstream_nodes, downstream_nodes = [], []

    spof_edges = [edge for edge in edges if edge.is_single_point_of_failure]

    return {
        "ci_options": ci_options,
        "selected_ci_token": selected_ci_token,
        "selected_ci_label": selected_ci_label,
        "selected_environment": selected_environment,
        "environment_choices": CmdbRelationship.ENVIRONMENT_CHOICES,
        "upstream_nodes": upstream_nodes,
        "downstream_nodes": downstream_nodes,
        "spof_edges": spof_edges,
        "total_active_edges": len(edges),
        "total_spof_edges": len(spof_edges),
    }


@login_required
def cmdb_impact_analysis(request):
    """Display interactive CMDB upstream dependency & downstream blast-radius explorer."""
    context = _build_impact_context(request)
    return render(
        request,
        "assets/itassetmanagement/cmdb_impact_analysis.html",
        context,
    )


@login_required
def cmdb_impact_analysis_export_csv(request):
    """Export traversed CMDB upstream and downstream impact nodes as a formula-safe CSV."""
    ctx = _build_impact_context(request)
    headers = [
        "Selected CI",
        "Direction",
        "Hop Distance",
        "Impacted / Dependency CI",
        "Relationship",
        "Criticality",
        "Impact Severity",
        "SPOF",
        "Edge #",
    ]
    rows = []
    for direction_label, nodes in (
        ("Upstream Dependency", ctx["upstream_nodes"]),
        ("Downstream Blast Radius", ctx["downstream_nodes"]),
    ):
        for node in nodes:
            rows.append(
                [
                    ctx["selected_ci_label"],
                    direction_label,
                    node["hop"],
                    node["ci_label"],
                    node["relationship_label"],
                    node["criticality_label"],
                    node["impact_label"],
                    "Yes" if node["is_spof"] else "No",
                    node["edge"].number,
                ]
            )
    return csv_export_response(
        filename="cmdb_impact_analysis.csv",
        headers=headers,
        rows=rows,
    )
