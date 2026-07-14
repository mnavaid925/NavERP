"""CRM 1.5 Activity & Communication Management — Tasks models (split from apps/crm/models.py)."""
from apps.crm.models._base import *  # noqa: F401,F403


class CrmTask(TenantNumbered):
    """A to-do / call / follow-up (1.5). ``completed_at`` is system-set on done. Recurring tasks
    spawn the next open occurrence when completed (see ``_spawn_next_occurrence``)."""

    NUMBER_PREFIX = "TASK"

    TYPE_CHOICES = [
        ("todo", "To-Do"),
        ("call", "Call"),
        ("email", "Email"),
        ("meeting", "Meeting"),
        ("follow_up", "Follow-Up"),
    ]
    PRIORITY_CHOICES = [("low", "Low"), ("medium", "Medium"), ("high", "High")]
    STATUS_CHOICES = [
        ("open", "Open"),
        ("in_progress", "In Progress"),
        ("done", "Done"),
        ("cancelled", "Cancelled"),
    ]
    RECURRENCE_CHOICES = [
        ("none", "Does Not Repeat"),
        ("daily", "Daily"),
        ("weekly", "Weekly"),
        ("monthly", "Monthly"),
    ]
    OPEN_STATUSES = ["open", "in_progress"]

    subject = models.CharField(max_length=255)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="todo")
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default="medium")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    due_date = models.DateField(null=True, blank=True)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_tasks")
    party = models.ForeignKey("core.Party", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_tasks")
    related_opportunity = models.ForeignKey("crm.Opportunity", on_delete=models.SET_NULL, null=True, blank=True, related_name="tasks")
    related_case = models.ForeignKey("crm.Case", on_delete=models.SET_NULL, null=True, blank=True, related_name="crm_tasks")
    description = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)  # system-set
    # ---- Automated recurring tasks (1.5) ----------------------------------------------------
    recurrence = models.CharField(max_length=10, choices=RECURRENCE_CHOICES, default="none")
    recurrence_interval = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])  # "every N"
    recurrence_until = models.DateField(null=True, blank=True)  # optional series end date
    # System-set: links a spawned occurrence back to the series origin (never on the form).
    recurrence_parent = models.ForeignKey("self", on_delete=models.SET_NULL, null=True, blank=True, related_name="recurrence_children")

    class Meta:
        ordering = ["due_date", "-created_at"]
        unique_together = ("tenant", "number")
        indexes = [
            models.Index(fields=["tenant", "status"], name="crm_task_tenant_status_idx"),
            models.Index(fields=["tenant", "due_date", "created_at"], name="crm_task_tnt_due_created_idx"),
            # health scoring counts a party's tasks (tenant, party) on every recompute (perf-review).
            models.Index(fields=["tenant", "party"], name="crm_task_tnt_party_idx"),
        ]

    @property
    def is_overdue(self):
        return bool(self.due_date and self.status in self.OPEN_STATUSES
                    and self.due_date < timezone.localdate())

    def save(self, *args, **kwargs):
        # Detect the open→done transition (drives recurrence spawn) before writing.
        prev_status = (type(self).objects.filter(pk=self.pk)
                       .values_list("status", flat=True).first()) if self.pk else None
        # System-set completed_at: stamp when first marked done, clear if re-opened.
        if self.status == "done":
            if self.completed_at is None:
                self.completed_at = timezone.now()
        else:
            self.completed_at = None
        # Atomic: the parent write + the spawned next occurrence commit or roll back together,
        # so a failed spawn never leaves a completed task with a broken recurrence chain.
        with transaction.atomic():
            super().save(*args, **kwargs)
            # Automated recurring tasks: on the first transition into "done", spawn the next open
            # occurrence. The transition guard (prev != done) prevents double-spawn on re-save and
            # stops the spawned open child from recursing.
            if (self.status == "done" and prev_status != "done"
                    and self.recurrence != "none" and self.due_date):
                self._spawn_next_occurrence()

    def _next_due(self):
        """Next occurrence's due date, advancing by ``recurrence_interval`` units. Stdlib only —
        python-dateutil is not installed, so monthly is computed with ``calendar.monthrange``."""
        n = self.recurrence_interval or 1
        if self.recurrence == "daily":
            return self.due_date + timedelta(days=n)
        if self.recurrence == "weekly":
            return self.due_date + timedelta(weeks=n)
        if self.recurrence == "monthly":
            idx = self.due_date.month - 1 + n
            year = self.due_date.year + idx // 12
            month = idx % 12 + 1
            day = min(self.due_date.day, calendar.monthrange(year, month)[1])  # clamp to month end
            return self.due_date.replace(year=year, month=month, day=day)
        return None

    def _spawn_next_occurrence(self):
        next_due = self._next_due()
        if next_due is None:
            return
        if self.recurrence_until and next_due > self.recurrence_until:
            return  # the series has ended
        origin = self.recurrence_parent or self
        # Idempotent: never create a duplicate occurrence at the same next due date. (self can't
        # match — its own due_date is the current value, not next_due — so no self-exclude needed.)
        if CrmTask.objects.filter(tenant=self.tenant, recurrence_parent=origin,
                                  due_date=next_due).exists():
            return
        CrmTask.objects.create(
            tenant=self.tenant, subject=self.subject, type=self.type,
            priority=self.priority, status="open", due_date=next_due,
            owner=self.owner, party=self.party,
            related_opportunity=self.related_opportunity, related_case=self.related_case,
            recurrence=self.recurrence, recurrence_interval=self.recurrence_interval,
            recurrence_until=self.recurrence_until, recurrence_parent=origin,
        )

    def __str__(self):
        return f"{self.number} · {self.subject}"
