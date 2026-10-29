from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.SearchDiscovery.SearchMerchandisingRules import SearchMerchandisingRuleForm
from apps.ecommerce.models.SearchDiscovery.SearchMerchandisingRules import SearchMerchandisingRule
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def searchmerchandisingrule_list(request):
    qs = ecommerce_scope(
        SearchMerchandisingRule.objects.select_related("target_category", "boosted_product"),
        request,
    )

    search_query = request.GET.get("q", "").strip()
    rule_type = request.GET.get("rule_type", "").strip()
    action_type = request.GET.get("action_type", "").strip()
    is_active = request.GET.get("is_active", "").strip()

    if search_query:
        qs = qs.filter(
            Q(number__icontains=search_query)
            | Q(name__icontains=search_query)
            | Q(trigger_query__icontains=search_query)
            | Q(redirect_url__icontains=search_query)
            | Q(banner_title__icontains=search_query)
        )

    if rule_type:
        qs = qs.filter(rule_type=rule_type)

    if action_type:
        qs = qs.filter(action_type=action_type)

    if is_active in ("1", "true", "True"):
        qs = qs.filter(is_active=True)
    elif is_active in ("0", "false", "False"):
        qs = qs.filter(is_active=False)

    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "rules": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "q": search_query,
        "selected_rule_type": rule_type,
        "selected_action_type": action_type,
        "selected_active": is_active,
        "rule_type_choices": SearchMerchandisingRule.RULE_TYPE_CHOICES,
        "action_type_choices": SearchMerchandisingRule.ACTION_TYPE_CHOICES,
    }
    return render(
        request, "ecommerce/searchdiscovery/merchandisingrule/list.html", context
    )


@login_required
def searchmerchandisingrule_detail(request, pk):
    rule = ecommerce_object(
        request,
        SearchMerchandisingRule,
        pk,
        select_related=("target_category", "boosted_product"),
    )
    context = {
        "rule": rule,
    }
    return render(
        request, "ecommerce/searchdiscovery/merchandisingrule/detail.html", context
    )


@login_required
@tenant_admin_required
def searchmerchandisingrule_create(request):
    if request.method == "POST":
        form = SearchMerchandisingRuleForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            rule = form.save(commit=False)
            rule.tenant = request.tenant
            rule.save()
            write_audit_log(
                request,
                action="create",
                instance=rule,
                notes=f"Created merchandising rule {rule.number} ({rule.name})",
            )
            messages.success(request, f"Merchandising rule '{rule.name}' created.")
            return redirect("ecommerce:searchmerchandisingrule_detail", pk=rule.pk)
    else:
        form = SearchMerchandisingRuleForm(tenant=request.tenant)

    context = {
        "form": form,
        "rule": None,
        "is_edit": False,
    }
    return render(
        request, "ecommerce/searchdiscovery/merchandisingrule/form.html", context
    )


@login_required
@tenant_admin_required
def searchmerchandisingrule_edit(request, pk):
    rule = ecommerce_object(request, SearchMerchandisingRule, pk)
    if request.method == "POST":
        form = SearchMerchandisingRuleForm(
            request.POST, instance=rule, tenant=request.tenant
        )
        if form.is_valid():
            rule = form.save()
            write_audit_log(
                request,
                action="update",
                instance=rule,
                notes=f"Updated merchandising rule {rule.number} ({rule.name})",
            )
            messages.success(request, f"Merchandising rule '{rule.name}' updated.")
            return redirect("ecommerce:searchmerchandisingrule_detail", pk=rule.pk)
    else:
        form = SearchMerchandisingRuleForm(instance=rule, tenant=request.tenant)

    context = {
        "form": form,
        "rule": rule,
        "is_edit": True,
    }
    return render(
        request, "ecommerce/searchdiscovery/merchandisingrule/form.html", context
    )


@login_required
@tenant_admin_required
@require_POST
def searchmerchandisingrule_delete(request, pk):
    rule = ecommerce_object(request, SearchMerchandisingRule, pk)
    number = rule.number
    name = rule.name
    rule.delete()
    write_audit_log(
        request,
        action="delete",
        instance=rule,
        notes=f"Deleted merchandising rule {number} ({name})",
    )
    messages.success(request, f"Merchandising rule '{name}' deleted.")
    return redirect("ecommerce:searchmerchandisingrule_list")


@login_required
@tenant_admin_required
@require_POST
def searchmerchandisingrule_toggle(request, pk):
    rule = ecommerce_object(request, SearchMerchandisingRule, pk)
    rule.is_active = not rule.is_active
    rule.save(update_fields=["is_active", "updated_at"])
    state = "activated" if rule.is_active else "deactivated"
    write_audit_log(
        request,
        action="update",
        instance=rule,
        notes=f"{state.capitalize()} merchandising rule {rule.number}",
    )
    messages.success(request, f"Merchandising rule '{rule.name}' {state}.")
    return redirect("ecommerce:searchmerchandisingrule_detail", pk=rule.pk)
