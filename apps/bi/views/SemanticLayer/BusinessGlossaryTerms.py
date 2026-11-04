from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.bi.forms.SemanticLayer.BusinessGlossaryTerms import (
    BusinessGlossaryTermCertificationForm,
    BusinessGlossaryTermForm,
)
from apps.bi.models.SemanticLayer.BusinessGlossaryTerms import BusinessGlossaryTerm
from apps.bi.views._common import bi_object, bi_scope
from apps.core.utils import write_audit_log


@login_required
def business_glossary_term_list(request):
    queryset = (
        bi_scope(BusinessGlossaryTerm.objects.all(), request)
        .select_related("steward", "org_unit")
        .annotate(measure_count=Count("measures", distinct=True))
    )

    q = request.GET.get("q", "").strip()[:100]
    if q:
        queryset = queryset.filter(
            Q(name__icontains=q)
            | Q(code__icontains=q)
            | Q(number__icontains=q)
            | Q(short_definition__icontains=q)
            | Q(full_definition__icontains=q)
            | Q(synonyms__icontains=q)
        )

    domain_filter = request.GET.get("domain", "").strip()
    if domain_filter:
        queryset = queryset.filter(domain_category=domain_filter)

    certification_status_filter = request.GET.get("certification_status", "").strip()
    if certification_status_filter:
        queryset = queryset.filter(certification_status=certification_status_filter)

    is_active_filter = request.GET.get("is_active", "").strip()
    if is_active_filter in ("1", "true", "True"):
        queryset = queryset.filter(is_active=True)
    elif is_active_filter in ("0", "false", "False"):
        queryset = queryset.filter(is_active=False)

    total_count = queryset.count()
    paginator = Paginator(queryset.order_by("domain_category", "name"), 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    context = {
        "terms": page_obj,
        "glossary_terms": page_obj,
        "object_list": page_obj,
        "page_obj": page_obj,
        "is_paginated": page_obj.has_other_pages(),
        "total_count": total_count,
        "search_query": q,
        "domain_filter": domain_filter,
        "certification_status_filter": certification_status_filter,
        "is_active_filter": is_active_filter,
        "domain_category_choices": BusinessGlossaryTerm.DOMAIN_CATEGORY_CHOICES,
        "certification_status_choices": BusinessGlossaryTerm.CERTIFICATION_STATUS_CHOICES,
    }
    return render(request, "bi/semantic_layer/business_glossary_term/list.html", context)


@login_required
def business_glossary_term_detail(request, pk):
    term = bi_object(
        request,
        BusinessGlossaryTerm,
        pk,
        select_related=("steward", "org_unit", "certified_by"),
        prefetch_related=("related_terms",),
    )
    related_measures = term.measures.filter(tenant=request.tenant).select_related("semantic_model")

    certify_form = BusinessGlossaryTermCertificationForm(
        initial={
            "certification_status": term.certification_status,
            "certification_notes": term.certification_notes,
        }
    )

    context = {
        "term": term,
        "glossary_term": term,
        "object": term,
        "related_measures": related_measures,
        "certify_form": certify_form,
    }
    return render(request, "bi/semantic_layer/business_glossary_term/detail.html", context)


@login_required
def business_glossary_term_create(request):
    if request.method == "POST":
        form = BusinessGlossaryTermForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            term = form.save(commit=False)
            term.tenant = request.tenant
            if not term.steward:
                term.steward = request.user
            term.save()
            form.save_m2m()
            write_audit_log(request.user, term, "create", tenant=request.tenant)
            messages.success(request, f"Glossary Term '{term.name}' created successfully.")
            return redirect("bi:business_glossary_term_detail", pk=term.pk)
    else:
        form = BusinessGlossaryTermForm(tenant=request.tenant)

    context = {
        "form": form,
        "is_edit": False,
    }
    return render(request, "bi/semantic_layer/business_glossary_term/form.html", context)


@login_required
def business_glossary_term_edit(request, pk):
    term = bi_object(request, BusinessGlossaryTerm, pk, prefetch_related=("related_terms",))
    if request.method == "POST":
        form = BusinessGlossaryTermForm(request.POST, instance=term, tenant=request.tenant)
        if form.is_valid():
            term = form.save()
            write_audit_log(request.user, term, "update", tenant=request.tenant)
            messages.success(request, f"Glossary Term '{term.name}' updated successfully.")
            return redirect("bi:business_glossary_term_detail", pk=term.pk)
    else:
        form = BusinessGlossaryTermForm(instance=term, tenant=request.tenant)

    context = {
        "form": form,
        "term": term,
        "glossary_term": term,
        "object": term,
        "is_edit": True,
    }
    return render(request, "bi/semantic_layer/business_glossary_term/form.html", context)


@login_required
@require_POST
def business_glossary_term_delete(request, pk):
    term = bi_object(request, BusinessGlossaryTerm, pk)
    name = term.name
    num = term.number
    write_audit_log(request.user, term, "delete", tenant=request.tenant)
    term.delete()
    messages.success(request, f"Glossary Term '{name}' ({num}) deleted successfully.")
    return redirect("bi:business_glossary_term_list")


@login_required
@require_POST
def business_glossary_term_certify(request, pk):
    term = bi_object(request, BusinessGlossaryTerm, pk)
    form = BusinessGlossaryTermCertificationForm(request.POST)
    if form.is_valid():
        new_status = form.cleaned_data["certification_status"]
        notes = form.cleaned_data.get("certification_notes", "")
        old_status = term.certification_status
        term.certification_status = new_status
        term.certification_notes = notes
        if new_status == "certified":
            term.certified_by = request.user
            term.certified_at = timezone.now()
        else:
            term.certified_by = None
            term.certified_at = None
        term.save(update_fields=["certification_status", "certification_notes", "certified_by", "certified_at", "updated_at"])
        write_audit_log(request.user, term, "certify", tenant=request.tenant)
        messages.success(request, f"Certification status updated to '{term.get_certification_status_display()}'.")
    else:
        messages.error(request, "Invalid certification status submitted.")
    return redirect("bi:business_glossary_term_detail", pk=term.pk)
