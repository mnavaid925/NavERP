"""SCM 4.3 Inventory Management — ReorderRule views."""
from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._common import _changed
from apps.scm.views._helpers import _need_tenant
from apps.scm.models import ReorderRule
from apps.scm.forms import ReorderRuleForm


@login_required
def reorderrule_list(request):
    qs = ReorderRule.objects.filter(tenant=request.tenant).select_related("item", "location")
    return crud_list(
        request, qs, "scm/inventory/reorderrule/list.html",
        search_fields=["item__sku", "item__name", "location__code"],
        filters=[("is_active", "is_active", False),
                 # 4.7 added the safety-stock policy to this rule; the list filters on it so a
                 # planner can see which rules are still on the hand-entered `fixed` method.
                 ("safety_stock_method", "safety_stock_method", False)],
        extra_context={"method_choices": ReorderRule.SAFETY_STOCK_METHOD_CHOICES},
    )


@login_required
def reorderrule_create(request):
    if _need_tenant(request):
        return redirect("scm:reorderrule_list")
    return _reorderrule_form(request, instance=None)


@login_required
def reorderrule_edit(request, pk):
    obj = get_object_or_404(ReorderRule, pk=pk, tenant=request.tenant)
    return _reorderrule_form(request, instance=obj)


def _is_tenant_admin(user):
    return bool(getattr(user, "is_superuser", False) or getattr(user, "is_tenant_admin", False))


def _reorderrule_form(request, instance):
    """Hand-rolled rather than `crud_*` so the form learns whether the user may write the LIVE
    ``safety_stock``/``reorder_point``.

    Those two columns are what 4.1 purchasing reorders against, which is why 4.7's
    ``safety_stock_apply`` is admin-gated — this page writes the same columns, so it needs the same
    gate or the other one is decoration. Everything else on the rule (the policy inputs, the reorder
    quantity, active) stays editable by any planner.
    """
    is_edit = instance is not None
    is_admin = _is_tenant_admin(request.user)
    if request.method == "POST":
        form = ReorderRuleForm(request.POST, instance=instance, tenant=request.tenant,
                               is_tenant_admin=is_admin)
        if form.is_valid():
            rule = form.save(commit=False)
            rule.tenant = request.tenant
            rule.save()
            write_audit_log(request.user, rule, "update" if is_edit else "create", _changed(form))
            messages.success(request, "Updated successfully." if is_edit else "Created successfully.")
            return redirect("scm:reorderrule_list")
    else:
        form = ReorderRuleForm(instance=instance, tenant=request.tenant, is_tenant_admin=is_admin)
    return render(request, "scm/inventory/reorderrule/form.html",
                  {"form": form, "obj": instance, "is_edit": is_edit})


@login_required
@require_POST
def reorderrule_delete(request, pk):
    return crud_delete(request, model=ReorderRule, pk=pk, success_url="scm:reorderrule_list")
