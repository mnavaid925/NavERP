"""Shared imports for the HRM views package.

apps/hrm/views.py was split into this package (one sub-package per sub-module 3.1-3.41, one
module per entity, mirroring models/ forms/ urls/). Every entity module does
``from apps.hrm.views._common import *``; cross-sub-module private helpers live in
``views/_helpers.py``, sub-module-scoped ones in ``views/<SubModule>/_helpers.py``. The package
__init__ re-exports every view so the apps/hrm/urls/ package (``views.<name>``) is unchanged.

Imports inside these packages MUST be absolute: the original ``from .services import`` /
``from .analytics import`` were rewritten, since a relative import resolves to the wrong package
one level deeper.

The import block below is the ORIGINAL views.py header, verbatim.
"""
import math
import secrets
from datetime import date as _date, timedelta
from decimal import Decimal, InvalidOperation
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import (Avg, Count, DecimalField, ExpressionWrapper, F, Min, OuterRef, Prefetch, ProtectedError, Q, Subquery, Sum)
from django.db.models.functions import Coalesce, TruncMonth
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.views.decorators.http import require_POST
from django.conf import settings
from django.core.mail import send_mail
from apps.core.crud import _changed, crud_create, crud_delete, crud_detail, crud_edit, crud_list
from apps.core.decorators import tenant_admin_required
from apps.core.models import Employment, OrgUnit, Party, PartyRole
from apps.core.utils import write_audit_log
from apps.hrm.services import (
    apply_template_to_requisition,
    compute_leave_encashment,
    generate_approval_chain,
    generate_clearance_checklist,
    generate_offer_approval_chain,
    generate_preboarding_checklist,
    generate_tasks_from_template,
)
import bisect  # noqa: E402
import json  # noqa: E402
from collections import Counter  # noqa: E402
from django.contrib.auth import get_user_model as _get_user_model  # noqa: E402
from apps.hrm.analytics import (  # noqa: E402
    compute_widget as _compute_widget, _turnover_rate, _headcount_trend_series,
    _present_absent_counts, _attrition_risk_scores,
)
