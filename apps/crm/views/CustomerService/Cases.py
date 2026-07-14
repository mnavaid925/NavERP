"""CRM 1.4 Customer Service & Support — Cases views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    Case,
    CaseComment,
)
from apps.crm.forms import (
    CaseCommentForm,
    CaseForm,
)


# ============================================================ Cases / Tickets (1.4)
@login_required
def case_list(request):
    return crud_list(
        request,
        Case.objects.filter(tenant=request.tenant).select_related("account", "owner").defer(
            "description", "satisfaction_comment"),  # large TextFields not shown on the list
        "crm/service/case/list.html",
        search_fields=["subject", "number"],
        filters=[("status", "status", False), ("priority", "priority", False), ("type", "type", False)],
        extra_context={"status_choices": Case.STATUS_CHOICES,
                       "priority_choices": Case.PRIORITY_CHOICES,
                       "type_choices": Case.TYPE_CHOICES},
    )


@login_required
def case_create(request):
    return crud_create(request, form_class=CaseForm, template="crm/service/case/form.html",
                       success_url="crm:case_list")


@login_required
def case_detail(request, pk):
    obj = get_object_or_404(
        Case.objects.select_related("account", "contact", "owner", "sla_policy"),
        pk=pk, tenant=request.tenant)
    return render(request, "crm/service/case/detail.html", {
        "obj": obj,
        "comments": CaseComment.objects.filter(
            tenant=request.tenant, case=obj).select_related("author"),
        "comment_form": CaseCommentForm(tenant=request.tenant),
    })


@login_required
def case_edit(request, pk):
    return crud_edit(request, model=Case, pk=pk, form_class=CaseForm,
                     template="crm/service/case/form.html", success_url="crm:case_list")


@login_required
@require_POST
def case_delete(request, pk):
    return crud_delete(request, model=Case, pk=pk, success_url="crm:case_list")


@login_required
@require_POST
def case_comment_add(request, pk):
    """Add a reply/note to a case's conversation thread. The first PUBLIC agent reply stamps
    the SLA first-response clock (``first_responded_at``)."""
    case = get_object_or_404(Case, pk=pk, tenant=request.tenant)
    form = CaseCommentForm(request.POST, tenant=request.tenant)
    if not form.is_valid():
        messages.error(request, "A comment body is required.")
        return redirect("crm:case_detail", pk=case.pk)
    comment = form.save(commit=False)
    comment.tenant = request.tenant
    comment.case = case
    comment.author = request.user
    comment.author_name = request.user.get_full_name() or request.user.username
    with transaction.atomic():
        comment.save()
        if comment.is_public:
            # Atomic claim — only the first public reply stamps the SLA first-response clock
            # (no read-check-write race between two agents replying concurrently).
            Case.objects.filter(pk=case.pk, first_responded_at__isnull=True).update(
                first_responded_at=timezone.now(), updated_at=timezone.now())
    messages.success(request, "Comment added.")
    return redirect("crm:case_detail", pk=case.pk)
