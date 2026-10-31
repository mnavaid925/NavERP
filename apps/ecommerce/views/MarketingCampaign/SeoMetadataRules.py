from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.MarketingCampaign.SeoMetadataRules import SeoMetadataRuleForm
from apps.ecommerce.models.MarketingCampaign.SeoMetadataRules import SeoMetadataRule
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def seometadatarule_list(request):
    qs = ecommerce_scope(SeoMetadataRule.objects.all(), request).select_related(
        "target_category", "target_product"
    )

    search_query = request.GET.get("q", "").strip()
    rule_type = request.GET.get("rule_type", "").strip()
    schema_type = request.GET.get("schema_type", "").strip()
    is_active = request.GET.get("is_active", "").strip()

    if search_query:
        qs = qs.filter(
            Q(number__icontains=search_query)
            | Q(name__icontains=search_query)
            | Q(target_keyword__icontains=search_query)
            | Q(meta_title_template__icontains=search_query)
        )

    if rule_type:
        qs = qs.filter(rule_type=rule_type)

    if schema_type:
        qs = qs.filter(json_ld_schema_type=schema_type)

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
        "rule_type_choices": SeoMetadataRule.RULE_TYPE_CHOICES,
        "schema_type_choices": SeoMetadataRule.SCHEMA_TYPE_CHOICES,
        "robots_choices": SeoMetadataRule.ROBOTS_CHOICES,
        "selected_type": rule_type,
        "selected_schema": schema_type,
        "selected_active": is_active,
        "search_query": search_query,
        "q": search_query,
    }
    return render(request, "ecommerce/marketing_campaign/seo_rule/list.html", context)


@login_required
def seometadatarule_detail(request, pk):
    rule = ecommerce_object(
        request,
        SeoMetadataRule,
        pk,
        select_related=("target_category", "target_product"),
    )

    sample_context = {
        "product_name": rule.target_product.name if rule.target_product else "Classic Cotton T-Shirt",
        "brand": "NavStore Originals",
        "category": rule.target_category.name if rule.target_category else "Apparel",
        "price": "29.99",
        "site_name": "NavStore",
    }
    preview_title = rule.render_title(sample_context)
    preview_description = rule.render_description(sample_context)

    context = {
        "rule": rule,
        "preview_title": preview_title,
        "preview_description": preview_description,
    }
    return render(request, "ecommerce/marketing_campaign/seo_rule/detail.html", context)


@login_required
@tenant_admin_required
def seometadatarule_create(request):
    if request.method == "POST":
        form = SeoMetadataRuleForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            rule = form.save(commit=False)
            rule.tenant = request.tenant
            rule.save()
            write_audit_log(
                request.tenant,
                request.user,
                "create",
                f"Created SEO rule {rule.number} ({rule.name})",
            )
            messages.success(request, f"SEO rule '{rule.name}' created successfully.")
            return redirect("ecommerce:seometadatarule_detail", pk=rule.pk)
    else:
        form = SeoMetadataRuleForm(tenant=request.tenant)

    context = {
        "form": form,
    }
    return render(request, "ecommerce/marketing_campaign/seo_rule/form.html", context)


@login_required
@tenant_admin_required
def seometadatarule_edit(request, pk):
    rule = ecommerce_object(request, SeoMetadataRule, pk)
    if request.method == "POST":
        form = SeoMetadataRuleForm(request.POST, instance=rule, tenant=request.tenant)
        if form.is_valid():
            rule = form.save()
            write_audit_log(
                request.tenant,
                request.user,
                "update",
                f"Updated SEO rule {rule.number} ({rule.name})",
            )
            messages.success(request, f"SEO rule '{rule.name}' updated successfully.")
            return redirect("ecommerce:seometadatarule_detail", pk=rule.pk)
    else:
        form = SeoMetadataRuleForm(instance=rule, tenant=request.tenant)

    context = {
        "form": form,
        "rule": rule,
    }
    return render(request, "ecommerce/marketing_campaign/seo_rule/form.html", context)


@login_required
@tenant_admin_required
@require_POST
def seometadatarule_delete(request, pk):
    rule = ecommerce_object(request, SeoMetadataRule, pk)
    name = rule.name
    number = rule.number
    rule.delete()
    write_audit_log(
        request.tenant,
        request.user,
        "delete",
        f"Deleted SEO rule {number} ({name})",
    )
    messages.success(request, f"SEO rule '{name}' was deleted.")
    return redirect("ecommerce:seometadatarule_list")


@login_required
@tenant_admin_required
@require_POST
def seometadatarule_toggle(request, pk):
    rule = ecommerce_object(request, SeoMetadataRule, pk)
    rule.is_active = not rule.is_active
    rule.save()
    status_label = "activated" if rule.is_active else "deactivated"
    write_audit_log(
        request.tenant,
        request.user,
        "update",
        f"{status_label.capitalize()} SEO rule {rule.number} ({rule.name})",
    )
    messages.success(request, f"SEO rule '{rule.name}' was {status_label}.")
    return redirect("ecommerce:seometadatarule_detail", pk=rule.pk)
