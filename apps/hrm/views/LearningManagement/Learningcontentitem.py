"""HRM 3.23 Learning Management (LMS) — Learningcontentitem views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    LearningContentItem,
    TrainingCourse,
)
from apps.hrm.forms import (
    LearningContentItemForm,
)


# ------------------------------------------------------------ LearningContentItem (3.23 Course Content)
@login_required
def learningcontentitem_create(request, course_pk):
    """Nested under a course (mirrors pipcheckin_create) — tenant+course set on the instance BEFORE
    validation, so no crud_create tenant-timing gotcha. Redirects to the course so the lesson shows."""
    course = get_object_or_404(TrainingCourse, pk=course_pk, tenant=request.tenant)
    if request.method == "POST":
        form = LearningContentItemForm(
            request.POST, request.FILES,
            instance=LearningContentItem(tenant=request.tenant, course=course), tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, "Content added.")
            return redirect("hrm:trainingcourse_detail", pk=course.pk)
    else:
        form = LearningContentItemForm(
            instance=LearningContentItem(tenant=request.tenant, course=course), tenant=request.tenant)
    return render(request, "hrm/lms/learningcontentitem/form.html",
                  {"form": form, "is_edit": False, "course": course})


@login_required
def learningcontentitem_list(request):
    qs = LearningContentItem.objects.filter(tenant=request.tenant).select_related("course")
    return crud_list(
        request, qs.order_by("course", "sequence"),
        "hrm/lms/learningcontentitem/list.html",
        search_fields=("title", "description", "course__title"),
        filters=[("content_type", "content_type", False), ("course", "course_id", True),
                 ("is_required", "is_required", False)],
        extra_context={
            "content_type_choices": LearningContentItem.CONTENT_TYPE_CHOICES,
            "courses": TrainingCourse.objects.filter(tenant=request.tenant).order_by("title"),
        },
    )


@login_required
def learningcontentitem_detail(request, pk):
    return crud_detail(request, model=LearningContentItem, pk=pk,
                       template="hrm/lms/learningcontentitem/detail.html", select_related=("course",))


@login_required
def learningcontentitem_edit(request, pk):
    return crud_edit(request, model=LearningContentItem, pk=pk, form_class=LearningContentItemForm,
                     template="hrm/lms/learningcontentitem/form.html",
                     success_url="hrm:learningcontentitem_list")


@login_required
@require_POST
def learningcontentitem_delete(request, pk):
    return crud_delete(request, model=LearningContentItem, pk=pk, success_url="hrm:learningcontentitem_list")
