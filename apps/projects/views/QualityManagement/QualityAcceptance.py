"""Projects 7.6 — the Deliverable Acceptance & Sign-off board (computed on read; no model).

Bullet **5 Deliverable Acceptance & Sign-off** as one GET-only page over the WBS deliverable
tree, the plans and the inspections:

* **The acceptance board** — one row per WBS ``deliverable`` node of the selected project: its
  quality plan (and the plan's own status), its latest ``DeliverableInspection``, the recorded
  result and usage decision, the open-defect punch-list count, and the derived acceptance state.
  The acceptance decision itself is taken on the inspection's detail page (``qci_accept`` —
  Ruling 4: the record is the inspection row, the sign-off is the verb, the documentation is a
  ``core.Document``).
* **The acceptance queue** — the ``inspection_type="acceptance"`` inspections still awaiting a
  usage decision, planned-date ordered; each links to its detail page where the decision verbs
  live.

The acceptance state per deliverable reads the LATEST inspection that carries a decision — an
older inspection's reject must not brand a deliverable that has since passed re-inspection.
``pending`` covers everything without an accept/reject-with-deviation decision yet (a ``rework``
decision is pending too: the deliverable is going around again).
"""
from django.db.models import Count

from apps.core.crud import as_db_int
from apps.projects.models import Project, ProjectTask, QualityDefect, QualityPlan, \
    DeliverableInspection
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import login_required, render
from apps.projects.views._helpers import projects as project_choices

#: The live punch-list statuses — a conditional acceptance's open items.
_OPEN_DEFECT_STATUSES = ("open", "in_progress")

#: usage_decision -> (acceptance state, badge class) — the state vocabulary the board renders.
_DECISION_STATES = {
    "accept": ("accepted", "badge-green"),
    "accept_with_deviation": ("conditional", "badge-amber"),
    "reject": ("rejected", "badge-red"),
    "rework": ("pending", "badge-slate"),
    "pending": ("pending", "badge-slate"),
}


def _acceptance_state(usage_decision):
    return _DECISION_STATES.get(usage_decision, ("pending", "badge-slate"))


@login_required
def quality_acceptance(request):
    tenant = request.tenant
    project = None
    project_id = as_db_int(request.GET.get("project"))
    if project_id is not None:
        project = Project.objects.filter(tenant=tenant, pk=project_id).first()

    inspections_qs = (DeliverableInspection.objects.filter(tenant=tenant)
                      .select_related("project", "wbs_node", "quality_plan", "inspector"))
    if project is not None:
        inspections_qs = inspections_qs.filter(project=project)

    # The board rows — one per deliverable node of the selected project. Without a project the
    # board is empty rather than a cross-project blur; the queue below stays tenant-wide so the
    # page still answers "what is awaiting sign-off?".
    deliverable_rows = []
    if project is not None:
        nodes = (ProjectTask.objects.filter(tenant=tenant, project=project,
                                            node_type="deliverable")
                 .order_by("name", "id"))
        plans_by_node = {}
        for plan_row in QualityPlan.objects.filter(
                tenant=tenant, project=project, wbs_node__isnull=False).order_by(
                "-created_at", "-id"):
            plans_by_node.setdefault(plan_row.wbs_node_id, plan_row)
        open_defects_by_node = dict(
            QualityDefect.objects.filter(tenant=tenant, project=project,
                                         wbs_node__isnull=False,
                                         status__in=_OPEN_DEFECT_STATUSES)
            .values_list("wbs_node_id")
            .annotate(n=Count("id")))
        latest_by_node = {}
        for insp in inspections_qs.filter(wbs_node__isnull=False).order_by(
                "wbs_node_id", "-created_at", "-id"):
            latest_by_node.setdefault(insp.wbs_node_id, insp)
        for node in nodes:
            plan = plans_by_node.get(node.pk)
            latest = latest_by_node.get(node.pk)
            state, badge = _acceptance_state(latest.usage_decision if latest else "pending")
            deliverable_rows.append({
                "wbs_node": node,
                "plan": plan,
                "plan_status": plan.status if plan else None,
                "latest_inspection": latest,
                "result": latest.result if latest else None,
                "usage_decision": latest.usage_decision if latest else None,
                "open_defects": open_defects_by_node.get(node.pk, 0),
                "acceptance_state": state,
                "badge": badge,
            })

    # The queue and the counts — tenant-wide unless a project is selected, so the header answers
    # the same question at both scopes.
    queue_qs = (inspections_qs.filter(inspection_type="acceptance", usage_decision="pending")
                .order_by("planned_date", "id"))
    acceptance_queue = list(queue_qs)
    return render(request, "projects/quality/quality_acceptance.html", {
        "projects": project_choices(tenant),
        "project": project,
        "deliverable_rows": deliverable_rows,
        "acceptance_queue": acceptance_queue,
        "acceptance_queue_count": len(acceptance_queue),
        "accepted_count": inspections_qs.filter(usage_decision="accept").count(),
        "conditional_count": inspections_qs.filter(
            usage_decision="accept_with_deviation").count(),
        "rejected_count": inspections_qs.filter(usage_decision="reject").count(),
        "pending_count": inspections_qs.filter(usage_decision="pending").count(),
    })
