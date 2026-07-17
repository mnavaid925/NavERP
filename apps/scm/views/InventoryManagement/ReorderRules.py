"""SCM 4.3 Inventory Management — ReorderRule views."""
from apps.scm.views._common import *  # noqa: F401,F403
from apps.scm.views._helpers import _need_tenant
from apps.scm.models import ReorderRule
from apps.scm.forms import ReorderRuleForm


@login_required
def reorderrule_list(request):
    qs = ReorderRule.objects.filter(tenant=request.tenant).select_related("item", "location")
    return crud_list(
        request, qs, "scm/inventory/reorderrule/list.html",
        search_fields=["item__sku", "item__name", "location__code"],
        filters=[("is_active", "is_active", False)],
    )


@login_required
def reorderrule_create(request):
    if _need_tenant(request):
        return redirect("scm:reorderrule_list")
    return crud_create(request, form_class=ReorderRuleForm, template="scm/inventory/reorderrule/form.html",
                       success_url="scm:reorderrule_list")


@login_required
def reorderrule_edit(request, pk):
    return crud_edit(request, model=ReorderRule, pk=pk, form_class=ReorderRuleForm,
                     template="scm/inventory/reorderrule/form.html", success_url="scm:reorderrule_list")


@login_required
@require_POST
def reorderrule_delete(request, pk):
    return crud_delete(request, model=ReorderRule, pk=pk, success_url="scm:reorderrule_list")
