"""HRM 3.19 Performance Review — Reviewtemplate views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    ReviewTemplate,
)
from apps.hrm.forms import (
    ReviewTemplateForm,
)


# ------------------------------------------------------- ReviewTemplate (3.19.3/3.19.4 form definition)
@login_required
def reviewtemplate_list(request):
    return crud_list(
        request,
        ReviewTemplate.objects.filter(tenant=request.tenant),
        "hrm/performance/reviewtemplate/list.html",
        search_fields=("name", "number"),
        filters=[("review_type", "review_type", False), ("is_active", "is_active", False)],
        extra_context={"review_type_choices": ReviewTemplate.REVIEW_TYPE_CHOICES},
    )


@login_required
def reviewtemplate_create(request):
    return crud_create(request, form_class=ReviewTemplateForm,
                       template="hrm/performance/reviewtemplate/form.html",
                       success_url="hrm:reviewtemplate_list")


@login_required
def reviewtemplate_detail(request, pk):
    return crud_detail(request, model=ReviewTemplate, pk=pk,
                       template="hrm/performance/reviewtemplate/detail.html")


@login_required
def reviewtemplate_edit(request, pk):
    return crud_edit(request, model=ReviewTemplate, pk=pk, form_class=ReviewTemplateForm,
                     template="hrm/performance/reviewtemplate/form.html",
                     success_url="hrm:reviewtemplate_list")


@login_required
@require_POST
def reviewtemplate_delete(request, pk):
    # template is SET_NULL on PerformanceReview — delete succeeds (historical reviews keep their
    # data, just lose the template link). No pre-check needed.
    return crud_delete(request, model=ReviewTemplate, pk=pk, success_url="hrm:reviewtemplate_list")
