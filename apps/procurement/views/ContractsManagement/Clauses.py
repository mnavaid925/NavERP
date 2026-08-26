"""Procurement 6.8 Contract Management â€” ContractClause views.

The clause library is legal language, so WRITES are tenant-admin gated (the same
authority bar as the approval engine's routing rules); reads are open to every
signed-in member of the workspace.
"""
from django.db.models import Count, ProtectedError

from apps.core.crud import crud_list

from apps.procurement.forms import ContractClauseForm
from apps.procurement.models import ContractClause
from apps.procurement.views._common import *  # noqa: F401,F403

CATEGORY_CHOICES = [value for value in ContractClause.CATEGORY_CHOICES]


@login_required
def clause_list(request):
    # n_links annotated once per page: rendering the reverse relation's .count()
    # in the table would fire one COUNT query per row.
    qs = (ContractClause.objects.filter(tenant=request.tenant)
          .annotate(n_links=Count("procurement_clause_links")))
    return crud_list(
        request, qs, "procurement/contractsmanagement/clauses/list.html",
        search_fields=["title", "body", "notes"],
        filters=[("category", "category", False),
                 ("active", "is_active", True)],
        extra_context={"category_choices": CATEGORY_CHOICES},
    )


@login_required
def clause_detail(request, pk):
    obj = get_object_or_404(ContractClause, pk=pk, tenant=request.tenant)
    used_by = (obj.procurement_clause_links
               .select_related("contract").order_by("section_order")[:20])
    return render(request, "procurement/contractsmanagement/clauses/detail.html",
                  {"obj": obj, "used_by": used_by})


def _clause_form(request, instance):
    if instance is None and request.tenant is None:
        messages.error(request, "Select a tenant workspace before adding clauses.")
        return redirect("dashboard:home")
    is_edit = instance is not None
    if request.method == "POST":
        form = ContractClauseForm(request.POST, instance=instance,
                                  tenant=request.tenant)
        if form.is_valid():
            clause = form.save(commit=False)
            clause.tenant = request.tenant
            clause.save()
            write_audit_log(request.user, clause, "update" if is_edit else "create")
            messages.success(request, f"Clause '{clause.title}' saved.")
            return redirect("procurement:clause_detail", pk=clause.pk)
    else:
        form = ContractClauseForm(instance=instance, tenant=request.tenant)
    return render(request, "procurement/contractsmanagement/clauses/form.html",
                  {"form": form, "obj": instance, "is_edit": is_edit})


@login_required
@tenant_admin_required
def clause_create(request):
    return _clause_form(request, None)


@login_required
@tenant_admin_required
def clause_edit(request, pk):
    obj = get_object_or_404(ContractClause, pk=pk, tenant=request.tenant)
    return _clause_form(request, obj)


@login_required
@tenant_admin_required
@require_POST
def clause_delete(request, pk):
    """Refused while any agreement still drafts this clause â€” PROTECT would raise,
    so the check produces a readable message instead of an IntegrityError page."""
    obj = get_object_or_404(ContractClause, pk=pk, tenant=request.tenant)
    if obj.procurement_clause_links.exists():
        messages.error(request,
                       "This clause is drafted into at least one agreement and cannot "
                       "be deleted â€” deactivate it instead.")
        return redirect("procurement:clause_detail", pk=pk)
    title = obj.title
    try:
        obj.delete()
    except ProtectedError:
        # A link was drafted between the check above and now â€” never 500 on it.
        messages.error(request,
                       "This clause was just drafted into an agreement â€” deactivate "
                       "it instead.")
        return redirect("procurement:clause_detail", pk=pk)
    write_audit_log(request.user, obj, "delete")
    messages.success(request, f"Clause '{title}' deleted.")
    return redirect("procurement:clause_list")
