"""Forms for 8.6's ASC 606 revenue register.

Two forms, and the split between them is the whole design of this entity.

``RevenueScheduleForm`` carries the six authorable fields of the SCHEDULE, and ``status`` is on
it — the single authorable ``status`` in 8.6, because a revenue schedule is drafted and voided
by a person rather than driven by a workflow verb. Its widget is narrowed to
``RevenueSchedule.STATUS_CHOICES`` explicitly, so a value outside the pinned list cannot be
authored even if the field's own choices were ever widened.

What is deliberately NOT on it, each for a reason that matters:

* ``tenant`` — set by ``TenantUniqueMixin`` from the view's ``request.tenant``, never from input.
* ``number`` — auto-numbered ``RVS-`` by ``TenantNumbered.save()``.
* ``journal_entry`` — **reference-only, ``editable=False``**. 8.6 posts NOTHING (L29). A form
  carrying it would let a clerk record that revenue was posted to the ledger when nothing was
  posted, and the L22 rule is that an account of a system event is written by the system.
* ``created_at`` / ``updated_at`` — auto_now* stamps.

``PerformanceObligationForm`` carries the nine authorable fields of one obligation and is
constructed with the parent as ``schedule=``, never from user input: the obligation belongs to
the schedule the URL named, and a form that let the POST body choose the parent would be a way
to append an obligation to somebody else's contract.

Two exclusion sets here are load-bearing rather than cosmetic, because of the 0.20 close-out
finding:

* this form does NOT carry ``schedule``, nor ``allocated_amount`` / ``recognized_amount``
  (``editable=False``), nor the timestamps. That is exactly why
  ``PerformanceObligation.clean()`` is keyed on ``NON_FIELD_ERRORS`` and nothing else — a guard
  keyed on an absent field routes through ``add_error(None, …)`` and raises ``ValueError``,
  500ing every create and edit.
* ``allocated_amount`` / ``recognized_amount`` are absent for the same reason on the SCHEDULE
  side: they are not on ``RevenueSchedule`` at all. The only two money columns in 8.6 live on
  the obligation and are written by ``RevenueSchedule.recompute()``.

Every FK queryset is narrowed to ``tenant=self.tenant``, and ``_reject_foreign()`` re-checks
the submitted values on top of that — a narrowed widget is a usability feature, not a security
boundary.
"""
from django import forms

from apps.sales.forms._common import TenantModelForm, TenantUniqueMixin, _reject_foreign
from apps.sales.models.OrderManagement.RevenueSchedules import (
    PerformanceObligation,
    RevenueSchedule,
)


class RevenueScheduleForm(TenantUniqueMixin, TenantModelForm):
    """Draft or amend one revenue schedule. The obligations are the verbs' job."""

    class Meta:
        model = RevenueSchedule
        # Excluded, with the reason for each:
        #   tenant         — set by the mixin from the view's request.tenant, never from input.
        #   number         — auto-numbered RVS- by TenantNumbered.save().
        #   journal_entry  — REFERENCE-ONLY, editable=False; 8.6 posts nothing (L29).
        #   created_at / updated_at — auto_now* stamps.
        fields = [
            "sales_order",
            "status",
            "method",
            "compliance_standard",
            "fiscal_period",
            "notes",
        ]
        widgets = {
            "sales_order": forms.Select(attrs={"class": "form-select"}),
            "status": forms.Select(attrs={"class": "form-select"}),
            "method": forms.Select(attrs={"class": "form-select"}),
            "compliance_standard": forms.Select(attrs={"class": "form-select"}),
            "fiscal_period": forms.Select(attrs={"class": "form-select"}),
            "notes": forms.Textarea(attrs={
                "class": "form-textarea",
                "rows": 3,
                "placeholder": "Why this schedule exists, in words a colleague can act on.",
            }),
        }
        labels = {
            "sales_order": "Sales order",
            "compliance_standard": "Compliance standard",
            "fiscal_period": "Fiscal period",
        }
        help_texts = {
            "sales_order": "The SCM 4.5 order this contract is recognised against.",
            "status": "Only an ACTIVE schedule can recognise revenue. A draft stays at zero "
                      "however far its recognition dates are in the past.",
            "method": "How revenue is released across the obligations.",
            "compliance_standard": "ASC 606, IFRS 15, or both — they agree on the arithmetic "
                                   "and differ in wording.",
            "fiscal_period": "Optional. The accounting period recognition is being booked into.",
        }

    def __init__(self, *args, tenant=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        # ``status`` is the ONE authorable status in 8.6, so its choices are narrowed to the
        # model's own list EXPLICITLY rather than inherited: a widget that ever drifted from
        # STATUS_CHOICES would let a value no template badge knows about be typed in, and the
        # page would render it through the {% else %} fallback forever.
        self.fields["status"].widget = forms.Select(
            choices=RevenueSchedule.STATUS_CHOICES, attrs={"class": "form-select"},
        )
        # TenantModelForm already narrows every ModelChoiceField to the tenant. These two are
        # spelled out anyway so the ORDERING is pinned — the order dropdown is read by eye.
        if self.tenant is not None:
            from apps.accounting.models import FiscalPeriod
            from apps.scm.models import SalesOrder

            self.fields["sales_order"].queryset = (
                SalesOrder.objects.filter(tenant=self.tenant)
                .select_related("customer")
                .order_by("-order_date", "-id")
            )
            self.fields["fiscal_period"].queryset = (
                FiscalPeriod.objects.filter(tenant=self.tenant).order_by("-start_date")
            )
        self.fields["fiscal_period"].required = False

    def clean(self):
        cleaned = super().clean()
        # Belt and braces on top of the narrowed querysets: a queryset filter alone rejects a
        # cross-tenant pk with "Select a valid choice", and this says WHY in the author's own
        # terms — the same helper every other 8.6 form uses.
        _reject_foreign(self, cleaned, ["sales_order", "fiscal_period"])
        return cleaned



class PerformanceObligationForm(TenantModelForm):
    """Add / edit ONE performance obligation on a schedule the parent view supplies.

    Constructed as ``PerformanceObligationForm(tenant=..., schedule=schedule)``. ``schedule`` is
    NOT in ``Meta.fields`` and never comes from the POST body — the obligation belongs to the
    schedule whose URL this was reached through, and letting the body choose the parent would
    be a way to append a promise to somebody else's contract.

    ``allocated_amount`` and ``recognized_amount`` are absent because they do not belong to a
    person: they are written by ``RevenueSchedule.recompute()`` in Python, from the contract
    value and these percentages. A clerk who could type the allocated amount would be stating
    the answer the schedule exists to work out.
    """

    class Meta:
        model = PerformanceObligation
        # Excluded, with the reason for each:
        #   schedule          — SET BY THE PARENT VIEW, never from user input.
        #   allocated_amount / recognized_amount — RECOMPUTED by RevenueSchedule.recompute(),
        #                        and editable=False, so no form could write them even if named.
        #   created_at / updated_at — auto_now* stamps.
        fields = [
            "sales_order_line",
            "item",
            "obligation_type",
            "description",
            "allocation_pct",
            "recognition_method",
            "recognize_on",
            "milestone_label",
            "evidence_reference",
        ]
        widgets = {
            "sales_order_line": forms.Select(attrs={"class": "form-select"}),
            "item": forms.Select(attrs={"class": "form-select"}),
            "obligation_type": forms.Select(attrs={"class": "form-select"}),
            "recognition_method": forms.Select(attrs={"class": "form-select"}),
            "description": forms.TextInput(attrs={
                "class": "form-input",
                "placeholder": "The distinct promise, in the words a customer would recognise.",
            }),
            "allocation_pct": forms.NumberInput(attrs={"class": "form-input", "step": "0.01"}),
            "recognize_on": forms.DateInput(attrs={"class": "form-input", "type": "date"}),
            "milestone_label": forms.TextInput(attrs={
                "class": "form-input",
                "placeholder": "e.g. 'Site handover signed off' — blank unless this is a milestone.",
            }),
            "evidence_reference": forms.TextInput(attrs={
                "class": "form-input",
                "placeholder": "The document or tracking reference proving it happened.",
            }),
        }
        labels = {
            "sales_order_line": "Order line",
            "item": "Item",
            "obligation_type": "Obligation type",
            "allocation_pct": "Allocation %",
            "recognition_method": "Recognition method",
            "recognize_on": "Recognise on",
        }

        help_texts = {
            "sales_order_line": "Optional. Only this schedule's own order lines are offered.",
            "item": "Optional. Links the promise to the catalogue.",
            "allocation_pct": "This obligation's share of the contract price. The obligations "
                              "on a schedule should add up to 100.",
            "recognize_on": "Leave blank only if the performance has no date yet. A blank date "
                            "is allocated but never recognised.",
            "milestone_label": "What 'done' looks like for this obligation.",
            "evidence_reference": "The proof. Never overwritten once written — a system that "
                                  "restated the evidence after the fact would be restating the "
                                  "conclusion too.",
        }

    def __init__(self, *args, tenant=None, schedule=None, **kwargs):
        super().__init__(*args, tenant=tenant, **kwargs)
        self.schedule = schedule
        from apps.scm.models import SalesOrderLine

        # ``SalesOrderLine`` is TENANT-LESS (reached through ``sales_order``), so
        # TenantModelForm cannot narrow this queryset for us. The ORDER scope below is the real
        # guard, and ``PerformanceObligation.clean()`` plus this form's ``clean()`` both re-check
        # it on the submitted value.
        if schedule is not None and schedule.sales_order_id:
            self.fields["sales_order_line"].queryset = (
                SalesOrderLine.objects.filter(sales_order_id=schedule.sales_order_id)
                .select_related("item")
                .order_by("id")
            )
        else:
            # No parent means there is no order to scope to, so offer nothing rather than every
            # line in the database. The form will refuse the submit regardless.
            self.fields["sales_order_line"].queryset = SalesOrderLine.objects.none()

    def clean(self):
        """Parent-match and cross-order guards.

        The parent is NOT a field on this form, so a mismatch with the URL's schedule is a
        non-field message — never ``add_error("schedule", …)``, which is the exact 0.20
        ``ValueError``, because the form has no ``schedule`` field to attach it to.
        """
        cleaned = super().clean()
        if self.schedule is None:
            self.add_error(None, "This obligation must be added through its revenue schedule.")
            return cleaned
        if self.instance.pk and self.instance.schedule_id != self.schedule.pk:
            self.add_error(None, "This obligation belongs to a different revenue schedule.")
            return cleaned

        order_id = self.schedule.sales_order_id
        chosen = cleaned.get("sales_order_line")
        if chosen is not None and chosen.sales_order_id != order_id:
            self.add_error(
                "sales_order_line",
                "That line belongs to a different order. Only this schedule's own order lines "
                "can be named here.",
            )
        _reject_foreign(self, cleaned, ["item"])
        return cleaned

