"""Projects 7.4 — BudgetRevision views: the budget register and its governance verbs.

Five verbs, all POST-only (GET → 405), and every one of them refuses a disallowed transition with
a message rather than a 500 or a silent no-op:

``submit`` ⇒ draft → pending_approval · ``approve`` (tenant admin) ⇒ approved — deliberately NOT
active · ``reject`` (tenant admin, reason required) ⇒ rejected · ``activate`` (tenant admin) ⇒
the re-baseline: supersedes every other approved revision of the project and stamps
``activated_at``, making THIS row the cost baseline.

Approved and superseded rows are frozen cost history: their edit and delete views refuse them,
because a baseline that could be quietly rewritten would not be a baseline (the ``ScheduleBaseline``
frozen-row guard). The correction path is a NEW revision — that is what bullet 5's audit trail is
for.

Audit actions stay ≤ 10 characters (``core.AuditLog.action`` is ``varchar(10)``); the verb itself
goes in ``changes``. Every verb captures ``previous = obj.status`` BEFORE mutating (the ``prq_*``
idiom — a hard-coded ``{"from": ...}`` asserts the gate was respected in exactly the cases where
it was not).
"""
from django.db import transaction
from django.db.models import Sum

from apps.projects.forms import BudgetRevisionDecisionForm, BudgetRevisionForm
from apps.projects.models import BudgetRevision
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import get_object_or_404, login_required, redirect, render, require_POST
from apps.projects.views._helpers import projects

_LOCKED_MSG = ("An approved or superseded revision is frozen cost history and cannot be edited "
               "or deleted — submit a new revision to change the budget.")


@login_required
def bvr_list(request):
    qs = (BudgetRevision.objects.filter(tenant=request.tenant)
          .select_related("project"))
    return crud_list(
        request, qs, "projects/cost/budgetrevision/list.html",
        search_fields=["number", "title", "reason"],
        filters=[("project", "project_id", True),
                 ("status", "status", False)],
        extra_context={
            "status_choices": BudgetRevision.STATUS_CHOICES,
            "projects": projects(request.tenant),
        },
    )


@login_required
def bvr_create(request):
    """Hand-wrapped so ``created_by`` is stamped and the redirect lands on the new row's detail —
    the ``crud_create`` helper does neither (the ``prq_create`` idiom)."""
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = BudgetRevisionForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.created_by = request.user
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Budget revision {obj.number} created.")
            return redirect("projects:bvr_detail", pk=obj.pk)
    else:
        form = BudgetRevisionForm(tenant=request.tenant,
                                  initial={"project": request.GET.get("project", "")})
    return render(request, "projects/cost/budgetrevision/form.html",
                  {"form": form, "is_edit": False})


@login_required
def bvr_detail(request, pk):
    obj = get_object_or_404(
        BudgetRevision.objects.select_related(
            "project", "currency", "requested_by", "decided_by", "created_by"),
        pk=pk, tenant=request.tenant)
    lines = obj.lines.select_related("wbs_node", "control_account", "gl_account")
    # `.order_by()` clears Meta.ordering before the GROUP BY — an aggregate carrying
    # "ORDER BY created_at DESC, id DESC" is Error-1055 on stock MySQL (ONLY_FULL_GROUP_BY);
    # the scm Reports idiom.
    totals = {line["category"]: line["total"] for line in lines.order_by()
              .values("category").annotate(total=Sum("amount"))}
    return render(request, "projects/cost/budgetrevision/detail.html",
                  {"obj": obj, "lines": lines, "category_totals": totals})


@login_required
def bvr_edit(request, pk):
    obj = get_object_or_404(BudgetRevision, pk=pk, tenant=request.tenant)
    if obj.is_locked:
        messages.error(request, _LOCKED_MSG)
        return redirect("projects:bvr_detail", pk=obj.pk)
    return crud_edit(
        request, model=BudgetRevision, pk=pk, form_class=BudgetRevisionForm,
        template="projects/cost/budgetrevision/form.html", success_url="projects:bvr_list")


@login_required
@require_POST
def bvr_delete(request, pk):
    obj = get_object_or_404(BudgetRevision, pk=pk, tenant=request.tenant)
    if obj.is_locked:
        messages.error(request, _LOCKED_MSG)
        return redirect("projects:bvr_detail", pk=obj.pk)
    return crud_delete(request, model=BudgetRevision, pk=pk, success_url="projects:bvr_list")


# -- governance verbs ----------------------------------------------------------------------------
#
# Approve/reject/activate move governance state, so all three are TENANT-ADMIN gated (7.1
# precedent: rendering the buttons to an ordinary member would just serve a hard 403). Submit
# stays login-only: sending your own plan up for approval is the requester's act.

@login_required
@require_POST
def bvr_submit(request, pk):
    obj = get_object_or_404(BudgetRevision, pk=pk, tenant=request.tenant)
    if obj.status != "draft":
        messages.info(request, f"That revision is already {obj.get_status_display().lower()}.")
        return redirect("projects:bvr_detail", pk=obj.pk)
    previous = obj.status
    obj.status = "pending_approval"
    obj.requested_at = timezone.now()
    obj.save(update_fields=["status", "requested_at", "updated_at"])
    write_audit_log(request.user, obj, "submit",
                    changes={"verb": "submit", "from": previous, "to": obj.status})
    messages.success(request, f"Submitted “{obj.title}” for approval.")
    return redirect("projects:bvr_detail", pk=obj.pk)


@login_required
@tenant_admin_required
@require_POST
def bvr_approve(request, pk):
    """Record the approval. This does NOT activate the baseline — activation is the separate,
    equally-governed step, so two approved revisions can coexist while the re-baseline decision
    is pending."""
    obj = get_object_or_404(BudgetRevision, pk=pk, tenant=request.tenant)
    if obj.status != "pending_approval":
        messages.error(
            request,
            f"Only a revision pending approval can be approved — this one is "
            f"{obj.get_status_display().lower()}.")
        return redirect("projects:bvr_detail", pk=obj.pk)
    previous = obj.status
    obj.status = "approved"
    obj.decided_by = request.user
    obj.decided_at = timezone.now()
    obj.save(update_fields=["status", "decided_by", "decided_at", "updated_at"])
    write_audit_log(request.user, obj, "approve",
                    changes={"verb": "approve", "from": previous, "to": obj.status})
    messages.success(request,
                     f"Approved “{obj.title}” — activate it to make it the cost baseline.")
    return redirect("projects:bvr_detail", pk=obj.pk)


@login_required
@tenant_admin_required
@require_POST
def bvr_reject(request, pk):
    obj = get_object_or_404(BudgetRevision, pk=pk, tenant=request.tenant)
    # The status precondition fires BEFORE form validation — a stale POST against a non-pending
    # revision must get the status refusal, not "A rejection needs a stated reason." (messages
    # identical either way; only the order is pinned).
    if obj.status != "pending_approval":
        messages.error(
            request,
            f"Only a revision pending approval can be rejected — this one is "
            f"{obj.get_status_display().lower()}.")
        return redirect("projects:bvr_detail", pk=obj.pk)
    form = BudgetRevisionDecisionForm(request.POST)
    if not form.is_valid():
        messages.error(request, "A rejection needs a stated reason.")
        return redirect("projects:bvr_detail", pk=obj.pk)
    previous = obj.status
    obj.status = "rejected"
    obj.decision_notes = form.cleaned_data["decision_notes"]
    obj.decided_by = request.user
    obj.decided_at = timezone.now()
    obj.save(update_fields=["status", "decision_notes", "decided_by", "decided_at", "updated_at"])
    write_audit_log(request.user, obj, "reject",
                    changes={"verb": "reject", "from": previous, "to": obj.status})
    messages.success(request, f"Rejected “{obj.title}”.")
    return redirect("projects:bvr_detail", pk=obj.pk)


@login_required
@tenant_admin_required
@require_POST
def bvr_activate(request, pk):
    """The re-baseline. ``approve`` deliberately does not activate, so two ``approved`` revisions
    can coexist; THIS verb picks one. Supersedes EVERY other approved revision of the project
    (not just "the previous one" — approve-does-not-activate means there may be several), keeping
    their ``activated_at`` as history, then stamps this row. One atomic block: a half-applied
    re-baseline (two active baselines, or none) is exactly the corruption EVM math cannot survive.
    """
    obj = get_object_or_404(BudgetRevision, pk=pk, tenant=request.tenant)
    if obj.status != "approved":
        messages.error(
            request,
            f"Only an approved revision can be activated as the baseline — this one is "
            f"{obj.get_status_display().lower()}.")
        return redirect("projects:bvr_detail", pk=obj.pk)
    if obj.activated_at:
        messages.info(request, "That revision is already the active baseline.")
        return redirect("projects:bvr_detail", pk=obj.pk)
    previous = obj.status
    with transaction.atomic():
        for other in (BudgetRevision.objects.select_for_update()
                      .filter(tenant=obj.tenant_id, project=obj.project_id, status="approved")
                      .exclude(pk=obj.pk)):
            other_previous = other.status
            other.status = "superseded"
            other.save(update_fields=["status", "updated_at"])
            write_audit_log(request.user, other, "supersede",
                            changes={"verb": "supersede", "from": other_previous, "to": other.status})
        obj.activated_at = timezone.now()
        obj.save(update_fields=["activated_at", "updated_at"])
        # Activation does NOT change status — the audit records the gate it passed (approved ->
        # approved, the prq idiom with "to" = the post-mutation status). Inside the atomic block:
        # a crash between commit and audit would leave an activation with no audit row.
        write_audit_log(request.user, obj, "activate",
                        changes={"verb": "activate", "from": previous, "to": previous})
    messages.success(request, f"Revision {obj.number} is now the project's cost baseline.")
    return redirect("projects:bvr_detail", pk=obj.pk)
