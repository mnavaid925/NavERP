"""CRM 1.4 Customer Service & Support — KnowledgeBase views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    KbCategory,
    KnowledgeArticle,
)
from apps.crm.forms import (
    KnowledgeArticleForm,
)


# ====================================================== Knowledge Base / Solutions (1.4)
@login_required
def knowledgearticle_list(request):
    return crud_list(
        request,
        KnowledgeArticle.objects.filter(tenant=request.tenant).select_related("kb_category").defer("body"),
        "crm/service/knowledgearticle/list.html",
        search_fields=["title", "category", "number"],
        filters=[("status", "status", False), ("visibility", "visibility", False),
                 ("kb_category", "kb_category_id", True)],
        extra_context={"status_choices": KnowledgeArticle.STATUS_CHOICES,
                       "visibility_choices": KnowledgeArticle.VISIBILITY_CHOICES,
                       "categories": KbCategory.objects.filter(tenant=request.tenant).only("pk", "name", "number")},
    )


@login_required
def knowledgearticle_create(request):
    return crud_create(request, form_class=KnowledgeArticleForm,
                       template="crm/service/knowledgearticle/form.html",
                       success_url="crm:knowledgearticle_list")


@login_required
def knowledgearticle_detail(request, pk):
    # Count a view via an atomic F() update (tenant-scoped); bypasses save() so it neither
    # touches updated_at nor re-numbers.
    KnowledgeArticle.objects.filter(pk=pk, tenant=request.tenant).update(views_count=F("views_count") + 1)
    obj = get_object_or_404(KnowledgeArticle.objects.select_related("owner", "kb_category"),
                            pk=pk, tenant=request.tenant)
    return render(request, "crm/service/knowledgearticle/detail.html", {"obj": obj})


@login_required
def knowledgearticle_edit(request, pk):
    return crud_edit(request, model=KnowledgeArticle, pk=pk, form_class=KnowledgeArticleForm,
                     template="crm/service/knowledgearticle/form.html",
                     success_url="crm:knowledgearticle_list")


@login_required
@require_POST
def knowledgearticle_delete(request, pk):
    return crud_delete(request, model=KnowledgeArticle, pk=pk,
                       success_url="crm:knowledgearticle_list")
