from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.core.utils import write_audit_log
from apps.documents.forms.DocumentAuthoring.DocumentTemplates import DocumentTemplateForm
from apps.documents.models.DocumentAuthoring.DocumentTemplates import DocumentTemplate
from apps.documents.views._common import documents_object, documents_scope
from apps.documents.views._helpers import count_words


@login_required
def template_list(request):
    qs = documents_scope(DocumentTemplate.objects.defer("content"), request)

    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(number__icontains=q) | Q(description__icontains=q))

    template_type = request.GET.get("template_type", "").strip()
    if template_type:
        qs = qs.filter(template_type=template_type)

    category = request.GET.get("category", "").strip()
    if category:
        qs = qs.filter(category=category)

    is_active = request.GET.get("is_active", "").strip()
    if is_active in ("1", "true", "True"):
        qs = qs.filter(is_active=True)
    elif is_active in ("0", "false", "False"):
        qs = qs.filter(is_active=False)

    paginator = Paginator(qs, 15)
    total_count = paginator.count
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "documents/document_authoring/document_template/list.html",
        {
            "templates": page_obj,
            "page_obj": page_obj,
            "search_query": q,
            "template_type_choices": DocumentTemplate.TEMPLATE_TYPE_CHOICES,
            "category_choices": DocumentTemplate.CATEGORY_CHOICES,
            "total_count": total_count,
        },
    )


@login_required
def template_detail(request, pk):
    template = documents_object(
        request,
        DocumentTemplate,
        pk,
        select_related=("target_org_unit", "owner"),
        prefetch_related=("sections",),
    )
    sections = template.sections.all()
    drafts_count = template.derived_drafts.count()

    return render(
        request,
        "documents/document_authoring/document_template/detail.html",
        {
            "template": template,
            "sections": sections,
            "drafts_count": drafts_count,
        },
    )


@login_required
def template_create(request):
    if request.method == "POST":
        form = DocumentTemplateForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                template = form.save(commit=False)
                template.tenant = request.tenant
                template.save()
                form.save_m2m()
                write_audit_log(request.user, template, "create", tenant=request.tenant)
            messages.success(request, f"Document template '{template.name}' created successfully.")
            return redirect("documents:template_detail", pk=template.pk)
    else:
        form = DocumentTemplateForm(tenant=request.tenant)

    return render(
        request,
        "documents/document_authoring/document_template/form.html",
        {
            "form": form,
            "is_edit": False,
        },
    )


@login_required
def template_edit(request, pk):
    template = documents_object(request, DocumentTemplate, pk)
    if template.is_locked and not (request.user.is_superuser or getattr(request.user, "is_tenant_admin", False) or getattr(request, "is_tenant_admin", False)):
        messages.error(request, f"Document template '{template.name}' is locked and can only be modified by an administrator.")
        return redirect("documents:template_detail", pk=template.pk)

    if request.method == "POST":
        form = DocumentTemplateForm(request.POST, instance=template, tenant=request.tenant)
        if form.is_valid():
            with transaction.atomic():
                template = form.save()
                write_audit_log(request.user, template, "edit", tenant=request.tenant)
            messages.success(request, f"Document template '{template.name}' updated successfully.")
            return redirect("documents:template_detail", pk=template.pk)
    else:
        form = DocumentTemplateForm(instance=template, tenant=request.tenant)

    return render(
        request,
        "documents/document_authoring/document_template/form.html",
        {
            "form": form,
            "template": template,
            "is_edit": True,
        },
    )


@login_required
@require_POST
def template_delete(request, pk):
    template = documents_object(request, DocumentTemplate, pk)
    if template.is_locked and not (request.user.is_superuser or getattr(request.user, "is_tenant_admin", False) or getattr(request, "is_tenant_admin", False)):
        messages.error(request, f"Document template '{template.name}' is locked and cannot be deleted.")
        return redirect("documents:template_detail", pk=template.pk)

    name = template.name
    with transaction.atomic():
        write_audit_log(request.user, template, "delete", tenant=request.tenant)
        template.delete()
    messages.success(request, f"Document template '{name}' deleted successfully.")
    return redirect("documents:template_list")


@login_required
@require_POST
def template_instantiate(request, pk):
    template = documents_object(request, DocumentTemplate, pk)
    from apps.documents.models.DocumentAuthoring.DocumentDrafts import DocumentDraft

    with transaction.atomic():
        draft = DocumentDraft(
            tenant=request.tenant,
            template=template,
            title=f"Draft: {template.name}",
            document_type=template.template_type if template.template_type in dict(DocumentDraft.DOCUMENT_TYPE_CHOICES) else "sop",
            content=template.content,
            word_count=count_words(template.content),
            status="draft",
            author=request.user,
            department=template.target_org_unit,
        )
        draft.save()
        write_audit_log(request.user, draft, "create", tenant=request.tenant)

    messages.success(request, f"Instantiated new working draft '{draft.title}' from template.")
    return redirect("documents:draft_detail", pk=draft.pk)
