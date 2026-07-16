"""HRM 3.36 Helpdesk — Helpdeskcategory views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    HelpdeskCategory,
    HelpdeskTicket,
    KnowledgeArticle,
)
from apps.hrm.forms import (
    HelpdeskCategoryForm,
)
from apps.hrm.views.PerformanceReview._helpers import _is_admin


# ---- Helpdesk categories (admin-managed routing + KB taxonomy) --------------------------------
@login_required
def helpdeskcategory_list(request):
    qs = (HelpdeskCategory.objects.filter(tenant=request.tenant)
          .select_related("default_assignee", "default_sla_policy"))
    return crud_list(request, qs, "hrm/helpdesk/helpdeskcategory/list.html",
                     search_fields=["name", "description"],
                     filters=[("department", "department", False), ("is_active", "is_active", False)],
                     extra_context={"is_admin": _is_admin(request.user),
                                    "department_choices": HelpdeskCategory.DEPARTMENT_CHOICES})


@tenant_admin_required
def helpdeskcategory_create(request):
    return crud_create(request, form_class=HelpdeskCategoryForm,
                       template="hrm/helpdesk/helpdeskcategory/form.html", success_url="hrm:helpdeskcategory_list")


@login_required
def helpdeskcategory_detail(request, pk):
    return crud_detail(request, model=HelpdeskCategory, pk=pk,
                       template="hrm/helpdesk/helpdeskcategory/detail.html",
                       select_related=("default_assignee", "default_sla_policy"),
                       extra_context={"is_admin": _is_admin(request.user),
                                      "ticket_count": HelpdeskTicket.objects.filter(
                                          tenant=request.tenant, category_id=pk).count(),
                                      "article_count": KnowledgeArticle.objects.filter(
                                          tenant=request.tenant, category_id=pk).count()})


@tenant_admin_required
def helpdeskcategory_edit(request, pk):
    return crud_edit(request, model=HelpdeskCategory, pk=pk, form_class=HelpdeskCategoryForm,
                     template="hrm/helpdesk/helpdeskcategory/form.html", success_url="hrm:helpdeskcategory_list")


@tenant_admin_required
@require_POST
def helpdeskcategory_delete(request, pk):
    if HelpdeskTicket.objects.filter(tenant=request.tenant, category_id=pk).exists():
        messages.error(request, "This category is used by existing tickets and can't be deleted.")
        return redirect("hrm:helpdeskcategory_detail", pk=pk)
    return crud_delete(request, model=HelpdeskCategory, pk=pk, success_url="hrm:helpdeskcategory_list")
