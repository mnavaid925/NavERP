from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.documents.forms.MetadataIndexing.TaxonomyTerms import TaxonomyTermForm
from apps.documents.models.MetadataIndexing.TaxonomyTerms import TaxonomyTerm


@login_required
def taxonomy_term_list(request):
    """
    Sub-module 13.5: List all controlled vocabulary terms with search and category filtering.
    """
    tenant = request.tenant
    qs = TaxonomyTerm.objects.filter(tenant=tenant).select_related("parent")

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(
            Q(name__icontains(q)) |
            Q(term_code__icontains(q)) |
            Q(description__icontains(q)) |
            Q(synonyms_json__icontains(q)) |
            Q(external_code__icontains(q))
        )

    category = request.GET.get("category", "").strip()
    if category:
        qs = qs.filter(category=category)

    is_active_param = request.GET.get("is_active", "").strip()
    if is_active_param in ["true", "1"]:
        qs = qs.filter(is_active=True)
    elif is_active_param in ["false", "0"]:
        qs = qs.filter(is_active=False)

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context = {
        "taxonomy_terms": page_obj.object_list,
        "page_obj": page_obj,
        "is_paginated": page_obj.has_other_pages(),
        "q": q,
        "category": category,
        "is_active": is_active_param,
        "category_choices": TaxonomyTerm.CATEGORY_CHOICES,
    }
    return render(request, "documents/metadata_indexing/taxonomy_term/list.html", context)


@login_required
def taxonomy_term_tree(request):
    """
    Visual hierarchical view of controlled vocabularies and thesauri.
    """
    tenant = request.tenant
    selected_category = request.GET.get("category", "").strip()
    qs = TaxonomyTerm.objects.filter(tenant=tenant, is_active=True).prefetch_related("children")

    if selected_category:
        qs = qs.filter(category=selected_category)

    root_terms = qs.filter(parent__isnull=True).order_by("category", "name")

    # Group by category
    category_groups = {}
    for term in root_terms:
        cat_label = dict(TaxonomyTerm.CATEGORY_CHOICES).get(term.category, term.category)
        if cat_label not in category_groups:
            category_groups[cat_label] = []
        category_groups[cat_label].append(term)

    context = {
        "root_terms": root_terms,
        "category_groups": category_groups,
        "selected_category": selected_category,
        "category_choices": TaxonomyTerm.CATEGORY_CHOICES,
    }
    return render(request, "documents/metadata_indexing/taxonomy_term/tree.html", context)


@login_required
def taxonomy_term_create(request):
    """
    Define a new standardized controlled vocabulary term.
    """
    tenant = request.tenant
    if request.method == "POST":
        form = TaxonomyTermForm(request.POST, tenant=tenant)
        if form.is_valid():
            with transaction.atomic():
                term = form.save(commit=False)
                term.tenant = tenant
                term.created_by = request.user
                term.save()
                write_audit_log(request.user, term, "create", tenant=tenant)
            messages.success(request, f"Taxonomy Term '{term.name}' [{term.term_code}] created successfully.")
            return redirect("documents:taxonomy_term_detail", pk=term.pk)
    else:
        initial = {}
        parent_id = request.GET.get("parent", "").strip()
        if parent_id.isdigit():
            initial["parent"] = int(parent_id)
        cat = request.GET.get("category", "").strip()
        if cat:
            initial["category"] = cat
        form = TaxonomyTermForm(initial=initial, tenant=tenant)

    context = {
        "form": form,
        "is_edit": False,
        "category_choices": TaxonomyTerm.CATEGORY_CHOICES,
    }
    return render(request, "documents/metadata_indexing/taxonomy_term/form.html", context)


@login_required
def taxonomy_term_detail(request, pk):
    """
    Detailed inspection of a taxonomy term, child terms, and synonym catalog.
    """
    tenant = request.tenant
    term = get_object_or_404(
        TaxonomyTerm.objects.select_related("parent", "created_by").prefetch_related("children"),
        pk=pk,
        tenant=tenant,
    )

    child_terms = term.children.filter(tenant=tenant)
    synonyms_list = term.parsed_synonyms

    context = {
        "taxonomy_term": term,
        "obj": term,
        "child_terms": child_terms,
        "synonyms_list": synonyms_list,
        "category_badge": term.category_badge,
        "status_badge": term.status_badge,
    }
    return render(request, "documents/metadata_indexing/taxonomy_term/detail.html", context)


@login_required
def taxonomy_term_edit(request, pk):
    """
    Modify an existing taxonomy term or adjust its synonym list.
    """
    tenant = request.tenant
    term = get_object_or_404(TaxonomyTerm, pk=pk, tenant=tenant)

    if request.method == "POST":
        form = TaxonomyTermForm(request.POST, instance=term, tenant=tenant)
        if form.is_valid():
            with transaction.atomic():
                updated_term = form.save()
                write_audit_log(request.user, updated_term, "update", tenant=tenant)
            messages.success(request, f"Taxonomy Term '{updated_term.name}' updated successfully.")
            return redirect("documents:taxonomy_term_detail", pk=updated_term.pk)
    else:
        form = TaxonomyTermForm(instance=term, tenant=tenant)

    context = {
        "form": form,
        "taxonomy_term": term,
        "obj": term,
        "is_edit": True,
        "category_choices": TaxonomyTerm.CATEGORY_CHOICES,
    }
    return render(request, "documents/metadata_indexing/taxonomy_term/form.html", context)


@login_required
@require_POST
def taxonomy_term_delete(request, pk):
    """
    Delete a taxonomy term.
    """
    tenant = request.tenant
    term = get_object_or_404(TaxonomyTerm, pk=pk, tenant=tenant)

    if term.children.exists():
        messages.error(request, f"Cannot delete taxonomy term '{term.name}' because it has child terms. Reassign or delete child terms first.")
        return redirect("documents:taxonomy_term_detail", pk=term.pk)

    is_admin = request.user.is_superuser or getattr(request.user, "is_tenant_admin", False)
    if term.is_governed and not is_admin:
        messages.error(request, f"Taxonomy Term '{term.name}' is governed and requires administrator authorization to delete.")
        return redirect("documents:taxonomy_term_detail", pk=term.pk)

    name = term.name
    with transaction.atomic():
        write_audit_log(request.user, term, "delete", tenant=tenant)
        term.delete()
    messages.success(request, f"Taxonomy Term '{name}' deleted successfully.")
    return redirect("documents:taxonomy_term_list")
