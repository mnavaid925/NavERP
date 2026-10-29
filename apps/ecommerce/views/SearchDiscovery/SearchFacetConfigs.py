from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.SearchDiscovery.SearchFacetConfigs import SearchFacetConfigForm
from apps.ecommerce.models.SearchDiscovery.SearchFacetConfigs import SearchFacetConfig
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def searchfacetconfig_list(request):
    qs = ecommerce_scope(
        SearchFacetConfig.objects.select_related("category_scope"),
        request,
    )

    search_query = request.GET.get("q", "").strip()
    source_type = request.GET.get("source_type", "").strip()
    widget_type = request.GET.get("widget_type", "").strip()
    filter_logic = request.GET.get("filter_logic", "").strip()
    is_active = request.GET.get("is_active", "").strip()

    if search_query:
        qs = qs.filter(
            Q(number__icontains=search_query)
            | Q(name__icontains=search_query)
            | Q(code__icontains=search_query)
            | Q(option_key__icontains=search_query)
        )

    if source_type:
        qs = qs.filter(source_type=source_type)

    if widget_type:
        qs = qs.filter(widget_type=widget_type)

    if filter_logic:
        qs = qs.filter(filter_logic=filter_logic)

    if is_active in ("1", "true", "True"):
        qs = qs.filter(is_active=True)
    elif is_active in ("0", "false", "False"):
        qs = qs.filter(is_active=False)

    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "facet_configs": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "q": search_query,
        "selected_source": source_type,
        "selected_widget": widget_type,
        "selected_logic": filter_logic,
        "selected_active": is_active,
        "source_type_choices": SearchFacetConfig.SOURCE_TYPE_CHOICES,
        "widget_type_choices": SearchFacetConfig.WIDGET_TYPE_CHOICES,
        "filter_logic_choices": SearchFacetConfig.FILTER_LOGIC_CHOICES,
    }
    return render(
        request, "ecommerce/searchdiscovery/facetconfig/list.html", context
    )


@login_required
def searchfacetconfig_detail(request, pk):
    facet_config = ecommerce_object(
        request, SearchFacetConfig, pk, select_related=("category_scope",)
    )
    context = {
        "facet_config": facet_config,
    }
    return render(
        request, "ecommerce/searchdiscovery/facetconfig/detail.html", context
    )


@login_required
@tenant_admin_required
def searchfacetconfig_create(request):
    if request.method == "POST":
        form = SearchFacetConfigForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            facet_config = form.save(commit=False)
            facet_config.tenant = request.tenant
            facet_config.save()
            write_audit_log(
                request.user,
                facet_config,
                "create",
                {"number": facet_config.number, "name": facet_config.name},
            )
            messages.success(
                request, f"Facet configuration '{facet_config.name}' created."
            )
            return redirect(
                "ecommerce:searchfacetconfig_detail", pk=facet_config.pk
            )
    else:
        form = SearchFacetConfigForm(tenant=request.tenant)

    context = {
        "form": form,
        "facet_config": None,
        "is_edit": False,
    }
    return render(
        request, "ecommerce/searchdiscovery/facetconfig/form.html", context
    )


@login_required
@tenant_admin_required
def searchfacetconfig_edit(request, pk):
    facet_config = ecommerce_object(request, SearchFacetConfig, pk)
    if request.method == "POST":
        form = SearchFacetConfigForm(
            request.POST, instance=facet_config, tenant=request.tenant
        )
        if form.is_valid():
            facet_config = form.save()
            write_audit_log(
                request.user,
                facet_config,
                "update",
                {"number": facet_config.number, "name": facet_config.name},
            )
            messages.success(
                request, f"Facet configuration '{facet_config.name}' updated."
            )
            return redirect(
                "ecommerce:searchfacetconfig_detail", pk=facet_config.pk
            )
    else:
        form = SearchFacetConfigForm(instance=facet_config, tenant=request.tenant)

    context = {
        "form": form,
        "facet_config": facet_config,
        "is_edit": True,
    }
    return render(
        request, "ecommerce/searchdiscovery/facetconfig/form.html", context
    )


@login_required
@tenant_admin_required
@require_POST
def searchfacetconfig_delete(request, pk):
    facet_config = ecommerce_object(request, SearchFacetConfig, pk)
    number = facet_config.number
    name = facet_config.name
    facet_config.delete()
    write_audit_log(
        request.user,
        facet_config,
        "delete",
        {"number": number, "name": name},
    )
    messages.success(request, f"Facet configuration '{name}' deleted.")
    return redirect("ecommerce:searchfacetconfig_list")


@login_required
@tenant_admin_required
@require_POST
def searchfacetconfig_toggle(request, pk):
    facet_config = ecommerce_object(request, SearchFacetConfig, pk)
    facet_config.is_active = not facet_config.is_active
    facet_config.save(update_fields=["is_active", "updated_at"])
    state = "activated" if facet_config.is_active else "deactivated"
    write_audit_log(
        request.user,
        facet_config,
        "update",
        {"is_active": facet_config.is_active},
    )
    messages.success(
        request, f"Facet configuration '{facet_config.name}' {state}."
    )
    return redirect("ecommerce:searchfacetconfig_detail", pk=facet_config.pk)
