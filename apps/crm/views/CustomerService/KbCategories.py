"""CRM 1.4 Customer Service & Support — KbCategories views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    KbCategory,
    KnowledgeArticle,
)
from apps.crm.forms import (
    KbCategoryForm,
)


# ------------------------------------------------------------ KB categories (1.4)
@login_required
def kbcategory_list(request):
    return crud_list(
        request,
        KbCategory.objects.filter(tenant=request.tenant).select_related("parent").defer("description", "slug"),
        "crm/service/kbcategory/list.html",
        search_fields=["number", "name"],
        filters=[("is_active", "is_active", False)],
        extra_context={},
    )


@login_required
def kbcategory_create(request):
    return crud_create(request, form_class=KbCategoryForm, template="crm/service/kbcategory/form.html",
                       success_url="crm:kbcategory_list")


@login_required
def kbcategory_detail(request, pk):
    obj = get_object_or_404(KbCategory.objects.select_related("parent"), pk=pk, tenant=request.tenant)
    return render(request, "crm/service/kbcategory/detail.html", {
        "obj": obj,
        "children": KbCategory.objects.filter(
            tenant=request.tenant, parent=obj).only("pk", "number", "name", "order"),
        "articles": KnowledgeArticle.objects.filter(
            tenant=request.tenant, kb_category=obj).only("pk", "number", "title", "status")[:50],
    })


@login_required
def kbcategory_edit(request, pk):
    return crud_edit(request, model=KbCategory, pk=pk, form_class=KbCategoryForm,
                     template="crm/service/kbcategory/form.html", success_url="crm:kbcategory_list")


@login_required
@require_POST
def kbcategory_delete(request, pk):
    return crud_delete(request, model=KbCategory, pk=pk, success_url="crm:kbcategory_list")
