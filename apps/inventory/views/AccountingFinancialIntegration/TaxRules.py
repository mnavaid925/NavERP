"""Inventory 5.18 — Tax Management views.

CRUD over the TaxRule catalog. Rule WRITES are admin-gated (`@tenant_admin_required`)
— a rule decides what tax every drafted bill/invoice line carries, which is a money
decision; list/detail stay member-readable.
"""
from apps.core.decorators import tenant_admin_required
from apps.inventory.forms import TaxRuleForm
from apps.inventory.models import TaxRule
from apps.inventory.views._common import *  # noqa: F401,F403


def _scoped(tenant):
    return (TaxRule.objects.filter(tenant=tenant)
            .select_related("item", "category", "tax_code"))


@login_required
def taxrule_list(request):
    qs = _scoped(request.tenant)
    return crud_list(
        request, qs, "inventory/finint/taxrule/list.html",
        search_fields=["name", "country", "notes", "item__sku", "category__name"],
        filters=[("active", "is_active", False)],
        extra_context={
            "is_admin": bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)),
        },
    )


@login_required
def taxrule_detail(request, pk):
    obj = get_object_or_404(_scoped(request.tenant), pk=pk)
    return render(request, "inventory/finint/taxrule/detail.html", {
        "obj": obj,
        "specificity": TaxRule._specificity(obj),
        "is_admin": bool(request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)),
    })


@tenant_admin_required
def taxrule_create(request):
    return crud_create(
        request, form_class=TaxRuleForm,
        template="inventory/finint/taxrule/form.html",
        success_url="inventory:taxrule_list",
    )


@tenant_admin_required
def taxrule_edit(request, pk):
    return crud_edit(
        request, model=TaxRule, pk=pk, form_class=TaxRuleForm,
        template="inventory/finint/taxrule/form.html",
        success_url="inventory:taxrule_list",
    )


@tenant_admin_required
@require_POST
def taxrule_delete(request, pk):
    return crud_delete(request, model=TaxRule, pk=pk,
                       success_url="inventory:taxrule_list")
