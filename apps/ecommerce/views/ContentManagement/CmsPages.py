from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.ContentManagement.CmsPages import CmsPageForm
from apps.ecommerce.models.ContentManagement.CmsPages import CmsPage
from apps.ecommerce.views._common import ecommerce_object


@login_required
def cmspage_list(request):
    qs = CmsPage.objects.filter(tenant=request.tenant).defer("raw_html_body", "content_json")

    search_query = request.GET.get("q", "").strip()
    if search_query:
        qs = qs.filter(
            Q(title__icontains=search_query)
            | Q(slug__icontains=search_query)
            | Q(number__icontains=search_query)
            | Q(meta_title__icontains=search_query)
        )

    selected_type = request.GET.get("page_type", "").strip()
    if selected_type:
        qs = qs.filter(page_type=selected_type)

    selected_status = request.GET.get("status", "").strip()
    if selected_status:
        qs = qs.filter(status=selected_status)

    selected_layout = request.GET.get("template_layout", "").strip()
    if selected_layout:
        qs = qs.filter(template_layout=selected_layout)

    paginator = Paginator(qs, 20)
    page_number = request.GET.get("page")
    pages = paginator.get_page(page_number)

    return render(
        request,
        "ecommerce/content_management/page/list.html",
        {
            "pages": pages,
            "page_type_choices": CmsPage.PAGE_TYPE_CHOICES,
            "status_choices": CmsPage.STATUS_CHOICES,
            "layout_choices": CmsPage.LAYOUT_CHOICES,
            "selected_type": selected_type,
            "selected_status": selected_status,
            "selected_layout": selected_layout,
            "search_query": search_query,
        },
    )


@login_required
def cmspage_detail(request, pk):
    page = ecommerce_object(request, CmsPage, pk)
    return render(
        request,
        "ecommerce/content_management/page/detail.html",
        {"page": page},
    )


@login_required
def cmspage_create(request):
    if request.method == "POST":
        form = CmsPageForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            page = form.save()
            write_audit_log(
                request.user,
                page,
                "create",
                {"title": page.title, "slug": page.slug, "status": page.status},
                tenant=request.tenant,
            )
            messages.success(request, f"CMS Page '{page.title}' created successfully.")
            return redirect("ecommerce:cmspage_detail", pk=page.pk)
    else:
        form = CmsPageForm(tenant=request.tenant)

    return render(
        request,
        "ecommerce/content_management/page/form.html",
        {"form": form, "page": None},
    )


@login_required
def cmspage_edit(request, pk):
    page = ecommerce_object(request, CmsPage, pk)
    if request.method == "POST":
        form = CmsPageForm(request.POST, instance=page, tenant=request.tenant)
        if form.is_valid():
            page = form.save()
            write_audit_log(
                request.user,
                page,
                "update",
                {"title": page.title, "status": page.status},
                tenant=request.tenant,
            )
            messages.success(request, f"CMS Page '{page.title}' updated successfully.")
            return redirect("ecommerce:cmspage_detail", pk=page.pk)
    else:
        form = CmsPageForm(instance=page, tenant=request.tenant)

    return render(
        request,
        "ecommerce/content_management/page/form.html",
        {"form": form, "page": page},
    )


@login_required
@tenant_admin_required
@require_POST
def cmspage_delete(request, pk):
    page = ecommerce_object(request, CmsPage, pk)
    title = page.title
    number = page.number
    write_audit_log(
        request.user,
        page,
        "delete",
        {"number": number, "title": title},
        tenant=request.tenant,
    )
    page.delete()
    messages.success(request, f"CMS Page '{title}' deleted.")
    return redirect("ecommerce:cmspage_list")


@login_required
def cmspage_preview(request, pk):
    page = ecommerce_object(request, CmsPage, pk)
    return render(
        request,
        "ecommerce/content_management/page/detail.html",
        {"page": page, "is_preview": True},
    )
