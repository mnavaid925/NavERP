"""Procurement 6.2 Requisition Management — Requisition tracking views.

**Requisition Tracking** + **Duplicate Requisition Check** bullets. The requisitions themselves
stay 4.1's ``scm.PurchaseRequisition`` (L36): this module adds no second register — it adds the
management lens OVER the spine: a tracking register with pipeline/duplicate visibility, and a
detail page that reads the immutable audit trail as the real-time timeline from draft through
approval to PO conversion. Creation itself maps to scm's full form (the sidebar bullet links
there); everything AFTER creation lives here.
"""
from django.contrib.contenttypes.models import ContentType

from apps.core.crud import apply_search, as_db_int, paginate
from apps.core.models import AuditLog
from apps.procurement.views._common import *  # noqa: F401,F403
from apps.procurement.views._helpers import (
    DUPLICATE_ACTIVE_STATUSES,
    DUPLICATE_WINDOW_DAYS,
    duplicate_pk_set,
    find_duplicate_requisitions,
)
from apps.scm.models import PurchaseRequisition

#: The linear happy path of the procure-to-pay opening — rendered as a stage strip on the detail
#: page. Terminal statuses (rejected / cancelled) leave the strip and surface as status badges.
_PIPELINE = [
    ("draft", "Draft"),
    ("pending_approval", "Pending approval"),
    ("approved", "Approved"),
    ("converted", "PO raised"),
]


def _pipeline_stages(requisition):
    """The four-stage strip with each stage marked done/current/todo for the template."""
    keys = [key for key, _label in _PIPELINE]
    try:
        current = keys.index(requisition.status)
    except ValueError:
        current = -1
    return [{"key": key,
             "label": label,
             "state": "done" if i < current else ("current" if i == current else "todo")}
            for i, (key, label) in enumerate(_PIPELINE)]


@login_required
def req_list(request):
    """The requisition register: search + status/department filters BEFORE pagination, then a
    duplicate-flag badge computed for exactly the rows on THIS page (two queries total, not one
    per row). ``?dupes=1`` narrows to live requisitions inside the duplicate window — the
    sidebar's Duplicate Requisition Check entry deep-links to precisely that slice."""
    qs = (PurchaseRequisition.objects.filter(tenant=request.tenant)
          .select_related("requester", "org_unit"))
    dupes_only = request.GET.get("dupes") == "1"
    if dupes_only:
        from datetime import timedelta

        from django.utils import timezone

        qs = qs.filter(status__in=DUPLICATE_ACTIVE_STATUSES,
                       created_at__gte=timezone.now() - timedelta(days=DUPLICATE_WINDOW_DAYS))

    q = request.GET.get("q", "").strip()
    qs = apply_search(qs, q, ["number", "title", "justification"])
    status_val = request.GET.get("status", "").strip()
    if status_val:
        qs = qs.filter(status=status_val)
    org_number = as_db_int(request.GET.get("org_unit", ""))
    if org_number is not None:
        qs = qs.filter(org_unit_id=org_number)

    page_obj = paginate(request, qs.order_by("-created_at", "-id"), per_page=15)
    ctx = {
        "object_list": page_obj.object_list,
        "page_obj": page_obj,
        "q": q,
        "status_choices": PurchaseRequisition.STATUS_CHOICES,
        "org_units": _org_units(request.tenant),
        "dupe_pks": duplicate_pk_set(request.tenant.pk, page_obj.object_list),
        "dupes_only": dupes_only,
        "window_days": DUPLICATE_WINDOW_DAYS,
    }
    return render(request, "procurement/requisitionmanagement/requisitions/list.html", ctx)


def _org_units(tenant):
    from apps.core.models import OrgUnit

    if tenant is None:
        return OrgUnit.objects.none()
    return OrgUnit.objects.filter(tenant=tenant).order_by("name")


@login_required
def req_detail(request, pk):
    """Real-time tracking for ONE requisition: pipeline strip, lines, linked RFQs/POs, open
    amendments, potential duplicates (with reasons), and the audit trail as the timeline."""
    obj = get_object_or_404(
        PurchaseRequisition.objects.select_related(
            "requester", "org_unit", "budget", "currency", "approved_by"),
        pk=pk, tenant=request.tenant,
    )
    lines = list(obj.lines.select_related("gl_account"))
    amendments = list(
        obj.amendments.select_related("requested_by", "decided_by").order_by("-created_at", "-id"))
    duplicates = find_duplicate_requisitions(obj)

    # The timeline IS the append-only audit trail — who did what to this requisition and when.
    # Fabricating stage timestamps would be a second, editable source of truth; the trail cannot
    # drift because nothing can edit it.
    history = list(
        AuditLog.objects
        .filter(tenant=request.tenant,
                content_type=ContentType.objects.get_for_model(PurchaseRequisition),
                object_id=obj.pk)
        .select_related("user")
        .order_by("-at", "-id")[:20])

    return render(request, "procurement/requisitionmanagement/requisitions/detail.html", {
        "obj": obj,
        "lines": lines,
        "pipeline": _pipeline_stages(obj),
        "amendments": amendments,
        "open_amendment": any(a.is_pending for a in amendments),
        "duplicates": duplicates,
        "window_days": DUPLICATE_WINDOW_DAYS,
        "rfqs": obj.rfqs.only("id", "number", "title", "status"),
        "purchase_orders": obj.purchase_orders.select_related("vendor").only(
            "id", "number", "status", "total", "vendor__name"),
        "history": history,
    })
