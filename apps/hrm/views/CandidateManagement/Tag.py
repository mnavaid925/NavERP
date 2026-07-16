"""HRM 3.6 Candidate Management — Tag views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    CandidateTag,
)
from apps.hrm.forms import (
    CandidateTagForm,
)


# --------------------------------------------------------------- Candidate Tags (3.6)
@login_required
def candidatetag_list(request):
    return crud_list(
        request, CandidateTag.objects.filter(tenant=request.tenant)
        .annotate(candidate_count=Count("candidates", distinct=True)).order_by("name"),
        "hrm/candidates/tag/list.html",
        search_fields=["name", "description"])


@login_required
def candidatetag_create(request):
    return crud_create(request, form_class=CandidateTagForm, template="hrm/candidates/tag/form.html",
                       success_url="hrm:candidatetag_list")


@login_required
def candidatetag_edit(request, pk):
    return crud_edit(request, model=CandidateTag, pk=pk, form_class=CandidateTagForm,
                     template="hrm/candidates/tag/form.html", success_url="hrm:candidatetag_list")


@login_required
@require_POST
def candidatetag_delete(request, pk):
    return crud_delete(request, model=CandidateTag, pk=pk, success_url="hrm:candidatetag_list")
