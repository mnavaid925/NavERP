"""Projects 7.4 — CostControlAccount views: the EVM register and its detail panel.

No verbs — the register is read + CRUD; money governance lives on BudgetRevision and cost
evidence on ProjectExpense. The detail page reads the EVM metrics straight off the model's
properties (no computed context keys), and the "budget_lines" / "expenses" tables ride the
related names, so a cross-tenant id can never leak: every fetch is tenant-scoped first.
"""
from django.db import transaction
from django.db.models import ProtectedError

from apps.projects.forms import CostControlAccountForm
from apps.projects.models import CostControlAccount
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import get_object_or_404, login_required, redirect, render, require_POST
from apps.projects.views._helpers import projects


@login_required
def cca_list(request):
    qs = (CostControlAccount.objects.filter(tenant=request.tenant)
          .select_related("project"))
    return crud_list(
        request, qs, "projects/cost/costcontrolaccount/list.html",
        search_fields=["number", "name", "code", "note"],
        filters=[("project", "project_id", True),
                 ("status", "status", False)],
        extra_context={
            "status_choices": CostControlAccount.STATUS_CHOICES,
            "projects": projects(request.tenant),
        },
    )


@login_required
def cca_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = CostControlAccountForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Control account {obj.number} created.")
            return redirect("projects:cca_detail", pk=obj.pk)
    else:
        form = CostControlAccountForm(tenant=request.tenant,
                                      initial={"project": request.GET.get("project", "")})
    return render(request, "projects/cost/costcontrolaccount/form.html",
                  {"form": form, "is_edit": False})


@login_required
def cca_detail(request, pk):
    obj = get_object_or_404(
        CostControlAccount.objects.select_related(
            "project", "wbs_node", "gl_account"),
        pk=pk, tenant=request.tenant)
    # The baseline rows this CA measures: lines of the ACTIVE revision mapped to this account —
    # pinned to the exact active revision (an approved-but-never-activated revision, and a
    # superseded one still carrying its historical activated_at, must both stay out).
    active = obj.active_revision
    budget_lines = (obj.budget_lines.filter(budget_revision=active)
                    .select_related("budget_revision", "wbs_node")
                    if active else obj.budget_lines.none())
    expenses = (obj.expenses.filter(status="posted")
                .select_related("project").order_by("-entry_date", "-id")[:25])
    return render(request, "projects/cost/costcontrolaccount/detail.html",
                  {"obj": obj, "budget_lines": budget_lines, "expenses": expenses})


@login_required
def cca_edit(request, pk):
    return crud_edit(
        request, model=CostControlAccount, pk=pk, form_class=CostControlAccountForm,
        template="projects/cost/costcontrolaccount/form.html", success_url="projects:cca_list")


@login_required
@require_POST
def cca_delete(request, pk):
    """Delete a control account — with the house ``except ProtectedError`` guard
    (``party_delete``/``currency_delete``).

    ``ProjectExpense.control_account`` is PROTECT and non-nullable (a CA-less cost row would
    silently drop out of every EVM index), so any CA with cost history is referenced and a bare
    delete is an uncaught ``ProtectedError`` — a 500. Worse: ``crud_delete`` writes its ``delete``
    audit row BEFORE ``obj.delete()``, so each failed attempt also left an orphan audit row for a
    CA that still exists. One ``atomic()`` block around the whole ``crud_delete`` call rolls the
    audit row back with the failed delete — the audit row only ever lands on success.
    """
    obj = get_object_or_404(CostControlAccount.objects.only("pk"), pk=pk, tenant=request.tenant)
    try:
        with transaction.atomic():
            return crud_delete(request, model=CostControlAccount, pk=pk,
                               success_url="projects:cca_list")
    except ProtectedError as exc:
        blockers = sorted({protected._meta.verbose_name for protected in exc.protected_objects})
        messages.error(
            request,
            f"Control account {obj.number} is still referenced by {', '.join(blockers)} and "
            "cannot be deleted — it carries cost history the EVM math reads.")
        return redirect("projects:cca_detail", pk=pk)
