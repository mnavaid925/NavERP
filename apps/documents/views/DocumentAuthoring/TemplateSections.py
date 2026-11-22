from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.documents.forms.DocumentAuthoring.TemplateSections import TemplateSectionForm
from apps.documents.models.DocumentAuthoring.DocumentTemplates import DocumentTemplate
from apps.documents.models.DocumentAuthoring.TemplateSections import TemplateSection
from apps.documents.views._common import documents_object, documents_scope


@login_required
def template_section_list(request):
    qs = documents_scope(TemplateSection.objects.select_related("template"), request)

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(number__icontains=q) | Q(content__icontains=q))

    section_type = request.GET.get("section_type", "").strip()
    if section_type:
        qs = qs.filter(section_type=section_type)

    template_id = request.GET.get("template", "").strip()
    if template_id.isdigit():
        qs = qs.filter(template_id=int(template_id))

    total_count = qs.count()
    paginator = Paginator(qs, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    template_choices = documents_scope(DocumentTemplate.objects.all(), request).order_by("name")

    return render(
        request,
        "documents/document_authoring/template_section/list.html",
        {
            "sections": page_obj,
            "page_obj": page_obj,
            "search_query": q,
            "section_type_choices": TemplateSection.SECTION_TYPE_CHOICES,
            "template_choices": template_choices,
            "total_count": total_count,
        },
    )


@login_required
def template_section_detail(request, pk):
    section = documents_object(request, TemplateSection, pk, select_related=("template",))
    return render(
        request,
        "documents/document_authoring/template_section/detail.html",
        {
            "section": section,
        },
    )


@login_required
def template_section_create(request):
    initial = {}
    template_id = request.GET.get("template")
    if template_id and template_id.isdigit():
        initial["template"] = int(template_id)

    if request.method == "POST":
        form = TemplateSectionForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                section = form.save(commit=False)
                section.tenant = request.tenant
                section.save()
                write_audit_log(request.user, section, "create", tenant=request.tenant)
            messages.success(request, f"Template section '{section.title}' created successfully.")
            if section.template:
                return redirect("documents:template_detail", pk=section.template.pk)
            return redirect("documents:template_section_detail", pk=section.pk)
    else:
        form = TemplateSectionForm(initial=initial, tenant=request.tenant)

    return render(
        request,
        "documents/document_authoring/template_section/form.html",
        {
            "form": form,
            "is_edit": False,
        },
    )


@login_required
def template_section_edit(request, pk):
    section = documents_object(request, TemplateSection, pk)
    if request.method == "POST":
        form = TemplateSectionForm(request.POST, instance=section, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                section = form.save()
                write_audit_log(request.user, section, "edit", tenant=request.tenant)
            messages.success(request, f"Template section '{section.title}' updated successfully.")
            return redirect("documents:template_section_detail", pk=section.pk)
    else:
        form = TemplateSectionForm(instance=section, tenant=request.tenant)

    return render(
        request,
        "documents/document_authoring/template_section/form.html",
        {
            "form": form,
            "section": section,
            "is_edit": True,
        },
    )


@login_required
@require_POST
def template_section_delete(request, pk):
    section = documents_object(request, TemplateSection, pk)
    title = section.title
    parent_template_pk = section.template_id
    with transaction.atomic():
        write_audit_log(request.user, section, "delete", tenant=request.tenant)
        section.delete()
    messages.success(request, f"Template section '{title}' deleted successfully.")
    if parent_template_pk:
        return redirect("documents:template_detail", pk=parent_template_pk)
    return redirect("documents:template_section_list")
