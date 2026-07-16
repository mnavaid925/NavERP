"""HRM 3.23 Learning Management (LMS) — Learningpath views (split from apps/hrm/views.py)."""
from apps.hrm.views._common import *  # noqa: F401,F403
from apps.hrm.views._helpers import *  # noqa: F401,F403
from apps.hrm.models import (
    Designation,
    LearningPath,
)
from apps.hrm.forms import (
    LearningPathForm,
)


# ------------------------------------------------------------ LearningPath (3.23 Learning Paths)
@login_required
def learningpath_list(request):
    qs = (LearningPath.objects.filter(tenant=request.tenant)
          .select_related("target_designation", "target_department")
          .annotate(item_count=Count("items", distinct=True)))
    return crud_list(
        request, qs.order_by("title"),
        "hrm/lms/learningpath/list.html",
        search_fields=("number", "title", "description"),
        filters=[("is_mandatory", "is_mandatory", False), ("is_active", "is_active", False),
                 ("target_designation", "target_designation_id", True),
                 ("target_department", "target_department_id", True)],
        extra_context={
            "designations": Designation.objects.filter(tenant=request.tenant).order_by("name"),
            "departments": OrgUnit.objects.filter(tenant=request.tenant, kind="department").order_by("name"),
        },
    )


@login_required
def learningpath_create(request):
    return crud_create(request, form_class=LearningPathForm,
                       template="hrm/lms/learningpath/form.html", success_url="hrm:learningpath_list")


@login_required
def learningpath_detail(request, pk):
    obj = get_object_or_404(
        LearningPath.objects.select_related("target_designation", "target_department"),
        pk=pk, tenant=request.tenant)
    items = obj.items.select_related("course").order_by("sequence")
    return render(request, "hrm/lms/learningpath/detail.html", {"obj": obj, "items": items})


@login_required
def learningpath_edit(request, pk):
    return crud_edit(request, model=LearningPath, pk=pk, form_class=LearningPathForm,
                     template="hrm/lms/learningpath/form.html", success_url="hrm:learningpath_list")


@login_required
@require_POST
def learningpath_delete(request, pk):
    # LearningPathItem.path is CASCADE (items die with the path); LearningProgress.learning_path is
    # SET_NULL — so no ProtectedError concern here, plain crud_delete is safe.
    return crud_delete(request, model=LearningPath, pk=pk, success_url="hrm:learningpath_list")
