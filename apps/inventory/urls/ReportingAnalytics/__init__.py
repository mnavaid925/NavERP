"""Inventory 5.17 urls package."""
from .Reports import urlpatterns as _ra_reports
from .ReportSnapshots import urlpatterns as _ra_snapshots

urlpatterns = [*_ra_reports, *_ra_snapshots]
