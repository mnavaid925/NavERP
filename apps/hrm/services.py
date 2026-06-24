"""HRM domain services — request-free business logic shared by views, the seeder, and tests.

Keeping this out of ``views.py`` lets the management command (and tests) call it without importing
the view layer (a layering violation). Pure model logic only; no request/response coupling.
"""
from datetime import timedelta

from .models import OnboardingTask


def generate_tasks_from_template(program):
    """Create concrete ``OnboardingTask`` rows from the program's template task lines, each with
    ``due_date = program.start_date + due_offset_days``. Idempotent — ``get_or_create`` keyed on the
    task title means re-running never duplicates an existing task. Returns the count of newly-created
    tasks.

    NOTE (known limitation): renaming a template task after generation and re-running creates a new
    task rather than renaming the old one (the old title lingers). Acceptable for this pass — regen
    is meant to *add* newly-introduced template tasks, not reconcile renames.
    """
    if not program.template_id:
        return 0
    template_tasks = list(program.template.template_tasks.order_by("phase", "order", "title"))
    if not template_tasks:
        return 0
    # One SELECT for the titles already present, then one bulk INSERT — keeps the idempotency
    # contract (title-keyed) while avoiding the 2N queries a per-row get_or_create would run.
    existing = set(OnboardingTask.objects.filter(tenant=program.tenant, program=program)
                   .values_list("title", flat=True))
    to_create = []
    for tt in template_tasks:
        if tt.title in existing:
            continue
        due = program.start_date + timedelta(days=tt.due_offset_days) if program.start_date else None
        to_create.append(OnboardingTask(
            tenant=program.tenant, program=program, title=tt.title,
            description=tt.description, task_category=tt.task_category,
            assignee_role=tt.assignee_role, due_date=due, phase=tt.phase,
            is_mandatory=tt.is_mandatory, order=tt.order))
    if to_create:
        OnboardingTask.objects.bulk_create(to_create)
    return len(to_create)
