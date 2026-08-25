"""Inventory 5.18 — GL Posting Rules views.

CRUD over the account map the JE automation posts through. Same gating as every other
rule table in this app: writes are `@tenant_admin_required` (a rule IS where money goes),
list/detail are member-readable.
"""
from apps.core.decorators import tenant_admin_required
from apps.inventory.forms import GLPostRuleForm
from apps.inventory.models import GLPostRule
from apps.inventory.views._common import *  # noqa: F401,F403


def _scoped(tenant):
    return (GLPostRule.objects.filter(tenant=tenant)
            .select_related("inventory_account", "offset_account"))


@login_required
def glpostrule_list(request):
    return crud_list(
        request, _scoped(request.tenant), "inventory/finint/glpostrule/list.html",
        search_fields=["name", "notes", "inventory_account__name", "offset_account__name"],
        filters=[("active", "is_active", False)],
        extra_context={
            "is_admin": bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)),
        },
    )


@login_required
def glpostrule_detail(request, pk):
    obj = get_object_or_404(_scoped(request.tenant), pk=pk)
    return render(request, "inventory/finint/glpostrule/detail.html", {
        "obj": obj,
        "is_admin": bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)),
    })


@tenant_admin_required
def glpostrule_create(request):
    return crud_create(
        request, form_class=GLPostRuleForm,
        template="inventory/finint/glpostrule/form.html",
        success_url="inventory:glpostrule_list",
    )


@tenant_admin_required
def glpostrule_edit(request, pk):
    return crud_edit(
        request, model=GLPostRule, pk=pk, form_class=GLPostRuleForm,
        template="inventory/finint/glpostrule/form.html",
        success_url="inventory:glpostrule_list",
    )


@tenant_admin_required
@require_POST
def glpostrule_delete(request, pk):
    return crud_delete(request, model=GLPostRule, pk=pk,
                       success_url="inventory:glpostrule_list")
