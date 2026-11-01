from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.ContentManagement.BlogArticles import BlogArticleForm
from apps.ecommerce.models.ContentManagement.BlogArticles import BlogArticle
from apps.ecommerce.views._common import ecommerce_object


@login_required
def blogarticle_list(request):
    qs = BlogArticle.objects.filter(tenant=request.tenant).select_related("author", "featured_media")

    search_query = request.GET.get("q", "").strip()
    if search_query:
        qs = qs.filter(
            Q(title__icontains=search_query)
            | Q(slug__icontains=search_query)
            | Q(number__icontains=search_query)
            | Q(excerpt__icontains=search_query)
            | Q(tags__icontains=search_query)
        )

    selected_category = request.GET.get("category", "").strip()
    if selected_category:
        qs = qs.filter(category=selected_category)

    selected_status = request.GET.get("status", "").strip()
    if selected_status:
        qs = qs.filter(status=selected_status)

    paginator = Paginator(qs, 20)
    page_number = request.GET.get("page")
    articles = paginator.get_page(page_number)

    return render(
        request,
        "ecommerce/content_management/blog/list.html",
        {
            "articles": articles,
            "category_choices": BlogArticle.CATEGORY_CHOICES,
            "status_choices": BlogArticle.STATUS_CHOICES,
            "selected_category": selected_category,
            "selected_status": selected_status,
            "search_query": search_query,
        },
    )


@login_required
def blogarticle_detail(request, pk):
    article = ecommerce_object(request, BlogArticle, pk)
    return render(
        request,
        "ecommerce/content_management/blog/detail.html",
        {"article": article},
    )


@login_required
def blogarticle_create(request):
    if request.method == "POST":
        form = BlogArticleForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            article = form.save()
            write_audit_log(
                request.user,
                article,
                "create",
                {"title": article.title, "slug": article.slug, "status": article.status},
                tenant=request.tenant,
            )
            messages.success(request, f"Blog Article '{article.title}' created successfully.")
            return redirect("ecommerce:blogarticle_detail", pk=article.pk)
    else:
        form = BlogArticleForm(tenant=request.tenant)

    return render(
        request,
        "ecommerce/content_management/blog/form.html",
        {"form": form, "article": None},
    )


@login_required
def blogarticle_edit(request, pk):
    article = ecommerce_object(request, BlogArticle, pk)
    if request.method == "POST":
        form = BlogArticleForm(request.POST, instance=article, tenant=request.tenant)
        if form.is_valid():
            article = form.save()
            write_audit_log(
                request.user,
                article,
                "update",
                {"title": article.title, "status": article.status},
                tenant=request.tenant,
            )
            messages.success(request, f"Blog Article '{article.title}' updated successfully.")
            return redirect("ecommerce:blogarticle_detail", pk=article.pk)
    else:
        form = BlogArticleForm(instance=article, tenant=request.tenant)

    return render(
        request,
        "ecommerce/content_management/blog/form.html",
        {"form": form, "article": article},
    )


@login_required
@tenant_admin_required
@require_POST
def blogarticle_delete(request, pk):
    article = ecommerce_object(request, BlogArticle, pk)
    title = article.title
    number = article.number
    write_audit_log(
        request.user,
        article,
        "delete",
        {"number": number, "title": title},
        tenant=request.tenant,
    )
    article.delete()
    messages.success(request, f"Blog Article '{title}' deleted.")
    return redirect("ecommerce:blogarticle_list")
