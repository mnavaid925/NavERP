"""Projects 7.4 — ProjectExpense views: the cost register and its post/void verbs.

Two verbs, both POST-only (GET → 405): ``post`` (login) turns a draft into burning evidence, and
``void`` (tenant admin) stops a posted row counting while keeping it visible — the ONLY
correction path, because posted rows refuse edit and delete (they are what CPI/EAC stand on).

The create view supplies the currency initial: the project's active revision's currency when the
register deep-links in with ``?project=``, else the tenant's first Currency — face-value
bookkeeping (L29: ``Currency`` is global, nothing converts).
"""
from apps.accounting.models import Currency
from apps.core.crud import as_db_int
from apps.projects.forms import ProjectExpenseForm
from apps.projects.models import CostControlAccount, Project, ProjectExpense
from apps.projects.views._common import *  # noqa: F401,F403
from apps.projects.views._common import get_object_or_404, login_required, redirect, render, require_POST
from apps.projects.views._helpers import projects

_EVIDENCE_MSG = ("A posted or voided expense is frozen cost evidence and cannot be edited or "
                 "deleted — void it (admins) and enter a corrected row instead.")


def _initial_currency(request, project_param):
    """The create form's currency initial: the project's active revision's currency when the
    register was deep-linked with ``?project=``, else the first Currency on file (Currency is a
    global table — L29 — so 'first' is the deterministic lowest pk)."""
    project_pk = as_db_int(project_param)
    if project_pk:
        project = Project.objects.filter(pk=project_pk, tenant=request.tenant).first()
        if project:
            active = (project.budget_revisions
                      .filter(status="approved", activated_at__isnull=False)
                      .order_by("-activated_at").first())
            if active and active.currency_id:
                return active.currency_id
    first = Currency.objects.order_by("pk").first()
    return first.pk if first else None


@login_required
def pex_list(request):
    qs = (ProjectExpense.objects.filter(tenant=request.tenant)
          .select_related("project", "control_account"))
    return crud_list(
        request, qs, "projects/cost/projectexpense/list.html",
        search_fields=["number", "description", "source_number"],
        filters=[("project", "project_id", True),
                 ("entry_type", "entry_type", False),
                 ("status", "status", False),
                 ("control_account", "control_account_id", True)],
        extra_context={
            "projects": projects(request.tenant),
            "entry_type_choices": ProjectExpense.ENTRY_TYPE_CHOICES,
            "status_choices": ProjectExpense.STATUS_CHOICES,
            "source_kind_choices": ProjectExpense.SOURCE_KIND_CHOICES,
            "control_accounts": CostControlAccount.objects.filter(tenant=request.tenant),
        },
    )


@login_required
def pex_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = ProjectExpenseForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.created_by = request.user
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Expense {obj.number} created.")
            return redirect("projects:pex_detail", pk=obj.pk)
    else:
        project_param = request.GET.get("project", "")
        initial = {"project": project_param}
        currency_pk = _initial_currency(request, project_param)
        if currency_pk:
            initial["currency"] = currency_pk
        form = ProjectExpenseForm(tenant=request.tenant, initial=initial)
    return render(request, "projects/cost/projectexpense/form.html",
                  {"form": form, "is_edit": False})


@login_required
def pex_detail(request, pk):
    obj = get_object_or_404(
        ProjectExpense.objects.select_related(
            "project", "control_account", "wbs_node", "vendor", "gl_account", "currency",
            "created_by"),
        pk=pk, tenant=request.tenant)
    return render(request, "projects/cost/projectexpense/detail.html", {"obj": obj})


@login_required
def pex_edit(request, pk):
    obj = get_object_or_404(ProjectExpense, pk=pk, tenant=request.tenant)
    if obj.is_locked:
        messages.error(request, _EVIDENCE_MSG)
        return redirect("projects:pex_detail", pk=obj.pk)
    return crud_edit(
        request, model=ProjectExpense, pk=pk, form_class=ProjectExpenseForm,
        template="projects/cost/projectexpense/form.html", success_url="projects:pex_list")


@login_required
@require_POST
def pex_delete(request, pk):
    obj = get_object_or_404(ProjectExpense, pk=pk, tenant=request.tenant)
    if obj.is_locked:
        messages.error(request, _EVIDENCE_MSG)
        return redirect("projects:pex_detail", pk=obj.pk)
    return crud_delete(request, model=ProjectExpense, pk=pk, success_url="projects:pex_list")


# -- evidence verbs ------------------------------------------------------------------------------

@login_required
@require_POST
def pex_post(request, pk):
    """A draft burns nothing; posting makes it count. Idempotent-safe: already-posted says so
    and writes nothing."""
    obj = get_object_or_404(ProjectExpense, pk=pk, tenant=request.tenant)
    if obj.status == "posted":
        messages.info(request, "That expense is already posted.")
        return redirect("projects:pex_detail", pk=obj.pk)
    if obj.status == "void":
        messages.error(request, "A voided expense cannot be posted — enter a new one.")
        return redirect("projects:pex_detail", pk=obj.pk)
    previous = obj.status
    obj.status = "posted"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "post",
                    changes={"verb": "post", "from": previous, "to": obj.status})
    messages.success(request, f"Posted {obj.number} — it now counts against the budget.")
    return redirect("projects:pex_detail", pk=obj.pk)


@login_required
@tenant_admin_required
@require_POST
def pex_void(request, pk):
    """Stop a posted row counting WITHOUT hiding it — the correction path for evidence the EVM
    math reads. Drafts have nothing to void; voiding is admin-gated because it rewrites what the
    cost figures say."""
    obj = get_object_or_404(ProjectExpense, pk=pk, tenant=request.tenant)
    if obj.status == "void":
        messages.info(request, "That expense is already voided.")
        return redirect("projects:pex_detail", pk=obj.pk)
    if obj.status != "posted":
        messages.error(request, "Only a posted expense can be voided — delete the draft "
                                "instead.")
        return redirect("projects:pex_detail", pk=obj.pk)
    previous = obj.status
    obj.status = "void"
    obj.save(update_fields=["status", "updated_at"])
    write_audit_log(request.user, obj, "void",
                    changes={"verb": "void", "from": previous, "to": obj.status})
    messages.success(request, f"Voided {obj.number} — it no longer counts against the budget.")
    return redirect("projects:pex_detail", pk=obj.pk)
