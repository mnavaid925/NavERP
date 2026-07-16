"""HRM 3.36 Helpdesk — Knowledgearticle views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    HelpdeskCategory,
    KnowledgeArticle,
)
from apps.hrm.forms import (
    KnowledgeArticleForm,
)
from apps.hrm.views.PerformanceReview._helpers import _is_admin
# star-imports skip underscore names -> import the privates explicitly
from apps.hrm.views._common import _changed


# ---- Knowledge base (internal FAQ / self-help) ------------------------------------------------
@login_required
def knowledgearticle_list(request):
    is_admin = _is_admin(request.user)
    qs = KnowledgeArticle.objects.filter(tenant=request.tenant).select_related("category", "owner")
    # Non-admins get the self-help view: only PUBLISHED articles. Admins/authors see every status.
    if not is_admin:
        qs = qs.filter(status="published")
    return crud_list(request, qs, "hrm/helpdesk/knowledgearticle/list.html",
                     search_fields=["number", "title", "summary", "body", "tags"],
                     filters=[("status", "status", False), ("category", "category_id", True)],
                     extra_context={"is_admin": is_admin,
                                    "status_choices": KnowledgeArticle.STATUS_CHOICES,
                                    "categories": HelpdeskCategory.objects.filter(tenant=request.tenant)
                                    .order_by("department", "name")})


@tenant_admin_required
def knowledgearticle_create(request):
    if request.tenant is None:
        messages.error(request, "Select a tenant workspace before creating records.")
        return redirect("dashboard:home")
    if request.method == "POST":
        form = KnowledgeArticleForm(request.POST, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.tenant = request.tenant
            obj.owner = request.user
            if obj.status == "published" and obj.published_at is None:
                obj.published_at = timezone.now()
            obj.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, f"Article {obj.number} created.")
            return redirect("hrm:knowledgearticle_detail", pk=obj.pk)
    else:
        form = KnowledgeArticleForm(tenant=request.tenant)
    return render(request, "hrm/helpdesk/knowledgearticle/form.html", {"form": form, "is_edit": False})


@login_required
def knowledgearticle_detail(request, pk):
    obj = get_object_or_404(KnowledgeArticle.objects.select_related("category", "owner"),
                            pk=pk, tenant=request.tenant)
    is_admin = _is_admin(request.user)
    if obj.status != "published" and not is_admin:
        raise PermissionDenied("This article isn't published.")
    # Count a read with a cheap atomic increment (not audited).
    KnowledgeArticle.objects.filter(pk=obj.pk).update(view_count=F("view_count") + 1)
    obj.view_count += 1
    return render(request, "hrm/helpdesk/knowledgearticle/detail.html", {"obj": obj, "is_admin": is_admin})


@tenant_admin_required
def knowledgearticle_edit(request, pk):
    obj = get_object_or_404(KnowledgeArticle, pk=pk, tenant=request.tenant)
    if request.method == "POST":
        form = KnowledgeArticleForm(request.POST, instance=obj, tenant=request.tenant)
        if form.is_valid():
            obj = form.save(commit=False)
            if obj.status == "published" and obj.published_at is None:
                obj.published_at = timezone.now()
            obj.save()
            write_audit_log(request.user, obj, "update", changes=_changed(form))
            messages.success(request, "Article updated.")
            return redirect("hrm:knowledgearticle_detail", pk=obj.pk)
    else:
        form = KnowledgeArticleForm(instance=obj, tenant=request.tenant)
    return render(request, "hrm/helpdesk/knowledgearticle/form.html", {"form": form, "obj": obj, "is_edit": True})


@tenant_admin_required
@require_POST
def knowledgearticle_delete(request, pk):
    return crud_delete(request, model=KnowledgeArticle, pk=pk, success_url="hrm:knowledgearticle_list")


@login_required
@require_POST
def knowledgearticle_helpful(request, pk):
    """Any employee can mark a published article helpful (bumps the counter; internal deflection metric)."""
    obj = get_object_or_404(KnowledgeArticle, pk=pk, tenant=request.tenant)
    if obj.status != "published" and not _is_admin(request.user):
        raise PermissionDenied("This article isn't published.")
    KnowledgeArticle.objects.filter(pk=obj.pk).update(helpful_count=F("helpful_count") + 1)
    messages.success(request, "Thanks for the feedback!")
    return redirect("hrm:knowledgearticle_detail", pk=obj.pk)
