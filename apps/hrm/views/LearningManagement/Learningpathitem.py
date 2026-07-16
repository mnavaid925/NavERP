"""HRM 3.23 Learning Management (LMS) — Learningpathitem views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    LearningPath,
    LearningPathItem,
    TrainingCourse,
)
from apps.hrm.forms import (
    LearningPathItemForm,
)


# ------------------------------------------------------------ LearningPathItem (nested under a path)
@login_required
def learningpathitem_create(request, path_pk):
    path = get_object_or_404(LearningPath, pk=path_pk, tenant=request.tenant)
    if request.method == "POST":
        form = LearningPathItemForm(
            request.POST, instance=LearningPathItem(tenant=request.tenant, path=path), tenant=request.tenant)
        if form.is_valid():
            obj = form.save()
            write_audit_log(request.user, obj, "create")
            messages.success(request, "Course added to the path.")
            return redirect("hrm:learningpath_detail", pk=path.pk)
    else:
        form = LearningPathItemForm(
            instance=LearningPathItem(tenant=request.tenant, path=path), tenant=request.tenant)
    return render(request, "hrm/lms/learningpathitem/form.html",
                  {"form": form, "is_edit": False, "path": path})


@login_required
def learningpathitem_list(request):
    qs = LearningPathItem.objects.filter(tenant=request.tenant).select_related("path", "course")
    return crud_list(
        request, qs.order_by("path", "sequence"),
        "hrm/lms/learningpathitem/list.html",
        search_fields=("path__title", "course__title"),
        filters=[("path", "path_id", True), ("course", "course_id", True),
                 ("is_mandatory", "is_mandatory", False)],
        extra_context={
            "paths": LearningPath.objects.filter(tenant=request.tenant).order_by("title"),
            "courses": TrainingCourse.objects.filter(tenant=request.tenant).order_by("title"),
        },
    )


@login_required
def learningpathitem_detail(request, pk):
    # course__prerequisite_course: the detail template shows the course's prerequisite title (2nd FK hop).
    return crud_detail(request, model=LearningPathItem, pk=pk,
                       template="hrm/lms/learningpathitem/detail.html",
                       select_related=("path", "course", "course__prerequisite_course"))


@login_required
def learningpathitem_edit(request, pk):
    return crud_edit(request, model=LearningPathItem, pk=pk, form_class=LearningPathItemForm,
                     template="hrm/lms/learningpathitem/form.html", success_url="hrm:learningpathitem_list")


@login_required
@require_POST
def learningpathitem_delete(request, pk):
    item = get_object_or_404(LearningPathItem, pk=pk, tenant=request.tenant)
    path_id = item.path_id
    write_audit_log(request.user, item, "delete")
    item.delete()
    messages.success(request, "Course removed from the path.")
    return redirect("hrm:learningpath_detail", pk=path_id)
