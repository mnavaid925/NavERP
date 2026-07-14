"""CRM 1.4 Customer Service & Support — PublicPages views (split from apps/crm/views.py)."""
from apps.crm.views._common import *  # noqa: F401,F403
from apps.crm.models import (
    Case,
    CaseComment,
    KnowledgeArticle,
)
from apps.crm.forms import (
    PublicCommentForm,
    PublicSatisfactionForm,
)


# ------------------------------------------------------------ Public help-desk pages (1.4, no login)
def case_public(request, token):
    """Public case-status tracking page — no login; the unguessable token is the bearer credential.
    Shows status/SLA + PUBLIC comments only (internal notes never leak) and lets the customer post a
    reply or a CSAT rating. CSRF-protected via the template tag; tenant taken from the case itself.
    # WARNING: unauthenticated POST — add per-IP rate-limiting (django-ratelimit) or a WAF throttle
    # in production to stop public comment floods."""
    case = get_object_or_404(
        Case.objects.select_related("sla_policy", "owner", "contact"), public_token=token)
    sat_form = PublicSatisfactionForm()
    comment_form = PublicCommentForm()
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "comment":
            comment_form = PublicCommentForm(request.POST)
            if comment_form.is_valid():
                CaseComment.objects.create(
                    tenant=case.tenant, case=case, author=None,
                    author_name=(case.contact.name if case.contact else "Customer"),
                    body=comment_form.cleaned_data["body"], is_public=True)
                return redirect("crm:case_public", token=token)
        elif action == "satisfaction" and case.satisfaction_rating is None:  # CSAT submitted once
            sat_form = PublicSatisfactionForm(request.POST)
            if sat_form.is_valid():
                # Atomic guard — a concurrent second submit updates 0 rows (can't overwrite the
                # rating); mirrors the first_responded_at claim, no TOCTOU race.
                Case.objects.filter(pk=case.pk, satisfaction_rating__isnull=True).update(
                    satisfaction_rating=int(sat_form.cleaned_data["rating"]),
                    satisfaction_comment=sat_form.cleaned_data["comment"],
                    satisfaction_at=timezone.now(), updated_at=timezone.now())
                return redirect("crm:case_public", token=token)
    return render(request, "crm/service/case_public.html", {
        "case": case,
        "comments": CaseComment.objects.filter(
            tenant=case.tenant, case=case, is_public=True).select_related("author"),
        "sat_form": sat_form, "comment_form": comment_form,
    })


def kb_public(request, token):
    """Public KB article page — no login; only a published + external article resolves (drafts and
    internal articles → 404). Counts a view via an atomic F() bump."""
    article = get_object_or_404(
        KnowledgeArticle.objects.select_related("kb_category"),
        public_token=token, status="published", visibility="external")
    KnowledgeArticle.objects.filter(pk=article.pk).update(views_count=F("views_count") + 1)
    return render(request, "crm/service/kb_public.html", {"article": article})


@require_POST
def kb_helpful(request, token):
    """Public helpful/not-helpful vote on a KB article (CSRF-protected, F() increment).
    # WARNING: unauthenticated — add per-IP rate-limiting in production to prevent vote stuffing."""
    article = get_object_or_404(
        KnowledgeArticle, public_token=token, status="published", visibility="external")
    vote = request.POST.get("vote")
    if vote == "yes":
        KnowledgeArticle.objects.filter(pk=article.pk).update(helpful_count=F("helpful_count") + 1)
    elif vote == "no":
        KnowledgeArticle.objects.filter(pk=article.pk).update(not_helpful_count=F("not_helpful_count") + 1)
    return redirect("crm:kb_public", token=token)
