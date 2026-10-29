from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.SearchDiscovery.SearchSynonyms import SearchSynonymForm
from apps.ecommerce.models.SearchDiscovery.SearchSynonyms import SearchSynonym
from apps.ecommerce.views._common import ecommerce_object, ecommerce_scope


@login_required
def searchsynonym_list(request):
    qs = ecommerce_scope(SearchSynonym.objects.all(), request)

    search_query = request.GET.get("q", "").strip()
    synonym_type = request.GET.get("synonym_type", "").strip()
    is_active = request.GET.get("is_active", "").strip()

    if search_query:
        qs = qs.filter(
            Q(number__icontains=search_query)
            | Q(name__icontains=search_query)
            | Q(root_term__icontains=search_query)
            | Q(synonyms__icontains=search_query)
        )

    if synonym_type:
        qs = qs.filter(synonym_type=synonym_type)

    if is_active in ("1", "true", "True"):
        qs = qs.filter(is_active=True)
    elif is_active in ("0", "false", "False"):
        qs = qs.filter(is_active=False)

    paginator = Paginator(qs, 25)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "synonyms": page_obj,
        "paginator": paginator,
        "is_paginated": page_obj.has_other_pages(),
        "q": search_query,
        "selected_type": synonym_type,
        "selected_active": is_active,
        "synonym_type_choices": SearchSynonym.SYNONYM_TYPE_CHOICES,
    }
    return render(request, "ecommerce/searchdiscovery/synonym/list.html", context)


@login_required
def searchsynonym_detail(request, pk):
    synonym = ecommerce_object(request, SearchSynonym, pk)
    context = {
        "synonym": synonym,
        "synonym_list": synonym.get_synonym_list(),
    }
    return render(request, "ecommerce/searchdiscovery/synonym/detail.html", context)


@login_required
@tenant_admin_required
def searchsynonym_create(request):
    if request.method == "POST":
        form = SearchSynonymForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            synonym = form.save(commit=False)
            synonym.tenant = request.tenant
            synonym.save()
            write_audit_log(
                request,
                action="create",
                instance=synonym,
                notes=f"Created search synonym {synonym.number} ({synonym.root_term})",
            )
            messages.success(request, f"Search synonym rule '{synonym.name}' created.")
            return redirect("ecommerce:searchsynonym_detail", pk=synonym.pk)
    else:
        initial = {}
        root_param = request.GET.get("root", "").strip()
        if root_param:
            initial["root_term"] = root_param
        form = SearchSynonymForm(tenant=request.tenant, initial=initial)

    context = {
        "form": form,
        "synonym": None,
        "is_edit": False,
    }
    return render(request, "ecommerce/searchdiscovery/synonym/form.html", context)


@login_required
@tenant_admin_required
def searchsynonym_edit(request, pk):
    synonym = ecommerce_object(request, SearchSynonym, pk)
    if request.method == "POST":
        form = SearchSynonymForm(request.POST, instance=synonym, tenant=request.tenant)
        if form.is_valid():
            synonym = form.save()
            write_audit_log(
                request,
                action="update",
                instance=synonym,
                notes=f"Updated search synonym {synonym.number} ({synonym.root_term})",
            )
            messages.success(request, f"Search synonym rule '{synonym.name}' updated.")
            return redirect("ecommerce:searchsynonym_detail", pk=synonym.pk)
    else:
        form = SearchSynonymForm(instance=synonym, tenant=request.tenant)

    context = {
        "form": form,
        "synonym": synonym,
        "is_edit": True,
    }
    return render(request, "ecommerce/searchdiscovery/synonym/form.html", context)


@login_required
@tenant_admin_required
@require_POST
def searchsynonym_delete(request, pk):
    synonym = ecommerce_object(request, SearchSynonym, pk)
    number = synonym.number
    name = synonym.name
    synonym.delete()
    write_audit_log(
        request,
        action="delete",
        instance=synonym,
        notes=f"Deleted search synonym {number} ({name})",
    )
    messages.success(request, f"Search synonym rule '{name}' deleted.")
    return redirect("ecommerce:searchsynonym_list")


@login_required
@tenant_admin_required
@require_POST
def searchsynonym_toggle(request, pk):
    synonym = ecommerce_object(request, SearchSynonym, pk)
    synonym.is_active = not synonym.is_active
    synonym.save(update_fields=["is_active", "updated_at"])
    state = "activated" if synonym.is_active else "deactivated"
    write_audit_log(
        request,
        action="update",
        instance=synonym,
        notes=f"{state.capitalize()} search synonym {synonym.number}",
    )
    messages.success(request, f"Search synonym rule '{synonym.name}' {state}.")
    return redirect("ecommerce:searchsynonym_detail", pk=synonym.pk)
