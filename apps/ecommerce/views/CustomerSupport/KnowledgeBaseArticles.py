from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import F, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.decorators import tenant_admin_required
from apps.core.utils import write_audit_log
from apps.ecommerce.forms.CustomerSupport.KnowledgeBaseArticles import KnowledgeBaseArticleForm
from apps.ecommerce.models.CustomerSupport.KnowledgeBaseArticles import KnowledgeBaseArticle
from apps.ecommerce.views._common import ecommerce_object


@login_required
def knowledgebasearticle_list(request):
    qs = KnowledgeBaseArticle.objects.filter(tenant=request.tenant).select_related("author").defer("content")

    query = request.GET.get("q", "").strip()
    if query:
        qs = qs.filter(
            Q(title__icontains=query)
            | Q(summary__icontains=query)
            | Q(content__icontains=query)
            | Q(keywords__icontains=query)
            | Q(number__icontains=query)
        )

    selected_category = request.GET.get("category", "").strip()
    if selected_category:
        qs = qs.filter(category=selected_category)

    selected_status = request.GET.get("status", "").strip()
    if selected_status:
        qs = qs.filter(status=selected_status)

    selected_audience = request.GET.get("audience", "").strip()
    if selected_audience:
        qs = qs.filter(target_audience=selected_audience)

    paginator = Paginator(qs, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "articles": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "category_choices": KnowledgeBaseArticle.CATEGORY_CHOICES,
        "status_choices": KnowledgeBaseArticle.STATUS_CHOICES,
        "audience_choices": KnowledgeBaseArticle.AUDIENCE_CHOICES,
        "selected_category": selected_category,
        "selected_status": selected_status,
        "selected_audience": selected_audience,
        "query": query,
    }
    return render(request, "ecommerce/customer_support/article/list.html", context)


@login_required
def knowledgebasearticle_detail(request, pk):
    article = ecommerce_object(request, KnowledgeBaseArticle, pk, select_related=("author",))
    # Increment view count
    KnowledgeBaseArticle.objects.filter(pk=article.pk, tenant=request.tenant).update(view_count=F("view_count") + 1)
    article.view_count += 1
    return render(request, "ecommerce/customer_support/article/detail.html", {"article": article})


@login_required
def knowledgebasearticle_create(request):
    if request.method == "POST":
        form = KnowledgeBaseArticleForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            article = form.save(commit=False)
            article.tenant = request.tenant
            if not article.author and request.user.is_authenticated:
                article.author = request.user
            article.save()
            write_audit_log(
                request.user,
                article,
                "create",
                {"number": article.number, "title": article.title, "category": article.category},
                tenant=request.tenant,
            )
            messages.success(request, f"Knowledge Base article {article.number} published successfully.")
            return redirect("ecommerce:knowledgebasearticle_detail", pk=article.pk)
    else:
        form = KnowledgeBaseArticleForm(tenant=request.tenant)

    return render(
        request,
        "ecommerce/customer_support/article/form.html",
        {"form": form, "article": None},
    )


@login_required
def knowledgebasearticle_edit(request, pk):
    article = ecommerce_object(request, KnowledgeBaseArticle, pk)
    if request.method == "POST":
        form = KnowledgeBaseArticleForm(request.POST, instance=article, tenant=request.tenant)
        if form.is_valid():
            article = form.save()
            write_audit_log(
                request.user,
                article,
                "update",
                {"title": article.title, "status": article.status},
                tenant=request.tenant,
            )
            messages.success(request, f"Article {article.number} updated successfully.")
            return redirect("ecommerce:knowledgebasearticle_detail", pk=article.pk)
    else:
        form = KnowledgeBaseArticleForm(instance=article, tenant=request.tenant)

    return render(
        request,
        "ecommerce/customer_support/article/form.html",
        {"form": form, "article": article},
    )


@login_required
@tenant_admin_required
@require_POST
def knowledgebasearticle_delete(request, pk):
    article = ecommerce_object(request, KnowledgeBaseArticle, pk)
    number = article.number
    write_audit_log(
        request.user,
        article,
        "delete",
        {"number": number},
        tenant=request.tenant,
    )
    article.delete()
    messages.success(request, f"Article {number} deleted.")
    return redirect("ecommerce:knowledgebasearticle_list")
